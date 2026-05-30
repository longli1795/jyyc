"""
系统管理API
提供会话管理、性能监控和数据库管理功能
"""

from flask import Blueprint, jsonify, request, session
from datetime import datetime, timedelta
import psutil
import os

from app.models.database import db, UserSession, SessionDataset, CalculationHistory, SystemMetrics
from app.models.session_data_manager import SessionDataManagerFactory, SessionDataManager
from app.models.compatibility import migrate_from_pickle
from app.utils.auth_utils import login_required

system_bp = Blueprint('system', __name__)

@system_bp.route('/session/info', methods=['GET'])
def get_session_info():
    """获取当前会话信息"""
    try:
        session_id = session.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': '没有活跃的会话'
            }), 400
        
        # 获取会话详细信息
        user_session = UserSession.query.filter_by(session_id=session_id).first()
        if not user_session:
            return jsonify({
                'success': False,
                'error': '会话不存在'
            }), 404
        
        # 获取会话数据统计
        datasets = SessionDataset.query.filter_by(session_id=session_id).all()
        data_summary = {}
        total_size = 0
        
        for dataset in datasets:
            data_summary[dataset.data_key] = {
                'type': dataset.data_type,
                'size_bytes': dataset.data_size or 0,
                'rows': dataset.row_count,
                'columns': dataset.column_count,
                'updated_at': dataset.updated_at.isoformat() if dataset.updated_at else None
            }
            total_size += dataset.data_size or 0
        
        # 获取计算历史
        recent_calculations = CalculationHistory.query.filter_by(
            session_id=session_id
        ).order_by(CalculationHistory.started_at.desc()).limit(5).all()
        
        return jsonify({
            'success': True,
            'data': {
                'session': user_session.to_dict(),
                'data_summary': data_summary,
                'total_data_size': total_size,
                'dataset_count': len(datasets),
                'recent_calculations': [calc.to_dict() for calc in recent_calculations]
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取会话信息失败: {str(e)}'
        }), 500

@system_bp.route('/session/sync-notification', methods=['GET'])
@login_required
def get_sync_notification():
    """获取当前用户的同步通知（只读，不消费）。"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': '没有活跃的会话'}), 400
        notification = SessionDataManager.peek_sync_notification(user_id)
        if not notification:
            return jsonify({
                'success': True,
                'data': {'pending': False}
            })
        return jsonify({
            'success': True,
            'data': {
                'pending': True,
                'from_user_id': notification.get('from_user_id'),
                'from_name': notification.get('from_name') or '',
                'synced_at': notification.get('synced_at') or '',
                'prediction_period': notification.get('prediction_period'),
                'sync_id': notification.get('sync_id') or '',
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取同步通知失败: {str(e)}'
        }), 500


@system_bp.route('/user-ui-settings', methods=['GET'])
@login_required
def get_user_ui_settings_api():
    """获取当前用户的界面设置（预测期数等）。"""
    try:
        user_id = session.get('user_id')
        session_id = session.get('session_id') or (f'user_{user_id}' if user_id else None)
        if not session_id:
            return jsonify({'success': False, 'error': '没有活跃的会话'}), 400
        settings = SessionDataManager.get_user_ui_settings(session_id=session_id)
        return jsonify({'success': True, 'data': settings})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@system_bp.route('/user-ui-settings', methods=['POST'])
@login_required
def save_user_ui_settings_api():
    """保存当前用户的界面设置。"""
    try:
        user_id = session.get('user_id')
        session_id = session.get('session_id') or (f'user_{user_id}' if user_id else None)
        if not session_id:
            return jsonify({'success': False, 'error': '没有活跃的会话'}), 400
        payload = request.get_json(silent=True) or {}
        updates = {}
        if 'prediction_period' in payload:
            try:
                pp = int(payload['prediction_period'])
                if 1 <= pp <= 120:
                    updates['prediction_period'] = pp
            except (TypeError, ValueError):
                return jsonify({'success': False, 'error': '预测期数无效'}), 400
        if not updates:
            return jsonify({'success': False, 'error': '没有可保存的设置'}), 400
        settings = SessionDataManager.upsert_user_ui_settings(session_id, updates)
        db.session.commit()
        return jsonify({'success': True, 'data': settings})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@system_bp.route('/session/sync-notification/accept', methods=['POST'])
@login_required
def accept_sync_notification():
    """用户确认刷新，清除同步通知。"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': '没有活跃的会话'}), 400
        SessionDataManager.clear_sync_notification(user_id)
        return jsonify({'success': True, 'message': '已确认'})
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'确认同步通知失败: {str(e)}'
        }), 500


@system_bp.route('/session/sync-notification/dismiss', methods=['POST'])
@login_required
def dismiss_sync_notification():
    """用户稍后处理，清除同步通知。"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': '没有活跃的会话'}), 400
        SessionDataManager.clear_sync_notification(user_id)
        return jsonify({'success': True, 'message': '已忽略'})
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'忽略同步通知失败: {str(e)}'
        }), 500


@system_bp.route('/session/sync-history', methods=['GET'])
@login_required
def get_sync_history():
    """获取当前用户的同步历史列表。"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': '没有活跃的会话'}), 400
        from app.services.sync_history_service import list_sync_entries
        items = list_sync_entries(user_id)
        return jsonify({'success': True, 'data': items})
    except Exception as e:
        return jsonify({'success': False, 'error': f'获取同步历史失败: {str(e)}'}), 500


@system_bp.route('/session/sync-history/apply', methods=['POST'])
@login_required
def apply_sync_history():
    """应用选定的同步历史版本到当前用户会话。"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': '没有活跃的会话'}), 400
        payload = request.get_json(silent=True) or {}
        sync_id = (payload.get('sync_id') or '').strip()
        if not sync_id:
            return jsonify({'success': False, 'error': '请选择同步记录'}), 400
        from app.services.sync_history_service import apply_sync_entry
        result = apply_sync_entry(user_id, sync_id)
        db.session.commit()
        return jsonify({'success': True, 'message': '已应用同步数据', 'data': result})
    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'应用同步历史失败: {str(e)}'}), 500

@system_bp.route('/session/list', methods=['GET'])
def list_active_sessions():
    """列出所有活跃会话"""
    try:
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        
        # 查询活跃会话
        sessions_query = UserSession.query.filter(
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        ).order_by(UserSession.last_accessed.desc())
        
        sessions = sessions_query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        session_list = []
        for user_session in sessions.items:
            # 获取每个会话的数据统计
            dataset_count = SessionDataset.query.filter_by(
                session_id=user_session.session_id
            ).count()
            
            total_size = db.session.query(
                db.func.sum(SessionDataset.data_size)
            ).filter_by(session_id=user_session.session_id).scalar() or 0
            
            session_info = user_session.to_dict()
            session_info.update({
                'dataset_count': dataset_count,
                'total_data_size': total_size
            })
            session_list.append(session_info)
        
        return jsonify({
            'success': True,
            'data': {
                'sessions': session_list,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': sessions.total,
                    'pages': sessions.pages
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取会话列表失败: {str(e)}'
        }), 500

@system_bp.route('/session/cleanup', methods=['POST'])
def cleanup_expired_sessions():
    """手动清理过期会话"""
    try:
        # 执行清理
        SessionDataManagerFactory.cleanup_expired_sessions()
        
        # 统计清理结果
        active_count = UserSession.query.filter(
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        ).count()
        
        inactive_count = UserSession.query.filter(
            UserSession.is_active == False
        ).count()
        
        return jsonify({
            'success': True,
            'data': {
                'active_sessions': active_count,
                'cleaned_sessions': inactive_count,
                'cleanup_time': datetime.utcnow().isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'清理会话失败: {str(e)}'
        }), 500

@system_bp.route('/metrics', methods=['GET'])
def get_system_metrics():
    """获取系统性能指标"""
    try:
        # 获取系统资源使用情况
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # 获取应用统计
        active_sessions = UserSession.query.filter(
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        ).count()
        
        total_sessions = UserSession.query.count()
        
        total_datasets = SessionDataset.query.count()
        total_data_size = db.session.query(
            db.func.sum(SessionDataset.data_size)
        ).scalar() or 0
        
        # 计算最近1小时的计算次数
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        calculations_per_hour = CalculationHistory.query.filter(
            CalculationHistory.started_at >= one_hour_ago
        ).count()
        
        # 计算平均计算时间
        avg_duration = db.session.query(
            db.func.avg(CalculationHistory.duration)
        ).filter(
            CalculationHistory.duration.isnot(None)
        ).scalar() or 0
        
        # 保存指标到数据库
        metric = SystemMetrics(
            active_sessions=active_sessions,
            total_sessions=total_sessions,
            calculations_per_hour=calculations_per_hour,
            avg_calculation_time=float(avg_duration),
            memory_usage_mb=memory.used / 1024 / 1024,
            cpu_usage_percent=cpu_percent,
            total_datasets=total_datasets,
            total_data_size_mb=total_data_size / 1024 / 1024
        )
        
        db.session.add(metric)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': {
                'timestamp': datetime.utcnow().isoformat(),
                'system': {
                    'cpu_percent': cpu_percent,
                    'memory_used_mb': memory.used / 1024 / 1024,
                    'memory_total_mb': memory.total / 1024 / 1024,
                    'memory_percent': memory.percent,
                    'disk_used_gb': disk.used / 1024 / 1024 / 1024,
                    'disk_total_gb': disk.total / 1024 / 1024 / 1024,
                    'disk_percent': (disk.used / disk.total) * 100
                },
                'application': {
                    'active_sessions': active_sessions,
                    'total_sessions': total_sessions,
                    'total_datasets': total_datasets,
                    'total_data_size_mb': total_data_size / 1024 / 1024,
                    'calculations_per_hour': calculations_per_hour,
                    'avg_calculation_time': float(avg_duration)
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取系统指标失败: {str(e)}'
        }), 500

@system_bp.route('/metrics/history', methods=['GET'])
def get_metrics_history():
    """获取系统指标历史"""
    try:
        hours = int(request.args.get('hours', 24))
        start_time = datetime.utcnow() - timedelta(hours=hours)
        
        metrics = SystemMetrics.query.filter(
            SystemMetrics.timestamp >= start_time
        ).order_by(SystemMetrics.timestamp.desc()).limit(100).all()
        
        return jsonify({
            'success': True,
            'data': {
                'metrics': [metric.to_dict() for metric in metrics],
                'period_hours': hours
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取指标历史失败: {str(e)}'
        }), 500

@system_bp.route('/database/info', methods=['GET'])
def get_database_info():
    """获取数据库信息"""
    try:
        from flask import current_app
        
        # 获取数据库统计信息
        tables_info = {}
        
        # 用户会话表
        sessions_count = UserSession.query.count()
        active_sessions_count = UserSession.query.filter(
            UserSession.is_active == True
        ).count()
        
        # 数据集表
        datasets_count = SessionDataset.query.count()
        total_data_size = db.session.query(
            db.func.sum(SessionDataset.data_size)
        ).scalar() or 0
        
        # 计算历史表
        calculations_count = CalculationHistory.query.count()
        completed_calculations = CalculationHistory.query.filter(
            CalculationHistory.status == 'completed'
        ).count()
        
        # 系统指标表
        metrics_count = SystemMetrics.query.count()
        
        return jsonify({
            'success': True,
            'data': {
                'database_type': current_app.config.get('DATABASE_TYPE', 'unknown'),
                'database_url': current_app.config.get('SQLALCHEMY_DATABASE_URI', '').split('@')[-1] if '@' in current_app.config.get('SQLALCHEMY_DATABASE_URI', '') else 'local',
                'tables': {
                    'user_sessions': {
                        'total_count': sessions_count,
                        'active_count': active_sessions_count
                    },
                    'session_datasets': {
                        'total_count': datasets_count,
                        'total_size_mb': total_data_size / 1024 / 1024
                    },
                    'calculation_history': {
                        'total_count': calculations_count,
                        'completed_count': completed_calculations
                    },
                    'system_metrics': {
                        'total_count': metrics_count
                    }
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取数据库信息失败: {str(e)}'
        }), 500

@system_bp.route('/migration/from-pickle', methods=['POST'])
def migrate_data_from_pickle():
    """从pickle文件迁移数据"""
    try:
        success = migrate_from_pickle()
        
        if success:
            return jsonify({
                'success': True,
                'message': '数据迁移完成'
            })
        else:
            return jsonify({
                'success': False,
                'error': '数据迁移失败，请检查日志'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'迁移失败: {str(e)}'
        }), 500

@system_bp.route('/health', methods=['GET'])
def health_check():
    """系统健康检查"""
    try:
        # 检查数据库连接
        db_status = "healthy"
        try:
            UserSession.query.first()
        except Exception as e:
            db_status = f"database_error: {str(e)}"
        
        # 检查Redis连接  
        redis_status = "healthy"
        try:
            from app.models.session_data_manager import SessionDataManagerFactory
            manager = SessionDataManagerFactory.get_manager()
            if manager.redis_client:
                manager.redis_client.ping()
            else:
                redis_status = "redis_unavailable"
        except Exception as e:
            redis_status = f"redis_error: {str(e)}"
        
        # 检查会话数量
        active_sessions = UserSession.query.filter_by(is_active=True).count()
        
        return jsonify({
            'success': True,
            'status': 'healthy',
            'database': db_status,
            'redis': redis_status,
            'active_sessions': active_sessions,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@system_bp.route('/session/fallback', methods=['POST'])
def toggle_fallback_sessions():
    """切换备用会话机制"""
    try:
        data = request.get_json() or {}
        enable = data.get('enable', False)
        
        from flask import session
        session['enable_fallback_sessions'] = bool(enable)
        session.modified = True
        
        return jsonify({
            'success': True,
            'message': f'备用会话机制已{"启用" if enable else "禁用"}',
            'enabled': bool(enable)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@system_bp.route('/session/fallback', methods=['GET'])
def get_fallback_status():
    """获取备用会话机制状态"""
    try:
        from flask import session
        enabled = session.get('enable_fallback_sessions', False)
        
        return jsonify({
            'success': True,
            'enabled': enabled,
            'message': f'备用会话机制{"已启用" if enabled else "已禁用"}'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 