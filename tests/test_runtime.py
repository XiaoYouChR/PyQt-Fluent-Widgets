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


def test_svg_cache_hits_on_resource_and_clears_on_unload(fluentApp, tmp_path):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QPainter, QPixmap
    from qfluentwidgets.common import icon as iconMod
    from qfluentwidgets.components.widgets.info_bar import InfoBarIcon

    iconMod.clearCache()
    pm = QPixmap(24, 24)
    painter = QPainter(pm)
    InfoBarIcon.INFORMATION.render(painter, QRectF(0, 0, 16, 16), indexes=[0], fill="#0078d4")
    InfoBarIcon.INFORMATION.render(painter, QRectF(0, 0, 16, 16), indexes=[0], fill="#0078d4")
    painter.end()
    assert iconMod.svgRenderer.cache_info().hits >= 1
    assert iconMod.svgRenderer.cache_info().currsize == 1

    # Local filesystem SVG is read without caching stale disk content
    localSvg = tmp_path / "sample.svg"
    localSvg.write_text('<svg><path fill="#111111" d="M0 0h1v1z"/></svg>', encoding="utf-8")
    assert "#222222" in writeSvg(str(localSvg), fill="#222222")
    localSvg.write_text('<svg><path id="v2" fill="#111111" d="M0 0h1v1z"/></svg>', encoding="utf-8")
    assert 'id="v2"' in writeSvg(str(localSvg), fill="#333333")

    qfluentwidgets.unload()
    assert iconMod.svgRenderer.cache_info().currsize == 0
