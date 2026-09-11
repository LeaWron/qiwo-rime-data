#!/usr/bin/env python3
"""给 symbols_v.yaml 的每个 'vXX' 键补上同值的 '/XX' 键（反之亦然），幂等。

符号触发有两种前缀：全拼系用 v（手机软键盘打不出 /，2026-09-01 改的），桌面老习惯
和双拼系用 /（v 在双拼里是声母键）。两种前缀同时可用的前提是符号表两种键都有，
本脚本维护这一点，tools/validate.py 检查它没有漂移。以后改符号表只改一种写法，
然后跑本脚本即可：

  python tools/symbols_dual_prefix.py          # 补齐
  python tools/symbols_dual_prefix.py --check  # 只检查，缺就报错退出 1

按行处理、不重排文件：新键紧跟在原键后面，原有注释与顺序原样保留。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "symbols_v.yaml"
KEY_LINE = re.compile(r"^(?P<indent>[ \t]*)'(?P<prefix>[v/])(?P<rest>[^']+)':(?P<value>.*)$")


def main() -> int:
    check_only = "--check" in sys.argv[1:]
    text = TARGET.read_text(encoding="utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)

    # 上游文件里有重复键（如 'vaa' 出现两次，YAML 取最后一个）。要让 '/aa' 与 'vaa'
    # 解析结果一致，每一处出现都要紧跟一个同值的孪生键，而不是全文只补一次。
    # 幂等判据是「相邻行已经是孪生键」，与键在别处是否出现过无关。
    out: list[str] = []
    added: list[str] = []
    for i, line in enumerate(lines):
        out.append(line)
        m = KEY_LINE.match(line)
        if not m:
            continue
        if not m.group("value").strip():
            print(f"warning: {m.group('prefix')}{m.group('rest')} 的值不在同一行，跳过", file=sys.stderr)
            continue
        twin = ("/" if m.group("prefix") == "v" else "v") + m.group("rest")
        twin_line = f"{m.group('indent')}'{twin}':{m.group('value')}"
        before = lines[i - 1] if i > 0 else None
        after = lines[i + 1] if i + 1 < len(lines) else None
        if twin_line in (before, after):
            continue
        out.append(twin_line)
        added.append(twin)

    if not added:
        print("symbols_v.yaml: 两种前缀的键已齐全")
        return 0
    if check_only:
        print(f"symbols_v.yaml: 缺 {len(added)} 个键，例如 {added[:5]}；跑 tools/symbols_dual_prefix.py 补齐")
        return 1
    TARGET.write_text(newline.join(out), encoding="utf-8", newline="")
    print(f"symbols_v.yaml: 补了 {len(added)} 个键，例如 {added[:5]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
