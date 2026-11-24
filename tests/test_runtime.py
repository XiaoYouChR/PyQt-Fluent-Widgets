from __future__ import annotations

import pytest
from PySide6.QtCore import QFile, QSize
from PySide6.QtSvg import QSvgRenderer

import qfluentwidgets
from qfluentwidgets import FluentIcon
from qfluentwidgets.common.icon import writeSvg

from conftest import runPython


def test_import_leaves_resources_unregistered():
    proc = runPython(
        """
from PySide6.QtCore import QFile
import qfluentwidgets
from qfluentwidgets import qconfig
print(QFile.exists(":/qfluentwidgets/qss/light/button.qss"))
"""
    )
    assert proc.stdout.strip() == "False"


def test_load_and_unload_toggle_resources(qapp):
    qfluentwidgets.unload()
    assert not QFile.exists(":/qfluentwidgets/qss/light/button.qss")

    qfluentwidgets.load(qapp)
    qfluentwidgets.load(qapp)
    assert QFile.exists(":/qfluentwidgets/qss/light/button.qss")
    assert QFile.exists(":/qfluentwidgets/images/icons/Add_black.svg")

    qfluentwidgets.unload()
    assert not QFile.exists(":/qfluentwidgets/qss/light/button.qss")
    qfluentwidgets.unload()


def test_load_invalid_app_raises():
    with pytest.raises(TypeError):
        qfluentwidgets.load("not-an-app")  # type: ignore[arg-type]


def test_set_theme_auto_resolves_without_darkdetect():
    proc = runPython(
        """
import sys
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, qconfig
app = QApplication([])
qconfig.theme = Theme.AUTO
assert qconfig.theme in (Theme.LIGHT, Theme.DARK)
print("OK")
""",
        extraEnv={"QT_QPA_PLATFORM": "offscreen"},
    )
    assert proc.stdout.strip() == "OK"


def test_write_svg_renders_colored_icon(fluentApp):
    svg = writeSvg(FluentIcon.ADD.path(), fill="#ff0000")
    assert "#ff0000" in svg
    assert QSvgRenderer(svg.encode("utf-8")).isValid()
    assert not FluentIcon.ADD.icon(color="#00aa88").pixmap(QSize(16, 16)).isNull()
