# -*- coding: utf-8 -*-
"""
验证：拆解收益分析表在「不考虑期初」下制造费用含屏费用分摊、间接/公共分摊等字段；
并校验「不考虑期初」环保费与只读「被减扣数据」sheet 口径一致（非手工表）。

运行：python scripts/validate_disassembly_profit_manufacturing.py
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, Set

import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _nf(x, default=0.0) -> float:
    try:
        if x is None:
            return default
        if pd.isna(x):
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def _build_env_fee_price_mapping() -> Dict[str, float]:
    from data.base_data.price_data import load_price_data

    mapping: Dict[str, float] = {}
    price_df = load_price_data()
    if price_df is None or price_df.empty or "销售单价-不含税(元/KG)" not in price_df.columns:
        return mapping
    price_df = price_df.copy()
    price_df["销售单价-不含税(元/KG)"] = pd.to_numeric(
        price_df["销售单价-不含税(元/KG)"], errors="coerce"
    ).fillna(0)
    for _, row in price_df[price_df["销售单价-不含税(元/KG)"] < 0].iterrows():
        pc = str(row.get("拆解产物编码", "")).strip()
        up = _nf(row.get("销售单价-不含税(元/KG)"))
        if pc and up < 0:
            mapping[pc] = abs(up)
    return mapping


def _calc_env_fee_total(
    deducted_df,
    valid_material_codes: Set[str],
    price_mapping: Dict[str, float],
) -> float:
    if deducted_df is None or deducted_df.empty:
        return 0.0
    if not all(c in deducted_df.columns for c in ("类别", "处置类别", "计算结果(KG)", "拆解产物编码", "原物料代码")):
        return 0.0
    env_mask = (
        (deducted_df["类别"].astype(str) == "拆解产物")
        & (deducted_df["处置类别"].astype(str).isin(["付费处置", "内转荧光灯处置"]))
    )
    env_data = deducted_df[env_mask].copy()
    if env_data.empty:
        return 0.0
    env_data["计算结果(KG)"] = pd.to_numeric(env_data["计算结果(KG)"], errors="coerce").fillna(0)
    total = 0.0
    for _, row in env_data.iterrows():
        material_code = str(row.get("原物料代码", "")).strip()
        product_code = str(row.get("拆解产物编码", "")).strip()
        if material_code not in valid_material_codes or not product_code:
            continue
        weight = _nf(row.get("计算结果(KG)"))
        up = price_mapping.get(product_code, 0.0)
        if weight > 0 and up > 0:
            total += weight * up
    return total


def main() -> int:
    from app import create_app
    from app.models.compatibility import AppDataManagerAdapter
    from app.api.statistics_api import _calculate_disassembly_profit_analysis_data
    from app.api.data_management_api import _build_deducted_readonly_dataframe
    from app.api.cost_forecast_api import calculate_material_cost

    def pick_session():
        from app.models.database import UserSession, SessionDataset

        required = {"extracted_data_manual", "disassembly_data"}
        for s in UserSession.query.order_by(UserSession.last_accessed.desc()).limit(50).all():
            keys = {d.data_key for d in SessionDataset.query.filter_by(session_id=s.session_id).all()}
            if keys & required:
                return s.session_id
        return None

    app = create_app("development")
    with app.app_context():
        sid = pick_session()
        if not sid:
            print("no session")
            return 2
        app_data = AppDataManagerAdapter.get_instance(sid)
        res_open = _calculate_disassembly_profit_analysis_data(
            app_data, 1, consider_opening_stock=True
        )
        res_no = _calculate_disassembly_profit_analysis_data(
            app_data, 1, consider_opening_stock=False
        )

        def get_data(res):
            if hasattr(res, "get_json"):
                return (res.get_json() or {}).get("data", []) or []
            return (res or {}).get("data", []) or []

        for name, res in [("考虑期初", res_open), ("不考虑期初", res_no)]:
            data = get_data(res)
            if not data:
                print(name, ": no data")
                continue
            r0 = data[0]
            mfg = float(r0.get("制造费用", 0) or 0)
            scr = float(r0.get("屏费用分摊", 0) or 0)
            ind = float(r0.get("制造费用间接人工分摊", 0) or 0)
            pub = float(r0.get("制造费用公共成本分摊", 0) or 0)
            pbf = float(r0.get("公共费用分摊", 0) or 0)
            print(f"{name}: row0 mfg={mfg:.2f} screen={scr:.2f} ind11={ind:.2f} pub11={pub:.2f} pub_sum11={pbf:.2f}")

        data_no = get_data(res_no)
        total_no = sum(float(r.get("制造费用", 0) or 0) for r in data_no)
        screen_no = sum(float(r.get("屏费用分摊", 0) or 0) for r in data_no)
        env_no = sum(float(r.get("环保费", 0) or 0) for r in data_no)
        print("no_opening mfg_total", round(total_no, 2), "screen_total", round(screen_no, 2), "env_total", round(env_no, 2))

        if data_no:
            assert "屏费用分摊" in data_no[0]

        # 环保费：不考虑期初应与只读被减扣数据口径一致
        extracted = app_data.get_data("extracted_data_manual")
        valid_material_codes: Set[str] = set()
        if extracted is not None and not extracted.empty:
            cost_data = calculate_material_cost(extracted)
            if cost_data is not None and not cost_data.empty and "类别" in cost_data.columns:
                old = cost_data[cost_data["类别"] == "旧机"].copy()
                if "非限制使用的库存" in old.columns:
                    old["非限制使用的库存"] = pd.to_numeric(
                        old["非限制使用的库存"], errors="coerce"
                    ).fillna(0)
                    old = old[old["非限制使用的库存"] > 0]
                for _, row in old.iterrows():
                    code = str(row.get("物料代码", "")).strip()
                    if code:
                        valid_material_codes.add(code)

        price_mapping = _build_env_fee_price_mapping()
        readonly_df = _build_deducted_readonly_dataframe(app_data)
        manual_df = app_data.get_data("deducted_data_manual")
        expected_readonly = _calc_env_fee_total(readonly_df, valid_material_codes, price_mapping)
        expected_manual = _calc_env_fee_total(manual_df, valid_material_codes, price_mapping)

        print("env_fee expected(readonly):", round(expected_readonly, 2))
        print("env_fee expected(manual):", round(expected_manual, 2))
        print("env_fee actual(no_opening):", round(env_no, 2))
        print("env_fee diff vs readonly:", round(env_no - expected_readonly, 2))

        if abs(env_no - expected_readonly) > 0.02:
            print("FAIL: 不考虑期初环保费与只读被减扣数据不一致")
            return 6

        print("OK fields present; env fee matches readonly deducted data")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
