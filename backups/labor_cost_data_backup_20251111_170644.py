# 旧机拆解人工提成单价数据 - 内置数据
# 数据来源：旧机拆解人工提成单价.xlsx
# 计件单价单位：元/台（TAI）

import pandas as pd

# 完整的旧机拆解人工提成单价数据
LABOR_COST_DATA = [
    # 数据将通过导入脚本自动生成
    # 格式: {"类别": "类别名", "R3系统代码": "代码", "系统名称": "名称", "计件型号": "型号", "计件单价": 单价}
]

def get_labor_cost_dataframe():
    """获取旧机拆解人工提成单价DataFrame"""
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
    """根据R3系统代码获取人工提成单价"""
    df = get_labor_cost_dataframe()
    if df.empty:
        return None
    result = df[df['R3系统代码'].astype(str) == str(code)]
    if len(result) > 0:
        return result.iloc[0].to_dict()
    return None

