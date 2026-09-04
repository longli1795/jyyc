from app.core.data_processor import DataProcessor
from app.core.calculation_engine import CalculationEngine
from app.models.compatibility import AppDataManager
import time

class CalculationService:
    """计算服务层"""
    
    def __init__(self, session_id: str = None):
        self.app_data = AppDataManager.get_instance(session_id)
        self.data_processor = DataProcessor(session_id)
        self.calculation_engine = CalculationEngine(session_id)
        print(f"[INFO] CalculationService使用会话ID: {session_id}")
    
    def auto_process_all(self):
        """一键自动处理所有步骤"""
        start_time = time.time()
        calc_id = None
        
        try:
            # 记录计算开始
            calc_id = self.app_data.record_calculation(
                calculation_type='auto_process_all',
                status='started',
                input_parameters={}
            )
            
            self.app_data.update_status('开始自动处理...')
            
            # 清除数据清除标志（如果存在），允许重新计算
            self.app_data.set_data('__data_cleared__', False)
            
            # 步骤1: 提取数据
            if not self.data_processor.extract_data_auto():
                error_msg = '数据提取失败'
                self.app_data.record_calculation(
                    calculation_type='auto_process_all',
                    status='failed',
                    error_message=error_msg,
                    duration=time.time() - start_time
                )
                return False, error_msg
            
            self.app_data.update_status('数据提取完成，开始计算拆解...')
            
            # 步骤2: 计算旧机拆解
            if not self.calculation_engine.calculate_disassembly_auto():
                error_msg = '旧机拆解计算失败'
                self.app_data.record_calculation(
                    calculation_type='auto_process_all',
                    status='failed',
                    error_message=error_msg,
                    duration=time.time() - start_time
                )
                return False, error_msg
            
            self.app_data.update_status('拆解计算完成，开始深加工计算...')
            
            # 步骤3: 计算深加工
            if not self.calculate_deep_processing():
                error_msg = '深加工计算失败'
                self.app_data.record_calculation(
                    calculation_type='auto_process_all',
                    status='failed',
                    error_message=error_msg,
                    duration=time.time() - start_time
                )
                return False, error_msg
            
            self.app_data.update_status('深加工计算完成，开始合并可销售量数据...')
            
            # 步骤4: 合并生成可销售量数据
            if not self.calculation_engine.merge_saleable_data():
                error_msg = '可销售量数据合并失败'
                self.app_data.record_calculation(
                    calculation_type='auto_process_all',
                    status='failed',
                    error_message=error_msg,
                    duration=time.time() - start_time
                )
                return False, error_msg
            
            self.app_data.update_status('可销售量数据合并完成（含价格和收益）')
            
            # 步骤5: 计算基金补贴收入
            if not self.calculation_engine.calculate_subsidy_income():
                error_msg = '基金补贴收入计算失败'
                self.app_data.record_calculation(
                    calculation_type='auto_process_all',
                    status='failed',
                    error_message=error_msg,
                    duration=time.time() - start_time
                )
                return False, error_msg
            
            self.app_data.update_status('基金补贴收入计算完成')
            
            # 步骤6: 将补贴收入添加到可销售量数据
            if not self.calculation_engine.add_subsidy_to_saleable_data():
                error_msg = '补贴收入添加失败'
                self.app_data.record_calculation(
                    calculation_type='auto_process_all',
                    status='failed',
                    error_message=error_msg,
                    duration=time.time() - start_time
                )
                return False, error_msg
            
            self.app_data.update_status('补贴收入已添加到可销售量数据')
            
            # 步骤7: 初始化提取结果手工数据（用于成本预测）
            self.app_data.update_status('开始初始化成本预测数据...')
            if not self.initialize_cost_forecast_data():
                error_msg = '成本预测数据初始化失败'
                self.app_data.record_calculation(
                    calculation_type='auto_process_all',
                    status='failed',
                    error_message=error_msg,
                    duration=time.time() - start_time
                )
                return False, error_msg
            
            self.app_data.update_status('成本预测数据初始化完成')
            
            # 步骤8: 计算成本预测（拆解物原料成本和生产工人计件工资）
            self.app_data.update_status('开始计算成本预测...')
            if not self.calculate_cost_forecast():
                error_msg = '成本预测计算失败'
                self.app_data.record_calculation(
                    calculation_type='auto_process_all',
                    status='failed',
                    error_message=error_msg,
                    duration=time.time() - start_time
                )
                return False, error_msg
            
            self.app_data.update_status('成本预测计算完成')
            
            # 步骤9: 刷新成本计算页缓存（屏分摊→生产分摊→拆解产物成本→深加工产物成本）
            self.app_data.update_status('开始刷新成本计算页缓存...')
            self.refresh_cost_calculation_caches()
            self.app_data.update_status('成本计算页缓存刷新完成')
            
            self.app_data.update_status('所有计算完成')
            
            # 记录成功完成
            duration = time.time() - start_time
            self.app_data.record_calculation(
                calculation_type='auto_process_all',
                status='completed',
                duration=duration,
                result_summary={
                    'total_steps': 9,
                    'duration_seconds': duration,
                    'session_id': self.get_session_id()
                }
            )
            
            return True, '自动处理完成！'
            
        except Exception as e:
            error_msg = f'自动处理失败: {str(e)}'
            self.app_data.update_status(error_msg)
            
            # 记录失败
            self.app_data.record_calculation(
                calculation_type='auto_process_all',
                status='failed',
                error_message=error_msg,
                duration=time.time() - start_time
            )
            
            return False, error_msg
    
    def extract_data(self):
        """手动提取数据"""
        start_time = time.time()
        
        try:
            calc_id = self.app_data.record_calculation(
                calculation_type='extract_data',
                status='started'
            )
            
            result = self.data_processor.extract_data_auto()
            
            self.app_data.record_calculation(
                calculation_type='extract_data',
                status='completed' if result else 'failed',
                duration=time.time() - start_time
            )
            
            return result
            
        except Exception as e:
            self.app_data.record_calculation(
                calculation_type='extract_data',
                status='failed',
                error_message=str(e),
                duration=time.time() - start_time
            )
            return False
    
    def calculate_disassembly(self):
        """手动计算拆解"""
        start_time = time.time()
        
        try:
            calc_id = self.app_data.record_calculation(
                calculation_type='calculate_disassembly',
                status='started'
            )
            
            result = self.calculation_engine.calculate_disassembly_auto()
            
            self.app_data.record_calculation(
                calculation_type='calculate_disassembly',
                status='completed' if result else 'failed',
                duration=time.time() - start_time
            )
            
            return result
            
        except Exception as e:
            self.app_data.record_calculation(
                calculation_type='calculate_disassembly',
                status='failed',
                error_message=str(e),
                duration=time.time() - start_time
            )
            return False
    
    def calculate_deep_processing(self):
        """计算深加工"""
        start_time = time.time()
        
        try:
            calc_id = self.app_data.record_calculation(
                calculation_type='calculate_deep_processing',
                status='started'
            )
            
            result = self.calculation_engine.calculate_deep_processing_auto()
            
            self.app_data.record_calculation(
                calculation_type='calculate_deep_processing',
                status='completed' if result else 'failed',
                duration=time.time() - start_time,
                result_summary={
                    'deep_processing_completed': result
                }
            )
            
            return result
            
        except Exception as e:
            self.app_data.record_calculation(
                calculation_type='calculate_deep_processing',
                status='failed',
                error_message=str(e),
                duration=time.time() - start_time
            )
            return False
    
    def get_results_summary(self):
        """获取计算结果摘要"""
        try:
            summary = {}
            
            # 获取各种数据的统计
            source_data = self.app_data.get_data('source_data')
            extracted_data = self.app_data.get_data('extracted_data')
            disassembly_data = self.app_data.get_data('disassembly_data')
            # 🔧 架构重构：只使用 deducted_data_manual，不再使用 deducted_data (只读)
            deducted_data_manual = self.app_data.get_data('deducted_data_manual')
            deep_processing_data = self.app_data.get_data('deep_processing_data')
            saleable_data = self.app_data.get_data('saleable_data')
            
            summary['source_count'] = len(source_data) if source_data is not None else 0
            summary['extracted_count'] = len(extracted_data) if extracted_data is not None else 0
            summary['disassembly_count'] = len(disassembly_data) if disassembly_data is not None else 0
            summary['deducted_count'] = len(deducted_data_manual) if deducted_data_manual is not None else 0  # 🔧 架构重构
            summary['deducted_manual_count'] = len(deducted_data_manual) if deducted_data_manual is not None else 0
            summary['deep_processing_count'] = len(deep_processing_data) if deep_processing_data is not None else 0
            summary['saleable_count'] = len(saleable_data) if saleable_data is not None else 0
            
            # 检查是否需要手工编辑被减扣数据
            summary['needs_manual_editing'] = (
                summary['deducted_count'] > 0 and 
                summary['deducted_manual_count'] == 0 and
                summary['deep_processing_count'] == 0
            )
            
            # 如果需要手工编辑，提供引导信息
            if summary['needs_manual_editing']:
                summary['next_step'] = {
                    'action': 'manual_edit_deducted_data',
                    'message': f'已生成 {summary["deducted_count"]} 条被减扣数据，请前往手工编辑页面进行调整',
                    'url': '/data-management/deducted-data',
                    'button_text': '前往手工编辑页面'
                }
            
            return summary
            
        except Exception as e:
            print(f"获取结果摘要失败: {str(e)}")
            return {
                'error': str(e),
                'needs_manual_editing': False
            }
    
    def get_session_id(self):
        """获取当前会话ID"""
        return self.app_data._session_manager.session_id
    
    def get_calculation_history(self, limit: int = 10):
        """获取计算历史"""
        return self.app_data.get_calculation_history(limit)
    
    def get_session_info(self):
        """获取会话信息"""
        return self.app_data.get_session_info()
    
    def initialize_cost_forecast_data(self):
        """初始化成本预测数据（从提取结果数据初始化手工数据）"""
        try:
            import pandas as pd
            from datetime import datetime
            
            # 获取只读数据
            readonly_data = self.app_data.get_data('extracted_data')
            if readonly_data is None or readonly_data.empty:
                print("⚠️ 没有提取结果数据，跳过成本预测数据初始化")
                return True  # 不是错误，只是没有数据
            
            # 检查是否已有手工数据
            manual_data = self.app_data.get_data('extracted_data_manual')
            if manual_data is not None and not manual_data.empty:
                print("ℹ️ 提取结果手工数据已存在，跳过初始化")
                return True
            
            # 复制所有类别的数据（保留完整数据）
            print("[成本预测初始化] 开始初始化提取结果手工数据...")
            manual_data = readonly_data.copy()
            
            # 检查是否有旧机类别
            if '类别' in manual_data.columns:
                old_machine_count = len(manual_data[manual_data['类别'] == '旧机'])
                if old_machine_count == 0:
                    print("[成本预测初始化] 没有找到旧机类别数据，跳过初始化")
                    return True
            
            # 添加新列
            manual_data['初始数据'] = 0.0
            manual_data['本期计划采购数量'] = 0.0
            manual_data['计划采购单价'] = 0.0
            manual_data['本期计划投产数量'] = 0.0
            
            # 只为旧机类别填充数据
            if '类别' in manual_data.columns and '非限制使用的库存' in manual_data.columns:
                mask_old_machine = manual_data['类别'] == '旧机'
                
                # 初始数据 = 非限制使用的库存
                inventory_values = pd.to_numeric(manual_data.loc[mask_old_machine, '非限制使用的库存'], errors='coerce').fillna(0)
                manual_data.loc[mask_old_machine, '初始数据'] = inventory_values
                
                # 本期计划投产数量 = 初始数据
                manual_data.loc[mask_old_machine, '本期计划投产数量'] = manual_data.loc[mask_old_machine, '初始数据']
                
                # 计划采购单价 = 单价（从Excel表内的单价列复制）
                if '单价' in manual_data.columns:
                    price_values = pd.to_numeric(manual_data.loc[mask_old_machine, '单价'], errors='coerce').fillna(0)
                    manual_data.loc[mask_old_machine, '计划采购单价'] = price_values
            
            # 重新排列列顺序
            cols = list(manual_data.columns)
            if '非限制使用的库存' in cols:
                insert_pos = cols.index('非限制使用的库存') + 1
                new_cols = [c for c in cols if c not in ['初始数据', '本期计划采购数量', '计划采购单价', '本期计划投产数量']]
                new_cols.insert(insert_pos, '初始数据')
                new_cols.insert(insert_pos + 1, '本期计划投产数量')
                new_cols.insert(insert_pos + 2, '本期计划采购数量')
                new_cols.insert(insert_pos + 3, '计划采购单价')
                manual_data = manual_data[new_cols]
            
            # 保存完整的手工数据（包含所有类别）
            self.app_data.set_data('extracted_data_manual', manual_data)
            self.app_data.set_data('original_extracted_data', readonly_data.copy())
            self.app_data.set_data('extracted_data_modified', False)
            self.app_data.set_data('extracted_modification_timestamp', datetime.now().isoformat())
            
            print(f"[成本预测初始化] 提取结果手工数据初始化成功: {len(manual_data)} 条记录")
            return True
            
        except Exception as e:
            print(f"⚠️ 成本预测数据初始化失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _get_prediction_period(self):
        """获取当前预测期数（与成本页 API 一致）"""
        prediction_period = 1
        try:
            from flask import session
            session_prediction_period = session.get('prediction_period')
            if session_prediction_period:
                prediction_period = int(session_prediction_period)
        except Exception:
            pass
        return prediction_period

    def refresh_cost_calculation_caches(self):
        """全局重算后刷新成本计算页会话缓存（失败不阻断主流程）"""
        prediction_period = self._get_prediction_period()
        try:
            from app.api.cost_forecast_api import (
                calculate_screen_cost_allocation,
                calculate_production_cost_allocation,
                calculate_disassembly_product_cost,
                calculate_deep_processing_product_cost,
            )

            screen_result = calculate_screen_cost_allocation(self.app_data, prediction_period)
            if screen_result is not None:
                self.app_data.set_data(
                    f'screen_cost_allocation_result_v2_{prediction_period}',
                    screen_result,
                )
                print(f"[成本缓存] 屏成本分摊已刷新: period={prediction_period}")

            production_result = calculate_production_cost_allocation(
                self.app_data, prediction_period
            )
            self.app_data.set_data(
                f'production_cost_allocation_result_v2_{prediction_period}',
                production_result,
            )
            print(
                f"[成本缓存] 生产成本分摊已刷新: {len(production_result or [])} 条, period={prediction_period}"
            )

            disassembly_result = calculate_disassembly_product_cost(
                self.app_data, prediction_period
            )
            self.app_data.set_data(
                f'disassembly_product_cost_result_v2_{prediction_period}',
                disassembly_result,
            )
            print(
                f"[成本缓存] 一次拆解产物成本已刷新: {len(disassembly_result or [])} 条, period={prediction_period}"
            )

            deep_result = calculate_deep_processing_product_cost(
                self.app_data, prediction_period
            )
            self.app_data.set_data(
                f'deep_processing_product_cost_result_v1_{prediction_period}',
                deep_result,
            )
            print(
                f"[成本缓存] 深加工产物成本已刷新: {len(deep_result or [])} 条, period={prediction_period}"
            )
            return True
        except Exception as e:
            print(f"⚠️ 成本计算页缓存刷新失败（不阻断主流程）: {e}")
            import traceback
            traceback.print_exc()
            return False

    def calculate_cost_forecast(self):
        """计算成本预测（拆解物原料成本和生产工人计件工资）"""
        try:
            # 获取手工数据
            manual_data = self.app_data.get_data('extracted_data_manual')
            if manual_data is None or manual_data.empty:
                print("⚠️ 没有提取结果手工数据，跳过成本预测计算")
                return True  # 不是错误，只是没有数据
            
            # 计算拆解物原料成本
            from app.api.cost_forecast_api import calculate_material_cost
            cost_data = calculate_material_cost(manual_data)
            self.app_data.set_data('cost_forecast_data', cost_data)
            print(f"[成本预测计算] 拆解物原料成本计算完成: {len(cost_data)} 条记录")
            
            # 计算生产工人计件工资（会自动计算，不需要额外步骤）
            # calculate_piece_rate_wage 会在API调用时自动计算
            print("[成本预测计算] 成本预测计算完成")
            return True
            
        except Exception as e:
            print(f"⚠️ 成本预测计算失败: {e}")
            import traceback
            traceback.print_exc()
            return False 