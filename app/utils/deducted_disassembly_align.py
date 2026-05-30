# -*- coding: utf-8 -*-
"""将「被减扣」相关表中的「原库存数量(TAI)」与「原始数据(未减扣)」disassembly_data 对齐。"""
from typing import Optional

import pandas as pd


def _norm_code(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ''
    s = str(val).strip()
    if s.endswith('.0'):
        base = s[:-2]
        if base.replace('-', '').isdigit():
            s = base
    return s


def _tai_numeric_or_none(val):
    """将 TAI 单元格转为 float 或 None（不可比数值视为 None）。"""
    if val is None or val == "" or val == "-":
        return None
    if isinstance(val, str) and str(val).strip() == "-":
        return None
    n = pd.to_numeric(val, errors="coerce")
    if pd.isna(n):
        return None
    return float(n)


def _tai_value_changed(old_v, new_v) -> bool:
    """对齐前后 TAI 是否发生数值变化（用于决定是否仅对该行重算 KG）。"""
    o = _tai_numeric_or_none(old_v)
    n = _tai_numeric_or_none(new_v)
    if o is None and n is None:
        return False
    if o is None or n is None:
        return True
    return abs(o - n) > 1e-9


def _formula_kg_for_tai_value(df: pd.DataFrame, idx, tai_val) -> Optional[float]:
    """
    使用指定 TAI 与该行系数计算理论 KG（与 _recalculate_deducted_kg_row 公式一致）。
    tai_val 可为对齐前的旧 TAI，用于判断当前 KG 是否仍为公式值（非用户直接改数）。
    """
    if df is None or df.empty or "计算结果(KG)" not in df.columns:
        return None
    need = ["单台重量(KG/台)", "投入产出比例", "拆解系数"]
    if not all(c in df.columns for c in need):
        return None
    if tai_val is None or tai_val == "" or tai_val == "-":
        return None
    if isinstance(tai_val, str) and str(tai_val).strip() == "-":
        return None
    tai = pd.to_numeric(tai_val, errors="coerce")
    if pd.isna(tai):
        return None
    w = pd.to_numeric(df.at[idx, "单台重量(KG/台)"], errors="coerce")
    r = pd.to_numeric(df.at[idx, "投入产出比例"], errors="coerce")
    c = pd.to_numeric(df.at[idx, "拆解系数"], errors="coerce")
    if pd.isna(w) or pd.isna(r) or pd.isna(c):
        return None
    return round(float(tai) * float(w) * float(r) * float(c), 6)


def _kg_matches_formula_value(kg_cell, formula_kg, abs_tol: float = 1e-3) -> bool:
    """当前单元格 KG 是否与公式值一致（用于区分用户手工覆盖）。"""
    if formula_kg is None:
        return False
    kg = pd.to_numeric(kg_cell, errors="coerce")
    if pd.isna(kg):
        return False
    return abs(float(kg) - float(formula_kg)) <= abs_tol


def _recalculate_deducted_kg_row(df: pd.DataFrame, idx) -> None:
    """单行：KG = TAI × 单台重量 × 投入产出比例 × 拆解系数。"""
    if df is None or df.empty or "计算结果(KG)" not in df.columns:
        return
    need = ["单台重量(KG/台)", "投入产出比例", "拆解系数", "原库存数量(TAI)"]
    if not all(c in df.columns for c in need):
        return
    tai_v = df.at[idx, "原库存数量(TAI)"]
    if tai_v is None or tai_v == "" or tai_v == "-":
        return
    if isinstance(tai_v, str) and str(tai_v).strip() == "-":
        return
    tai = pd.to_numeric(tai_v, errors="coerce")
    if pd.isna(tai):
        return
    w = pd.to_numeric(df.at[idx, "单台重量(KG/台)"], errors="coerce")
    r = pd.to_numeric(df.at[idx, "投入产出比例"], errors="coerce")
    c = pd.to_numeric(df.at[idx, "拆解系数"], errors="coerce")
    if pd.isna(w) or pd.isna(r) or pd.isna(c):
        return
    df.at[idx, "计算结果(KG)"] = round(float(tai) * float(w) * float(r) * float(c), 6)


def _recalculate_deducted_kg_from_formula(df: pd.DataFrame) -> None:
    """与 calculation_engine 一致：全表按公式重算 计算结果(KG)。"""
    if df is None or df.empty or "计算结果(KG)" not in df.columns:
        return
    need = ["单台重量(KG/台)", "投入产出比例", "拆解系数"]
    if not all(c in df.columns for c in need):
        return
    for idx in df.index:
        _recalculate_deducted_kg_row(df, idx)


def align_deducted_inventory_tai_from_disassembly(
    deducted_df: pd.DataFrame,
    disassembly_df: pd.DataFrame,
    recalculate_kg: bool = True,
    recalculate_kg_when_tai_changed: bool = False,
) -> pd.DataFrame:
    """
    按 原物料代码 + 拆解产物编码 (+ 期间) 从 disassembly_df 回填 原库存数量(TAI)。

    Args:
        deducted_df: 被减扣相关表（手工/只读快照等）。
        disassembly_df: 原始数据(未减扣) disassembly_data。
        recalculate_kg: 为 True 时，在回填 TAI 后按与未减扣表相同公式重算全部 计算结果(KG)。
            与 recalculate_kg_when_tai_changed 同时使用时，本参数优先（整表重算）。
        recalculate_kg_when_tai_changed: 为 True 且 recalculate_kg 为 False 时，仅对「回填 TAI 前后
            数值发生变化」的行考虑重算 计算结果(KG)。若该行当前 KG 与「旧 TAI×系数」公式值不一致，
            视为用户手工改数，保留 KG；仅当与旧公式一致时才按新 TAI 重算，避免覆盖手工编辑。
    """
    if deducted_df is None or deducted_df.empty:
        return deducted_df
    if disassembly_df is None or disassembly_df.empty:
        return deducted_df.copy()
    if '原库存数量(TAI)' not in deducted_df.columns:
        return deducted_df.copy()
    need = ['原物料代码', '拆解产物编码']
    for c in need:
        if c not in disassembly_df.columns or c not in deducted_df.columns:
            return deducted_df.copy()

    out = deducted_df.copy()
    old_tai = None
    if recalculate_kg_when_tai_changed and not recalculate_kg:
        old_tai = out["原库存数量(TAI)"].copy()

    use_period = '期间' in disassembly_df.columns and '期间' in out.columns

    lookup = {}
    for _, row in disassembly_df.iterrows():
        p = str(row.get('期间', '')) if use_period else ''
        k = (_norm_code(row['原物料代码']), _norm_code(row['拆解产物编码']), p)
        tai = row.get('原库存数量(TAI)')
        lookup[k] = tai

    for idx in out.index:
        p = str(out.loc[idx, '期间']) if use_period else ''
        k = (
            _norm_code(out.loc[idx, '原物料代码']),
            _norm_code(out.loc[idx, '拆解产物编码']),
            p,
        )
        if k not in lookup:
            continue
        tai = lookup[k]
        if tai is None or (isinstance(tai, float) and pd.isna(tai)):
            continue
        out.loc[idx, '原库存数量(TAI)'] = tai

    if recalculate_kg:
        _recalculate_deducted_kg_from_formula(out)
    elif recalculate_kg_when_tai_changed and old_tai is not None:
        for idx in out.index:
            if idx not in old_tai.index:
                continue
            if not _tai_value_changed(old_tai.loc[idx], out.loc[idx, "原库存数量(TAI)"]):
                continue
            # 旧 TAI 下的理论 KG
            formula_old = _formula_kg_for_tai_value(out, idx, old_tai.loc[idx])
            current_kg = out.loc[idx, "计算结果(KG)"]
            # 与旧公式不一致：视为用户直接编辑过「计算结果(KG)」，只同步 TAI，不重算 KG
            if not _kg_matches_formula_value(current_kg, formula_old):
                continue
            _recalculate_deducted_kg_row(out, idx)
    return out
