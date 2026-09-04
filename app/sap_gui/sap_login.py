# -*- coding: utf-8 -*-
"""自动打开 PRD 并登录。Logon 750 不用 OpenConnection（会卡在连接列表）。"""
from __future__ import print_function

import os
import subprocess
import time

from app.sap_gui.paths import log as _path_log, secrets_path

CRED_TARGET = os.environ.get("SAP_CRED_TARGET", "SAP/PRD")
DEFAULT_CONNECTION = os.environ.get("SAP_CONNECTION", "[p1 PRD")
DEFAULT_CLIENT = os.environ.get("SAP_CLIENT", "800")
DEFAULT_LANG = os.environ.get("SAP_LANGUAGE", "ZH")
DEFAULT_SID = os.environ.get("SAP_SYSTEM", "PRD")

GUI_DIR_CANDIDATES = (
    os.path.dirname(os.environ.get("SAPLOGON_EXE", "")) if os.environ.get("SAPLOGON_EXE") else "",
    r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui",
    r"C:\Program Files\SAP\FrontEnd\SAPgui",
)


def _log(msg):
    _path_log(msg)


def _ini():
    path = secrets_path()
    if not os.path.isfile(path):
        return {}
    try:
        import configparser

        cfg = configparser.ConfigParser()
        cfg.read(path, encoding="utf-8")
        return {
            "connection": cfg.get("sap", "connection", fallback="").strip(),
            "client": cfg.get("sap", "client", fallback="").strip(),
            "language": cfg.get("sap", "language", fallback="").strip(),
            "user": cfg.get("sap", "user", fallback="").strip(),
            "password": cfg.get("sap", "password", fallback=""),
            "system": cfg.get("sap", "system", fallback="").strip(),
        }
    except Exception:
        return {}


def load_credentials():
    user = os.environ.get("SAP_USER", "").strip()
    password = os.environ.get("SAP_PASSWORD", "")
    if user and password:
        return user, password, "env"

    ini = _ini()
    if ini.get("user") and ini.get("password"):
        return ini["user"], ini["password"], "secrets.ini"

    try:
        import win32cred

        info = win32cred.CredRead(CRED_TARGET, win32cred.CRED_TYPE_GENERIC)
        user = (info.get("UserName") or "").strip()
        blob = info.get("CredentialBlob") or b""
        if isinstance(blob, bytes):
            password = blob.decode("utf-16-le", errors="ignore").rstrip("\x00")
        else:
            password = str(blob)
        if user and password:
            return user, password, "Credential Manager " + CRED_TARGET
    except Exception:
        pass

    raise RuntimeError(
        "未找到账号密码。先运行 python scripts\\set_sap_credential.py"
    )


def _gui_file(name):
    for folder in GUI_DIR_CANDIDATES:
        if not folder:
            continue
        path = os.path.join(folder, name)
        if os.path.isfile(path):
            return path
    return None


def _find(sess, cid):
    return sess.findById(cid, False)


def _wait_idle(sess, timeout=120):
    t0 = time.time()
    while True:
        try:
            busy = bool(sess.Busy)
        except Exception:
            busy = False
        if not busy:
            return
        if time.time() - t0 > timeout:
            raise TimeoutError("登录等待超时")
        time.sleep(0.3)


def get_engine():
    import win32com.client

    last = None
    for factory in (
        lambda: win32com.client.GetObject("SAPGUI"),
        lambda: win32com.client.Dispatch("SAPGUI.ScriptingCtrl.1"),
    ):
        try:
            gui = factory()
            if gui is None:
                continue
            engine = gui.GetScriptingEngine
            if engine is not None:
                return engine
        except Exception as e:
            last = e
            continue
    get_engine.last_error = last
    return None


get_engine.last_error = None


def wait_engine(timeout=40):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        engine = get_engine()
        if engine is not None:
            return engine
        last = getattr(get_engine, "last_error", None)
        time.sleep(0.8)
    raise RuntimeError("拿不到 SAPGUI Scripting: {}".format(last))


def existing_session(engine):
    try:
        if engine is None or engine.Children.Count < 1:
            return None
        conn = engine.Children(0)
        if conn.Children.Count < 1:
            return None
        sess = conn.Children(0)
        if _find(sess, "wnd[0]/usr/txtRSYST-BNAME") is not None:
            return None
        return sess
    except Exception:
        return None


def wait_gui_session(timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        engine = get_engine()
        if engine is None:
            time.sleep(0.6)
            continue
        try:
            if engine.Children.Count > 0 and engine.Children(0).Children.Count > 0:
                return engine.Children(0).Children(0)
        except Exception:
            pass
        time.sleep(0.6)
    return None


def start_saplogon():
    engine = get_engine()
    if engine is not None:
        return engine
    exe = _gui_file("saplogon.exe")
    if not exe:
        raise RuntimeError("找不到 saplogon.exe")
    _log("start " + exe)
    subprocess.Popen([exe])
    return wait_engine(45)


def connection_names():
    # sapshcut / OpenConnection 认的是「系统描述」，本机 Logon 里是 [p1 PRD 而不是名称 PRD
    names = []
    ini = _ini()
    for item in (
        os.environ.get("SAP_CONNECTION", "").strip(),
        ini.get("connection"),
        DEFAULT_CONNECTION,
        "[p1 PRD",
    ):
        if item and item not in names:
            names.append(item)
    return names


def _enum_windows(match):
    import win32gui

    found = []

    def _cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd) or ""
        if match(title):
            found.append((hwnd, title))

    win32gui.EnumWindows(_cb, None)
    return found


def _close_sap_message_boxes():
    import win32con
    import win32gui

    for hwnd, title in _enum_windows(lambda t: t.strip() == "SAP GUI"):
        _log("close dialog: " + title)
        try:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        except Exception:
            pass
    time.sleep(0.4)


def _activate(hwnd):
    import win32con
    import win32gui

    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


def _open_via_logon_button():
    """SAP Logon 750 已选中 PRD 时，点「登录(O)」打开登录屏。"""
    import win32com.client

    _close_sap_message_boxes()
    wins = _enum_windows(lambda t: "SAP Logon" in t)
    if not wins:
        _log("SAP Logon window not found")
        return None
    hwnd, title = wins[0]
    _log("click Logon on " + title)
    if not _activate(hwnd):
        _log("cannot focus SAP Logon")
    time.sleep(0.4)
    shell = win32com.client.Dispatch("WScript.Shell")
    shell.AppActivate(title)
    time.sleep(0.2)
    # 按钮快捷键是 登录(O)
    shell.SendKeys("%o")
    sess = wait_gui_session(20)
    if sess is not None:
        return sess
    _activate(hwnd)
    time.sleep(0.2)
    shell.SendKeys("{ENTER}")
    return wait_gui_session(20)


def _open_via_scripting(engine):
    import threading

    result = {"conn": None, "err": None}

    def _call(name):
        try:
            result["conn"] = engine.OpenConnection(name, True)
        except Exception as e:
            result["err"] = e

    for name in connection_names():
        _log("OpenConnection " + name)
        result["conn"] = result["err"] = None
        th = threading.Thread(target=_call, args=(name,))
        th.daemon = True
        th.start()
        th.join(18)
        if th.is_alive():
            _log("OpenConnection timeout: " + name)
            continue
        if result["conn"] is not None:
            return result["conn"]
        _log("OpenConnection fail {}: {}".format(name, result["err"]))
    return None


def _radio_text(ctrl):
    for attr in ("Text", "Tooltip", "Name"):
        try:
            val = getattr(ctrl, attr)
            if val:
                return str(val)
        except Exception:
            continue
    return ""


def _handle_multi_logon(sess):
    """处理「多次登录许可证信息」。本环境不允许同时在线，只能结束其他登录。"""
    wnd = _find(sess, "wnd[1]")
    if wnd is None:
        return False
    radios = []
    for i in range(1, 6):
        ctrl = _find(sess, "wnd[1]/usr/radMULTI_LOGON_OPT{}".format(i))
        if ctrl is not None:
            radios.append(ctrl)
    if not radios:
        return False

    chosen = None
    for ctrl in radios:
        text = _radio_text(ctrl)
        if "终止此次" in text:
            continue
        if "结束" in text or "继续此登录" in text:
            chosen = ctrl
            break
    if chosen is None:
        chosen = _find(sess, "wnd[1]/usr/radMULTI_LOGON_OPT1") or radios[0]
    try:
        chosen.Select()
    except Exception:
        try:
            chosen.select()
        except Exception as e:
            _log("cannot select multi-logon option: {}".format(e))
            return False
    _log("multi-logon: continue this login and end other sessions")
    btn = _find(sess, "wnd[1]/tbar[0]/btn[0]")
    try:
        if btn is not None:
            btn.press()
        else:
            wnd.sendVKey(0)
    except Exception:
        try:
            wnd.sendVKey(0)
        except Exception as e:
            _log("confirm multi-logon failed: {}".format(e))
            return False
    _wait_idle(sess)
    return True


def _dismiss_after_login(sess):
    t0 = time.time()
    while time.time() - t0 < 8:
        if _handle_multi_logon(sess):
            break
        if _find(sess, "wnd[1]") is None:
            break
        time.sleep(0.3)

    for _ in range(4):
        if _find(sess, "wnd[1]") is None:
            break
        if _handle_multi_logon(sess):
            continue
        btn = _find(sess, "wnd[1]/tbar[0]/btn[0]")
        if btn is None:
            break
        try:
            btn.press()
            _wait_idle(sess)
        except Exception:
            break


def fill_login(sess, user, password):
    _wait_idle(sess)
    _dismiss_after_login(sess)
    if _find(sess, "wnd[0]/usr/txtRSYST-BNAME") is None:
        _log("already past login screen")
        return sess

    ini = _ini()
    client = ini.get("client") or DEFAULT_CLIENT
    lang = ini.get("language") or DEFAULT_LANG
    mandt = _find(sess, "wnd[0]/usr/txtRSYST-MANDT")
    if mandt is not None:
        mandt.Text = client
    _find(sess, "wnd[0]/usr/txtRSYST-BNAME").Text = user
    _find(sess, "wnd[0]/usr/pwdRSYST-BCODE").Text = password
    lang_ctrl = _find(sess, "wnd[0]/usr/txtRSYST-LANGU")
    if lang_ctrl is not None:
        lang_ctrl.Text = lang
    sess.findById("wnd[0]").sendVKey(0)
    _wait_idle(sess)
    _dismiss_after_login(sess)
    if _find(sess, "wnd[0]/usr/txtRSYST-BNAME") is not None:
        raise RuntimeError("仍停在登录屏，请核客户端号/账号/密码")
    _log("logged on client={} user={}".format(client, user))
    return sess


def login_session(engine, user, password):
    sess = wait_gui_session(2)
    if sess is None:
        _log("no GUI session, click SAP Logon 登录")
        sess = _open_via_logon_button()
    if sess is None and engine is not None:
        conn = _open_via_scripting(engine)
        if conn is not None and conn.Children.Count > 0:
            sess = conn.Children(0)
    if sess is None:
        raise RuntimeError(
            "未能从 SAP Logon 打开 PRD。请先关掉黄色报错框，确认连接列表已选中 PRD，再重跑。"
        )
    return fill_login(sess, user, password)


def attach_or_login():
    engine = start_saplogon()
    sess = existing_session(engine)
    if sess is not None:
        _log("reuse existing session")
        return sess
    user, password, src = load_credentials()
    _log("credentials from " + src)
    return login_session(engine, user, password)
