# 已知问题登记（重构中"原样保留"的缺陷）

阶段一是**纯结构重构**：为了可验证的"行为等价"，原版的缺陷**不修**，只在下面登记清楚
（位置、成因、可复现证据、修复方向）。

**但阶段一之后有八处主动修复/改动**（用户实测后要求，属于有意偏离原版）：
取词失败被静默吞掉（#20）、界面改热键要重启才生效（#21）、热键里的 Alt/Shift 会"毒化"注入的 Ctrl+C（#22）、
悬浮卡片改为按"热键按下瞬间"的鼠标位置显示（#23）、卡片不再定时消失而是等用户下一次按键/点鼠标（#24）、
新增代理设置（#25）、**砍掉两条失效线路 + 引擎标签只进日志不进卡片（#26/#27）**
——见 §五 `[修复]`。修完仍有回归测试兜底，其余条目状态不变。

标记说明：`[保留]` = 行为等价保留；`[修复]` = 已主动修掉（偏离原版，配回归测试）；
`[偏差]` = 本轮有意引入的差异；`[历史]` = 仓库遗留问题；
`[已缓解]` / `[已修]` / `[已失效]` = 后续修复（F1–F8）带来的状态变化，括号内指向对应条目。

---

## 一、翻译源与网络

### #1 requests 不读 Windows 系统代理 `[已提供开关 → 见 #25]`
- 位置：`infrastructure/network/http.py`（所有翻译请求统一走这里）。
- 原状：`requests` 只认 `HTTP_PROXY/HTTPS_PROXY` 环境变量，而 Clash Verge 的"系统代理"写的是
  注册表 `HKCU\...\Internet Settings\ProxyServer`，于是"开着梯子也用不上"。
- 现在：新增代理设置（直连 / 跟随系统代理 / 自定义，见 §五 F6 #25），请求层按策略走代理；
  仍保留"代理连不上自动回退直连"。

### #2 每次划词 = 5 路并发跨境请求 `[已缓解 → 见 F7/#26]`
- 位置：`infrastructure/translation/racing.py`（与原 `main.py:262-304` 等价）。
- 成因：竞速不做健康探测，谁先返回有效译文用谁；`TRANSLATE_TIMEOUT=(6,22)`、`TRANSLATE_RETRIES=2`，
  最坏情况一次划词要挂 ~28s 才报错；`cancel_futures` 只能取消尚未起跑的任务。
- 现状：并发数已从 5 降到 **2**（gtx / Lingva 两条失效线路已删除，见 F7）；
  "最坏 28s" 的尾巴仍在（只剩 2 条，理论最坏 ~28s，但两条都是实测可用的线路）。
- 修复方向：成功率/延迟先验排序 + 串行短路 + 探测缓存。

### #3 MyMemory 是翻译记忆库而非机器翻译 `[保留，F7 后权重上升]`
- 证据：本机 `vocab.json` 中存在 `Generally → (无翻译结果)`、`parade → 示威游行,阅兵…;v.游行` 这类输出。
- 成因：免费匿名额度 + 语料库匹配；配额提示混在译文正文里（`MYMEMORY WARNING...`），
  代码靠关键字识别（`infrastructure/translation/mymemory.py:parse_mymemory_response`）。
- 现状：F7 砍掉两条线路后，MyMemory 从"5 选 1"变成"2 选 1"，**命中率翻倍**，
  译文质量参差的问题会比以前更常见（实测 `the quick brown fox...` 它翻成"敏捷的棕色狐狸跳过了懒狗"，
  不如 clients5 的"那只懒狗"）。
- 修复方向：把它降级为最后兜底，主通道改用官方 API 或 LLM（第一项改善路线图的主线）。

### #4 缓存命中时不显示引擎标签 `[已失效 → 见 F8/#27]`
- 位置：`racing.py` 竞速前的缓存短路（与原 `main.py:267-270` 一致）→ `engine_label=None`，
  日志里不会出现"（X 最快返回）"。
- 现状：F8 之后**卡片本来就不显示引擎标签**（只有日志显示），所以"第二次查询标签消失"这件事
  用户已经看不到；日志侧缓存命中无标签属数据事实，保留。
- 测试：`test_cache_hit_has_no_label` 仍固定日志侧行为。

---

## 二、界面与交互

### #5 悬浮卡片固定 500×140、2.2 秒后自动消失 `[保留]`
- 位置：`presentation/tk/floating_card.py`（与原 `main.py:729-741` 一致）。
- 影响：查单词时卡片过大留白、查长句时高度不够；鼠标一动或稍一走神内容就没了，不能钉住/拖动/复制。

### #6 悬浮卡片"收录生词本"会把引擎标签写进词表 `[已修 → 见 F8/#27，重要]`
- 位置：原 `presentation/tk/floating_card.py` + `translate_window.py`（原 `main.py:854-861 → 675-678 → 944-947`）。
- 成因：卡片按钮存的是 `TranslationResult.display_text`（含 `\n（Google 最快返回）`），
  经 `clean_text` 折行后落库；而"最近 3 条"的收录按钮存的是干净译文——两处语义不一致。
- 证据：本机 `vocab.json` 中已有 `atmospheric → 大气 的（Google 最快返回）`、`verified → 已验证 （Google 最快返回）` 等条目。
- 现状：F8 拆出 `TranslationResult.card_text`（干净译文），卡片显示与"收录"都改用它，
  污染源已消失；**历史脏数据未清洗**（需要时写一次性清洗脚本，按 `（X 最快返回）` 正则剥离）。

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
| D7 | **F1（#20）**：取词失败不再静默翻译剪贴板旧内容（改为明确报错并放弃翻译） | 见 §五；行为有意偏离原版，用户实测后要求 |
| D8 | **F2（#21）**：界面改热键立即生效（监听器支持热更新） | 见 §五；这本来就是原版行为，阶段一漏掉，属补回 |
| D9 | **F3（#22）**：注入 Ctrl+C 前先等 Alt/Shift/Win 松开，并在按键之间留 15ms 间隔 | 见 §五；带来最多 ~0.6s 的等待（仅当热键含 Alt/Shift 时），Ctrl 组合热键不受影响 |
| D10 | **F4（#23）**：悬浮卡片以"热键按下瞬间"的鼠标位置为锚点 | 见 §五；原版是结果返回后才读光标，选中单词后手一动卡片就飘走 |
| D11 | **F5（#24）**：卡片不再定时自动关闭，改为"下一次按任意键/鼠标左右键"才关（点在卡片上不算） | 见 §五；新增一个 25ms 的输入监听线程（`Win32InputWatcher`） |
| D12 | **F6（#25）**：新增代理设置（直连 / 跟随系统代理 / 自定义）+ 代理失败自动回退直连 | 见 §五；默认仍是直连，只有用户显式打开才走代理 |
| D13 | **F7（#26）**：删除 gtx 与 Lingva 两条线路，竞速从 5 路降到 2 路（clients5 + MyMemory） | 见 §五；实测两条都是失效线路（gtx 429 / Lingva 403，直连与代理下均失败），保留只是浪费并发与配额 |
| D14 | **F8（#27）**：引擎标签只留在日志，不再画到悬浮卡片上（`TranslationResult.card_text`） | 见 §五；卡片回归"干净译文"，同时顺手掐掉 #6 的标签污染源 |

---

## 五、阶段一之后的有意修复 `[修复]`

下面是**主动偏离原版**的修复，各自配了回归测试；其余登记条目状态不变。

### F1 取词失败被静默吞掉：把剪贴板旧内容当成原文 ← 已修
- **现象**：在浏览器里划词翻译，连续三次都返回"上次复制过的网址"——
  `https://code.visualstudio.com/updates/v1_138 => https://code.visualstudio.com/updates/v1_138`。
- **原版机理**：`copy_selected_text()`（`main.py:949-964`）只比较"剪贴板内容有没有变"，
  内容没变时**不报错**，直接把剪贴板里的旧内容当取词结果返回。于是当 Ctrl+C 没真正生效
  （浏览器/系统抢了快捷键、选区丢失、该区域禁止复制）时，用户看到的就是"旧内容 => 旧内容"，
  而且毫无提示。另外翻译源对网址是**原样返回**（实测：clients5 与 MyMemory 均把 URL 原样吐回），
  所以这类输入看起来就像"翻译没干活"。
- **修复**：取词判据换成**剪贴板版本号** `GetClipboardSequenceNumber`——
  只要真的发生了一次复制，版本号必然变化（即使复制到的文本与旧值完全相同）；
  失败时返回 `copied=False`，用例直接判"取词失败"并**放弃翻译**，绝不回退到旧内容；
  版本号不可用（返回 0）时自动退回原来的内容比对，保持旧行为。
- **新增可观测性**：光标提示"取词失败：Ctrl+C 未生效"（2 秒）+ 界面翻译记录里一条说明原因的中文提示
  + 控制台一行 `取词失败：Ctrl+C 未生效（已放弃翻译，未使用剪贴板旧内容）`。
- **代码**：`domain/models/selection.py`、`domain/ports/selection_reader.py`、`domain/ports/clipboard.py`、
  `infrastructure/input/win32_selection.py`、`application/translate_selection.py`、`presentation/texts.py`
- **回归测试**：`tests/test_selection_capture.py`（9 项，核心用例是"剪贴板里是网址 + 复制失败"）、
  `tests/test_use_cases.py::TranslateSelectionUseCaseTests`（3 项，含"翻译器一次都没被调用"）

### F2 界面改热键要重启才生效 ← 已修（#21）
- **成因**：原版 `_tab_combo_loop` 每轮（8ms）重新读窗口上的热键字符串，所以改完**立即生效**；
  阶段一把绑定在 `start()` 时一次性交给监听器，导致改热键后必须重启程序。
- **修复**：`HotkeyListener` 端口新增 `update_bindings()`；轮询监听器每轮读取可变快照；
  `TranslateApp.on_apply_hotkeys()` 校验通过后立即同步（不重启）。
- **回归测试**：`tests/test_hotkey_listener.py`（5 项：改绑后旧组合不再触发、新组合立即触发）、
  `scripts/gui_smoke.py --with-tk`（真窗口 + 真监听器的端到端断言）。

### F3 热键里的 Alt/Shift 会"毒化"注入的 Ctrl+C ← 已修（#22）
- **现象**：F1 修好之后，用户用 `alt+z` 复测两次，日志里都是
  `取词失败：Ctrl+C 未生效（已放弃翻译，未使用剪贴板旧内容）`——不再返回网址，但**根本没取到词**。
- **根因（受控实验实测，`scripts/diagnose_modifier_poisoning.py`）**：监听器在热键按下**那一刻**
  就注入 Ctrl+C；热键是 `Alt+Z` 时人手还没松开 Alt，目标程序收到的是 **Ctrl+Alt+C**（不是复制）。
  在记事本上连测多轮：不按修饰键 → 复制成功；**按住 Ctrl → 成功；按住 Alt → 4/4 失败**。
  默认热键 `Ctrl+L` 之所以"看起来一直能用"，正因为人本来就按着 Ctrl（注入的仍是 Ctrl+C）——
  这也解释了用户第一次的"网址 => 网址"：那时 Ctrl+L 让浏览器把焦点移到地址栏，Ctrl+C 忠实地复制了网址。
- **修复**：注入 Ctrl+C 之前先等 **Alt / Shift / Win** 松开（Ctrl 除外，Ctrl+C 需要它；上限 0.6s，
  超时也照样尝试并把 `modifiers_held=True` 带回给调用方）；同时四次按键之间各留 15ms 间隔。
  实测（真实读取器）：`ctrl+f9` 组合成功、`alt+z` 且 Alt 稍后松开也成功。
- **顺带的人性化提示**：若失败且修饰键一直按着，界面直接提示
  "请松开修饰键再按一次；或把翻译热键改成 Ctrl 组合（例如 ctrl+f9）最稳"。
- **代码**：`infrastructure/input/win32_selection.py`、`domain/models/selection.py`、
  `application/translate_selection.py`、`presentation/texts.py`
- **回归测试**：`tests/test_selection_capture.py::ModifierReleaseTests`（5 项：先等松开再注入、
  一直按着要如实上报、Ctrl 不算毒化修饰键、注入有间隔、无修饰键时不空等）
- **诚实说明**：受控实验的目标程序是记事本（无浏览器可控），浏览器里的最终确认需要用户复测；
  逻辑上"松开 Alt 后注入干净的 Ctrl+C"对浏览器同样成立，且提示里已给出 Ctrl 组合的稳妥退路。

### F4 悬浮卡片要按"按下热键时的鼠标位置"显示 ← 已改（#23）
- **现象/诉求**：原版是在**翻译返回后**才读光标（`main.py:730` 的 `get_cursor_pos()`），
  而"选中单词 → 按热键 → 等结果"这段时间里用户往往会移动鼠标，于是卡片飘到了别处。
- **改法**：在热键触发的那一刻（监听线程）取一次坐标，作为本次结果的锚点一路传下去；
  为此新增 `Pointer` 端口（`GetCursorPos`，线程安全）替代原来的 Tk `winfo_pointerxy`，
  并把它作为 `anchor` 参数贯穿 `dispatch → run_* → handle_outcome → show_result/show_float → FloatingCard.show`。
  截图路径用选区左下角做锚点（手势结束后鼠标也可能已经移开）。
- **代码**：`domain/ports/pointer.py`、`infrastructure/input/win32_pointer.py`、
  `presentation/tk/{app_events,translate_sink,floating_card,translate_window}.py`
- **回归测试**：`tests/test_translate_jobs.py`（5 项，含"热键时鼠标在 A、显示时在 B → 必须用 A"）、
  `scripts/gui_smoke.py --with-tk`（真实 Tk 断言卡片落点）

### F5 卡片不再定时消失，改为"下一次输入"才关 ← 已改（#24）
- **诉求**：原版 `after(2200, withdraw)` 固定 2.2 秒（错误提示 2.8 秒、收录反馈 2 秒），
  用户希望"显示之后一直留着，直到我按任意键或鼠标左/右键"。
- **改法**：新增 `InputWatcher` 端口 + `Win32InputWatcher`（25ms 轮询 `GetAsyncKeyState`，
  与工程里既有的热键监听同一套机制，不装钩子、不干扰其它程序）；卡片显示时开始监听、
  关闭时停止。**启动瞬间已按下的键被忽略**（否则用 `alt+z` 触发时 Alt 还按着，卡片会立刻被关掉）；
  鼠标落在卡片矩形内（例如点"收录生词本"）不算关闭信号。
- **代码**：`domain/ports/input_watcher.py`、`infrastructure/input/win32_input_watcher.py`、
  `presentation/tk/floating_card.py`
- **回归测试**：`tests/test_input_watcher.py`（7 项：启动时按着的键忽略、任意键/鼠标左右键触发、
  长按不重复、重复按再次触发、stop 生效）、`scripts/gui_smoke.py --with-tk`（真实 Tk：不自动消失、
  卡片内点击不关、卡片外输入关闭、关闭后监听停止）

### F6 代理做进请求层（含"跟随系统代理"与失败回退）← 已加（#25）
- **诉求**：`requests` 不读 Windows 系统代理（原 #1），"开着 Clash 也用不上梯子"。
- **改法**：
  1. 所有翻译请求统一走 `infrastructure/network/http.py:get()`：`trust_env=False`（不猜环境变量）
     + 显式 `proxies`（由 `ProxyPolicy` 按主机决定）；
  2. 三种模式（存 `main_settings.json` 的 `proxy_mode` / `proxy_url`）：`off` 直连（默认）、
     `system` 读注册表 `Internet Settings`、`custom` 自定义；界面控制卡片里新增一行单选 + 地址 + 应用 + 测试；
  3. **私有/回环地址永远直连**（`10.*` / `192.168.*` / `172.16-31.*` / localhost），不会把内网请求塞进代理；
  4. **代理连不上自动回退直连一次**（`ProxyError` → 用空 proxies 重试），
     所以"跟随系统代理"在 Clash 被关掉时只是退化成直连，而不是翻译全挂；
  5. 改完**立即生效**（策略对象共享，界面改完下一个请求就按新策略走）。
- **实测（本机，2026-09-17）**：`off` 直连可用（MyMemory，1014ms）；`system`/`custom`（Clash 127.0.0.1:7897）
  可用且更快（clients5，664~710ms，译文也更完整）。同时确认 **gtx 仍 429、Lingva 被 Cloudflare 挡（403）**，
  这两条与代理无关，属于线路本身失效（见 #3 / #4）。
- **代码**：`config/proxy.py`、`domain/ports/proxy.py`、`infrastructure/network/{system_proxy,proxy_policy,http}.py`、
  `infrastructure/translation/*`（4 个引擎接受 `policy`）、`application/settings.py`、`presentation/tk/{translate_panel,translate_shell,translate_window}.py`
- **回归测试**：`tests/test_proxy.py`（17 项：模式解析、私有地址直连、回退直连、设置往返、引擎接线）、
  `scripts/gui_smoke.py --with-tk`（界面改代理 → 策略即时生效 + 落盘）

### F7 砍掉两条"拖后腿"的线路：竞速 5 路 → 2 路 ← 已删（#2 / #26）
- **依据（本机实测，2026-09-17）**：gtx 直连与走 Clash 都是 **HTTP 429**（Google 已对免费 gtx 端点限流）；
  Lingva（`lingva.ml` 等公共实例）直连与走 Clash 都是 **403**（Cloudflare 拦截）；
  clients5 **HTTP 200**（直连 715ms / Clash 343ms）、MyMemory **HTTP 200**（~1.3s）。
  即 5 条线路里只有 2 条真的能出中文，另 3 条（含 `translate.googleapis.com` 的 gtx）
  每次划词都在白等并发与超时预算。
- **改法**：
  1. 删除 `infrastructure/translation/lingva.py` 整个文件，删掉 gtx 相关类与端点常量
     （`infrastructure/translation/google.py` 现在只留 clients5）；
  2. `policy.py` 的 `RACE_MAX_WORKERS` 从 5 降到 **2**，缓存归属键只剩 `google_c5` / `mymemory`；
  3. `RacingTranslator` 改为显式接收两条线路（`google_clients5` + `mymemory`），
     并暴露 `line_names` 供自检/日志打印；
  4. 界面下拉里的"自动竞速"文案改成"clients5 + MyMemory（谁先成功用谁）"。
- **实测收益**：一次划词从"5 路并发、最坏 ~28s"变成"2 路并发"，直连实测 **632ms** 出结果
  （此前同一句 1014ms）。
- **保留的部分**：超时/重试参数（`(6,22)` / `2`）与"谁先成功用谁"策略不变，仍是行为等价的一部分。
- **代码**：`infrastructure/translation/{policy,racing,google,factory}.py`（`lingva.py` 已删）、
  `presentation/texts.py`、`scripts/diagnose_url_capture.py`
- **回归测试**：`tests/test_translation_infra.py::test_only_two_lines_participate`（断言只有两条线路被启动）、
  `tests/test_proxy.py`（引擎接线断言从 4 个引擎收敛到 `_clients5` / `_mymemory`）

### F8 引擎标签只进日志，不进悬浮卡片 ← 已改（#4 / #6 / #27）
- **诉求**："（'最快返回了'）这些直接在日志里面显示就好了" —— 卡片是给人看译文的地方，
  不需要出现实现细节。
- **改法**：`TranslationResult` 拆成两个属性——
  `display_text` = **日志文本**（仍带 `\n（X 最快返回）`，控制台/翻译记录/对拍脚本口径不变），
  `card_text` = **卡片文本**（干净译文）；`presentation/tk/translate_sink.py:show_result()` 记录日志用前者、
  画卡片用后者；卡片上的"收录生词本"按钮随之存干净译文。
- **实测**：日志文本 `敏捷的棕色狐狸跳过了懒狗。\n（MyMemory 最快返回）`，
  卡片文本 `敏捷的棕色狐狸跳过了懒狗。`。
- **顺带修掉**：#6（卡片收录把引擎标签写进词表）的污染源消失——两处收录语义现在一致。
  **历史脏数据未清洗**（需要时按 `（X 最快返回）` 正则写一次性脚本）。
- **代码**：`domain/models/translation.py`、`presentation/tk/{translate_sink,app_events}.py`、`presentation/texts.py`
- **回归测试**：`tests/test_translate_jobs.py::test_engine_label_only_in_log_not_on_card`、
  `tests/test_translation_domain.py`（`display_text` 带标签 / `card_text` 不带）

---

## 六、仓库历史遗留 `[历史]`

| # | 现象 | 说明 |
|---|---|---|
| H1 | README 写 `reset_vocab_scores.py`，实际文件是 `set.py` | 原仓库文档与文件名不一致 |
| H2 | `image/1.png` 等实为 JPEG 字节 | 扩展名与内容不符（浏览器可容错显示） |
| H3 | 原仓库 `__pycache__/quick_select_translate.cpython-310.pyc` | 已删除模块的残留，说明历史上还有"快速划词"模块 |
| H4 | 上游最后提交 2026-05-22，无 release、无打包 | 23 star / 4 fork 的个人项目，不提供预编译产物 |
