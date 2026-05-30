# -*- coding: utf-8 -*-
"""
销售价格数据模块
用于加载和管理销售价格信息
"""

import pandas as pd
import os
from typing import Optional, Dict

# 价格文件路径
PRICE_FILE_PATH = '销售价格.xlsx'

# 全局价格数据缓存
_price_data_cache: Optional[pd.DataFrame] = None
_price_mapping_cache: Optional[Dict[str, float]] = None

# 内置价格数据（当Excel文件不存在时使用）
BUILTIN_PRICE_DATA = [
    {"序号": 1, "销售产物名称": "铜管", "拆解产物编码": "811052753", "销售单价(元/KG)": 50.0, "备注": ""},
    {"序号": 2, "销售产物名称": "铝件", "拆解产物编码": "811053075", "销售单价(元/KG)": 15.0, "备注": ""},
    {"序号": 3, "销售产物名称": "破碎塑料", "拆解产物编码": "811053014", "销售单价(元/KG)": 3.0, "备注": ""},
    {"序号": 4, "销售产物名称": "铁件", "拆解产物编码": "811052939", "销售单价(元/KG)": 2.5, "备注": ""},
    {"序号": 5, "销售产物名称": "电路板", "拆解产物编码": "811052978", "销售单价(元/KG)": 25.0, "备注": ""},
]


def load_price_data() -> Optional[pd.DataFrame]:
    """
    加载销售价格数据（支持双模式：优先Excel，回退到内置数据）
    
    Returns:
        pd.DataFrame: 价格数据，包含列：序号、销售产物名称、拆解产物编码、销售单价(元/KG)、销售单价-不含税(元/KG)
        None: 加载失败
    """
    global _price_data_cache
    
    # 如果已有缓存，直接返回
    if _price_data_cache is not None:
        return _price_data_cache.copy()
    
    # 优先尝试从Excel加载
    if os.path.exists(PRICE_FILE_PATH):
        try:
            # 读取Excel文件
            df = pd.read_excel(PRICE_FILE_PATH)
            
            # 验证必需的列是否存在
            required_columns = ['拆解产物编码', '销售单价(元/KG)']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                print(f"警告: 价格文件缺少必需的列: {missing_columns}，使用内置数据")
            else:
                # 确保编码列为字符串类型
                df['拆解产物编码'] = df['拆解产物编码'].astype(str)
                
                # 确保价格列为数值类型（含税价）
                df['销售单价(元/KG)'] = pd.to_numeric(df['销售单价(元/KG)'], errors='coerce')
                
                # 计算不含税价格：含税价 ÷ 1.13（增值税率13%）
                df['销售单价-不含税(元/KG)'] = df['销售单价(元/KG)'] / 1.13
                
                # 缓存数据
                _price_data_cache = df.copy()
                
                print(f"✓ 成功从Excel加载价格数据: {len(df)} 条记录")
                return df.copy()
                
        except Exception as e:
            print(f"警告: Excel加载失败，使用内置数据: {e}")
    
    # Excel不存在或加载失败，使用内置数据
    try:
        print(f"📦 使用内置价格数据（共 {len(BUILTIN_PRICE_DATA)} 条记录）")
        df = pd.DataFrame(BUILTIN_PRICE_DATA)
        
        # 确保有所有必需的列
        if '序号' not in df.columns:
            df.insert(0, '序号', range(1, len(df) + 1))
        if '销售产物名称' not in df.columns:
            df['销售产物名称'] = ''
        if '备注' not in df.columns:
            df['备注'] = ''
        
        # 确保编码列为字符串类型
        df['拆解产物编码'] = df['拆解产物编码'].astype(str)
        
        # 确保价格列为数值类型（含税价）
        df['销售单价(元/KG)'] = pd.to_numeric(df['销售单价(元/KG)'], errors='coerce')
        
        # 计算不含税价格：含税价 ÷ 1.13（增值税率13%）
        df['销售单价-不含税(元/KG)'] = df['销售单价(元/KG)'] / 1.13
        
        # 缓存数据
        _price_data_cache = df.copy()
        
        print(f"✓ 内置价格数据加载成功")
        return df.copy()
        
    except Exception as e:
        print(f"错误: 加载内置价格数据失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_price_mapping() -> Dict[str, float]:
    """
    获取产物编码到不含税价格的映射字典
    
    Returns:
        Dict[str, float]: {产物编码: 不含税单价(元/KG)}
    """
    global _price_mapping_cache
    
    # 如果已有缓存，直接返回
    if _price_mapping_cache is not None:
        return _price_mapping_cache.copy()
    
    # 加载价格数据
    price_df = load_price_data()
    
    if price_df is None or price_df.empty:
        print("警告: 无法创建价格映射：价格数据为空")
        return {}
    
    # 创建映射字典（产物编码 -> 不含税单价）
    mapping = {}
    for _, row in price_df.iterrows():
        code = str(row['拆解产物编码']).strip()
        price_no_tax = row['销售单价-不含税(元/KG)']
        
        # 跳过无效数据
        if pd.isna(price_no_tax) or code == '' or code == 'nan':
            continue
        
        mapping[code] = float(price_no_tax)
    
    # 缓存映射
    _price_mapping_cache = mapping.copy()
    
    print(f"创建价格映射: {len(mapping)} 个产物编码（使用不含税价）")
    return mapping.copy()


def get_price_by_code(product_code: str) -> Optional[float]:
    """
    根据产物编码获取不含税单价
    
    Args:
        product_code: 产物编码
        
    Returns:
        float: 不含税单价(元/KG)，如果找不到则返回None
    """
    mapping = get_price_mapping()
    code = str(product_code).strip()
    return mapping.get(code)


def refresh_price_data():
    """
    刷新价格数据缓存（重新从文件加载）
    """
    global _price_data_cache, _price_mapping_cache
    _price_data_cache = None
    _price_mapping_cache = None
    
    # 重新加载模块以获取最新的内置数据
    import importlib
    import sys
    if 'data.base_data.price_data' in sys.modules:
        current_module = sys.modules['data.base_data.price_data']
        importlib.reload(current_module)
    
    # 重新加载
    load_price_data()
    get_price_mapping()
    
    print("🔄 价格数据缓存已刷新")


def get_price_dataframe() -> pd.DataFrame:
    """
    获取内置价格数据的DataFrame
    
    Returns:
        pd.DataFrame: 内置价格数据
    """
    df = pd.DataFrame(BUILTIN_PRICE_DATA)
    
    # 确保有所有必需的列
    if '序号' not in df.columns:
        df.insert(0, '序号', range(1, len(df) + 1))
    if '销售产物名称' not in df.columns:
        df['销售产物名称'] = ''
    if '备注' not in df.columns:
        df['备注'] = ''
    
    # 确保编码列为字符串类型
    df['拆解产物编码'] = df['拆解产物编码'].astype(str)
    
    # 确保价格列为数值类型
    df['销售单价(元/KG)'] = pd.to_numeric(df['销售单价(元/KG)'], errors='coerce')
    
    # 计算不含税价格
    df['销售单价-不含税(元/KG)'] = df['销售单价(元/KG)'] / 1.13
    
    return df


def export_builtin_data_to_excel(output_path: str = None) -> bool:
    """
    将内置价格数据导出为Excel文件
    
    Args:
        output_path: 输出文件路径，默认为 PRICE_FILE_PATH
        
    Returns:
        bool: 是否成功导出
    """
    try:
        if output_path is None:
            output_path = PRICE_FILE_PATH
        
        df = get_price_dataframe()
        df.to_excel(output_path, index=False)
        
        print(f"✓ 成功导出内置数据到Excel: {output_path} ({len(df)} 条记录)")
        return True
        
    except Exception as e:
        print(f"✗ 导出内置数据失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_data_source() -> str:
    """
    获取当前数据源类型
    
    Returns:
        str: 'excel' 或 'builtin'
    """
    if os.path.exists(PRICE_FILE_PATH):
        try:
            df = pd.read_excel(PRICE_FILE_PATH)
            required_columns = ['拆解产物编码', '销售单价(元/KG)']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if not missing_columns:
                return 'excel'
        except:
            pass
    return 'builtin'


def get_price_statistics() -> Dict:
    """
    获取价格数据统计信息（含税价和不含税价）
    
    Returns:
        Dict: 统计信息
    """
    price_df = load_price_data()
    
    if price_df is None or price_df.empty:
        return {
            'total_count': 0,
            'valid_count': 0,
            'min_price': 0,
            'max_price': 0,
            'avg_price': 0,
            'min_price_no_tax': 0,
            'max_price_no_tax': 0,
            'avg_price_no_tax': 0
        }
    
    valid_prices = price_df[price_df['销售单价(元/KG)'].notna()]['销售单价(元/KG)']
    valid_prices_no_tax = price_df[price_df['销售单价-不含税(元/KG)'].notna()]['销售单价-不含税(元/KG)']
    
    return {
        'total_count': len(price_df),
        'valid_count': len(valid_prices),
        # 含税价统计
        'min_price': float(valid_prices.min()) if len(valid_prices) > 0 else 0,
        'max_price': float(valid_prices.max()) if len(valid_prices) > 0 else 0,
        'avg_price': float(valid_prices.mean()) if len(valid_prices) > 0 else 0,
        # 不含税价统计
        'min_price_no_tax': float(valid_prices_no_tax.min()) if len(valid_prices_no_tax) > 0 else 0,
        'max_price_no_tax': float(valid_prices_no_tax.max()) if len(valid_prices_no_tax) > 0 else 0,
        'avg_price_no_tax': float(valid_prices_no_tax.mean()) if len(valid_prices_no_tax) > 0 else 0
    }


# 模块初始化时加载数据
def _init_module():
    """模块初始化"""
    try:
        load_price_data()
        get_price_mapping()
    except Exception as e:
        print(f"警告: 价格数据模块初始化警告: {e}")


# 自动初始化
_init_module()

