"""
验证：当期拆解收益测算分析表 - 直接人工归集是否覆盖 KG 独立行。

运行方式（在项目根目录）：
  python scripts/validate_disassembly_profit_direct_labor.py
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional


# 确保项目根目录在 sys.path 中（避免因工作目录/编码问题导致 import 失败）
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


def _pick_candidate_session_id() -> Optional[str]:
    """从数据库里找一个包含关键数据集的 session_id。"""
    from app.models.database import UserSession, SessionDataset

    required_any = {
        "extracted_data_manual",
        "disassembly_data",
        "deducted_data_manual",
        "deep_processing_data",
    }

    # 先看最近活跃会话
    sessions = (
        UserSession.query.order_by(UserSession.last_accessed.desc())
        .limit(50)
        .all()
    )
    for s in sessions:
        keys = {
            d.data_key
            for d in SessionDataset.query.filter_by(session_id=s.session_id).all()
        }
        if keys & required_any:
            return s.session_id
    return None


def _calc_expected_direct_labor_by_code(
    direct_labor_result: Dict[str, Any],
) -> Dict[str, float]:
    """
    用“直接人工成本”接口返回结构，按物料代码/原物料代码汇总：
      直接人工 = 计件工资(旧机+一次拆解产物+打包铁/一破) + 分摊固定成本(黑电/白电/冰箱/金属打包/塑料)
    """
    by_code: Dict[str, float] = {}

    # 计件工资：旧机按物料代码
    for item in direct_labor_result.get("part1_details", []) or []:
        code = _normalize_code(item.get("物料代码"))
        if not code:
            continue
        by_code[code] = by_code.get(code, 0.0) + float(item.get("工资", 0) or 0)

    # 计件工资：一次拆解产物按原物料代码
    for item in direct_labor_result.get("part2_details", []) or []:
        code = _normalize_code(item.get("原物料代码"))
        if not code:
            continue
        by_code[code] = by_code.get(code, 0.0) + float(item.get("工资", 0) or 0)

    # 计件工资：深加工仅打包铁/一破按原物料代码
    for item in direct_labor_result.get("part3_details", []) or []:
        cat = str(item.get("类别", "")).strip()
        if cat not in ("打包铁", "一破"):
            continue
        code = _normalize_code(item.get("原物料代码"))
        if not code:
            continue
        by_code[code] = by_code.get(code, 0.0) + float(item.get("工资", 0) or 0)

    # 分摊固定成本
    category_details = direct_labor_result.get("category_details", {}) or {}

    # 黑电/白电/冰箱：按物料代码
    for cat in ("黑电", "白电", "冰箱"):
        for alloc in (category_details.get(cat, {}) or {}).get("item_allocations", []) or []:
            item = alloc.get("item", {}) or {}
            code = _normalize_code(item.get("物料代码"))
            if not code:
                continue
            by_code[code] = by_code.get(code, 0.0) + float(alloc.get("fixed_cost", 0) or 0)

    # 金属打包/塑料：按原物料代码（此处不做回查兜底，仅用于验证 KG 行是否能出值）
    for cat in ("金属打包", "塑料"):
        for alloc in (category_details.get(cat, {}) or {}).get("item_allocations", []) or []:
            item = alloc.get("item", {}) or {}
            code = _normalize_code(item.get("原物料代码"))
            if not code:
                continue
            by_code[code] = by_code.get(code, 0.0) + float(alloc.get("fixed_cost", 0) or 0)

    return by_code


def main() -> int:
    from app import create_app
    from app.models.compatibility import AppDataManagerAdapter
    from app.api.cost_forecast_api import calculate_direct_labor_cost
    from app.api.statistics_api import _calculate_disassembly_profit_analysis_data

    app = create_app("development")
    with app.app_context():
        session_id = _pick_candidate_session_id()
        if not session_id:
            print("未找到可用于验证的 session_id（数据库里没有相关会话数据）。")
            return 2

        app_data = AppDataManagerAdapter.get_instance(session_id)

        # 预测期数先用 1
        prediction_period = 1

        # 直接人工成本（来源）
        direct_labor_result = calculate_direct_labor_cost(app_data, prediction_period)
        if not direct_labor_result or direct_labor_result.get("error"):
            print("直接人工成本计算失败：", direct_labor_result.get("error") if direct_labor_result else "empty")
            return 3

        expected_by_code = _calc_expected_direct_labor_by_code(direct_labor_result)

        # 当期拆解收益测算分析表（目标）
        result = _calculate_disassembly_profit_analysis_data(app_data, prediction_period)

        # 兼容内部函数偶尔返回 jsonify(Response) 的情况
        data: List[Dict[str, Any]]
        if hasattr(result, "get_json"):
            payload = result.get_json() or {}
            data = payload.get("data", []) or []
        else:
            data = (result or {}).get("data", []) or []

        if not data:
            print(f"分析表无数据（session_id={session_id}）。")
            return 4

        tai_codes = {_normalize_code(r.get("物料代码", "")) for r in data if r.get("单位") == "台"}
        kg_rows = [r for r in data if r.get("单位") == "KG"]
        kg_codes = {_normalize_code(r.get("物料代码", "")) for r in kg_rows}
        kg_only_codes = sorted([c for c in kg_codes if c and c not in tai_codes])

        print("session_id:", session_id)
        print("rows_total:", len(data), "rows_kg:", len(kg_rows), "kg_only_codes:", len(kg_only_codes))

        # 找一个 kg_only 物料做抽样
        sample_code = None
        for c in kg_only_codes:
            if c in expected_by_code:
                sample_code = c
                break
        if not sample_code and kg_only_codes:
            sample_code = kg_only_codes[0]

        if not sample_code:
            print("没有找到 KG 独立物料代码用于抽样验证。")
            return 5

        # 取分析表中的该 code（KG行）直接人工
        sample_rows = [r for r in kg_rows if _normalize_code(r.get("物料代码", "")) == sample_code]
        sample_direct_labor = float(sample_rows[0].get("直接人工", 0) or 0) if sample_rows else 0.0

        expected = float(expected_by_code.get(sample_code, 0.0))

        print("sample_code:", sample_code)
        print("analysis.direct_labor(KG_row):", round(sample_direct_labor, 2))
        print("expected.direct_labor(from_cost_page):", round(expected, 2))
        print("diff:", round(sample_direct_labor - expected, 2))

        # 再额外打印前 5 个 KG-only 的直接人工，便于肉眼确认不再全是 0
        print("kg_only_preview (code -> direct_labor):")
        kg_only_set = set(kg_only_codes)
        printed = 0
        for r in kg_rows:
            code = _normalize_code(r.get("物料代码", ""))
            if code and code in kg_only_set:
                print(" ", code, "->", r.get("直接人工", 0))
                kg_only_set.remove(code)
                printed += 1
                if printed >= 5:
                    break

        # ---------- 不考虑期初库存：直接人工为另一套口径（③⑤ 与上表不同）----------
        result_no = _calculate_disassembly_profit_analysis_data(
            app_data, prediction_period, consider_opening_stock=False
        )
        if hasattr(result_no, "get_json"):
            payload_no = result_no.get_json() or {}
            data_no = payload_no.get("data", []) or []
        else:
            data_no = (result_no or {}).get("data", []) or []
        if data_no:
            total_dl_open = sum(float(r.get("直接人工", 0) or 0) for r in data)
            total_dl_no = sum(float(r.get("直接人工", 0) or 0) for r in data_no)
            print("\n[不考虑期初库存] 直接人工列合计:", round(total_dl_no, 2))
            print("[考虑期初库存]   直接人工列合计:", round(total_dl_open, 2))
            print(
                "(不考虑期初时「直接人工」为①②③④⑤规则：③⑤ 见 statistics_api consider_opening_stock=False)"
            )
        else:
            print("\n[不考虑期初库存] 分析表无数据，跳过对比。")

        return 0


if __name__ == "__main__":
    raise SystemExit(main())

