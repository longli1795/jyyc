# -*- coding: utf-8 -*-
"""
更新制造费用基础数据Excel文件中的空备注
将所有空备注填充为"预计月均费用"
"""

import pandas as pd
import os

def update_manufacturing_cost_remarks():
    """更新Excel文件中的空备注"""
    try:
        excel_file = '制造费用基础数据.xlsx'
        
        if not os.path.exists(excel_file):
            print(f"错误: 找不到文件 {excel_file}")
            return False
        
        # 读取Excel文件
        print(f"正在读取Excel文件: {excel_file}")
        df = pd.read_excel(excel_file)
        
        # 统计空备注数量
        empty_count = df['备注'].isna().sum()
        print(f"发现 {empty_count} 条空备注记录")
        
        # 填充空备注为"预计月均费用"
        df['备注'] = df['备注'].fillna('预计月均费用')
        
        # 保存回Excel文件
        df.to_excel(excel_file, index=False)
        print(f"✓ 已更新Excel文件，{empty_count} 条空备注已填充为'预计月均费用'")
        
        return True
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = update_manufacturing_cost_remarks()
    if success:
        print("\n请运行以下命令重新生成数据文件:")
        print("python scripts/init_manufacturing_cost_from_excel.py")









