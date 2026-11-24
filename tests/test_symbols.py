from __future__ import annotations

import importlib
import json
import subprocess
import sys

import pytest

from qfluentwidgets._symbols import PACKAGE_EXPORTS

from conftest import REPO_ROOT, runPython

sys.path.insert(0, str(REPO_ROOT / "tools"))
import build_fork  # noqa: E402


def test_import_config_skips_widgets_and_qt_extras():
    proc = runPython(
        """
import json, sys
from qfluentwidgets import qconfig, Theme, ConfigItem
qfwMods = sorted(m for m in sys.modules if m.startswith("qfluentwidgets"))
qtMods = sorted(m for m in sys.modules if m.startswith("PySide6.Qt"))
print(json.dumps({"qfw": qfwMods, "qt": qtMods, "darkdetect": "darkdetect" in sys.modules}))
"""
    )
    assert "QFluentWidgets Pro" not in proc.stdout
    assert "QFluentWidgets Pro" not in proc.stderr
    data = json.loads(proc.stdout.strip())
    assert data["qfw"] == [
        "qfluentwidgets",
        "qfluentwidgets._symbols",
        "qfluentwidgets.common",
        "qfluentwidgets.common.config",
        "qfluentwidgets.common.exception_handler",
    ]
    assert data["darkdetect"] is False
    assert "PySide6.QtXml" not in data["qt"]
    assert "PySide6.QtSvg" not in data["qt"]
    assert "PySide6.QtSvgWidgets" not in data["qt"]
    assert "qfluentwidgets._rc" not in data["qfw"]


def test_import_widget_skips_unrelated_modules():
    proc = runPython(
        """
import json, sys
from qfluentwidgets import CheckBox
qfwMods = sorted(m for m in sys.modules if m.startswith("qfluentwidgets"))
qtMods = sorted(m for m in sys.modules if m.startswith("PySide6.Qt"))
print(json.dumps({"qfw": qfwMods, "qt": qtMods}))
"""
    )
    data = json.loads(proc.stdout.strip())
    assert "qfluentwidgets.components.widgets.check_box" in data["qfw"]
    for skipped in (
        "qfluentwidgets.components.date_time.calendar_picker",
        "qfluentwidgets.components.dialog_box.color_dialog",
        "qfluentwidgets.components.widgets.table_view",
        "qfluentwidgets.multimedia.media_player",
    ):
        assert skipped not in data["qfw"]
    assert "PySide6.QtXml" not in data["qt"]
    assert "PySide6.QtSvg" not in data["qt"]
    assert "PySide6.QtSvgWidgets" not in data["qt"]


def test_access_unknown_symbol_raises():
    proc = runPython(
        """
import qfluentwidgets
try:
    _ = qfluentwidgets.NonExistentWidget123
except AttributeError:
    print("OK")
else:
    raise SystemExit(1)
"""
    )
    assert proc.stdout.strip() == "OK"


def test_access_symbol_caches_in_module():
    proc = runPython(
        """
import qfluentwidgets
first = qfluentwidgets.PushButton
assert "PushButton" in vars(qfluentwidgets)
assert qfluentwidgets.PushButton is first
print("OK")
"""
    )
    assert proc.stdout.strip() == "OK"


def test_resolve_exports_matches_upstream():
    hasUpstream = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--verify", "upstream/PySide6"],
        capture_output=True,
    ).returncode == 0
    if not hasUpstream:
        pytest.skip("missing upstream/PySide6 git ref")

    assert PACKAGE_EXPORTS == build_fork.buildExportTable("upstream/PySide6")
    for pkgName, exports in PACKAGE_EXPORTS.items():
        if pkgName == "qfluentwidgets.multimedia":
            continue
        mod = importlib.import_module(pkgName)
        for symbol in exports:
            assert hasattr(mod, symbol), f"{pkgName}.{symbol} failed to resolve"
