# 打包说明（PyInstaller）

一行命令：

```powershell
pip install pyinstaller            # PyInstaller ≥ 6.15 才支持 Python 3.14
python scripts\build_packages.py            # 主包（三个 Tk 应用 + 启动器/托盘）
python scripts\build_packages.py --web      # 主包 + Web 包（含 streamlit）
python scripts\build_packages.py --onefile  # 出单文件 exe
python scripts\build_packages.py --clean    # 构建前清 dist/work
```

打完会**自动对产物跑一遍 `--self-check`**（路径 / 日志 / 容器装配 / tkinter / 托盘 / 热键 /
单实例 / 图标），通过才算成功。也可以自己跑：

```powershell
dist\SnapTranslate\SnapTranslate.exe --self-check
# 报告写在 exe 同级的 self-check.txt（窗口程序没有控制台，所以报告落文件）
```

## 两个包

| 包 | 产物 | 内容 | 体积（本机实测） | 状态 |
|---|---|---|---|---|
| 主包 | `dist/SnapTranslate/` | 启动器 + 托盘 + 划词翻译 / 生词复习 / 词表管理 | **约 52 MB** | ✅ 已验收（`--self-check` 全绿 + 面板/托盘/单实例/子窗口实测） |
| Web 包 | `dist/SnapTranslateWeb/` | Streamlit 网页复习端 | **约 195 MB** | ⚠️ **实验性**：服务能起（`/_stcore/health` 返回 200、端口 8501 正确），但冻结后首页 `/` 仍 404（streamlit 1.64 的静态资源路径在 PyInstaller 里没解析到），**暂时请用源码/虚拟环境跑网页端** |

主包**刻意排除 streamlit**：它会连带 pandas / pyarrow / altair / numpy，实测多出约 220 MB，
而这三个 Tk 应用一个字都用不到（见 `snaptranslate.spec` 的 `excludes`）。

> Web 包的后续方向（留给以后）：把 streamlit 的 `static/` 目录用 `--add-data` 落到
> `_internal/streamlit/static`（已在做，353 个文件在位）之外，还需要让 streamlit 运行时
> 通过 `importlib.resources` 找到它；常见做法是打一个 `runtime_hook` 在导入前把
> `streamlit.web.server.server` 的静态目录改成绝对路径，或退到 `streamlit.web.cli` +
> 显式端口的组合再验证。

## 发布（exe 只进 Release，仓库只留源码）

**约定**：仓库里**不放** exe / 便携包（`.gitignore` 已排除 `dist/`、`releases/`、`*.exe`、`*.zip`），
想改代码的人 `git clone` 拿到的就是纯源码 + 构建脚本；要"下载即用"的人从 **Releases** 拿便携包。

```powershell
python scripts\build_packages.py                        # 1) 打包（自动跑产物自检）
python scripts\make_release.py --tag v2.1.0             # 2) 生成 releases\SnapTranslate-v2.1.0-win64-portable.zip
python scripts\make_release.py --tag v2.1.0 --upload    # 3) 建/更新 GitHub Release 并上传（需 GITHUB_TOKEN）
```

第 3 步也可以手动做：在 GitHub 上 `Releases → Draft a new release`，选标签后把 zip 拖进去。

`make_release.py` 做的事：清掉本机运行期数据（`vocab.json` / 设置 / 日志 / 自检报告）→
打成带顶层目录的便携 zip → 附一份 `使用说明.txt`；上传是幂等的（同名资产先删后传）。

## 用法（主包）

```powershell
.\SnapTranslate.exe                 # 控制台窗口 + 托盘常驻
.\SnapTranslate.exe --app=translate # 划词翻译
.\SnapTranslate.exe --app=review    # 生词复习
.\SnapTranslate.exe --app=admin     # 词表管理
.\SnapTranslate.exe --self-check    # 自检
```

- 控制台里的三个按钮 / 托盘菜单都能启动对应窗口；**已经开着就唤到前台**，不会开出第二个；
- 每个子应用都有**单实例互斥**：热键是轮询式的，两个划词实例会同时响应同一次划词并互相覆盖 `vocab.json`；
- 勾选"关闭窗口时最小化到托盘常驻"后，关窗只是隐藏；**退出**请用托盘菜单或控制台里的"退出"
  （它会一并结束由它拉起的子进程）。

## 数据目录（便携）

打包后数据目录 = **exe 所在目录**（`config/paths.py` 里对 `sys.frozen` 做了处理）：

```
dist\SnapTranslate\
├─ SnapTranslate.exe
├─ _internal\...           运行时（含 assets\snaptranslate.ico）
├─ vocab.json              生词本（首次收录时创建）
├─ main_settings.json      热键 / 音量 / 代理
├─ vocab_review_settings.json
├─ backups\                词表自动备份
├─ 划词日志.txt             运行日志（窗口程序没有控制台，日志落这里）
└─ self-check.txt          自检报告（跑 --self-check 后生成）
```

**迁移方式＝整个文件夹拷走**。也可以用环境变量指到别处（两种运行方式都优先）：

```powershell
$env:SNAPTRANSLATE_DATA_DIR = "D:\SnapTranslateData"
```

> `--onefile` 也是同样语义：数据写在 **exe 同级目录**，不会写进临时解包目录。

## 图标

`assets/snaptranslate.ico` 由原仓库 `image/logo.png` 生成（多尺寸 16/24/32/48/64/128/256），
托盘、exe 图标、窗口图标共用同一份；生成命令见 `scripts/` 里的一次性脚本注释（Pillow `save(format="ICO", sizes=...)`）。

## 已知限制

- **未做代码签名**：首次运行会有 SmartScreen 提示，点"仍要运行"即可；要发布给别人建议买证书签一下。
- **Tesseract 不随包分发**：截图 OCR 需要用户自己装 Tesseract + `eng`/`chi_sim` 语言包（与原版一致，见 `KNOWN_ISSUES.md` #16）。
- **仅 Windows**：整个程序依赖 Win32（`GetAsyncKeyState` / 剪贴板 / `Shell_NotifyIcon`）。
- 主包的 `--app=web` 会提示"主包不含 Web 复习端"——那是预期行为，请用 Web 包或源码运行。
- **Web 包还没验收通过**（见上表）：只用主包的话完全不受影响。

## 版本与修复记录（打包相关）

| 版本 | 内容 |
|---|---|
| 2.1.0 | 第一版打包（onedir 便携包 + 启动器/托盘/单实例）。**已知问题**：划词翻译朗读时会闪一个 PowerShell 窗口 |
| 2.1.1 | 修复闪窗：所有子进程统一走 `infrastructure/process/no_window.py`（`CREATE_NO_WINDOW` + `SW_HIDE`）；附 `tests/test_no_window.py` 静态门禁 |
