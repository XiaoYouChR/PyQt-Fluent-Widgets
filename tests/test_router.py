from __future__ import annotations

import weakref

from PySide6.QtWidgets import QStackedWidget, QWidget

from qfluentwidgets import qrouter

from conftest import waitReclaim


def test_unregister_clears_stacked_history(fluentApp):
    stacked = QStackedWidget()
    page1 = QWidget(stacked)
    page1.setObjectName("p1")
    page2 = QWidget(stacked)
    page2.setObjectName("p2")
    stacked.addWidget(page1)
    stacked.addWidget(page2)

    qrouter.setDefaultRouteKey(stacked, "p1")
    qrouter.push(stacked, "p2")
    assert len(qrouter.history) == 1
    assert stacked in qrouter.stackHistories

    qrouter.unregister(stacked)
    assert qrouter.history == []
    assert stacked not in qrouter.stackHistories


def test_delete_stacked_prunes_history(qtbot, fluentApp):
    stacked = QStackedWidget()
    page1 = QWidget(stacked)
    page1.setObjectName("p1")
    page2 = QWidget(stacked)
    page2.setObjectName("p2")
    stacked.addWidget(page1)
    stacked.addWidget(page2)

    qrouter.setDefaultRouteKey(stacked, "p1")
    qrouter.push(stacked, "p2")
    ref = weakref.ref(stacked)
    stacked.deleteLater()
    del stacked, page1, page2

    waitReclaim(qtbot)
    assert ref() is None
    assert qrouter.history == []
    assert len(qrouter.stackHistories) == 0
