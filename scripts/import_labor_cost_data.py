# -*- coding: utf-8 -*-
"""
旧机拆解人工提成单价数据导入脚本
从Excel文件读取数据并生成 labor_cost_data.py 文件
"""

import pandas as pd
import os
import sys

def import_labor_cost_data():
    """从Excel文件导入数据并生成Python数据文件"""
    try:
        # Excel文件路径
        excel_file = '旧机拆解人工提成单价.xlsx'
        
        if not os.path.exists(excel_file):
            print(f"错误: 找不到文件 {excel_file}")
            return False
        
        # 读取Excel文件
        print(f"正在读取Excel文件: {excel_file}")
        df = pd.read_excel(excel_file)
        
        # 验证必需的列
        required_columns = ['类别', 'R3系统代码', '系统名称', '计件型号', '计件单价']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"错误: Excel文件缺少必需的列: {', '.join(missing_columns)}")
            print(f"当前列: {', '.join(df.columns.tolist())}")
            return False
        
        # 清理数据：删除空行
        df = df.dropna(subset=['R3系统代码', '系统名称'])
        
        # 处理计件单价：转换为数值类型
        df['计件单价'] = pd.to_numeric(df['计件单价'], errors='coerce')
        df = df.dropna(subset=['计件单价'])
        
        # 填充空值
        df['类别'] = df['类别'].fillna('')
        df['计件型号'] = df['计件型号'].fillna('')
        
        print(f"成功读取 {len(df)} 条记录")
        
        # 生成Python文件内容
        file_content = '''# 旧机拆解人工提成单价数据 - 内置数据
# 数据来源：旧机拆解人工提成单价.xlsx
# 计件单价单位：元/台（TAI）

import pandas as pd

# 完整的旧机拆解人工提成单价数据
LABOR_COST_DATA = [
'''
        
        # 添加数据记录
        for index, row in df.iterrows():
            category = str(row['类别']).replace('"', '\\"').replace('\\', '\\\\')
            code = str(row['R3系统代码']).replace('"', '\\"').replace('\\', '\\\\')
            name = str(row['系统名称']).replace('"', '\\"').replace('\\', '\\\\')
            model = str(row['计件型号']).replace('"', '\\"').replace('\\', '\\\\') if pd.notna(row['计件型号']) else ''
            price = float(row['计件单价'])
            
            file_content += f'    {{"类别": "{category}", "R3系统代码": "{code}", "系统名称": "{name}", "计件型号": "{model}", "计件单价": {price}}},\n'
        
        file_content += ''']

def get_labor_cost_dataframe():
    """获取旧机拆解人工提成单价DataFrame"""
    return pd.DataFrame(LABOR_COST_DATA)

def filter_by_category(category):
    """根据类别筛选数据"""
    df = get_labor_cost_dataframe()
    return df[df['类别'] == category]

def get_all_categories():
    """获取所有类别列表"""
    df = get_labor_cost_dataframe()
    return df['类别'].unique().tolist()

def get_category_stats():
    """获取类别统计信息"""
    df = get_labor_cost_dataframe()
    return df['类别'].value_counts().to_dict()

def get_labor_cost_by_code(code):
    """根据R3系统代码获取人工提成单价"""
    df = get_labor_cost_dataframe()
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
        print(f"  总记录数: {len(df)}")
        categories = df['类别'].unique()
        print(f"  类别数量: {len(categories)}")
        print(f"  类别列表: {', '.join(categories)}")
        
        return True
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = import_labor_cost_data()
    sys.exit(0 if success else 1)

