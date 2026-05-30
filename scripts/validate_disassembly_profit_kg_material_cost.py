"""
验证：当期拆解收益测算分析表 - KG 行材料成本 = 提取结果(手工)「单价」× 拆解数量(KG)。

运行方式（在项目根目录）：
  python scripts/validate_disassembly_profit_kg_material_cost.py
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional


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
    from app.models.database import UserSession, SessionDataset

    required_any = {
        "extracted_data_manual",
        "deducted_data_manual",
    }

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


def _build_price_by_code(extracted_data, extracted_readonly=None) -> Dict[str, float]:
    """从「提取结果」构建物料代码→单价映射（不限类别，优先只读 extracted_data）。"""
    import pandas as pd

    price_by_code: Dict[str, float] = {}
    source = extracted_readonly
    if source is None or source.empty:
        source = extracted_data
    if source is None or source.empty:
        return price_by_code
    if "物料代码" not in source.columns or "单价" not in source.columns:
        return price_by_code

    price_df = source.copy()
    price_df["单价"] = pd.to_numeric(price_df["单价"], errors="coerce").fillna(0)
    for _, row in price_df.iterrows():
        code = _normalize_code(row.get("物料代码", ""))
        if not code:
            continue
        price = float(row.get("单价", 0) or 0)
        if code not in price_by_code or (price > 0 and price_by_code[code] == 0):
            price_by_code[code] = price
    return price_by_code


def main() -> int:
    from app import create_app
    from app.models.compatibility import AppDataManagerAdapter
    from app.api.statistics_api import _calculate_disassembly_profit_analysis_data

    app = create_app("development")
    with app.app_context():
        session_id = _pick_candidate_session_id()
        if not session_id:
            print("未找到可用于验证的 session_id（数据库里没有相关会话数据）。")
            return 2

        app_data = AppDataManagerAdapter.get_instance(session_id)
        prediction_period = 1

        extracted_data = app_data.get_data("extracted_data_manual")
        extracted_readonly = app_data.get_data("extracted_data")
        price_by_code = _build_price_by_code(extracted_data, extracted_readonly)

        result = _calculate_disassembly_profit_analysis_data(
            app_data, prediction_period, consider_opening_stock=True
        )
        if hasattr(result, "get_json"):
            payload = result.get_json() or {}
            data = payload.get("data", []) or []
        else:
            data = (result or {}).get("data", []) or []

        if not data:
            print(f"分析表无数据（session_id={session_id}）。")
            return 4

        kg_rows = [r for r in data if r.get("单位") == "KG"]
        print("session_id:", session_id)
        print("rows_total:", len(data), "rows_kg:", len(kg_rows))

        if not kg_rows:
            print("没有 KG 行可用于验证。")
            return 5

        mismatches = []
        for row in kg_rows:
            code = _normalize_code(row.get("物料代码", ""))
            qty = float(row.get("拆解数量", 0) or 0)
            actual = float(row.get("材料成本", 0) or 0)
            unit_price = price_by_code.get(code, 0)
            expected = unit_price * qty
            diff = abs(actual - expected)
            if diff > 0.01:
                mismatches.append(
                    {
                        "code": code,
                        "qty": qty,
                        "unit_price": unit_price,
                        "expected": expected,
                        "actual": actual,
                        "diff": diff,
                    }
                )

        print("kg_rows_checked:", len(kg_rows))
        print("mismatches:", len(mismatches))

        preview_count = min(5, len(kg_rows))
        print(f"kg_preview (code -> 单价×数量=期望, 实际):")
        for row in kg_rows[:preview_count]:
            code = _normalize_code(row.get("物料代码", ""))
            qty = float(row.get("拆解数量", 0) or 0)
            unit_price = price_by_code.get(code, 0)
            expected = unit_price * qty
            actual = float(row.get("材料成本", 0) or 0)
            print(
                f"  {code} -> {unit_price}×{qty}={round(expected, 2)}, actual={round(actual, 2)}"
            )

        if mismatches:
            print("mismatch_samples:")
            for item in mismatches[:5]:
                print(" ", item)
            return 6

        print("验证通过：所有 KG 行材料成本 = 单价 × 拆解数量(KG)")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
