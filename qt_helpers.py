#!/usr/bin/env python3
"""
WhisperRocket - Small Qt behaviour fixes shared between windows
"""
from PySide6.QtCore import QObject, QEvent
from PySide6.QtWidgets import QApplication, QComboBox, QAbstractSpinBox, QScrollArea


class NoWheelFilter(QObject):
    """
    Stops the mouse wheel from changing a dropdown or a number field.

    Qt lets a combo box and a spin box consume wheel events, so scrolling a
    settings page with the pointer resting over one of them silently changes the
    value - you set the model to Sonnet, scroll past it looking for something
    else, and it is on Haiku. A setting should change when you open the menu and
    pick something, not while you are navigating the page.

    The event is blocked and handed to the enclosing scroll area instead, so the
    page still scrolls where the user pointed. Wheel events inside an open
    dropdown are unaffected: the popup is a separate widget.
    """

    @staticmethod
    def _scroll_area(widget):
        parent = widget.parent()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                return parent
            parent = parent.parent()
        return None

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            area = self._scroll_area(obj)
            if area is not None:
                QApplication.sendEvent(area.viewport(), event)
            return True
        return False


def block_wheel_changes(root):
    """
    Apply NoWheelFilter to every dropdown and number field under root.

    Call it once after the widgets exist; anything added later to the same window
    needs another call. The filter is parented to root so it lives as long as the
    window does.
    """
    if not hasattr(root, "_no_wheel_filter"):
        root._no_wheel_filter = NoWheelFilter(root)
    for widget in root.findChildren(QComboBox) + root.findChildren(QAbstractSpinBox):
        widget.installEventFilter(root._no_wheel_filter)
