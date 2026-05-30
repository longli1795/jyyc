# -*- coding: utf-8 -*-
"""回归：被减扣「原库存数量(TAI)」与原始数据(未减扣)对齐，及 KG 公式一致"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd


def _coeff_row():
    return {
        "单台重量(KG/台)": 8.404833388,
        "投入产出比例": 0.999046126,
        "拆解系数": 0.013997623,
    }


def test_align_recalcs_kg_after_tai_sync():
    from app.utils.deducted_disassembly_align import align_deducted_inventory_tai_from_disassembly

    coeff = _coeff_row()
    deducted = pd.DataFrame(
        [
            {
                "原物料代码": "810979118",
                "拆解产物编码": "811052988",
                "期间": "",
                "原库存数量(TAI)": 215,
                "计算结果(KG)": 25.270125,
                **coeff,
            }
        ]
    )
    disassembly = pd.DataFrame(
        [
            {
                "原物料代码": "810979118",
                "拆解产物编码": "811052988",
                "期间": "",
                "原库存数量(TAI)": 315,
            }
        ]
    )
    out = align_deducted_inventory_tai_from_disassembly(deducted, disassembly)
    assert float(out["原库存数量(TAI)"].iloc[0]) == 315
    expected = round(315 * 8.404833388 * 0.999046126 * 0.013997623, 6)
    assert abs(float(out["计算结果(KG)"].iloc[0]) - expected) < 1e-4
    assert abs(float(out["计算结果(KG)"].iloc[0]) - 37.023672) < 0.001


def test_align_simple_tai_and_kg():
    from app.utils.deducted_disassembly_align import align_deducted_inventory_tai_from_disassembly

    deducted = pd.DataFrame(
        [
            {
                "原物料代码": "M001",
                "拆解产物编码": "P01",
                "期间": "2024-01",
                "原库存数量(TAI)": 100,
                "计算结果(KG)": 1.5,
                "单台重量(KG/台)": 1.0,
                "投入产出比例": 1.0,
                "拆解系数": 1.0,
            }
        ]
    )
    disassembly = pd.DataFrame(
        [
            {
                "原物料代码": "M001",
                "拆解产物编码": "P01",
                "期间": "2024-01",
                "原库存数量(TAI)": 250,
            }
        ]
    )
    out = align_deducted_inventory_tai_from_disassembly(deducted, disassembly)
    assert float(out["原库存数量(TAI)"].iloc[0]) == 250
    assert float(out["计算结果(KG)"].iloc[0]) == 250.0


def test_align_code_normalization():
    from app.utils.deducted_disassembly_align import align_deducted_inventory_tai_from_disassembly

    deducted = pd.DataFrame(
        [
            {
                "原物料代码": "100.0",
                "拆解产物编码": "200.0",
                "期间": "",
                "原库存数量(TAI)": 1,
                "计算结果(KG)": 0.0,
                "单台重量(KG/台)": 1.0,
                "投入产出比例": 1.0,
                "拆解系数": 1.0,
            }
        ]
    )
    disassembly = pd.DataFrame(
        [
            {
                "原物料代码": 100,
                "拆解产物编码": "200",
                "期间": "",
                "原库存数量(TAI)": 88,
            }
        ]
    )
    out = align_deducted_inventory_tai_from_disassembly(deducted, disassembly)
    assert float(out["原库存数量(TAI)"].iloc[0]) == 88
    assert float(out["计算结果(KG)"].iloc[0]) == 88.0


def test_period_mismatch_recalc_uses_local_tai():
    from app.utils.deducted_disassembly_align import align_deducted_inventory_tai_from_disassembly

    deducted = pd.DataFrame(
        [
            {
                "原物料代码": "M",
                "拆解产物编码": "P",
                "期间": "A",
                "原库存数量(TAI)": 10,
                "计算结果(KG)": 999.0,
                "单台重量(KG/台)": 2.0,
                "投入产出比例": 1.0,
                "拆解系数": 1.0,
            }
        ]
    )
    disassembly = pd.DataFrame(
        [
            {
                "原物料代码": "M",
                "拆解产物编码": "P",
                "期间": "B",
                "原库存数量(TAI)": 99,
            }
        ]
    )
    out = align_deducted_inventory_tai_from_disassembly(deducted, disassembly)
    assert float(out["原库存数量(TAI)"].iloc[0]) == 10
    assert float(out["计算结果(KG)"].iloc[0]) == 20.0


def test_empty_disassembly_unchanged():
    from app.utils.deducted_disassembly_align import align_deducted_inventory_tai_from_disassembly

    deducted = pd.DataFrame([{"原物料代码": "M", "拆解产物编码": "P", "原库存数量(TAI)": 7}])
    out = align_deducted_inventory_tai_from_disassembly(deducted, pd.DataFrame())
    assert float(out["原库存数量(TAI)"].iloc[0]) == 7


def test_align_tai_only_preserves_kg():
    """recalculate_kg=False：只更新 TAI，不覆盖 计算结果(KG)（被减扣修改前快照 / 手工值）。"""
    from app.utils.deducted_disassembly_align import align_deducted_inventory_tai_from_disassembly

    coeff = _coeff_row()
    deducted = pd.DataFrame(
        [
            {
                "原物料代码": "810979118",
                "拆解产物编码": "811052988",
                "期间": "",
                "原库存数量(TAI)": 215,
                "计算结果(KG)": 25.270125,
                **coeff,
            }
        ]
    )
    disassembly = pd.DataFrame(
        [
            {
                "原物料代码": "810979118",
                "拆解产物编码": "811052988",
                "期间": "",
                "原库存数量(TAI)": 315,
            }
        ]
    )
    out = align_deducted_inventory_tai_from_disassembly(
        deducted, disassembly, recalculate_kg=False
    )
    assert float(out["原库存数量(TAI)"].iloc[0]) == 315
    assert abs(float(out["计算结果(KG)"].iloc[0]) - 25.270125) < 1e-6


def test_align_recalc_kg_only_when_tai_changed():
    """TAI 变化的行重算 KG；TAI 未变行保留手工 KG。"""
    from app.utils.deducted_disassembly_align import align_deducted_inventory_tai_from_disassembly

    coeff = {"单台重量(KG/台)": 2.0, "投入产出比例": 1.0, "拆解系数": 1.0}
    deducted = pd.DataFrame(
        [
            {
                "原物料代码": "810979118",
                "拆解产物编码": "811052988",
                "期间": "",
                "原库存数量(TAI)": 215,
                "计算结果(KG)": 430.0,
                **coeff,
            },
            {
                "原物料代码": "M002",
                "拆解产物编码": "P02",
                "期间": "",
                "原库存数量(TAI)": 100,
                "计算结果(KG)": 999.0,
                **coeff,
            },
        ]
    )
    disassembly = pd.DataFrame(
        [
            {
                "原物料代码": "810979118",
                "拆解产物编码": "811052988",
                "期间": "",
                "原库存数量(TAI)": 315,
            },
            {
                "原物料代码": "M002",
                "拆解产物编码": "P02",
                "期间": "",
                "原库存数量(TAI)": 100,
            },
        ]
    )
    out = align_deducted_inventory_tai_from_disassembly(
        deducted,
        disassembly,
        recalculate_kg=False,
        recalculate_kg_when_tai_changed=True,
    )
    assert float(out.iloc[0]["原库存数量(TAI)"]) == 315
    assert float(out.iloc[0]["计算结果(KG)"]) == 630.0
    assert float(out.iloc[1]["原库存数量(TAI)"]) == 100
    assert float(out.iloc[1]["计算结果(KG)"]) == 999.0


def test_recalculate_kg_true_overrides_when_tai_changed_flag():
    """recalculate_kg=True 时整表重算，与 when_tai_changed 无关。"""
    from app.utils.deducted_disassembly_align import align_deducted_inventory_tai_from_disassembly

    coeff = {"单台重量(KG/台)": 2.0, "投入产出比例": 1.0, "拆解系数": 1.0}
    deducted = pd.DataFrame(
        [
            {
                "原物料代码": "M002",
                "拆解产物编码": "P02",
                "期间": "",
                "原库存数量(TAI)": 100,
                "计算结果(KG)": 999.0,
                **coeff,
            },
        ]
    )
    disassembly = pd.DataFrame(
        [
            {
                "原物料代码": "M002",
                "拆解产物编码": "P02",
                "期间": "",
                "原库存数量(TAI)": 100,
            },
        ]
    )
    out = align_deducted_inventory_tai_from_disassembly(
        deducted,
        disassembly,
        recalculate_kg=True,
        recalculate_kg_when_tai_changed=True,
    )
    assert float(out.iloc[0]["计算结果(KG)"]) == 200.0


def test_skip_kg_when_tai_is_dash():
    from app.utils.deducted_disassembly_align import align_deducted_inventory_tai_from_disassembly

    deducted = pd.DataFrame(
        [
            {
                "原物料代码": "X",
                "拆解产物编码": "X",
                "期间": "",
                "原库存数量(TAI)": "-",
                "计算结果(KG)": 12.5,
                "单台重量(KG/台)": 1.0,
                "投入产出比例": 1.0,
                "拆解系数": 1.0,
            }
        ]
    )
    disassembly = pd.DataFrame(
        [{"原物料代码": "X", "拆解产物编码": "X", "期间": "", "原库存数量(TAI)": "-"}]
    )
    out = align_deducted_inventory_tai_from_disassembly(deducted, disassembly)
    assert out["计算结果(KG)"].iloc[0] == 12.5


if __name__ == "__main__":
    test_align_recalcs_kg_after_tai_sync()
    test_align_simple_tai_and_kg()
    test_align_code_normalization()
    test_period_mismatch_recalc_uses_local_tai()
    test_empty_disassembly_unchanged()
    test_align_tai_only_preserves_kg()
    test_align_recalc_kg_only_when_tai_changed()
    test_recalculate_kg_true_overrides_when_tai_changed_flag()
    test_skip_kg_when_tai_is_dash()
    print("test_deducted_tai_align: all passed")
