"""
向后兼容适配器
让现有代码能够无缝使用新的会话隔离数据管理器
"""

import uuid
from typing import Any, Dict, Optional
from contextlib import contextmanager
from app.models.session_data_manager import SessionDataManagerFactory
from app.models.app_data import AppDataManager as OriginalAppDataManager


class AppDataManagerAdapter:
    """
    AppDataManager适配器
    提供与原始AppDataManager相同的接口，但使用会话隔离的数据管理器
    """
    
    def __init__(self, session_id: str = None):
        self._session_manager = SessionDataManagerFactory.get_manager(session_id)
        self._fallback_session_id = None  # 添加备用会话ID
        self._data_cleared = False  # 添加数据清除标志
    
    @classmethod
    def get_instance(cls, session_id: str = None):
        """获取适配器实例（保持原有接口）"""
        return cls(session_id)
    
    def _find_data_session(self) -> Optional[str]:
        """查找包含数据的会话"""
        if self._fallback_session_id:
            return self._fallback_session_id
            
        # 🔐 重要修改：只有在明确启用备用会话机制时才查找
        # 检查是否在会话中明确启用了备用会话功能
        try:
            from flask import session
            enable_fallback = session.get('enable_fallback_sessions', False)
            if not enable_fallback:
                # 移除频繁的调试日志
                return None
        except:
            # 移除频繁的调试日志
            return None
            
        try:
            import sqlite3
            import os
            
            db_path = 'data_storage/business_forecast.db'
            if not os.path.exists(db_path):
                return None
                
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 查找包含saleable_data的会话（排除当前会话）
            cursor.execute("SELECT session_id FROM session_datasets WHERE data_key = 'saleable_data' AND session_id != ? LIMIT 1;", 
                          (self._session_manager.session_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                self._fallback_session_id = result[0]
                # 只在首次找到时记录日志
                if not hasattr(self, '_fallback_logged'):
                    self._fallback_logged = True
                    print(f"🔍 找到备用数据会话: {self._fallback_session_id}")
                return self._fallback_session_id
                
        except Exception as e:
            print(f"查找数据会话失败: {e}")
        
        return None
    
    def _is_data_cleared(self) -> bool:
        """检查数据是否已被清除（结果在实例生命周期内缓存）"""
        if self._data_cleared:
            return True
        if not hasattr(self, '_session_clear_checked'):
            self._session_clear_checked = bool(
                self._session_manager.get_data('__data_cleared__')
            )
            if self._session_clear_checked:
                self._data_cleared = True
        return self._data_cleared

    def get_data(self, key: str = None) -> Any:
        """获取数据"""
        data = self._session_manager.get_data(key)
        
        if self._is_data_cleared():
            return data
        
        # 若当前未取到数据，先从 DB 强制读一次（解决同步后缓存未更新导致接口仍返回空的问题）
        if data is None and key:
            data = self._session_manager.get_data_from_db(key)
        
        # 如果当前会话没有数据，尝试从备用会话获取
        if data is None and key:
            fallback_session_id = self._find_data_session()
            if fallback_session_id and fallback_session_id != self._session_manager.session_id:
                try:
                    fallback_manager = SessionDataManagerFactory.get_manager(fallback_session_id)
                    if not fallback_manager.get_data('__data_cleared__'):
                        data = fallback_manager.get_data(key)
                        if data is not None:
                            pass
                except Exception as e:
                    print(f"从备用会话获取数据失败: {e}")
        
        return data
    
    def get_data_from_db(self, key: str = None) -> Any:
        """仅从数据库读取数据，不经过缓存（用于同步后判断是否有数据等场景）。"""
        if not key:
            return None
        return self._session_manager.get_data_from_db(key)
    
    def set_data(self, key: str, value: Any):
        """设置数据"""
        self._session_manager.set_data(key, value)

    @contextmanager
    def batch_update(self):
        """批量写入上下文，减少频繁数据库提交。"""
        with self._session_manager.batch_update():
            yield self
    
    def update_status(self, status: str, progress: Optional[int] = None):
        """更新状态"""
        self._session_manager.update_status(status, progress)
    
    def safe_json_convert(self, df):
        """安全的DataFrame转JSON转换"""
        return self._session_manager.safe_json_convert(df)
    
    def save_persistent_data(self):
        """保存持久化数据（新架构中自动保存，此方法保持兼容性）"""
        # 在新架构中，数据自动保存到数据库和Redis，此方法仅记录日志
        try:
            from flask import current_app
            current_app.logger.info(f"数据已自动保存到数据库 - 会话ID: {self._session_manager.session_id}")
        except:
            pass
    
    def load_persistent_data(self):
        """加载持久化数据（新架构中自动加载，此方法保持兼容性）"""
        # 在新架构中，数据从数据库和Redis自动加载，此方法仅记录日志
        try:
            from flask import current_app
            current_app.logger.info(f"数据已自动加载 - 会话ID: {self._session_manager.session_id}")
        except:
            pass
    
    def clear_all_data(self):
        """清除所有数据"""
        self._session_manager.clear_all_data()
        self._fallback_session_id = None
        self._data_cleared = True
        self._session_clear_checked = True
        print("🧹 数据已清除，备用会话引用已重置")
    
    def get_data_info(self) -> Dict[str, Any]:
        """获取数据信息"""
        all_data = self._session_manager.get_data()
        data_keys = list(all_data.keys()) if all_data else []
        non_empty_keys = [k for k, v in all_data.items() if v is not None] if all_data else []
        
        return {
            'data_keys': data_keys,
            'non_empty_keys': non_empty_keys,
            'session_id': self._session_manager.session_id,
            'last_updated': self._session_manager.get_session_info().get('last_accessed')
        }
    
    # 新增方法：被减扣数据管理
    def mark_deducted_data_modified(self):
        """标记被减扣数据已修改"""
        from datetime import datetime
        self._session_manager.set_data('deducted_data_modified', True)
        self._session_manager.set_data('modification_timestamp', datetime.now())
    
    def is_deducted_data_modified(self) -> bool:
        """检查被减扣数据是否已修改"""
        return self._session_manager.get_data('deducted_data_modified') or False
    
    def get_modification_timestamp(self):
        """获取修改时间戳"""
        return self._session_manager.get_data('modification_timestamp')
    
    def get_session_info(self) -> Dict[str, Any]:
        """获取会话信息"""
        return self._session_manager.get_session_info()
    
    def backup_original_deducted_data(self):
        """备份原始被减扣数据并初始化手工数据"""
        try:
            import copy
            import pandas as pd
            
            # 🔧 架构重构：从 deducted_data_manual 备份，不再使用 deducted_data
            manual_data = self._session_manager.get_data('deducted_data_manual')
            original_data = self._session_manager.get_data('original_deducted_data')
            
            # 检查是否有被减扣数据(手工)
            if manual_data is None or (isinstance(manual_data, pd.DataFrame) and manual_data.empty):
                print("⚠️ 没有被减扣数据(手工)，无法备份")
                return False
            
            # 检查是否需要创建原始备份
            if original_data is None or (isinstance(original_data, pd.DataFrame) and original_data.empty):
                # 深拷贝备份手工数据作为原始备份
                self._session_manager.set_data('original_deducted_data', copy.deepcopy(manual_data))
                print(f"✅ 已创建原始被减扣数据备份: {len(manual_data)} 条记录")
            
            # 确保修改标志正确
            if not self._session_manager.get_data('deducted_data_modified'):
                self._session_manager.set_data('deducted_data_modified', False)
                self._session_manager.set_data('deducted_modifications', {})
            
            return True
            
        except Exception as e:
            print(f"⚠️ 备份原始被减扣数据失败: {e}")
            return False
    
    def restore_original_deducted_data(self):
        """恢复原始被减扣数据"""
        original_data = self._session_manager.get_data('original_deducted_data')
        if original_data is not None:
            self._session_manager.set_data('deducted_data_manual', original_data.copy())
            self._session_manager.set_data('deducted_data_modified', False)
            self._session_manager.set_data('modification_timestamp', None)
    
    def reset_deducted_data_to_original(self):
        """重置被减扣数据(手工)到原始状态"""
        try:
            original_data = self._session_manager.get_data('original_deducted_data')
            if original_data is not None:
                # 重置手工数据为原始数据
                self._session_manager.set_data('deducted_data_manual', original_data.copy())
                self._session_manager.set_data('deducted_data_modified', False)
                self._session_manager.set_data('deducted_modifications', {})
                self._session_manager.set_data('modification_timestamp', None)
                print("✅ 被减扣数据(手工)已重置到原始状态")
                return True
            else:
                print("⚠️ 没有原始被减扣数据备份，无法重置")
                return False
        except Exception as e:
            print(f"⚠️ 重置被减扣数据失败: {e}")
            return False
    
    # 新增方法：计算历史记录
    def record_calculation(self, calculation_type: str, **kwargs):
        """记录计算历史"""
        return self._session_manager.record_calculation(calculation_type, **kwargs)
    
    def get_calculation_history(self, limit: int = 10):
        """获取计算历史"""
        return self._session_manager.get_calculation_history(limit)
    
    def get_data_for_deep_processing(self):
        """
        获取用于深加工计算的数据源
        🔧 架构重构：只使用 deducted_data_manual，不再使用 deducted_data (只读)
        重要逻辑：
        1. 优先使用 deducted_data_manual（唯一工作数据源）
        2. 如果 deducted_data_manual 为空且未修改，尝试从 original_deducted_data 恢复
        """
        # 优先使用手工数据（唯一工作数据源）
        manual_data = self._session_manager.get_data('deducted_data_manual')
        if manual_data is not None and not (hasattr(manual_data, 'empty') and manual_data.empty):
            modified = self._session_manager.get_data('deducted_data_modified')
            if modified:
                print(f"🔄 使用已编辑的被减扣数据(手工)进行深加工计算 - {len(manual_data)} 条记录")
                print(f"   ✅ 修改后的数据将参与计算")
            else:
                print(f"🔄 使用被减扣数据(手工)进行深加工计算 - {len(manual_data)} 条记录")
                print(f"   ✅ 使用原始数据，未修改")
            self._session_manager.set_data('deep_processing_data_source', 'manual')
            return manual_data
        
        # 如果手工数据为空且未修改，尝试从原始备份恢复
        modified = self._session_manager.get_data('deducted_data_modified')
        if not modified:
            original_data = self._session_manager.get_data('original_deducted_data')
            if original_data is not None and not (hasattr(original_data, 'empty') and original_data.empty):
                # 从原始备份恢复
                import copy
                self._session_manager.set_data('deducted_data_manual', copy.deepcopy(original_data))
                print(f"🔄 从原始备份恢复被减扣数据(手工) - {len(original_data)} 条记录")
                self._session_manager.set_data('deep_processing_data_source', 'manual')
                return original_data
        
        print("⚠️ 没有被减扣数据，跳过深加工计算")
        self._session_manager.set_data('deep_processing_data_source', 'none')
        return None
    
    def record_modification(self, row_index: int, column: str, old_value: Any, new_value: Any):
        """记录数据修改历史"""
        from datetime import datetime
        
        # 获取现有的修改记录
        modifications = self._session_manager.get_data('data_modifications') or []
        
        # 添加新的修改记录
        modification_record = {
            'timestamp': datetime.now().isoformat(),
            'row_index': row_index,
            'column': column,
            'old_value': old_value,
            'new_value': new_value,
            'session_id': self._session_manager.session_id
        }
        
        modifications.append(modification_record)
        
        # 保存修改记录（保留最近1000条）
        if len(modifications) > 1000:
            modifications = modifications[-1000:]
        
        self._session_manager.set_data('data_modifications', modifications)
        self.mark_deducted_data_modified()
        
        print(f"📝 记录数据修改: 行{row_index}, 列'{column}': {old_value} -> {new_value}")
    
    # 新增方法：提取结果数据管理
    def backup_original_extracted_data(self):
        """仅备份原始提取结果数据，不自动创建手工数据"""
        try:
            import copy
            import pandas as pd
            
            extracted_data = self._session_manager.get_data('extracted_data')
            original_data = self._session_manager.get_data('original_extracted_data')
            
            # 检查是否有提取结果数据
            if extracted_data is None or (isinstance(extracted_data, pd.DataFrame) and extracted_data.empty):
                print("⚠️ 没有提取结果数据，无法备份")
                return False
            
            # 检查是否需要创建原始备份
            if original_data is None or (isinstance(original_data, pd.DataFrame) and original_data.empty):
                # 深拷贝备份原始数据
                self._session_manager.set_data('original_extracted_data', copy.deepcopy(extracted_data))
                print(f"✅ 已创建原始提取结果数据备份: {len(extracted_data)} 条记录")
            
            # 不再自动创建手工数据，手工数据必须通过"从只读数据初始化"按钮显式创建
            
            return True
            
        except Exception as e:
            print(f"⚠️ 备份原始提取结果数据失败: {e}")
            return False
    
    def mark_extracted_data_modified(self):
        """标记提取结果数据已修改"""
        from datetime import datetime
        self._session_manager.set_data('extracted_data_modified', True)
        self._session_manager.set_data('extracted_modification_timestamp', datetime.now())
    
    def is_extracted_data_modified(self) -> bool:
        """检查提取结果数据是否已修改"""
        return self._session_manager.get_data('extracted_data_modified') or False
    
    def get_extracted_modification_timestamp(self):
        """获取提取结果修改时间戳"""
        return self._session_manager.get_data('extracted_modification_timestamp')
    
    def reset_extracted_data_to_original(self):
        """重置提取结果数据(手工)到原始状态"""
        try:
            original_data = self._session_manager.get_data('original_extracted_data')
            if original_data is not None:
                # 重置手工数据为原始数据
                self._session_manager.set_data('extracted_data_manual', original_data.copy())
                self._session_manager.set_data('extracted_data_modified', False)
                self._session_manager.set_data('extracted_modifications', {})
                self._session_manager.set_data('extracted_modification_timestamp', None)
                print("✅ 提取结果数据(手工)已重置到原始状态")
                return True
            else:
                print("⚠️ 没有原始提取结果数据备份，无法重置")
                return False
        except Exception as e:
            print(f"⚠️ 重置提取结果数据失败: {e}")
            return False
    
    def get_extracted_comparison_stats(self) -> Dict[str, Any]:
        """获取提取结果数据对比统计（旧机口径：原始=初始数据基准，当前=非限制使用的库存）"""
        try:
            import pandas as pd

            def _old_machine_subset(df):
                if df is None or (isinstance(df, pd.DataFrame) and df.empty):
                    return None
                if not isinstance(df, pd.DataFrame):
                    return None
                if '类别' in df.columns:
                    return df[df['类别'] == '旧机']
                return df

            def _sum_column(df, col_name: str) -> float:
                sub = _old_machine_subset(df)
                if sub is None or sub.empty or col_name not in sub.columns:
                    return 0.0
                try:
                    col = pd.to_numeric(sub[col_name], errors='coerce').fillna(0)
                    return float(col.sum())
                except Exception as ex:
                    print(f"汇总列 {col_name} 时出错: {ex}")
                    return 0.0

            def _old_machine_count(df) -> int:
                sub = _old_machine_subset(df)
                return int(len(sub)) if sub is not None else 0

            original_data = self._session_manager.get_data('original_extracted_data')
            manual_data = self._session_manager.get_data('extracted_data_manual')
            readonly_extracted = self._session_manager.get_data('extracted_data')

            stats = {
                'modified': False,
                'modification_timestamp': None,
                'original': {
                    'count': 0,
                    'total_inventory': 0
                },
                'current': {
                    'count': 0,
                    'total_inventory': 0
                },
                'difference': {
                    'count': 0,
                    'inventory': 0
                }
            }

            # 当前总库存：手工表旧机「非限制使用的库存」；无手工表时用只读提取结果
            if manual_data is not None and not manual_data.empty:
                stats['current']['total_inventory'] = _sum_column(manual_data, '非限制使用的库存')
                stats['current']['count'] = _old_machine_count(manual_data)
            else:
                stats['current']['total_inventory'] = _sum_column(readonly_extracted, '非限制使用的库存')
                stats['current']['count'] = _old_machine_count(readonly_extracted)

            # 原始总库存：有手工表且含「初始数据」时按旧机初始数据之和；否则按快照/只读旧机「非限制使用的库存」
            if (
                manual_data is not None
                and not manual_data.empty
                and isinstance(manual_data, pd.DataFrame)
                and '初始数据' in manual_data.columns
            ):
                stats['original']['total_inventory'] = _sum_column(manual_data, '初始数据')
                stats['original']['count'] = _old_machine_count(manual_data)
            elif original_data is not None and not original_data.empty:
                stats['original']['total_inventory'] = _sum_column(original_data, '非限制使用的库存')
                stats['original']['count'] = _old_machine_count(original_data)
            else:
                stats['original']['total_inventory'] = _sum_column(readonly_extracted, '非限制使用的库存')
                stats['original']['count'] = _old_machine_count(readonly_extracted)

            # 计算差异
            stats['difference']['count'] = stats['current']['count'] - stats['original']['count']
            stats['difference']['inventory'] = stats['current']['total_inventory'] - stats['original']['total_inventory']
            
            # 检查是否有修改
            if self.is_extracted_data_modified():
                stats['modified'] = True
                stats['modification_timestamp'] = self.get_extracted_modification_timestamp()
            
            # 如果有库存差异，标记为有变化
            if abs(stats['difference']['inventory']) > 0.001:
                stats['modified'] = True
            
            return stats
            
        except Exception as e:
            print(f"获取提取结果数据对比统计失败: {e}")
            return {
                'modified': False,
                'modification_timestamp': None,
                'original': {
                    'count': 0,
                    'total_inventory': 0
                },
                'current': {
                    'count': 0,
                    'total_inventory': 0
                },
                'difference': {
                    'count': 0,
                    'inventory': 0
                },
                'error': str(e)
            }
    
    def get_deducted_comparison_stats(self) -> Dict[str, Any]:
        """获取被减扣数据对比统计"""
        try:
            original_data = self._session_manager.get_data('original_deducted_data')
            manual_data = self._session_manager.get_data('deducted_data_manual')
            
            stats = {
                'modified': False,
                'modification_timestamp': None,
                'original': {
                    'count': len(original_data) if original_data is not None else 0,
                    'total_weight': 0
                },
                'current': {
                    'count': len(manual_data) if manual_data is not None else 0,
                    'total_weight': 0
                },
                'difference': {
                    'count': 0,
                    'weight': 0
                }
            }
            
            # 计算原始数据总重量
            if original_data is not None and not original_data.empty:
                try:
                    import pandas as pd
                    if isinstance(original_data, pd.DataFrame) and '计算结果(KG)' in original_data.columns:
                        # 将非数值转换为0，然后求和
                        weight_col = original_data['计算结果(KG)']
                        weight_col = pd.to_numeric(weight_col, errors='coerce').fillna(0)
                        stats['original']['total_weight'] = float(weight_col.sum())
                except Exception as e:
                    print(f"计算原始数据总重量时出错: {e}")
            
            # 计算手工数据总重量
            if manual_data is not None and not manual_data.empty:
                try:
                    import pandas as pd
                    if isinstance(manual_data, pd.DataFrame) and '计算结果(KG)' in manual_data.columns:
                        # 将非数值转换为0，然后求和
                        weight_col = manual_data['计算结果(KG)']
                        weight_col = pd.to_numeric(weight_col, errors='coerce').fillna(0)
                        stats['current']['total_weight'] = float(weight_col.sum())
                except Exception as e:
                    print(f"计算手工数据总重量时出错: {e}")
            
            # 计算差异
            stats['difference']['count'] = stats['current']['count'] - stats['original']['count']
            stats['difference']['weight'] = stats['current']['total_weight'] - stats['original']['total_weight']
            
            # 检查是否有修改
            if self.is_deducted_data_modified():
                stats['modified'] = True
                stats['modification_timestamp'] = self.get_modification_timestamp()
            
            # 如果有重量差异，标记为有变化
            if abs(stats['difference']['weight']) > 0.001:  # 考虑浮点数精度
                stats['modified'] = True
            
            # 计算数据差异（保留原有逻辑）
            if original_data is not None and manual_data is not None:
                try:
                    import pandas as pd
                    if isinstance(original_data, pd.DataFrame) and isinstance(manual_data, pd.DataFrame):
                        # 比较数值列的差异
                        numeric_cols = original_data.select_dtypes(include=['number']).columns
                        for col in numeric_cols:
                            if col in manual_data.columns:
                                original_sum = original_data[col].sum() if not original_data[col].isna().all() else 0
                                manual_sum = manual_data[col].sum() if not manual_data[col].isna().all() else 0
                                if abs(original_sum - manual_sum) > 0.001:  # 考虑浮点数精度
                                    stats['modified'] = True
                                    break
                except Exception as e:
                    print(f"比较数据差异时出错: {e}")
            
            return stats
            
        except Exception as e:
            print(f"获取被减扣数据对比统计失败: {e}")
            return {
                'modified': False,
                'modification_timestamp': None,
                'original': {
                    'count': 0,
                    'total_weight': 0
                },
                'current': {
                    'count': 0,
                    'total_weight': 0
                },
                'difference': {
                    'count': 0,
                    'weight': 0
                },
                'error': str(e)
            }


def migrate_from_pickle():
    """
    从pickle文件迁移数据到新的数据库系统
    这是一个一次性迁移工具
    """
    import os
    import pickle
    from app.config import config
    from flask import current_app
    
    try:
        # 检查是否存在旧的pickle文件
        pickle_file = config.PERSISTENT_DATA_FILE
        if not os.path.exists(pickle_file):
            current_app.logger.info("没有找到旧的pickle文件，跳过迁移")
            return True
        
        # 读取pickle文件
        with open(pickle_file, 'rb') as f:
            old_data = pickle.load(f)
        
        current_app.logger.info(f"开始迁移pickle数据，共 {len(old_data)} 个数据项")
        
        # 创建迁移会话
        migration_session_id = "migration_" + str(uuid.uuid4())
        adapter = AppDataManagerAdapter(migration_session_id)
        
        # 迁移数据
        for key, value in old_data.items():
            if value is not None:
                adapter.set_data(key, value)
                current_app.logger.info(f"迁移数据项: {key}")
        
        # 备份原文件
        backup_file = f"{pickle_file}.backup"
        import shutil
        shutil.move(pickle_file, backup_file)
        
        current_app.logger.info(f"数据迁移完成，原文件已备份到: {backup_file}")
        current_app.logger.info(f"迁移会话ID: {migration_session_id}")
        
        return True
        
    except Exception as e:
        current_app.logger.error(f"数据迁移失败: {e}")
        return False


# 全局适配器实例（向后兼容）
_global_adapter = None

def get_global_adapter() -> AppDataManagerAdapter:
    """获取全局适配器实例"""
    global _global_adapter
    if _global_adapter is None:
        _global_adapter = AppDataManagerAdapter()
    return _global_adapter


# 替换原始的AppDataManager类（向后兼容）
class AppDataManager(AppDataManagerAdapter):
    """
    替换原始的AppDataManager类
    保持完全的向后兼容性
    """
    
    _instance = None
    
    def __new__(cls, session_id: str = None):
        # 不再使用单例模式，每个会话都有独立的实例
        return super().__new__(cls)
    
    def __init__(self, session_id: str = None):
        if hasattr(self, '_initialized'):
            return
        super().__init__(session_id)
        self._initialized = True
    
    @classmethod
    def get_instance(cls, session_id: str = None):
        """获取实例（不再是单例）"""
        return cls(session_id) 