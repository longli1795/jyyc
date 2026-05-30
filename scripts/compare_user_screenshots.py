# -*- coding: utf-8 -*-
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

USER_MFG = {
    "电视": 44641.25,
    "电脑": 115782.42,
    "冰箱": 586705.91,
    "空调": 146701.84,
    "洗衣机": 108081.83,
}
USER_PUB = {
    "电视": 23375.52,
    "电脑": 44061.04,
    "冰箱": 141508.30,
    "空调": 400771.12,
    "洗衣机": 89029.43,
}
USER_IND = {
    "电视": 39063.73,
    "电脑": 117946.22,
    "冰箱": 209116.17,
    "空调": 142167.43,
    "洗衣机": 149114.11,
}
USER_SHOWN = {
    "电视": 122624.05,
    "电脑": 277245.89,
    "冰箱": 937330.38,
    "空调": 685694.32,
    "洗衣机": 333040.77,
}
CATS = ["电视", "电脑", "冰箱", "空调", "洗衣机"]


def main():
    from app import create_app
    from app.models.compatibility import AppDataManagerAdapter
    from app.api.cost_forecast_api import (
        calculate_indirect_labor_cost,
        calculate_manufacturing_cost,
        calculate_screen_cost_allocation,
        collect_production_manufacturing_cost_by_category,
        summarize_indirect_labor_manufacturing_by_category,
        summarize_manufacturing_cost_category_totals,
    )

    app = create_app("development")
    with app.app_context():
        app_data = AppDataManagerAdapter.get_instance("user_1")
        p = 1
        mfg = summarize_manufacturing_cost_category_totals(
            calculate_manufacturing_cost(app_data, p)
        )
        pub = (
            calculate_screen_cost_allocation(app_data, p).get("allocation") or {}
        ).get("category_allocation") or {}
        ind = summarize_indirect_labor_manufacturing_by_category(
            calculate_indirect_labor_cost(app_data, p, include_no_opening_columns=False)
        )
        comb = collect_production_manufacturing_cost_by_category(app_data, p)

        print("=== 截图三来源 vs 当前后端三来源 ===")
        for c in CATS:
            um, up, ui = USER_MFG[c], USER_PUB[c], USER_IND[c]
            print(
                f"{c}: mfg差{mfg[c]-um:+.2f} pub差{float(pub.get(c,0))-up:+.2f} "
                f"ind差{ind[c]-ui:+.2f}"
            )

        print("\n=== 截图三来源相加 vs 分摊页制造费用列 ===")
        for c in CATS:
            exp = USER_MFG[c] + USER_PUB[c] + USER_IND[c]
            print(
                f"{c}: 三源和={exp:.2f} 分摊页={USER_SHOWN[c]:.2f} "
                f"差额={USER_SHOWN[c]-exp:+.2f} 后端现算={comb[c]:.2f}"
            )


if __name__ == "__main__":
    main()
