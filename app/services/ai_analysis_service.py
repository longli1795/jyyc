"""
AI分析服务模块
用于调用AI大模型进行利润测算汇总表分析
"""

import json
import urllib.request
import urllib.error
import socket
from typing import Dict, Optional, Tuple, List
from flask import current_app


class AIAnalysisService:
    """AI分析服务类"""
    
    def __init__(self):
        """初始化AI分析服务"""
        self.base_url = current_app.config.get('AI_MODEL_BASE_URL', 'http://10.30.5.83:1234')
        self.model_name = current_app.config.get('AI_MODEL_NAME', '')
        self.timeout = current_app.config.get('AI_REQUEST_TIMEOUT', 60)
        self.max_tokens = current_app.config.get('AI_MAX_TOKENS', 4000)  # 最大生成token数
        self.api_endpoint = f"{self.base_url}/v1/chat/completions"
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词（长虹格润资深运营策略师角色）"""
        # 获取当前日期和时间信息
        from datetime import datetime
        current_date = datetime.now().strftime('%Y年%m月%d日')
        current_year = datetime.now().year
        current_month = datetime.now().month
        current_quarter = (current_month - 1) // 3 + 1
        
        # 计算未来季度示例
        def calc_future_quarter(months_ahead):
            future_month = current_month + months_ahead
            future_year = current_year
            if future_month > 12:
                future_year += (future_month - 1) // 12
                future_month = ((future_month - 1) % 12) + 1
            future_quarter = (future_month - 1) // 3 + 1
            return f"{future_year}Q{future_quarter}"
        
        q1_3 = calc_future_quarter(2)  # 1-3个月后
        q4_6 = calc_future_quarter(5)  # 4-6个月后
        q7_12 = calc_future_quarter(9)  # 7-12个月后
        
        return f"""你是长虹格润的资深运营策略师，具有以下特征：

**重要时间信息（请严格遵守）**
- 当前日期：{current_date}
- 当前年份：{current_year}年
- 当前季度：{current_year}年第{current_quarter}季度
- **请务必基于以上真实时间信息制定时间计划和行动方案**
- **绝对不要使用2024年或更早的时间作为未来计划的时间节点**
- 制定行动计划时的时间参考示例：
  * 1-3个月后：约{q1_3}（{current_year}年第{current_quarter + 1 if current_quarter < 4 else 1}季度或{current_year + 1 if current_quarter == 4 else current_year}年）
  * 4-6个月后：约{q4_6}（{current_year}年第{current_quarter + 2 if current_quarter <= 2 else (current_quarter - 2) if current_quarter > 2 else 1}季度或{current_year + 1 if current_quarter >= 3 else current_year}年）
  * 7-12个月后：约{q7_12}（{current_year + 1}年第1季度或更晚）

**角色定位**
- 身份：长虹格润资深运营策略师
- 性格类型：INTJ（内向直觉思维判断型）
- 专业领域：电子废弃物拆解处理企业的运营策略优化、成本控制、效率提升
- 工作风格：理性、专业、务实，注重数据驱动的决策
- 企业背景：深度了解长虹格润的业务模式、运营流程和行业特点

**核心能力**
1. 深入分析电子废弃物拆解处理企业的运营流程、市场环境、竞争对手
2. 制定和优化运营策略的创意思维和战略规划能力
3. 数据分析和市场调研的专业技能
4. 高效沟通和协调团队合作的能力
5. 熟悉"四机一脑"（冰箱、空调、电脑、电视、洗衣机）拆解业务特点

**分析原则**
- 以长虹格润的长远发展为中心，关注企业可持续经营
- 追求卓越，不断创新和优化运营策略
- 注重团队合作，共同实现企业目标
- 基于充分的数据分析提供切实可行的建议
- 结合电子废弃物处理行业特点，提供专业建议

**工作流程**
1. 收集长虹格润的运营数据和市场信息，进行初步分析
2. 深入了解企业的发展战略和核心价值，明确优化目标
3. 分析运营流程中存在的问题和改进空间，提出初步建议
4. 制定详细的运营策略方案，包括流程优化、成本控制、效率提升等方面
5. 提供可执行的运营策略建议，特别关注拆解业务、成本分摊、基金补贴等关键环节

**专业背景**
- 熟悉电子废弃物拆解处理行业政策法规
- 了解基金补贴机制和成本分摊方法
- 掌握"四机一脑"拆解业务运营特点
- 具备财务分析和运营优化的专业能力

请以长虹格润资深运营策略师的身份，用专业、理性、务实的方式分析企业运营数据，提供有针对性的运营改进建议。

**数据访问能力**
- 你可以访问长虹格润的所有页面数据，包括但不限于：
  * 利润测算汇总表数据（营业收入、成本、毛利、期间费用、税金及附加、营业利润等）
  * 统计数据汇总（各数据节点的记录数、重量、分类统计等）
  * 业务数据（源数据、提取数据、拆解数据、被减扣数据、计算后数据、深加工数据、可销售量数据等）
  * 基础数据（映射表、产品拆解系数、人工成本、制造费用等）
- 在回答问题时，可以基于这些数据进行综合分析，提供全面的运营策略建议

**时间计划特别提醒**
- 当前真实日期是：{current_date}（{current_year}年第{current_quarter}季度）
- 制定任何时间计划时，必须基于当前真实日期计算未来时间节点
- 绝对不要使用2024年、2023年等过去的时间作为未来计划的时间
- 如果提到"第一阶段"、"第二阶段"等，请使用{current_year}年或{current_year + 1}年的具体季度
- 例如：第一阶段（1-3个月）应该是{q1_3}，而不是2024Q3或2024Q4"""
    
    def _collect_all_page_data(self, app_data) -> Dict:
        """
        收集所有页面的数据
        
        Args:
            app_data: 应用数据管理器实例
            
        Returns:
            Dict: 包含所有页面数据的字典
        """
        all_data = {}
        
        try:
            # 1. 利润测算汇总表数据（如果存在）
            try:
                from flask import request
                from app.api.cost_forecast_api import (
                    calculate_disassembly_product_cost,
                    calculate_deep_processing_product_cost,
                    get_production_cost_allocation,
                    calculate_period_cost
                )
                # 尝试获取利润测算汇总表数据
                prediction_period = int(request.args.get('prediction_period', 1)) if request else 1
                # 这里不实际调用，因为需要参数，在API层处理
            except:
                pass
            
            # 2. 统计数据汇总（直接实现统计逻辑）
            try:
                import pandas as pd
                
                # 数据类型映射
                data_mapping = {
                    'extracted': 'extracted_data',
                    'extracted_manual': 'extracted_data_manual',
                    'original': 'disassembly_data',
                    'final': 'calculated_data',
                    'deducted': 'deducted_data_manual',
                    'deducted_manual': 'deducted_data_manual',
                    'deep_original': 'deep_processing_data',
                    'saleable': 'saleable_data',
                    'saleable_manual': 'saleable_data_manual'
                }
                
                # 基础数据类型
                data_types = ['extracted', 'original', 'final', 'deducted', 'deep_original', 'saleable']
                
                # 如果提取数据被修改过，则增加手工节点
                if app_data.get_data('extracted_data_modified'):
                    data_types.insert(1, 'extracted_manual')
                
                # 如果被减扣数据被修改过，则增加手工节点
                if app_data.get_data('deducted_data_modified'):
                    data_types.insert(data_types.index('deducted') + 1 if 'deducted' in data_types else 4, 'deducted_manual')
                
                # 如果可销售量数据被修改过，则增加手工节点
                if app_data.get_data('saleable_data_modified'):
                    data_types.append('saleable_manual')
                
                summary = {}
                categories = ['冰箱', '空调', '电脑', '电视', '洗衣机']
                
                # 重量列映射（与statistics_api.py保持一致）
                weight_column_mapping = {
                    'extracted': '非限制使用的库存',
                    'extracted_manual': '非限制使用的库存',
                    'original': '计算结果(KG)',
                    'final': '计算结果(KG)',
                    'deducted': '计算结果(KG)',
                    'deducted_manual': '计算结果(KG)',
                    'deep_original': '深加工结果(KG)',
                    'saleable': '计算结果(KG)',
                    'saleable_manual': '计算结果(KG)'
                }
                
                for data_type in data_types:
                    try:
                        actual_key = data_mapping.get(data_type, data_type + '_data')
                        weight_column = weight_column_mapping.get(data_type, '重量')
                        df = app_data.get_data(actual_key)
                        
                        if df is not None and not df.empty:
                            total_records = len(df)
                            total_weight = 0.0
                            category_stats = []
                            
                            # 计算总重量（使用正确的列名）
                            if weight_column in df.columns:
                                weight_numeric = pd.to_numeric(df[weight_column], errors='coerce')
                                total_weight = float(weight_numeric.fillna(0).sum())
                            elif '重量' in df.columns:
                                weight_numeric = pd.to_numeric(df['重量'], errors='coerce')
                                total_weight = float(weight_numeric.fillna(0).sum())
                            
                            # 按类别统计
                            if '类别' in df.columns:
                                for category in categories:
                                    category_df = df[df['类别'] == category]
                                    if not category_df.empty:
                                        cat_weight = 0.0
                                        if weight_column in category_df.columns:
                                            cat_weight = float(pd.to_numeric(category_df[weight_column], errors='coerce').fillna(0).sum())
                                        elif '重量' in category_df.columns:
                                            cat_weight = float(pd.to_numeric(category_df['重量'], errors='coerce').fillna(0).sum())
                                        
                                        category_stats.append({
                                            'category': category,
                                            'count': len(category_df),
                                            'weight': round(cat_weight, 2)
                                        })
                            
                            summary[data_type] = {
                                'total_records': total_records,
                                'total_weight': round(total_weight, 2),
                                'categories': category_stats
                            }
                        else:
                            summary[data_type] = {
                                'total_records': 0,
                                'total_weight': 0.0,
                                'categories': []
                            }
                    except Exception as e:
                        current_app.logger.warning(f"获取{data_type}统计失败: {str(e)}")
                        summary[data_type] = {
                            'total_records': 0,
                            'total_weight': 0.0,
                            'categories': []
                        }
                
                # 计算总收益统计
                try:
                    # 销售收益从可销售量数据中获取
                    revenue_data = None
                    if app_data.get_data('saleable_data_modified'):
                        revenue_data = app_data.get_data('saleable_data_manual')
                    if revenue_data is None or revenue_data.empty:
                        revenue_data = app_data.get_data('saleable_data')
                    
                    total_sales_revenue = 0.0
                    if revenue_data is not None and not revenue_data.empty:
                        if '销售收益(元)' in revenue_data.columns:
                            total_sales_revenue = float(pd.to_numeric(revenue_data['销售收益(元)'], errors='coerce').fillna(0).sum())
                        elif '销售收益' in revenue_data.columns:
                            total_sales_revenue = float(pd.to_numeric(revenue_data['销售收益'], errors='coerce').fillna(0).sum())
                    
                    # 基金补贴收入从独立的 subsidy_income_data 中获取
                    subsidy_income_data = app_data.get_data('subsidy_income_data')
                    total_subsidy_income = 0.0
                    if subsidy_income_data is not None and not subsidy_income_data.empty:
                        if '基金补贴收入(元)' in subsidy_income_data.columns:
                            total_subsidy_income = float(pd.to_numeric(subsidy_income_data['基金补贴收入(元)'], errors='coerce').fillna(0).sum())
                    
                    # 总收益 = 销售收益 + 基金补贴收入
                    total_revenue = total_sales_revenue + total_subsidy_income
                    summary['total_revenue'] = {
                        'sales_revenue': round(total_sales_revenue, 2),
                        'subsidy_income': round(total_subsidy_income, 2),
                        'total': round(total_revenue, 2),
                        'sales_percentage': round((total_sales_revenue / total_revenue * 100) if total_revenue > 0 else 0, 2),
                        'subsidy_percentage': round((total_subsidy_income / total_revenue * 100) if total_revenue > 0 else 0, 2)
                    }
                except Exception as e:
                    current_app.logger.warning(f"计算总收益统计失败: {str(e)}")
                    summary['total_revenue'] = {
                        'sales_revenue': 0.0,
                        'subsidy_income': 0.0,
                        'total': 0.0,
                        'sales_percentage': 0.0,
                        'subsidy_percentage': 0.0
                    }
                
                if summary:
                    all_data['statistics_summary'] = summary
            except Exception as e:
                current_app.logger.warning(f"获取统计数据失败: {str(e)}")
                import traceback
                traceback.print_exc()
            
            # 3. 业务数据（从app_data获取）
            data_keys = [
                'source_data',           # 源数据
                'extracted_data',        # 提取数据
                'extracted_data_manual', # 手工提取数据
                'disassembly_data',      # 拆解数据
                'deducted_data_manual',  # 被减扣数据
                'calculated_data',       # 计算后数据
                'deep_processing_data',  # 深加工数据
                'saleable_data',         # 可销售量数据
                'saleable_data_manual'   # 手工可销售量数据
            ]
            
            for key in data_keys:
                try:
                    df = app_data.get_data(key)
                    if df is not None and not df.empty:
                        # 只保存统计信息，避免数据过大
                        all_data[key] = {
                            'record_count': len(df),
                            'columns': list(df.columns),
                            'sample_data': df.head(5).to_dict('records') if len(df) > 0 else []
                        }
                        # 如果有重量列，计算总重量
                        if '重量' in df.columns:
                            total_weight = df['重量'].fillna(0).sum()
                            all_data[key]['total_weight'] = float(total_weight)
                        # 如果有类别列，统计各类别数量
                        if '类别' in df.columns:
                            category_stats = df['类别'].value_counts().to_dict()
                            all_data[key]['category_stats'] = {str(k): int(v) for k, v in category_stats.items()}
                except Exception as e:
                    current_app.logger.warning(f"获取{key}数据失败: {str(e)}")
            
            # 4. 基础数据（产品、映射、人工成本、制造费用等）
            try:
                from data.base_data.mapping_data import get_mapping_dataframe
                mapping_df = get_mapping_dataframe()
                if mapping_df is not None and not mapping_df.empty:
                    all_data['mapping_data'] = {
                        'record_count': len(mapping_df),
                        'columns': list(mapping_df.columns)
                    }
            except Exception as e:
                current_app.logger.warning(f"获取映射数据失败: {str(e)}")
            
            try:
                from data.base_data.product_data import PRODUCT_DISASSEMBLY_DATA
                if PRODUCT_DISASSEMBLY_DATA:
                    all_data['product_data'] = {
                        'product_count': len(PRODUCT_DISASSEMBLY_DATA)
                    }
            except Exception as e:
                current_app.logger.warning(f"获取产品数据失败: {str(e)}")
            
            try:
                from app.api.data_management_api import get_labor_cost_dataframe
                labor_cost_df = get_labor_cost_dataframe()
                if labor_cost_df is not None and not labor_cost_df.empty:
                    all_data['labor_cost_data'] = {
                        'record_count': len(labor_cost_df),
                        'columns': list(labor_cost_df.columns)
                    }
            except Exception as e:
                current_app.logger.warning(f"获取人工成本数据失败: {str(e)}")
            
            try:
                from app.api.data_management_api import get_manufacturing_cost_dataframe
                manufacturing_cost_df = get_manufacturing_cost_dataframe()
                if manufacturing_cost_df is not None and not manufacturing_cost_df.empty:
                    all_data['manufacturing_cost_data'] = {
                        'record_count': len(manufacturing_cost_df),
                        'columns': list(manufacturing_cost_df.columns)
                    }
            except Exception as e:
                current_app.logger.warning(f"获取制造费用数据失败: {str(e)}")
                
        except Exception as e:
            current_app.logger.error(f"收集所有页面数据时出错: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return all_data
    
    def _format_all_data_for_context(self, all_data: Dict, profit_data: Optional[Dict] = None) -> str:
        """
        格式化所有数据为AI可理解的文本格式
        
        Args:
            all_data: 所有页面数据的字典
            profit_data: 可选的利润测算汇总表数据（优先使用）
            
        Returns:
            str: 格式化后的文本
        """
        lines = []
        lines.append("=" * 80)
        lines.append("长虹格润运营数据概览")
        lines.append("=" * 80)
        lines.append("")
        
        # 1. 利润测算汇总表数据（优先）
        if profit_data:
            profit_text = self._format_profit_data(profit_data)
            lines.append(profit_text)
            lines.append("")
        
        # 2. 统计数据汇总
        if 'statistics_summary' in all_data:
            summary = all_data['statistics_summary']
            lines.append("【统计数据汇总】")
            
            # 各数据节点统计
            data_type_names = {
                'extracted': '提取数据',
                'extracted_manual': '手工提取数据',
                'original': '拆解数据',
                'final': '计算后数据',
                'deducted': '被减扣数据',
                'deducted_manual': '手工被减扣数据',
                'deep_original': '深加工数据',
                'saleable': '可销售量数据',
                'saleable_manual': '手工可销售量数据'
            }
            
            for key, name in data_type_names.items():
                if key in summary:
                    stats = summary[key]
                    lines.append(f"  {name}:")
                    lines.append(f"    - 记录数: {stats.get('total_records', 0)}")
                    lines.append(f"    - 总重量: {stats.get('total_weight', 0):,.2f} 公斤")
                    if stats.get('categories'):
                        lines.append(f"    - 分类统计:")
                        for cat in stats['categories']:
                            lines.append(f"      * {cat.get('category', '')}: {cat.get('weight', 0):,.2f} 公斤 ({cat.get('count', 0)} 条)")
            
            # 总收益统计
            if 'total_revenue' in summary:
                revenue = summary['total_revenue']
                lines.append("  【总收益统计】")
                lines.append(f"    - 销售收益: {revenue.get('sales_revenue', 0):,.2f} 元 ({revenue.get('sales_percentage', 0):.2f}%)")
                lines.append(f"    - 基金补贴收入: {revenue.get('subsidy_income', 0):,.2f} 元 ({revenue.get('subsidy_percentage', 0):.2f}%)")
                lines.append(f"    - 总收益: {revenue.get('total', 0):,.2f} 元")
            lines.append("")
        
        # 3. 业务数据详情
        business_data_keys = [
            ('source_data', '源数据'),
            ('extracted_data', '提取数据'),
            ('extracted_data_manual', '手工提取数据'),
            ('disassembly_data', '拆解数据'),
            ('deducted_data_manual', '被减扣数据'),
            ('calculated_data', '计算后数据'),
            ('deep_processing_data', '深加工数据'),
            ('saleable_data', '可销售量数据'),
            ('saleable_data_manual', '手工可销售量数据')
        ]
        
        has_business_data = False
        for key, name in business_data_keys:
            if key in all_data:
                has_business_data = True
                break
        
        if has_business_data:
            lines.append("【业务数据详情】")
            for key, name in business_data_keys:
                if key in all_data:
                    data_info = all_data[key]
                    lines.append(f"  {name}:")
                    lines.append(f"    - 记录数: {data_info.get('record_count', 0)}")
                    if 'total_weight' in data_info:
                        lines.append(f"    - 总重量: {data_info['total_weight']:,.2f} 公斤")
                    if 'category_stats' in data_info:
                        lines.append(f"    - 分类统计:")
                        for cat, count in data_info['category_stats'].items():
                            lines.append(f"      * {cat}: {count} 条")
                    if 'columns' in data_info:
                        lines.append(f"    - 数据列: {', '.join(data_info['columns'][:10])}{'...' if len(data_info['columns']) > 10 else ''}")
            lines.append("")
        
        # 4. 基础数据
        if 'mapping_data' in all_data:
            lines.append("【基础数据】")
            mapping = all_data['mapping_data']
            lines.append(f"  - 映射表数据: {mapping.get('record_count', 0)} 条记录")
        
        if 'product_data' in all_data:
            product = all_data['product_data']
            lines.append(f"  - 产品拆解系数数据: {product.get('product_count', 0)} 个产品")
        
        if 'labor_cost_data' in all_data:
            labor = all_data['labor_cost_data']
            lines.append(f"  - 人工成本数据: {labor.get('record_count', 0)} 条记录")
        
        if 'manufacturing_cost_data' in all_data:
            manufacturing = all_data['manufacturing_cost_data']
            lines.append(f"  - 制造费用数据: {manufacturing.get('record_count', 0)} 条记录")
        
        if any(key in all_data for key in ['mapping_data', 'product_data', 'labor_cost_data', 'manufacturing_cost_data']):
            lines.append("")
        
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def _format_profit_data(self, data: Dict) -> str:
        """格式化利润测算汇总表数据为易读文本"""
        categories = ['冰箱', '空调', '电脑', '电视', '洗衣机']
        
        # 计算各项指标
        calculated = {
            'revenue': {},      # 营业收入
            'cost': {},         # 营业成本
            'gross_profit': {}, # 项目毛利
            'gross_profit_margin': {}, # 项目毛利率
            'operating_profit': {} # 营业利润
        }
        
        # 计算各分类的指标
        for category in categories:
            # 营业收入 = 产物销售收入 + 基金补贴收入
            product_sales_revenue = data.get('product_sales_revenue', {}).get(category, 0) or 0
            subsidy_income = data.get('subsidy_income', {}).get(category, 0) or 0
            calculated['revenue'][category] = product_sales_revenue + subsidy_income
            
            # 营业成本 = 产物销售成本 + 基金补贴成本
            product_sales_cost = data.get('product_sales_cost', {}).get(category, 0) or 0
            subsidy_cost = data.get('subsidy_cost', {}).get(category, 0) or 0
            calculated['cost'][category] = product_sales_cost + subsidy_cost
            
            # 项目毛利 = 营业收入 - 营业成本
            calculated['gross_profit'][category] = calculated['revenue'][category] - calculated['cost'][category]
            
            # 项目毛利率 = 项目毛利 / 营业收入
            if calculated['revenue'][category] > 0:
                calculated['gross_profit_margin'][category] = (
                    calculated['gross_profit'][category] / calculated['revenue'][category] * 100
                )
            else:
                calculated['gross_profit_margin'][category] = 0
            
            # 营业利润 = 项目毛利 - 期间费用 - 税金及附加
            period_cost = data.get('period_cost', {}).get(category, 0) or 0
            tax_surcharge = data.get('tax_surcharge', {}).get(category, 0) or 0
            calculated['operating_profit'][category] = (
                calculated['gross_profit'][category] - period_cost - tax_surcharge
            )
        
        # 计算小计
        totals = {
            'product_sales_revenue': sum(data.get('product_sales_revenue', {}).get(cat, 0) or 0 for cat in categories),
            'subsidy_income': sum(data.get('subsidy_income', {}).get(cat, 0) or 0 for cat in categories),
            'revenue': sum(calculated['revenue'][cat] for cat in categories),
            'product_sales_cost': sum(data.get('product_sales_cost', {}).get(cat, 0) or 0 for cat in categories),
            'subsidy_cost': sum(data.get('subsidy_cost', {}).get(cat, 0) or 0 for cat in categories),
            'cost': sum(calculated['cost'][cat] for cat in categories),
            'gross_profit': sum(calculated['gross_profit'][cat] for cat in categories),
            'period_cost': sum(data.get('period_cost', {}).get(cat, 0) or 0 for cat in categories),
            'tax_surcharge': sum(data.get('tax_surcharge', {}).get(cat, 0) or 0 for cat in categories),
            'operating_profit': sum(calculated['operating_profit'][cat] for cat in categories)
        }
        
        if totals['revenue'] > 0:
            totals['gross_profit_margin'] = (totals['gross_profit'] / totals['revenue']) * 100
        else:
            totals['gross_profit_margin'] = 0
        
        # 格式化数字
        def format_number(value):
            if value is None or value == '':
                return '0.00'
            try:
                return f"{float(value):,.2f}"
            except:
                return str(value)
        
        # 构建文本格式
        lines = []
        lines.append("=" * 80)
        lines.append("利润测算汇总表数据")
        lines.append("=" * 80)
        lines.append("")
        
        # 各分类详细数据
        for category in categories:
            lines.append(f"【{category}】")
            lines.append(f"  1.1 产物销售收入: {format_number(data.get('product_sales_revenue', {}).get(category, 0))} 元")
            lines.append(f"  1.2 基金补贴收入: {format_number(data.get('subsidy_income', {}).get(category, 0))} 元")
            lines.append(f"  1. 营业收入: {format_number(calculated['revenue'][category])} 元")
            lines.append(f"  2.1 产物销售成本: {format_number(data.get('product_sales_cost', {}).get(category, 0))} 元")
            lines.append(f"  2.2 基金补贴成本: {format_number(data.get('subsidy_cost', {}).get(category, 0))} 元")
            lines.append(f"  2. 营业成本: {format_number(calculated['cost'][category])} 元")
            lines.append(f"  3. 项目毛利: {format_number(calculated['gross_profit'][category])} 元")
            lines.append(f"  4. 项目毛利率: {calculated['gross_profit_margin'][category]:.2f}%")
            lines.append(f"  5. 期间费用: {format_number(data.get('period_cost', {}).get(category, 0))} 元")
            lines.append(f"  6. 税金及附加: {format_number(data.get('tax_surcharge', {}).get(category, 0))} 元")
            lines.append(f"  7. 营业利润: {format_number(calculated['operating_profit'][category])} 元")
            lines.append("")
        
        # 小计
        lines.append("【合计】")
        lines.append(f"  1.1 产物销售收入: {format_number(totals['product_sales_revenue'])} 元")
        lines.append(f"  1.2 基金补贴收入: {format_number(totals['subsidy_income'])} 元")
        lines.append(f"  1. 营业收入: {format_number(totals['revenue'])} 元")
        lines.append(f"  2.1 产物销售成本: {format_number(totals['product_sales_cost'])} 元")
        lines.append(f"  2.2 基金补贴成本: {format_number(totals['subsidy_cost'])} 元")
        lines.append(f"  2. 营业成本: {format_number(totals['cost'])} 元")
        lines.append(f"  3. 项目毛利: {format_number(totals['gross_profit'])} 元")
        lines.append(f"  4. 项目毛利率: {totals['gross_profit_margin']:.2f}%")
        lines.append(f"  5. 期间费用: {format_number(totals['period_cost'])} 元")
        lines.append(f"  6. 税金及附加: {format_number(totals['tax_surcharge'])} 元")
        lines.append(f"  7. 营业利润: {format_number(totals['operating_profit'])} 元")
        lines.append("")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def _build_user_prompt(self, data: Dict) -> str:
        """构建用户提示词"""
        formatted_data = self._format_profit_data(data)
        
        # 获取当前时间信息
        from datetime import datetime
        current_date = datetime.now().strftime('%Y年%m月%d日')
        current_year = datetime.now().year
        current_quarter = (datetime.now().month - 1) // 3 + 1
        
        return f"""请基于以下利润测算汇总表数据，进行深入的运营策略分析：

**当前时间信息**：{current_date}（{current_year}年第{current_quarter}季度）
**重要提醒**：制定行动计划时，请使用当前真实日期作为基准，不要使用2024年或更早的时间。

{formatted_data}

请从以下维度进行分析：

1. **营业收入结构分析**
   - 产物销售收入与基金补贴收入的占比关系
   - 各分类（冰箱、空调、电脑、电视、洗衣机）的收入分布
   - 收入结构的合理性和优化空间

2. **成本结构分析**
   - 产物销售成本与基金补贴成本的构成
   - 各分类的成本占比和成本控制情况
   - 成本结构的优化建议

3. **毛利率分析**
   - 各分类的毛利率对比分析
   - 毛利率差异的原因分析
   - 提升毛利率的策略建议

4. **期间费用分析**
   - 期间费用的分摊合理性
   - 费用占比和费用控制情况
   - 费用优化的具体建议

5. **税金及附加分析**
   - 各分类税金及附加的分布情况
   - 与营业收入、产值分摊的匹配性
   - 税费控制与优化建议

6. **营业利润分析**
   - 各分类的盈利能力评估
   - 利润贡献度分析
   - 盈利能力提升策略

7. **运营优化建议**
   - 基于数据分析的具体运营改进建议
   - 流程优化、成本控制、效率提升等方面的建议
   - 可执行的行动计划

请以专业、理性、务实的方式提供分析，重点关注可执行的运营策略建议。"""
    
    def analyze_profit_summary(self, data: Dict) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        分析利润测算汇总表数据
        
        Args:
            data: 利润测算汇总表数据字典
            
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: (成功标志, 分析结果, 错误信息)
        """
        try:
            # 构建请求数据
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(data)
            
            # 如果模型名称为空，使用空字符串让API使用默认模型
            # 某些OpenAI兼容API支持不指定模型名称，会自动使用默认模型
            model = self.model_name if self.model_name else ""
            
            # 如果模型名称为空字符串，尝试使用常见的默认模型名称
            # 这取决于具体的API实现，如果API不支持空模型名，可以在这里设置默认值
            if not model:
                # 对于大多数OpenAI兼容API，可以尝试这些常见的模型名称
                # 如果API返回错误，用户可以通过环境变量配置正确的模型名称
                model = "gpt-3.5-turbo"
            
            request_data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": self.max_tokens
            }
            
            # 准备HTTP请求
            json_data = json.dumps(request_data).encode('utf-8')
            req = urllib.request.Request(
                self.api_endpoint,
                data=json_data,
                headers={
                    'Content-Type': 'application/json',
                    'Content-Length': str(len(json_data))
                },
                method='POST'
            )
            
            # 发送请求
            try:
                # urllib.request.urlopen的timeout参数会同时设置连接超时和读取超时
                # 对于大模型，处理时间可能较长，所以超时时间已设置为180秒（可在配置中调整）
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    response_data = json.loads(response.read().decode('utf-8'))
                    
                    # 检查响应格式
                    if 'choices' in response_data and len(response_data['choices']) > 0:
                        analysis_result = response_data['choices'][0]['message']['content']
                        return True, analysis_result, None
                    elif 'error' in response_data:
                        error_msg = response_data['error'].get('message', '未知错误')
                        return False, None, f"AI模型返回错误: {error_msg}"
                    else:
                        return False, None, f"AI模型返回格式异常: {str(response_data)}"
                        
            except socket.timeout:
                return False, None, f"请求超时（{self.timeout}秒）。AI模型处理时间较长，请稍后重试或增加超时时间设置。"
            except urllib.error.HTTPError as e:
                error_body = ''
                try:
                    if e.fp:
                        error_body = e.read().decode('utf-8')
                except:
                    pass
                if not error_body:
                    error_body = '无错误详情'
                return False, None, f"HTTP错误 {e.code}: {error_body}"
            except urllib.error.URLError as e:
                error_msg = str(e)
                if 'timed out' in error_msg.lower() or 'timeout' in error_msg.lower():
                    return False, None, f"请求超时（{self.timeout}秒）。AI模型处理时间较长，请稍后重试或增加超时时间设置。"
                return False, None, f"网络连接错误: {error_msg}"
            except TimeoutError as e:
                return False, None, f"请求超时（{self.timeout}秒）。AI模型处理时间较长，请稍后重试或增加超时时间设置。"
            except Exception as e:
                error_msg = str(e)
                if 'timed out' in error_msg.lower() or 'timeout' in error_msg.lower():
                    return False, None, f"请求超时（{self.timeout}秒）。AI模型处理时间较长，请稍后重试或增加超时时间设置。"
                return False, None, f"请求处理错误: {error_msg}"
                
        except Exception as e:
            current_app.logger.error(f"AI分析服务错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return False, None, f"分析服务内部错误: {str(e)}"
    
    def chat_with_ai(self, messages: list, profit_data: Optional[Dict] = None, all_page_data: Optional[Dict] = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        与AI进行对话（支持多轮对话）
        
        Args:
            messages: 对话消息列表，格式为 [{"role": "user", "content": "..."}, ...]
            profit_data: 可选的利润测算汇总表数据，用于提供上下文
            all_page_data: 可选的所有页面数据，用于提供完整上下文
            
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: (成功标志, AI回复, 错误信息)
        """
        try:
            # 构建系统提示词
            system_prompt = self._build_system_prompt()
            
            # 添加数据上下文
            data_context_parts = []
            
            # 如果提供了所有页面数据，格式化并添加
            if all_page_data:
                data_context = self._format_all_data_for_context(all_page_data, profit_data)
                data_context_parts.append(data_context)
            # 如果只提供了利润数据，使用旧的格式
            elif profit_data:
                data_context = self._format_profit_data(profit_data)
                data_context_parts.append(f"**当前利润测算汇总表数据**（供参考）：\n{data_context}")
            
            # 如果有数据上下文，添加到系统提示中
            if data_context_parts:
                system_prompt += "\n\n**当前运营数据**（供参考）：\n" + "\n".join(data_context_parts)
                system_prompt += "\n\n**重要说明**：你可以基于以上所有数据进行问答分析，包括利润测算汇总表、统计数据、业务数据等。"
            
            # 构建消息列表
            chat_messages = [{"role": "system", "content": system_prompt}]
            
            # 添加历史对话消息
            chat_messages.extend(messages)
            
            # 如果模型名称为空，使用默认模型
            model = self.model_name if self.model_name else "gpt-3.5-turbo"
            
            request_data = {
                "model": model,
                "messages": chat_messages,
                "temperature": 0.7,
                "max_tokens": self.max_tokens
            }
            
            # 准备HTTP请求
            json_data = json.dumps(request_data, ensure_ascii=False).encode('utf-8')
            req = urllib.request.Request(
                self.api_endpoint,
                data=json_data,
                headers={
                    'Content-Type': 'application/json',
                    'Content-Length': str(len(json_data))
                },
                method='POST'
            )
            
            # 发送请求
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    response_data = json.loads(response.read().decode('utf-8'))
                    
                    # 检查响应格式
                    if 'choices' in response_data and len(response_data['choices']) > 0:
                        ai_reply = response_data['choices'][0]['message']['content']
                        return True, ai_reply, None
                    elif 'error' in response_data:
                        error_msg = response_data['error'].get('message', '未知错误')
                        return False, None, f"AI模型返回错误: {error_msg}"
                    else:
                        return False, None, f"AI模型返回格式异常: {str(response_data)}"
                        
            except socket.timeout:
                return False, None, f"请求超时（{self.timeout}秒）。AI模型处理时间较长，请稍后重试或增加超时时间设置。"
            except urllib.error.HTTPError as e:
                error_body = ''
                try:
                    if e.fp:
                        error_body = e.read().decode('utf-8')
                except:
                    pass
                if not error_body:
                    error_body = '无错误详情'
                return False, None, f"HTTP错误 {e.code}: {error_body}"
            except urllib.error.URLError as e:
                error_msg = str(e)
                if 'timed out' in error_msg.lower() or 'timeout' in error_msg.lower():
                    return False, None, f"请求超时（{self.timeout}秒）。AI模型处理时间较长，请稍后重试或增加超时时间设置。"
                return False, None, f"网络连接错误: {error_msg}"
            except TimeoutError as e:
                return False, None, f"请求超时（{self.timeout}秒）。AI模型处理时间较长，请稍后重试或增加超时时间设置。"
            except Exception as e:
                error_msg = str(e)
                if 'timed out' in error_msg.lower() or 'timeout' in error_msg.lower():
                    return False, None, f"请求超时（{self.timeout}秒）。AI模型处理时间较长，请稍后重试或增加超时时间设置。"
                return False, None, f"请求处理错误: {error_msg}"
                
        except Exception as e:
            current_app.logger.error(f"AI对话服务错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return False, None, f"对话服务内部错误: {str(e)}"
    
    def stream_chat_with_ai(self, messages: list, profit_data: Optional[Dict] = None, all_page_data: Optional[Dict] = None):
        """
        与AI进行流式对话（生成器函数，逐步返回内容）
        
        Args:
            messages: 对话消息列表
            profit_data: 可选的利润测算汇总表数据
            all_page_data: 可选的所有页面数据，用于提供完整上下文
            
        Yields:
            Tuple[str, bool]: (内容片段, 是否完成)
        """
        try:
            # 构建系统提示词
            system_prompt = self._build_system_prompt()
            
            # 添加数据上下文
            data_context_parts = []
            
            # 如果提供了所有页面数据，格式化并添加
            if all_page_data:
                data_context = self._format_all_data_for_context(all_page_data, profit_data)
                data_context_parts.append(data_context)
            # 如果只提供了利润数据，使用旧的格式
            elif profit_data:
                data_context = self._format_profit_data(profit_data)
                data_context_parts.append(f"**当前利润测算汇总表数据**（供参考）：\n{data_context}")
            
            # 如果有数据上下文，添加到系统提示中
            if data_context_parts:
                system_prompt += "\n\n**当前运营数据**（供参考）：\n" + "\n".join(data_context_parts)
                system_prompt += "\n\n**重要说明**：你可以基于以上所有数据进行问答分析，包括利润测算汇总表、统计数据、业务数据等。"
            
            # 构建消息列表
            chat_messages = [{"role": "system", "content": system_prompt}]
            chat_messages.extend(messages)
            
            # 如果模型名称为空，使用默认模型
            model = self.model_name if self.model_name else "gpt-3.5-turbo"
            
            request_data = {
                "model": model,
                "messages": chat_messages,
                "temperature": 0.7,
                "max_tokens": self.max_tokens,
                "stream": True  # 启用流式响应
            }
            
            # 准备HTTP请求
            json_data = json.dumps(request_data, ensure_ascii=False).encode('utf-8')
            req = urllib.request.Request(
                self.api_endpoint,
                data=json_data,
                headers={
                    'Content-Type': 'application/json',
                    'Content-Length': str(len(json_data))
                },
                method='POST'
            )
            
            # 发送流式请求
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    buffer = ""
                    for line in response:
                        line_str = line.decode('utf-8')
                        buffer += line_str
                        
                        # SSE格式：每行以data:开头
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            line = line.strip()
                            
                            if line.startswith('data: '):
                                data_str = line[6:]  # 移除'data: '前缀
                                
                                if data_str == '[DONE]':
                                    yield ('', True)
                                    return
                                
                                try:
                                    data = json.loads(data_str)
                                    if 'choices' in data and len(data['choices']) > 0:
                                        delta = data['choices'][0].get('delta', {})
                                        content = delta.get('content', '')
                                        if content:
                                            yield (content, False)
                                        
                                        # 检查是否完成（必须在处理content之后检查）
                                        finish_reason = data['choices'][0].get('finish_reason')
                                        if finish_reason:
                                            # 确保所有内容都已发送后再返回
                                            yield ('', True)
                                            return
                                except json.JSONDecodeError:
                                    # 忽略无效的JSON
                                    pass
                                    
            except Exception as e:
                error_msg = str(e)
                yield (f"\n\n[错误: {error_msg}]", True)
                
        except Exception as e:
            current_app.logger.error(f"AI流式对话服务错误: {str(e)}")
            import traceback
            traceback.print_exc()
            yield (f"\n\n[错误: 对话服务内部错误: {str(e)}]", True)
    
    def stream_analyze_profit_summary(self, data: Dict):
        """
        流式分析利润测算汇总表数据（生成器函数）
        
        Args:
            data: 利润测算汇总表数据字典
            
        Yields:
            Tuple[str, bool]: (内容片段, 是否完成)
        """
        try:
            # 构建请求数据
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(data)
            
            model = self.model_name if self.model_name else "gpt-3.5-turbo"
            
            request_data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": self.max_tokens,
                "stream": True  # 启用流式响应
            }
            
            # 准备HTTP请求
            json_data = json.dumps(request_data).encode('utf-8')
            req = urllib.request.Request(
                self.api_endpoint,
                data=json_data,
                headers={
                    'Content-Type': 'application/json',
                    'Content-Length': str(len(json_data))
                },
                method='POST'
            )
            
            # 发送流式请求
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    buffer = ""
                    for line in response:
                        line_str = line.decode('utf-8')
                        buffer += line_str
                        
                        # SSE格式处理
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            line = line.strip()
                            
                            if line.startswith('data: '):
                                data_str = line[6:]
                                
                                if data_str == '[DONE]':
                                    # 处理缓冲区中剩余的数据
                                    if buffer.strip():
                                        remaining_lines = buffer.split('\n')
                                        for rem_line in remaining_lines:
                                            if rem_line.strip().startswith('data: '):
                                                try:
                                                    rem_data = json.loads(rem_line.strip()[6:])
                                                    if 'choices' in rem_data and len(rem_data['choices']) > 0:
                                                        delta = rem_data['choices'][0].get('delta', {})
                                                        content = delta.get('content', '')
                                                        if content:
                                                            yield (content, False)
                                                except:
                                                    pass
                                    yield ('', True)
                                    return
                                
                                try:
                                    data = json.loads(data_str)
                                    if 'choices' in data and len(data['choices']) > 0:
                                        delta = data['choices'][0].get('delta', {})
                                        content = delta.get('content', '')
                                        # 先处理content（如果有）
                                        if content:
                                            yield (content, False)
                                        
                                        # 检查是否完成（必须在处理content之后）
                                        finish_reason = data['choices'][0].get('finish_reason')
                                        if finish_reason:
                                            # 处理缓冲区中剩余的数据
                                            if buffer.strip():
                                                remaining_lines = buffer.split('\n')
                                                for rem_line in remaining_lines:
                                                    if rem_line.strip().startswith('data: '):
                                                        try:
                                                            rem_data = json.loads(rem_line.strip()[6:])
                                                            if 'choices' in rem_data and len(rem_data['choices']) > 0:
                                                                delta = rem_data['choices'][0].get('delta', {})
                                                                content = delta.get('content', '')
                                                                if content:
                                                                    yield (content, False)
                                                        except:
                                                            pass
                                            # 确保所有内容都已发送后再返回
                                            yield ('', True)
                                            return
                                except json.JSONDecodeError:
                                    pass
                    
                    # 如果循环结束，处理缓冲区中剩余的数据
                    if buffer.strip():
                        remaining_lines = buffer.split('\n')
                        for rem_line in remaining_lines:
                            if rem_line.strip().startswith('data: '):
                                try:
                                    rem_data = json.loads(rem_line.strip()[6:])
                                    if 'choices' in rem_data and len(rem_data['choices']) > 0:
                                        delta = rem_data['choices'][0].get('delta', {})
                                        content = delta.get('content', '')
                                        if content:
                                            yield (content, False)
                                except:
                                    pass
                    yield ('', True)
                                    
            except Exception as e:
                error_msg = str(e)
                yield (f"\n\n[错误: {error_msg}]", True)
                
        except Exception as e:
            current_app.logger.error(f"AI流式分析服务错误: {str(e)}")
            import traceback
            traceback.print_exc()
            yield (f"\n\n[错误: 分析服务内部错误: {str(e)}]", True)

