import pandas as pd
import numpy as np
import json
from datetime import datetime, date

def safe_json_convert(data):
    """
    安全地将pandas DataFrame或其他数据转换为JSON格式
    处理NaN、日期等特殊值
    """
    if isinstance(data, pd.DataFrame):
        # 先清理DataFrame中的问题值
        data_clean = data.copy()
        # 替换NaN、无穷大等问题值
        data_clean = data_clean.replace([np.nan, np.inf, -np.inf], None)
        # 将DataFrame转换为字典列表
        data_dict = data_clean.to_dict('records')
        return json.loads(json.dumps(data_dict, default=json_serializer))
    elif isinstance(data, (list, dict)):
        return json.loads(json.dumps(data, default=json_serializer))
    else:
        return data

def json_serializer(obj):
    """JSON序列化器，处理特殊数据类型"""
    # 首先检查NaN，因为NaN也是np.floating类型
    if pd.isna(obj) or obj is None:
        return None
    elif isinstance(obj, (np.integer, np.floating)):
        value = float(obj)
        # 再次检查转换后的值是否为NaN或无穷大
        if np.isnan(value) or np.isinf(value):
            return None
        return value
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    else:
        return str(obj)

def clean_dataframe_for_json(df):
    """
    清理DataFrame以便JSON序列化
    """
    df = df.copy()
    
    # 处理NaN值
    df = df.fillna('')
    
    # 处理无穷大值
    df = df.replace([np.inf, -np.inf], '')
    
    # 确保所有数值类型都是Python原生类型
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str)
        elif pd.api.types.is_numeric_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    return df 