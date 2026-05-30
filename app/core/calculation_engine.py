import pandas as pd
import numpy as np
from app.models.compatibility import AppDataManagerAdapter
import data.base_data.deep_processing_data as dpd
from data.base_data.deduction_data import should_deduct, get_code_description, get_disposal_category
from data.base_data.product_data import PRODUCT_DISASSEMBLY_DATA
from data.base_data.price_data import get_price_by_code, get_price_mapping
from data.base_data.subsidy_data import get_subsidy_mapping, match_category_by_description

class CalculationEngine:
    """计算引擎核心类"""
    
    def __init__(self, session_id: str = None):
        self.app_data = AppDataManagerAdapter.get_instance(session_id)
    
    def calculate_disassembly_auto(self):
        """自动计算旧机拆解，不弹窗不交互"""
        try:
            print("🔧 开始计算旧机拆解...")
            
            # 优先使用手工编辑的提取结果数据
            manual_extracted_data = self.app_data.get_data('extracted_data_manual')
            if manual_extracted_data is not None and not manual_extracted_data.empty:
                print("🔄 使用手工编辑的提取结果数据进行计算")
                extracted_data = manual_extracted_data
            else:
                # 使用原始提取数据
                extracted_data = self.app_data.get_data('extracted_data')
                if extracted_data is None:
                    raise Exception("请先提取数据")
                print("🔄 使用原始提取结果数据进行计算")
                
            data = extracted_data
            
            # 筛选出类别为"旧机"的记录
            old_machine_data = data[data['类别'] == '旧机'].copy()
            
            if old_machine_data.empty:
                print("⚠️ 提取的数据中没有找到类别为'旧机'的记录")
                # 仍然处理非旧机数据
                old_machine_data = pd.DataFrame()
            else:
                print(f"找到 {len(old_machine_data)} 条旧机记录")

            # 创建计算结果列表
            original_rows = []  # 原始完整数据（不减扣）
            calculated_rows = []  # 减扣后数据
            deducted_rows = []  # 被减扣的数据

            # 处理旧机数据
            for index, row in old_machine_data.iterrows():
                material_code = str(row.get('物料代码', ''))
                inventory_tai = row.get('非限制使用的库存', 0)  # TAI数量
                unit = row.get('单位', '')
                
                print(f"处理旧机物料: {material_code}, 库存: {inventory_tai} {unit}")
                
                # 尝试转换库存数量为数值
                try:
                    inventory_tai = float(inventory_tai) if inventory_tai != '' else 0
                except (ValueError, TypeError):
                    inventory_tai = 0

                # 在产品拆解系数数据中查找对应的物料代码
                if material_code in PRODUCT_DISASSEMBLY_DATA:
                    product_data = PRODUCT_DISASSEMBLY_DATA[material_code]
                    unit_weight = product_data['单台重量']  # KG/台
                    input_output_ratio = product_data['一次拆解投入产出比例']
                    
                    print(f"找到拆解数据: 单台重量={unit_weight}KG, 投入产出比例={input_output_ratio}")
                    
                    # 为每个拆解系数明细创建一行
                    for detail in product_data['拆解系数_明细']:
                        disassembly_coefficient = detail['一次拆解系数']
                        product_code = detail['一次拆解产物编码']
                        product_name = detail['一次拆解产物名称']
                        
                        # 修复产物编码的小数点问题：确保是字符串并移除.0后缀
                        product_code = str(product_code)
                        if product_code.endswith('.0'):
                            product_code = product_code[:-2]
                        
                        # 计算结果：旧机库存数量(TAI) × 单台重量(KG/台) × 一次拆解投入产出比例 × 一次拆解系数
                        calculated_amount_kg = inventory_tai * unit_weight * input_output_ratio * disassembly_coefficient
                        
                        # 检查是否需要减扣
                        is_deduction = should_deduct(product_code)
                        deduction_description = get_code_description(product_code) if is_deduction else ''
                        disposal_category = get_disposal_category(product_code) if is_deduction else ''
                        
                        # 创建原始数据行（所有项目都添加到原始数据）
                        original_row = {
                            '序号': len(original_rows) + 1,
                            '原物料代码': material_code,
                            '原物料名称': row.get('物料描述', ''),
                            '原库存数量(TAI)': inventory_tai,
                            '原单位': unit,
                            '单台重量(KG/台)': unit_weight,
                            '投入产出比例': input_output_ratio,
                            '拆解系数': disassembly_coefficient,
                            '拆解产物编码': product_code,
                            '拆解产物名称': product_name,
                            '计算结果(KG)': round(calculated_amount_kg, 6),
                            '是否减扣': '是' if is_deduction else '否',
                            '减扣说明': deduction_description,
                            '处置类别': disposal_category,
                            '类别': '拆解产物',
                            '期间': row.get('期间', '')
                        }
                        original_rows.append(original_row)
                        
                        # 如果不需要减扣，也添加到减扣后数据中
                        if not is_deduction:
                            calc_row = {
                                '序号': len(calculated_rows) + 1,
                                '原物料代码': material_code,
                                '原物料名称': row.get('物料描述', ''),
                                '原库存数量(TAI)': inventory_tai,
                                '原单位': unit,
                                '单台重量(KG/台)': unit_weight,
                                '投入产出比例': input_output_ratio,
                                '拆解系数': disassembly_coefficient,
                                '拆解产物编码': product_code,
                                '拆解产物名称': product_name,
                                '计算结果(KG)': round(calculated_amount_kg, 6),
                                '处置类别': '',
                                '类别': '拆解产物',
                                '期间': row.get('期间', '')
                            }
                            calculated_rows.append(calc_row)
                        else:
                            # 添加到被减扣数据中
                            deducted_row = {
                                '序号': len(deducted_rows) + 1,
                                '原物料代码': material_code,
                                '原物料名称': row.get('物料描述', ''),
                                '原库存数量(TAI)': inventory_tai,
                                '原单位': unit,
                                '单台重量(KG/台)': unit_weight,
                                '投入产出比例': input_output_ratio,
                                '拆解系数': disassembly_coefficient,
                                '拆解产物编码': product_code,
                                '拆解产物名称': product_name,
                                '计算结果(KG)': round(calculated_amount_kg, 6),
                                '减扣说明': deduction_description,
                                '处置类别': disposal_category,
                                '类别': '拆解产物',
                                '期间': row.get('期间', '')
                            }
                            deducted_rows.append(deducted_row)
                            if len(original_rows) <= 10:  # 只打印前几条调试信息
                                print(f"减扣项目: {product_code} - {product_name} (计算值: {calculated_amount_kg:.6f}KG)")
                        
                        if len(original_rows) <= 5:  # 只打印前几条调试信息
                            deduct_text = " (减扣)" if is_deduction else ""
                            print(f"计算: {inventory_tai} × {unit_weight} × {input_output_ratio} × {disassembly_coefficient} = {calculated_amount_kg:.6f}KG{deduct_text}")
                else:
                    print(f"未找到物料代码 {material_code} 的拆解数据")
                    # 如果找不到对应的拆解系数，创建一个提示行
                    original_row = {
                        '序号': len(original_rows) + 1,
                        '原物料代码': material_code,
                        '原物料名称': row.get('物料描述', ''),
                        '原库存数量(TAI)': inventory_tai,
                        '原单位': unit,
                        '单台重量(KG/台)': '未找到数据',
                        '投入产出比例': '未找到数据',
                        '拆解系数': '未找到数据',
                        '拆解产物编码': '未找到数据',
                        '拆解产物名称': '未找到数据',
                        '计算结果(KG)': 0,
                        '是否减扣': '否',
                        '减扣说明': '',
                        '类别': '旧机',
                        '期间': row.get('期间', '')
                    }
                    original_rows.append(original_row)
                    
                    calc_row = {
                        '序号': len(calculated_rows) + 1,
                        '原物料代码': material_code,
                        '原物料名称': row.get('物料描述', ''),
                        '原库存数量(TAI)': inventory_tai,
                        '原单位': unit,
                        '单台重量(KG/台)': '未找到数据',
                        '投入产出比例': '未找到数据',
                        '拆解系数': '未找到数据',
                        '拆解产物编码': '未找到数据',
                        '拆解产物名称': '未找到数据',
                        '计算结果(KG)': 0,
                        '类别': '旧机',
                        '期间': row.get('期间', '')
                    }
                    calculated_rows.append(calc_row)

            # 添加非旧机类别的数据到计算结果中
            non_old_machine_data = data[data['类别'] != '旧机'].copy()
            
            if not non_old_machine_data.empty:
                print(f"添加 {len(non_old_machine_data)} 条非旧机数据到计算结果中")
                
                # 为非旧机数据创建统一的行格式
                for index, row in non_old_machine_data.iterrows():
                    # 获取库存数量，如果是数值型就保持原样，如果不是就设为0
                    inventory = row.get('非限制使用的库存', 0)
                    try:
                        inventory = float(inventory) if inventory != '' else 0
                    except (ValueError, TypeError):
                        inventory = 0
                    
                    # 检查非旧机产物是否需要减扣
                    material_code = str(row.get('物料代码', ''))
                    # 修复产物编码的小数点问题：确保是字符串并移除.0后缀
                    if material_code.endswith('.0'):
                        material_code = material_code[:-2]
                    is_deduction = should_deduct(material_code)
                    non_old_deduction_description = get_code_description(material_code) if is_deduction else ''
                    non_old_disposal_category = get_disposal_category(material_code) if is_deduction else ''
                    
                    # 添加到原始数据（所有非旧机项目）
                    original_non_old_row = {
                        '序号': len(original_rows) + 1,
                        '原物料代码': material_code,
                        '原物料名称': row.get('物料描述', ''),
                        '原库存数量(TAI)': '-',
                        '原单位': row.get('单位', ''),
                        '单台重量(KG/台)': '-',
                        '投入产出比例': '-',
                        '拆解系数': '-',
                        '拆解产物编码': material_code,
                        '拆解产物名称': row.get('物料描述', ''),
                        '计算结果(KG)': inventory,
                        '是否减扣': '是' if is_deduction else '否',
                        '减扣说明': non_old_deduction_description,
                        '处置类别': non_old_disposal_category,
                        '类别': row.get('类别', ''),
                        '期间': row.get('期间', '')
                    }
                    original_rows.append(original_non_old_row)
                    
                    # 如果不需要减扣，也添加到减扣后数据中
                    if not is_deduction:
                        non_old_row = {
                            '序号': len(calculated_rows) + 1,
                            '原物料代码': material_code,
                            '原物料名称': row.get('物料描述', ''),
                            '原库存数量(TAI)': '-',
                            '原单位': row.get('单位', ''),
                            '单台重量(KG/台)': '-',
                            '投入产出比例': '-',
                            '拆解系数': '-',
                            '拆解产物编码': material_code,
                            '拆解产物名称': row.get('物料描述', ''),
                            '计算结果(KG)': inventory,
                            '处置类别': '',
                            '类别': row.get('类别', ''),
                            '期间': row.get('期间', '')
                        }
                        calculated_rows.append(non_old_row)
                    else:
                        # 添加到被减扣数据中
                        deducted_non_old_row = {
                            '序号': len(deducted_rows) + 1,
                            '原物料代码': material_code,
                            '原物料名称': row.get('物料描述', ''),
                            '原库存数量(TAI)': '-',
                            '原单位': row.get('单位', ''),
                            '单台重量(KG/台)': '-',
                            '投入产出比例': '-',
                            '拆解系数': '-',
                            '拆解产物编码': material_code,
                            '拆解产物名称': row.get('物料描述', ''),
                            '计算结果(KG)': inventory,
                            '减扣说明': non_old_deduction_description,
                            '处置类别': non_old_disposal_category,
                            '类别': row.get('类别', ''),
                            '期间': row.get('期间', '')
                        }
                        deducted_rows.append(deducted_non_old_row)
                        print(f"减扣的非旧机项目: {material_code} - {row.get('物料描述', '')}")

            # 创建三个数据集
            original_data = pd.DataFrame(original_rows) if original_rows else pd.DataFrame()
            calculated_data = pd.DataFrame(calculated_rows) if calculated_rows else pd.DataFrame()
            deducted_data_df = pd.DataFrame(deducted_rows) if deducted_rows else pd.DataFrame()

            # 存储到数据管理器中
            self.app_data.set_data('disassembly_data', original_data)     # 原始数据(未减扣)
            self.app_data.set_data('calculated_data', calculated_data)    # 减扣后数据

            # 参考可销售量数据模式：deducted_data = 系统计算只读数据；deducted_data_manual = 手工编辑数据
            self.app_data.set_data('deducted_data', deducted_data_df.copy())
            print(f"📊 被减扣数据（只读）已更新: {len(deducted_data_df)} 条记录")

            deducted_data_modified = self.app_data.get_data('deducted_data_modified')
            deducted_data_manual = self.app_data.get_data('deducted_data_manual')

            if deducted_data_modified and deducted_data_manual is not None and not deducted_data_manual.empty:
                # 已编辑：保护用户修改，仅同步 TAI + 追加新增行
                print("🛡️ 检测到已编辑的手工数据，同步 TAI + 合并新增行")
                print(f"   - 系统计算: {len(deducted_data_df)} 条, 手工表: {len(deducted_data_manual)} 条")
                try:
                    from app.utils.deducted_disassembly_align import (
                        align_deducted_inventory_tai_from_disassembly,
                    )
                    synced_manual = align_deducted_inventory_tai_from_disassembly(
                        deducted_data_manual,
                        original_data,
                        recalculate_kg=False,
                        recalculate_kg_when_tai_changed=True,
                    )
                    # 合并新增行（以 原物料代码+拆解产物编码+处置类别 为唯一键）
                    def _make_key(r):
                        return (
                            str(r.get('原物料代码', '')).strip(),
                            str(r.get('拆解产物编码', '')).strip(),
                            str(r.get('处置类别', '')).strip(),
                        )
                    existing_keys = {_make_key(r) for _, r in synced_manual.iterrows()}
                    new_rows = [r.to_dict() for _, r in deducted_data_df.iterrows() if _make_key(r) not in existing_keys]
                    if new_rows:
                        merged = pd.concat([synced_manual, pd.DataFrame(new_rows)], ignore_index=True)
                        merged['序号'] = range(1, len(merged) + 1)
                        self.app_data.set_data('deducted_data_manual', merged)
                        print(f"   ➕ 追加 {len(new_rows)} 条新增行（{len(synced_manual)} → {len(merged)}）")
                    else:
                        self.app_data.set_data('deducted_data_manual', synced_manual)
                        print("   ✅ TAI 已同步，无新增行")
                except Exception as sync_err:
                    print(f"   ⚠️ 同步失败: {sync_err}")
            else:
                # 未编辑：直接复制系统数据到手工表
                self.app_data.set_data('deducted_data_manual', deducted_data_df.copy())
                print(f"🔄 手工表已同步为系统数据: {len(deducted_data_df)} 条记录")
            
            # 统计信息
            total_rows = len(calculated_rows)
            original_total_rows = len(original_rows)
            old_machine_rows = len([row for row in calculated_rows if row['类别'] == '拆解产物'])
            non_old_machine_rows = total_rows - old_machine_rows
            deducted_count = len(deducted_rows)
            
            print(f"✅ 旧机拆解计算完成:")
            print(f"   - 原始数据: {original_total_rows} 条记录")
            print(f"   - 减扣后数据: {total_rows} 条记录")
            print(f"     * 拆解产物: {old_machine_rows} 条")
            print(f"     * 非旧机产物: {non_old_machine_rows} 条")
            print(f"   - 被减扣数据: {deducted_count} 条记录")
            
            return True
            
        except Exception as e:
            print(f"✗ 旧机拆解计算失败: {e}")
            return False 
    
    def calculate_deep_processing_auto(self):
        """自动计算深加工，不弹窗不交互"""
        try:
            print("🏭 开始计算深加工...")
            
            # 🔧 重要：获取用于深加工计算的数据源
            # 优先使用手工编辑的数据（deducted_data_manual），确保修改后的数据参与计算
            deducted_data = self.app_data.get_data_for_deep_processing()
            if deducted_data is None or deducted_data.empty:
                print("⚠️ 没有被减扣数据，跳过深加工计算")
                return True
            
            # 明确显示使用的数据源类型
            data_source = self.app_data.get_data('deep_processing_data_source')
            is_manual = data_source == 'manual'
            print(f"📊 深加工计算数据源: {'手工编辑数据' if is_manual else '只读数据'}")
            print(f"   - 数据记录数: {len(deducted_data)} 条")
            
            # 如果使用的是手工数据，显示修改状态
            if is_manual:
                modified = self.app_data.get_data('deducted_data_modified')
                if modified:
                    print(f"   ✅ 使用已编辑的手工数据，修改后的数据将参与计算")
                else:
                    print(f"   ℹ️ 使用手工数据（未修改）")
                
            # 获取深加工拆解系数表数据
            deep_processing_df = dpd.get_deep_processing_dataframe()
            print(f"深加工拆解系数表: {len(deep_processing_df)} 条记录")
            
            # 创建深加工计算结果列表
            deep_processing_original_rows = []  # 深加工原始数据（包含减扣项）
            deep_processing_final_rows = []     # 深加工最终数据（减扣后）
            
            processed_count = 0
            matched_count = 0
            
            # 遍历被减扣数据表中的每条记录
            for index, row in deducted_data.iterrows():
                # 根据处置类别筛选：只处理需要深加工的类别
                category = row.get('类别', '')
                disposal_category = row.get('处置类别', '')
                deep_processing_categories = ['内转屏处置', '内转印制板处置', '深加工-打包铁', '深加工-塑料一破']
                
                if disposal_category not in deep_processing_categories:
                    continue
                    
                processed_count += 1
                
                # 获取拆解产物编码和计算结果
                material_code = str(row.get('拆解产物编码', ''))
                # 修复产物编码的小数点问题：确保是字符串并移除.0后缀
                if material_code.endswith('.0'):
                    material_code = material_code[:-2]
                calculation_result_kg = row.get('计算结果(KG)', 0)
                
                # 确保计算结果是数值
                try:
                    calculation_result_kg = float(calculation_result_kg) if calculation_result_kg != '' else 0
                except (ValueError, TypeError):
                    calculation_result_kg = 0
                    
                if calculation_result_kg <= 0:
                    continue
                
                # 根据拆解产物编码匹配深加工拆解系数表
                matching_records = deep_processing_df[deep_processing_df['拆解产物编码'] == material_code]
                
                if matching_records.empty:
                    continue
                
                matched_count += 1
                
                # 为每个匹配的深加工记录创建计算结果
                for _, deep_row in matching_records.iterrows():
                    deep_input_output_ratio = deep_row.get('深加工投入产出比例', 1.0)
                    deep_disassembly_coefficient = deep_row.get('深加工拆解系数', 1.0)
                    deep_product_code = str(deep_row.get('深加工产物编码', ''))
                    # 修复深加工产物编码的小数点问题：确保是字符串并移除.0后缀
                    if deep_product_code.endswith('.0'):
                        deep_product_code = deep_product_code[:-2]
                    deep_product_name = deep_row.get('深加工产物名称', '')
                    
                    # 计算深加工结果：被减扣数据的计算结果(KG) × 深加工投入产出比例 × 深加工拆解系数
                    deep_processing_result = calculation_result_kg * deep_input_output_ratio * deep_disassembly_coefficient
                    
                    # 检查深加工产物是否需要减扣
                    is_deduction = should_deduct(str(deep_product_code))
                    deep_deduction_description = get_code_description(str(deep_product_code)) if is_deduction else ''
                    deep_disposal_category = get_disposal_category(str(deep_product_code)) if is_deduction else ''
                    
                    # 创建深加工结果记录
                    deep_processing_row = {
                        '序号': len(deep_processing_original_rows) + 1,
                        '原物料代码': row.get('原物料代码', ''),
                        '原物料名称': row.get('原物料名称', ''),
                        '一次拆解产物编码': material_code,
                        '一次拆解产物名称': row.get('拆解产物名称', ''),
                        '一次拆解重量(KG)': calculation_result_kg,
                        '深加工投入产出比例': deep_input_output_ratio,
                        '深加工拆解系数': deep_disassembly_coefficient,
                        '深加工产物编码': deep_product_code,
                        '深加工产物名称': deep_product_name,
                        '深加工结果(KG)': round(deep_processing_result, 6),
                        '是否减扣': '是' if is_deduction else '否',
                        '减扣说明': deep_deduction_description,
                        '类别': '深加工产物',
                        '期间': row.get('期间', '')
                    }
                    
                    # 添加到原始数据
                    deep_processing_original_rows.append(deep_processing_row)
                    
                    # 如果不需要减扣，也添加到最终数据
                    if not is_deduction:
                        final_row = deep_processing_row.copy()
                        final_row['序号'] = len(deep_processing_final_rows) + 1
                        deep_processing_final_rows.append(final_row)
            
            # 创建深加工原始数据集（深加工数据）
            deep_processing_original_data = pd.DataFrame(deep_processing_original_rows) if deep_processing_original_rows else pd.DataFrame()
                
            # 创建深加工最终数据集（可销售量：减扣后数据 + 深加工最终数据）
            deep_processing_final_df = pd.DataFrame(deep_processing_final_rows) if deep_processing_final_rows else pd.DataFrame()
            
            # 合并减扣后数据与深加工最终数据，形成可销售量数据集
            calculated_final_data = self.app_data.get_data('calculated_data')
            
            # 使用合并逻辑
            saleable_data = self._merge_deducted_and_deep_processing_data(calculated_final_data, deep_processing_final_df)
            
            # 存储到新的数据结构中
            self.app_data.set_data('deep_processing_data', deep_processing_original_data)  # 深加工数据
            self.app_data.set_data('saleable_data', saleable_data)                        # 可销售量数据
            
            # 自动初始化可销售量手工数据（仅当没有手工数据时）
            if not saleable_data.empty:
                try:
                    existing_manual = self.app_data.get_data('saleable_data_manual')
                    if existing_manual is None or existing_manual.empty:
                        print("🔄 自动初始化可销售量手工数据...")
                        manual_data = saleable_data.copy()
                        self.app_data.set_data('saleable_data_manual', manual_data)
                        # 注意：这里不设置 saleable_data_modified，只有用户手工编辑时才设置
                        from datetime import datetime
                        self.app_data.set_data('saleable_auto_init_timestamp', datetime.now().isoformat())
                        print(f"✅ 可销售量手工数据自动初始化完成: {len(manual_data)} 条记录（未标记为手工修改）")
                    else:
                        print(f"可销售量手工数据已存在，保持用户修改（{len(existing_manual)} 条记录）")
                except Exception as init_error:
                    print(f"⚠️ 自动初始化可销售量手工数据失败: {init_error}")
            
            # 统计信息
            original_count = len(deep_processing_original_rows)
            deep_final_count = len(deep_processing_final_rows)
            deducted_count = original_count - deep_final_count
            
            print(f"✅ 深加工计算完成:")
            print(f"   - 处理拆解产物: {processed_count} 个")
            print(f"   - 匹配深加工数据: {matched_count} 个")
            print(f"   - 深加工原始记录: {original_count} 条")
            print(f"   - 深加工最终记录: {deep_final_count} 条")
            print(f"   - 深加工减扣记录: {deducted_count} 条")
            
            return True
            
        except Exception as e:
            print(f"✗ 深加工计算失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _merge_deducted_and_deep_processing_data(self, calculated_final_data, deep_processing_final_df):
        """合并减扣后数据与深加工最终数据，形成可销售量数据集"""
        try:
            # 如果没有减扣后数据，直接返回深加工最终数据
            if calculated_final_data is None or calculated_final_data.empty:
                print("没有减扣后数据，仅返回深加工最终数据")
                return deep_processing_final_df
            
            # 如果没有深加工最终数据，直接返回减扣后数据
            if deep_processing_final_df.empty:
                print("没有深加工最终数据，仅返回减扣后数据")
                return calculated_final_data.copy()
            
            print(f"开始合并数据：减扣后数据 {len(calculated_final_data)} 条 + 深加工最终数据 {len(deep_processing_final_df)} 条")
            
            # 准备合并的数据
            merged_rows = []
            
            # 1. 添加减扣后数据（保持原有格式）
            for index, row in calculated_final_data.iterrows():
                merged_row = {
                    '序号': len(merged_rows) + 1,
                    '原物料代码': row.get('原物料代码', ''),
                    '原物料名称': row.get('原物料名称', ''),
                    '拆解产物编码': row.get('拆解产物编码', ''),
                    '拆解产物名称': row.get('拆解产物名称', ''),
                    '拆解系数': row.get('拆解系数', ''),
                    '原物料重量(KG)': row.get('原物料重量(KG)', ''),
                    '计算结果(KG)': row.get('计算结果(KG)', ''),
                    '是否减扣': row.get('是否减扣', ''),
                    '减扣说明': row.get('减扣说明', ''),
                    '处置类别': row.get('处置类别', ''),
                    '类别': row.get('类别', ''),
                    '期间': row.get('期间', '')
                }
                merged_rows.append(merged_row)
            
            # 2. 添加深加工最终数据（调整格式以匹配减扣后数据）
            for index, row in deep_processing_final_df.iterrows():
                merged_row = {
                    '序号': len(merged_rows) + 1,
                    '原物料代码': row.get('原物料代码', ''),
                    '原物料名称': row.get('原物料名称', ''),
                    '拆解产物编码': row.get('深加工产物编码', ''),  # 深加工产物编码映射到拆解产物编码
                    '拆解产物名称': row.get('深加工产物名称', ''),  # 深加工产物名称映射到拆解产物名称
                    '拆解系数': f"{row.get('深加工投入产出比例', '')}×{row.get('深加工拆解系数', '')}",  # 组合系数
                    '原物料重量(KG)': row.get('一次拆解重量(KG)', ''),  # 一次拆解重量作为原物料重量
                    '计算结果(KG)': row.get('深加工结果(KG)', ''),  # 深加工结果映射到计算结果
                    '是否减扣': row.get('是否减扣', ''),
                    '减扣说明': row.get('减扣说明', ''),
                    '处置类别': row.get('处置类别', ''),  # 深加工产物的处置类别为空
                    '类别': row.get('类别', ''),
                    '期间': row.get('期间', '')
                }
                merged_rows.append(merged_row)
            
            # 创建合并后的DataFrame
            if merged_rows:
                merged_df = pd.DataFrame(merged_rows)
                
                # 确保数值列的数据类型正确
                numeric_columns = ['计算结果(KG)', '原物料重量(KG)']
                for col in numeric_columns:
                    if col in merged_df.columns:
                        try:
                            merged_df[col] = pd.to_numeric(merged_df[col], errors='coerce')
                        except Exception as e:
                            print(f"⚠️ 转换{col}列数据类型失败: {e}")
                
                print(f"合并完成：总计 {len(merged_df)} 条记录")
                return merged_df
            else:
                print("合并结果为空")
                return pd.DataFrame()
                
        except Exception as e:
            print(f"数据合并出错: {str(e)}")
            import traceback
            traceback.print_exc()
            # 出错时返回减扣后数据
            return calculated_final_data.copy() if calculated_final_data is not None else pd.DataFrame() 
    
    def merge_saleable_data(self):
        """重新合并生成可销售量数据（包含价格和收益计算）"""
        try:
            print("🔄 开始重新合并可销售量数据...")
            
            # 获取减扣后数据和深加工数据
            calculated_data = self.app_data.get_data('calculated_data')
            deep_processing_data = self.app_data.get_data('deep_processing_data')
            
            # 从深加工数据中提取最终数据（非减扣项）
            deep_processing_final_rows = []
            if deep_processing_data is not None and not deep_processing_data.empty:
                for index, row in deep_processing_data.iterrows():
                    # 只包含非减扣的深加工产物
                    if row.get('是否减扣', '否') == '否':
                        deep_processing_final_rows.append(row.to_dict())
            
            deep_processing_final_df = pd.DataFrame(deep_processing_final_rows) if deep_processing_final_rows else pd.DataFrame()
            
            # 使用合并逻辑
            saleable_data = self._merge_deducted_and_deep_processing_data(calculated_data, deep_processing_final_df)
            
            # 添加价格和收益列
            if not saleable_data.empty:
                print("添加价格和收益信息...")
                
                # 获取价格映射（返回的是不含税价）
                price_mapping_no_tax = get_price_mapping()
                
                # 获取完整价格数据以便获取含税价
                from data.base_data.price_data import load_price_data
                price_df = load_price_data()
                
                if price_mapping_no_tax and price_df is not None:
                    print(f"加载了 {len(price_mapping_no_tax)} 个产物的价格信息（不含税）")
                    print(f"示例不含税价映射: {dict(list(price_mapping_no_tax.items())[:3])}")
                    
                    # 打印一些产物编码用于调试
                    sample_codes = saleable_data['拆解产物编码'].head(5).tolist()
                    print(f"可销售量数据中的示例产物编码: {sample_codes}")
                    
                    # 创建含税价映射
                    price_mapping_with_tax = {}
                    for _, row in price_df.iterrows():
                        code = str(row['拆解产物编码']).strip()
                        price_with_tax = row['销售单价(元/KG)']
                        if pd.notna(price_with_tax):
                            price_mapping_with_tax[code] = float(price_with_tax)
                    
                    # 添加含税价列
                    saleable_data['销售单价(元/KG)'] = saleable_data['拆解产物编码'].apply(
                        lambda code: price_mapping_with_tax.get(str(code).strip(), 0)
                    )
                    
                    # 添加不含税价列
                    saleable_data['销售单价-不含税(元/KG)'] = saleable_data['拆解产物编码'].apply(
                        lambda code: price_mapping_no_tax.get(str(code).strip(), 0)
                    )
                    
                    # 使用不含税价计算销售收益
                    saleable_data['销售收益(元)'] = saleable_data.apply(
                        lambda row: round(float(row['计算结果(KG)']) * float(row['销售单价-不含税(元/KG)']), 2)
                        if row['计算结果(KG)'] and row['销售单价-不含税(元/KG)'] else 0,
                        axis=1
                    )
                    
                    matched = (saleable_data['销售单价-不含税(元/KG)'] > 0).sum()
                    unmatched = (saleable_data['销售单价-不含税(元/KG)'] == 0).sum()
                    total_revenue = saleable_data['销售收益(元)'].sum()
                    print(f"价格匹配完成: 匹配 {matched} 个, 未匹配 {unmatched} 个")
                    print(f"总收益（使用不含税价计算）: {total_revenue:.2f} 元")
                else:
                    print("警告: 价格数据为空，设置默认价格为0")
                    saleable_data['销售单价(元/KG)'] = 0
                    saleable_data['销售单价-不含税(元/KG)'] = 0
                    saleable_data['销售收益(元)'] = 0
            
            # 存储合并后的可销售量数据
            self.app_data.set_data('saleable_data', saleable_data)
            
            # 保存持久化数据，确保数据被保存到数据库
            try:
                self.app_data.save_persistent_data()
                print("✅ 可销售量数据已持久化保存")
            except Exception as save_error:
                print(f"⚠️ 持久化保存可销售量数据失败: {save_error}")
            
            # 自动初始化可销售量手工数据（但不标记为已修改）
            if not saleable_data.empty:
                try:
                    print("自动同步可销售量手工数据...")
                    # 检查是否已有手工数据
                    existing_manual = self.app_data.get_data('saleable_data_manual')
                    # 🔧 重要：只有当被减扣数据未修改且可销售量数据未被手工修改时，才更新手工数据为系统计算的数据
                    deducted_data_modified = self.app_data.get_data('deducted_data_modified')
                    saleable_data_modified = self.app_data.get_data('saleable_data_modified')
                    if not deducted_data_modified and not saleable_data_modified:
                        # 被减扣数据未修改且可销售量数据未被手工修改，更新手工数据为系统计算的数据
                        manual_data = saleable_data.copy()
                        self.app_data.set_data('saleable_data_manual', manual_data)
                        self.app_data.set_data('saleable_data_modified', False)  # 确保标记为未修改
                        from datetime import datetime
                        self.app_data.set_data('saleable_auto_sync_timestamp', datetime.now().isoformat())
                        print(f"✅ 可销售量手工数据已更新为系统计算的数据（被减扣数据未修改且可销售量数据未手工修改）: {len(manual_data)} 条记录")
                    elif existing_manual is None or existing_manual.empty:
                        # 没有手工数据，自动初始化（但不设置修改标志）
                        manual_data = saleable_data.copy()
                        self.app_data.set_data('saleable_data_manual', manual_data)
                        # 注意：这里不设置 saleable_data_modified，只有用户手工编辑时才设置
                        from datetime import datetime
                        self.app_data.set_data('saleable_auto_sync_timestamp', datetime.now().isoformat())
                        print(f"可销售量手工数据自动初始化完成: {len(manual_data)} 条记录（未标记为手工修改）")
                    else:
                        # 手工数据已存在：未标记手工修改时同步系统重量；已标记（含 Excel 导入）时保留手工计算结果(KG)，仅刷新价格与收益
                        if saleable_data_modified:
                            print("可销售量数据已标记手工修改（含 Excel 导入），保留手工计算结果(KG)；仅刷新价格并重算销售收益...")
                        else:
                            print("手工数据已存在，计算结果(KG)从系统重算同步，并更新价格与收益列...")
                        
                        if not saleable_data_modified:
                            # 仅在未手工修改时：将系统合并结果同步到手工表，便于上游被减扣/拆解变更后重量连续更新
                            if '拆解产物编码' in existing_manual.columns and '拆解产物编码' in saleable_data.columns:
                                saleable_weight_map = {}
                                for idx, row in saleable_data.iterrows():
                                    code = str(row.get('拆解产物编码', '')).strip()
                                    category = str(row.get('类别', '')).strip()
                                    material_code = str(row.get('原物料代码', '')).strip()
                                    weight = row.get('计算结果(KG)', 0)
                                    match_key = f"{code}|{category}|{material_code}"
                                    if code and pd.notna(weight):
                                        try:
                                            saleable_weight_map[match_key] = float(weight)
                                        except (ValueError, TypeError):
                                            pass
                                if '计算结果(KG)' in existing_manual.columns:
                                    updated_count = 0
                                    for idx, row in existing_manual.iterrows():
                                        code = str(row.get('拆解产物编码', '')).strip()
                                        category = str(row.get('类别', '')).strip()
                                        material_code = str(row.get('原物料代码', '')).strip()
                                        match_key = f"{code}|{category}|{material_code}"
                                        if match_key in saleable_weight_map:
                                            new_weight = saleable_weight_map[match_key]
                                            old_weight = row.get('计算结果(KG)', 0)
                                            try:
                                                old_weight = float(old_weight) if pd.notna(old_weight) else 0
                                            except (ValueError, TypeError):
                                                old_weight = 0
                                            if abs(new_weight - old_weight) > 0.0001:
                                                existing_manual.at[idx, '计算结果(KG)'] = new_weight
                                                updated_count += 1
                                                print(f"  更新记录 {idx}: {code} ({category}) - 重量 {old_weight:.6f} -> {new_weight:.6f} KG")
                                    if updated_count > 0:
                                        print(f"✅ 已同步 {updated_count} 条记录的计算结果(KG)从系统数据到手工数据")
                        
                        # 重新获取价格映射（确保使用最新的价格数据）
                        manual_price_mapping_no_tax = get_price_mapping()
                        manual_price_df = load_price_data()
                        
                        if manual_price_mapping_no_tax and manual_price_df is not None:
                            # 创建含税价映射
                            manual_price_mapping_with_tax = {}
                            for _, row in manual_price_df.iterrows():
                                code = str(row['拆解产物编码']).strip()
                                price_with_tax = row['销售单价(元/KG)']
                                if pd.notna(price_with_tax):
                                    manual_price_mapping_with_tax[code] = float(price_with_tax)
                            
                            # 更新价格列（含税价和不含税价）
                            if '拆解产物编码' in existing_manual.columns:
                                # 更新含税价
                                existing_manual['销售单价(元/KG)'] = existing_manual['拆解产物编码'].apply(
                                    lambda code: manual_price_mapping_with_tax.get(str(code).strip(), existing_manual.loc[existing_manual['拆解产物编码'] == code, '销售单价(元/KG)'].iloc[0] if len(existing_manual[existing_manual['拆解产物编码'] == code]) > 0 else 0)
                                )
                                # 更新不含税价
                                existing_manual['销售单价-不含税(元/KG)'] = existing_manual['拆解产物编码'].apply(
                                    lambda code: manual_price_mapping_no_tax.get(str(code).strip(), existing_manual.loc[existing_manual['拆解产物编码'] == code, '销售单价-不含税(元/KG)'].iloc[0] if len(existing_manual[existing_manual['拆解产物编码'] == code]) > 0 else 0)
                                )
                                # 重新计算销售收益（不含税价 × 当前手工表计算结果(KG)）
                                existing_manual['销售收益(元)'] = existing_manual.apply(
                                    lambda row: round(float(row['计算结果(KG)']) * float(row['销售单价-不含税(元/KG)']), 2)
                                    if row['计算结果(KG)'] and row['销售单价-不含税(元/KG)'] else 0,
                                    axis=1
                                )
                                # 保存更新后的手工数据
                                self.app_data.set_data('saleable_data_manual', existing_manual)
                                total_revenue = existing_manual['销售收益(元)'].sum()
                                print(f"✅ 手工数据价格和收益已更新: {len(existing_manual)} 条记录，总收益: {total_revenue:.2f} 元")
                        
                        # 如果上面的更新没有执行（因为条件不满足），则执行备用逻辑
                        elif '销售收益(元)' not in existing_manual.columns or '销售单价(元/KG)' not in existing_manual.columns:
                            print("手工数据缺少价格或收益列，添加这些列...")
                            
                            # 获取价格映射（不含税价）
                            price_mapping_no_tax = get_price_mapping()
                            # 获取完整价格数据以便获取含税价
                            from data.base_data.price_data import load_price_data
                            price_df = load_price_data()
                            
                            if price_mapping_no_tax and price_df is not None:
                                # 创建含税价映射
                                price_mapping_with_tax = {}
                                for _, row in price_df.iterrows():
                                    code = str(row['拆解产物编码']).strip()
                                    price_with_tax = row['销售单价(元/KG)']
                                    if pd.notna(price_with_tax):
                                        price_mapping_with_tax[code] = float(price_with_tax)
                                
                                # 添加或更新销售单价列（含税价）
                                existing_manual['销售单价(元/KG)'] = existing_manual['拆解产物编码'].apply(
                                    lambda code: price_mapping_with_tax.get(str(code).strip(), 0)
                                )
                                
                                # 添加或更新不含税价列
                                existing_manual['销售单价-不含税(元/KG)'] = existing_manual['拆解产物编码'].apply(
                                    lambda code: price_mapping_no_tax.get(str(code).strip(), 0)
                                )
                                
                                # 计算销售收益（使用不含税价）
                                existing_manual['销售收益(元)'] = existing_manual.apply(
                                    lambda row: round(float(row['计算结果(KG)']) * float(row['销售单价-不含税(元/KG)']), 2)
                                    if row['计算结果(KG)'] and row['销售单价-不含税(元/KG)'] else 0,
                                    axis=1
                                )
                                
                                # 保存更新后的手工数据
                                self.app_data.set_data('saleable_data_manual', existing_manual)
                                total_revenue = existing_manual['销售收益(元)'].sum()
                                print(f"✅ 手工数据价格和收益列已添加: {len(existing_manual)} 条记录，总收益: {total_revenue:.2f} 元")
                            else:
                                print("警告: 无法获取价格数据，跳过收益计算")
                        else:
                            # 即使有收益列，也要检查是否需要重新计算（例如价格更新了）
                            # 这里可以选择性地更新，暂时保持用户的手工修改
                            print("手工数据已包含价格和收益列，保持用户修改")
                        
                        # 保存手工数据的持久化（统一保存）
                        try:
                            self.app_data.save_persistent_data()
                            print("✅ 可销售量手工数据已持久化保存")
                        except Exception as save_error:
                            print(f"⚠️ 持久化保存可销售量手工数据失败: {save_error}")
                            
                except Exception as init_error:
                    print(f"警告: 自动同步可销售量手工数据失败: {init_error}")
            
            print(f"✅ 可销售量数据重新合并完成: {len(saleable_data)} 条记录")
            return True
            
        except Exception as e:
            print(f"✗ 可销售量数据合并失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def calculate_subsidy_income(self):
        """计算基金补贴收入"""
        try:
            print("💰 开始计算基金补贴收入...")
            
            # 获取提取数据（优先手工版）
            manual_extracted_data = self.app_data.get_data('extracted_data_manual')
            if manual_extracted_data is not None and not manual_extracted_data.empty:
                print("🔄 使用手工编辑的提取结果数据")
                extracted_data = manual_extracted_data
            else:
                # 使用原始提取数据
                extracted_data = self.app_data.get_data('extracted_data')
                if extracted_data is None or extracted_data.empty:
                    print("⚠️ 没有提取数据，跳过补贴收入计算")
                    return True
                print("🔄 使用原始提取结果数据")
            
            # 筛选类别为"旧机"的记录
            old_machine_data = extracted_data[extracted_data['类别'] == '旧机'].copy()
            
            if old_machine_data.empty:
                print("⚠️ 没有找到类别为'旧机'的记录，跳过补贴收入计算")
                # 存储空的补贴收入数据
                self.app_data.set_data('subsidy_income_data', pd.DataFrame())
                return True
            
            print(f"找到 {len(old_machine_data)} 条旧机记录")
            
            # 获取补贴单价映射
            subsidy_mapping = get_subsidy_mapping()
            if not subsidy_mapping:
                print("⚠️ 无法获取补贴单价数据")
                self.app_data.set_data('subsidy_income_data', pd.DataFrame())
                return True
            
            print(f"补贴单价映射: {subsidy_mapping}")
            
            # 创建补贴收入计算结果列表
            subsidy_income_rows = []
            category_summary = {}  # 按类别汇总
            
            # 遍历旧机数据
            for index, row in old_machine_data.iterrows():
                material_code = str(row.get('物料代码', ''))
                material_desc = str(row.get('物料描述', ''))
                inventory_tai = row.get('非限制使用的库存', 0)
                period = row.get('期间', '')
                
                # 确保库存数量是数值
                try:
                    inventory_tai = float(inventory_tai) if inventory_tai != '' else 0
                except (ValueError, TypeError):
                    inventory_tai = 0
                
                if inventory_tai <= 0:
                    continue
                
                # 根据物料描述匹配补贴大类
                subsidy_category = match_category_by_description(material_desc)
                
                if not subsidy_category:
                    # 没有匹配到补贴类别，跳过
                    continue
                
                # 获取补贴单价
                subsidy_price = subsidy_mapping.get(subsidy_category)
                
                if not subsidy_price or subsidy_price <= 0:
                    continue
                
                # 计算补贴收入：当期拆解量(台) × 补贴单价(元/台)
                subsidy_income = inventory_tai * subsidy_price
                
                # 创建补贴收入记录
                subsidy_row = {
                    '序号': len(subsidy_income_rows) + 1,
                    '物料代码': material_code,
                    '物料描述': material_desc,
                    '补贴大类': subsidy_category,
                    '当期拆解量(台)': inventory_tai,
                    '补贴单价(元/台)': subsidy_price,
                    '基金补贴收入(元)': round(subsidy_income, 2),
                    '期间': period
                }
                subsidy_income_rows.append(subsidy_row)
                
                # 按类别汇总
                if subsidy_category not in category_summary:
                    category_summary[subsidy_category] = {
                        '拆解量': 0,
                        '补贴收入': 0
                    }
                category_summary[subsidy_category]['拆解量'] += inventory_tai
                category_summary[subsidy_category]['补贴收入'] += subsidy_income
                
                print(f"匹配: {material_desc} -> {subsidy_category}, {inventory_tai}台 × {subsidy_price}元/台 = {subsidy_income:.2f}元")
            
            # 创建补贴收入数据集
            if subsidy_income_rows:
                subsidy_income_df = pd.DataFrame(subsidy_income_rows)
                self.app_data.set_data('subsidy_income_data', subsidy_income_df)
                
                # 统计信息
                total_subsidy = subsidy_income_df['基金补贴收入(元)'].sum()
                total_quantity = subsidy_income_df['当期拆解量(台)'].sum()
                
                print(f"✅ 基金补贴收入计算完成:")
                print(f"   - 匹配记录: {len(subsidy_income_df)} 条")
                print(f"   - 拆解总量: {total_quantity:.2f} 台")
                print(f"   - 补贴总收入: {total_subsidy:.2f} 元")
                print(f"   - 按类别汇总:")
                for category, data in category_summary.items():
                    print(f"     * {category}: {data['拆解量']:.2f}台, {data['补贴收入']:.2f}元")
            else:
                print("⚠️ 没有匹配到任何补贴类别")
                self.app_data.set_data('subsidy_income_data', pd.DataFrame())
            
            return True
            
        except Exception as e:
            print(f"✗ 基金补贴收入计算失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def add_subsidy_to_saleable_data(self):
        """
        注意：基金补贴收入不添加到可销售量数据的每一行中
        基金补贴收入是针对"旧机"这个整体的，不应该分摊到拆解产物上
        这个方法现在只是打印统计信息，不修改可销售量数据
        """
        try:
            print("💰 统计基金补贴收入...")
            
            # 获取补贴收入数据
            subsidy_income_data = self.app_data.get_data('subsidy_income_data')
            
            # 获取可销售量数据（用于统计销售收益）
            saleable_data = self.app_data.get_data('saleable_data')
            
            # 统计销售收益
            total_sales_revenue = 0
            if saleable_data is not None and not saleable_data.empty and '销售收益(元)' in saleable_data.columns:
                total_sales_revenue = saleable_data['销售收益(元)'].sum()
            
            # 统计基金补贴收入
            total_subsidy = 0
            if subsidy_income_data is not None and not subsidy_income_data.empty and '基金补贴收入(元)' in subsidy_income_data.columns:
                total_subsidy = subsidy_income_data['基金补贴收入(元)'].sum()
            
            # 计算总收益
            total_revenue = total_sales_revenue + total_subsidy
            
            print(f"✅ 收益统计完成:")
            print(f"   - 销售收益（拆解产物）: {total_sales_revenue:.2f} 元")
            print(f"   - 基金补贴收入（旧机）: {total_subsidy:.2f} 元")
            print(f"   - 总收益: {total_revenue:.2f} 元")
            
            return True
            
        except Exception as e:
            print(f"✗ 收益统计失败: {e}")
            import traceback
            traceback.print_exc()
            return False