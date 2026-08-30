#!/usr/bin/env python3
"""
WhisperRocket - Small Qt behaviour fixes shared between windows
"""
from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtWidgets import (QApplication, QComboBox, QAbstractSpinBox,
                               QScrollArea, QDialog, QVBoxLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QCheckBox,
                               QTextEdit)


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


STATUS_ICONS = {
    "ok": ("✓", "#4CAF50"),
    "warn": ("!", "#FF9800"),
    "fail": ("✗", "#F44336"),
    "na": ("–", "#888888"),
}


def make_copy_row(cmd):
    """Read-only monospace command field with a copy button (same pattern as
    the wizard's conversion-deps dialog)."""
    row = QHBoxLayout()
    field = QLineEdit(cmd)
    field.setReadOnly(True)
    field.setCursorPosition(0)  # long commands: show the beginning, not the tail
    field.setStyleSheet("font-family: monospace; font-size: 12px; padding: 4px; "
                        "background: #2b2b2b; color: #e0e0e0; border: 1px solid #555;")
    row.addWidget(field)
    copy_btn = QPushButton("⧉")
    copy_btn.setFixedWidth(34)
    copy_btn.clicked.connect(
        lambda: (QApplication.clipboard().setText(cmd), copy_btn.setText("✓")))
    row.addWidget(copy_btn)
    return row


def show_health_dialog(results, lang, parent=None, show_suppress=True):
    """Modal dialog listing failed/degraded system checks with copyable fix
    commands. Returns True when the user ticked "don't show again".

    ``results`` is a list of system_check.CheckResult. Only non-"ok" rows are
    rendered; pass a pre-filtered list to control what the user sees.
    """
    from translations import t

    dlg = QDialog(parent)
    dlg.setWindowTitle(t("health_title", lang))
    dlg.setMinimumWidth(520)
    layout = QVBoxLayout(dlg)
    layout.setSpacing(10)

    intro = QLabel(t("health_intro", lang))
    intro.setWordWrap(True)
    layout.addWidget(intro)

    for r in results:
        if r.status == "ok":
            continue
        icon, color = STATUS_ICONS.get(r.status, STATUS_ICONS["warn"])
        label = QLabel(f'<span style="color: {color}; font-weight: bold;">{icon}</span>  '
                       f'{t(r.label_key, lang)}'
                       + (f'  <span style="color: #888;">— {r.detail}</span>'
                          if r.detail else ""))
        label.setWordWrap(True)
        layout.addWidget(label)
        if r.fix_cmd:
            layout.addLayout(make_copy_row(r.fix_cmd))

    suppress_check = None
    if show_suppress:
        suppress_check = QCheckBox(t("health_suppress", lang))
        layout.addWidget(suppress_check)

    ok_btn = QPushButton("OK")
    ok_btn.setDefault(True)
    ok_btn.clicked.connect(dlg.accept)
    btn_row = QHBoxLayout()
    btn_row.addStretch()
    btn_row.addWidget(ok_btn)
    layout.addLayout(btn_row)

    dlg.exec()
    return bool(suppress_check and suppress_check.isChecked())


def show_update_dialog(info, lang, parent=None):
    """New-version dialog: localized cumulative release notes, the user
    decides. Returns (choice, disable_auto) where choice is "update" or
    "later" and disable_auto is True when the user asked to stop automatic
    checks. ``info`` is an update_checker.UpdateInfo."""
    from translations import t

    dlg = QDialog(parent)
    dlg.setWindowTitle(t("update_available_title", lang, version=info.latest))
    dlg.setMinimumWidth(520)
    layout = QVBoxLayout(dlg)
    layout.setSpacing(10)

    title = QLabel(f'<b>{t("update_available_title", lang, version=info.latest)}</b>')
    title.setWordWrap(True)
    layout.addWidget(title)

    notes = QTextEdit()
    notes.setReadOnly(True)
    notes.setPlainText(info.notes_text or "")
    notes.setMinimumHeight(180)
    layout.addWidget(notes)

    disable_check = QCheckBox(t("update_disable_auto", lang))
    layout.addWidget(disable_check)

    btn_row = QHBoxLayout()
    btn_row.addStretch()
    later_btn = QPushButton(t("update_later_btn", lang))
    later_btn.clicked.connect(dlg.reject)
    btn_row.addWidget(later_btn)
    update_btn = QPushButton(t("update_now_btn", lang))
    update_btn.setDefault(True)
    update_btn.setStyleSheet("QPushButton { background-color: #0A84FF; color: white; "
                             "border: none; border-radius: 8px; padding: 8px 18px; "
                             "font-weight: 600; } "
                             "QPushButton:hover { background-color: #0071E3; }")
    update_btn.clicked.connect(dlg.accept)
    btn_row.addWidget(update_btn)
    layout.addLayout(btn_row)

    accepted = dlg.exec() == QDialog.Accepted
    return ("update" if accepted else "later"), disable_check.isChecked()


def show_source_update_hint(info, lang, parent=None):
    """Source installs cannot self-update - hand the user the exact git
    command and a link to the release notes."""
    import os
    import webbrowser
    from translations import t

    repo_dir = os.path.dirname(os.path.abspath(__file__))

    dlg = QDialog(parent)
    dlg.setWindowTitle(t("update_available_title", lang, version=info.latest))
    dlg.setMinimumWidth(520)
    layout = QVBoxLayout(dlg)
    layout.setSpacing(10)

    hint = QLabel(t("update_source_hint", lang))
    hint.setWordWrap(True)
    layout.addWidget(hint)
    layout.addLayout(make_copy_row(f"git -C {repo_dir} pull"))

    btn_row = QHBoxLayout()
    release_btn = QPushButton(t("update_view_release", lang))
    release_btn.clicked.connect(lambda: webbrowser.open(info.release_url))
    btn_row.addWidget(release_btn)
    btn_row.addStretch()
    ok_btn = QPushButton("OK")
    ok_btn.setDefault(True)
    ok_btn.clicked.connect(dlg.accept)
    btn_row.addWidget(ok_btn)
    layout.addLayout(btn_row)
    dlg.exec()


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
