# SnapTranslate（分层重构版）

Windows 划词翻译 + 截图 OCR + 生词本复习工具。本仓库是
[ChenAI-TGF/SnapTranslate](https://github.com/ChenAI-TGF/SnapTranslate) **v2.0（4 个裸脚本、约 3500 行）的纯结构重构版**：
功能与行为保持不变，代码改为分层、模块化、依赖单向的大型工程结构。

> **行为等价**是硬指标，不是口号：`scripts/parity_check.py` 会把原版脚本与新实现放在
> 同一批输入上逐函数对拍（当前 **173 项用例、0 差异**）。

---

## 快速开始

```powershell
# 1) 安装依赖（与原版一致，未引入任何新依赖）
pip install -r requirements.txt

# 2) 任选一种启动方式
python entrypoints\main.py                     # 划词翻译主窗口
python entrypoints\vocab_review.py             # 生词复习（桌面）
streamlit run entrypoints\vocab_review_web.py  # 生词复习（网页）
python entrypoints\set.py                      # 词表后台管理
```

也可以用 console_scripts（需先 `pip install -e .`）：

```powershell
snaptranslate              # 划词翻译
snaptranslate-review       # 生词复习（桌面）
snaptranslate-review-web   # 生词复习（网页）
snaptranslate-admin        # 词表后台管理
```

数据文件默认就在**工程根目录**（与原版"脚本与数据同目录"一致）：
`vocab.json`、`api_key.txt`、`main_settings.json`、`vocab_review_settings.json`、`backups/`。
如需换目录（例如把数据放到别处），用环境变量覆盖：

```powershell
$env:SNAPTRANSLATE_DATA_DIR = "D:\SnapTranslateData"
```

> ⚠️ 这些**运行期数据不入库**（已写进 `.gitignore`）：词表是你的个人生词本、`api_key.txt` 是密钥、
> 设置里还有热键与代理。换电脑时按需手动拷过去即可（见下一节）。

---

## 换一台电脑 / 克隆后怎么用

```powershell
git clone https://github.com/LINGJIU11/SnapTranslate-Refactor.git
cd SnapTranslate-Refactor
pip install -r requirements.txt
python entrypoints\main.py
```

克隆下来的是**纯代码**，运行期数据需要自己准备（都可以后补，缺了也能启动）：

| 文件 | 作用 | 不带会怎样 |
|---|---|---|
| `vocab.json` | 生词本 | 复习页显示"词表为空"，划词翻译照常可用；从旧机器拷一份即可 |
| `api_key.txt` | DeepSeek Key（生成例句用） | 点"生成例句"时会让你在界面里填 |
| `main_settings.json` | 热键 / TTS 音量 / 代理模式 | 用默认值启动（`alt+z` / `tab+q` / `tab+e`，直连） |
| `vocab_review_settings.json` | 复习端音量等 | 用默认值 |
| `backups/` | 词表自动备份 | 首次运行自动创建 |

环境相关（按需）：截图 OCR 需要本机装 **Tesseract** 及语言包；界面里的代理一行可选
**直连 / 跟随系统代理 / 自定义**（用 Clash 就填 `http://127.0.0.1:7897`）。
本工具依赖 Win32 API（`GetAsyncKeyState` / `SendInput` / 剪贴板），**只在 Windows 上跑**。

---

## 目录地图（文件分级）

```
SnapTranslate重构/
├─ ARCHITECTURE.md        分层架构契约（依赖方向、端口与适配器、关键设计决策）
├─ FILE_MAP.md            文件分级清单 + 原版函数 → 新文件的逐项映射
├─ KNOWN_ISSUES.md        原样保留的缺陷登记 + 本轮有意偏差清单
├─ pyproject.toml         依赖与 console_scripts
├─ requirements.txt       与原版一致的直接依赖
├─ entrypoints/           与原版同名的薄壳入口
├─ scripts/               分层校验 / 等价性对拍 / 冒烟自检
├─ src/snaptranslate/
│   ├─ config/            路径、主题、应用元信息（叶子层）
│   ├─ domain/            模型、领域服务、端口 Protocol（零 IO、零框架）
│   ├─ infrastructure/    翻译源、OCR、TTS、持久化、Win32 输入、DeepSeek（适配器）
│   ├─ application/       用例编排 + 依赖包（只依赖端口）
│   ├─ presentation/      Tk 窗口、Streamlit 页面、统一文案表
│   └─ bootstrap/         组合根：容器、装配、CLI 与 Streamlit 进程入口
└─ tests/                 215 个单元测试（含分层约束与 GUI 事件链回归）
```

依赖方向（`scripts/check_layering.py` 会静态校验，违反即失败）：

```
presentation → application → domain
      ↓             ↓          ↑
      └──→ infrastructure ─────┘
                 ↓
              config
```

---

## 验证

```powershell
python scripts\check_layering.py              # 分层依赖方向（AST 静态检查）
python -m unittest discover -s tests -t .     # 单元测试（215 项）
python scripts\smoke_check.py                 # 全包导入 + 依赖装配 + 关键纯函数
python scripts\parity_check.py <原版目录>       # 与原版逐函数/流程对拍（173 项，默认 C:\Translate\SnapTranslate）
python scripts\gui_smoke.py --with-tk         # 真实创建三个 Tk 窗口后立即销毁（含事件链断言）
python scripts\web_smoke.py                   # Streamlit 页面渲染 + 与原版结构对拍
python scripts\verify_all.py                  # 上面六项一次跑完，任一失败即非 0 退出
```

六者都是"可执行的约束"：分层违规、行为漂移、装配断裂、界面建不起来都会让命令非 0 退出。

---

## 版本与标签

按交付阶段打了标签，换电脑时可以直接检出某个阶段的状态看差异：

| 标签 | 内容 |
|---|---|
| `stage1-refactor` | 阶段一：纯结构重构交付（116 模块，行为等价基线） |
| `stage1.1-capture-fix` | 取词失败不再静默翻译剪贴板旧内容；改热键立即生效 |
| `stage1.2-modifier-fix` | Alt 组合热键不再"毒化"注入的 Ctrl+C |
| `stage1.3-floating-card` | 悬浮卡片按热键瞬间锚点显示 + 不再定时消失 |
| `stage1.4-proxy` | 代理支持（直连 / 跟随系统 / 自定义） |
| `stage1.5-prune-and-log-label` | 砍掉失效线路（竞速 5 路 → 2 路）；引擎标签只进日志 |
| `stage1.6-review-advance-fix` | 复习界面评分后卡片前进（回归修复）+ 仓库整理 |

```powershell
git tag                     # 看全部标签
git checkout stage1.5-prune-and-log-label   # 回到某个阶段
```

---

## 主要改进点（相对于 4 个裸脚本）

| 方面 | 原版 | 现在 |
|---|---|---|
| 文件组织 | 4 个巨型脚本（`main.py` 1918 行） | 120 个 60–300 行的单职责模块，按层分目录 |
| 依赖关系 | 全局常量 + 模块级函数互相调用 | 六层单向依赖 + 端口/适配器，静态可校验 |
| 重复实现 | 词表 IO / 评分 / 热键 / 例句解析 / 主题色各写 2–4 份 | 收敛为单一实现（**语义差异显式命名**，不偷偷合并） |
| 可测试性 | 逻辑与 Tk/网络耦合，无法单测 | 用例层依赖 Protocol，215 个测试用假适配器跑，不联网不起 GUI |
| 界面文案 | 散落在业务逻辑里 | 集中在 `presentation/texts.py`，两端共用 |
| 入口 | 必须 `python xxx.py` 且依赖当前目录 | 薄壳入口 + console_scripts + 数据目录可配置 |
| 行为验证 | 无 | 与原版逐函数对拍脚本（173 项） |

**阶段一（纯结构重构）不包含**任何功能改动：翻译源仍是原来的免费逆向接口集合，界面布局与文案保持一致，
已知缺陷原样保留并登记在 `KNOWN_ISSUES.md`（含证据与位置），供后续单独排期修复。

**阶段一之后**按真机实测反馈做了 9 处修复（`KNOWN_ISSUES.md §五` F1–F9）：取词失败不再静默、
热键热更新、Alt 组合不再毒化取词、卡片按热键瞬间的锚点显示、卡片不再自动消失、新增代理设置、
**砍掉实测失效的 gtx / Lingva 两条线路（竞速 5 路 → 2 路）**、**引擎标签只进日志不进卡片**、
**复习界面评分后卡片正确前进（#28，阶段一回归）**。
