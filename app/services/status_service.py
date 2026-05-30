"""
状态信息服务
"""
import os
import json
from app.models.app_data import AppDataManager
from app.config import config

class StatusService:
    """状态信息服务"""
    
    def __init__(self, session_id=None):
        # 支持会话隔离
        if session_id:
            from app.models.compatibility import AppDataManagerAdapter
            self.app_data = AppDataManagerAdapter.get_instance(session_id)
        else:
            self.app_data = AppDataManager.get_instance()
    
    def get_status_info(self):
        """获取系统状态信息"""
        try:
            # 获取映射数据计数 - 直接从基础数据文件获取
            mapping_count = 0
            try:
                from data.base_data.mapping_data import get_mapping_dataframe
                mapping_df = get_mapping_dataframe()
                mapping_count = len(mapping_df) if mapping_df is not None else 0
            except ImportError:
                mapping_count = 0
            
            # 获取产品数据计数
            product_count = 0
            try:
                from data.base_data.product_data import PRODUCT_DISASSEMBLY_DATA
                product_count = len(PRODUCT_DISASSEMBLY_DATA)
            except ImportError:
                product_count = 0
            
            # 获取减扣规则计数
            deduction_count = 0
            try:
                from data.base_data.deduction_data import DEDUCTION_CODES
                deduction_count = len(DEDUCTION_CODES)
            except ImportError:
                deduction_count = 0
            
            # 获取深加工数据计数
            deep_processing_count = 0
            try:
                import data.base_data.deep_processing_data as dpd
                deep_df = dpd.get_deep_processing_dataframe()
                deep_processing_count = len(deep_df) if deep_df is not None else 0
            except (ImportError, AttributeError):
                deep_processing_count = 0
            
            has_calc_results = self._check_persistent_data()

            from app.services.opening_inventory_store import (
                get_status_fields,
                get_global_source_row_count,
            )
            opening_fields = get_status_fields()
            global_source_rows = get_global_source_row_count()

            # 构建状态信息
            status_info = {
                'mapping_count': mapping_count,
                'product_count': product_count,
                'deduction_count': deduction_count,
                'deep_processing_count': deep_processing_count,
                'current_status': self.app_data.get_data('status') or '就绪',
                'has_persistent_data': has_calc_results,
                'source_records': global_source_rows or self._get_data_count('source_data'),
                'extracted_records': self._get_data_count('extracted_data'),
                'saleable_records': self._get_data_count('saleable_data'),
                'deep_processing_records': self._get_data_count('deep_processing_data'),
            }
            status_info.update(opening_fields)
            status_info['can_run_calculation'] = (
                opening_fields.get('can_run_calculation', False) or has_calc_results
            )

            # 获取数据时间戳
            status_info['data_timestamp'] = self._get_data_timestamp()
            
            return status_info
            
        except Exception as e:
            # 返回默认状态信息
            return {
                'mapping_count': 0,
                'product_count': 0,
                'deduction_count': 0,
                'deep_processing_count': 0,
                'current_status': f'状态获取异常: {str(e)}',
                'has_persistent_data': False,
                'has_opening_inventory_file': False,
                'has_source_data': False,
                'can_run_calculation': False,
                'opening_inventory_meta': None,
                'opening_inventory_rows': 0,
                'source_records': 0,
                'extracted_records': 0,
                'saleable_records': 0,
                'deep_processing_records': 0,
                'data_timestamp': '未知'
            }
    
    def _get_data_count(self, key):
        """获取数据计数"""
        data = self.app_data.get_data(key)
        return len(data) if data is not None else 0
    
    def _check_persistent_data(self):
        """检查是否有持久化数据"""
        # 新架构：检查当前会话是否有可销售量数据（表示已完成计算流程）
        # 优先从 DB 直接读，避免同步后因内存/Redis 缓存未更新而误判为无数据
        try:
            get_from_db = getattr(self.app_data, 'get_data_from_db', None)
            if callable(get_from_db):
                saleable_data = get_from_db('saleable_data')
                deep_processing_data = get_from_db('deep_processing_data')
            else:
                saleable_data = self.app_data.get_data('saleable_data')
                deep_processing_data = self.app_data.get_data('deep_processing_data')
            if (saleable_data is not None and hasattr(saleable_data, 'empty') and not saleable_data.empty) or \
               (deep_processing_data is not None and hasattr(deep_processing_data, 'empty') and not deep_processing_data.empty):
                return True
            return False
        except Exception:
            return os.path.exists(config.PERSISTENT_DATA_FILE)
    
    def _get_data_timestamp(self):
        """获取数据时间戳"""
        try:
            if os.path.exists(config.DATA_INFO_FILE):
                with open(config.DATA_INFO_FILE, 'r', encoding='utf-8') as f:
                    data_info = json.load(f)
                    return data_info.get('timestamp', '未知')
            else:
                return '未知'
        except Exception:
            return '未知' 