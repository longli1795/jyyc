# -*- coding: utf-8 -*-
"""
基金补贴单价数据模块
用于加载和管理基金补贴单价信息
"""

import pandas as pd
import os
from typing import Optional, Dict

# 补贴单价文件路径
SUBSIDY_FILE_PATH = '基金补贴单价.xlsx'

# 全局补贴数据缓存
_subsidy_data_cache: Optional[pd.DataFrame] = None
_subsidy_mapping_cache: Optional[Dict[str, float]] = None

# 内置补贴单价数据（当Excel文件不存在时使用）
# 新结构：产品类型 + 补贴大类（两级结构）
BUILTIN_SUBSIDY_DATA = [
    {"序号": 1, "产品类型": "电视机", "补贴大类": "电视机", "单价": 15.14, "备注": ""},
    {"序号": 2, "产品类型": "冰箱", "补贴大类": "冰箱", "单价": 39.22, "备注": ""},
    {"序号": 3, "产品类型": "洗衣机", "补贴大类": "洗衣机", "单价": 18.48, "备注": ""},
    {"序号": 4, "产品类型": "空调", "补贴大类": "整机", "单价": 46.68, "备注": ""},
    {"序号": 5, "产品类型": "空调", "补贴大类": "内机", "单价": 23.34, "备注": ""},
    {"序号": 6, "产品类型": "空调", "补贴大类": "外机", "单价": 23.34, "备注": ""},
    {"序号": 7, "产品类型": "电脑", "补贴大类": "笔记本", "单价": 23.36, "备注": ""},
    {"序号": 8, "产品类型": "电脑", "补贴大类": "显示器", "单价": 11.68, "备注": ""},
    {"序号": 9, "产品类型": "电脑", "补贴大类": "主机", "单价": 11.68, "备注": ""}
]

# 物料描述关键字匹配规则
CATEGORY_KEYWORDS = {
    "电视机": ["电视", "CRT", "液晶电视", "等离子"],
    "冰箱": ["冰箱", "冰柜"],
    "洗衣机": ["洗衣机"],
    "空调": ["空调"],
    "电脑": ["电脑", "主机", "笔记本", "显示器"]
}


def load_subsidy_data() -> Optional[pd.DataFrame]:
    """
    加载基金补贴单价数据（支持双模式：优先Excel，回退到内置数据）
    支持新格式（产品类型、补贴大类、单价）和旧格式（类别、补贴单价(元/台)）兼容
    
    Returns:
        pd.DataFrame: 补贴单价数据，包含列：序号、产品类型、补贴大类、单价、备注
        None: 加载失败
    """
    global _subsidy_data_cache
    
    # 如果已有缓存，直接返回
    if _subsidy_data_cache is not None:
        return _subsidy_data_cache.copy()
    
    # 优先尝试从Excel加载
    if os.path.exists(SUBSIDY_FILE_PATH):
        try:
            # 读取Excel文件
            df = pd.read_excel(SUBSIDY_FILE_PATH)
            
            # 检查是新格式还是旧格式
            has_new_format = '产品类型' in df.columns and '补贴大类' in df.columns and '单价' in df.columns
            has_old_format = '类别' in df.columns and '补贴单价(元/台)' in df.columns
            
            if has_new_format:
                # 新格式：产品类型、补贴大类、单价
                print(f"✓ 检测到新格式Excel文件")
                # 确保列名正确
                if '序号' not in df.columns:
                    df.insert(0, '序号', range(1, len(df) + 1))
                if '备注' not in df.columns:
                    df['备注'] = ''
                
                # 确保数据类型正确
                df['产品类型'] = df['产品类型'].astype(str)
                df['补贴大类'] = df['补贴大类'].astype(str)
                df['单价'] = pd.to_numeric(df['单价'], errors='coerce')
                
                # 缓存数据
                _subsidy_data_cache = df.copy()
                print(f"✓ 成功从Excel加载补贴单价数据（新格式）: {len(df)} 条记录")
                return df.copy()
                
            elif has_old_format:
                # 旧格式：类别、补贴单价(元/台) - 自动转换为新格式
                print(f"✓ 检测到旧格式Excel文件，自动转换为新格式")
                df_new = pd.DataFrame()
                df_new['序号'] = range(1, len(df) + 1) if '序号' not in df.columns else df['序号']
                df_new['产品类型'] = df['类别'].astype(str)
                df_new['补贴大类'] = df['类别'].astype(str)  # 旧格式中类别就是补贴大类
                df_new['单价'] = pd.to_numeric(df['补贴单价(元/台)'], errors='coerce')
                df_new['备注'] = df['备注'] if '备注' in df.columns else ''
                
                # 缓存数据
                _subsidy_data_cache = df_new.copy()
                print(f"✓ 成功从Excel加载补贴单价数据（旧格式转换）: {len(df_new)} 条记录")
                return df_new.copy()
            else:
                print(f"警告: 补贴单价文件格式不正确，使用内置数据")
                
        except Exception as e:
            print(f"警告: Excel加载失败，使用内置数据: {e}")
    
    # Excel不存在或加载失败，使用内置数据
    try:
        print(f"📦 使用内置补贴单价数据（共 {len(BUILTIN_SUBSIDY_DATA)} 条记录）")
        df = pd.DataFrame(BUILTIN_SUBSIDY_DATA)
        
        # 确保有所有必需的列
        if '序号' not in df.columns:
            df.insert(0, '序号', range(1, len(df) + 1))
        if '备注' not in df.columns:
            df['备注'] = ''
        
        # 确保数据类型正确
        df['产品类型'] = df['产品类型'].astype(str)
        df['补贴大类'] = df['补贴大类'].astype(str)
        df['单价'] = pd.to_numeric(df['单价'], errors='coerce')
        
        # 缓存数据
        _subsidy_data_cache = df.copy()
        
        print(f"✓ 内置补贴单价数据加载成功")
        return df.copy()
        
    except Exception as e:
        print(f"错误: 加载内置补贴单价数据失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_subsidy_mapping() -> Dict[str, float]:
    """
    获取补贴大类到单价的映射字典（新结构：补贴大类 -> 单价）
    
    Returns:
        Dict[str, float]: {补贴大类: 单价}
    """
    global _subsidy_mapping_cache
    
    # 如果已有缓存，直接返回
    if _subsidy_mapping_cache is not None:
        return _subsidy_mapping_cache.copy()
    
    # 加载补贴数据
    subsidy_df = load_subsidy_data()
    
    if subsidy_df is None or subsidy_df.empty:
        print("警告: 无法创建补贴映射：补贴数据为空")
        return {}
    
    # 创建映射字典（补贴大类 -> 单价）
    mapping = {}
    for _, row in subsidy_df.iterrows():
        # 支持新格式和旧格式
        if '补贴大类' in subsidy_df.columns and '单价' in subsidy_df.columns:
            # 新格式
            subsidy_category = str(row['补贴大类']).strip()
            subsidy_price = row['单价']
        elif '类别' in subsidy_df.columns and '补贴单价(元/台)' in subsidy_df.columns:
            # 旧格式兼容
            subsidy_category = str(row['类别']).strip()
            subsidy_price = row['补贴单价(元/台)']
        else:
            continue
        
        # 跳过无效数据
        if pd.isna(subsidy_price) or subsidy_category == '' or subsidy_category == 'nan':
            continue
        
        mapping[subsidy_category] = float(subsidy_price)
    
    # 缓存映射
    _subsidy_mapping_cache = mapping.copy()
    
    print(f"创建补贴映射: {len(mapping)} 个补贴大类")
    return mapping.copy()


def get_subsidy_by_category(category: str) -> Optional[float]:
    """
    根据类别获取补贴单价
    
    Args:
        category: 类别名称（电视机、冰箱、洗衣机、空调、电脑）
        
    Returns:
        float: 补贴单价(元/台)，如果找不到则返回None
    """
    mapping = get_subsidy_mapping()
    category = str(category).strip()
    return mapping.get(category)


def match_category_by_description(description: str) -> Optional[str]:
    """
    根据物料描述匹配基金补贴大类（两级匹配：产品类型 -> 补贴大类）
    
    匹配规则：
    1. 先匹配产品类型（电视机、冰箱、洗衣机、空调、电脑）
    2. 如果是空调或电脑，进行二级匹配：
       - 空调：
         * 包含"内机"或"室内机" → 返回"内机"
         * 包含"外机"或"室外机" → 返回"外机"
         * 仅包含"空调"（无内机/外机关键字） → 返回"整机"
       - 电脑：
         * 包含"笔记本"或"笔记本电脑" → 返回"笔记本"
         * 包含"显示器"或"显示屏" → 返回"显示器"
         * 包含"主机"或"台式机"或"电脑主机" → 返回"主机"
    3. 其他产品类型直接返回产品类型名称作为补贴大类
    
    Args:
        description: 物料描述字符串
        
    Returns:
        str: 匹配到的补贴大类名称（如"整机"、"内机"、"外机"、"笔记本"、"显示器"、"主机"等），如果没有匹配则返回None
    """
    if not description:
        return None
    
    description = str(description).strip()
    description_lower = description.lower()  # 用于不区分大小写的匹配
    
    # 第一步：匹配产品类型
    product_type = None
    matches = []
    
    # 遍历每个产品类型的关键字进行匹配
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            # 查找关键字在描述中的位置（不区分大小写）
            position = description_lower.find(keyword.lower())
            if position != -1:  # 找到了
                matches.append((position, category, keyword))
    
    # 如果没有匹配到产品类型，返回None
    if not matches:
        return None
    
    # 如果有多个匹配，按位置排序，选择位置最靠前的产品类型
    matches.sort(key=lambda x: x[0])  # 按位置排序
    product_type = matches[0][1]  # 获取产品类型
    
    # 第二步：根据产品类型进行二级匹配（仅对空调和电脑）
    if product_type == "空调":
        # 空调的二级匹配
        if "内机" in description or "室内机" in description:
            return "内机"
        elif "外机" in description or "室外机" in description:
            return "外机"
        else:
            # 默认返回整机
            return "整机"
    
    elif product_type == "电脑":
        # 电脑的二级匹配
        if "笔记本" in description or "笔记本电脑" in description:
            return "笔记本"
        elif "显示器" in description or "显示屏" in description:
            return "显示器"
        elif "主机" in description or "台式机" in description or "电脑主机" in description:
            return "主机"
        else:
            # 默认返回笔记本
            return "笔记本"
    
    else:
        # 其他产品类型（电视机、冰箱、洗衣机）直接返回产品类型名称作为补贴大类
        return product_type


def refresh_subsidy_data():
    """
    刷新补贴数据缓存（重新从文件加载）
    """
    global _subsidy_data_cache, _subsidy_mapping_cache
    _subsidy_data_cache = None
    _subsidy_mapping_cache = None
    
    # 重新加载模块以获取最新的内置数据
    import importlib
    import sys
    if 'data.base_data.subsidy_data' in sys.modules:
        current_module = sys.modules['data.base_data.subsidy_data']
        importlib.reload(current_module)
    
    # 重新加载
    load_subsidy_data()
    get_subsidy_mapping()
    
    print("🔄 补贴数据缓存已刷新")


def get_subsidy_dataframe() -> pd.DataFrame:
    """
    获取内置补贴数据的DataFrame
    
    Returns:
        pd.DataFrame: 内置补贴数据（新格式）
    """
    df = pd.DataFrame(BUILTIN_SUBSIDY_DATA)
    
    # 确保有所有必需的列
    if '序号' not in df.columns:
        df.insert(0, '序号', range(1, len(df) + 1))
    if '备注' not in df.columns:
        df['备注'] = ''
    
    # 确保数据类型正确
    df['产品类型'] = df['产品类型'].astype(str)
    df['补贴大类'] = df['补贴大类'].astype(str)
    df['单价'] = pd.to_numeric(df['单价'], errors='coerce')
    
    return df


def export_builtin_data_to_excel(output_path: str = None) -> bool:
    """
    将内置补贴数据导出为Excel文件
    
    Args:
        output_path: 输出文件路径，默认为 SUBSIDY_FILE_PATH
        
    Returns:
        bool: 是否成功导出
    """
    try:
        if output_path is None:
            output_path = SUBSIDY_FILE_PATH
        
        df = get_subsidy_dataframe()
        df.to_excel(output_path, index=False)
        
        print(f"✓ 成功导出内置补贴数据到Excel: {output_path} ({len(df)} 条记录)")
        return True
        
    except Exception as e:
        print(f"✗ 导出内置补贴数据失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_data_source() -> str:
    """
    获取当前数据源类型
    
    Returns:
        str: 'excel' 或 'builtin'
    """
    if os.path.exists(SUBSIDY_FILE_PATH):
        try:
            df = pd.read_excel(SUBSIDY_FILE_PATH)
            # 检查新格式或旧格式
            has_new_format = '产品类型' in df.columns and '补贴大类' in df.columns and '单价' in df.columns
            has_old_format = '类别' in df.columns and '补贴单价(元/台)' in df.columns
            if has_new_format or has_old_format:
                return 'excel'
        except:
            pass
    return 'builtin'


def get_subsidy_statistics() -> Dict:
    """
    获取补贴数据统计信息
    
    Returns:
        Dict: 统计信息
    """
    subsidy_df = load_subsidy_data()
    
    if subsidy_df is None or subsidy_df.empty:
        return {
            'total_count': 0,
            'valid_count': 0,
            'min_price': 0,
            'max_price': 0,
            'avg_price': 0
        }
    
    # 支持新格式和旧格式
    if '单价' in subsidy_df.columns:
        price_col = '单价'
    elif '补贴单价(元/台)' in subsidy_df.columns:
        price_col = '补贴单价(元/台)'
    else:
        return {
            'total_count': len(subsidy_df),
            'valid_count': 0,
            'min_price': 0,
            'max_price': 0,
            'avg_price': 0
        }
    
    valid_prices = subsidy_df[subsidy_df[price_col].notna()][price_col]
    
    return {
        'total_count': len(subsidy_df),
        'valid_count': len(valid_prices),
        'min_price': float(valid_prices.min()) if len(valid_prices) > 0 else 0,
        'max_price': float(valid_prices.max()) if len(valid_prices) > 0 else 0,
        'avg_price': float(valid_prices.mean()) if len(valid_prices) > 0 else 0
    }


# 模块初始化时加载数据
def _init_module():
    """模块初始化"""
    try:
        load_subsidy_data()
        get_subsidy_mapping()
    except Exception as e:
        print(f"警告: 补贴数据模块初始化警告: {e}")


# 自动初始化
_init_module()

