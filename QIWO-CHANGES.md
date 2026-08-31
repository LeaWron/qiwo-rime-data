# Qiwo 对 rime-frost 的修改

本仓库是 [rime-frost](https://github.com/gaboolic/rime-frost) 的修改版，
按 GPL-3.0 第 5(a) 条在此声明修改内容与日期。上游许可（GPL-3.0）不变，
`LICENSE` 与上游 `README.md` 的著作权与致谢声明原样保留。

**上游基线**：`6af2892b8344cfd792bff4463a0de99b8d0b0125`（`1.0.4-12-g6af2892`）
**首次导入并修改**：2026-08-31

---

## 1. 删除的目录与文件（2026-08-31）

只删不改，删的都是运行时不需要的东西。

| 路径 | 体积 | 理由 |
| --- | --- | --- |
| `others/` | 103 MB | 词库制作原料与工具：`维基频.txt` 36M、`知频.txt` 29M、`zhihu_deal_sort_merge.txt` 20M、`3字统计结果.txt` 14M、`2字词频表.txt` 3.5M，以及 `program/` `script/` `recipes/` `test/` 与 README 配图。librime 运行时不读取其中任何一个字节。 |
| `.github/` | — | 上游的 nightly/release 工作流与 FUNDING.yml。在本仓库会空跑失败，且赞助链接指向上游会造成混淆。 |
| `cn_dicts/tencent.dict.yaml` | 11 MB | 腾讯词向量词库。`rime_frost.dict.yaml` 里这一行本来就是注释掉的（`# - cn_dicts/tencent`），默认方案不加载。 |

删除依据（实证，非推断）：

- 全仓 `*.yaml` / `*.lua` / `*.json` 中对 `others/` 路径的引用只有两处，
  且都是 YAML 注释——`cn_dicts/8105.dict.yaml:20` 与
  `cn_dicts/tencent.dict.yaml:17` 的「需要注音的字词设定在
  others/script/rime/需要注音.txt」。
- `lua/` 下全部 `io.open` / `loadfile` / `dofile` 只读两个文件：
  `lua/aux_code/moqi_aux_code.txt` 与 `cn_dicts/corrections.dict.yaml`，
  都不在 `others/` 内。

### 名字里带 others 但**必须保留**的文件

再导入时若要重写排除规则，请务必用目录前缀 `others/` 匹配，
不要用 `*others*` 之类的通配：

- `cn_dicts/others.dict.yaml` —— 被 `rime_frost.dict.yaml` 的
  `import_tables: - cn_dicts/others` 导入，默认方案的主词典组成部分。
- `opencc/others.txt` —— 被 `opencc/emoji.json` 引用，emoji 转换依赖它。

### 同样**必须保留**的大目录

它们都被 `import_tables` 引用，删掉会导致对应方案编不出词典：

- `cn_dicts_cell/`（45 MB，23 个细胞词库）—— `rime_frost.dict.yaml` 直接依赖，
  **默认方案就用它**。
- `cn_dicts_common/`（4.3 MB）—— `rime_frost_moqi_single_xh.dict.yaml` 依赖。
- `cn_dicts_wb/`（4.3 MB）—— `rime_frost_wubi86.dict.yaml` 依赖。

---

## 2. 代码修改（2026-08-31）

### `lua/corrector.lua`：补共享数据目录回退

原实现只查用户数据目录：

```lua
local file = io.open(rime_api.get_user_data_dir() .. corrections_file, "r")
if not file then
    return corrections        -- 静默返回空表
end
```

Qiwo 五端把分发的词库放在 **共享数据目录**（Android 的
`usr/share/rime-data`、Windows 的 `%INSTDIR%\data`），用户目录只留个人数据
（`user.yaml` / `userdb` / `custom_phrase` / `sync` / `installation.yaml`）。
在这种布局下 `cn_dicts/corrections.dict.yaml` 不在用户目录里，
原实现会静默返回空表，**错音错字提示完全失效且没有任何报错**。

而 `corrector` 是默认方案的一等功能：`rime_frost.schema.yaml` 挂了
`lua_filter@*corrector`，并专门为它配了 `spelling_hints: 8`、
`always_show_comments: true` 与 `comment_format`。

修改后补上共享目录回退，写法与同仓 `lua/aux_lookup_filter.lua`
（上游本来就写对了的那个）保持一致：

```lua
local file = io.open(rime_api.get_user_data_dir() .. corrections_file, "r")
if not file and rime_api.get_shared_data_dir then
    file = io.open(rime_api.get_shared_data_dir() .. corrections_file, "r")
end
if not file then
    return corrections
end
```

全仓 `lua/` 只有这一处存在该问题。

### `default.yaml` 与各方案：内置 Qiwo 的默认开关

以下设置原本由 `init-frost` 在**用户的** `default.custom.yaml` / `*.custom.yaml`
里做字符串拼接注入。那套拼接会在用户手改过配置时毁掉它——例如用户写了
`patch: # 我的配置`，锚点匹配不上，就会再追加一个顶层 `patch:` 键，yaml-cpp
取后者，用户原有的整个 `schema_list` 被静默丢弃。Rust 与 C++ 两侧各有一份
同样的实现，同样的毛病。

改为放在分发层，走 Rime 正确的分层：分发层给默认值，用户在自己的
`*.custom.yaml` 里覆盖，我们只读不写。

| 文件 | 追加 |
| --- | --- |
| `default.yaml` → `switcher/hotkeys` | `- F4` |
| `default.yaml` → `switcher/save_options` | `- auto_commit_spacing` |
| 9 个自带 `switches:` 的 `rime_frost*.schema.yaml` | `auto_commit_spacing` 开关 |

`rime_frost_aux` 与 `rime_frost_t9` 通过 `__include` 继承 `rime_frost.schema.yaml`
的 `switches`，**不要**给它们单独加，否则会重复。

`default.yaml` 的 `schema_list` 本来就以 `rime_frost` 打头，原先注入的那条
`schema_list` patch 是冗余的，一并去掉。

注意：开关未设 `reset`，故初始值为状态 0（关闭），由 `save_options` 记忆。
这与原先注入的行为一致；若要改为默认开启需另行决定。

---

## 3. 为什么是 squash 而不是 fork 完整历史

上游 `.git` 有 351 MB（363 次提交，历史里全是那 103 MB 语料的 blob），
工作树 213 MB。作为子模块被五个平台仓各挂一次，每次克隆约 564 MB。
本仓库以单提交导入 **98.4 MB / 167 文件** 的运行时数据，克隆体积降到约 1/6，
各平台构建脚本也不再需要各自维护一份排除规则。

代价是不能 `git rebase upstream`，上游更新要走下面的再导入流程。
rime-frost 一年更新数次，可以接受。

---

## 4. 再导入上游的流程

1. 克隆或更新一份上游工作副本，检出目标 commit。
2. 把上游工作树复制过来，排除 `.git`、`others/`、`cn_dicts/tencent.dict.yaml`
   （**只按目录前缀 `others/` 排除**，见上文陷阱）。
3. 重新施加第 2 节的**全部**修改（corrector.lua 回退、`default.yaml` 的
   F4 与 save_options、9 个方案的 auto_commit_spacing 开关）；逐条核对是否
   仍然必要（若上游已自行修复，则从本文件移除该条）。
4. 更新本文件的「上游基线」与日期，在下方追加一条导入记录。
5. 单提交提交，commit message 写明上游 commit 与本次改动。
6. 跑一次真机验证：部署成功、候选正常、错音错字提示可见
   （输入 `geiyu` 应在候选注释里看到「给予」的正确读音提示）。

## 导入记录

| 日期 | 上游 commit | 备注 |
| --- | --- | --- |
| 2026-08-31 | `6af2892` | 首次导入；删 `others/` 与 `tencent.dict.yaml`；补 `corrector.lua` 共享目录回退 |
| 2026-08-31 | `6af2892` | 内置 Qiwo 默认开关（`default.yaml` 的 F4 / save_options，9 个方案的 auto_commit_spacing），取代 init-frost 对用户文件的字符串拼接 |

### 10 个白霜系方案：`express_editor` → `fluid_editor`（2026-08-31）

express_editor 的 BackSpace 绑定 `RevertLastEdit`——只有「紧随选词之后」
按退格才回退该次选择，一旦中间发生过光标移动等任何操作就退化为删除
末字符。移动端预编辑点击编辑是一等交互（Qiwo Android 的核心功能），
「选了词 → 移光标 → 想撤销选择」是高频路径，express 语义在此不可用。

fluid_editor 的 BackSpace 绑定 `BackToPreviousInput`：
`ReopenPreviousSegment() || ReopenPreviousSelection() || PopInput()`——
无条件先尝试回退已确认段，与光标状态无关；无段可回退时才删字符。

涉及：`rime_frost*.schema.yaml` 全部 10 个（melt_eng 英文方案与
cangjie5/radical_pinyin 辅助方案保持上游 express_editor 不动）。
