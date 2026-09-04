# -*- coding: utf-8 -*-
"""CLI：从 SAP 导出上个月库存并接入期初库存。"""
from __future__ import print_function

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="SAP 物料库存取数并接入期初库存")
    parser.add_argument("--period", help="会计期间 YYYY.MM，默认上个月（北京时间）")
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="只导出筛选，不覆盖期初库存固化文件",
    )
    parser.add_argument(
        "--no-reload-http",
        action="store_true",
        help="写入后不通知正在运行的 Flask 进程",
    )
    parser.add_argument(
        "--via-http",
        action="store_true",
        help="请求本机网站 /api/sap/export，与首页「从 SAP 取数」同一条链路",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="不经过网站，直接跑导出管道（仅排障）",
    )
    return parser.parse_args(argv)


def trigger_homepage_export(period=None, ingest=True):
    """POST /api/sap/export，由已运行的 Flask 进程按按钮逻辑拉起取数。"""
    import json
    import time
    import urllib.error
    import urllib.request

    from app.sap_gui.paths import log

    port = os.environ.get("FLASK_PORT", "8080")
    base = "http://127.0.0.1:{}".format(port)
    body = {}
    if period:
        body["period"] = period
    if not ingest:
        body["ingest"] = False
    payload = json.dumps(body).encode("utf-8")
    url = base + "/api/sap/export"
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else str(e)
        if e.code == 409:
            log("via-http already running: {}".format(raw))
            status = 409
        elif e.code == 401:
            raise RuntimeError(
                "网站返回未登录。请重启一次生产服务以加载本机取数接口，然后再跑定时任务。"
            )
        else:
            raise RuntimeError("网站返回 HTTP {} {}".format(e.code, raw))
    except urllib.error.URLError as e:
        raise RuntimeError(
            "网站未在 {} 运行，定时取数需先启动生产服务: {}".format(base, e.reason)
        )

    log("via-http POST {} -> {} {}".format(url, status, raw[:300]))
    data = {}
    try:
        data = json.loads(raw) if raw else {}
    except ValueError:
        pass
    if status not in (200, 202, 409) or data.get("success") is False:
        raise RuntimeError(data.get("message") or raw or "启动取数失败")

    deadline = time.time() + 15 * 60
    last_phase = ""
    while time.time() < deadline:
        time.sleep(3)
        st_req = urllib.request.Request(base + "/api/sap/status")
        try:
            with urllib.request.urlopen(st_req, timeout=15) as resp:
                info = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as e:
            log("via-http poll status skipped: {}".format(e))
            return 0
        job = (info or {}).get("data") or {}
        phase = job.get("phase") or ""
        if phase != last_phase:
            log("via-http status: {} {}".format(phase, job.get("message") or ""))
            last_phase = phase
        if job.get("running"):
            continue
        if phase == "error":
            raise RuntimeError(job.get("message") or job.get("error") or "SAP 取数失败")
        return 0
    raise RuntimeError("等待 SAP 取数超时")


def main(argv=None):
    args = parse_args(argv)
    from app.sap_gui.paths import last_month_period, log
    from app.sap_gui.pipeline import _ensure_utf8_stdio, run_pipeline

    _ensure_utf8_stdio()

    period = args.period or last_month_period()
    if args.via_http and not args.direct:
        log("CLI via-http period={} ingest={}".format(period, not args.skip_ingest))
        return trigger_homepage_export(period=period, ingest=not args.skip_ingest)

    log("CLI export period={} ingest={}".format(period, not args.skip_ingest))

    if args.skip_ingest:
        result = run_pipeline(
            period=period,
            ingest=False,
            notify_http=False,
        )
        print(result.get("message", "done"))
        return 0

    from app import create_app

    os.environ['SKIP_SCHEDULED_TASKS'] = '1'
    config_name = os.environ.get("FLASK_ENV", "development")
    app = create_app(config_name)
    with app.app_context():
        result = run_pipeline(
            period=period,
            ingest=True,
            notify_http=not args.no_reload_http,
        )
    print(result.get("message", "done"))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("ERROR {}".format(e), file=sys.stderr)
        sys.exit(1)
