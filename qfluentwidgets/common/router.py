# coding:utf-8
from typing import List
from itertools import groupby
import weakref

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget, QStackedWidget
from shiboken6 import isValid


class RouteItem:
    """ Route item """

    def __init__(self, stacked: QStackedWidget, routeKey: str):
        self._stackedRef = weakref.ref(stacked)
        self.routeKey = routeKey

    @property
    def stacked(self) -> QStackedWidget | None:
        stacked = self._stackedRef()
        if stacked is not None and isValid(stacked):
            return stacked
        return None

    def __eq__(self, other):
        if other is None:
            return False

        return other.stacked is self.stacked and self.routeKey == other.routeKey


class StackedHistory:
    """ Stacked history """

    def __init__(self, stacked: QStackedWidget):
        self._stackedRef = weakref.ref(stacked)
        self.defaultRouteKey = None  # type: str
        self.history = [self.defaultRouteKey]   # type: List[str]

    @property
    def stacked(self) -> QStackedWidget | None:
        stacked = self._stackedRef()
        if stacked is not None and isValid(stacked):
            return stacked
        return None

    def __len__(self):
        return len(self.history)

    def isEmpty(self):
        return len(self) <= 1

    def push(self, routeKey: str):
        if self.history[-1] == routeKey:
            return False

        self.history.append(routeKey)
        return True

    def pop(self):
        if self.isEmpty():
            return

        self.history.pop()
        self.goToTop()

    def remove(self, routeKey: str):
        if routeKey not in self.history:
            return

        self.history[1:] = [i for i in self.history[1:] if i != routeKey]
        self.history = [k for k, g in groupby(self.history)]
        self.goToTop()

    def top(self):
        return self.history[-1]

    def setDefaultRouteKey(self, routeKey: str):
        self.defaultRouteKey = routeKey
        self.history[0] = routeKey

    def goToTop(self):
        stacked = self.stacked
        if stacked is None:
            return
        w = stacked.findChild(QWidget, self.top())
        if w:
            stacked.setCurrentWidget(w)


class Router(QObject):
    """ Router """

    emptyChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.history = []   # type: List[RouteItem]
        self.stackHistories = weakref.WeakKeyDictionary()

    def _register(self, stacked: QStackedWidget) -> StackedHistory:
        history = self.stackHistories.get(stacked)
        if history is None:
            history = StackedHistory(stacked)
            self.stackHistories[stacked] = history
            stacked.destroyed.connect(self._pruneDead)
        return history

    def _pruneDead(self, _obj=None) -> None:
        before = len(self.history)
        self.history = [i for i in self.history if i.stacked is not None]
        if len(self.history) != before:
            self.emptyChanged.emit(not bool(self.history))

    def setDefaultRouteKey(self, stacked: QStackedWidget, routeKey: str):
        """ set the default route key of stacked widget """
        self._register(stacked).setDefaultRouteKey(routeKey)

    def push(self, stacked: QStackedWidget, routeKey: str):
        """ push history

        Parameters
        ----------
        stacked: QStackedWidget
            stacked widget

        routeKey: str
            route key of sub insterface, it should be the object name of sub interface
        """
        item = RouteItem(stacked, routeKey)
        history = self._register(stacked)

        # don't add duplicated history
        success = history.push(routeKey)
        if success:
            self.history.append(item)

        self.emptyChanged.emit(not bool(self.history))

    def pop(self):
        """ pop history """
        self._pruneDead()
        if not self.history:
            return

        item = self.history.pop()
        self.emptyChanged.emit(not bool(self.history))
        stacked = item.stacked
        if stacked is not None:
            history = self.stackHistories.get(stacked)
            if history is not None:
                history.pop()

    def remove(self, routeKey: str):
        """ remove history """
        self._pruneDead()
        self.history = [i for i in self.history if i.routeKey != routeKey]
        self.history = [list(g)[0] for k, g in groupby(self.history, lambda i: i.routeKey)]
        self.emptyChanged.emit(not bool(self.history))

        for stacked, history in list(self.stackHistories.items()):
            if not isValid(stacked):
                continue
            w = stacked.findChild(QWidget, routeKey)
            if w:
                return history.remove(routeKey)

    def unregister(self, stacked: QStackedWidget) -> None:
        """ remove all route history bound to a stacked widget """
        self.history = [i for i in self.history if i.stacked is not None and i.stacked is not stacked]
        self.stackHistories.pop(stacked, None)
        self.emptyChanged.emit(not bool(self.history))

    def clear(self) -> None:
        """ clear all route history """
        wasNonEmpty = bool(self.history)
        self.history.clear()
        self.stackHistories.clear()
        if wasNonEmpty:
            self.emptyChanged.emit(True)


qrouter = Router()
