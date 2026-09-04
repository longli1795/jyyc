# -*- coding: utf-8 -*-
"""执行 ZMMR0010N_Y 并导出 xlsx。附加已登录会话，不写密码。"""
from __future__ import print_function

import os
import sys
import time
from datetime import datetime

from app.sap_gui.paths import exports_dir, last_month_period, log

TCODE = os.environ.get("SAP_TCODE", "ZMMR0010N_Y")
COMPANY = os.environ.get("SAP_COMPANY", "N300")


def attach():
    from app.sap_gui.sap_login import attach_or_login

    return attach_or_login()


def wait_idle(sess, timeout=600):
    t0 = time.time()
    while True:
        try:
            busy = bool(sess.Busy)
        except Exception:
            busy = False
        if not busy:
            return
        if time.time() - t0 > timeout:
            raise TimeoutError("等待 SAP 执行超时 {}s".format(timeout))
        time.sleep(0.4)


def find(sess, cid):
    return sess.findById(cid, False)


def set_text(sess, cid, value):
    ctrl = find(sess, cid)
    if ctrl is None:
        raise RuntimeError("找不到控件 " + cid)
    ctrl.Text = value


def set_check(sess, cid, selected=True):
    ctrl = find(sess, cid)
    if ctrl is None:
        raise RuntimeError("找不到复选框 " + cid)
    ctrl.Selected = selected


def on_selection(sess):
    return find(sess, "wnd[0]/usr/ctxtS_BUKRS-LOW") is not None


def on_result(sess):
    return find(sess, "wnd[0]/usr/cntlGRID1/shellcont/shell") is not None


def goto_selection(sess):
    sess.StartTransaction(TCODE)
    wait_idle(sess)
    if on_selection(sess):
        log("started " + TCODE)
        return
    back = find(sess, "wnd[0]/tbar[0]/btn[3]")
    if back is not None:
        try:
            back.press()
            wait_idle(sess)
        except Exception:
            pass
    if not on_selection(sess):
        sess.StartTransaction(TCODE)
        wait_idle(sess)
    if not on_selection(sess):
        raise RuntimeError("无法回到选择屏，请先登录 PRD 并进入 ZMMR0010N_Y")


def fill_and_execute(sess, period):
    log("current tcode={}".format(sess.Info.Transaction))
    if find(sess, "wnd[0]/usr/txtRSYST-BNAME") is not None:
        raise RuntimeError("仍停在 SAP 登录屏，未取数，期初库存不会被覆盖")
    # 已登录但停在上次结果屏时必须重进选择屏并填写本月期间，不能直接导出旧 ALV
    if on_result(sess) or not on_selection(sess):
        log("not on selection, restart {}".format(TCODE))
        goto_selection(sess)
    set_text(sess, "wnd[0]/usr/ctxtS_BUKRS-LOW", COMPANY)
    set_text(sess, "wnd[0]/usr/ctxtP_MONTH", period)
    for cid in (
        "wnd[0]/usr/chkP_NOZERO",
        "wnd[0]/usr/chkP_FXZ",
        "wnd[0]/usr/chkP_E",
        "wnd[0]/usr/chkP_Q",
        "wnd[0]/usr/chkP_K",
        "wnd[0]/usr/chkP_W",
    ):
        set_check(sess, cid, True)
    log("filled bukrs={} period={}".format(COMPANY, period))
    sess.findById("wnd[0]/tbar[1]/btn[8]").press()
    wait_idle(sess)
    log("executed F8, tcode={}".format(sess.Info.Transaction))
    if find(sess, "wnd[0]/usr/txtRSYST-BNAME") is not None:
        raise RuntimeError("执行后又回到登录屏，未取数，期初库存不会被覆盖")
    if not on_result(sess):
        raise RuntimeError("未进入结果屏，未取数，期初库存不会被覆盖")


def export_inventory(period, dest_dir=None):
    """登录/复用会话，导出指定期间原表。返回原表路径。"""
    out_dir = dest_dir or exports_dir()
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    dest = os.path.join(
        out_dir, "E01_{}_{}_{}.xlsx".format(COMPANY, period.replace(".", ""), stamp)
    )
    sess = attach()
    log("attached {} client={}".format(sess.Info.SystemName, sess.Info.Client))
    fill_and_execute(sess, period)

    from app.sap_gui.export_from_result import grid_to_xlsx

    log("export via ALV grid")
    grid_to_xlsx(sess, dest)
    if not (os.path.isfile(dest) and os.path.getsize(dest) > 200):
        raise RuntimeError("FAIL no xlsx in output: " + dest)
    return dest


def main(period=None):
    from app.sap_gui.format_export import polish

    period = period or last_month_period()
    dest = export_inventory(period)
    styled, n_keep, n_all = polish(dest)
    log("PASS raw={} filtered={}/{} -> {}".format(dest, n_keep, n_all, styled))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log("ERROR {}".format(e))
        raise
