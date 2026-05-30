# -*- coding: utf-8 -*-
"""
验证：生产成本分摊页「制造费用」= 三来源按产线相加。

  1. 制造费用成本页「分类费用汇总」合计
  2. 公共费用分摊页「按类别分摊」
  3. 间接人工成本页「制造费用汇总」合计

运行：python scripts/validate_production_cost_manufacturing.py
"""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

TOLERANCE = 0.01
CATEGORIES = ["电视", "电脑", "冰箱", "空调", "洗衣机"]


def pick_session():
    from app.models.database import SessionDataset, UserSession

    required = {"extracted_data_manual", "disassembly_data"}
    for s in UserSession.query.order_by(UserSession.last_accessed.desc()).limit(50).all():
        keys = {d.data_key for d in SessionDataset.query.filter_by(session_id=s.session_id).all()}
        if keys & required:
            return s.session_id
    return None


def main() -> int:
    from app import create_app
    from app.api.cost_forecast_api import (
        calculate_indirect_labor_cost,
        calculate_manufacturing_cost,
        INDIRECT_LABOR_PAGE_INCLUDE_NO_OPENING,
        calculate_screen_cost_allocation,
        collect_production_manufacturing_cost_by_category,
        summarize_indirect_labor_manufacturing_by_category,
        summarize_manufacturing_cost_category_totals,
    )
    from app.models.compatibility import AppDataManagerAdapter

    app = create_app("development")
    with app.app_context():
        sid = pick_session()
        if not sid:
            print("no session with extracted_data_manual + disassembly_data")
            return 2

        app_data = AppDataManagerAdapter.get_instance(sid)
        period = 1

        mfg_result = calculate_manufacturing_cost(app_data, period)
        mfg_part = summarize_manufacturing_cost_category_totals(mfg_result)

        screen_result = calculate_screen_cost_allocation(app_data, period)
        pub_part = (screen_result.get("allocation") or {}).get("category_allocation") or {}

        indirect_result = calculate_indirect_labor_cost(
            app_data, period, include_no_opening_columns=INDIRECT_LABOR_PAGE_INCLUDE_NO_OPENING
        )
        ind_part = summarize_indirect_labor_manufacturing_by_category(indirect_result)

        combined = collect_production_manufacturing_cost_by_category(app_data, period)

        failed = 0
        print(f"session={sid} period={period}")
        print(f"{'产线':<8} {'制造费用成本':>14} {'公共分摊':>14} {'间接制造费用':>14} {'三源合计':>14} {'分摊页':>14} {'差额':>10}")
        print("-" * 95)

        for cat in CATEGORIES:
            expected = (
                mfg_part.get(cat, 0.0)
                + float(pub_part.get(cat, 0) or 0)
                + ind_part.get(cat, 0.0)
            )
            actual = combined.get(cat, 0.0)
            diff = actual - expected
            ok = abs(diff) <= TOLERANCE
            if not ok:
                failed += 1
            flag = "OK" if ok else "FAIL"
            mfg_val = mfg_part.get(cat, 0.0)
            pub_val = float(pub_part.get(cat, 0) or 0)
            ind_val = ind_part.get(cat, 0.0)
            print(
                f"{cat:<8} {mfg_val:>14.2f} {pub_val:>14.2f} {ind_val:>14.2f} "
                f"{expected:>14.2f} {actual:>14.2f} {diff:>10.2f}  {flag}"
            )

        total_actual = sum(combined.get(c, 0.0) for c in CATEGORIES)
        total_expected = (
            sum(mfg_part.get(c, 0.0) for c in CATEGORIES)
            + sum(float(pub_part.get(c, 0) or 0) for c in CATEGORIES)
            + sum(ind_part.get(c, 0.0) for c in CATEGORIES)
        )
        total_diff = total_actual - total_expected
        if abs(total_diff) > TOLERANCE:
            failed += 1
        print("-" * 50)
        print(
            f"{'合计':<8} {total_actual:>14.2f} {total_expected:>14.2f} {total_diff:>10.2f}"
        )

        if failed:
            print(f"\n{failed} 项未通过（容差 {TOLERANCE} 元）")
            return 1
        print("\n全部通过")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
