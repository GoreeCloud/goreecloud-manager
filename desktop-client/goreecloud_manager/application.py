from __future__ import annotations

import sys

from PySide6.QtGui import QAction, QActionGroup, QColor
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from .config import AppConfig, load_config, save_config
from .recovery import prepare_config_recovery, protect_config_before_write
from .theme import (
    APPEARANCE_VALUES,
    apply_theme,
    normalize_appearance,
    semantic_color,
)
from .ui import MainWindow, SettingsDialog


_APPEARANCE_LABELS = {
    "system": "System",
    "light": "Light",
    "dark": "Dark",
}


class ManagerWindow(MainWindow):
    """Theme-aware shell around the existing read-only Manager dashboard."""

    def __init__(self, app: QApplication, config: AppConfig):
        self.app = app
        self._appearance_actions: dict[str, QAction] = {}
        super().__init__(config)
        self._install_appearance_menu()
        self._refresh_semantic_item_colors()

    def _install_appearance_menu(self) -> None:
        view_menu = self.menuBar().addMenu("View")
        appearance_menu = view_menu.addMenu("Appearance")
        action_group = QActionGroup(self)
        action_group.setExclusive(True)

        for value in APPEARANCE_VALUES:
            action = QAction(_APPEARANCE_LABELS[value], self)
            action.setCheckable(True)
            action.setData(value)
            action.triggered.connect(
                lambda checked=False, appearance=value: self.set_appearance(appearance)
            )
            action_group.addAction(action)
            appearance_menu.addAction(action)
            self._appearance_actions[value] = action

        self._sync_appearance_actions()

    def _sync_appearance_actions(self) -> None:
        selected = normalize_appearance(self.config.appearance)
        for value, action in self._appearance_actions.items():
            action.setChecked(value == selected)

    def _color(self, role: str) -> QColor:
        return QColor(semantic_color(self.config.appearance, role, self.app))

    def _refresh_semantic_item_colors(self) -> None:
        if hasattr(self, "container_table"):
            for row in range(self.container_table.rowCount()):
                state_item = self.container_table.item(row, 2)
                health_item = self.container_table.item(row, 3)
                if state_item is not None:
                    state = state_item.text().strip().casefold()
                    state_role = {
                        "running": "success",
                        "restarting": "warning",
                        "paused": "warning",
                        "dead": "danger",
                    }.get(state, "muted")
                    state_item.setForeground(self._color(state_role))
                if health_item is not None:
                    health = health_item.text().strip().casefold()
                    health_role = {
                        "healthy": "success",
                        "unhealthy": "danger",
                        "starting": "warning",
                    }.get(health, "muted")
                    health_item.setForeground(self._color(health_role))

        if hasattr(self, "peer_table"):
            for row in range(self.peer_table.rowCount()):
                status_item = self.peer_table.item(row, 2)
                if status_item is None:
                    continue
                status = status_item.text().strip().casefold()
                status_role = {
                    "connected": "success",
                    "connecting": "warning",
                    "idle": "warning",
                    "disconnected": "danger",
                    "offline": "danger",
                }.get(status, "muted")
                status_item.setForeground(self._color(status_role))

        if hasattr(self, "attention_label"):
            role = "warning" if self.attention_label.text().startswith("Needs attention:") else "muted"
            self.attention_label.setStyleSheet(f"color: {semantic_color(self.config.appearance, role, self.app)};")

    def _apply_container_filter(self):
        super()._apply_container_filter()
        self._refresh_semantic_item_colors()

    def _apply_peer_filter(self):
        super()._apply_peer_filter()
        self._refresh_semantic_item_colors()

    def _update_operational_status(self):
        super()._update_operational_status()
        self._refresh_semantic_item_colors()

    def set_appearance(self, appearance: str) -> None:
        appearance = normalize_appearance(appearance)
        previous = self.config.appearance
        if appearance == previous:
            apply_theme(self.app, appearance)
            self._sync_appearance_actions()
            self._refresh_semantic_item_colors()
            return

        self.config.appearance = appearance
        try:
            protect_config_before_write()
            save_config(self.config)
        except Exception as exc:
            self.config.appearance = previous
            self._sync_appearance_actions()
            QMessageBox.critical(self, "Could not save appearance", str(exc))
            return

        apply_theme(self.app, appearance)
        self._sync_appearance_actions()
        self._refresh_semantic_item_colors()

    def refresh_system_appearance(self) -> None:
        if normalize_appearance(self.config.appearance) == "system":
            apply_theme(self.app, "system")
            self._refresh_semantic_item_colors()

    def open_settings(self, initial_tab: int = 0):
        """Preserve the appearance preference across the existing settings editor."""
        dialog = SettingsDialog(self.config, self, initial_tab=initial_tab)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.result_config is None:
            return

        dialog.result_config.appearance = self.config.appearance
        try:
            protect_config_before_write()
            save_config(dialog.result_config)
        except Exception as exc:
            QMessageBox.critical(self, "Could not save settings", str(exc))
            return

        self.config = dialog.result_config
        self.setWindowTitle(self.config.title)
        self.title_label.setText(self.config.title)
        self.subtitle_label.setText(self.config.environment)
        self.configure_timer()
        self.rebuild_service_cards()
        self.pending_service_checks = 0
        self.system_check_pending = False
        self.infrastructure_check_pending = False
        self._sync_appearance_actions()
        self._refresh_semantic_item_colors()
        self.refresh_all()


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("GoreeCloud Manager")

    recovery_notice = ""
    try:
        recovery_notice = prepare_config_recovery()
        config = load_config()
        protect_config_before_write()
    except Exception as exc:
        apply_theme(app, "system")
        QMessageBox.critical(None, "GoreeCloud Manager", f"Could not load configuration:\n\n{exc}")
        return 1

    apply_theme(app, config.appearance)
    window = ManagerWindow(app, config)
    app.styleHints().colorSchemeChanged.connect(
        lambda _scheme: window.refresh_system_appearance()
    )
    window.show()
    if recovery_notice:
        QMessageBox.warning(window, "Configuration recovered", recovery_notice)
    return app.exec()
