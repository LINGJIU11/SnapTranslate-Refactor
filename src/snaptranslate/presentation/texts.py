"""表示层唯一的界面文案表。

原版把中文文案写死在业务逻辑里（例如 ``main.py:1048 1074 1120``），
分层后文案属于表示层：``application`` 只发阶段枚举与结果种类，本模块负责映射成字。
**任何界面新增/修改文案都应改这里，而不是改用例。**
"""

from __future__ import annotations

from snaptranslate.application.dto import CollectKind, DeleteKind, ErrorKind
from snaptranslate.application.progress import Stage
from snaptranslate.domain.models.hotkey import label_or_placeholder
from snaptranslate.domain.models.review import Grade

# ———————————————————————————— 划词翻译窗口 ————————————————————————————


class StatusText:
    """状态栏 / 光标提示条文案（含原版的自动隐藏时长）。"""

    #: 阶段 → (状态栏文案, 光标提示文案, 自动隐藏毫秒)
    STAGE_TEXT: dict[Stage, tuple[str | None, str, int | None]] = {
        Stage.READING_SELECTION: (None, "读取划词内容…", None),
        #: 取词失败（Ctrl+C 未生效）——原版没有这个状态，见 KNOWN_ISSUES.md #20
        Stage.CAPTURE_FAILED: (None, "取词失败：Ctrl+C 未生效", 2000),
        Stage.TRANSLATING: (None, "并发翻译中…", None),
        Stage.DONE: (None, "翻译完成", 1000),
        Stage.FAILED: (None, "翻译失败", 1500),
        Stage.NO_TEXT: (None, "未检测到可翻译文本", 1300),
        Stage.OCR_PREPARING: (None, "OCR 准备中…", None),
        Stage.OCR_CAPTURING: ("OCR：正在截取屏幕…", "OCR 截图中…", None),
        Stage.OCR_RECOGNIZING: (
            "OCR：正在识别文字（区域越大可能越慢，请稍候）…",
            "OCR 识别中…",
            None,
        ),
        Stage.OCR_TRANSLATING: ("OCR：正在翻译…", "并发翻译中…", None),
        Stage.OCR_UNAVAILABLE: (None, "OCR 不可用", 1500),
        Stage.OCR_BUSY: ("OCR 正在进行中，请稍候…", "OCR 正在进行中，请稍候…", 1300),
        Stage.OCR_FAILED: (None, "OCR 失败", 1500),
    }

    @classmethod
    def texts(cls, stage: Stage) -> tuple[str | None, str, int | None]:
        return cls.STAGE_TEXT.get(stage, (None, "", None))


class ErrorTitle:
    """错误提示标题（原版 ``_ui_show_error`` 的第一个参数）。"""

    OCR_FAILED = "OCR 失败"
    OCR_UNAVAILABLE = "OCR 不可用"
    HINT = "提示"

    @classmethod
    def for_kind(cls, kind: ErrorKind | None, source_text: str = "") -> str:
        if kind is ErrorKind.OCR_FAILED:
            return cls.OCR_FAILED
        if kind is ErrorKind.OCR_UNAVAILABLE:
            return cls.OCR_UNAVAILABLE
        # 翻译失败时原版用"原文"当标题
        return source_text


class WindowText:
    TITLE = "SnapTranslate"
    SUBTITLE = "选中文字后按快捷键翻译 · 简体中文 · 可朗读英文"
    ENABLE_CHECKBOX = "启用划词翻译"
    FLOATING_CHECKBOX = "鼠标旁悬浮提示"
    SOURCE_LABEL = "翻译源"
    SOURCE_MYMEMORY = "MyMemory（免梯 · 免密钥 · 有每日免费限额）"
    SOURCE_AUTO_RACE = "自动竞速（clients5 + MyMemory，谁先成功用谁）"
    SOURCE_HINT = (
        "竞速含 clients5.google.com 与 MyMemory；"
        "gtx（稳定 429）与两个 Lingva 镜像（Cloudflare 403）已停用。"
    )
    HOTKEY_LABEL = "快捷键设置（格式：ctrl+l / tab+q）"
    HOTKEY_APPLY = "应用并保存"
    #: 第 4 组是新增功能（中译英输入框），见 KNOWN_ISSUES.md 偏差 D15
    HOTKEY_FIELDS = (("翻译", "translate"), ("截图", "snip"), ("收录", "save_last"), ("中译英", "input"))
    TTS_VOLUME_LABEL = "英文朗读音量（独立于系统音量）"
    RECENT_TRANSLATIONS_LABEL = "最近 3 条翻译（可直接收录生词本）"
    # —— 代理（KNOWN_ISSUES.md #25）——
    PROXY_LABEL = "网络代理（翻译请求走这里）"
    PROXY_MODE_OFF = "直连"
    PROXY_MODE_SYSTEM = "跟随系统代理"
    PROXY_MODE_CUSTOM = "自定义"
    PROXY_APPLY = "应用"
    PROXY_TEST = "测试代理"
    PROXY_HINT = "直连即可用 clients5 / MyMemory；本地 Clash 填 127.0.0.1:7897；香港出口走 WireGuard 的 10.8.0.6"
    PROXY_APPLIED = "代理已应用：{detail}"
    PROXY_TESTING = "正在测试代理…"
    PROXY_TEST_RESULT = "代理测试：{detail}"
    RECENT_SAVED_LABEL = "最近加入生词本（可一键删除）"
    EMPTY_RECENT = "（暂无）"
    COLLECT_BUTTON = "收录"
    DELETE_BUTTON = "删除"
    CLEAR_LOG = "清空记录"
    LOG_TITLE = "翻译记录"
    FLOATING_COLLECT_BUTTON = "收录生词本"
    READY = "就绪"
    HOTKEY_ERROR_FORMAT = "快捷键格式错误：{name}={value}（示例：ctrl+l / tab+q）"
    #: 新增功能加入第 4 组热键（中译英输入框），故原版"3 组"改为"4 组"（偏差 D15）
    HOTKEY_DUPLICATE = "快捷键不能重复，请设置 4 组不同组合"
    SNIP_HINT = "拖拽框选要 OCR 的区域（松开鼠标确认 / ESC 取消）"
    SNIP_HINT_SHORT = "截图模式：拖拽选择区域，ESC 取消"
    SNIP_CANVAS_HINT = "拖拽框选要 OCR 翻译的区域（松开鼠标确认 / ESC 取消）"
    SNIP_SIZE = "区域大小：{width} × {height}"
    SNIP_TOO_SMALL = "截图区域太小，已取消"
    SNIP_OCR_RUNNING = "OCR 识别中…"
    SNIP_CANCELLED = "已取消截图"
    SNIP_FAILED = "截图模式启动失败：{error}"

    @staticmethod
    def status_enabled(hotkeys: dict[str, str]) -> str:
        return (
            f"已开启 — {label_or_placeholder(hotkeys.get('translate', ''))} 划词翻译，"
            f"{label_or_placeholder(hotkeys.get('snip', ''))} 截图 OCR，"
            f"{label_or_placeholder(hotkeys.get('save_last', ''))} 收录最近一条，"
            f"{label_or_placeholder(hotkeys.get('input', ''))} 中译英输入框"
        )

    @staticmethod
    def status_disabled(hotkeys: dict[str, str]) -> str:
        return (
            f"已关闭 — 不会响应 {label_or_placeholder(hotkeys.get('translate', ''))} / "
            f"{label_or_placeholder(hotkeys.get('snip', ''))} / "
            f"{label_or_placeholder(hotkeys.get('save_last', ''))}"
        )

    @staticmethod
    def hotkey_hint(hotkeys: dict[str, str]) -> str:
        return (
            f"划词翻译：{label_or_placeholder(hotkeys.get('translate', ''))}  |  "
            f"截图 OCR：{label_or_placeholder(hotkeys.get('snip', ''))}  |  "
            f"收录：{label_or_placeholder(hotkeys.get('save_last', ''))}  |  "
            f"中译英：{label_or_placeholder(hotkeys.get('input', ''))}"
        )

    @staticmethod
    def no_selection_hint(hotkey_label: str) -> str:
        return f"未检测到选中文本，请先划词再按 {hotkey_label}"

    @staticmethod
    def capture_failed_hint(hotkey_label: str) -> str:
        """取词失败（模拟 Ctrl+C 没有生效）时的提示。

        新增文案（原版没有这个分支）：原版把这种情况当成"取到了内容"，于是把剪贴板里的
        旧内容（例如上次复制的网址）当原文翻译，用户只会看到"网址 => 网址"。见 KNOWN_ISSUES.md #20。
        """
        return (
            "取词失败：模拟 Ctrl+C 没有生效，本次已放弃翻译（没有拿剪贴板里的旧内容顶替）。"
            f"当前热键：{hotkey_label}。常见原因：① 该热键被浏览器/系统占用（例如 Ctrl+L 在浏览器里是"
            "聚焦地址栏）；② 该区域禁止复制（PDF 阅读器、图片、跨域 iframe）；③ 选区已丢失。"
        )

    @staticmethod
    def capture_modifier_hint(hotkey_label: str) -> str:
        """取词失败、且热键里的 Alt/Shift/Win 一直按着时的提示（KNOWN_ISSUES #22）。

        实测结论：Alt 还按着时注入的 Ctrl+C 会被目标程序当成 Ctrl+Alt+C，复制不会发生。
        """
        return (
            f"取词失败：{hotkey_label} 里的修饰键（Alt/Shift/Win）在复制瞬间仍按着，"
            "Ctrl+C 被系统当成了别的组合键，所以没有取到文本（已放弃翻译）。"
            "请松开修饰键再按一次；或把翻译热键改成 Ctrl 组合（例如 ctrl+f9）最稳。"
        )

    #: 原 ``main.py:1171`` 传给 ``_translate_text_job`` 的 ``no_text_hint``
    NO_SNIP_TEXT_HINT = "截图区域未识别到文字，请重试更清晰区域"


class CollectText:
    """收录/删除的提示文案（原版四种反馈 + 三种删除反馈）。"""

    #: 收录反馈的标题（原 ``_ui_vocab_feedback("生词本", ...)`` 的第一个参数）
    TITLE = "生词本"

    @staticmethod
    def for_outcome(kind: CollectKind, word: str, translate_hotkey_label: str = "") -> tuple[str, str] | None:
        """返回 ``(标题, 正文)``；``NO_LAST`` 需要当前翻译热键标签。"""
        if kind is CollectKind.ADDED:
            return (CollectText.TITLE, f"已记录到生词本：{word}")
        if kind is CollectKind.DUPLICATE:
            return (CollectText.TITLE, f"已存在于生词本：{word}")
        if kind is CollectKind.EMPTY:
            return (CollectText.TITLE, "暂无可记录内容：请先翻译一次")
        if kind is CollectKind.FAILED:
            return (CollectText.TITLE, "记录失败：写入生词本出错")
        if kind is CollectKind.NO_LAST:
            return (CollectText.TITLE, f"暂无可收录内容：请先按 {translate_hotkey_label} 翻译一次")
        return None

    @staticmethod
    def for_delete(kind: DeleteKind, word: str) -> tuple[str, bool]:
        """返回 ``(文案, 是否同时弹悬浮提示)``。

        原 ``_delete_saved_word``（``main.py:916-934``）四个分支**都不弹悬浮提示**：
        ``DELETED`` 走"追加日志 + 状态栏"，其余三个只改状态栏。故第二项恒为 ``False``。
        """
        if kind is DeleteKind.DELETED:
            return (f"已删除：{word}", False)
        if kind is DeleteKind.NOT_FOUND:
            return (f"未找到词条：{word}", False)
        if kind is DeleteKind.FAILED:
            return (f"删除失败：{word}", False)
        return ("该条记录为空", False)


# ———————————————————————————— 生词复习 ————————————————————————————


class ReviewText:
    TITLE = "SnapTranslate — 生词复习"
    SUBTITLE = "自评保存熟练度 · DeepSeek 可批量生成英例与中译"
    HEADING = "生词复习"
    VOCAB_LABEL = "词表"
    BROWSE = "浏览…"
    SORT_LABEL = "复习顺序"
    READ_LABEL = "朗读（系统英文语音）"
    TTS_VOLUME_LABEL = "朗读音量（独立于系统音量）"
    MANUAL_REPEAT = "手动重读当前词条"
    SHOW_MEANING = "显示/隐藏释义"
    SHOW_EXAMPLE = "显示/隐藏例句"
    SHOW_EXAMPLE_ZH = "显示/隐藏例句翻译"
    GRADE_HINT = "自评（是否已看释义/例句会影响加减分）"
    GRADE_KNOW = "认识"
    GRADE_VAGUE = "模糊"
    GRADE_UNKNOWN = "不认识"
    MEANING_PLACEHOLDER = "（点击按钮显示释义/例句）"
    MEANING_HIDDEN = "（已隐藏，再次点击显示）"
    EXAMPLE_EMPTY = "例句：（暂无）"
    EXAMPLE_MISSING = "（暂无）"
    EXAMPLE_EN_PREFIX = "例句（英）："
    EXAMPLE_ZH_PREFIX = "例句（译）："
    EMPTY_VOCAB = "（词表为空或无法读取）"
    READY = "就绪"

    #: 原 ``vocab_review.py:557-561`` 文件选择对话框标题
    PICK_TITLE = "选择 vocab.json"
    #: 原 ``vocab_review.py:188`` 初始值（"熟练度 —" 含一个全角破折号）
    SCORE_PLACEHOLDER = "熟练度 —"
    #: 原 ``_show_card`` 在"无当前词条"分支把释义清空
    MEANING_EMPTY = ""

    SORT_MODES: tuple[tuple[str, str], ...] = (
        ("随机", "random"),
        ("得分低→高", "score_asc"),
        ("得分高→低", "score_desc"),
    )
    READ_MODES: tuple[tuple[str, str], ...] = (
        ("不朗读", "none"),
        ("单词", "word"),
        ("单词+例句", "word_example"),
    )

    GEN_BUTTON = "用 DeepSeek 生成英例句 + 中译（约 {pending} 条待补全）"
    API_KEY_PROMPT_TITLE = "配置 DeepSeek API Key"
    API_KEY_PROMPT_BODY = "首次使用需要配置 DeepSeek API Key。\n请输入后将保存到本地 api_key.txt："
    API_KEY_EMPTY = "API Key 不能为空。"
    API_KEY_SAVE_FAILED = "保存失败"
    MISSING_DEPENDENCY_TITLE = "缺少依赖"
    MISSING_DEPENDENCY_BODY = "请先安装：pip install openai\n然后重新运行本程序。"
    SAVE_FAILED_TITLE = "保存失败"
    NOTHING_TO_GENERATE_TITLE = "提示"
    NOTHING_TO_GENERATE_BODY = "没有需要生成的例句（英文与中译均已齐全）。"
    GENERATING = "正在请求 DeepSeek…"
    GENERATE_DONE_TITLE = "完成"
    GENERATE_DONE_BODY = "例句生成结束。\n成功写入：{ok} / 本次任务：{total}"
    GENERATE_ABORTED_TITLE = "批量生成已中止"
    GENERATE_INSUFFICIENT_BALANCE = (
        "DeepSeek 返回 402：账户余额不足（Insufficient Balance）。\n"
        "请登录 DeepSeek 开放平台充值或更换有余额的 API Key；"
        "这不是本程序 bug，未充值成功前批量生成会持续失败。"
    )
    GENERATE_ABORTED_HINT = "已因余额不足中止，后续请求已跳过（避免无意义重试）。"
    #: 402 中止弹窗的正文（原 ``vocab_review.py:999-1002`` 的 f-string）
    GENERATE_ABORTED_BODY = "{reason}\n\n已成功写入：{ok} / 本次计划：{total}"
    GENERATE_FINISHED_STATUS = "完成：成功 {ok} / 计划 {total}"

    GRADE_LABELS: dict[Grade, str] = {
        Grade.KNOW: "认识",
        Grade.VAGUE: "模糊",
        Grade.UNKNOWN: "不认识",
    }
    REVEALED_HINT = "已看释义/例句"
    UNREVEALED_HINT = "未看释义/例句"

    @staticmethod
    def grade_log(word: str, grade: Grade, revealed: bool, old: float, new: float, delta: float) -> str:
        label = ReviewText.GRADE_LABELS.get(grade, str(grade))
        hint = ReviewText.REVEALED_HINT if revealed else ReviewText.UNREVEALED_HINT
        return f"评分「{word}」{label}（{hint}）{old:.1f} → {new:.1f}（Δ{delta:+.1f}）"

    @staticmethod
    def progress(position: int, total: int) -> str:
        return f"{position + 1} / {total}"

    @staticmethod
    def score(score: float, reviews: int, max_score: float) -> str:
        return f"熟练度 {score:.1f} / {max_score:.0f}（已评 {reviews} 次）"

    @staticmethod
    def meaning(meaning: str) -> str:
        return f"释义：{meaning}"

    @staticmethod
    def item_log(order: int, total: int, word: str) -> str:
        return f"[{order}/{total}] OK：{word}"

    @staticmethod
    def item_fail_log(order: int, total: int, word: str, error: str) -> str:
        return f"[{order}/{total}] 失败：{word} — {error}"

    @staticmethod
    def backup_log(ok: bool, detail: str) -> str:
        return f"启动备份已创建：{detail}" if ok else detail

    @staticmethod
    def loaded_log(path: str, total: int, pending: int) -> str:
        return f"已加载 {path}，共 {total} 条；待生成/待补全（英或中译）约 {pending} 条。"


# ———————————————————————————— Web 复习页 ————————————————————————————


class WebText:
    PAGE_TITLE = "SnapTranslate 生词复习"
    TITLE = "📘 SnapTranslate"
    SETTINGS = "设置"
    VOCAB_PATH = "词表路径"
    LOAD_VOCAB = "加载词表"
    SORT_LABEL = "复习顺序"
    DEEPSEEK = "DeepSeek（可选）"
    KEY_PATH = "API Key 文件路径"
    MANUAL_KEY = "手动填写 API Key（仅缺少本地文件时）"
    SORT_OPTIONS = {"random": "随机", "score_asc": "得分低→高", "score_desc": "得分高→低"}
    READ_OPTIONS = {
        "none": "不朗读",
        "word": "只朗读单词",
        "word_example": "朗读单词+例句（显示例句后才读例句）",
    }
    READ_LABEL = "自动朗读模式"
    SHOW_MEANING = "显示 / 隐藏 释义"
    SHOW_EXAMPLE = "显示 / 隐藏 例句"
    SHOW_EXAMPLE_ZH = "显示 / 隐藏 例句翻译"
    SPEAK_WORD = "朗读单词"
    SPEAK_EXAMPLE = "朗读例句"
    MEANING = "释义：{meaning}"
    EXAMPLE_EN = "**例句（英）**"
    EXAMPLE_ZH = "**例句（译）**"
    EXAMPLE_MISSING = "（暂无）"
    REVEAL_HINT = "点击按钮后显示释义/例句。"
    SCORE = "熟练度：**{score:.1f}**"
    VOCAB_LINE = "词表：`{path}`"
    COUNT_LINE = "条目总数：**{total}**，待补全例句：**{pending}**"
    EMPTY_VOCAB = "词表为空。"
    MISSING_DEPENDENCY = "缺少依赖：请先安装 openai。"
    NO_KEY_WARNING = "未检测到 API Key，请在侧边栏填写后重试。"
    KEY_SAVE_FAILED = "保存 API Key 失败：{error}"
    GENERATE_BUTTON = "用 DeepSeek 生成英例句+中译（约 {pending} 条）"
    REFRESH = "刷新读取磁盘词表"
    NOTHING_TO_GENERATE = "没有需要生成的条目。"
    GENERATING = "[{order}/{total}] 生成中：{word}"
    GENERATE_FAILED = "[{order}/{total}] 失败：{word} — {error}"
    GENERATE_INSUFFICIENT_BALANCE = "检测到余额不足（402），已中止后续生成。"
    GENERATE_DONE = "完成：成功 {ok} / 计划 {total}"
    GENERATE_DONE_MSG = "批量生成完成：成功 {ok} / 计划 {total}"
    BACKUP_PREFIX = "启动备份：{detail}"
    GRADE_SAVE_FAILED = "保存失败：{error}"
    #: 三档自评按钮标签（键为领域枚举；原版是三个中文字面量按钮）
    GRADE_LABELS: dict[Grade, str] = {
        Grade.KNOW: "认识",
        Grade.VAGUE: "模糊",
        Grade.UNKNOWN: "不认识",
    }

    @staticmethod
    def grade_saved(old: float, new: float, delta: float) -> str:
        """评分落盘后的一行提示（原 ``vocab_review_web.py:232`` 的格式逐字保留）。"""
        return f"评分已保存：{old:.1f} -> {new:.1f}（Δ{delta:+.1f}）"


# ———————————————————————————— 词表后台管理 ————————————————————————————


class AdminText:
    TITLE = "词表后台管理功能"
    VOCAB_PATH = "词表路径"
    BACKUP_DIR = "备份目录"
    STATUS_BOX = "状态"
    READ_FAILED = "读取失败"
    TOTAL = "词表总数：{value}"
    WITH_EXAMPLE = "有例句+翻译：{value}"
    PENDING = "待补全例句：{value}"
    BACKUP_COUNT = "备份文件数：{value}"
    LATEST_BACKUP = "最新备份：{value}"
    NONE = "暂无"
    REFRESH = "刷新状态"
    RESET_SCORES = "1) 词表评分重置系统"
    CLEANUP_BACKUPS = "2) 删除备份（仅保留最新1个）"
    READY = "就绪"
    ERROR_TITLE = "错误"
    FAILED_TITLE = "失败"
    VOCAB_MISSING = "找不到词表文件：{path}"
    RESET_CONFIRM_TITLE = "确认"
    RESET_CONFIRM_BODY = "确定重置所有词条评分和复习次数吗？"
    CLEANUP_CONFIRM_BODY = "确定删除旧备份，仅保留最新 1 个吗？"
    RESET_DONE = "已重置 {count} 条：score=50，reviews=0"
    CLEANUP_DONE = "已删除 {removed} 个备份，保留：{name}"
    CLEANUP_NOTHING = "没有可删除的备份文件。"
    READ_FAILED_STATUS = "读取词表失败：{error}"


class InputText:
    """中译英输入框的文案（**新增功能**，原版没有这条路径）。"""

    TITLE = "中译英"
    HINT = "Enter 翻译 · Shift+Enter 换行 · Esc 关闭 · 点回框内继续输入"
    PLACEHOLDER = "（在此输入中文，回车翻译成英文）"
    OUTPUT_PLACEHOLDER = "（英文会显示在这里）"
    PENDING = "翻译中…"
    EMPTY = "请先输入要翻译的中文"
    TRUNCATED = "输入过长，已只翻译前 {limit} 个字符"
    TRANSLATE_BUTTON = "翻译"
    CLOSE_BUTTON = "关闭"


class LauncherText:
    """启动器控制台 + 托盘的文案（**新增功能**，原版没有统一入口）。"""

    TITLE = "SnapTranslate 控制台"
    SUBTITLE = "一个入口管三个窗口；关掉本窗口后可继续驻留托盘"
    STAY_IN_TRAY = "关闭窗口时最小化到托盘常驻"
    RUNNING = "运行中"
    STOPPED = "未运行"
    OPEN_BUTTON = "打开"
    OPEN_DATA_DIR = "打开数据目录"
    QUIT = "退出"
    DATA_DIR_LINE = "数据目录：{path}"
    LAUNCHED = "已启动：{label}"
    FOCUSED = "已唤起：{label}"
    TRAY_TOOLTIP = "SnapTranslate — 双击打开控制台"
    TRAY_PANEL = "打开控制台"
    TRAY_QUIT = "退出"
    TRAY_ITEMS_PREFIX = ""
    TRAY_HINT = "托盘已就绪：右键图标可切换窗口"
    TRAY_UNAVAILABLE = "托盘不可用（仍可用本窗口切换；退出后窗口会一起关）"

    #: 三个子应用：``(键名, 按钮文字, 一句话说明)``
    APPS = (
        ("translate", "划词翻译", "选中文字后按热键翻译；重启后保持托盘常驻"),
        ("review", "生词复习", "自评熟练度、批量补例句"),
        ("admin", "词表管理", "统计 / 重置评分 / 清理备份"),
    )


__all__ = [
    "AdminText",
    "CollectText",
    "ErrorTitle",
    "InputText",
    "LauncherText",
    "ReviewText",
    "Stage",
    "StatusText",
    "WebText",
    "WindowText",
]
