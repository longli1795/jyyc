import pandas as pd
from app.models.compatibility import AppDataManager
from data.base_data.mapping_data import get_mapping_dataframe

class DataService:
    """数据服务层"""
    
    def __init__(self, session_id: str = None):
        self.app_data = AppDataManager.get_instance(session_id)
        print(f"🔑 DataService使用会话ID: {session_id}")
    
    def load_source_data(self, file_path):
        """加载源数据文件"""
        try:
            print(f"🔍 正在加载文件: {file_path}")
            
            # 检查文件是否存在
            import os
            if not os.path.exists(file_path):
                raise ValueError(f"文件不存在: {file_path}")
            
            # 获取文件扩展名（不区分大小写）
            file_ext = file_path.lower().split('.')[-1]
            print(f"🔍 文件扩展名: {file_ext}")
            
            if file_ext in ['xlsx', 'xls']:
                print("📊 正在读取Excel文件...")
                # 优先尝试读取"提取结果"sheet，如果不存在则读取第一个sheet
                try:
                    # 先检查是否有"提取结果"sheet
                    excel_file = pd.ExcelFile(file_path)
                    sheet_names = excel_file.sheet_names
                    print(f"📋 Excel文件中的sheet列表: {sheet_names}")
                    
                    if '提取结果' in sheet_names:
                        print("✅ 找到'提取结果'sheet，从该sheet读取数据")
                        data = pd.read_excel(file_path, sheet_name='提取结果')
                    else:
                        print("⚠️ 未找到'提取结果'sheet，从第一个sheet读取数据")
                        data = pd.read_excel(file_path)
                except Exception as e:
                    print(f"⚠️ 读取Excel文件时出错: {e}，尝试读取第一个sheet")
                    data = pd.read_excel(file_path)
            elif file_ext == 'csv':
                print("📄 正在读取CSV文件...")
                # 尝试多种编码
                try:
                    data = pd.read_csv(file_path, encoding='utf-8')
                except UnicodeDecodeError:
                    try:
                        data = pd.read_csv(file_path, encoding='gbk')
                    except UnicodeDecodeError:
                        data = pd.read_csv(file_path, encoding='latin-1')
            else:
                raise ValueError(f"不支持的文件格式: .{file_ext}，支持的格式: .xlsx, .xls, .csv")
            
            # 验证数据
            if data.empty:
                raise ValueError("文件为空或无法读取数据")
            
            # 记录计算历史
            self.app_data.record_calculation(
                calculation_type='load_source_data',
                status='completed',
                result_summary={
                    'rows': len(data),
                    'columns': len(data.columns),
                    'file_path': file_path
                }
            )
            
            self.app_data.set_data('source_data', data)
            print(f"✅ 源数据加载成功: {len(data)} 行, {len(data.columns)} 列")
            print(f"📋 列名: {list(data.columns)[:10]}{'...' if len(data.columns) > 10 else ''}")
            return True
            
        except Exception as e:
            error_msg = f"源数据加载失败: {str(e)}"
            print(f"✗ {error_msg}")
            
            # 记录失败的计算历史
            self.app_data.record_calculation(
                calculation_type='load_source_data',
                status='failed',
                error_message=error_msg,
                input_parameters={'file_path': file_path}
            )
            
            # 如果是pandas相关错误，提供更具体的信息
            err_text = str(e)
            err_lower = err_text.lower()
            if "openpyxl" in err_lower or "xlrd" in err_lower:
                if "openpyxl" in err_lower and (
                    "3.1.5" in err_text or "newer" in err_lower
                ):
                    print(
                        "💡 提示: pandas 需要 openpyxl>=3.1.5，请执行: "
                        'pip install -U "openpyxl>=3.1.5"'
                    )
                else:
                    print("💡 提示: 可能需要安装Excel读取依赖: pip install openpyxl xlrd")
            return False
    
    def load_mapping_data(self):
        """加载映射数据"""
        try:
            # 总是重新导入模块以获取最新的映射数据（避免缓存问题）
            print("🔄 重新加载映射数据模块以获取最新数据...")
            import importlib
            from data.base_data import mapping_data as mapping_module
            importlib.reload(mapping_module)
            mapping_data = mapping_module.get_mapping_dataframe()
            
            if mapping_data is None or mapping_data.empty:
                print("⚠️ 映射数据为空，重新加载后仍无数据")
                raise Exception("映射数据为空")
            
            # 记录计算历史
            self.app_data.record_calculation(
                calculation_type='load_mapping_data',
                status='completed',
                result_summary={
                    'rows': len(mapping_data) if mapping_data is not None else 0
                }
            )
            
            self.app_data.set_data('mapping_data', mapping_data)
            print(f"✅ 映射数据加载成功: {len(mapping_data)} 条记录")
            print(f"📋 映射数据列: {list(mapping_data.columns) if mapping_data is not None else 'None'}")
            return True
        except Exception as e:
            error_msg = f"映射数据加载失败: {e}"
            print(f"✗ {error_msg}")
            
            # 记录失败的计算历史
            self.app_data.record_calculation(
                calculation_type='load_mapping_data',
                status='failed',
                error_message=error_msg
            )
            
            import traceback
            traceback.print_exc()
            return False
    
    def get_data_summary(self):
        """获取数据摘要"""
        summary = {}
        
        source_data = self.app_data.get_data('source_data')
        if source_data is not None:
            summary['source_data'] = {
                'rows': len(source_data),
                'columns': len(source_data.columns),
                'columns_list': source_data.columns.tolist()
            }
        
        extracted_data = self.app_data.get_data('extracted_data')
        if extracted_data is not None:
            summary['extracted_data'] = {
                'rows': len(extracted_data),
                'columns': len(extracted_data.columns)
            }
        
        calculated_data = self.app_data.get_data('calculated_data')
        if calculated_data is not None:
            summary['calculated_data'] = {
                'rows': len(calculated_data),
                'columns': len(calculated_data.columns)
            }
        
        # 添加会话信息
        summary['session_info'] = self.app_data.get_session_info()
        
        return summary
    
    def get_session_id(self):
        """获取当前会话ID"""
        return self.app_data._session_manager.session_id
    
    def get_calculation_history(self, limit: int = 10):
        """获取计算历史"""
        return self.app_data.get_calculation_history(limit)
    
    def clear_all_data(self):
        """清除所有数据"""
        self.app_data.clear_all_data()
        
    def get_session_info(self):
        """获取会话信息"""
        return self.app_data.get_session_info()
    
    def save_data(self):
        """保存数据到持久化存储"""
        try:
            self.app_data.save_persistent_data()
            print("✅ 数据已保存到持久化存储")
            return True
        except Exception as e:
            print(f"✗ 保存数据失败: {e}")
            import traceback
            traceback.print_exc()
            return False 