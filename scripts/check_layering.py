"""分层依赖方向静态校验（AST，不执行任何代码）。

用法::

    python scripts/check_layering.py            # 扫描默认工程
    python scripts/check_layering.py <root>     # 指定工程根目录

规则见 ARCHITECTURE.md §1：

======================  ================================================
层                       允许 import 的项目内层
======================  ================================================
``config``                （无，只允许标准库）
``domain``                domain
``infrastructure``        domain, config, infrastructure
``application``           domain, config, application
``presentation``          domain, application, config, presentation
``bootstrap``             全部
======================  ================================================

另外：``config`` 与 ``domain`` 不允许 import 任何第三方库（保持叶子层纯净）。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PACKAGE_ROOT_PARTS = ("src", "snaptranslate")

LAYER_ALLOWED: dict[str, set[str]] = {
    "config": set(),
    "domain": {"domain"},
    "infrastructure": {"domain", "config", "infrastructure"},
    "application": {"domain", "config", "application"},
    "presentation": {"domain", "application", "config", "presentation"},
    "bootstrap": {"domain", "application", "config", "infrastructure", "presentation", "bootstrap"},
}

#: 只允许标准库的层
STDLIB_ONLY_LAYERS = {"config", "domain"}

STDLIB = set(getattr(sys, "stdlib_module_names", set()))


def _layer_of(path: Path, package_dir: Path) -> str | None:
    try:
        relative = path.relative_to(package_dir)
    except ValueError:
        return None
    if len(relative.parts) < 2:
        return None
    layer = relative.parts[0]
    if layer.endswith(".py"):
        return None
    return layer if layer in LAYER_ALLOWED else None


def _iter_python_files(root: Path):
    package_dir = root.joinpath(*PACKAGE_ROOT_PARTS)
    if not package_dir.is_dir():
        return
    for path in sorted(package_dir.rglob("*.py")):
        yield path, package_dir


def scan(root: Path) -> list[str]:
    """返回违规描述列表；空列表表示合规。"""
    violations: list[str] = []
    for path, package_dir in _iter_python_files(root):
        layer = _layer_of(path, package_dir)
        if layer is None:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:  # 语法错误直接算违规
            violations.append(f"{path}: 语法错误 {exc}")
            continue
        for node in ast.walk(tree):
            for module, lineno in _imported_modules(node):
                if module is None:
                    continue
                top = module.split(".", 1)[0]
                if top == "snaptranslate":
                    parts = module.split(".")
                    target = parts[1] if len(parts) > 1 else ""
                    if target and target not in LAYER_ALLOWED[layer]:
                        violations.append(
                            f"{path}:{lineno}: {layer} 层不得 import snaptranslate.{target}（允许："
                            f"{sorted(LAYER_ALLOWED[layer]) or '仅标准库'}）"
                        )
                elif layer in STDLIB_ONLY_LAYERS and top not in STDLIB:
                    violations.append(
                        f"{path}:{lineno}: {layer} 层不得依赖第三方库 {top}（只允许标准库）"
                    )
    return violations


def _imported_modules(node: ast.AST):
    if isinstance(node, ast.Import):
        for alias in node.names:
            yield alias.name, node.lineno
    elif isinstance(node, ast.ImportFrom):
        # 相对 import（level>0）视为包内引用，永远合规
        if node.level and node.level > 0:
            yield None, node.lineno
        else:
            yield node.module, node.lineno


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    root = Path(argv[0]).resolve() if argv else Path(__file__).resolve().parents[1]
    violations = scan(root)
    if violations:
        print(f"[FAIL] 分层校验未通过，共 {len(violations)} 条：")
        for item in violations:
            print(f"  - {item}")
        return 1
    print(f"[OK] 分层校验通过：{root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
