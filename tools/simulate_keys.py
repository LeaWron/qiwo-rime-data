#!/usr/bin/env python3
"""用 rime.dll 模拟按键，打印编辑栏与候选——改方案后的本机回归手段（Windows）。

没有 rime_api_console 也能验：librime 导出的是平坦 C API，ctypes 直接调
RimeSimulateKeySequence / RimeGetContext 就够了。为了不碰运行中输入法的
用户词典锁，请把 %APPDATA%/Rime 复制一份（排除 others/、sync/、*.userdb）
当 --user-dir，再把仓库里改过的方案/lua 覆盖进去，用 --full-check 重建。

注意：只有 default.custom.yaml 的 schema_list 里列出的方案才会被重建，
要测的方案不在列表里就先加进去（否则选到的是 build/ 里的旧产物）。

用法：
  python tools/simulate_keys.py --user-dir %TEMP%/rime-test --full-check
      --schema rime_frost unite ushikou "nihao {space}"

按键串语法同 RimeSimulateKeySequence：普通字符直接写，特殊键用 {space}
{Return} {BackSpace} {Escape} 等。每个按键串独立执行：先打印结果，再用
RimeClearComposition 清场（fluid_editor 下 Escape 只回退一步，清不干净会串台）。
--dll 缺省从注册表 HKLM/SOFTWARE/WOW6432Node/Qiwo 的 QiwoRoot 取 rime.dll。
"""

from __future__ import annotations

import argparse
import ctypes
import os
import sys
from ctypes import POINTER, Structure, byref, c_char_p, c_int, c_void_p, sizeof

Bool = c_int
SessionId = ctypes.c_size_t


class RimeTraits(Structure):
    _fields_ = [
        ("data_size", c_int),
        ("shared_data_dir", c_char_p),
        ("user_data_dir", c_char_p),
        ("distribution_name", c_char_p),
        ("distribution_code_name", c_char_p),
        ("distribution_version", c_char_p),
        ("app_name", c_char_p),
        ("modules", POINTER(c_char_p)),
        ("min_log_level", c_int),
        ("log_dir", c_char_p),
        ("prebuilt_data_dir", c_char_p),
        ("staging_dir", c_char_p),
    ]


class RimeComposition(Structure):
    _fields_ = [
        ("length", c_int),
        ("cursor_pos", c_int),
        ("sel_start", c_int),
        ("sel_end", c_int),
        ("preedit", c_char_p),
    ]


class RimeCandidate(Structure):
    _fields_ = [("text", c_char_p), ("comment", c_char_p), ("reserved", c_void_p)]


class RimeMenu(Structure):
    _fields_ = [
        ("page_size", c_int),
        ("page_no", c_int),
        ("is_last_page", Bool),
        ("highlighted_candidate_index", c_int),
        ("num_candidates", c_int),
        ("candidates", POINTER(RimeCandidate)),
        ("select_keys", c_char_p),
    ]


class RimeContext(Structure):
    _fields_ = [
        ("data_size", c_int),
        ("composition", RimeComposition),
        ("menu", RimeMenu),
        ("commit_text_preview", c_char_p),
        ("select_labels", POINTER(c_char_p)),
    ]


class RimeCommit(Structure):
    _fields_ = [("data_size", c_int), ("text", c_char_p)]


def default_dll() -> str:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Qiwo") as k:
            root, _ = winreg.QueryValueEx(k, "QiwoRoot")
        return os.path.join(root, "rime.dll")
    except OSError:
        return "rime.dll"


def dec(b: bytes | None) -> str:
    return (b or b"").decode("utf-8", "replace")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("keys", nargs="+", help="按键串，每个独立执行")
    ap.add_argument("--dll", default=default_dll())
    ap.add_argument("--user-dir", required=True)
    ap.add_argument("--shared-dir", default=None, help="缺省与 --user-dir 相同")
    ap.add_argument("--schema", default="rime_frost")
    ap.add_argument("--full-check", action="store_true", help="强制重建 schema_list 里的方案")
    ap.add_argument("--max-cands", type=int, default=6)
    a = ap.parse_args()

    user = os.path.abspath(a.user_dir)
    shared = os.path.abspath(a.shared_dir) if a.shared_dir else user
    log_dir = os.path.join(user, "log")
    os.makedirs(log_dir, exist_ok=True)

    rime = ctypes.CDLL(a.dll)
    rime.RimeSetup.argtypes = [POINTER(RimeTraits)]
    rime.RimeInitialize.argtypes = [POINTER(RimeTraits)]
    rime.RimeStartMaintenance.argtypes = [Bool]
    rime.RimeStartMaintenance.restype = Bool
    rime.RimeCreateSession.restype = SessionId
    rime.RimeDestroySession.argtypes = [SessionId]
    rime.RimeSelectSchema.argtypes = [SessionId, c_char_p]
    rime.RimeSelectSchema.restype = Bool
    rime.RimeSimulateKeySequence.argtypes = [SessionId, c_char_p]
    rime.RimeSimulateKeySequence.restype = Bool
    rime.RimeGetContext.argtypes = [SessionId, POINTER(RimeContext)]
    rime.RimeGetContext.restype = Bool
    rime.RimeFreeContext.argtypes = [POINTER(RimeContext)]
    rime.RimeGetCommit.argtypes = [SessionId, POINTER(RimeCommit)]
    rime.RimeGetCommit.restype = Bool
    rime.RimeFreeCommit.argtypes = [POINTER(RimeCommit)]
    rime.RimeClearComposition.argtypes = [SessionId]

    traits = RimeTraits()
    traits.data_size = sizeof(RimeTraits) - sizeof(c_int)
    traits.shared_data_dir = shared.encode("utf-8")
    traits.user_data_dir = user.encode("utf-8")
    traits.distribution_name = "齐我输入法".encode("utf-8")
    traits.distribution_code_name = b"Qiwo"
    traits.distribution_version = b"simulate"
    traits.app_name = b"rime.qiwo-simulate"
    traits.min_log_level = 0
    traits.log_dir = log_dir.encode("utf-8")
    rime.RimeSetup(byref(traits))
    rime.RimeInitialize(None)
    if rime.RimeStartMaintenance(1 if a.full_check else 0):
        rime.RimeJoinMaintenanceThread()

    sid = rime.RimeCreateSession()
    print("schema", a.schema, "select:", rime.RimeSelectSchema(sid, a.schema.encode("utf-8")))

    def show(label: str) -> None:
        ctx = RimeContext()
        ctx.data_size = sizeof(RimeContext) - sizeof(c_int)
        if not rime.RimeGetContext(sid, byref(ctx)):
            print(label, "no context")
            return
        cands = []
        for i in range(min(ctx.menu.num_candidates, a.max_cands)):
            c = ctx.menu.candidates[i]
            s = dec(c.text)
            if c.comment:
                s += "<" + dec(c.comment) + ">"
            cands.append(s)
        comp = ctx.composition
        print(
            "%-14s preedit=[%s] sel=%d..%d n=%d cands=%s"
            % (label, dec(comp.preedit), comp.sel_start, comp.sel_end, ctx.menu.num_candidates, " | ".join(cands))
        )
        rime.RimeFreeContext(byref(ctx))

    def commit_text() -> str | None:
        cm = RimeCommit()
        cm.data_size = sizeof(RimeCommit) - sizeof(c_int)
        if rime.RimeGetCommit(sid, byref(cm)):
            t = dec(cm.text)
            rime.RimeFreeCommit(byref(cm))
            return t
        return None

    for keys in a.keys:
        ok = rime.RimeSimulateKeySequence(sid, keys.encode("utf-8"))
        show(keys if ok else keys + " (FAILED)")
        committed = commit_text()
        if committed is not None:
            print("%-14s committed: %r" % ("", committed))
        rime.RimeClearComposition(sid)
    rime.RimeDestroySession(sid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
