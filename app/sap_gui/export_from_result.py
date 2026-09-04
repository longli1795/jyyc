# -*- coding: utf-8 -*-
"""从 ZMMR0010N_Y 结果 ALV 滚动读取并写 xlsx。不依赖本机 Excel。"""
from __future__ import print_function

import os
import time
import zipfile
from xml.sax.saxutils import escape

from app.sap_gui.paths import exports_dir, log


OUT_DIR = exports_dir()


def find(sess, cid):
    return sess.findById(cid, False)


def write_xlsx(path, headers, rows):
    def col_name(idx):
        s = ""
        n = idx
        while n > 0:
            n, r = divmod(n - 1, 26)
            s = chr(65 + r) + s
        return s

    def cell_xml(r, c, value):
        ref = "{}{}".format(col_name(c), r)
        text = "" if value is None else str(value)
        return '<c r="{}" t="inlineStr"><is><t>{}</t></is></c>'.format(ref, escape(text))

    sheet_rows = []
    for r, row in enumerate([headers] + rows, 1):
        cells = "".join(cell_xml(r, c, v) for c, v in enumerate(row, 1))
        sheet_rows.append('<row r="{}">{}</row>'.format(r, cells))

    workbook = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="物料库存" sheetId="1" r:id="rId1"/></sheets>
</workbook>
"""
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>{}</sheetData></worksheet>"
    ).format("".join(sheet_rows))
    ctypes = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
"""
    wb_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>
"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", ctypes)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet)


def _alv_visible_count(grid):
    try:
        n = int(grid.VisibleRowCount)
        if n > 0:
            return n
    except Exception:
        pass
    return 20


def _alv_bring_row(grid, row_index, total, first_col=None):
    vis = _alv_visible_count(grid)
    top = row_index
    if top + vis > total:
        top = max(0, total - vis)
    if first_col:
        try:
            grid.setCurrentCell(row_index, first_col)
        except Exception:
            pass
    for setter in (
        lambda: setattr(grid, "firstVisibleRow", top),
        lambda: setattr(grid, "currentCellRow", row_index),
    ):
        try:
            setter()
            return
        except Exception:
            continue
    try:
        grid.verticalScrollbar.position = top
    except Exception:
        pass


def grid_to_xlsx(sess, dest):
    grid = find(sess, "wnd[0]/usr/cntlGRID1/shellcont/shell")
    if grid is None:
        raise RuntimeError("结果屏没有 ALV 表格")
    rows = int(grid.RowCount)
    cols = int(grid.ColumnCount)
    vis = _alv_visible_count(grid)
    log("ALV rows={} cols={} visible={}".format(rows, cols, vis))
    names = []
    try:
        names = list(grid.ColumnOrder)
    except Exception:
        names = []
    if not names:
        names = [grid.GetColumnName(i) for i in range(cols)]
    headers = []
    for name in names:
        title = name
        try:
            title = grid.GetColumnTitles(name)[0]
        except Exception:
            try:
                title = str(grid.GetDisplayedColumnTitle(name))
            except Exception:
                title = str(name)
        headers.append(title)
    data = []
    nonempty = 0
    for r in range(rows):
        if r % vis == 0:
            _alv_bring_row(grid, r, rows, names[0] if names else None)
            time.sleep(0.05)
        line = []
        for name in names:
            try:
                line.append(grid.GetCellValue(r, name))
            except Exception:
                line.append("")
        if any(str(c).strip() for c in line):
            nonempty += 1
        data.append(line)
        if r and r % 200 == 0:
            log("read {}/{} nonempty={}".format(r, rows, nonempty))
    write_xlsx(dest, headers, data)
    log("wrote {} rows nonempty={} -> {}".format(rows, nonempty, dest))
    if rows > vis * 2 and nonempty <= vis + 2:
        raise RuntimeError("ALV 只读到可视行 {}/{}".format(nonempty, rows))
