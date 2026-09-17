# 文件分级与迁移映射

本文回答两个问题：**①新工程的目录与文件是怎么分级的；②原版的每一段代码搬到了哪里。**
分层规则与依赖方向见 `ARCHITECTURE.md`。

---

## 一、目录分级（重构后实测）

| 层级 | 目录 | 文件 | 行数 | 职责 | 允许依赖 |
|---|---|---|---|---|---|
| L0 配置 | `src/snaptranslate/config/` | 4 | 98 | 路径解析、主题色、应用元信息 | 仅标准库 |
| L1 领域 | `src/snaptranslate/domain/` | 27 | 785 | 模型、领域服务、端口 Protocol、错误 | 标准库 + domain |
| L2 基础设施 | `src/snaptranslate/infrastructure/` | 28 | 1235 | 5 条翻译线路与竞速、Tesseract OCR、SAPI 朗读、JSON 持久化、Win32 输入、DeepSeek | + config |
| L3 应用 | `src/snaptranslate/application/` | 14 | 737 | 8 个用例 + 依赖包 + 进度/结果 DTO | + domain、config |
| L4 表示 | `src/snaptranslate/presentation/` | 32 | 3720 | 文案总表 + Tk（`tk/` 24 文件）+ Streamlit（`web/` 6 文件） | + application |
| L5 组装 | `src/snaptranslate/bootstrap/` | 5 | 271 | 容器（唯一装配点）、装配函数、CLI/Streamlit 进程入口 | 全部 |
| — | 主包合计 | **111** | **6854** | | |

外围：`entrypoints/`（4 个兼容入口）、`scripts/`（6 个门禁脚本）、`tests/`（13 个文件 / 160 项测试）。

粒度：单文件 60–300 行、单文件单职责。**唯一例外**是 `presentation/texts.py`（321 行，全部界面文案的唯一出口），已在 `ARCHITECTURE.md §3` 登记。

---

## 二、`main.py`（1918 行）→ 新位置

| 原版位置 | 内容 | 新位置 |
|---|---|---|
| 44-99 | `MAX_TEXT_LENGTH`、超时/重试、Lingva 列表、HTTP 头、Tesseract 路径 | `domain/services/text_cleaning.py`、`infrastructure/translation/policy.py`、`config/paths.py` |
| 57-76 | 翻译结果内存缓存（OrderedDict + LRU） | `infrastructure/translation/cache.py` |
| 102-127 | Google gtx 线路 | `infrastructure/translation/google.py:GoogleGtxTranslator` |
| 129-182 | MyMemory 线路（额度提示识别、langpair 猜测） | `infrastructure/translation/mymemory.py` |
| 185-228 | Google clients5 线路 | `infrastructure/translation/google.py:GoogleClients5Translator` |
| 231-259 | Lingva 镜像 | `infrastructure/translation/lingva.py` |
| 262-304 | 5 路并发竞速 | `infrastructure/translation/racing.py` |
| 307-325 | 失败文案格式化 | `infrastructure/translation/errors.py` |
| 328-348 | 界面配色与字体 | `config/theme.py` |
| 351-409 | `TranslatorApp.__init__` 状态字段 | `presentation/tk/translate_window.py` + `bootstrap/container.py` |
| 411-416 | `clean_text` | `domain/services/text_cleaning.py` |
| 418-459 | 设置读写与 TTS 音量 | `infrastructure/persistence/json_settings.py` + `application/settings.py` |
| 461-548 | 热键规范化/解析/标签/VK 映射 | `domain/models/hotkey.py` + `infrastructure/input/win32_keys.py` + `presentation/tk/hotkey_controls.py` |
| 508-541 | `GetAsyncKeyState` 判定与 Tab 组合边沿检测 | `infrastructure/input/win32_hotkeys.py` |
| 550-567 | 状态栏文案与热键提示行 | `presentation/texts.py:WindowText` |
| 569-582 | 启动时备份词表 | `application/backup.py` + `infrastructure/persistence/backup.py` |
| 584-615 | 翻译器选择与容错入口 | `application/translate_text.py` + `infrastructure/translation/factory.py` |
| 617-620 | 取光标位置 | `presentation/tk/translate_window.py`（`winfo_pointerxy`，见 `KNOWN_ISSUES.md` 附注） |
| 622-657 | 启用开关、热键应用与校验 | `presentation/tk/translate_window.py` + `hotkey_controls.py` |
| 659-667 | 日志写入（原文/译文分色） | `presentation/tk/translate_transcript.py:TranscriptPanel.append` |
| 669-741 | 鼠标旁悬浮卡片 | `presentation/tk/floating_card.py` |
| 743-852 | 光标旁状态条（跟随 + 自动隐藏） | `presentation/tk/cursor_status.py` |
| 854-947 | 结果落地、反馈、最近列表、收录/删除 | `presentation/tk/translate_sink.py`（`ResultPresenter`）+ `collect_actions.py` + `app_events.py` + `application/vocabulary_collection.py` |
| 949-964 | 模拟 Ctrl+C 取词 | `infrastructure/input/win32_selection.py` |
| 966-1011 | 文本翻译主流程 | `application/translate_text.py` + `presentation/tk/app_events.py` |
| 1013-1016 | 英文判定 | `domain/services/text_cleaning.py` |
| 1019-1041 | PowerShell + System.Speech 朗读 | `infrastructure/tts/windows_sapi.py` |
| 1043-1048 | 划词翻译入口 | `application/translate_selection.py` |
| 1050-1067 | 收录"最近一条翻译" | `application/vocabulary_collection.py:RecallLastTranslationUseCase` + `app_events.run_save_last` |
| 1069-1206 | 截图 OCR 翻译、Tesseract 选择 | `application/translate_screenshot.py` + `infrastructure/ocr/tesseract.py` |
| 1208-1263 | Win32 抢焦点、遮罩激活 | `infrastructure/input/win32_window.py` + `presentation/tk/snip_overlay.py` |
| 1265-1408 | 截图遮罩（拖拽、尺寸提示、取消） | `presentation/tk/snip_overlay.py` |
| 1410-1455 | 8ms 轮询热键循环 | `infrastructure/input/win32_hotkeys.py:Win32PollingHotkeyListener` |
| 1457-1471 | 词表读写 | `infrastructure/persistence/json_vocabulary.py` |
| 1473-1503 | 收录生词本 | `application/vocabulary_collection.py` + `presentation/tk/collect_actions.py` |
| 1505-1528 | `RegisterHotKey` 消息循环（**原版从未启动**） | `infrastructure/input/win32_hotkeys.py:Win32RegisteredHotkeyListener`（默认不装配） |
| 1530-1535 | 清空日志 | `presentation/tk/translate_transcript.py:TranscriptPanel.clear` |
| 1537-1883 | `_build_ui` 主界面 | `presentation/tk/translate_shell.py`（变量/几何/头部/日志区）+ `translate_panel.py`（控制卡片）+ `translate_ui.py`（Protocol） |
| 1885-1918 | 关闭与 `run`/`main` | `presentation/tk/translate_window.py` + `bootstrap/wiring.py` + `entrypoints/main.py` |

---

## 三、`vocab_review.py`（1026 行）→ 新位置

| 原版位置 | 内容 | 新位置 |
|---|---|---|
| 20-26 | 路径与 DeepSeek 常量 | `config/paths.py`、`infrastructure/llm/deepseek.py` |
| 28-56 | 主题、评分常量与 `GRADE_DELTA` | `config/theme.py`、`domain/services/scoring.py` |
| 59-74 | `item_score` / `normalize_vocab_scores` | `domain/services/scoring.py` |
| 76-93 | `load_vocab` / `save_vocab` | `infrastructure/persistence/json_vocabulary.py` |
| 96-114 | API Key 文件读写 | `infrastructure/persistence/api_key_file.py` |
| 117-129 | 待补例句判定与统计 | `domain/models/vocab_entry.py` |
| 132-156 | 双语 JSON 解析、402 判定 | `infrastructure/llm/deepseek.py` |
| 159-548 | `VocabReviewApp` 状态与界面 | `presentation/tk/review_window.py` + `settings_form.py` + `card_form.py` + `grade_buttons.py` + `example_panel.py` + `log_panel.py` |
| 550-574 | 日志与词表切换 | `presentation/tk/log_panel.py` + `application/vocabulary_target.py` + `review_window._pick_vocab_file` |
| 576-604 | 复习端音量设置 | `application/settings.py:ReviewSettingsUseCase` |
| 606-633 | 排序、当前卡片 | `domain/services/review_session.py` |
| 635-692 | 朗读（阻塞/卡面自动/手动重读） | `infrastructure/tts/windows_sapi.py` + `application/review.py` + `presentation/tk/speech.py` |
| 694-732 | 评分与推进 | `application/review.py:grade` + `domain/services/review_session.py:advance_after_grade` + `presentation/tk/card_controller.py` |
| 734-784 | 例句面板渲染（关键词加粗） | `presentation/tk/example_panel.py` |
| 786-855 | 揭示状态与卡片刷新 | `domain/services/review_session.py:RevealState` + `presentation/tk/card_controller.py` + `card_form.py` |
| 857-935 | 生成按钮、API Key 弹窗、DeepSeek 调用 | `presentation/tk/generator_setup.py` + `infrastructure/llm/deepseek.py` |
| 937-1004 | 批量生成循环与结束弹窗 | `application/generate_examples.py` + `presentation/tk/generator_setup.py` + `review_window.py` |
| 1006-1026 | `run` / `main` | `presentation/tk/review_window.py` + `entrypoints/vocab_review.py` |

---

## 四、`vocab_review_web.py`（510 行）→ 新位置

| 原版位置 | 内容 | 新位置 |
|---|---|---|
| 14-161 | 常量、词表 IO、例句解析、备份、排序 | 与桌面端同一批模块（`config` / `domain` / `infrastructure`） |
| 164-232 | `rebuild_order`、`current_item`、评分、状态初始化 | `domain/services/review_session.py` + `application/review.py` + `presentation/web/session_state.py` |
| 267-319 | API Key 获取、批量生成 | `infrastructure/llm/deepseek.py` + `application/generate_examples.py` + `presentation/web/generate_panel.py` |
| 322-358 | 浏览器 `speechSynthesis` 注入与自动朗读 token | `presentation/web/speech_inject.py` |
| 361-510 | 页面主体（侧边栏 / 卡片 / 底部） | `presentation/web/streamlit_review.py`（`render_page`）+ `card_view.py` |
| 进程入口 | `streamlit run ...` | `bootstrap/streamlit_entry.py` + `entrypoints/vocab_review_web.py` |

---

## 五、`set.py`（197 行）→ 新位置

| 原版位置 | 内容 | 新位置 |
|---|---|---|
| 16-28 | `load_vocab`（严格语义）/ `save_vocab` | `infrastructure/persistence/json_vocabulary.py`（`load_strict` / `save`） |
| 31-38 | `count_with_example` | `domain/models/vocab_entry.py:with_example_count` |
| 41-50 | `list_backups` | `infrastructure/persistence/backup.py` |
| 53-61 | `reset_scores` | `application/vocabulary_admin.py:reset_scores` |
| 64-76 | `cleanup_backups_keep_latest` | `infrastructure/persistence/backup.py` |
| 79-189 | `AdminApp` 界面与交互 | `presentation/tk/admin_window.py` |
| 192-197 | `main` | `entrypoints/set.py` |

---

## 六、新增文件（原版没有对应物）

| 文件 | 作用 |
|---|---|
| `domain/ports/*.py`（12 个） | 端口 Protocol：翻译、OCR、朗读、词表仓储、设置仓储、API Key、备份、剪贴板、取词、热键、窗口激活、例句生成、时钟、错误格式化 |
| `domain/services/review_session.py` | 复习会话状态机（桌面端与 Web 端共用） |
| `application/deps.py` | 表示层依赖包（四套：划词 / 复习 / 网页 / 后台） |
| `application/progress.py`、`application/dto.py` | 流程阶段枚举 + 进度回调 + 用例结果对象 |
| `application/vocabulary_target.py` | 当前词表绑定（支持复习端切换词表文件） |
| `application/backup.py` | 启动备份用例 |
| `presentation/texts.py` | 全部界面文案的唯一出口 |
| `presentation/tk/translate_sink.py`、`app_events.py` | 线程安全的结果出口 + 热键→线程→用例编排 |
| `presentation/tk/translate_ui.py` | 面板与窗口壳的 Protocol 契约 |
| `bootstrap/container.py` / `wiring.py` / `cli.py` / `streamlit_entry.py` | 组合根与四类进程入口 |
| `scripts/*.py`（6 个） | 分层校验 / 对拍 / 冒烟 / Tk 冒烟 / Web 结构对拍 / 一键全跑 |
| `tests/*`（13 个） | 160 项测试（含分层约束与表示层纯逻辑） |
