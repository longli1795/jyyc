# -*- coding: utf-8 -*-
"""关闭 SAP GUI「某脚本正试图访问 SAP GUI」提示，供无人值守使用。

只改当前用户 HKCU，等同于：
选项 → 辅助功能与脚本 → 脚本 → 去掉「附加时警告 / 连接时警告」，并启用脚本。
改完必须完全退出 SAP Logon / SAP GUI 再开。
"""
from __future__ import print_function

import os
import sys

REG_PATH = r"Software\SAP\SAPGUI Front\SAP Frontend Server\Security"
VALUES = (
    ("UserScripting", 1, "启用脚本"),
    ("WarnOnAttach", 0, "附加时不弹「某脚本正试图访问 SAP GUI」"),
    ("WarnOnConnection", 0, "连接时不弹脚本警告"),
)


def main():
    try:
        import winreg
    except ImportError:
        print("需要 Windows + winreg")
        return 1

    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_PATH)
    print("HKCU\\" + REG_PATH)
    for name, value, desc in VALUES:
        try:
            old, _ = winreg.QueryValueEx(key, name)
        except OSError:
            old = "(missing)"
        winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, value)
        print("  {} : {} -> {}  ({})".format(name, old, value, desc))
    winreg.CloseKey(key)

    print("")
    print("NEXT=完全退出 SAP Logon 和所有 saplogon/sapgui 窗口，再重新登录 PRD")
    print("然后运行 scripts\\probe_gui_scripting.bat，期望 RESULT=SCRIPTING_USABLE")
    print("若重开后弹窗还在：集团策略可能锁定了这两项，把截图交给信息化，不要用自动点确定绕过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
