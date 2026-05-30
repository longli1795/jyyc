import os
from flask import Blueprint, request, jsonify, send_file, session
from app.services.data_service import DataService
from app.services.calculation_service import CalculationService
from app.models.app_data import AppDataManager
from app.utils.auth_utils import login_required, require_can_edit

calculation_bp = Blueprint('calculation', __name__)

# 服务将在每次请求时创建，确保使用最新数据

@calculation_bp.route('/upload', methods=['POST'])
@login_required
@require_can_edit
def upload_file():
    """文件上传接口：固化到磁盘并加载全局期初库存"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '没有选择文件'})

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': '没有选择文件'})

        if not file or not file.filename:
            return jsonify({'success': False, 'message': '无效的文件'})

        from app.services.opening_inventory_store import (
            GLOBAL_OPENING_SESSION_ID,
            save_uploaded_file,
            load_from_disk_into_memory,
            get_meta,
        )
        from app.utils.auth_utils import get_current_user

        user = get_current_user()
        user_id = user.id if user else session.get('user_id')

        ok, msg, meta = save_uploaded_file(file, uploaded_by_user_id=user_id)
        if not ok:
            return jsonify({'success': False, 'message': msg})

        load_ok, load_msg = load_from_disk_into_memory()
        if not load_ok:
            return jsonify({'success': False, 'message': load_msg})

        data_service = DataService(GLOBAL_OPENING_SESSION_ID)
        summary = data_service.get_data_summary()

        return jsonify({
            'success': True,
            'message': '期初库存已固化并加载',
            'data_summary': summary,
            'opening_inventory_meta': get_meta() or meta,
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'文件处理失败: {str(e)}'})

@calculation_bp.route('/auto_process', methods=['POST'])
@login_required
@require_can_edit
def auto_process():
    """一键自动处理"""
    try:
        # 创建服务实例
        from flask import session
        session_id = session.get('session_id')
        data_service = DataService(session_id)
        calculation_service = CalculationService(session_id)
        
        success, message = calculation_service.auto_process_all()
        
        if success:
            # 保存数据到文件
            data_service.save_data()
            
            return jsonify({
                'success': True, 
                'message': message,
                'results': calculation_service.get_results_summary()
            })
        else:
            return jsonify({'success': False, 'message': message})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'自动处理失败: {str(e)}'})

@calculation_bp.route('/manual_extract', methods=['POST'])
@login_required
@require_can_edit
def manual_extract():
    """手动提取数据"""
    try:
        from flask import session
        session_id = session.get('session_id')
        calculation_service = CalculationService(session_id)
        if calculation_service.extract_data():
            return jsonify({'success': True, 'message': '数据提取完成'})
        else:
            return jsonify({'success': False, 'message': '数据提取失败'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'提取失败: {str(e)}'})

@calculation_bp.route('/manual_disassembly', methods=['POST'])
@login_required
@require_can_edit
def manual_disassembly():
    """手动计算拆解"""
    try:
        from flask import session
        session_id = session.get('session_id')
        calculation_service = CalculationService(session_id)
        if calculation_service.calculate_disassembly():
            return jsonify({'success': True, 'message': '拆解计算完成'})
        else:
            return jsonify({'success': False, 'message': '拆解计算失败'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'计算失败: {str(e)}'})

@calculation_bp.route('/manual_deep_processing', methods=['POST'])
@login_required
@require_can_edit
def manual_deep_processing():
    """手动计算深加工"""
    try:
        from flask import session
        session_id = session.get('session_id')
        calculation_service = CalculationService(session_id)
        if calculation_service.calculate_deep_processing():
            return jsonify({'success': True, 'message': '深加工计算完成'})
        else:
            return jsonify({'success': False, 'message': '深加工计算失败'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'计算失败: {str(e)}'})

@calculation_bp.route('/get_status', methods=['GET'])
def get_status():
    """获取处理状态"""
    from flask import session
    from app.models.compatibility import AppDataManagerAdapter
    session_id = session.get('session_id')
    app_data = AppDataManagerAdapter.get_instance(session_id)
    status = app_data.get_data('status')
    progress = app_data.get_data('progress')
    return jsonify({'status': status, 'progress': progress})

@calculation_bp.route('/get_data', methods=['GET'])
def get_data():
    """获取数据"""
    try:
        data_type = request.args.get('type', 'calculated_data')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        from flask import session
        from app.models.compatibility import AppDataManagerAdapter
        session_id = session.get('session_id')
        app_data = AppDataManagerAdapter.get_instance(session_id)
        data = app_data.get_data(data_type)
        
        if data is None or data.empty:
            return jsonify({
                'success': True,
                'data': [],
                'total': 0,
                'current_page': page,
                'per_page': per_page,
                'pages': 0
            })
        
        # 分页处理
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_data = data.iloc[start_idx:end_idx]
        
        # 转换为JSON格式
        json_data = app_data.safe_json_convert(page_data)
        
        total_pages = (len(data) + per_page - 1) // per_page
        
        return jsonify({
            'success': True,
            'data': json_data,
            'total': len(data),
            'current_page': page,
            'per_page': per_page,
            'pages': total_pages
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取数据失败: {str(e)}'})

@calculation_bp.route('/get_data/<data_type>', methods=['GET'])
def get_data_by_type(data_type):
    """获取指定类型的数据 - 兼容原始API格式"""
    try:
        from flask import session
        from app.models.compatibility import AppDataManagerAdapter
        session_id = session.get('session_id')
        app_data = AppDataManagerAdapter.get_instance(session_id)
        
        # 数据类型映射
        data_mapping = {
            'source': 'source_data',
            'extracted': 'extracted_data', 
            'original': 'disassembly_data',
            'final': 'calculated_data',
            'deducted': 'deducted_data_manual',  # 🔧 架构重构：使用 deducted_data_manual
            'deep_original': 'deep_processing_data',
            'saleable': 'saleable_data'
        }
        
        # 获取实际的数据键名
        actual_key = data_mapping.get(data_type, data_type + '_data')
        data = app_data.get_data(actual_key)
        
        if data is not None and not data.empty:
            return jsonify(app_data.safe_json_convert(data))
        else:
            return jsonify([])
            
    except Exception as e:
        print(f"获取数据失败: {str(e)}")
        return jsonify([])

@calculation_bp.route('/clear_data', methods=['POST'])
@login_required
@require_can_edit
def clear_data():
    """清除数据"""
    try:
        import pandas as pd
        from flask import session
        from app.models.compatibility import AppDataManagerAdapter
        session_id = session.get('session_id')
        data_service = DataService(session_id)
        data_service.clear_all_data()
        
        # 明确清除所有相关数据（设置为None，确保API返回空数据）
        app_data = AppDataManagerAdapter.get_instance(session_id)
        
        # ========== 清除成本预测相关的数据 ==========
        app_data.set_data('extracted_data_manual', None)
        app_data.set_data('cost_forecast_data', None)
        app_data.set_data('extracted_data_modified', False)
        app_data.set_data('extracted_modification_timestamp', None)
        app_data.set_data('original_extracted_data', None)
        app_data.set_data('extracted_data', None)
        
        # ========== 清除收入预测相关的数据 ==========
        app_data.set_data('subsidy_income_data', None)  # 基金补贴收入数据
        app_data.set_data('saleable_data_manual', None)  # 可销售量手工数据
        app_data.set_data('saleable_data', None)  # 可销售量系统数据
        app_data.set_data('saleable_data_modified', False)
        app_data.set_data('disassembly_product_output_value_data', None)  # 一次拆解产物产值数据
        
        # ========== 清除成本计算相关的缓存（清除所有可能的预测期数缓存 1-120个月）==========
        for period in range(1, 121):
            app_data.set_data(f'disassembly_product_cost_result_v2_{period}', None)
            app_data.set_data(f'screen_cost_allocation_result_v2_{period}', None)
            app_data.set_data(f'production_cost_allocation_result_v2_{period}', None)
            app_data.set_data(f'screen_cost_allocation_result_{period}', None)
            app_data.set_data(f'production_cost_allocation_result_{period}', None)
            # 清除旧版本的缓存键（如果有）
            app_data.set_data(f'disassembly_product_cost_result_{period}', None)
        
        # ========== 清除其他相关数据 ==========
        app_data.set_data('deducted_data_manual', None)
        app_data.set_data('deducted_data_modified', False)
        app_data.set_data('original_deducted_data', None)
        app_data.set_data('calculated_data', None)
        app_data.set_data('deep_processing_data', None)
        app_data.set_data('disassembly_data', None)
        
        # 确保清除标志已设置
        app_data.set_data('__data_cleared__', True)
        
        print("✅ 已清除所有数据，包括成本预测、收入预测、成本计算相关数据和缓存")
        return jsonify({'success': True, 'message': '数据已清除'})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'清除数据失败: {str(e)}'}) 

@calculation_bp.route('/export-deducted-data', methods=['GET'])
def export_deducted_data():
    """导出被减扣数据到Excel"""
    try:
        from app.utils.excel_utils import create_deducted_data_excel
        from datetime import datetime
        from app.utils.deducted_disassembly_align import align_deducted_inventory_tai_from_disassembly
        
        # 获取数据类型参数
        data_type = request.args.get('type', 'manual')
        
        from flask import session
        from app.models.compatibility import AppDataManagerAdapter
        session_id = session.get('session_id')
        app_data = AppDataManagerAdapter.get_instance(session_id)
        modified = bool(app_data.get_data('deducted_data_modified'))
        disassembly_data = app_data.get_data('disassembly_data')
        
        if data_type == 'readonly':
            # 已手工修改：导出修改前快照 + 当前 TAI；未修改：系统被减扣表 + 公式 KG
            filename_prefix = '被减扣数据(只读)'
            if modified:
                deducted_data = app_data.get_data('original_deducted_data')
                if deducted_data is None or deducted_data.empty:
                    deducted_data = app_data.get_data('deducted_data_manual')
                recalculate_kg = True
            else:
                deducted_data = app_data.get_data('deducted_data_manual')
                if deducted_data is None or deducted_data.empty:
                    od = app_data.get_data('original_deducted_data')
                    if od is not None and not od.empty:
                        deducted_data = od
                recalculate_kg = True
            if deducted_data is not None and not deducted_data.empty:
                deducted_data = deducted_data.copy()
                if disassembly_data is not None and not disassembly_data.empty:
                    deducted_data = align_deducted_inventory_tai_from_disassembly(
                        deducted_data,
                        disassembly_data,
                        recalculate_kg=recalculate_kg,
                        recalculate_kg_when_tai_changed=False,
                    )
        else:
            # 导出手工数据（仅在被减扣已编辑时存在）
            filename_prefix = '被减扣数据(手工)'
            if not modified:
                return jsonify({
                    'success': False,
                    'error': '未编辑被减扣数据，无被减扣数据(手工)可导出',
                }), 400
            deducted_data = app_data.get_data('deducted_data_manual')
            if deducted_data is not None and not deducted_data.empty:
                deducted_data = deducted_data.copy()
                if disassembly_data is not None and not disassembly_data.empty:
                    deducted_data = align_deducted_inventory_tai_from_disassembly(
                        deducted_data,
                        disassembly_data,
                        recalculate_kg=False,
                        recalculate_kg_when_tai_changed=True,
                    )
        
        if deducted_data is None or deducted_data.empty:
            return jsonify({'success': False, 'error': f'没有{filename_prefix}可以导出'}), 400
        
        # 生成Excel文件
        excel_file = create_deducted_data_excel(deducted_data)
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f'{filename_prefix}_{timestamp}.xlsx'
        
        return send_file(
            excel_file,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        print(f"导出被减扣数据失败: {str(e)}")
        return jsonify({'success': False, 'error': f'导出失败: {str(e)}'}), 500

@calculation_bp.route('/deducted-data-template', methods=['GET'])
def download_deducted_data_template():
    """下载被减扣数据导入模板"""
    try:
        from app.utils.excel_utils import create_deducted_data_template
        
        # 生成模板文件
        template_file = create_deducted_data_template()
        
        return send_file(
            template_file,
            as_attachment=True,
            download_name='被减扣数据导入模板.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        print(f"生成模板失败: {str(e)}")
        return jsonify({'success': False, 'error': f'模板生成失败: {str(e)}'}), 500

@calculation_bp.route('/parse-deducted-excel', methods=['POST'])
@login_required
@require_can_edit
def parse_deducted_excel():
    """解析被减扣数据Excel文件"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '没有选择文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '没有选择文件'}), 400
        
        # 验证文件类型
        allowed_extensions = {'.xlsx', '.xls'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return jsonify({'success': False, 'error': '请选择有效的Excel文件 (.xlsx 或 .xls)'}), 400
        
        from app.utils.excel_utils import parse_deducted_data_excel
        
        # 解析Excel文件
        data, errors = parse_deducted_data_excel(file)
        
        return jsonify({
            'success': True,
            'data': data,
            'errors': errors,
            'total_count': len(data),
            'valid_count': len([row for row in data if not row.get('error')]),
            'error_count': len([row for row in data if row.get('error')])
        })
        
    except Exception as e:
        print(f"解析Excel文件失败: {str(e)}")
        return jsonify({'success': False, 'error': f'Excel文件解析失败: {str(e)}'}), 500

@calculation_bp.route('/import-deducted-data', methods=['POST'])
@login_required
@require_can_edit
def import_deducted_data():
    """导入被减扣数据（已迁移至 /api/data-management/import-deducted-data，保留兼容）"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '请提供数据'}), 400
        
        import_data = data.get('data', [])
        import_mode = data.get('mode', 'replace')  # replace, merge, append
        
        if not import_data:
            return jsonify({'success': False, 'error': '没有有效的导入数据'}), 400
        
        from app.services.calculation_service import CalculationService
        import pandas as pd
        
        # 转换为DataFrame
        import_df = pd.DataFrame(import_data)
        
        from flask import session
        from app.models.compatibility import AppDataManagerAdapter
        session_id = session.get('session_id')
        app_data = AppDataManagerAdapter.get_instance(session_id)
        
        import copy

        # 修改：导入到手工数据而不是只读数据
        current_data = app_data.get_data('deducted_data_manual')
        # 导入前快照：首页导出「被减扣数据」sheet 为导入前手工表，「被减扣数据(手工)」为导入后
        if current_data is not None and not current_data.empty:
            app_data.set_data('original_deducted_data', copy.deepcopy(current_data))
        else:
            original_data = app_data.get_data('original_deducted_data')
            if original_data is None or (isinstance(original_data, pd.DataFrame) and original_data.empty):
                app_data.backup_original_deducted_data()
        
        if import_mode == 'replace':
            # 完全覆盖
            new_data = import_df
            imported_count = len(import_df)
        elif import_mode == 'merge':
            # 合并更新：基于拆解产物编码进行合并
            if current_data is not None and not current_data.empty:
                # 删除重复的记录，保留导入的数据
                key_column = '拆解产物编码'
                if key_column in import_df.columns and key_column in current_data.columns:
                    # 移除现有数据中与导入数据重复的记录
                    mask = ~current_data[key_column].isin(import_df[key_column])
                    filtered_current = current_data[mask]
                    new_data = pd.concat([filtered_current, import_df], ignore_index=True)
                else:
                    new_data = pd.concat([current_data, import_df], ignore_index=True)
            else:
                new_data = import_df
            imported_count = len(import_df)
        elif import_mode == 'append':
            # 追加模式
            if current_data is not None and not current_data.empty:
                new_data = pd.concat([current_data, import_df], ignore_index=True)
            else:
                new_data = import_df
            imported_count = len(import_df)
        else:
            return jsonify({'success': False, 'error': '无效的导入模式'}), 400
        
        # 重新编号
        if not new_data.empty:
            new_data['序号'] = range(1, len(new_data) + 1)
        
        # 修改：保存到手工数据
        app_data.set_data('deducted_data_manual', new_data)
        
        # 标记数据已修改
        app_data.mark_deducted_data_modified()
        
        # 自动保存持久化数据
        app_data.save_persistent_data()
        
        print(f"✅ 被减扣数据导入成功: {imported_count} 条记录，总计 {len(new_data)} 条")
        
        return jsonify({
            'success': True,
            'message': f'数据导入成功，{import_mode}模式导入了 {imported_count} 条记录。请返回首页点击“重新计算”使结果链路生效',
            'imported_count': imported_count,
            'total_count': len(new_data)
        })
        
    except Exception as e:
        print(f"导入数据失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'导入失败: {str(e)}'}), 500

@calculation_bp.route('/recalculate-deducted', methods=['POST'])
@login_required
@require_can_edit
def recalculate_deducted_data():
    """重新计算被减扣数据"""
    try:
        data = request.get_json()
        modified_data = data.get('modified_data', [])
        
        if not modified_data:
            return jsonify({'success': False, 'error': '没有修改的数据需要重新计算'}), 400
        
        from flask import session
        from app.models.compatibility import AppDataManagerAdapter
        session_id = session.get('session_id')
        app_data = AppDataManagerAdapter.get_instance(session_id)
        # 🔧 架构重构：使用 deducted_data_manual，不再使用 deducted_data (只读)
        current_deducted_data = app_data.get_data('deducted_data_manual')
        if current_deducted_data is None or current_deducted_data.empty:
            # 如果手工数据为空且未修改，尝试使用原始备份
            original_data = app_data.get_data('original_deducted_data')
            if original_data is not None and not original_data.empty:
                import copy
                current_deducted_data = copy.deepcopy(original_data)
            else:
                return jsonify({'success': False, 'error': '没有被减扣数据'}), 400
        
        # 更新修改的记录
        updated_count = 0
        for modified_item in modified_data:
            # 根据序号或唯一标识找到对应的记录
            row_id = modified_item.get('序号') or modified_item.get('id')
            if row_id:
                # 查找对应的行
                mask = current_deducted_data['序号'] == row_id
                if mask.any():
                    # 更新数据
                    for key, value in modified_item.items():
                        if key in current_deducted_data.columns:
                            current_deducted_data.loc[mask, key] = value
                    
                    # 重新计算结果
                    row_index = current_deducted_data[mask].index[0]
                    inventory = float(current_deducted_data.loc[row_index, '原库存数量(TAI)']) if current_deducted_data.loc[row_index, '原库存数量(TAI)'] != '-' else 0
                    weight = float(current_deducted_data.loc[row_index, '单台重量(KG/台)']) if current_deducted_data.loc[row_index, '单台重量(KG/台)'] != '-' else 0
                    ratio = float(current_deducted_data.loc[row_index, '投入产出比例']) if current_deducted_data.loc[row_index, '投入产出比例'] != '-' else 0
                    coefficient = float(current_deducted_data.loc[row_index, '拆解系数']) if current_deducted_data.loc[row_index, '拆解系数'] != '-' else 0
                    
                    if inventory != 0 and weight != 0:
                        new_result = inventory * weight * ratio * coefficient
                        current_deducted_data.loc[row_index, '计算结果(KG)'] = round(new_result, 6)
                    
                    updated_count += 1
        
        # 🔧 架构重构：保存到 deducted_data_manual，不再使用 deducted_data (只读)
        app_data.set_data('deducted_data_manual', current_deducted_data)
        
        # 自动保存持久化数据
        from flask import session
        session_id = session.get('session_id')
        data_service = DataService(session_id)
        data_service.save_data()
        
        return jsonify({
            'success': True,
            'message': f'重新计算完成，更新了 {updated_count} 条记录',
            'updated_count': updated_count
        })
        
    except Exception as e:
        print(f"重新计算失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'重新计算失败: {str(e)}'}), 500

@calculation_bp.route('/apply-deducted-changes', methods=['POST'])
@login_required
@require_can_edit
def apply_deducted_changes():
    """将编辑后的被减扣数据应用到主计算流程"""
    try:
        from app.core.calculation_engine import CalculationEngine
        from app.services.data_service import DataService
        
        # 获取当前被减扣数据（已经通过其他接口更新过）
        from flask import session
        from app.models.compatibility import AppDataManagerAdapter
        session_id = session.get('session_id')
        app_data = AppDataManagerAdapter.get_instance(session_id)
        # 🔧 架构重构：使用 deducted_data_manual，不再使用 deducted_data (只读)
        current_deducted_data = app_data.get_data('deducted_data_manual')
        if current_deducted_data is None or current_deducted_data.empty:
            # 如果手工数据为空且未修改，尝试使用原始备份
            original_data = app_data.get_data('original_deducted_data')
            if original_data is not None and not original_data.empty:
                import copy
                current_deducted_data = copy.deepcopy(original_data)
            else:
                return jsonify({
                    'success': False, 
                    'error': '没有被减扣数据可以应用'
                }), 400
        
        # 备份当前数据状态
        original_deep_processing = app_data.get_data('deep_processing_data')
        original_saleable = app_data.get_data('saleable_data')
        
        print(f"🔄 开始应用被减扣数据更改到主流程...")
        print(f"   当前被减扣数据: {len(current_deducted_data)} 条记录")
        
        # 标记数据已修改（确保深加工计算使用修改后的数据）
        app_data.mark_deducted_data_modified()
        
        # 重新计算深加工
        calculation_engine = CalculationEngine()
        success = calculation_engine.calculate_deep_processing_auto()
        
        if success:
            # 获取更新后的数据
            new_deep_processing = app_data.get_data('deep_processing_data')
            new_saleable = app_data.get_data('saleable_data')
            
            # 统计更新信息
            deep_processing_count = len(new_deep_processing) if new_deep_processing is not None else 0
            saleable_count = len(new_saleable) if new_saleable is not None else 0
            
            # 保存持久化数据
            from flask import session
            session_id = session.get('session_id')
            data_service = DataService(session_id)
            data_service.save_data()
            
            print(f"✅ 被减扣数据已成功应用到主流程:")
            print(f"   - 深加工数据: {deep_processing_count} 条记录")
            print(f"   - 可销售量数据: {saleable_count} 条记录")
            
            return jsonify({
                'success': True,
                'message': '被减扣数据已应用到主流程，深加工计算和可销售量数据已更新',
                'statistics': {
                    'deducted_count': len(current_deducted_data),
                    'deep_processing_count': deep_processing_count,
                    'saleable_count': saleable_count
                }
            })
        else:
            # 恢复原始数据
            if original_deep_processing is not None:
                app_data.set_data('deep_processing_data', original_deep_processing)
            if original_saleable is not None:
                app_data.set_data('saleable_data', original_saleable)
                
            return jsonify({
                'success': False,
                'error': '深加工重新计算失败，已恢复原始数据'
            }), 500
            
    except Exception as e:
        print(f"应用被减扣数据更改失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'error': f'应用更改失败: {str(e)}'
        }), 500 