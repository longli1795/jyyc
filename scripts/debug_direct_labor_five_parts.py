# -*- coding: utf-8 -*-
"""
按物料代码拆分「不考虑期初」直接人工 ①～⑤，与手算逐项对比。

用法（项目根目录）：
  python scripts/debug_direct_labor_five_parts.py [物料代码] [session_id]

未传 session_id 时自动从数据库挑一个会话。

Windows 下若用管道截取输出，请加无缓冲，否则可能长时间看不到打印：
  set PYTHONUNBUFFERED=1
  python -u scripts/debug_direct_labor_five_parts.py 810978870
"""
from __future__ import annotations

import math
import os
import sys
from typing import Any, Dict, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _normalize_code(value: Any) -> str:
    if value is None:
        return ""
    try:
        import pandas as pd

        if pd.isna(value):
            return ""
    except Exception:
        pass
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return ""
    if s.endswith(".0"):
        s = s[:-2]
    return s


def _finite_float(x, default=0.0) -> float:
    try:
        if x is None:
            return default
        try:
            import pandas as pd

            if pd.isna(x):
                return default
        except Exception:
            pass
        v = float(x)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(v):
        return default
    return v


def _pick_session_id() -> Optional[str]:
    from app.models.database import UserSession, SessionDataset

    required_any = {"extracted_data_manual", "deducted_data_manual"}
    sessions = (
        UserSession.query.order_by(UserSession.last_accessed.desc()).limit(50).all()
    )
    for s in sessions:
        keys = {d.data_key for d in SessionDataset.query.filter_by(session_id=s.session_id).all()}
        if keys & required_any:
            return s.session_id
    return None


def main() -> int:
    target = _normalize_code(sys.argv[1] if len(sys.argv) > 1 else "810978870")
    session_id = sys.argv[2] if len(sys.argv) > 2 else None

    from app import create_app
    from app.models.compatibility import AppDataManagerAdapter
    from app.api.cost_forecast_api import (
        calculate_direct_labor_cost,
        calculate_material_cost,
        classify_by_product_name,
    )
    from data.base_data.deep_processing_data import DEEP_PROCESSING_DATA
    from data.base_data.labor_cost_data import get_labor_cost_dataframe
    from data.base_data.salary_accounting_data import get_salary_accounting_dataframe
    import pandas as pd

    app = create_app("development")
    with app.app_context():
        if not session_id:
            session_id = _pick_session_id()
        if not session_id:
            print("未找到 session_id，请传入：python scripts/debug_direct_labor_five_parts.py 810978870 <session_id>")
            return 2

        app_data = AppDataManagerAdapter.get_instance(session_id)
        prediction_period = 1

        extracted_data = app_data.get_data("extracted_data_manual")
        if extracted_data is None or extracted_data.empty:
            print("无 extracted_data_manual")
            return 3

        cost_data = calculate_material_cost(extracted_data)
        if cost_data is None or cost_data.empty:
            print("无 cost_data")
            return 4

        valid_material_codes: set = set()
        if "类别" in cost_data.columns and "物料代码" in cost_data.columns:
            old_machine_data = cost_data[cost_data["类别"] == "旧机"].copy()
            if "非限制使用的库存" in old_machine_data.columns:
                old_machine_data["非限制使用的库存"] = pd.to_numeric(
                    old_machine_data["非限制使用的库存"], errors="coerce"
                ).fillna(0)
                for _, row in old_machine_data[old_machine_data["非限制使用的库存"] > 0].iterrows():
                    mc = str(row.get("物料代码", "")).strip()
                    if mc:
                        valid_material_codes.add(mc)

        allowed_material_codes = set(valid_material_codes)
        if target not in allowed_material_codes:
            print(f"物料 {target} 不在 valid_material_codes（拆解物原料成本旧机且数量>0）中，当前样本含：{sorted(valid_material_codes)[:20]}...")
            return 5

        direct_labor_result = calculate_direct_labor_cost(app_data, prediction_period)
        if not direct_labor_result or direct_labor_result.get("error"):
            print("calculate_direct_labor_cost 失败:", direct_labor_result)
            return 6

        original_data = app_data.get_data("disassembly_data")
        deducted_data = app_data.get_data("deducted_data_manual")
        deep_processing_data = app_data.get_data("deep_processing_data")

        # ---------- ① ----------
        p1 = 0.0
        for item in direct_labor_result.get("part1_details") or []:
            if _normalize_code(item.get("物料代码", "")) == target:
                p1 += float(item.get("工资", 0) or 0)

        # ---------- ②（与 statistics_api 一致，part2_wage_by_code 含全部本表物料）----------
        part2_wage_by_code: Dict[str, float] = {}
        for item in direct_labor_result.get("part2_details") or []:
            wage = float(item.get("工资", 0) or 0)
            mc = _normalize_code(item.get("原物料代码", ""))
            if mc and mc in allowed_material_codes:
                part2_wage_by_code[mc] = part2_wage_by_code.get(mc, 0.0) + wage
            else:
                product_code = _normalize_code(item.get("拆解产物编码", ""))
                if original_data is not None and not original_data.empty:
                    if "类别" in original_data.columns and "拆解产物编码" in original_data.columns:
                        product_mask = original_data["类别"] == "拆解产物"
                        product_data = original_data[product_mask]
                        matched_rows = product_data[
                            product_data["拆解产物编码"]
                            .astype(str)
                            .str.strip()
                            .str.replace(r"\.0$", "", regex=True)
                            == product_code
                        ]
                        for _, row in matched_rows.iterrows():
                            mc2 = _normalize_code(row.get("原物料代码", ""))
                            if mc2 and mc2 in allowed_material_codes:
                                part2_wage_by_code[mc2] = part2_wage_by_code.get(mc2, 0.0) + wage
        p2 = _finite_float(part2_wage_by_code.get(target, 0), 0.0)

        # ---------- ③ + pack/yipo（与 statistics_api 不考虑期初分支一致）----------
        pack_wage_by_code: Dict[str, float] = {}
        yipo_wage_by_code: Dict[str, float] = {}
        p3_target = 0.0

        coeff_by_first_dl: Dict[str, list] = {}
        for r in DEEP_PROCESSING_DATA:
            first = str(r.get("拆解产物编码", "")).strip()
            if first:
                coeff_by_first_dl.setdefault(first, []).append(r)

        labor_df = get_labor_cost_dataframe()
        labor_cost_dict: Dict[tuple, float] = {}
        if labor_df is not None and not labor_df.empty:
            for _, lr in labor_df.iterrows():
                code = _normalize_code(lr.get("R3系统代码", ""))
                if not code:
                    continue
                cat = str(lr.get("类别", "")).strip()
                pr = float(lr.get("生产计件单价", 0) or 0) if pd.notna(lr.get("生产计件单价")) else 0.0
                labor_cost_dict[(code, cat)] = pr

        deep_dl = ["内转屏处置", "内转印制板处置", "深加工-打包铁", "深加工-塑料一破"]
        if deducted_data is not None and not deducted_data.empty:
            if all(c in deducted_data.columns for c in ("类别", "处置类别", "原物料代码", "拆解产物编码", "计算结果(KG)")):
                mask_dl = (deducted_data["类别"] == "拆解产物") & (
                    deducted_data["处置类别"].astype(str).str.strip().isin(deep_dl)
                )
                filt = deducted_data[mask_dl].copy()
                filt["计算结果(KG)"] = pd.to_numeric(filt["计算结果(KG)"], errors="coerce").fillna(0)
                for _, drow in filt.iterrows():
                    mc = _normalize_code(drow.get("原物料代码", ""))
                    if not mc or mc not in allowed_material_codes:
                        continue
                    product_code = str(drow.get("拆解产物编码", "")).strip()
                    weight = float(drow.get("计算结果(KG)", 0))
                    if weight <= 0:
                        continue
                    for coeff in coeff_by_first_dl.get(product_code, []):
                        io_ratio = _finite_float(coeff.get("深加工投入产出比例", 0), 0.0)
                        coef = _finite_float(coeff.get("深加工拆解系数", 0), 0.0)
                        deep_product_code = _normalize_code(coeff.get("深加工产物编码", ""))
                        if not deep_product_code:
                            continue
                        deep_weight = weight * io_ratio * coef
                        if deep_weight <= 0:
                            continue
                        unit_price = 0.0
                        matched_cat = None
                        for category in ["一破", "打包铁", "屏"]:
                            key = (deep_product_code, category)
                            if key in labor_cost_dict and labor_cost_dict[key] > 0:
                                unit_price = labor_cost_dict[key]
                                matched_cat = category
                                break
                        if unit_price <= 0 or matched_cat == "屏":
                            continue
                        wage = deep_weight * unit_price
                        if mc == target:
                            p3_target += wage
                        if matched_cat == "打包铁":
                            pack_wage_by_code[mc] = pack_wage_by_code.get(mc, 0.0) + wage
                        elif matched_cat == "一破":
                            yipo_wage_by_code[mc] = yipo_wage_by_code.get(mc, 0.0) + wage

        # ---------- ④ ----------
        p4 = 0.0
        category_details = direct_labor_result.get("category_details", {}) or {}
        for cat in ("黑电", "白电", "冰箱"):
            for alloc in (category_details.get(cat, {}) or {}).get("item_allocations", []) or []:
                item = alloc.get("item", {}) or {}
                if _normalize_code(item.get("物料代码", "")) == target:
                    p4 += float(alloc.get("fixed_cost", 0) or 0)

        # ---------- ⑤ ----------
        total_pack = _finite_float(sum(pack_wage_by_code.values()), 0.0)
        part2_total = _finite_float(sum(part2_wage_by_code.values()), 0.0)
        total_yipo = _finite_float(sum(yipo_wage_by_code.values()), 0.0)
        plastic_denom = part2_total + total_yipo
        if not math.isfinite(plastic_denom):
            plastic_denom = 0.0

        def _salary_bundle(row):
            return (
                _finite_float(row.get("平均工资（元/月/人）"), 0.0)
                + _finite_float(row.get("奖励/补助（元/月）"), 0.0)
                + _finite_float(row.get("餐补（元/月/人）"), 0.0)
                + _finite_float(row.get("年终奖（元/人）"), 0.0)
                + _finite_float(row.get("养老保险费（元/月/人）"), 0.0)
                + _finite_float(row.get("失业保险费（元/月/人）"), 0.0)
                + _finite_float(row.get("医疗/生育保险费（元/月/人）"), 0.0)
                + _finite_float(row.get("工伤保险费（元/月/人）"), 0.0)
                + _finite_float(row.get("住房公积金（元/月/人）"), 0.0)
            )

        metal_pool = 0.0
        plastic_pool = 0.0
        sdf = get_salary_accounting_dataframe()
        if sdf is not None and not sdf.empty:
            for _, srow in sdf.iterrows():
                pos = str(srow.get("岗位", "")).strip()
                pb = _finite_float(srow.get("人员基础配置"), 0.0)
                if pos == "金属打包":
                    metal_pool += _finite_float(pb * prediction_period * _salary_bundle(srow), 0.0)
                elif pos == "塑料破碎分选":
                    plastic_pool += _finite_float(pb * prediction_period * _salary_bundle(srow), 0.0)

        pw = _finite_float(pack_wage_by_code.get(target, 0), 0.0)
        p2m = _finite_float(part2_wage_by_code.get(target, 0), 0.0)
        ypm = _finite_float(yipo_wage_by_code.get(target, 0), 0.0)
        add_m = _finite_float((pw / total_pack) * metal_pool, 0.0) if total_pack > 0 else 0.0
        add_p = (
            _finite_float(((p2m + ypm) / plastic_denom) * plastic_pool, 0.0)
            if plastic_denom > 0
            else 0.0
        )
        p5 = add_m + add_p

        total = p1 + p2 + p3_target + p4 + p5

        exp = {"①": 63.6, "②": 0.0, "③": 29.2, "④": 280.88, "⑤": 74.41, "合计": 448.09}
        got = {"①": p1, "②": p2, "③": p3_target, "④": p4, "⑤": p5, "合计": total}

        print("session_id:", session_id)
        print("物料代码:", target)
        print("--- 分项（程序） vs 手算 ---")
        for k in ("①", "②", "③", "④", "⑤", "合计"):
            g = got[k]
            e = exp[k]
            ok = abs(g - e) < 0.06
            flag = "OK" if ok else "DIFF"
            print(f"  {k}: 程序={g:.6f}  手算={e}  差={g - e:+.4f}  [{flag}]")
        print("--- ⑤ 明细 ---")
        print(f"  total_pack_wage(全物料)={total_pack:.4f}  本物料打包铁计件 pw={pw:.6f}")
        print(f"  part2_total_table={part2_total:.4f}  total_yipo={total_yipo:.4f}  plastic_denom={plastic_denom:.4f}")
        print(f"  本物料② p2={p2m:.6f}  本物料③一破 yp={ypm:.6f}  metal_pool={metal_pool:.4f}  plastic_pool={plastic_pool:.4f}")
        print(f"  add_m(金属)={add_m:.6f}  add_p(塑料)={add_p:.6f}")

        # 与接口整行对比
        from app.api.statistics_api import _calculate_disassembly_profit_analysis_data

        res = _calculate_disassembly_profit_analysis_data(
            app_data, prediction_period, consider_opening_stock=False
        )
        if hasattr(res, "get_json"):
            res = res.get_json() or {}
        rows = res.get("data", []) if isinstance(res, dict) else []
        api_dl = None
        for r in rows:
            if _normalize_code(r.get("物料代码", "")) == target and r.get("单位") == "台":
                api_dl = float(r.get("直接人工", 0) or 0)
                break
        if api_dl is not None:
            print("--- API 行直接人工(台) ---")
            print(f"  直接人工={api_dl}  与上面合计差={api_dl - total:+.6f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
