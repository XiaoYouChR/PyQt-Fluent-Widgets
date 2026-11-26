from __future__ import annotations

import sys
import weakref

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

import qfluentwidgets
from qfluentwidgets import (
    BodyLabel,
    CalendarPicker,
    CardWidget,
    CheckBox,
    ComboBox,
    FluentIcon,
    FluentStyleSheet,
    LineEdit,
    PlainTextEdit,
    PrimaryPushButton,
    PrimarySplitPushButton,
    PushButton,
    ScrollArea,
    SettingCard,
    SwitchButton,
    TextBrowser,
    TextEdit,
    Theme,
    TimePicker,
    ToolButton,
    qconfig,
    setStyleSheet,
    setTheme,
    setThemeColor,
)
from qfluentwidgets.common.style_sheet import (
    CustomStyleSheet,
    MANAGED_BEGIN,
    MANAGED_END,
    addStyleSheet,
    updateStyleSheet,
)

from conftest import REPO_ROOT, waitReclaim

sys.path.insert(0, str(REPO_ROOT / "tools"))
import build_fork  # noqa: E402


def test_probe_app_qss_has_no_generic_selectors():
    assert build_fork.probeUnsafeAppSelectors() == []


def test_probe_widget_qss_has_no_broad_base_selectors():
    assert build_fork.probeUnsafeWidgetSelectors() == []


def test_combo_box_and_primary_button_in_setting_card_keep_app_style(qtbot, fluentApp):
    setTheme(Theme.DARK)
    setThemeColor("#0078d4", save=False)

    standalone = ComboBox()
    standalone.addItem("Option A")
    qtbot.addWidget(standalone)

    card = SettingCard(FluentIcon.SETTING, "Choice", "Desc")
    nested = ComboBox(card)
    nested.addItem("Option A")
    primary = PrimaryPushButton("Apply", card)
    primary.setFixedSize(120, 32)
    card.hBoxLayout.addWidget(nested)
    card.hBoxLayout.addWidget(primary)
    qtbot.addWidget(card)

    standalone.show()
    card.show()
    qtbot.waitExposed(card)

    assert nested.sizeHint().width() == standalone.sizeHint().width()

    image = QImage(primary.size(), QImage.Format_ARGB32)
    image.fill(QColor(0, 0, 0))
    primary.render(image)
    pixel = image.pixelColor(10, 10)
    assert pixel.blue() > 140


def test_update_before_load_leaves_app_empty(fluentApp):
    qfluentwidgets.unload()
    assert fluentApp.styleSheet() == ""
    setThemeColor("#ff5500", save=False)
    updateStyleSheet()
    assert fluentApp.styleSheet() == ""


def test_load_applies_app_qss_once(qtbot, fluentApp, monkeypatch):
    qfluentwidgets.unload()
    writes: list[str] = []
    originalSet = fluentApp.setStyleSheet

    def recordSetStyleSheet(qss: str) -> None:
        writes.append(qss)
        originalSet(qss)

    monkeypatch.setattr(fluentApp, "setStyleSheet", recordSetStyleSheet)
    qfluentwidgets.load(fluentApp)

    widgets = []
    for _ in range(25):
        batch = (
            PushButton("Start"),
            BodyLabel("Speed"),
            LineEdit(),
            CheckBox("Auto"),
            ComboBox(),
            CardWidget(),
        )
        for widget in batch:
            qtbot.addWidget(widget)
        widgets.extend(batch)

    assert len(writes) == 1
    assert MANAGED_BEGIN in fluentApp.styleSheet()
    assert MANAGED_END in fluentApp.styleSheet()
    assert all(widget.styleSheet() == "" for widget in widgets)


def test_load_and_unload_preserve_host_qss(qtbot, fluentApp):
    qfluentwidgets.unload()
    hostRule = "QStatusBar { min-height: 22px; }"
    fluentApp.setStyleSheet(hostRule)

    qfluentwidgets.load(fluentApp)
    qtbot.addWidget(PushButton("Host"))
    assert hostRule in fluentApp.styleSheet()

    setTheme(Theme.DARK)
    assert hostRule in fluentApp.styleSheet()
    assert "rgba(255, 255, 255" in fluentApp.styleSheet()

    setThemeColor("#cc3366", save=False)
    assert hostRule in fluentApp.styleSheet()

    qfluentwidgets.unload()
    assert fluentApp.styleSheet() == hostRule


def test_update_after_theme_change_refreshes_app_qss(qtbot, fluentApp):
    qtbot.addWidget(PushButton("Switch"))
    lightQss = fluentApp.styleSheet()

    qconfig.theme = Theme.DARK
    updateStyleSheet()
    assert fluentApp.styleSheet() != lightQss

    qconfig.theme = Theme.LIGHT
    updateStyleSheet()
    assert fluentApp.styleSheet() == lightQss


def test_set_text_color_tracks_theme(qtbot, fluentApp):
    defaultLabel = BodyLabel("Normal")
    coloredLabel = BodyLabel("Error")
    qtbot.addWidget(defaultLabel)
    qtbot.addWidget(coloredLabel)

    assert defaultLabel.styleSheet() == ""

    coloredLabel.setTextColor("#112233", "#ddeeff")
    assert "#ff112233" in coloredLabel.styleSheet().lower()

    setTheme(Theme.DARK)
    assert "#ffddeeff" in coloredLabel.styleSheet().lower()

    setTheme(Theme.LIGHT)
    assert "#ff112233" in coloredLabel.styleSheet().lower()


def test_add_custom_style_sheet_tracks_theme(qtbot, fluentApp):
    widget = QWidget()
    qtbot.addWidget(widget)
    custom = CustomStyleSheet(widget)
    custom.setCustomStyleSheet(
        "QWidget { color: rgb(1, 2, 3); }",
        "QWidget { color: rgb(4, 5, 6); }",
    )
    addStyleSheet(widget, custom)
    assert "rgb(1, 2, 3)" in widget.styleSheet()

    setTheme(Theme.DARK)
    assert "rgb(4, 5, 6)" in widget.styleSheet()


def test_set_fixed_theme_overrides_app_qss(qtbot, fluentApp):
    button = PushButton("FixedDark")
    qtbot.addWidget(button)
    setStyleSheet(button, FluentStyleSheet.BUTTON, theme=Theme.DARK)
    assert "PushButton" in button.styleSheet()

    setStyleSheet(button, FluentStyleSheet.BUTTON, theme=Theme.AUTO)
    assert button.styleSheet() == ""


def test_update_lazy_defers_hidden_card_until_show(qtbot, fluentApp):
    card = SettingCard(FluentIcon.SETTING, "Lazy", "Desc")
    qtbot.addWidget(card)
    lightQss = card.styleSheet()
    assert lightQss != ""

    qconfig.theme = Theme.DARK
    updateStyleSheet(lazy=True)
    assert card.styleSheet() == lightQss

    card.show()
    qtbot.waitExposed(card)
    qtbot.waitUntil(lambda: card.styleSheet() != lightQss)


def test_enable_transparent_background_preserves_button_fill(qtbot, fluentApp):
    setTheme(Theme.DARK)
    setThemeColor("#0078d4", save=False)

    scroll = ScrollArea()
    container = QWidget()
    layout = QVBoxLayout(container)
    primary = PrimaryPushButton("Confirm", container)
    primary.setFixedSize(140, 36)
    layout.addWidget(primary)
    scroll.setWidget(container)
    scroll.enableTransparentBackground()
    qtbot.addWidget(scroll)

    scroll.resize(240, 120)
    scroll.show()
    qtbot.waitExposed(scroll)

    image = QImage(primary.size(), QImage.Format_ARGB32)
    image.fill(QColor(12, 34, 56))
    primary.render(image)
    pixel = image.pixelColor(10, 10)
    assert (pixel.red(), pixel.green(), pixel.blue()) != (12, 34, 56)
    assert pixel.blue() > 140


def test_update_dynamic_style_refreshes_button_icon_property(qtbot, fluentApp):
    button = PushButton("Action")
    qtbot.addWidget(button)
    button.show()
    qtbot.waitExposed(button)
    widthWithoutIcon = button.sizeHint().width()

    assert button.property("hasIcon") is False
    button.setIcon(FluentIcon.PLAY)
    assert button.property("hasIcon") is True
    assert button.sizeHint().width() > widthWithoutIcon

    button.setIcon(None)
    assert button.property("hasIcon") is False
    assert button.sizeHint().width() == widthWithoutIcon


def test_app_qss_widgets_keep_font_across_show_and_theme_change(qtbot, fluentApp):
    container = QWidget()
    widgets = (
        PushButton(container),
        PushButton("Cancel", container),
        PrimaryPushButton("Confirm", container),
        TextEdit(container),
        PlainTextEdit(container),
        TextBrowser(container),
    )
    qtbot.addWidget(container)
    container.show()
    qtbot.waitExposed(container)

    for widget in widgets:
        assert widget.testAttribute(Qt.WidgetAttribute.WA_SetFont)
        assert widget.font().pixelSize() == 14

    widgets[1].setIcon(FluentIcon.PLAY)
    setTheme(Theme.DARK)
    setTheme(Theme.LIGHT)

    for widget in widgets:
        assert widget.testAttribute(Qt.WidgetAttribute.WA_SetFont)
        assert widget.font().pixelSize() == 14


def test_delete_styled_widgets_reclaims_memory(qtbot, fluentApp):
    refs = []
    for _ in range(30):
        card = CardWidget()
        for _ in range(4):
            ToolButton(FluentIcon.PLAY, card)
        BodyLabel("Task", card)
        accentLabel = BodyLabel("Status", card)
        accentLabel.setTextColor("#112233", "#ddeeff")
        SettingCard(FluentIcon.SETTING, "Setting", "Desc", card)
        SwitchButton(card)
        refs.append(weakref.ref(card))
        refs.append(weakref.ref(accentLabel))
        card.deleteLater()
        del card, accentLabel

    waitReclaim(qtbot)
    assert [r for r in refs if r() is not None] == []


def test_apply_app_qss_aligns_push_button_layout_geometry(qtbot, fluentApp):
    host = QWidget()
    hostLayout = QHBoxLayout(host)
    splitButton = PrimarySplitPushButton("Download", host)
    hostLayout.addWidget(splitButton)
    qtbot.addWidget(host)
    host.show()
    qtbot.waitExposed(host)

    assert splitButton.dropButton.geometry().top() == splitButton.button.geometry().top() == 0
    assert splitButton.dropButton.geometry().height() == splitButton.button.geometry().height()

    for factory in (
        lambda parent: PushButton("Action", parent),
        lambda parent: ComboBox(parent),
        lambda parent: CalendarPicker(parent),
        lambda parent: TimePicker(parent),
    ):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        widget = factory(container)
        layout.addWidget(widget)
        qtbot.addWidget(container)
        container.show()
        qtbot.waitExposed(container)

        assert layout.itemAt(0).geometry() == widget.geometry()
