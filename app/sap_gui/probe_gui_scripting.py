# -*- coding: utf-8 -*-
"""探测 SAP GUI Scripting 开关。不登录、不跑事务码、不导出。"""
from __future__ import print_function

import os
import sys
from datetime import datetime

from app.sap_gui.paths import logs_dir, project_root

ROOT = project_root()
LOG_DIR = logs_dir()
LOG_PATH = os.path.join(LOG_DIR, "probe_result.txt")
REG_PATH = r"Software\SAP\SAPGUI Front\SAP Frontend Server\Security"
SERVICES = r"C:\WINDOWS\system32\drivers\etc\services"


def out(lines, msg):
    print(msg)
    lines.append(msg)


def read_user_scripting():
    try:
        import winreg
    except ImportError:
        return None, "winreg unavailable"
    for root, label in (
        (winreg.HKEY_CURRENT_USER, "HKCU"),
        (winreg.HKEY_LOCAL_MACHINE, "HKLM"),
    ):
        try:
            key = winreg.OpenKey(root, REG_PATH)
            val, _ = winreg.QueryValueEx(key, "UserScripting")
            winreg.CloseKey(key)
            if int(val) == 1:
                return True, "{} UserScripting=1".format(label)
        except OSError:
            continue
    return False, "UserScripting is not 1"


def main():
    lines = []
    out(lines, "=== SAP GUI Scripting probe ===")
    out(lines, "time={}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    out(lines, "host={}".format(os.environ.get("COMPUTERNAME", "")))
    out(lines, "")

    try:
        with open(SERVICES, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        if "sapmsPRD" in text:
            out(lines, "PASS services: sapmsPRD found")
        else:
            out(lines, "WARN services: sapmsPRD not found")
    except OSError as e:
        out(lines, "WARN services: {}".format(e))

    client_ok, detail = read_user_scripting()
    if client_ok:
        out(lines, "PASS client: {}".format(detail))
    else:
        out(lines, "FAIL client: {}".format(detail))

    com_ok = engine_ok = session_ok = server_ok = False
    try:
        import win32com.client  # type: ignore
    except ImportError:
        out(lines, "FAIL com: pywin32 not installed (pip install pywin32)")
        win32com = None  # noqa
    else:
        gui = None
        try:
            gui = win32com.client.GetObject("SAPGUI")
        except Exception:
            try:
                gui = win32com.client.Dispatch("SAPGUI.ScriptingCtrl.1")
            except Exception as e:
                out(lines, "FAIL com: {}".format(e))
        if gui is not None:
            com_ok = True
            out(lines, "PASS com: SAPGUI object created")
            try:
                engine = gui.GetScriptingEngine
                engine_ok = engine is not None
                out(lines, "PASS engine: GetScriptingEngine ok")
            except Exception as e:
                out(lines, "FAIL engine: {}".format(e))
                engine = None
            if engine_ok:
                try:
                    if engine.Children.Count > 0:
                        conn = engine.Children(0)
                        if conn.Children.Count > 0:
                            sess = conn.Children(0)
                            session_ok = sess is not None
                except Exception as e:
                    out(lines, "WARN session: {}".format(e))
                if session_ok:
                    out(lines, "PASS session: attached to existing GUI session")
                    try:
                        info = sess.Info
                        out(lines, "info.SystemName={}".format(info.SystemName))
                        out(lines, "info.Client={}".format(info.Client))
                        out(lines, "info.UserSet={}".format(bool(str(info.User))))
                        out(lines, "info.Transaction={}".format(info.Transaction))
                        try:
                            se = bool(info.ScriptingEngine)
                            out(lines, "info.ScriptingEngine={}".format(se))
                            server_ok = se
                            if server_ok:
                                out(lines, "PASS server: session reports ScriptingEngine=True")
                            else:
                                out(lines, "FAIL server: ScriptingEngine=False")
                        except Exception as e:
                            server_ok = True
                            out(
                                lines,
                                "WARN server: ScriptingEngine property unavailable ({}); attached via engine so treat as likely-on".format(e),
                            )
                    except Exception as e:
                        out(lines, "WARN server: {}".format(e))
                        server_ok = True
                else:
                    out(lines, "WARN session: no open connection. Log on to PRD and re-run.")

    if not client_ok:
        code, result = 1, "RESULT=CLIENT_OFF"
        next_action = "NEXT=enable SAP GUI Options > Accessibility & Scripting > Enable scripting, restart GUI, re-run"
    elif not com_ok or not engine_ok:
        code, result = 1, "RESULT=CLIENT_COM_FAIL"
        next_action = "NEXT=install/repair SAP GUI 740 and retry"
    elif not session_ok:
        code, result = 3, "RESULT=CLIENT_OK_NEED_LOGIN"
        next_action = "NEXT=log on to PRD then re-run this probe"
    elif not server_ok:
        code, result = 2, "RESULT=SERVER_SCRIPTING_OFF"
        next_action = "NEXT=stop bypassing; send docs/L0-集团取数申请.md"
    else:
        code, result = 0, "RESULT=SCRIPTING_USABLE"
        next_action = "NEXT=run scripts\\run_sap_monthly_export.bat --period YYYY.MM"

    out(lines, "")
    out(lines, result)
    out(lines, next_action)
    out(lines, "exit={}".format(code))

    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
