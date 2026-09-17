# 已知问题登记（重构中"原样保留"的缺陷）

本轮是**纯结构重构**：为了可验证的"行为等价"，原版的缺陷**不修**，只在下面登记清楚
（位置、成因、可复现证据、修复方向）。修复应在后续单独排期，并同步更新本文与测试。

标记说明：`[保留]` = 行为等价保留；`[偏差]` = 本轮唯一有意引入的差异；`[历史]` = 仓库遗留问题。

---

## 一、翻译源与网络

### #1 requests 不读 Windows 系统代理 `[保留]`
- 位置：`infrastructure/translation/*`（与原 `main.py:97-99, 114` 一致，只传 headers，不传 proxies）。
- 成因：`requests` 只认 `HTTP_PROXY/HTTPS_PROXY/ALL_PROXY` 环境变量，而 Clash Verge 的"系统代理"写的是
  注册表 `HKCU\...\Internet Settings\ProxyServer`。**开着梯子也可能连不上 Google / Lingva**，静默退化到 MyMemory。
- 影响：线路可用性完全取决于进程环境变量；用户很难自查。
- 修复方向：设置项 `proxy`（system / 自定义 / 关闭），system 时读注册表并用 `requests(proxies=...)`。

### #2 每次划词 = 5 路并发跨境请求 `[保留]`
- 位置：`infrastructure/translation/racing.py`（与原 `main.py:262-304` 等价）。
- 成因：竞速不做健康探测，谁先返回有效译文用谁；`TRANSLATE_TIMEOUT=(6,22)`、`TRANSLATE_RETRIES=2`，
  最坏情况一次划词要挂 ~28s 才报错；`cancel_futures` 只能取消尚未起跑的任务。
- 修复方向：成功率/延迟先验排序 + 串行短路 + 探测缓存。

### #3 MyMemory 是翻译记忆库而非机器翻译 `[保留]`
- 证据：本机 `vocab.json` 中存在 `Generally → (无翻译结果)`、`parade → 示威游行,阅兵…;v.游行` 这类输出。
- 成因：免费匿名额度 + 语料库匹配；配额提示混在译文正文里（`MYMEMORY WARNING...`），
  代码靠关键字识别（`infrastructure/translation/mymemory.py:parse_mymemory_response`）。
- 修复方向：把它降级为最后兜底，主通道改用官方 API 或 LLM。

### #4 缓存命中时不显示引擎标签 `[保留]`
- 位置：`racing.py` 竞速前的缓存短路（与原 `main.py:267-270` 一致）→ `engine_label=None`，
  界面不会出现"（X 最快返回）"。这是原版行为，测试 `test_cache_hit_has_no_label` 已固定。
- 影响：同一句话第二次查询时标签消失，用户会以为换了引擎。

---

## 二、界面与交互

### #5 悬浮卡片固定 500×140、2.2 秒后自动消失 `[保留]`
- 位置：`presentation/tk/floating_card.py`（与原 `main.py:729-741` 一致）。
- 影响：查单词时卡片过大留白、查长句时高度不够；鼠标一动或稍一走神内容就没了，不能钉住/拖动/复制。

### #6 悬浮卡片"收录生词本"会把引擎标签写进词表 `[保留，重要]`
- 位置：`presentation/tk/floating_card.py` + `translate_window.py`（原 `main.py:854-861 → 675-678 → 944-947`）。
- 成因：卡片按钮存的是 `TranslationResult.display_text`（含 `\n（Google 最快返回）`），
  经 `clean_text` 折行后落库；而"最近 3 条"的收录按钮存的是干净译文——两处语义不一致。
- 证据：本机 `vocab.json` 中已有 `atmospheric → 大气 的（Google 最快返回）`、`verified → 已验证 （Google 最快返回）` 等条目。
- 修复方向：卡片按钮改存 `result.text`；并写一次性清洗脚本处理历史数据。

### #7 取词会覆盖用户剪贴板且不还原 `[保留]`
- 位置：`infrastructure/input/win32_selection.py`（与原 `main.py:949-964` 一致）。
- 影响：划词翻译会污染用户正在复制的内容；对禁用 Ctrl+C 的界面无效。

### #8 长文本被硬截断且不提示 `[保留]`
- 位置：`application/translate_text.py` + `domain/services/text_cleaning.py`（原 `main.py:44, 976-977`）。
- 影响：`MAX_TEXT_LENGTH=120`，超出直接加 `...`，界面不提示"已截断"——学习场景里长句恰恰最需要翻译。
- 备注：重构后 `TranslationOutcome.truncated` 已把"是否被截断"作为**数据**暴露出来，表示层目前仍按原版不提示，
  将来接提示只需改一处。

### #9 英文自动朗读没有开关 `[保留]`
- 位置：`application/translate_text.py`（原 `main.py:978-985`）：含 ≥2 个拉丁字母就朗读，只能把音量调到 0。
- 成因：原版就没有该设置项。

### #10 8ms 轮询热键（含 Ctrl+L），CPU 常驻开销 `[保留]`
- 位置：`infrastructure/input/win32_hotkeys.py:Win32PollingHotkeyListener`（原 `main.py:1410-1455`）。
- 成因：`Tab+X` 无法用 `RegisterHotKey` 表达，原版统一用 `GetAsyncKeyState` 轮询，
  并有"先 Tab 后 X / 先 X 后 Tab / 同时按"三种边沿兼容逻辑（已原样保留）。
- 附带：原版 **`RegisterHotKey` 消息循环（`main.py:1505-1528`）定义了但从未被启动**——`run()` 里只启动了轮询线程，
  所以"Ctrl + L 注册失败"的提示永远不会出现，`_on_close` 里的 `PostThreadMessageW` 也永远拿不到 thread id。
  重构保留了 `Win32RegisteredHotkeyListener` 实现，但 bootstrap **默认不装配**（等价行为），见 `container.py:hotkey_listener`。

### #11 两处"待补全例句"口径不同 `[保留]`
- `application/generate_examples.py:pending_items` = "英例句或中译任一为空"（原 `vocab_review.py:117-125`）；
- `domain/models/vocab_entry.py:with_example_count` = "两者都不为空"（原 `set.py:31-38`）。
- 影响：同一份词表在复习端与后台管理里显示的"待补全"数字可能不同。重构**显式命名**两种语义，不做合并。

### #12 `apply_grade` 对非数字 `reviews` 抛 ValueError `[保留]`
- 位置：`domain/services/scoring.py:apply_grade`（原 `vocab_review.py:706` 的 `int(it.get("reviews") or 0) + 1`）。
- 说明：等价性由 `tests/test_domain_scoring.py` 固定；不要在重构中"顺手容错"。

### #18 Web 端单词未转义直接拼进 HTML `[保留]`
- 位置：`presentation/web/`（渲染卡片标题处，原 `vocab_review_web.py:408`）。
- 成因：`st.markdown(f"<h1 ...>{word}</h1>", unsafe_allow_html=True)`，词条里若含 HTML 标签会被渲染。
- 影响：词条来自划词翻译结果，通常无害，但属于注入面。

### #19 Web 端批量生成的提示被随后的 `st.rerun()` 吃掉 `[保留]`
- 位置：`presentation/web/`（生成/刷新按钮回调，原 `vocab_review_web.py:311-312, 500-506`）。
- 成因：`_generate_examples()` 内部的 `st.warning` / `st.info` 之后调用方立即 `st.rerun()`，
  页面立刻重绘，用户几乎看不到提示（余额不足、每批完成数等）。
- 影响：402 中止、单条失败等反馈在 Web 端实际不可见（桌面端有弹窗，不受影响）。

---

## 三、性能与工程化

### #13 每次朗读都起一个 PowerShell 进程 `[保留]`
- 位置：`infrastructure/tts/windows_sapi.py`（原 `main.py:1019-1041`、`vocab_review.py:636-659`）。
- 影响：首次朗读数百毫秒延迟、进程噪声；划词场景下每个词都会起一次。

### #14 词表无并发保护，多端同写互相覆盖 `[保留]`
- 位置：`infrastructure/persistence/json_vocabulary.py:save`（先写 `.tmp` 再 `os.replace`，原子但**非并发安全**）。
- 影响：桌面端与 Streamlit 网页端同时评分会 last-write-wins。

### #15 API Key 明文落盘 `[保留]`
- 位置：`infrastructure/persistence/api_key_file.py`（原 `api_key.txt`）。

### #16 OCR 依赖用户自装 Tesseract + 语言包 `[保留]`
- 位置：`infrastructure/ocr/tesseract.py`（语言包探测、`.traineddata` 扫描、`TESSDATA_PREFIX` 修正逻辑全部保留）。
- 影响：装不上或路径被旧版本劫持时，只能看到"OCR 不可用 / 未找到可用语言包"。

### #17 无日志文件、无单实例、无异常上报 `[保留]`
- 运行期只有 `print`（划词窗口）与界面日志区；崩溃无痕迹。

---

## 四、本轮有意引入的偏差 `[偏差]`

| # | 偏差 | 理由与影响 |
|---|---|---|
| D1 | 数据目录支持环境变量 `SNAPTRANSLATE_DATA_DIR`（**默认值不变**） | 便于把数据与代码分离；不设置时行为与原版完全一致 |
| D2 | 新增 `console_scripts` 与 `entrypoints/` 薄壳入口 | 原版 4 个脚本仍可用；不改任何运行逻辑 |
| D3 | 领域异常类型替换原版的裸异常（`VocabularyIoError` 等） | 展示文案逐字保留；`load_strict` 的"是否抛错"语义已由对拍脚本覆盖 |
| D4 | 三种词表加载语义、两种设置写语义被显式命名 | 原版是 4 份/2 份不同实现，合并会改变行为，因此只做命名与收口 |
| D5 | 测试临时目录放在工程内 `.tmp-tests/` | 仅测试用；沙箱环境下子进程可能不可写系统临时目录 |
| D6 | 原版图片素材（`image/*.png`，实为 JPEG）与博客稿未复制 | 与代码结构无关；需要时从原仓库取 |

---

## 五、仓库历史遗留 `[历史]`

| # | 现象 | 说明 |
|---|---|---|
| H1 | README 写 `reset_vocab_scores.py`，实际文件是 `set.py` | 原仓库文档与文件名不一致 |
| H2 | `image/1.png` 等实为 JPEG 字节 | 扩展名与内容不符（浏览器可容错显示） |
| H3 | 原仓库 `__pycache__/quick_select_translate.cpython-310.pyc` | 已删除模块的残留，说明历史上还有"快速划词"模块 |
| H4 | 上游最后提交 2026-05-22，无 release、无打包 | 23 star / 4 fork 的个人项目，不提供预编译产物 |
