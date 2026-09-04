# -*- coding: utf-8 -*-
"""SAP 取数 API：手动触发、状态查询、本机重载期初库存。"""
import os
import subprocess
import sys
import threading
from functools import wraps

from flask import Blueprint, jsonify, request

from app.sap_gui.paths import last_month_period, logs_dir, project_root, read_job_status, write_job_status
from app.utils.auth_utils import login_required, require_can_edit

sap_bp = Blueprint("sap", __name__)

_job_lock = threading.Lock()


def _is_localhost():
    addr = (request.remote_addr or "").strip()
    return addr in ("127.0.0.1", "::1", "localhost")


def _localhost_or(decorator):
    """本机调用与首页按钮同一接口，不要求浏览器登录态。"""

    def wrapper(f):
        decorated = decorator(f)

        @wraps(f)
        def inner(*args, **kwargs):
            if _is_localhost():
                return f(*args, **kwargs)
            return decorated(*args, **kwargs)

        return inner

    return wrapper


def _start_cli_export(period, ingest=True):
    """独立进程跑取数（与手工 CLI 同一条路径），避免 Flask 线程里 COM 拿不到 SAP GUI。"""
    root = project_root()
    script = os.path.join(root, "scripts", "run_sap_monthly_export.py")
    cmd = [sys.executable, script, "--direct", "--period", str(period)]
    if not ingest:
        cmd.append("--skip-ingest")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["SKIP_SCHEDULED_TASKS"] = "1"

    log_path = os.path.join(logs_dir(), "sap_export.log")

    def worker():
        try:
            with open(log_path, "a", encoding="utf-8") as logf:
                logf.write("\n--- UI spawn {} ---\n".format(" ".join(cmd)))
                logf.flush()
                proc = subprocess.Popen(
                    cmd,
                    cwd=root,
                    env=env,
                    stdout=logf,
                    stderr=subprocess.STDOUT,
                )
                code = proc.wait()
            if code != 0:
                status = read_job_status()
                if status.get("running") or status.get("phase") not in ("done", "error"):
                    write_job_status(
                        running=False,
                        phase="error",
                        message="SAP 取数进程失败，退出码 {}".format(code),
                        error="exit {}".format(code),
                    )
        except Exception as e:
            write_job_status(
                running=False,
                phase="error",
                message=str(e),
                error=str(e),
            )

    threading.Thread(target=worker, name="sap-export-cli", daemon=True).start()


@sap_bp.route("/api/sap/status", methods=["GET"])
@_localhost_or(login_required)
def sap_status():
    status = read_job_status()
    status.setdefault("default_period", last_month_period())
    return jsonify({"success": True, "data": status})


@sap_bp.route("/api/sap/export", methods=["POST"])
@_localhost_or(login_required)
@_localhost_or(require_can_edit)
def sap_export():
    payload = request.get_json(silent=True) or {}
    period = (payload.get("period") or "").strip() or last_month_period()
    ingest = payload.get("ingest", True)
    if ingest in ("0", "false", "False"):
        ingest = False

    with _job_lock:
        current = read_job_status()
        if current.get("running"):
            return jsonify({
                "success": False,
                "message": "SAP 取数正在进行中，请稍候",
                "data": current,
            }), 409
        write_job_status(
            running=True,
            phase="queued",
            period=period,
            message="已排队，即将开始导出 {}".format(period),
        )

    _start_cli_export(period, ingest=bool(ingest))
    return jsonify({
        "success": True,
        "message": "已开始从 SAP 导出 {}".format(period),
        "period": period,
    }), 202


@sap_bp.route("/api/opening-inventory/reload-from-disk", methods=["POST"])
def reload_opening_inventory_from_disk():
    """供本机定时脚本在 Redis 不可用时通知运行中的进程重载。"""
    if not _is_localhost():
        return jsonify({"success": False, "message": "仅允许本机调用"}), 403

    from app.services.opening_inventory_store import load_from_disk_into_memory

    ok, msg = load_from_disk_into_memory()
    return jsonify({"success": ok, "message": msg}), 200 if ok else 400
