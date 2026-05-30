"""
可销售量数据管理模块
提供最终可销售量数据的读取、保存和验证功能
"""

import pandas as pd
import os
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import io

# 可销售量数据文件路径
SALEABLE_DATA_FILE = 'data/base_data/saleable_quantity_data.xlsx'
SALEABLE_DATA_BACKUP_FILE = 'data/base_data/saleable_quantity_data_backup.xlsx'

def get_saleable_data_dataframe() -> Optional[pd.DataFrame]:
    """
    获取可销售量数据DataFrame
    
    Returns:
        pd.DataFrame: 可销售量数据，包含以下列：
            - 产品品类: 产品类别
            - 产品名称: 具体产品名称
            - 规格: 产品规格
            - 单位: 计量单位
            - 重量(吨): 最终可销售量重量
            - 备注: 备注信息
        None: 如果文件不存在或读取失败
    """
    try:
        if os.path.exists(SALEABLE_DATA_FILE):
            df = pd.read_excel(SALEABLE_DATA_FILE)
            return df
        else:
            # 创建默认的空数据框架
            return create_default_saleable_dataframe()
    except Exception as e:
        print(f"读取可销售量数据失败: {e}")
        return create_default_saleable_dataframe()

def create_default_saleable_dataframe() -> pd.DataFrame:
    """
    创建默认的可销售量数据框架
    
    Returns:
        pd.DataFrame: 包含示例数据的DataFrame
    """
    default_data = [
        {
            '产品品类': '拆解产物',
            '产品名称': '废钢',
            '规格': '普通废钢',
            '单位': '吨',
            '重量(吨)': 1200.5,
            '备注': '一次拆解产出'
        },
        {
            '产品品类': '拆解产物',
            '产品名称': '有色金属',
            '规格': '铜线',
            '单位': '吨',
            '重量(吨)': 85.3,
            '备注': '一次拆解产出'
        },
        {
            '产品品类': '深加工产物',
            '产品名称': '塑料粒子',
            '规格': 'ABS粒子',
            '单位': '吨',
            '重量(吨)': 45.8,
            '备注': '深加工产出'
        },
        {
            '产品品类': '深加工产物',
            '产品名称': '金属粉末',
            '规格': '铜粉',
            '单位': '吨',
            '重量(吨)': 12.6,
            '备注': '深加工产出'
        }
    ]
    
    return pd.DataFrame(default_data)

def save_saleable_data_dataframe(df: pd.DataFrame) -> Tuple[bool, str]:
    """
    保存可销售量数据到Excel文件
    
    Args:
        df: 要保存的数据框架
        
    Returns:
        Tuple[bool, str]: (是否成功, 消息)
    """
    try:
        # 验证数据格式
        is_valid, error_msg = validate_saleable_dataframe(df)
        if not is_valid:
            return False, f"数据验证失败: {error_msg}"
        
        # 创建备份
        if os.path.exists(SALEABLE_DATA_FILE):
            df_backup = pd.read_excel(SALEABLE_DATA_FILE)
            df_backup.to_excel(SALEABLE_DATA_BACKUP_FILE, index=False)
        
        # 确保目录存在
        os.makedirs(os.path.dirname(SALEABLE_DATA_FILE), exist_ok=True)
        
        # 保存数据
        df.to_excel(SALEABLE_DATA_FILE, index=False)
        
        return True, f"成功保存 {len(df)} 条可销售量数据记录"
    except Exception as e:
        return False, f"保存失败: {str(e)}"

def validate_saleable_dataframe(df: pd.DataFrame) -> Tuple[bool, str]:
    """
    验证可销售量数据格式
    
    Args:
        df: 要验证的数据框架
        
    Returns:
        Tuple[bool, str]: (是否有效, 错误信息)
    """
    required_columns = ['产品品类', '产品名称', '规格', '单位', '重量(吨)', '备注']
    
    # 检查必需列
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        return False, f"缺少必需列: {', '.join(missing_columns)}"
    
    # 检查数据类型
    for index, row in df.iterrows():
        try:
            # 检查重量是否为数值
            weight = row['重量(吨)']
            if pd.isna(weight):
                return False, f"第 {index + 1} 行重量不能为空"
            
            weight_float = float(weight)
            if weight_float < 0:
                return False, f"第 {index + 1} 行重量不能为负数"
                
        except (ValueError, TypeError):
            return False, f"第 {index + 1} 行重量格式错误"
        
        # 检查必填字段
        if pd.isna(row['产品品类']) or str(row['产品品类']).strip() == '':
            return False, f"第 {index + 1} 行产品品类不能为空"
        if pd.isna(row['产品名称']) or str(row['产品名称']).strip() == '':
            return False, f"第 {index + 1} 行产品名称不能为空"
    
    return True, ""

def get_saleable_data_summary() -> Dict:
    """
    获取可销售量数据摘要信息
    
    Returns:
        Dict: 包含统计信息的字典
    """
    try:
        df = get_saleable_data_dataframe()
        if df is None or len(df) == 0:
            return {
                'total_records': 0,
                'total_weight': 0,
                'categories': {},
                'last_updated': None
            }
        
        # 计算总重量
        total_weight = df['重量(吨)'].sum()
        
        # 按品类统计
        category_stats = df.groupby('产品品类').agg({
            '重量(吨)': ['sum', 'count']
        }).round(2)
        
        categories = {}
        for category in category_stats.index:
            categories[category] = {
                'weight': float(category_stats.loc[category, ('重量(吨)', 'sum')]),
                'count': int(category_stats.loc[category, ('重量(吨)', 'count')])
            }
        
        # 获取文件最后修改时间
        last_updated = None
        if os.path.exists(SALEABLE_DATA_FILE):
            timestamp = os.path.getmtime(SALEABLE_DATA_FILE)
            last_updated = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        
        return {
            'total_records': len(df),
            'total_weight': round(float(total_weight), 2),
            'categories': categories,
            'last_updated': last_updated
        }
    except Exception as e:
        print(f"获取可销售量数据摘要失败: {e}")
        return {
            'total_records': 0,
            'total_weight': 0,
            'categories': {},
            'last_updated': None
        }

def export_saleable_data_to_excel() -> Tuple[bool, str, Optional[bytes]]:
    """
    导出可销售量数据到Excel
    
    Returns:
        Tuple[bool, str, Optional[bytes]]: (是否成功, 消息, Excel文件字节流)
    """
    try:
        df = get_saleable_data_dataframe()
        if df is None:
            return False, "没有可销售量数据可导出", None
        
        # 创建Excel文件
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='可销售量数据', index=False)
            
            # 获取工作表并设置列宽
            worksheet = writer.sheets['可销售量数据']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        buffer.seek(0)
        return True, f"成功导出 {len(df)} 条记录", buffer.getvalue()
    except Exception as e:
        return False, f"导出失败: {str(e)}", None

def process_saleable_data_import(file_content: bytes) -> Tuple[bool, str, Optional[pd.DataFrame]]:
    """
    处理可销售量数据导入
    
    Args:
        file_content: Excel文件内容
        
    Returns:
        Tuple[bool, str, Optional[pd.DataFrame]]: (是否成功, 消息, 数据框架)
    """
    try:
        # 读取Excel文件
        df = pd.read_excel(io.BytesIO(file_content))
        
        # 验证数据格式
        is_valid, error_msg = validate_saleable_dataframe(df)
        if not is_valid:
            return False, error_msg, None
        
        return True, f"成功读取 {len(df)} 条记录", df
    except Exception as e:
        return False, f"文件读取失败: {str(e)}", None 