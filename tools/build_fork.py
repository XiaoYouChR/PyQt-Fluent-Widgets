from __future__ import annotations

import ast
import pprint
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PKG_ROOT = REPO_ROOT / "qfluentwidgets"
SYMBOLS_PATH = PKG_ROOT / "_symbols.py"
STYLE_SHEET_PATH = PKG_ROOT / "common" / "style_sheet.py"
QRC_PATH = PKG_ROOT / "_rc" / "resource.qrc"
RCC_PATH = PKG_ROOT / "_rc" / "resource.rcc"

PACKAGES = (
    "qfluentwidgets",
    "qfluentwidgets.common",
    "qfluentwidgets.components",
    "qfluentwidgets.components.date_time",
    "qfluentwidgets.components.dialog_box",
    "qfluentwidgets.components.layout",
    "qfluentwidgets.components.material",
    "qfluentwidgets.components.navigation",
    "qfluentwidgets.components.settings",
    "qfluentwidgets.components.widgets",
    "qfluentwidgets.multimedia",
    "qfluentwidgets.window",
)

EXTRA_EXPORTS: dict[str, dict[str, str]] = {
    "qfluentwidgets": {
        "load": "qfluentwidgets.common.runtime",
        "unload": "qfluentwidgets.common.runtime",
    },
    "qfluentwidgets.common": {
        "load": "qfluentwidgets.common.runtime",
        "unload": "qfluentwidgets.common.runtime",
    },
}

FORBIDDEN_GLOBAL_ROOTS = frozenset({
    "*",
    "QWidget",
    "QLabel",
    "QPushButton",
    "QToolButton",
    "QDialog",
    "QFrame",
    "QScrollArea",
    "QSlider",
    "QHeaderView",
    "QTableCornerButton",
    "QTableView",
    "QTreeView",
    "QGraphicsView",
    "#view",
    "#titleLabel",
    "#contentLabel",
    "#centerWidget",
    "#buttonGroup",
    "#scrollWidget",
    "#cancelButton",
})

FORBIDDEN_WIDGET_ROOTS = frozenset({
    "QLabel",
    "QPushButton",
})

EXCLUDED_STAR_NAMES = frozenset({"ALERT", "darkdetect"})


def loadSource(relPath: str, sourceRef: str | None) -> str:
    if sourceRef:
        return subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "show", f"{sourceRef}:{relPath}"],
            text=True,
            encoding="utf-8",
        )
    return (REPO_ROOT / relPath).read_text(encoding="utf-8")


def hasInitFile(pkgName: str, sourceRef: str | None) -> bool:
    relPath = "/".join((*pkgName.split("."), "__init__.py"))
    if sourceRef:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "cat-file", "-e", f"{sourceRef}:{relPath}"],
            capture_output=True,
        )
        return result.returncode == 0
    return (REPO_ROOT / relPath).is_file()


def parsePublicNames(modName: str, sourceRef: str | None) -> list[str]:
    relPath = "/".join(modName.split(".")) + ".py"
    tree = ast.parse(loadSource(relPath, sourceRef))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and not node.target.id.startswith("_"):
                names.add(node.target.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                if not bound.startswith("_"):
                    names.add(bound)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    bound = alias.asname or alias.name
                    if not bound.startswith("_"):
                        names.add(bound)
    return sorted(names - EXCLUDED_STAR_NAMES)


def parseExports(pkgName: str, sourceRef: str | None) -> dict[str, str]:
    relPath = "/".join((*pkgName.split("."), "__init__.py"))
    tree = ast.parse(loadSource(relPath, sourceRef))
    exports: dict[str, str] = {}
    for node in tree.body:
        if not (isinstance(node, ast.ImportFrom) and node.level == 1 and node.module):
            continue
        target = f"{pkgName}.{node.module}"
        for alias in node.names:
            if alias.name == "*":
                if hasInitFile(target, sourceRef):
                    exports.update(parseExports(target, sourceRef))
                else:
                    for name in parsePublicNames(target, sourceRef):
                        exports[name] = target
            else:
                if target == "qfluentwidgets._rc" and alias.name == "resource":
                    continue
                localName = alias.asname or alias.name
                if hasInitFile(target, sourceRef):
                    nested = parseExports(target, sourceRef)
                    exports[localName] = nested.get(alias.name, target)
                else:
                    exports[localName] = target
    return dict(sorted(exports.items()))


def buildExportTable(sourceRef: str | None) -> dict[str, dict[str, str]]:
    table: dict[str, dict[str, str]] = {}
    for pkg in PACKAGES:
        merged = parseExports(pkg, sourceRef)
        merged.update(EXTRA_EXPORTS.get(pkg, {}))
        table[pkg] = dict(sorted(merged.items()))
    return table


def buildSubpackages() -> dict[str, tuple[str, ...]]:
    grouped: dict[str, set[str]] = {"qfluentwidgets": {"_rc"}}
    for pkg in PACKAGES:
        if "." not in pkg:
            continue
        parent, child = pkg.rsplit(".", 1)
        grouped.setdefault(parent, set()).add(child)
    return {k: tuple(sorted(v)) for k, v in sorted(grouped.items())}


def buildSymbolsSource(table: dict[str, dict[str, str]]) -> str:
    formattedExports = pprint.pformat(table, width=100, sort_dicts=True)
    formattedSubs = pprint.pformat(buildSubpackages(), width=100, sort_dicts=True)
    return (
        "# coding:utf-8\n"
        "# Auto-generated by tools/build_fork.py. Do not edit manually.\n"
        "from __future__ import annotations\n\n"
        "import importlib\n\n"
        f"PACKAGE_EXPORTS: dict[str, dict[str, str]] = {formattedExports}\n\n"
        f"PACKAGE_SUBPACKAGES: dict[str, tuple[str, ...]] = {formattedSubs}\n\n\n"
        "def loadExport(packageName: str, packageGlobals: dict[str, object], name: str) -> object:\n"
        "    exports = PACKAGE_EXPORTS.get(packageName)\n"
        "    if exports is not None and name in exports:\n"
        "        module = importlib.import_module(exports[name])\n"
        "        value = getattr(module, name)\n"
        "        packageGlobals[name] = value\n"
        "        return value\n"
        "    subpackages = PACKAGE_SUBPACKAGES.get(packageName, ())\n"
        "    if name in subpackages:\n"
        "        value = importlib.import_module(f'{packageName}.{name}')\n"
        "        packageGlobals[name] = value\n"
        "        return value\n"
        "    raise AttributeError(f'module {packageName!r} has no attribute {name!r}')\n\n\n"
        "def listExports(packageName: str) -> list[str]:\n"
        "    return sorted(PACKAGE_EXPORTS.get(packageName, ()))\n\n\n"
        "def listDir(packageName: str) -> list[str]:\n"
        "    exports = PACKAGE_EXPORTS.get(packageName, {})\n"
        "    subpackages = PACKAGE_SUBPACKAGES.get(packageName, ())\n"
        "    return sorted(set(exports) | set(subpackages))\n"
    )


def saveSymbols(sourceRef: str | None) -> dict[str, dict[str, str]]:
    table = buildExportTable(sourceRef)
    SYMBOLS_PATH.write_text(buildSymbolsSource(table), encoding="utf-8")
    return table


def parseAppQssNames() -> list[str]:
    tree = ast.parse(STYLE_SHEET_PATH.read_text(encoding="utf-8"))
    enumValues: dict[str, str] = {}
    appMembers: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "FluentStyleSheet":
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                ):
                    enumValues[stmt.targets[0].id] = stmt.value.value
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "APP_SHEETS"
            and isinstance(node.value, ast.Call)
            and node.value.args
            and isinstance(node.value.args[0], ast.Set)
        ):
            for elt in node.value.args[0].elts:
                if isinstance(elt, ast.Attribute):
                    appMembers.append(elt.attr)
    return sorted(enumValues[m] for m in appMembers)


def probeUnsafeAppSelectors(qssNames: list[str] | None = None) -> list[str]:
    names = parseAppQssNames() if qssNames is None else qssNames
    selectorBlockRe = re.compile(r"^([^{}]+)\{", re.M)
    errors: list[str] = []
    for theme in ("light", "dark"):
        for name in names:
            raw = (PKG_ROOT / "_rc" / "qss" / theme / f"{name}.qss").read_text(encoding="utf-8")
            stripped = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)
            for block in selectorBlockRe.findall(stripped):
                for sel in block.split(","):
                    sel = sel.strip()
                    if not sel:
                        continue
                    root = re.split(r"[\s:>+\[\.]", sel)[0]
                    if root in FORBIDDEN_GLOBAL_ROOTS:
                        errors.append(f"{theme}/{name}.qss: {sel!r} (root={root!r})")
    return errors


def probeUnsafeWidgetSelectors(appQssNames: list[str] | None = None) -> list[str]:
    appSet = set(parseAppQssNames() if appQssNames is None else appQssNames)
    selectorBlockRe = re.compile(r"^([^{}]+)\{", re.M)
    errors: list[str] = []
    for theme in ("light", "dark"):
        qssDir = PKG_ROOT / "_rc" / "qss" / theme
        for path in sorted(qssDir.glob("*.qss")):
            if path.stem in appSet:
                continue
            stripped = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
            for block in selectorBlockRe.findall(stripped):
                for sel in block.split(","):
                    sel = sel.strip()
                    if not sel:
                        continue
                    root = re.split(r"[\s:>+\[\.]", sel)[0]
                    if root in FORBIDDEN_WIDGET_ROOTS:
                        errors.append(f"{theme}/{path.name}: {sel!r} (use .{root})")
    return errors


def probeLazyImports(table: dict[str, dict[str, str]]) -> list[str]:
    errors: list[str] = []
    for path in sorted(PKG_ROOT.rglob("*.py")):
        if path.name in ("__init__.py", "_symbols.py"):
            continue
        modParts = path.relative_to(REPO_ROOT).with_suffix("").parts
        pkgParts = modParts[:-1]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.level > 0:
                base = pkgParts[: len(pkgParts) - node.level + 1]
                target = ".".join((*base, node.module) if node.module else base)
            else:
                target = node.module or ""
            if target not in table:
                continue
            for alias in node.names:
                if alias.name in table[target]:
                    rel = path.relative_to(REPO_ROOT).as_posix()
                    errors.append(f"{rel}:{node.lineno}: {target}.{alias.name} -> {table[target][alias.name]}")
    return errors


def findRcc() -> str:
    exeDir = Path(sys.executable).parent
    for name in ("pyside6-rcc.exe", "pyside6-rcc"):
        candidate = exeDir / name
        if candidate.is_file():
            return str(candidate)
    return shutil.which("pyside6-rcc") or "pyside6-rcc"


def buildRcc(force: bool = False) -> None:
    if not force and RCC_PATH.is_file() and RCC_PATH.stat().st_mtime >= QRC_PATH.stat().st_mtime:
        return
    subprocess.run([findRcc(), "--binary", str(QRC_PATH), "-o", str(RCC_PATH)], check=True)


def main() -> int:
    sourceRef = None if "--working-tree" in sys.argv else "upstream/PySide6"
    table = saveSymbols(sourceRef)
    buildRcc(force="--force-rcc" in sys.argv)
    appQssNames = parseAppQssNames()
    selectorErrors = probeUnsafeAppSelectors(appQssNames)
    if selectorErrors:
        raise AssertionError("Unsafe selectors in app QSS:\n" + "\n".join(selectorErrors))
    widgetSelectorErrors = probeUnsafeWidgetSelectors(appQssNames)
    if widgetSelectorErrors:
        raise AssertionError("Broad base-class selectors in widget QSS:\n" + "\n".join(widgetSelectorErrors))
    lazyErrors = probeLazyImports(table)
    if lazyErrors:
        raise AssertionError("Internal imports through lazy __init__.py:\n" + "\n".join(lazyErrors))
    print(f"Saved {SYMBOLS_PATH.relative_to(REPO_ROOT)} ({len(table)} packages, {len(table['qfluentwidgets'])} top-level exports)")
    print(f"Built {RCC_PATH.relative_to(REPO_ROOT)} ({RCC_PATH.stat().st_size} bytes)")
    print(f"Verified {len(appQssNames)} app QSS sheets (light + dark): 0 unsafe selectors, 0 lazy package imports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
