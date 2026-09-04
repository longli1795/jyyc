# -*- coding: utf-8 -*-
"""一次性把 SAP 账号写入 Windows 凭据管理器，不落盘明文。"""
from __future__ import print_function

import getpass
import os
import sys

TARGET = os.environ.get("SAP_CRED_TARGET", "SAP/PRD")


def main():
    try:
        import win32cred
    except ImportError:
        print("需要 pywin32：pip install pywin32")
        return 1
    user = input("SAP 账号: ").strip()
    password = getpass.getpass("SAP 密码: ")
    if not user or not password:
        print("账号或密码为空")
        return 1
    win32cred.CredWrite(
        {
            "Type": win32cred.CRED_TYPE_GENERIC,
            "TargetName": TARGET,
            "UserName": user,
            "CredentialBlob": password,
            "Comment": "SAP GUI auto login for inventory export",
            "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
        },
        0,
    )
    print("已写入凭据管理器: " + TARGET)
    print("下次取数未登录时会自动用这个账号登录。密码不会出现在脚本里。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
