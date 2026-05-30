# -*- coding: utf-8 -*-
"""
从Excel文件初始化计件人工标准数据
读取"计件人工标准.xlsx"并生成labor_cost_data.py文件
"""

import pandas as pd
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def init_labor_cost_from_excel():
    """从Excel文件导入数据并生成Python数据文件"""
    try:
        # Excel文件路径
        excel_file = '计件人工标准.xlsx'
        
        if not os.path.exists(excel_file):
            print(f"错误: 找不到文件 {excel_file}")
            return False
        
        # 读取Excel文件
        print(f"正在读取Excel文件: {excel_file}")
        df = pd.read_excel(excel_file)
        
        print(f"Excel文件列名: {list(df.columns)}")
        print(f"总行数: {len(df)}")
        
        # 定义必需的列
        required_columns = ['类别', 'R3系统代码', '系统名称']
        price_columns = [
            '生产计件单价', '品管提成单价', '物流主管提成单价', '物流卸货提成单价',
            '班组长提成单价', '生产主管提成单价', '维修班长提成单价', '维修员提成单价',
            '冰箱维修主管提成单价', '叉车/司磅/库管等提成单价'
        ]
        
        # 检查必需列
        missing_columns = []
        for col in required_columns:
            if col not in df.columns:
                missing_columns.append(col)
        
        if missing_columns:
            print(f"错误: Excel文件缺少必需的列: {', '.join(missing_columns)}")
            print(f"当前列: {', '.join(df.columns.tolist())}")
            return False
        
        # 清理数据：删除关键字段为空的行
        df = df.dropna(subset=['R3系统代码', '系统名称'])
        
        # 处理单价列：转换为数值类型，缺失值填充为0
        for col in price_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0
        
        # 填充空值
        df['类别'] = df['类别'].fillna('')
        
        print(f"成功读取 {len(df)} 条记录")
        
        # 生成Python文件内容
        file_content = '''# 计件人工标准数据 - 内置数据
# 数据来源：计件人工标准.xlsx
# 单价单位：元/台（TAI）

import pandas as pd
import os

# 完整的计件人工标准数据
LABOR_COST_DATA = [
'''
        
        # 添加数据记录
        for index, row in df.iterrows():
            category = str(row['类别']).replace('"', '\\"').replace('\\', '\\\\')
            code = str(row['R3系统代码']).replace('"', '\\"').replace('\\', '\\\\')
            name = str(row['系统名称']).replace('"', '\\"').replace('\\', '\\\\')
            
            # 获取所有单价字段
            prices = {}
            for price_col in price_columns:
                if price_col in df.columns:
                    price_val = float(row[price_col]) if pd.notna(row[price_col]) else 0.0
                    prices[price_col] = price_val
                else:
                    prices[price_col] = 0.0
            
            # 构建记录字符串
            record_parts = [
                f'"类别": "{category}"',
                f'"R3系统代码": "{code}"',
                f'"系统名称": "{name}"'
            ]
            
            for price_col, price_val in prices.items():
                record_parts.append(f'"{price_col}": {price_val}')
            
            record_str = '{' + ', '.join(record_parts) + '}'
            file_content += f'    {record_str},\n'
        
        file_content += ''']

def get_labor_cost_dataframe():
    """获取计件人工标准DataFrame"""
    return pd.DataFrame(LABOR_COST_DATA)

def filter_by_category(category):
    """根据类别筛选数据"""
    df = get_labor_cost_dataframe()
    if df.empty:
        return df
    return df[df['类别'] == category]

def get_all_categories():
    """获取所有类别列表"""
    df = get_labor_cost_dataframe()
    if df.empty:
        return []
    return df['类别'].unique().tolist()

def get_category_stats():
    """获取类别统计信息"""
    df = get_labor_cost_dataframe()
    if df.empty:
        return {}
    return df['类别'].value_counts().to_dict()

def get_labor_cost_by_code(code):
    """根据R3系统代码获取计件人工标准"""
    df = get_labor_cost_dataframe()
    if df.empty:
        return None
    result = df[df['R3系统代码'].astype(str) == str(code)]
    if len(result) > 0:
        return result.iloc[0].to_dict()
    return None
'''
        
        # 确保目录存在
        output_dir = 'data/base_data'
        os.makedirs(output_dir, exist_ok=True)
        
        # 写入文件
        output_file = os.path.join(output_dir, 'labor_cost_data.py')
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(file_content)
        
        print(f"✓ 成功生成数据文件: {output_file}")
        print(f"✓ 共导入 {len(df)} 条记录")
        
        # 显示统计信息
        print("\n数据统计:")
        print(f"  类别数量: {df['类别'].nunique()}")
        print(f"  类别列表: {', '.join(df['类别'].unique().tolist()[:10])}")
        if len(df['类别'].unique()) > 10:
            print(f"  ... 共 {df['类别'].nunique()} 个类别")
        
        return True
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = init_labor_cost_from_excel()
    sys.exit(0 if success else 1)

