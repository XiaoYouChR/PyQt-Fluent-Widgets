from __future__ import annotations

import weakref

from PySide6.QtCore import QParallelAnimationGroup, QPoint, QPointF, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import QApplication, QWidget

import qfluentwidgets
from qfluentwidgets import (
    CardWidget,
    CheckableMenu,
    FluentIcon,
    IndeterminateProgressBar,
    IndeterminateProgressRing,
    InfoBar,
    InfoBarManager,
    InfoBarPosition,
    MSFluentWindow,
    MaskDialogBase,
    MenuIndicatorType,
    PopUpAniStackedWidget,
    PushButton,
    StateToolTip,
    Theme,
    ToolButton,
    ToolTip,
    ToolTipFilter,
    qrouter,
    setTheme,
)

from conftest import waitReclaim


def test_switch_theme_hidden_card_skips_animation(qtbot, fluentApp):
    cards = [CardWidget() for _ in range(20)]
    for card in cards:
        qtbot.addWidget(card)
        assert card.findChildren(QPropertyAnimation) == []

    lightColor = cards[0].backgroundColor
    setTheme(Theme.DARK)
    for card in cards:
        assert card.findChildren(QPropertyAnimation) == []

    cards[0].show()
    qtbot.waitExposed(cards[0])
    assert cards[0].backgroundColor != lightColor


def test_hide_progress_stops_animation(qtbot, fluentApp):
    bar = IndeterminateProgressBar(start=True)
    ring = IndeterminateProgressRing(start=True)
    qtbot.addWidget(bar)
    qtbot.addWidget(ring)

    assert bar.isStarted() is True
    assert ring.isStarted() is True
    assert bar.aniGroup.state() != QParallelAnimationGroup.Running
    assert ring.aniGroup.state() != QParallelAnimationGroup.Running

    bar.show()
    ring.show()
    qtbot.waitExposed(bar)
    qtbot.waitExposed(ring)
    assert bar.aniGroup.state() == QParallelAnimationGroup.Running
    assert ring.aniGroup.state() == QParallelAnimationGroup.Running

    bar.hide()
    ring.hide()
    assert bar.aniGroup.state() != QParallelAnimationGroup.Running
    assert ring.aniGroup.state() != QParallelAnimationGroup.Running


def test_delete_button_reclaims_tooltip(qtbot, fluentApp):
    window = QWidget()
    qtbot.addWidget(window)
    window.resize(200, 120)
    button = ToolButton(FluentIcon.PLAY, window)
    button.setToolTip("Play task")
    tipFilter = ToolTipFilter(button, showDelay=10)
    button.installEventFilter(tipFilter)

    assert tipFilter.findChildren(QTimer) == []

    window.show()
    qtbot.waitExposed(window)

    enterEvent = QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5))
    QApplication.sendEvent(button, enterEvent)
    assert window.findChildren(ToolTip) == []

    qtbot.waitUntil(lambda: len(window.findChildren(ToolTip)) == 1, timeout=1000)
    tipRef = weakref.ref(window.findChildren(ToolTip)[0])
    tipFilter.hideToolTip()
    waitReclaim(qtbot)
    assert tipRef() is None
    assert window.findChildren(ToolTip) == []

    QApplication.sendEvent(button, enterEvent)
    qtbot.waitUntil(lambda: len(window.findChildren(ToolTip)) == 1, timeout=1000)
    tipRef = weakref.ref(window.findChildren(ToolTip)[0])

    button.deleteLater()
    del button, tipFilter

    waitReclaim(qtbot)
    assert tipRef() is None
    assert window.findChildren(ToolTip) == []


def test_close_and_unload_clear_info_bar(qtbot, fluentApp):
    window = QWidget()
    qtbot.addWidget(window)
    window.resize(400, 300)
    window.show()
    qtbot.waitExposed(window)

    bar = InfoBar.success("Done", "Downloaded", duration=-1, position=InfoBarPosition.TOP_RIGHT, parent=window)
    mgr = InfoBarManager.make(InfoBarPosition.TOP_RIGHT)
    assert window in mgr.infoBars
    assert bar in mgr.infoBars[window]

    bar.close()
    waitReclaim(qtbot, rounds=1)
    assert window not in mgr.infoBars
    assert window not in mgr.aniGroups

    InfoBar.info("Keep", "Msg", duration=-1, position=InfoBarPosition.TOP_RIGHT, parent=window)
    assert window in mgr.infoBars
    qfluentwidgets.unload()
    assert window not in mgr.infoBars
    assert window not in mgr.aniGroups


def test_hide_mask_dialog_stops_tracking_resize(qtbot, fluentApp):
    window = QWidget()
    qtbot.addWidget(window)
    window.resize(400, 300)
    window.show()
    qtbot.waitExposed(window)

    dialog = MaskDialogBase(window)
    assert dialog.size() == window.size()

    dialog.show()
    qtbot.waitExposed(dialog)
    window.resize(520, 360)
    qtbot.waitUntil(lambda: dialog.size() == window.size())

    dialog.hide()
    hiddenSize = dialog.size()
    window.resize(600, 420)
    qtbot.wait(20)
    assert dialog.size() == hiddenSize


def test_mask_dialog_shadow_uses_cached_sibling_and_reclaims(qtbot, fluentApp):
    window = QWidget()
    qtbot.addWidget(window)
    window.resize(400, 300)
    window.show()
    qtbot.waitExposed(window)

    dialog = MaskDialogBase(window)
    dialog.widget.setFixedSize(200, 120)
    dialog.widget.setStyleSheet("#centerWidget { background: white; border-radius: 10px; }")
    dialog.show()
    qtbot.waitExposed(dialog)

    shadow = dialog._shadowLayer
    assert dialog.widget.graphicsEffect() is None
    assert shadow.isVisible() is True
    assert not shadow._pixmap.isNull()

    pixmapKey = shadow._pixmap.cacheKey()
    oldPos = shadow.pos()
    dialog.widget.move(dialog.widget.pos().x() + 12, dialog.widget.pos().y() + 8)
    assert shadow._pixmap.cacheKey() == pixmapKey
    assert shadow.pos() == oldPos + QPoint(12, 8)

    dialogRef = weakref.ref(dialog)
    shadowRef = weakref.ref(shadow)
    dialog.deleteLater()
    del dialog, shadow

    waitReclaim(qtbot)
    assert dialogRef() is None
    assert shadowRef() is None


def test_hide_state_tool_tip_stops_timer(qtbot, fluentApp):
    window = QWidget()
    qtbot.addWidget(window)
    window.resize(400, 200)
    tip = StateToolTip("Working", "Please wait", window)
    assert tip.rotateTimer.isActive() is False
    assert tip.animation.parent() is tip

    window.show()
    tip.show()
    qtbot.waitExposed(tip)
    assert tip.rotateTimer.isActive() is True

    tip.hide()
    assert tip.rotateTimer.isActive() is False


def test_switch_stacked_restores_layout_and_removes_widget(qtbot, fluentApp):
    stacked = PopUpAniStackedWidget()
    qtbot.addWidget(stacked)
    page1 = QWidget()
    page2 = QWidget()
    stacked.addWidget(page1)
    stacked.addWidget(page2)
    assert len(page1.findChildren(QPropertyAnimation)) == 1
    assert len(page2.findChildren(QPropertyAnimation)) == 1

    stacked.resize(300, 200)
    stacked.show()
    qtbot.waitExposed(stacked)

    stacked.setCurrentIndex(1, duration=20)
    qtbot.waitUntil(lambda: stacked.layout().isEnabled(), timeout=500)
    assert stacked.currentWidget() is page2

    stacked.removeWidget(page1)
    assert stacked.count() == 1


def test_delete_checkable_menu_reclaims_delegate(qtbot, fluentApp):
    menu = CheckableMenu(indicatorType=MenuIndicatorType.RADIO)
    delegateRef = weakref.ref(menu.view.itemDelegate())
    assert menu.view.itemDelegate().parent() is menu.view
    menu.deleteLater()
    del menu

    waitReclaim(qtbot)
    assert delegateRef() is None


def test_close_fluent_window_reclaims_window_and_router(qtbot, fluentApp):
    window = MSFluentWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    page = QWidget()
    page.setObjectName("tasksPage")
    button = PushButton("Start", page)
    button.setToolTip("Start task")
    button.installEventFilter(ToolTipFilter(button))
    window.addSubInterface(page, FluentIcon.HOME, "Tasks")
    window.show()
    qtbot.waitExposed(window)

    ref = weakref.ref(window)
    window.close()
    del window, page, button

    waitReclaim(qtbot, waitMs=80)
    assert ref() is None
    assert qrouter.history == []
    assert len(qrouter.stackHistories) == 0
