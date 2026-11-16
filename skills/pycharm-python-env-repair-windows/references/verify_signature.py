"""
验证 PE 文件的 Authenticode 数字签名（纯 ctypes 调 WinVerifyTrust，不依赖 PowerShell）。

为什么需要它：本机 PowerShell 工具输出为空、且从 bash 调用 powershell 被安全策略拦截，
而"下载来源可信"是本项目的硬性要求（用户明确要求"严格从官网下载"）。
数字签名验证比比对哈希更强：它同时证明 ①文件未被篡改 ②签名证书链受系统信任。

用法:
    python verify_signature.py <文件1> [文件2 ...]

返回码: 0 全部通过 / 1 存在未通过
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

# 已验证的通用校验动作 GUID
# {00AAC56B-CD44-11d0-8CC2-00C04FC295EE}
WINTRUST_ACTION_GENERIC_VERIFY_V2 = (
    0x00AAC56B,
    0xCD44,
    0x11D0,
    (0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE),
)

WTD_UI_NONE = 2
WTD_REVOKE_NONE = 0
WTD_CHOICE_FILE = 1
WTD_STATEACTION_VERIFY = 1
WTD_STATEACTION_CLOSE = 2
WTD_CACHE_ONLY_URL_RETRIEVAL = 0x00001000
WTD_SAFER_FLAG = 0x00000100

TRUST_E_NOSIGNATURE = -2146762496  # 0x800B0100
TRUST_E_SUBJECT_FORM_UNKNOWN = -2146762749
TRUST_E_PROVIDER_UNKNOWN = -2146762751


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class WINTRUST_FILE_INFO(ctypes.Structure):
    _fields_ = [
        ("cbStruct", wintypes.DWORD),
        ("pcwszFilePath", wintypes.LPCWSTR),
        ("hFile", wintypes.HANDLE),
        ("pgKnownSubject", ctypes.POINTER(GUID)),
    ]


class WINTRUST_DATA(ctypes.Structure):
    _fields_ = [
        ("cbStruct", wintypes.DWORD),
        ("pPolicyCallbackData", ctypes.c_void_p),
        ("pSIPClientData", ctypes.c_void_p),
        ("dwUIChoice", wintypes.DWORD),
        ("fdwRevocationChecks", wintypes.DWORD),
        ("dwUnionChoice", wintypes.DWORD),
        ("pFile", ctypes.POINTER(WINTRUST_FILE_INFO)),
        ("dwStateAction", wintypes.DWORD),
        ("hWVTStateData", wintypes.HANDLE),
        ("pwszURLReference", wintypes.LPWSTR),
        ("dwProvFlags", wintypes.DWORD),
        ("dwUIContext", wintypes.DWORD),
        ("pSignatureSettings", ctypes.c_void_p),
    ]


def verify(path: str) -> tuple[bool, int]:
    """校验签名。返回 (是否通过, WinVerifyTrust 返回码)。"""
    wintrust = ctypes.WinDLL("wintrust", use_last_error=True)
    wintrust.WinVerifyTrust.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(GUID),
        ctypes.c_void_p,
    ]
    wintrust.WinVerifyTrust.restype = ctypes.c_long

    action = GUID(
        WINTRUST_ACTION_GENERIC_VERIFY_V2[0],
        WINTRUST_ACTION_GENERIC_VERIFY_V2[1],
        WINTRUST_ACTION_GENERIC_VERIFY_V2[2],
        (ctypes.c_ubyte * 8)(*WINTRUST_ACTION_GENERIC_VERIFY_V2[3]),
    )

    file_info = WINTRUST_FILE_INFO()
    file_info.cbStruct = ctypes.sizeof(WINTRUST_FILE_INFO)
    file_info.pcwszFilePath = path
    file_info.hFile = None
    file_info.pgKnownSubject = None

    data = WINTRUST_DATA()
    data.cbStruct = ctypes.sizeof(WINTRUST_DATA)
    data.pPolicyCallbackData = None
    data.pSIPClientData = None
    data.dwUIChoice = WTD_UI_NONE
    data.fdwRevocationChecks = WTD_REVOKE_NONE
    data.dwUnionChoice = WTD_CHOICE_FILE
    data.pFile = ctypes.pointer(file_info)
    data.dwStateAction = WTD_STATEACTION_VERIFY
    data.hWVTStateData = None
    data.pwszURLReference = None
    data.dwProvFlags = WTD_CACHE_ONLY_URL_RETRIEVAL
    data.dwUIContext = 0
    data.pSignatureSettings = None

    rc = wintrust.WinVerifyTrust(None, ctypes.byref(action), ctypes.byref(data))

    # 关闭状态句柄，释放资源
    data.dwStateAction = WTD_STATEACTION_CLOSE
    wintrust.WinVerifyTrust(None, ctypes.byref(action), ctypes.byref(data))
    return rc == 0, rc


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    all_ok = True
    for p in argv[1:]:
        ok, rc = verify(p)
        name = p.split("/")[-1].split("\\")[-1]
        if ok:
            print(f"[通过] 签名有效、证书链可信 : {name}")
        else:
            all_ok = False
            if rc == TRUST_E_NOSIGNATURE:
                reason = "文件没有数字签名"
            else:
                reason = f"校验失败，WinVerifyTrust 返回码 {rc} (0x{rc & 0xFFFFFFFF:08X})"
            print(f"[未通过] {reason} : {name}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
