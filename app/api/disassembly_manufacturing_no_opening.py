# -*- coding: utf-8 -*-
"""拆解收益分析表：不考虑期初库存和库存结余口径下的制造费用累加逻辑。

按「制造费用修正.md」实现，对应 10 项公式：
① 旧机间接人工提成
② 一次拆解产物 / 打包铁 / 一破 班组长提成（取不考虑期初库存和库存结余列）
③ 旧机分摊固定（物流主管/生产主管/...）
④ 一次拆解产物 / 一破 生产班组长(塑料破碎)分摊固定成本（取不考虑期初库存和库存结余列）
⑤ 与拆解量相关的费用
⑥ 与电机入库量相关的费用
⑦ 预计月均费用分摊
⑧ 环保费（被减扣数据只读 sheet）
⑨ 屏费用分摊（按原物料代码的 A+B+C+D+E 组合公式）
⑩ 制造费用间接人工分摊 / 制造费用公共成本分摊
"""
import math
import pandas as pd


def _nf(x, default=0.0):
    try:
        if x is None:
            return default
        try:
            if pd.isna(x):
                return default
        except Exception:
            pass
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def apply_manufacturing_cost_no_opening(
    app_data,
    prediction_period,
    manufacturing_cost_by_code,
    manufacturing_cost_details_by_code,
    allowed_material_codes,
    valid_material_codes,
    material_info,
    original_data,
    deducted_data,
    product_value_by_code,
    category_total_value,
    classify_by_product_name,
    indirect_labor_result,
):
    """在已初始化的 manufacturing_cost_* 上累加不考虑期初库存和库存结余口径的制造费用。"""
    from app.api.cost_forecast_api import (
        calculate_manufacturing_cost,
        calculate_screen_cost_allocation,
        resolve_disassembly_category_unit_price,
    )
    from app.api.data_management_api import get_manufacturing_cost_dataframe
    from data.base_data.price_data import load_price_data

    if indirect_labor_result and not indirect_labor_result.get('error'):
        # ① 旧机提成
        for detail in indirect_labor_result.get('part1_details', []):
            material_code = str(detail.get('物料代码', '')).strip()
            if material_code not in allowed_material_codes:
                continue
            cost = (
                _nf(detail.get('物流主管提成成本'))
                + _nf(detail.get('物流卸货提成成本'))
                + _nf(detail.get('班组长提成成本'))
                + _nf(detail.get('生产主管提成成本'))
                + _nf(detail.get('维修班长提成成本'))
                + _nf(detail.get('维修员提成成本'))
                + _nf(detail.get('冰箱维修主管提成成本'))
            )
            manufacturing_cost_by_code[material_code] += cost
            manufacturing_cost_details_by_code[material_code]['间接人工提成成本'] += cost

        # ② 一次拆解产物 / 打包铁 / 一破：按"原物料代码"直接汇总「班组长提成成本(不考虑期初库存和库存结余)」
        tl_no_opening_key = '班组长提成成本(不考虑期初库存和库存结余)'
        for detail in indirect_labor_result.get('part2_details', []):
            if str(detail.get('类别', '')).strip() != '一次拆解产物':
                continue
            mc = str(detail.get('原物料代码', '')).strip()
            if not mc or mc not in allowed_material_codes:
                continue
            cost = _nf(detail.get(tl_no_opening_key))
            if cost == 0:
                continue
            manufacturing_cost_by_code[mc] += cost
            manufacturing_cost_details_by_code[mc]['间接人工提成成本'] += cost

        for detail in indirect_labor_result.get('part3_details', []):
            if str(detail.get('类别', '')).strip() not in ('打包铁', '一破'):
                continue
            mc = str(detail.get('原物料代码', '')).strip()
            if not mc or mc not in allowed_material_codes:
                continue
            cost = _nf(detail.get(tl_no_opening_key))
            if cost == 0:
                continue
            manufacturing_cost_by_code[mc] += cost
            manufacturing_cost_details_by_code[mc]['间接人工提成成本'] += cost

        # ③ 旧机分摊固定（不含塑料破碎比例段）
        for detail in indirect_labor_result.get('part1_details', []):
            material_code = str(detail.get('物料代码', '')).strip()
            if material_code not in valid_material_codes:
                continue
            cost = (
                _nf(detail.get('物流主管分摊固定成本'))
                + _nf(detail.get('生产主管分摊固定成本'))
                + _nf(detail.get('物流卸货分摊固定成本'))
                + _nf(detail.get('维修班长分摊固定成本'))
                + _nf(detail.get('维修员分摊固定成本'))
                + _nf(detail.get('冰箱维修主管分摊固定成本'))
                + _nf(detail.get('白电小组长分摊固定成本'))
                + _nf(detail.get('生产班组长(黑电)分摊固定成本'))
                + _nf(detail.get('生产班组长(冰箱)分摊固定成本'))
            )
            manufacturing_cost_by_code[material_code] += cost
            manufacturing_cost_details_by_code[material_code]['分摊固定成本明细'] += cost

        # ④ 一次拆解产物 / 一破：按"原物料代码"直接汇总「生产班组长(塑料破碎)分摊固定成本(不考虑期初库存和库存结余)」
        plastic_no_opening_key = '生产班组长(塑料破碎)分摊固定成本(不考虑期初库存和库存结余)'
        for detail in indirect_labor_result.get('part2_details', []):
            if str(detail.get('类别', '')).strip() != '一次拆解产物':
                continue
            mc = str(detail.get('原物料代码', '')).strip()
            if not mc or mc not in allowed_material_codes:
                continue
            cost = _nf(detail.get(plastic_no_opening_key))
            if cost == 0:
                continue
            manufacturing_cost_by_code[mc] += cost
            manufacturing_cost_details_by_code[mc]['分摊固定成本明细'] += cost

        for detail in indirect_labor_result.get('part3_details', []):
            if str(detail.get('类别', '')).strip() != '一破':
                continue
            mc = str(detail.get('原物料代码', '')).strip()
            if not mc or mc not in allowed_material_codes:
                continue
            cost = _nf(detail.get(plastic_no_opening_key))
            if cost == 0:
                continue
            manufacturing_cost_by_code[mc] += cost
            manufacturing_cost_details_by_code[mc]['分摊固定成本明细'] += cost

    manufacturing_result = calculate_manufacturing_cost(app_data, prediction_period)

    # ⑥ 与拆解量相关
    if manufacturing_result and not manufacturing_result.get('error'):
        manufacturing_cost_df = get_manufacturing_cost_dataframe()
        if manufacturing_cost_df is not None and not manufacturing_cost_df.empty and '备注' in manufacturing_cost_df.columns:
            disassembly_related_df = manufacturing_cost_df[
                manufacturing_cost_df['备注'].astype(str).str.contains('与拆解量相关', case=False, na=False)
            ].copy()
            extracted_data = app_data.get_data('extracted_data_manual')
            if extracted_data is not None and not extracted_data.empty:
                if '类别' in extracted_data.columns and '物料代码' in extracted_data.columns:
                    old_machine_data = extracted_data[extracted_data['类别'] == '旧机'].copy()
                    if '非限制使用的库存' in old_machine_data.columns:
                        old_machine_data['非限制使用的库存'] = pd.to_numeric(
                            old_machine_data['非限制使用的库存'], errors='coerce'
                        ).fillna(0)
                        for _, material_row in old_machine_data.iterrows():
                            material_code = str(material_row.get('物料代码', '')).strip()
                            if material_code not in valid_material_codes:
                                continue
                            material_name = str(material_row.get('物料描述', '')).strip()
                            quantity = _nf(material_row.get('非限制使用的库存'))
                            if quantity <= 0:
                                continue
                            material_category = classify_by_product_name(material_name)
                            if not material_category:
                                continue
                            total_unit_price = 0.0
                            for _, cost_row in disassembly_related_df.iterrows():
                                up = resolve_disassembly_category_unit_price(cost_row, material_category)
                                if up > 0:
                                    total_unit_price += up
                            if total_unit_price > 0:
                                cost = quantity * total_unit_price
                                manufacturing_cost_by_code[material_code] += cost
                                manufacturing_cost_details_by_code[material_code]['与拆解量相关的费用'] += cost

    # ⑥ 与电机入库量相关：从"被减扣数据（手工）"筛选类别=拆解产物 且 拆解产物编码∈电机编码集
    motor_codes = ['811053046', '811053050', '811304664', '811437999']
    motor_norm = [c.strip() for c in motor_codes]
    if deducted_data is not None and not deducted_data.empty:
        cols = deducted_data.columns
        if all(c in cols for c in ('拆解产物编码', '原物料代码', '计算结果(KG)')):
            motor_mask = deducted_data['拆解产物编码'].astype(str).str.strip().isin(motor_norm)
            if '类别' in cols:
                motor_mask = motor_mask & (deducted_data['类别'].astype(str) == '拆解产物')
            motor_data = deducted_data[motor_mask].copy()
            if not motor_data.empty:
                motor_data['计算结果(KG)'] = pd.to_numeric(motor_data['计算结果(KG)'], errors='coerce').fillna(0)
                name_column = None
                for cand in ('拆解产物名称', '原物料名称', '物料名称'):
                    if cand in motor_data.columns:
                        name_column = cand
                        break
                manufacturing_cost_df = get_manufacturing_cost_dataframe()
                if manufacturing_cost_df is not None and not manufacturing_cost_df.empty and '备注' in manufacturing_cost_df.columns:
                    motor_related_df = manufacturing_cost_df[
                        manufacturing_cost_df['备注'].astype(str).str.contains('与电机入库量相关', case=False, na=False)
                    ].copy()
                    for _, row in motor_data.iterrows():
                        material_code = str(row.get('原物料代码', '')).strip()
                        if material_code not in valid_material_codes:
                            continue
                        weight = _nf(row.get('计算结果(KG)'))
                        material_name = str(row.get(name_column, '')).strip() if name_column else ''
                        material_category = classify_by_product_name(material_name)
                        if material_category not in ('空调', '洗衣机'):
                            continue
                        for _, cost_row in motor_related_df.iterrows():
                            if material_category in cost_row.index:
                                unit_price = _nf(cost_row.get(material_category))
                                if unit_price > 0:
                                    manufacturing_cost_by_code[material_code] += weight * unit_price
                                    manufacturing_cost_details_by_code[material_code]['与电机入库量相关的费用'] += weight * unit_price
                                    break

    category_tvfp = {'电视': 0.0, '冰箱': 0.0, '空调': 0.0, '洗衣机': 0.0, '电脑': 0.0}
    for mc in valid_material_codes:
        pv = _nf(product_value_by_code.get(mc))
        if pv <= 0:
            continue
        cat = material_info.get(mc, {}).get('类别', '')
        if cat in category_tvfp:
            category_tvfp[cat] += pv

    # ⑧ 预计月均费用
    if manufacturing_result and not manufacturing_result.get('error'):
        monthly_average_list = manufacturing_result.get('monthly_average', [])
        category_monthly_cost_sum = {c: 0.0 for c in category_tvfp}
        for item in monthly_average_list:
            for detail in item.get('明细', []):
                category = detail.get('category', '')
                if category in category_monthly_cost_sum:
                    category_monthly_cost_sum[category] += _nf(detail.get('cost'))
        for category in category_monthly_cost_sum:
            category_total_cost = category_monthly_cost_sum[category]
            if category_total_cost <= 0:
                continue
            category_total = category_tvfp.get(category, 0.0)
            if category_total <= 0:
                continue
            for material_code in allowed_material_codes:
                material_value = _nf(product_value_by_code.get(material_code))
                if material_value <= 0:
                    continue
                material_category = None
                if material_code in valid_material_codes:
                    material_category = material_info.get(material_code, {}).get('类别', '')
                if material_category == category:
                    ac = category_total_cost * (material_value / category_total)
                    manufacturing_cost_by_code[material_code] += ac
                    manufacturing_cost_details_by_code[material_code]['预计月均费用分摊'] += ac

    # ⑨ 环保费（被减扣数据只读 sheet，与考虑期初口径/制造费用成本页一致，不用手工表）
    from app.api.data_management_api import _build_deducted_readonly_dataframe
    deducted_data_for_env = _build_deducted_readonly_dataframe(app_data)
    if deducted_data_for_env is not None and not deducted_data_for_env.empty:
        if '类别' in deducted_data_for_env.columns and '处置类别' in deducted_data_for_env.columns:
            env_mask = (
                (deducted_data_for_env['类别'].astype(str) == '拆解产物')
                & (deducted_data_for_env['处置类别'].astype(str).isin(['付费处置', '内转荧光灯处置']))
            )
            env_data = deducted_data_for_env[env_mask].copy()
            if not env_data.empty and '计算结果(KG)' in env_data.columns and '拆解产物编码' in env_data.columns:
                env_data['计算结果(KG)'] = pd.to_numeric(env_data['计算结果(KG)'], errors='coerce').fillna(0)
                env_data['拆解产物编码'] = env_data['拆解产物编码'].astype(str).str.strip()
                price_df = load_price_data()
                env_fee_price_mapping = {}
                if price_df is not None and not price_df.empty and '销售单价-不含税(元/KG)' in price_df.columns:
                    price_df = price_df.copy()
                    price_df['销售单价-不含税(元/KG)'] = pd.to_numeric(
                        price_df['销售单价-不含税(元/KG)'], errors='coerce'
                    ).fillna(0)
                    for _, price_row in price_df[price_df['销售单价-不含税(元/KG)'] < 0].iterrows():
                        pc = str(price_row.get('拆解产物编码', '')).strip()
                        up = _nf(price_row.get('销售单价-不含税(元/KG)'))
                        if pc and up < 0:
                            env_fee_price_mapping[pc] = abs(up)
                for _, row in env_data.iterrows():
                    material_code = str(row.get('原物料代码', '')).strip()
                    product_code = str(row.get('拆解产物编码', '')).strip()
                    if material_code not in valid_material_codes or not product_code:
                        continue
                    weight = _nf(row.get('计算结果(KG)'))
                    up = env_fee_price_mapping.get(product_code, 0.0)
                    if weight > 0 and up > 0:
                        manufacturing_cost_by_code[material_code] += weight * up
                        manufacturing_cost_details_by_code[material_code]['环保费'] += weight * up

    # ⑩ 屏费用分摊（不考虑期初库存和库存结余）= A + B + C + D + E，按"原物料代码"累加
    from app.api.cost_forecast_api import (
        calculate_direct_labor_cost,
        _build_no_opening_deep_result_kg_map,
    )

    screen_res = calculate_screen_cost_allocation(app_data, prediction_period)

    # A：直接人工成本页"生产工人计件工资"表筛选类别="屏"，按原物料代码匹配「工资(不考虑期初库存和库存结余)」
    # B：直接人工成本页"分摊固定工资、社保、公积金"卡片筛选类别="屏"，按原物料代码匹配「分摊固定成本（不考虑期初库存和库存结余）」
    try:
        dl_result = calculate_direct_labor_cost(app_data, prediction_period)
    except Exception:
        dl_result = None
    if dl_result and not dl_result.get('error'):
        screen_cat = (dl_result.get('category_details') or {}).get('屏') or {}
        for alloc in screen_cat.get('item_allocations', []) or []:
            item = alloc.get('item', {}) or {}
            mc = str(item.get('原物料代码', '')).strip()
            if not mc or mc not in valid_material_codes:
                continue
            wage_no_opening = _nf(item.get('工资(不考虑期初库存和库存结余)', item.get('工资', 0)))
            fixed_no_opening = _nf(alloc.get('fixed_cost_no_opening', alloc.get('fixed_cost', 0)))
            ab = wage_no_opening + fixed_no_opening
            if ab != 0:
                manufacturing_cost_by_code[mc] += ab
                manufacturing_cost_details_by_code[mc]['屏费用分摊'] += ab

    # C/D 依赖的"内转屏处置"被减扣汇总（按原物料代码 × KG），C 还需要屏"与拆解量相关的费用"单价之和
    ddm = app_data.get_data('deducted_data_manual')
    screen_kg_by_mc = {}
    screen_kg_total = 0.0
    if ddm is not None and not ddm.empty:
        cols_needed = ('类别', '处置类别', '原物料代码', '计算结果(KG)')
        if all(c in ddm.columns for c in cols_needed):
            scr_mask = (
                (ddm['类别'].astype(str) == '拆解产物')
                & (ddm['处置类别'].astype(str).str.strip() == '内转屏处置')
            )
            scr_sub = ddm[scr_mask].copy()
            if not scr_sub.empty:
                scr_sub['计算结果(KG)'] = pd.to_numeric(scr_sub['计算结果(KG)'], errors='coerce').fillna(0)
                for _, row in scr_sub.iterrows():
                    w = _nf(row.get('计算结果(KG)'))
                    if w <= 0:
                        continue
                    mc = str(row.get('原物料代码', '')).strip()
                    if not mc:
                        continue
                    screen_kg_by_mc[mc] = screen_kg_by_mc.get(mc, 0.0) + w
                    screen_kg_total += w

    # C：被减扣(类别=拆解产物, 处置类别=内转屏处置) 按原物料代码 KG × "制造费用基础数据管理"表中屏对应"与拆解量相关的费用"单价之和
    screen_disassembly_unit_price = 0.0
    manufacturing_cost_df = get_manufacturing_cost_dataframe()
    if manufacturing_cost_df is not None and not manufacturing_cost_df.empty and '备注' in manufacturing_cost_df.columns:
        screen_related_df = manufacturing_cost_df[
            manufacturing_cost_df['备注'].astype(str).str.contains('与拆解量相关', case=False, na=False)
        ]
        for _, cost_row in screen_related_df.iterrows():
            if '屏' in cost_row.index:
                up = _nf(cost_row.get('屏'))
                if up > 0:
                    screen_disassembly_unit_price += up
    if screen_disassembly_unit_price > 0:
        for mc, kg in screen_kg_by_mc.items():
            if mc not in valid_material_codes:
                continue
            add_c = kg * screen_disassembly_unit_price
            if add_c != 0:
                manufacturing_cost_by_code[mc] += add_c
                manufacturing_cost_details_by_code[mc]['屏费用分摊'] += add_c

    # D：预计月均费用(屏) × (被减扣[mc] / 被减扣[total])
    monthly_average_screen = 0.0
    if screen_res and not screen_res.get('error'):
        monthly_average_screen = _nf(
            (screen_res.get('manufacturing_cost') or {}).get('monthly_average_screen', 0.0)
        )
    if monthly_average_screen != 0 and screen_kg_total > 0:
        for mc, kg in screen_kg_by_mc.items():
            if mc not in valid_material_codes:
                continue
            add_d = monthly_average_screen * (kg / screen_kg_total)
            if add_d != 0:
                manufacturing_cost_by_code[mc] += add_d
                manufacturing_cost_details_by_code[mc]['屏费用分摊'] += add_d

    # E：深加工产物价值表（不考虑期初库存和库存结余）中深加工产物编码=CH1171141 的
    # 深加工产物重量 × |"销售价格管理"页"拆解产物编码"对应的"销售单价-不含税(元/KG)"|
    try:
        no_opening_deep_map = _build_no_opening_deep_result_kg_map(app_data)
    except Exception:
        no_opening_deep_map = {}
    ch_deep_kg_by_mc = {}
    for (origin_code, _first_code, deep_product_code), deep_kg in (no_opening_deep_map or {}).items():
        if deep_product_code != 'CH1171141':
            continue
        mc = str(origin_code or '').strip()
        if not mc:
            continue
        ch_deep_kg_by_mc[mc] = ch_deep_kg_by_mc.get(mc, 0.0) + _nf(deep_kg)

    ch_price = 0.0
    if ch_deep_kg_by_mc:
        price_df = load_price_data()
        if price_df is not None and not price_df.empty and '拆解产物编码' in price_df.columns and '销售单价-不含税(元/KG)' in price_df.columns:
            price_df_ch = price_df[price_df['拆解产物编码'].astype(str).str.strip() == 'CH1171141']
            if not price_df_ch.empty:
                raw_price = _nf(price_df_ch.iloc[0].get('销售单价-不含税(元/KG)'))
                ch_price = abs(raw_price)
    if ch_price > 0:
        for mc, deep_kg in ch_deep_kg_by_mc.items():
            if mc not in valid_material_codes:
                continue
            add_e = deep_kg * ch_price
            if add_e != 0:
                manufacturing_cost_by_code[mc] += add_e
                manufacturing_cost_details_by_code[mc]['屏费用分摊'] += add_e

    # ⑩ 制造费用间接人工分摊 / 制造费用公共成本分摊：按类别产值占比分摊
    if screen_res and not screen_res.get('error'):
        ind_tot = screen_res.get('indirect_labor_allocation', {}).get('category_totals') or {}
        pub_tot = screen_res.get('public_cost_allocation', {}).get('category_totals') or {}
        for mc in valid_material_codes:
            cat = material_info.get(mc, {}).get('类别', '')
            if cat not in ('电视', '冰箱', '空调', '洗衣机', '电脑'):
                continue
            pv = _nf(product_value_by_code.get(mc))
            ct = _nf(category_total_value.get(cat))
            if pv <= 0 or ct <= 0:
                continue
            i_alloc = _nf(ind_tot.get(cat)) * pv / ct
            p_alloc = _nf(pub_tot.get(cat)) * pv / ct
            manufacturing_cost_by_code[mc] += i_alloc + p_alloc
            manufacturing_cost_details_by_code[mc]['制造费用间接人工分摊'] += i_alloc
            manufacturing_cost_details_by_code[mc]['制造费用公共成本分摊'] += p_alloc
            manufacturing_cost_details_by_code[mc]['公共费用分摊'] += i_alloc + p_alloc
