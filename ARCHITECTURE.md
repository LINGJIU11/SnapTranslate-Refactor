# SnapTranslate 分层架构（重构版）

> 本文是重构后的**架构契约**。任何新增代码都必须遵守这里的依赖方向与层次职责。
> 本轮的边界是**纯结构重构**：对外行为与 `C:\Translate\SnapTranslate`（原版 4 个脚本）保持一致，任何有意或无意的偏差都登记在 `KNOWN_ISSUES.md`。

## 1. 总体分层

```
                       ┌──────────────────────────────┐
                       │  bootstrap（组装层 / 组合根） │  唯一允许 import 全部层
                       └───────────────┬──────────────┘
                                       │ 构造并注入
        ┌──────────────────────────────┴───────────────────────────────┐
        │                                                              │
┌───────▼────────┐        ┌──────────────────┐        ┌────────────────▼───────┐
│ presentation   │───────►│   application    │───────►│     domain             │
│ 表示层         │ 调用   │   应用层（用例）  │ 调用   │  领域层（模型/端口/服务）│
│ Tk / Streamlit │◄───────│  只依赖端口       │◄───────│  纯 Python，零 IO       │
└───────┬────────┘ 回调   └────────┬─────────┘ 结果   └────────────▲───────────┘
        │                          │                                │ 实现端口
        │                          │ 由 bootstrap 注入实现          │
        │                 ┌────────┴─────────┐                      │
        └────────────────►│ infrastructure   │──────────────────────┘
                          │ 基础设施层（适配器）│
                          └──────────────────┘
                                 │
                          ┌──────▼──────┐
                          │   config    │ 路径 / 主题 / 应用元信息（叶子层）
                          └─────────────┘
```

**依赖方向规则（单向，禁止逆向与跨层跳跃）**

| 层 | 允许 import | 禁止 import |
|---|---|---|
| `config` | 标准库 | 其它任何层 |
| `domain` | 标准库、`domain.*` | `config`、`application`、`infrastructure`、`presentation`、`bootstrap` |
| `infrastructure` | 标准库、第三方库、`domain.*`、`config.*` | `application`、`presentation`、`bootstrap` |
| `application` | 标准库、`domain.*`、`config.*`（只读常量） | `infrastructure`、`presentation`、`bootstrap` |
| `presentation` | 标准库、第三方 UI 库、`domain.*`、`application.*`、`config.*` | `infrastructure`、`bootstrap` |
| `bootstrap` | 全部 | — |

- 该规则由 `scripts/check_layering.py` 用 AST 静态校验，可随时执行；`tests/test_layering.py` 直接调用它，破坏分层会测试失败。
- **跨层通信只走 `domain/ports` 里的 Protocol**：上层定义需要什么能力（端口），下层提供实现（适配器），`bootstrap` 负责把适配器塞给用例。表示层永远拿不到"requests"或"pytesseract"这类实现细节。

## 2. 各层职责

### 2.1 `config/` — 配置与常量（叶子）
- `paths.py`：数据目录解析（默认=工程根目录，与原版"脚本同目录"一致）、各数据文件名（`vocab.json`/`api_key.txt`/`main_settings.json`/`vocab_review_settings.json`/`backups/`）、OCR/Tesseract 候选路径。
- `theme.py`：全部颜色与字体常量（原版在 `main.py` 与 `vocab_review.py` 各存了一份，现收敛为一份）。
- `app.py`：应用名、版本、窗口标题文案。

### 2.2 `domain/` — 领域层（纯逻辑，零 IO）
- `models/`
  - `vocab_entry.py`：`VocabEntry`（对原始 dict 的**强类型视图**，保留未知字段与键序）、`Vocabulary`（词条集合，封装增删查与"待补例句"统计）。
  - `review.py`：`SortMode`、`Grade`、`RevealState` 等枚举与值对象。
  - `translation.py`：`TranslationResult`（干净译文 + 引擎标签 + `display_text`）、`BBox`、`Language`。
  - `hotkey.py`：`Hotkey`（解析 `ctrl+l` / `tab+q` 这类组合，纯字符串规则）。
- `services/`
  - `scoring.py`：`DEFAULT_SCORE / SCORE_MIN / SCORE_MAX / GRADE_DELTA`、`item_score`、`normalize_scores`、`apply_grade`。
  - `review_session.py`：复习会话状态机（顺序构建、当前位置、推进、评分），桌面端与 Web 端**共用同一实现**。
  - `text_cleaning.py`：`clean_text`、`is_likely_english`、`truncate`。
- `ports/`：`translator.py`、`ocr.py`、`tts.py`、`vocabulary_repository.py`、`settings_repository.py`、`api_key_store.py`、`backup_writer.py`、`clipboard.py`（含 `sequence()` 剪贴板版本号）、`selection_reader.py`（返回 `SelectionCapture`，见 §4.7）、`hotkey_listener.py`（含 `update_bindings()` 热更新）、`pointer.py`（鼠标位置，线程安全）、`input_watcher.py`（"任意键/鼠标键按下"监听，用于关闭浮层）、`example_generator.py`、`clock.py`、`window.py`、`error_formatter.py`。
- `errors.py`：`SnapTranslateError` 及领域错误（`TranslationError`、`OcrError`、`VocabularyIoError`、`ExampleGenerationError`）。

### 2.3 `infrastructure/` — 基础设施层（适配器实现端口）
- `translation/`：`google_gtx.py`、`google_clients5.py`、`mymemory.py`、`lingva.py`、`racing.py`（并发竞速策略）、`cache.py`（进程内 OrderedDict 缓存）、`errors.py`（失败文案格式化）、`factory.py`。
- `ocr/tesseract.py`：屏幕截取 + Tesseract 识别 + 语言包探测 + `TESSDATA_PREFIX` 处理。
- `tts/windows_sapi.py`：PowerShell + `System.Speech` 朗读（阻塞/异步两种，与原版超时参数一致）。
- `persistence/`：`json_vocabulary.py`（三种加载语义见 §4）、`json_settings.py`、`api_key_file.py`、`backup.py`。
- `input/`：`win32_clipboard.py`、`win32_selection.py`（模拟 Ctrl+C 取词）、`win32_hotkeys.py`（`RegisterHotKey` 消息循环 + 轮询式监听器）、`win32_keys.py`（键名 → 虚拟键码表）。
- `llm/deepseek.py`：OpenAI 兼容客户端 + 例句生成提示词 + 402 余额不足识别（原版在桌面端与 Web 端各写了一份）。

### 2.4 `application/` — 应用层（用例编排）
只依赖 `domain` 的端口，不知道 GUI，也不知道 requests。

| 用例 | 职责 | 对应原版 |
|---|---|---|
| `TranslateTextUseCase` | 清洗 → 长度截断 → 英文自动朗读 → 调翻译端口 → 产出 `TranslationOutcome` | `main.py:_translate_text_job` |
| `TranslateSelectionUseCase` | 取词（端口）→ 上面的用例 | `main.py:_do_translate_job` |
| `TranslateScreenshotUseCase` | 区域 → OCR（端口）→ 上面的用例（含 OCR 互斥锁） | `main.py:_do_screen_ocr_translate_job` |
| `CollectVocabularyUseCase` | 收录/去重/删除最近词条 | `main.py:_do_save_vocab_job`、`_delete_saved_word` |
| `RecallLastTranslationUseCase` | 收录"最近一条翻译" | `main.py:_do_save_last_translation_job` |
| `ReviewUseCase` | 驱动 `ReviewSession` + 评分持久化 + 自动朗读 | `vocab_review.py`、`vocab_review_web.py` |
| `GenerateExamplesUseCase` | 批量补全例句，逐条落盘，402 中止 | 同上 |
| `VocabularyAdminUseCase` | 词表状态、评分重置、备份清理 | `set.py` |

### 2.5 `presentation/` — 表示层
- `texts.py`：**全部界面文案的唯一出口**（`WindowText` / `StatusText` / `ErrorTitle` / `CollectText` / `ReviewText` / `AdminText` / `WebText`）。Tk 与 Streamlit 共用同一套字符串与格式化函数。
- `tk/` — 划词翻译窗口一族（原 `main.py`）：
  - `translate_window.py`：`TranslateApp(deps)`——窗口壳、装配、面板回调、取值方法；
  - `translate_shell.py` / `translate_panel.py` / `translate_ui.py`：Tk 变量与窗口几何、控制卡片布局、面板与壳的 Protocol 契约；
  - `translate_sink.py`：结果落地契约 + `ResultPresenter`（线程安全出口：主线程直写、后台线程 `after(0)`）；
  - `app_events.py`：热键回调 → 线程调度 → 用例调用 → 结果分发；
  - `hotkey_controls.py` / `collect_actions.py` / `translate_transcript.py`：热键校验、收录/删除反馈、翻译记录与"最近 3 条"；
  - `floating_card.py` / `cursor_status.py` / `snip_overlay.py`：悬浮卡片、光标状态条、截图遮罩；
  - `ui_kit.py`：控件工厂 + `UiDispatcher` / `StatusBridge`。
- `tk/` — 复习与后台管理（原 `vocab_review.py` / `set.py`）：
  `review_window.py`、`admin_window.py`、`card_controller.py`、`card_form.py`、`settings_form.py`、
  `log_panel.py`、`example_panel.py`、`generator_setup.py`、`speech.py`、`grade_buttons.py`。
- `web/`：Streamlit 复习页，**只暴露 `render_page(deps)`**；进程级入口在 `bootstrap/streamlit_entry.py`。

### 2.6 `bootstrap/` — 组装层
- `container.py`：按配置构造全部适配器与用例（依赖注入的唯一位置）。
- `wiring.py`：面向入口的四个 `run_*()` 函数。
- `cli.py`：console_scripts 入口（`snaptranslate` / `-review` / `-review-web` / `-admin`）。
- `streamlit_entry.py`：`streamlit run` 所需的脚本入口（自己构造依赖后调用 `presentation.web`）。

> 命令行入口刻意放在 `bootstrap` 而非 `presentation`：入口必须 import `bootstrap.wiring`，
> 而 `presentation` 被禁止 import `bootstrap`（§1 依赖方向表）。

## 3. 目录与文件分级

```
SnapTranslate重构/
├─ ARCHITECTURE.md            架构契约（本文件）
├─ FILE_MAP.md                文件分级清单 + 旧→新映射（哪个原函数搬到哪个新文件）
├─ KNOWN_ISSUES.md            原样保留的缺陷与"有意偏差"登记
├─ README.md                  安装、运行、目录地图
├─ pyproject.toml             依赖 + console_scripts 入口
├─ requirements.txt           与原版一致的直接依赖
├─ entrypoints/               原版 4 个脚本的同名薄壳（保持 `python main.py` 可用）
│   ├─ main.py  ├─ vocab_review.py  ├─ vocab_review_web.py  └─ set.py
├─ scripts/                   工程脚本（分层校验 / 等价性对比 / 冒烟）
├─ src/snaptranslate/         主包（见上）
└─ tests/                     单元测试 + 分层约束测试
```

文件粒度约定：**单文件 60–300 行、单文件单职责**；同一文件里出现两类以上职责（如"UI 布局 + 网络请求"）必须再拆。

已登记的两个例外（都是"单一职责但天然较长"，拆开反而更难查）：

| 文件 | 行数 | 为何不拆 |
|---|---|---|
| `presentation/texts.py` | ~320 | 全部界面文案的唯一出口；按窗口拆成多份会让"同一句话在两个界面"重新分散 |
| `presentation/web/` 各模块 | 13–140 | 已按职责拆成 `streamlit_review` / `card_view` / `generate_panel` / `session_state` / `speech_inject` |

## 4. 关键设计决策

1. **词条以原始 dict 为事实来源**：`VocabEntry` 是视图而非拷贝，避免"重新序列化后键序变化/未知字段丢失"——这是行为等价的前提。
2. **三种词表加载语义被显式命名而非合并**（原版 4 份实现语义不同，合并会改变行为）：
   - `load_raw()`：只判断顶层是 list，**不过滤**非 dict 元素，出错返回 `[]`（原 `main.py`）；
   - `load_tolerant()`：过滤非 dict 元素，出错返回 `[]`（原 `vocab_review.py` / `vocab_review_web.py`）；
   - `load_strict()`：读取失败或顶层非 list **抛异常**（原 `set.py`）。
3. **设置写入语义同样显式区分**：`merge(patch)`（原 `main.py`，保留其它键）与 `replace(payload)`（原 `vocab_review.py`，整体覆盖并在失败时删临时文件）。
4. **翻译竞速的"引擎标签"与缓存短路语义原样保留**：命中缓存时**不带**引擎标签，未命中竞速才带——这决定了界面上是否出现"（Google 最快返回）"，也决定了原版把标签写进生词本的行为，本轮**不改**（见 `KNOWN_ISSUES.md`）。
5. **两端复习界面共用 `ReviewSession`**：原版桌面端与 Web 端各写了一份顺序/评分/推进逻辑，现收敛为领域服务，两端只做渲染。
6. **唯一的新增能力**：数据目录可用环境变量 `SNAPTRANSLATE_DATA_DIR` 覆盖（默认值与"脚本同目录"完全一致，不设该变量时行为不变）。
7. **取词结果必须能区分"取到了"与"没取到"**（阶段一之后的修复，见 `KNOWN_ISSUES.md` §五 F1）：
   `SelectionReader` 返回 `SelectionCapture(text, copied, clipboard_text)`，调用方据此在
   "Ctrl+C 未生效"时**放弃翻译**，而不是把剪贴板里的旧内容当原文——原版正是在这里把失败当成了成功，
   于是出现"上次复制的网址 => 同一个网址"。
8. **浮层的"锚点"在触发瞬间确定**（F4）：`Pointer` 端口（`GetCursorPos`）让监听线程也能安全取坐标，
   卡片以"热键按下那一刻"的鼠标位置显示，之后用户移动鼠标不影响结果落点。
9. **浮层的"生命周期"由输入驱动**（F5）：`InputWatcher` 端口监听"任意键/鼠标左右键"，
   卡片显示后一直保留到用户下一次输入；启动时已按下的键被忽略（否则热键里的 Alt 会把卡片立刻关掉）。

## 5. 验证策略

| 手段 | 命令 | 覆盖 |
|---|---|---|
| 语法/导入 | `python scripts/smoke_check.py` | 全包编译 + 分层导入 + 依赖装配 + 关键纯函数 |
| 分层约束 | `python scripts/check_layering.py` | 依赖方向、禁止跨层 import（AST 静态校验） |
| 单元测试 | `python -m unittest discover -s tests -t .`（或 `pytest tests`） | 评分、复习会话、清洗、热键解析、翻译响应解析、词表 IO 三种语义、设置两种写语义、备份、用例编排、表示层纯逻辑 |
| 与原版逐函数对拍 | `python scripts/parity_check.py <原版目录>` | 纯函数 + **流程级**（文本翻译主链路、生词收录分支），当前 173 项 0 差异 |
| Tk 界面冒烟 | `python scripts/gui_smoke.py --with-tk` | 真实创建三个窗口（构造后立即销毁，不进 mainloop） |
| Streamlit 结构对拍 | `python scripts/web_smoke.py` | 用官方 `AppTest` 渲染新页面并与原版逐项比较标题/按钮/下拉框/输入框/小标题 |

> 这些脚本都是"可执行的约束"：分层违规、行为漂移、装配断裂、界面建不起来都会让命令非 0 退出。
