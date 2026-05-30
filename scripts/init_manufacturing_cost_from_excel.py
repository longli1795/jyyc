# -*- coding: utf-8 -*-
"""
从Excel文件初始化制造费用基础数据
读取"制造费用基础数据.xlsx"并生成manufacturing_cost_data.py文件
"""

import pandas as pd
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def init_manufacturing_cost_from_excel():
    """从Excel文件导入数据并生成Python数据文件"""
    try:
        # Excel文件路径
        excel_file = '制造费用基础数据.xlsx'
        
        if not os.path.exists(excel_file):
            print(f"错误: 找不到文件 {excel_file}")
            return False
        
        # 读取Excel文件
        print(f"正在读取Excel文件: {excel_file}")
        df = pd.read_excel(excel_file)
        
        print(f"Excel文件列名: {list(df.columns)}")
        print(f"总行数: {len(df)}")
        
        # 删除完全为空的行
        df = df.dropna(how='all')
        
        # 如果数据为空，返回错误
        if df.empty:
            print("错误: Excel文件中没有有效数据")
            return False
        
        # 将备注列为空（None或NaN）的记录填充为"预计月均费用"
        if '备注' in df.columns:
            df['备注'] = df['备注'].fillna('预计月均费用')
            print(f"已将 {df['备注'].isna().sum()} 条空备注填充为'预计月均费用'")
        
        print(f"成功读取 {len(df)} 条记录")
        
        # 生成Python文件内容
        file_content = '''# 制造费用基础数据 - 内置数据
# 数据来源：制造费用基础数据.xlsx
# 说明：此文件由 scripts/init_manufacturing_cost_from_excel.py 自动生成

import pandas as pd
import os

# 完整的制造费用基础数据
MANUFACTURING_COST_DATA = [
'''
        
        # 添加数据记录
        for index, row in df.iterrows():
            # 跳过完全为空的行
            if row.isna().all():
                continue
            
            record_parts = []
            for col in df.columns:
                value = row[col]
                
                # 处理不同类型的值
                if pd.isna(value):
                    # 空值处理
                    record_parts.append(f'"{col}": None')
                elif isinstance(value, (int, float)):
                    # 数值类型
                    if pd.isna(value):
                        record_parts.append(f'"{col}": None')
                    else:
                        record_parts.append(f'"{col}": {value}')
                else:
                    # 字符串类型，需要转义
                    str_value = str(value).replace('"', '\\"').replace('\\', '\\\\')
                    record_parts.append(f'"{col}": "{str_value}"')
            
            record_str = '{' + ', '.join(record_parts) + '}'
            file_content += f'    {record_str},\n'
        
        file_content += ''']

def get_manufacturing_cost_dataframe():
    """获取制造费用基础数据DataFrame"""
    return pd.DataFrame(MANUFACTURING_COST_DATA)

def filter_by_category(category):
    """根据类别筛选数据（如果有类别字段）"""
    df = get_manufacturing_cost_dataframe()
    if df.empty:
        return df
    if '类别' in df.columns:
        return df[df['类别'] == category]
    return df

def get_all_categories():
    """获取所有类别列表（如果有类别字段）"""
    df = get_manufacturing_cost_dataframe()
    if df.empty:
        return []
    if '类别' in df.columns:
        return df['类别'].unique().tolist()
    return []

def get_category_stats():
    """获取类别统计信息（如果有类别字段）"""
    df = get_manufacturing_cost_dataframe()
    if df.empty:
        return {}
    if '类别' in df.columns:
        return df['类别'].value_counts().to_dict()
    return {}

def get_manufacturing_cost_by_id(record_id):
    """根据记录ID获取制造费用基础数据"""
    df = get_manufacturing_cost_dataframe()
    if df.empty:
        return None
    # 使用"费用名称"作为主键
    if len(df) > 0:
        if '费用名称' in df.columns:
            result = df[df['费用名称'].astype(str) == str(record_id)]
            if len(result) > 0:
                return result.iloc[0].to_dict()
        # 如果找不到费用名称字段，尝试使用第一列
        first_col = df.columns[0]
        if 'ID' in first_col.upper() or '代码' in first_col or '编号' in first_col:
            result = df[df[first_col].astype(str) == str(record_id)]
        else:
            # 使用索引
            try:
                idx = int(record_id)
                if 0 <= idx < len(df):
                    result = df.iloc[[idx]]
                else:
                    return None
            except (ValueError, TypeError):
                return None
        
        if len(result) > 0:
            return result.iloc[0].to_dict()
    return None
'''
        
        # 确保目录存在
        output_dir = 'data/base_data'
        os.makedirs(output_dir, exist_ok=True)
        
        # 写入文件
        output_file = os.path.join(output_dir, 'manufacturing_cost_data.py')
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(file_content)
        
        print(f"✓ 成功生成数据文件: {output_file}")
        print(f"✓ 共导入 {len(df)} 条记录")
        
        # 显示统计信息
        print("\n数据统计:")
        print(f"  总记录数: {len(df)}")
        print(f"  列数: {len(df.columns)}")
        print(f"  列名: {', '.join(df.columns.tolist()[:10])}")
        if len(df.columns) > 10:
            print(f"  ... 共 {len(df.columns)} 列")
        
        # 如果有费用类型字段，显示费用类型统计
        if '费用类型' in df.columns:
            print(f"  费用类型数量: {df['费用类型'].nunique()}")
            print(f"  费用类型列表: {', '.join(df['费用类型'].unique().tolist()[:10])}")
            if len(df['费用类型'].unique()) > 10:
                print(f"  ... 共 {df['费用类型'].nunique()} 个费用类型")
        
        return True
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = init_manufacturing_cost_from_excel()
    sys.exit(0 if success else 1)

