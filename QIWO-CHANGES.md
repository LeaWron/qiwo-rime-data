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
3. 重新施加第 2 节的代码修改；逐条核对是否仍然必要
   （若上游已自行修复，则从本文件移除该条）。
4. 更新本文件的「上游基线」与日期，在下方追加一条导入记录。
5. 单提交提交，commit message 写明上游 commit 与本次改动。
6. 跑一次真机验证：部署成功、候选正常、错音错字提示可见
   （输入 `geiyu` 应在候选注释里看到「给予」的正确读音提示）。

## 导入记录

| 日期 | 上游 commit | 备注 |
| --- | --- | --- |
| 2026-08-31 | `6af2892` | 首次导入；删 `others/` 与 `tencent.dict.yaml`；补 `corrector.lua` 共享目录回退 |
