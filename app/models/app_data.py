import os
import json
import pickle
import pandas as pd
import numpy as np
from datetime import datetime
from app.config import config
import copy

class AppDataManager:
    """应用数据管理器 - 单例模式"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppDataManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._data = {
            'source_data': None,
            'mapping_data': None,
            'extracted_data': None,
            'disassembly_data': None,  # 原始数据(未减扣)
            # 🔧 架构重构：移除 deducted_data (只读)，只保留 deducted_data_manual
            'deducted_data_manual': None,  # 被减扣数据(手工) - 唯一工作数据源，参与所有计算
            'calculated_data': None,   # 减扣后数据
            'deep_processing_data': None,  # 深加工数据
            'saleable_data': None,     # 可销售量数据
            # 被减扣数据备份和修改追踪
            'original_deducted_data': None,  # 原始被减扣数据备份（用于恢复）
            'deducted_data_modified': False,  # 标记是否有修改
            'deducted_modifications': {},     # 记录具体修改内容
            'modification_timestamp': None,   # 修改时间戳
            'deep_processing_data_source': 'original',  # 深加工数据源标记: 'original' 或 'modified'
            'status': '就绪',
            'progress': 0
        }
        
        # 确保数据存储目录存在
        if not os.path.exists(config.DATA_STORAGE_DIR):
            os.makedirs(config.DATA_STORAGE_DIR)
            
        self._initialized = True
    
    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def get_data(self, key=None):
        """获取数据"""
        if key is None:
            return self._data.copy()
        return self._data.get(key)
    
    def set_data(self, key, value):
        """设置数据"""
        self._data[key] = value
    
    def update_status(self, status, progress=None):
        """更新状态"""
        self._data['status'] = status
        if progress is not None:
            self._data['progress'] = progress
    
    def safe_json_convert(self, df):
        """安全的DataFrame转JSON转换"""
        if df is None or df.empty:
            return []
        try:
            df_clean = df.replace({np.nan: None})
            return df_clean.to_dict('records')
        except Exception as e:
            print(f'JSON转换错误: {e}')
            return []
    
    def save_persistent_data(self):
        """保存持久化数据"""
        try:
            # 创建备份目录
            backup_dir = os.path.join(config.DATA_STORAGE_DIR, 'backups')
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            
            # 如果存在旧文件，创建备份
            if os.path.exists(config.PERSISTENT_DATA_FILE):
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_file = os.path.join(backup_dir, f'app_data_backup_{timestamp}.pkl')
                import shutil
                shutil.copy2(config.PERSISTENT_DATA_FILE, backup_file)
            
            # 保存数据
            with open(config.PERSISTENT_DATA_FILE, 'wb') as f:
                pickle.dump(self._data, f)
            
            # 保存数据信息
            data_info = {
                'last_updated': datetime.now().isoformat(),
                'data_keys': list(self._data.keys()),
                'non_empty_keys': [k for k, v in self._data.items() if v is not None]
            }
            
            with open(config.DATA_INFO_FILE, 'w', encoding='utf-8') as f:
                json.dump(data_info, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f'保存数据失败: {e}')
            return False
    
    def load_persistent_data(self):
        """加载持久化数据"""
        try:
            if os.path.exists(config.PERSISTENT_DATA_FILE):
                with open(config.PERSISTENT_DATA_FILE, 'rb') as f:
                    loaded_data = pickle.load(f)
                
                # 恢复数据，处理旧格式
                for key, value in loaded_data.items():
                    if key in self._data:
                        # 检查是否是旧格式（带type字段的字典）
                        if isinstance(value, dict) and 'type' in value:
                            if value['type'] == 'dataframe' and value['data']:
                                # 重建DataFrame
                                self._data[key] = pd.DataFrame(value['data'])
                                print(f"恢复DataFrame数据: {key}, 形状: {self._data[key].shape}")
                            elif value['type'] == 'other':
                                self._data[key] = value['data']
                        else:
                            # 新格式，直接使用
                            self._data[key] = value
                            if isinstance(value, pd.DataFrame) and not value.empty:
                                print(f"加载DataFrame数据: {key}, 形状: {value.shape}")
                            elif value is not None:
                                print(f"加载数据: {key}, 类型: {type(value)}")
                
                # 打印关键数据状态
                # 🔧 架构重构：使用 deducted_data_manual，不再使用 deducted_data (只读)
                deducted_count = len(self._data['deducted_data_manual']) if self._data.get('deducted_data_manual') is not None and not self._data['deducted_data_manual'].empty else 0
                original_count = len(self._data['original_deducted_data']) if self._data.get('original_deducted_data') is not None and not self._data['original_deducted_data'].empty else 0
                manual_count = len(self._data['deducted_data_manual']) if self._data.get('deducted_data_manual') is not None and not self._data['deducted_data_manual'].empty else 0
                print(f'数据加载成功 - 被减扣数据: {deducted_count}条, 原始备份: {original_count}条, 手工数据: {manual_count}条')
                return True
        except Exception as e:
            print(f'加载数据失败: {e}')
            import traceback
            traceback.print_exc()
        
        return False
    
    def clear_data(self, key=None):
        """清除数据"""
        if key is None:
            # 清除所有数据但保持结构
            for k in self._data.keys():
                if k not in ['status', 'progress']:
                    self._data[k] = None
            self._data['status'] = '就绪'
            self._data['progress'] = 0
            
            # 重新加载内置映射表数据
            self._reload_builtin_mapping()
        else:
            if key in self._data:
                self._data[key] = None
    
    def _reload_builtin_mapping(self):
        """重新加载内置映射表数据"""
        try:
            from data.base_data.mapping_data import get_mapping_dataframe
            mapping_data = get_mapping_dataframe()
            self._data['mapping_data'] = mapping_data
            print(f"✅ 内置映射表重新加载成功: {len(mapping_data)} 条记录")
        except Exception as e:
            print(f"⚠️ 内置映射表重新加载失败: {e}")
            self._data['mapping_data'] = None
    
    def backup_original_deducted_data(self):
        """备份原始被减扣数据 - 🔧 架构重构：从 deducted_data_manual 备份"""
        try:
            # 🔧 架构重构：从 deducted_data_manual 备份，不再使用 deducted_data
            manual_data = self._data.get('deducted_data_manual')
            original_data = self._data.get('original_deducted_data')
            
            # 检查是否有被减扣数据(手工)
            if manual_data is None or (isinstance(manual_data, pd.DataFrame) and manual_data.empty):
                print("⚠️ 没有被减扣数据(手工)，无法备份")
                return False
            
            # 检查是否需要创建原始备份
            if original_data is None or (isinstance(original_data, pd.DataFrame) and original_data.empty):
                # 深拷贝备份手工数据作为原始备份
                self._data['original_deducted_data'] = copy.deepcopy(manual_data)
                print(f"✅ 已创建原始被减扣数据备份: {len(manual_data)} 条记录")
            
            # 确保修改标志正确
            if not self._data.get('deducted_data_modified'):
                self._data['deducted_data_modified'] = False
                self._data['deducted_modifications'] = {}
            
            return True
            
        except Exception as e:
            print(f"⚠️ 备份原始被减扣数据失败: {e}")
            return False
    
    def mark_deducted_data_modified(self):
        """标记被减扣数据(手工)已修改"""
        self._data['deducted_data_modified'] = True
        self._data['modification_timestamp'] = datetime.now()
        print(f"✅ 已标记被减扣数据(手工)为已修改状态，时间: {self._data['modification_timestamp']}")
    
    def record_modification(self, row_index, field, old_value, new_value):
        """记录具体修改内容"""
        try:
            if 'deducted_modifications' not in self._data:
                self._data['deducted_modifications'] = {}
            
            modification_key = f"{row_index}_{field}"
            self._data['deducted_modifications'][modification_key] = {
                'row_index': row_index,
                'field': field,
                'old_value': old_value,
                'new_value': new_value,
                'timestamp': datetime.now()
            }
            print(f"✅ 记录修改: 行{row_index} {field}: {old_value} -> {new_value}")
        except Exception as e:
            print(f"⚠️ 记录修改失败: {e}")
    
    def get_data_for_deep_processing(self):
        """
        获取用于深加工计算的数据源
        🔧 架构重构：只使用 deducted_data_manual，不再使用 deducted_data (只读)
        """
        # 优先使用手工数据（唯一工作数据源）
        manual_data = self._data.get('deducted_data_manual')
        if manual_data is not None and not (isinstance(manual_data, pd.DataFrame) and manual_data.empty):
            modified = self._data.get('deducted_data_modified')
            if modified:
                print(f"🔄 使用已编辑的被减扣数据(手工)进行深加工计算 - {len(manual_data)} 条记录")
            else:
                print(f"🔄 使用被减扣数据(手工)进行深加工计算 - {len(manual_data)} 条记录")
            self._data['deep_processing_data_source'] = 'manual'
            return manual_data
        
        # 如果手工数据为空且未修改，尝试从原始备份恢复
        modified = self._data.get('deducted_data_modified')
        if not modified:
            original_data = self._data.get('original_deducted_data')
            if original_data is not None and not (isinstance(original_data, pd.DataFrame) and original_data.empty):
                # 从原始备份恢复
                self._data['deducted_data_manual'] = copy.deepcopy(original_data)
                print(f"🔄 从原始备份恢复被减扣数据(手工) - {len(original_data)} 条记录")
                self._data['deep_processing_data_source'] = 'manual'
                return original_data
        
        print("⚠️ 没有被减扣数据，跳过深加工计算")
        self._data['deep_processing_data_source'] = 'none'
        return None
    
    def reset_deducted_data_to_original(self):
        """重置被减扣数据(手工)到原始状态"""
        try:
            if self._data.get('original_deducted_data') is not None:
                # 重置手工数据为原始数据
                self._data['deducted_data_manual'] = copy.deepcopy(self._data['original_deducted_data'])
                self._data['deducted_data_modified'] = False
                self._data['deducted_modifications'] = {}
                self._data['modification_timestamp'] = None
                print("✅ 被减扣数据(手工)已重置到原始状态")
                return True
            else:
                print("⚠️ 没有原始被减扣数据备份，无法重置")
                return False
        except Exception as e:
            print(f"⚠️ 重置被减扣数据失败: {e}")
            return False
    
    def get_deducted_comparison_stats(self):
        """获取被减扣数据对比统计"""
        try:
            original_data = self._data.get('original_deducted_data')
            current_data = self._data.get('deducted_data_manual')
            
            stats = {
                'modified': self._data.get('deducted_data_modified', False),
                'modification_timestamp': self._data.get('modification_timestamp'),
                'original': {'count': 0, 'total_weight': 0},
                'current': {'count': 0, 'total_weight': 0},
                'difference': {'count': 0, 'weight': 0}
            }
            
            if original_data is not None:
                stats['original']['count'] = len(original_data)
                if '计算结果(KG)' in original_data.columns:
                    stats['original']['total_weight'] = float(original_data['计算结果(KG)'].sum())
            
            if current_data is not None:
                stats['current']['count'] = len(current_data)
                if '计算结果(KG)' in current_data.columns:
                    stats['current']['total_weight'] = float(current_data['计算结果(KG)'].sum())
            
            # 计算差异
            stats['difference']['count'] = stats['current']['count'] - stats['original']['count']
            stats['difference']['weight'] = stats['current']['total_weight'] - stats['original']['total_weight']
            
            return stats
            
        except Exception as e:
            print(f"⚠️ 获取对比统计失败: {e}")
            return {
                'modified': False,
                'original': {'count': 0, 'total_weight': 0},
                'current': {'count': 0, 'total_weight': 0},
                'difference': {'count': 0, 'weight': 0}
            } 