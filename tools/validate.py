#!/usr/bin/env python3
"""校验这份分发数据的内部一致性。

这个仓库被五个端同时消费（qiwo-win / qiwo-mac / qiwo-lin / qiwo-android，
以及 qiwo-sync-core 的共享目录自检），一个坏掉的 YAML 或一处引用不到的 lua
会同时发给所有客户端，而且往往要到用户机器上部署失败才暴露。

覆盖的都是已经真实发生过、或差一点发生的问题：

* YAML 解析失败——批量改 schema 的脚本用 `\\s*` 匹配缩进时吞掉了前导换行，
  把 rime_frost_wubi86.schema.yaml 改坏过一次，靠人眼才发现。
* schema_list 里的方案没有对应文件。
* 分发的方案缺 auto_commit_spacing 开关——「自动空格状态按设备记忆」全靠它。
* `lua_translator@*foo` 引用了 lua/ 下不存在的脚本。qiwo-lin 的 CMake 就因为
  FILES_MATCHING 里漏了 `*.lua`，装出过一批引用 31 个不存在脚本的方案。
* GPL-3 §4/§5(a)：LICENSE 与改动声明必须在仓库里，各端打包时才拷得到。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - CI 会装上
    sys.exit("需要 PyYAML: pip install pyyaml")

ROOT = Path(__file__).resolve().parent.parent

# Rime 词典是「YAML 头 + `...` + TSV 正文」，整份喂给 YAML 解析器必然失败。
DOC_END = re.compile(r"^\.\.\.\s*$", re.M)

# lua_translator@*date_translator / lua_filter@*corrector@xxx / lua_processor@*v_filter
LUA_REF = re.compile(r"lua_(?:translator|filter|processor|segmentor)@\*([A-Za-z0-9_./]+)")

errors: list[str] = []
warnings: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


class RimeLoader(yaml.SafeLoader):
    """按 librime 用的 yaml-cpp 的宽松度来解析，而不是 PyYAML 的默认严格度。

    这里的目标是「这份数据 librime 读不读得了」，所以凡是 yaml-cpp 接受、
    PyYAML 拒绝的写法都要放行——否则校验器会把上游正常工作的数据判成坏的，
    进而诱使人去「修」根本没坏的东西。
    """


# `calculator: {prefix: =}`（rime_frost_t9 等）。PyYAML 把裸 `=` 解析成 YAML 1.1
# 的 tag:yaml.org,2002:value 并因为没有构造器而报错；yaml-cpp 当普通字符串。
RimeLoader.add_constructor(
    "tag:yaml.org,2002:value", lambda loader, node: loader.construct_scalar(node)
)


def load_yaml(path: Path) -> dict | None:
    """解析一份 Rime YAML。词典只解析 `...` 之前的头部。"""
    text = path.read_text(encoding="utf-8")
    if path.name.endswith(".dict.yaml"):
        m = DOC_END.search(text)
        if not m:
            fail(f"{path.relative_to(ROOT)}: 词典缺少 `...` 文档结束标记")
            return None
        text = text[: m.start()]

    # 上游 rime-frost 的 pin_cand_filter 用字面 tab 作字段分隔符
    # （`- q<TAB>去 其实 岂不是`，7 个方案里都有）。YAML 规范不允许 tab 出现在
    # token 起始位置，PyYAML 的扫描器据此直接报错，而 yaml-cpp 接受并照常工作。
    # 我们只关心结构（switches / schema_list / lua 引用），把 tab 当空白处理，
    # 既不改数据也不会把正常数据判成坏的。
    text = text.replace("\t", " ")

    try:
        return yaml.load(text, Loader=RimeLoader)
    except yaml.YAMLError as exc:
        fail(f"{path.relative_to(ROOT)}: YAML 解析失败: {exc}")
        return None


def check_all_yaml_parses() -> dict[Path, dict]:
    parsed: dict[Path, dict] = {}
    for path in sorted(ROOT.rglob("*.yaml")):
        if ".git" in path.parts:
            continue
        doc = load_yaml(path)
        if isinstance(doc, dict):
            parsed[path] = doc
        elif doc is not None:
            fail(f"{path.relative_to(ROOT)}: 顶层不是映射")
    return parsed


def check_default_yaml(parsed: dict[Path, dict]) -> list[str]:
    """返回 schema_list 里分发的方案 id。"""
    default = parsed.get(ROOT / "default.yaml")
    if default is None:
        fail("default.yaml 缺失或无法解析")
        return []

    switcher = default.get("switcher") or {}
    if "F4" not in (switcher.get("hotkeys") or []):
        fail("default.yaml: switcher/hotkeys 缺少 F4（Qiwo 的方案选单热键）")

    save_options = switcher.get("save_options") or []
    if "auto_commit_spacing" not in save_options:
        fail(
            "default.yaml: switcher/save_options 缺少 auto_commit_spacing。"
            "这是「自动空格状态按设备记忆」的唯一机制，缺了开关一关机就忘。"
        )

    ids = [e["schema"] for e in (default.get("schema_list") or []) if isinstance(e, dict) and "schema" in e]
    if not ids:
        fail("default.yaml: schema_list 为空")
    return ids


def resolve_switch(schema_id: str, parsed: dict[Path, dict], seen: set[str]) -> bool:
    """方案自身或其 __include 链上是否定义了 auto_commit_spacing 开关。"""
    if schema_id in seen:
        return False
    seen.add(schema_id)

    path = ROOT / f"{schema_id}.schema.yaml"
    doc = parsed.get(path)
    if doc is None:
        return False

    for sw in doc.get("switches") or []:
        if isinstance(sw, dict) and sw.get("name") == "auto_commit_spacing":
            states = sw.get("states") or []
            if len(states) != 2:
                fail(f"{path.name}: auto_commit_spacing 的 states 应有 2 项，实际 {len(states)}")
            return True

    # `__include: rime_frost.schema.yaml:/` 或 `__include: bopomofo.schema:/`
    inc = doc.get("__include")
    if isinstance(inc, str):
        base = inc.split(":")[0].removesuffix(".schema.yaml").removesuffix(".schema")
        return resolve_switch(base, parsed, seen)
    return False


def check_distributed_schemas(ids: list[str], parsed: dict[Path, dict]) -> None:
    for schema_id in ids:
        path = ROOT / f"{schema_id}.schema.yaml"
        if not path.exists():
            fail(f"default.yaml 的 schema_list 引用了不存在的方案: {path.name}")
            continue
        if not resolve_switch(schema_id, parsed, set()):
            fail(
                f"{path.name}: 分发的方案没有 auto_commit_spacing 开关"
                "（自身或 __include 链上都没有），该方案下自动空格无法切换也无法记忆"
            )


def check_lua_references() -> None:
    lua_dir = ROOT / "lua"
    for path in sorted(ROOT.glob("*.schema.yaml")):
        text = path.read_text(encoding="utf-8")
        for name in sorted(set(LUA_REF.findall(text))):
            # `*corrector@xxx` 这类带参数的，取 @ 之前的脚本名
            script = name.split("@")[0]
            candidates = [lua_dir / f"{script}.lua", lua_dir / script / "init.lua"]
            if not any(c.exists() for c in candidates):
                fail(f"{path.name}: 引用了不存在的 lua 脚本 lua/{script}.lua")


def check_license_files() -> None:
    # 数据是 GPL-3.0：§4 要求许可证随分发，§5(a) 要求声明改动。
    # 各端打包时从这里拷（build.bat 的 LICENSE.rime-data.txt、CMake 的
    # install(FILES ... RENAME)、Makefile 的 stage-shared-data），源头缺了就都缺。
    for name in ("LICENSE", "QIWO-CHANGES.md"):
        if not (ROOT / name).exists():
            fail(f"缺少 {name}（GPL-3 §4/§5(a) 要求随分发提供）")


def check_opencc_present() -> None:
    # librime 在 shared_data_dir 下找 opencc/。各端都直接分发这一份。
    required = ["TSCharacters.ocd2", "TSPhrases.ocd2", "STCharacters.ocd2"]
    missing = [n for n in required if not (ROOT / "opencc" / n).exists()]
    if missing:
        fail(f"opencc/ 缺少标准转换数据: {', '.join(missing)}")


def main() -> int:
    parsed = check_all_yaml_parses()
    ids = check_default_yaml(parsed)
    check_distributed_schemas(ids, parsed)
    check_lua_references()
    check_license_files()
    check_opencc_present()

    print(f"解析了 {len(parsed)} 份 YAML，分发方案 {len(ids)} 个: {', '.join(ids)}")
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}", file=sys.stderr)
    if errors:
        print(f"\n{len(errors)} 项检查未通过", file=sys.stderr)
        return 1
    print("全部检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
