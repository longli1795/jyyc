import pandas as pd
import numpy as np
from app.models.compatibility import AppDataManager
from data.base_data.mapping_data import get_mapping_dataframe, get_old_machine_mapping


def _normalize_material_code(code) -> str:
    """规范化物料代码（去空格、去 .0 后缀）"""
    s = str(code).strip()
    if s.endswith('.0'):
        s = s[:-2]
    return s


def supplement_old_machine_from_mapping(df: pd.DataFrame) -> tuple:
    """将内置映射表中缺失的旧机 R3 代码补入 DataFrame，返回 (补全后df, 新增行数)"""
    old_machine_mapping = get_old_machine_mapping()
    if old_machine_mapping is None or old_machine_mapping.empty:
        return (df if df is not None else pd.DataFrame()), 0

    if df is None:
        df = pd.DataFrame()

    existing_codes = set()
    if not df.empty and '类别' in df.columns and '物料代码' in df.columns:
        old_rows = df[df['类别'] == '旧机']
        existing_codes = {
            _normalize_material_code(c) for c in old_rows['物料代码']
        }

    period_default = ''
    unit_default = 'TAI'
    if not df.empty:
        if '期间' in df.columns:
            period_series = df['期间'].dropna()
            if len(period_series) > 0:
                period_default = period_series.iloc[0]
        if '类别' in df.columns and '单位' in df.columns:
            old_with_unit = df[
                (df['类别'] == '旧机') & df['单位'].notna() & (df['单位'].astype(str) != '')
            ]
            if len(old_with_unit) > 0:
                unit_default = str(old_with_unit['单位'].iloc[0])

    manual_columns = ['初始数据', '本期计划采购数量', '计划采购单价', '本期计划投产数量']
    new_rows = []
    for _, mapping_row in old_machine_mapping.iterrows():
        code = _normalize_material_code(mapping_row['R3系统代码'])
        if code in existing_codes:
            continue

        new_row = {
            '类别': '旧机',
            '物料代码': code,
            '物料描述': str(mapping_row.get('系统名称', '')).strip(),
            '单位': unit_default,
            '期间': period_default,
            '非限制使用的库存': 0,
            '价值': 0,
            '单价': 0,
            '库位描述': '',
        }
        for col in manual_columns:
            if not df.empty and col in df.columns:
                new_row[col] = 0.0
        new_rows.append(new_row)
        existing_codes.add(code)

    if not new_rows:
        return df, 0

    new_df = pd.DataFrame(new_rows)
    if df.empty:
        result = new_df
    else:
        for col in df.columns:
            if col not in new_df.columns:
                if pd.api.types.is_numeric_dtype(df[col]):
                    new_df[col] = 0
                else:
                    new_df[col] = ''
        for col in new_df.columns:
            if col not in df.columns:
                if pd.api.types.is_numeric_dtype(new_df[col]):
                    df[col] = 0
                else:
                    df[col] = ''
        result = pd.concat([df, new_df], ignore_index=True)

    if '序号' in result.columns:
        result['序号'] = list(range(1, len(result) + 1))
    else:
        result.insert(0, '序号', list(range(1, len(result) + 1)))

    old_count = len(result[result['类别'] == '旧机']) if '类别' in result.columns else 0
    print(f"✅ 补全旧机物料: 新增 {len(new_rows)} 条，当前共 {old_count} 条旧机")
    return result, len(new_rows)


class DataProcessor:
    """数据处理核心类"""
    
    def __init__(self, session_id: str = None):
        self.app_data = AppDataManager.get_instance(session_id)
    
    def create_column_mapping(self, data):
        """
        创建列名映射字典
        将数据中的列名映射到标准列名
        """
        mapping = {}
        
        # 定义标准列名及其可能的别名
        standard_columns = {
            '期间': ['期间', '会计期间', '月份', '年月', 'period', 'month'],
            '物料代码': ['物料代码', '物料编码', '代码', '编码', 'material_code', 'code'],
            '物料描述': ['物料描述', '物料名称', '描述', '名称', 'description', 'name'],
            '单位': ['单位', '计量单位', 'unit'],
            '非限制使用的库存': ['非限制使用的库存', '库存', '库存数量', 'stock', 'inventory'],
            '价值': ['价值', '金额', '总价值', 'value', 'amount'],
            '单价': ['单价', '价格', '单位价格', 'price', 'unit_price'],
            '库位描述': ['库位描述', '库位', '仓库', '存储位置', 'location', 'warehouse']
        }
        
        # 遍历数据的列名，尝试匹配标准列名
        for col in data.columns:
            col_str = str(col).strip()
            
            for standard_name, aliases in standard_columns.items():
                # 检查完全匹配或包含关系
                for alias in aliases:
                    if (col_str == alias or 
                        alias in col_str or 
                        col_str in alias):
                        mapping[standard_name] = col
                        print(f"列映射: {standard_name} -> {col}")
                        break
                
                # 如果找到映射，跳出循环
                if standard_name in mapping:
                    break
        
        return mapping
    
    def extract_data_auto(self):
        """自动提取数据（无用户交互）"""
        try:
            print("🔍 开始提取数据...")
            
            # 调试：检查会话ID
            session_id = getattr(self.app_data, '_session_manager', {})
            if hasattr(session_id, 'session_id'):
                print(f"🔑 当前会话ID: {session_id.session_id}")
            
            from app.services.opening_inventory_store import get_global_source_data

            source_data = get_global_source_data()
            if source_data is None:
                source_data = self.app_data.get_data('source_data')
            mapping_data = self.app_data.get_data('mapping_data')
            
            print(f"📊 源数据状态: {'已加载' if source_data is not None else '未加载'} ({len(source_data) if source_data is not None else 0} 行)")
            print(f"🗺️ 映射数据状态: {'已加载' if mapping_data is not None else '未加载'} ({len(mapping_data) if mapping_data is not None else 0} 条记录)")
            
            # 如果数据为空，尝试重新加载映射数据
            if mapping_data is None:
                print("🔄 尝试重新加载映射数据...")
                try:
                    from data.base_data.mapping_data import get_mapping_dataframe
                    mapping_data = get_mapping_dataframe()
                    if mapping_data is not None and not mapping_data.empty:
                        self.app_data.set_data('mapping_data', mapping_data)
                        print(f"✅ 映射数据重新加载成功: {len(mapping_data)} 条记录")
                except Exception as e:
                    print(f"❌ 映射数据重新加载失败: {e}")
            
            if source_data is None or mapping_data is None:
                raise Exception("源数据或映射表未加载")

            # 获取映射表中的R3系统代码
            mapping_codes = []
            mapping_code_column = None

            if 'R3系统代码' in mapping_data.columns:
                mapping_code_column = 'R3系统代码'
                mapping_codes = mapping_data['R3系统代码'].astype(str).tolist()
            else:
                # 尝试找到包含"代码"或"编码"的列
                code_columns = [col for col in mapping_data.columns if '代码' in col or '编码' in col or 'code' in col.lower()]
                if code_columns:
                    mapping_code_column = code_columns[0]
                    mapping_codes = mapping_data[code_columns[0]].astype(str).tolist()
                else:
                    # 如果没有找到代码列，使用第二列（通常是代码列）
                    if len(mapping_data.columns) >= 2:
                        mapping_code_column = mapping_data.columns[1]
                        mapping_codes = mapping_data.iloc[:, 1].astype(str).tolist()
                    else:
                        raise Exception("映射表中未找到代码列")

            # 在总数据中查找精确匹配的行
            extracted_rows = []
            matched_info = []

            # 将总数据的所有列转换为字符串进行比较
            source_data_str = source_data.astype(str)

            for code in mapping_codes:
                # 在总数据的每一列中查找完全匹配的代码
                for col in source_data_str.columns:
                    matching_rows = source_data_str[source_data_str[col] == code]
                    if not matching_rows.empty:
                        for idx in matching_rows.index:
                            # 获取原始数据行
                            original_row = source_data.loc[idx]
                            extracted_rows.append(original_row)
                            matched_info.append({
                                'code': code,
                                'column': col,
                                'row_index': idx
                            })

            if extracted_rows:
                extracted_df = pd.DataFrame(extracted_rows)
                extracted_df.reset_index(drop=True, inplace=True)

                # 添加匹配信息
                matched_codes = [info['code'] for info in matched_info]

                # 合并映射表信息
                mapping_dict = {}
                for _, mapping_row in mapping_data.iterrows():
                    code = str(mapping_row[mapping_code_column])
                    mapping_dict[code] = mapping_row.to_dict()

                # 添加映射表的类别信息
                categories = []
                for code in matched_codes:
                    if code in mapping_dict and '类别' in mapping_dict[code]:
                        categories.append(mapping_dict[code]['类别'])
                    else:
                        categories.append('')

                # 创建列名映射字典（根据常见的列名模式）
                column_mapping = self.create_column_mapping(extracted_df)

                # 构建最终的结果数据框
                final_data = {}

                # 第一列：序号
                final_data['序号'] = list(range(1, len(extracted_df) + 1))

                # 第二列：类别
                final_data['类别'] = categories

                # 按指定顺序添加其他列
                required_columns = ['期间', '物料代码', '物料描述', '单位', '非限制使用的库存', '价值', '单价', '库位描述']

                for col_name in required_columns:
                    if col_name in column_mapping and column_mapping[col_name] in extracted_df.columns:
                        source_col = column_mapping[col_name]
                        final_data[col_name] = extracted_df[source_col].tolist()
                        print(f"✓ 映射成功: {col_name} -> {source_col}")
                    else:
                        # 如果找不到对应列，尝试直接匹配列名
                        found = False
                        for source_col in extracted_df.columns:
                            if col_name in str(source_col) or str(source_col) in col_name:
                                final_data[col_name] = extracted_df[source_col].tolist()
                                print(f"✓ 模糊匹配: {col_name} -> {source_col}")
                                found = True
                                break
                        if not found:
                            final_data[col_name] = [''] * len(extracted_df)
                            print(f"✗ 未找到列: {col_name}")

                # 转换为DataFrame并补全缺失的旧机物料
                extracted_data = pd.DataFrame(final_data)
                extracted_data, added = supplement_old_machine_from_mapping(extracted_data)
                self.app_data.set_data('extracted_data', extracted_data)

                print(f"✅ 数据提取完成: 共提取 {len(extracted_data)} 条记录（补全旧机 {added} 条）")
                return True

            else:
                extracted_data, added = supplement_old_machine_from_mapping(pd.DataFrame())
                self.app_data.set_data('extracted_data', extracted_data)
                if added > 0:
                    print(f"⚠️ 期初库存无匹配数据，已补全 {added} 条旧机占位记录")
                else:
                    print("⚠️ 未找到匹配的数据")
                return True
                
        except Exception as e:
            print(f"✗ 数据提取失败: {e}")
            return False 