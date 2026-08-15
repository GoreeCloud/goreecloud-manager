from __future__ import annotations

import sys
import re
import webbrowser
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .config import (
    AppConfig,
    MonitoringConfig,
    ServerConfig,
    ServiceConfig,
    ensure_user_config,
    load_config,
    save_config,
)
from .infrastructure import (
    InfrastructureOverview,
    InfrastructureError,
    discover_infrastructure,
)
from .health import (
    ServiceHealth,
    SystemHealth,
    SystemHealthError,
    check_url,
    format_bytes,
    format_uptime,
    local_health,
    remote_ssh_health,
)


APP_VERSION = __version__


def _compact_docker_memory(usage: str, percent: str) -> str:
    """Show useful per-container memory without repeating the host-wide limit."""
    used = (usage or "").split(" / ", 1)[0].strip()
    pct = (percent or "").strip()
    if used and pct and pct != "—":
        return f"{used} ({pct})"
    return used or pct or "—"


class SortableTableItem(QTableWidgetItem):
    def __lt__(self, other):
        if isinstance(other, QTableWidgetItem):
            left = self.data(Qt.ItemDataRole.UserRole)
            right = other.data(Qt.ItemDataRole.UserRole)
            if left is not None and right is not None:
                try:
                    return left < right
                except TypeError:
                    pass
        return super().__lt__(other)


def _table_item(value: str, *, sort_value=None) -> QTableWidgetItem:
    item = SortableTableItem(value or "—")
    item.setToolTip(value or "—")
    if sort_value is not None:
        item.setData(Qt.ItemDataRole.UserRole, sort_value)
    return item


def _percent_number(value: str) -> float:
    try:
        return float((value or "").replace("%", "").strip())
    except ValueError:
        return -1.0


def _format_netbird_latency(value: str) -> str:
    text = (value or "").strip()
    if not text or text in {"—", "-", "0s", "0ms", "0.0ms"}:
        return "—"
    compact = text.replace(" ", "")
    try:
        if compact.endswith("ms"):
            return f"{float(compact[:-2]):.1f} ms"
        if compact.endswith("µs") or compact.endswith("us"):
            suffix_len = 2
            return f"{float(compact[:-suffix_len]) / 1000.0:.2f} ms"
        if compact.endswith("s"):
            seconds = float(compact[:-1])
            if seconds < 1:
                return f"{seconds * 1000.0:.1f} ms"
            return f"{seconds:.2f} s"
    except ValueError:
        pass
    return text


def _compact_netbird_endpoint(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return "—"
    prefix = "Connected to "
    if text.startswith(prefix):
        endpoint = text[len(prefix):].strip()
        endpoint = endpoint.removeprefix("https://").removeprefix("http://").rstrip("/")
        return f"Connected • {endpoint}"
    return text


def _format_created(value: str) -> str:
    text = (value or "").strip()
    if not text or text.startswith("0001-01-01T00:00:00"):
        return "—"
    # Docker commonly returns RFC3339Nano timestamps (up to 9 fractional digits),
    # while Python 3.10's ISO parser accepts microseconds. Trim only the excess
    # precision and preserve the timezone before converting to local time.
    normalized = text
    match = re.match(r"^(.*?\.)(\d+)(Z|[+-]\d{2}:?\d{2})$", normalized)
    if match and len(match.group(2)) > 6:
        normalized = f"{match.group(1)}{match.group(2)[:6]}{match.group(3)}"
    try:
        dt = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%b %-d, %Y • %-I:%M %p")
    except (ValueError, OSError):
        return text


def _clean_docker_status(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return "—"
    # Health is already shown in its own column/detail field; remove Docker's
    # parenthetical health suffix so the UI does not say Healthy twice.
    return re.sub(r"\s*\((?:healthy|unhealthy|health:\s*starting)\)\s*$", "", text, flags=re.IGNORECASE).strip() or text

APP_STYLE = """
QMainWindow, QDialog, QWidget#root, QWidget#scrollBody, QWidget#scrollViewport,
QWidget#settingsBody, QWidget#settingsViewport {
    background: #0b1120;
    color: #e5eefc;
}
QLabel#title {
    color: #f8fbff;
    font-size: 29px;
    font-weight: 700;
}
QLabel#dialogTitle {
    color: #f8fbff;
    font-size: 22px;
    font-weight: 700;
}
QLabel#subtitle, QLabel.muted {
    color: #91a4c2;
    font-size: 13px;
}
QLabel.formLabel {
    color: #b8c7dd;
    font-size: 12px;
    font-weight: 600;
}
QLabel#sectionTitle {
    color: #eaf2ff;
    font-size: 19px;
    font-weight: 700;
}
QLabel#sourceName {
    color: #f8fbff;
    font-size: 15px;
    font-weight: 700;
}
QLabel#sourceBadgeLocal, QLabel#sourceBadgeSsh, QLabel#sourceBadgeError {
    border-radius: 10px;
    padding: 4px 9px;
    font-size: 11px;
    font-weight: 700;
}
QLabel#sourceBadgeLocal {
    color: #bfdbfe;
    background: #172554;
    border: 1px solid #1d4ed8;
}
QLabel#sourceBadgeSsh {
    color: #bbf7d0;
    background: #052e16;
    border: 1px solid #15803d;
}
QLabel#sourceBadgeError {
    color: #fecdd3;
    background: #4c0519;
    border: 1px solid #be123c;
}
QFrame.card, QFrame#sourceCard, QFrame.settingsCard {
    background: #121a2c;
    border: 1px solid #22304a;
    border-radius: 14px;
}
QFrame.card:hover {
    border: 1px solid #3c82f6;
}
QFrame#sourceCard {
    background: #0f1729;
}
QLabel.metricLabel {
    color: #8fa1bd;
    font-size: 12px;
}
QLabel.metricValue {
    color: #ffffff;
    font-size: 22px;
    font-weight: 700;
}
QLabel.metricDetail {
    color: #91a4c2;
    font-size: 11px;
}
QLabel.metricStatusNormal { color: #4ade80; font-size: 11px; font-weight: 700; }
QLabel.metricStatusWarning { color: #fbbf24; font-size: 11px; font-weight: 700; }
QLabel.metricStatusCritical { color: #fb7185; font-size: 11px; font-weight: 700; }
QLabel.infoLabel {
    color: #8193b0;
    font-size: 11px;
}
QLabel.infoValue {
    color: #eef5ff;
    font-size: 13px;
    font-weight: 600;
}
QFrame#detailsCard {
    background: #0f1729;
    border: 1px solid #22304a;
    border-radius: 14px;
}
QLabel.serviceName {
    color: #f7fbff;
    font-size: 16px;
    font-weight: 700;
}
QLabel.serviceDescription {
    color: #91a4c2;
    font-size: 12px;
}
QLabel.statusHealthy { color: #4ade80; font-weight: 700; }
QLabel.statusReachable { color: #60a5fa; font-weight: 700; }
QLabel.statusDegraded, QLabel.statusUnknown { color: #fbbf24; font-weight: 700; }
QLabel.statusOffline { color: #fb7185; font-weight: 700; }
QPushButton {
    background: #1d4ed8;
    border: none;
    border-radius: 9px;
    color: white;
    padding: 8px 12px;
    font-weight: 600;
}
QPushButton:hover { background: #2563eb; }
QPushButton:disabled { background: #24324b; color: #6e7f9a; }
QPushButton.secondary {
    background: #1b263b;
    border: 1px solid #32415e;
}
QPushButton.secondary:hover { background: #23314a; }
QPushButton.danger {
    background: #351522;
    border: 1px solid #713044;
    color: #fecdd3;
}
QPushButton.danger:hover { background: #4c1d2d; }
QFrame#emptyState {
    background: #0f1729;
    border: 1px dashed #334155;
    border-radius: 14px;
}
QLabel#emptyTitle {
    color: #f8fbff;
    font-size: 16px;
    font-weight: 700;
}
QProgressBar {
    background: #0b1220;
    border: 1px solid #25334d;
    border-radius: 5px;
    height: 10px;
    text-align: center;
}
QProgressBar::chunk {
    background: #3b82f6;
    border-radius: 4px;
}
QLineEdit, QComboBox, QSpinBox {
    background: #0b1220;
    color: #eaf2ff;
    border: 1px solid #32415e;
    border-radius: 8px;
    padding: 7px 9px;
    min-height: 20px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #3b82f6; }
QComboBox QAbstractItemView {
    background: #121a2c;
    color: #eaf2ff;
    border: 1px solid #32415e;
    selection-background-color: #1d4ed8;
}
QCheckBox { color: #e5eefc; spacing: 7px; }
QTabWidget::pane { border: 1px solid #22304a; border-radius: 10px; top: -1px; }
QTabBar::tab {
    background: #11192a;
    color: #91a4c2;
    border: 1px solid #22304a;
    padding: 8px 16px;
}
QTabBar::tab:selected { background: #172554; color: #eaf2ff; border-bottom-color: #172554; }
QScrollArea { border: none; background: #0b1120; }
QScrollBar:vertical {
    background: #0f1729;
    width: 11px;
    margin: 0;
    border: none;
}
QScrollBar::handle:vertical {
    background: #334155;
    min-height: 32px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover { background: #475569; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QTableWidget {
    background: #0f1729;
    color: #e5eefc;
    border: 1px solid #22304a;
    border-radius: 10px;
    gridline-color: #22304a;
    alternate-background-color: #111a2c;
    selection-background-color: #1d4ed8;
}
QHeaderView::section {
    background: #121a2c;
    color: #a9bad3;
    border: none;
    border-bottom: 1px solid #2a3955;
    padding: 8px;
    font-weight: 600;
}
QTableCornerButton::section { background: #121a2c; border: none; }
QLabel.statusBadgeGood, QLabel.statusBadgeWarn, QLabel.statusBadgeBad, QLabel.statusBadgeNeutral {
    border-radius: 9px;
    padding: 4px 9px;
    font-size: 11px;
    font-weight: 700;
}
QLabel.statusBadgeGood { color: #bbf7d0; background: #052e16; border: 1px solid #15803d; }
QLabel.statusBadgeWarn { color: #fde68a; background: #422006; border: 1px solid #a16207; }
QLabel.statusBadgeBad { color: #fecdd3; background: #4c0519; border: 1px solid #be123c; }
QLabel.statusBadgeNeutral { color: #cbd5e1; background: #1e293b; border: 1px solid #475569; }
"""


class WorkerSignals(QObject):
    finished = Signal(object)


class ServiceCheckWorker(QRunnable):
    def __init__(self, index: int, url: str):
        super().__init__()
        self.index = index
        self.url = url
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        self.signals.finished.emit((self.index, check_url(self.url)))


class SystemCheckWorker(QRunnable):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = deepcopy(config)
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            if self.config.monitoring.mode == "ssh":
                health = remote_ssh_health(
                    name=self.config.server.name,
                    host=self.config.server.host,
                    user=self.config.server.user,
                    port=self.config.server.port,
                    identity_file=self.config.server.identity_file,
                    timeout=self.config.monitoring.ssh_timeout_seconds,
                )
            else:
                health = local_health()
            self.signals.finished.emit((health, ""))
        except SystemHealthError as exc:
            self.signals.finished.emit((None, str(exc)))
        except Exception as exc:
            self.signals.finished.emit((None, f"Metrics error: {exc}"))


class SshTestWorker(QRunnable):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = deepcopy(config)
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            health = remote_ssh_health(
                name=self.config.server.name,
                host=self.config.server.host,
                user=self.config.server.user,
                port=self.config.server.port,
                identity_file=self.config.server.identity_file,
                timeout=self.config.monitoring.ssh_timeout_seconds,
            )
            self.signals.finished.emit((True, f"Connected to {health.source_detail}"))
        except Exception as exc:
            self.signals.finished.emit((False, str(exc)))


class MetricCard(QFrame):
    def __init__(self, label: str, *, show_bar: bool = True):
        super().__init__()
        self.label_text = label
        self.setProperty("class", "card")
        self.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)

        top = QHBoxLayout()
        label_widget = QLabel(label)
        label_widget.setProperty("class", "metricLabel")
        self.status = QLabel("—")
        self.status.setProperty("class", "metricStatusNormal")
        top.addWidget(label_widget)
        top.addStretch(1)
        top.addWidget(self.status)
        layout.addLayout(top)

        self.value = QLabel("—")
        self.value.setProperty("class", "metricValue")
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.detail = QLabel("—")
        self.detail.setProperty("class", "metricDetail")
        layout.addWidget(self.value)
        layout.addWidget(self.bar)
        layout.addWidget(self.detail)
        if not show_bar:
            self.bar.hide()
            self.status.hide()

    def set_percent(self, value: float, *, disk: bool = False):
        bounded = max(0.0, min(100.0, value))
        self.value.setText(f"{bounded:.1f}%")
        self.bar.setValue(round(bounded))
        if disk:
            if bounded >= 90:
                self.set_status("Critical", "metricStatusCritical")
            elif bounded >= 75:
                self.set_status("Warning", "metricStatusWarning")
            else:
                self.set_status("Normal", "metricStatusNormal")
        else:
            if bounded >= 85:
                self.set_status("High", "metricStatusCritical")
            elif bounded >= 70:
                self.set_status("Elevated", "metricStatusWarning")
            else:
                self.set_status("Normal", "metricStatusNormal")

    def set_status(self, text: str, class_name: str):
        self.status.setText(text)
        self.status.setProperty("class", class_name)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def set_detail(self, text: str):
        self.detail.setText(text or "—")

    def clear(self):
        self.value.setText("—")
        self.bar.setValue(0)
        self.detail.setText("—")
        if self.status.isVisible():
            self.set_status("—", "metricStatusNormal")


class InfoField(QWidget):
    def __init__(self, label: str):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        caption = QLabel(label)
        caption.setProperty("class", "infoLabel")
        self.value = QLabel("—")
        self.value.setProperty("class", "infoValue")
        self.value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.value.setWordWrap(True)
        layout.addWidget(caption)
        layout.addWidget(self.value)

    def set_text(self, text: str):
        display = text or "—"
        self.value.setText(display)
        self.value.setToolTip(display)


class StatusSummaryField(QWidget):
    def __init__(self, label: str):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        caption = QLabel(label)
        caption.setProperty("class", "infoLabel")
        self.badge = QLabel("CHECKING")
        self.badge.setProperty("class", "statusBadgeNeutral")
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail = QLabel("Waiting for data")
        self.detail.setProperty("class", "metricDetail")
        self.detail.setWordWrap(True)
        layout.addWidget(caption)
        layout.addWidget(self.badge, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.detail)

    def set_state(self, text: str, detail: str, class_name: str = "statusBadgeNeutral"):
        self.badge.setText(text)
        self.badge.setProperty("class", class_name)
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)
        self.detail.setText(detail or "—")


class ServiceCard(QFrame):
    def __init__(self, service: ServiceConfig):
        super().__init__()
        self.service = service
        if service.url:
            self.health = ServiceHealth("checking", "Checking…", "Waiting for check")
        else:
            self.health = ServiceHealth("unconfigured", "Not configured", "URL not configured")
        self.setProperty("class", "card")
        self.setFrameShape(QFrame.Shape.NoFrame)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(10)

        top = QHBoxLayout()
        name = QLabel(service.name)
        name.setProperty("class", "serviceName")
        self.status = QLabel(self.health.label)
        self.status.setProperty("class", "statusUnknown")
        top.addWidget(name)
        top.addStretch(1)
        top.addWidget(self.status)
        outer.addLayout(top)

        description = QLabel(service.description)
        description.setWordWrap(True)
        description.setProperty("class", "serviceDescription")
        outer.addWidget(description)

        actions = QHBoxLayout()
        self.open_button = QPushButton("Open")
        self.open_button.setEnabled(bool(service.url))
        self.open_button.clicked.connect(self.open_url)
        self.detail = QLabel(self.health.detail)
        self.detail.setProperty("class", "serviceDescription")
        actions.addWidget(self.open_button)
        actions.addWidget(self.detail, 1)
        outer.addLayout(actions)

    def open_url(self):
        if self.service.url:
            webbrowser.open(self.service.url)

    def set_health(self, health: ServiceHealth):
        self.health = health
        class_map = {
            "healthy": "statusHealthy",
            "reachable": "statusReachable",
            "degraded": "statusDegraded",
            "offline": "statusOffline",
            "unconfigured": "statusUnknown",
            "checking": "statusUnknown",
        }
        self.status.setText(health.label)
        self.status.setProperty("class", class_map.get(health.state, "statusUnknown"))
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.detail.setText(health.detail)

    def set_checking(self):
        target = "health endpoint" if self.service.health_url else "service URL"
        self.set_health(ServiceHealth("checking", "Checking…", f"Checking {target}"))


class ServiceEditorCard(QFrame):
    remove_requested = Signal(object)

    def __init__(self, service: ServiceConfig | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        service = deepcopy(service) if service is not None else ServiceConfig(name="")
        self.setProperty("class", "settingsCard")

        layout = QGridLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(9)

        self.name_input = QLineEdit(service.name)
        self.name_input.setPlaceholderText("Service name")
        self.description_input = QLineEdit(service.description)
        self.description_input.setPlaceholderText("Optional description")
        self.url_input = QLineEdit(service.url)
        self.url_input.setPlaceholderText("https://service.example.com")
        self.health_url_input = QLineEdit(service.health_url)
        self.health_url_input.setPlaceholderText("Optional dedicated health endpoint")
        self.enabled_check = QCheckBox("Show on dashboard")
        self.enabled_check.setChecked(service.enabled)

        remove_button = QPushButton("Remove")
        remove_button.setProperty("class", "danger")
        remove_button.clicked.connect(lambda: self.remove_requested.emit(self))

        layout.addWidget(self._label("Name"), 0, 0)
        layout.addWidget(self.name_input, 0, 1)
        layout.addWidget(self.enabled_check, 0, 2)
        layout.addWidget(remove_button, 0, 3)
        layout.addWidget(self._label("Description"), 1, 0)
        layout.addWidget(self.description_input, 1, 1, 1, 3)
        layout.addWidget(self._label("Open URL"), 2, 0)
        layout.addWidget(self.url_input, 2, 1, 1, 3)
        layout.addWidget(self._label("Health URL"), 3, 0)
        layout.addWidget(self.health_url_input, 3, 1, 1, 3)
        layout.setColumnStretch(1, 1)

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("class", "formLabel")
        return label

    def has_any_values(self) -> bool:
        return any(
            field.text().strip()
            for field in (
                self.name_input,
                self.description_input,
                self.url_input,
                self.health_url_input,
            )
        )

    def to_service(self) -> ServiceConfig:
        return ServiceConfig(
            name=self.name_input.text().strip(),
            description=self.description_input.text().strip(),
            url=self.url_input.text().strip(),
            health_url=self.health_url_input.text().strip(),
            enabled=self.enabled_check.isChecked(),
        )


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent: QWidget | None = None, initial_tab: int = 0):
        super().__init__(parent)
        self.original = deepcopy(config)
        self.result_config: AppConfig | None = None
        self.thread_pool = QThreadPool.globalInstance()
        self.service_editors: list[ServiceEditorCard] = []

        self.setWindowTitle("GoreeCloud Manager Settings")
        self.resize(920, 700)
        self.setMinimumSize(780, 600)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        title = QLabel("Settings")
        title.setObjectName("dialogTitle")
        subtitle = QLabel("Configure monitoring and only the services that actually exist in GoreeCloud.")
        subtitle.setProperty("class", "muted")
        root.addWidget(title)
        root.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_monitoring_tab(), "Monitoring")
        self.tabs.addTab(self._build_services_tab(), "Services")
        self.tabs.setCurrentIndex(max(0, min(1, initial_tab)))
        root.addWidget(self.tabs, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel_button = QPushButton("Cancel")
        cancel_button.setProperty("class", "secondary")
        cancel_button.clicked.connect(self.reject)
        save_button = QPushButton("Save")
        save_button.clicked.connect(self._save_and_accept)
        actions.addWidget(cancel_button)
        actions.addWidget(save_button)
        root.addLayout(actions)

        self._update_mode_ui()

    def _form_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("class", "formLabel")
        return label

    def _build_monitoring_tab(self) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setObjectName("settingsViewport")

        body = QWidget()
        body.setObjectName("settingsBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        intro = QLabel(
            "Use local mode for this laptop, or SSH mode for read-only GoreeCloud server metrics plus Docker and NetBird discovery."
        )
        intro.setWordWrap(True)
        intro.setProperty("class", "muted")
        layout.addWidget(intro)

        general_card = QFrame()
        general_card.setProperty("class", "settingsCard")
        general = QFormLayout(general_card)
        general.setContentsMargins(16, 16, 16, 16)
        general.setSpacing(12)
        general.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        general.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("This computer", "local")
        self.mode_combo.addItem("GoreeCloud server over SSH", "ssh")
        mode_index = self.mode_combo.findData(self.original.monitoring.mode)
        self.mode_combo.setCurrentIndex(max(0, mode_index))
        self.mode_combo.currentIndexChanged.connect(self._update_mode_ui)

        self.refresh_spin = QSpinBox()
        self.refresh_spin.setRange(0, 3600)
        self.refresh_spin.setSuffix(" seconds")
        self.refresh_spin.setSpecialValueText("Manual only")
        self.refresh_spin.setValue(self.original.monitoring.auto_refresh_seconds)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 60)
        self.timeout_spin.setSuffix(" seconds")
        self.timeout_spin.setValue(self.original.monitoring.ssh_timeout_seconds)

        general.addRow(self._form_label("Metrics source"), self.mode_combo)
        general.addRow(self._form_label("Auto refresh"), self.refresh_spin)
        general.addRow(self._form_label("SSH timeout"), self.timeout_spin)
        layout.addWidget(general_card)

        self.server_card = QFrame()
        self.server_card.setProperty("class", "settingsCard")
        server = QFormLayout(self.server_card)
        server.setContentsMargins(16, 16, 16, 16)
        server.setSpacing(12)
        server.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        server.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.server_name = QLineEdit(self.original.server.name)
        self.server_host = QLineEdit(self.original.server.host)
        self.server_host.setPlaceholderText("NetBird IP, hostname, or server address")
        self.server_port = QSpinBox()
        self.server_port.setRange(1, 65535)
        self.server_port.setValue(self.original.server.port)
        self.server_user = QLineEdit(self.original.server.user)
        self.server_user.setPlaceholderText("Optional if ~/.ssh/config supplies the user")
        self.identity_file = QLineEdit(self.original.server.identity_file)
        self.identity_file.setPlaceholderText("Optional; uses SSH agent/default keys when blank")

        key_row = QWidget()
        key_layout = QHBoxLayout(key_row)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.setSpacing(8)
        key_layout.addWidget(self.identity_file, 1)
        browse = QPushButton("Browse…")
        browse.setProperty("class", "secondary")
        browse.clicked.connect(self._browse_identity_file)
        key_layout.addWidget(browse)

        server.addRow(self._form_label("Display name"), self.server_name)
        server.addRow(self._form_label("Server address"), self.server_host)
        server.addRow(self._form_label("SSH port"), self.server_port)
        server.addRow(self._form_label("SSH username (optional)"), self.server_user)
        server.addRow(self._form_label("SSH key (optional)"), key_row)

        test_row = QWidget()
        test_layout = QHBoxLayout(test_row)
        test_layout.setContentsMargins(0, 0, 0, 0)
        test_layout.setSpacing(10)
        self.test_ssh_button = QPushButton("Test SSH connection")
        self.test_ssh_button.clicked.connect(self._test_ssh)
        self.test_ssh_status = QLabel("Uses OpenSSH keys, your SSH agent, or ~/.ssh/config. Passwords are not stored.")
        self.test_ssh_status.setWordWrap(True)
        self.test_ssh_status.setProperty("class", "muted")
        test_layout.addWidget(self.test_ssh_button)
        test_layout.addWidget(self.test_ssh_status, 1)
        server.addRow(self._form_label("Connection test"), test_row)

        layout.addWidget(self.server_card)
        layout.addStretch(1)
        scroll.setWidget(body)
        tab_layout.addWidget(scroll)
        return tab

    def _build_services_tab(self) -> QWidget:
        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(12)

        intro_row = QHBoxLayout()
        intro = QLabel(
            "No applications are assumed or preconfigured. Add only services that are currently deployed in GoreeCloud. "
            "The health URL is optional; when blank, GoreeCloud Manager checks the Open URL."
        )
        intro.setWordWrap(True)
        intro.setProperty("class", "muted")
        intro_row.addWidget(intro, 1)
        add_button = QPushButton("+ Add service")
        add_button.clicked.connect(lambda: self._add_service_editor())
        intro_row.addWidget(add_button, alignment=Qt.AlignmentFlag.AlignTop)
        outer.addLayout(intro_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setObjectName("settingsViewport")
        self.services_body = QWidget()
        self.services_body.setObjectName("settingsBody")
        self.services_body_layout = QVBoxLayout(self.services_body)
        self.services_body_layout.setContentsMargins(0, 0, 8, 0)
        self.services_body_layout.setSpacing(10)

        self.services_empty = QFrame()
        self.services_empty.setObjectName("emptyState")
        empty_layout = QVBoxLayout(self.services_empty)
        empty_layout.setContentsMargins(22, 24, 22, 24)
        empty_layout.setSpacing(7)
        empty_title = QLabel("No services configured")
        empty_title.setObjectName("emptyTitle")
        empty_text = QLabel(
            "Add a service when it is actually deployed. Future services such as Nextcloud or ONLYOFFICE will not appear until you add them yourself."
        )
        empty_text.setWordWrap(True)
        empty_text.setProperty("class", "muted")
        empty_layout.addWidget(empty_title)
        empty_layout.addWidget(empty_text)
        self.services_body_layout.addWidget(self.services_empty)

        for service in self.original.services:
            self._add_service_editor(service, focus=False)

        self.services_body_layout.addStretch(1)
        self._update_services_empty_state()
        scroll.setWidget(self.services_body)
        outer.addWidget(scroll, 1)
        return tab

    def _add_service_editor(self, service: ServiceConfig | None = None, *, focus: bool = True):
        editor = ServiceEditorCard(service)
        editor.remove_requested.connect(self._remove_service_editor)
        # Keep the stretch at the bottom by inserting before it.
        insert_at = max(0, self.services_body_layout.count() - 1)
        self.services_body_layout.insertWidget(insert_at, editor)
        self.service_editors.append(editor)
        self._update_services_empty_state()
        if focus:
            editor.name_input.setFocus()
            self.tabs.setCurrentIndex(1)

    @Slot(object)
    def _remove_service_editor(self, editor):
        if editor not in self.service_editors:
            return
        self.service_editors.remove(editor)
        self.services_body_layout.removeWidget(editor)
        editor.deleteLater()
        self._update_services_empty_state()

    def _update_services_empty_state(self):
        if hasattr(self, "services_empty"):
            self.services_empty.setVisible(not self.service_editors)

    def _update_mode_ui(self):
        ssh_mode = self.mode_combo.currentData() == "ssh"
        self.server_card.setEnabled(True)
        self.test_ssh_button.setEnabled(ssh_mode)
        if not ssh_mode:
            self.test_ssh_status.setText("Switch to SSH mode to test the GoreeCloud server connection.")

    def _browse_identity_file(self):
        start = str(Path(self.identity_file.text() or "~/.ssh").expanduser())
        selected, _ = QFileDialog.getOpenFileName(self, "Select SSH private key", start)
        if selected:
            home = str(Path.home())
            if selected.startswith(home + "/"):
                selected = "~" + selected[len(home):]
            self.identity_file.setText(selected)

    def _build_config(self) -> AppConfig:
        services: list[ServiceConfig] = []
        for editor in self.service_editors:
            service = editor.to_service()
            if service.name:
                services.append(service)

        return AppConfig(
            title=self.original.title,
            environment=self.original.environment,
            monitoring=MonitoringConfig(
                mode=str(self.mode_combo.currentData()),
                auto_refresh_seconds=self.refresh_spin.value(),
                ssh_timeout_seconds=self.timeout_spin.value(),
            ),
            server=ServerConfig(
                name=self.server_name.text().strip() or "goreecloud-vps-01",
                host=self.server_host.text().strip(),
                port=self.server_port.value(),
                user=self.server_user.text().strip(),
                identity_file=self.identity_file.text().strip(),
            ),
            services=services,
        )

    def _test_ssh(self):
        config = self._build_config()
        if not config.server.host:
            self.test_ssh_status.setText("Enter the server address first.")
            return
        self.test_ssh_button.setEnabled(False)
        self.test_ssh_status.setText("Testing connection…")
        worker = SshTestWorker(config)
        worker.signals.finished.connect(self._on_ssh_test)
        self.thread_pool.start(worker)

    @Slot(object)
    def _on_ssh_test(self, result):
        success, message = result
        self.test_ssh_button.setEnabled(self.mode_combo.currentData() == "ssh")
        self.test_ssh_status.setText(("Connected: " if success else "Failed: ") + message)

    def _save_and_accept(self):
        seen_names: set[str] = set()
        for editor in self.service_editors:
            if not editor.has_any_values():
                continue
            service = editor.to_service()
            if not service.name:
                QMessageBox.warning(self, "Service name required", "Every configured service needs a name.")
                self.tabs.setCurrentIndex(1)
                editor.name_input.setFocus()
                return
            normalized = service.name.casefold()
            if normalized in seen_names:
                QMessageBox.warning(self, "Duplicate service", f"The service name '{service.name}' is used more than once.")
                self.tabs.setCurrentIndex(1)
                editor.name_input.setFocus()
                return
            seen_names.add(normalized)
            for label, value in (("Open URL", service.url), ("Health URL", service.health_url)):
                if value and not value.lower().startswith(("http://", "https://")):
                    QMessageBox.warning(
                        self,
                        "Invalid service URL",
                        f"{service.name}: {label} must begin with http:// or https://.",
                    )
                    self.tabs.setCurrentIndex(1)
                    return

        config = self._build_config()
        if config.monitoring.mode == "ssh" and not config.server.host:
            QMessageBox.warning(
                self,
                "SSH configuration incomplete",
                "SSH mode requires a server address. The username may be omitted when ~/.ssh/config supplies it.",
            )
            return
        self.result_config = config
        self.accept()


class InfrastructureCheckWorker(QRunnable):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = deepcopy(config)
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            overview = discover_infrastructure(self.config)
            self.signals.finished.emit((overview, ""))
        except (InfrastructureError, Exception) as exc:
            self.signals.finished.emit((None, str(exc)))


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.thread_pool = QThreadPool.globalInstance()
        self.service_cards: list[ServiceCard] = []
        self.pending_service_checks = 0
        self.system_check_pending = False
        self.infrastructure_check_pending = False
        self.defer_infrastructure_refresh = False
        self.current_system_health = None
        self.current_docker = None
        self.current_netbird = None
        self.infrastructure_error = ""
        self.infrastructure_last_refresh = None
        self.selected_container_key = None
        self.setWindowTitle(config.title)
        self.resize(1180, 820)
        self.setMinimumSize(940, 650)

        icon_path = Path(__file__).resolve().parent.parent / "assets" / "goreecloud-manager.svg"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        shell = QVBoxLayout(root)
        shell.setContentsMargins(26, 24, 26, 22)
        shell.setSpacing(14)

        header = QHBoxLayout()
        title_group = QVBoxLayout()
        self.title_label = QLabel(config.title)
        self.title_label.setObjectName("title")
        self.subtitle_label = QLabel(config.environment)
        self.subtitle_label.setObjectName("subtitle")
        title_group.addWidget(self.title_label)
        title_group.addWidget(self.subtitle_label)
        header.addLayout(title_group)
        header.addStretch(1)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setProperty("class", "secondary")
        self.refresh_button.clicked.connect(self.refresh_all)
        header.addWidget(self.refresh_button)
        shell.addLayout(header)

        source_card = QFrame()
        source_card.setObjectName("sourceCard")
        source_layout = QHBoxLayout(source_card)
        source_layout.setContentsMargins(16, 12, 16, 12)
        source_text = QVBoxLayout()
        source_caption = QLabel("METRICS SOURCE")
        source_caption.setProperty("class", "metricLabel")
        self.source_name = QLabel("Preparing metrics…")
        self.source_name.setObjectName("sourceName")
        self.source_detail = QLabel("Please wait")
        self.source_detail.setProperty("class", "muted")
        source_text.addWidget(source_caption)
        source_text.addWidget(self.source_name)
        source_text.addWidget(self.source_detail)
        source_layout.addLayout(source_text)
        source_layout.addStretch(1)
        self.source_badge = QLabel("LOCAL")
        self.source_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.source_badge.setObjectName("sourceBadgeLocal")
        source_layout.addWidget(self.source_badge)
        shell.addWidget(source_card)

        self.nav_tabs = QTabWidget()
        self.nav_tabs.setDocumentMode(True)
        self.nav_tabs.addTab(self._build_overview_tab(), "Overview")
        self.nav_tabs.addTab(self._build_containers_tab(), "Containers")
        self.nav_tabs.addTab(self._build_network_tab(), "Network")
        shell.addWidget(self.nav_tabs, 1)

        footer = QHBoxLayout()
        self.footer_note = QLabel(f"v{APP_VERSION} • Read-only operations console")
        self.footer_note.setObjectName("subtitle")
        footer.addWidget(self.footer_note)
        footer.addStretch(1)
        self.last_refresh = QLabel("Not refreshed yet")
        self.last_refresh.setProperty("class", "muted")
        footer.addWidget(self.last_refresh)
        config_file = QPushButton("Config file")
        config_file.setProperty("class", "secondary")
        config_file.clicked.connect(self.open_configuration)
        footer.addWidget(config_file)
        settings = QPushButton("Settings")
        settings.setProperty("class", "secondary")
        settings.clicked.connect(lambda: self.open_settings(0))
        footer.addWidget(settings)
        shell.addLayout(footer)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_auto)
        self.configure_timer()
        self.refresh_all()

    def _build_overview_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("scrollBody")
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(4, 12, 4, 4)
        outer.setSpacing(14)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(12)
        metrics.setVerticalSpacing(12)
        self.cpu_card = MetricCard("CPU")
        self.memory_card = MetricCard("Memory")
        self.disk_card = MetricCard("Disk")
        self.uptime_card = MetricCard("Uptime", show_bar=False)
        for i, card in enumerate((self.cpu_card, self.memory_card, self.disk_card, self.uptime_card)):
            metrics.addWidget(card, 0, i)
            metrics.setColumnStretch(i, 1)
        outer.addLayout(metrics)

        self.details_card = QFrame()
        self.details_card.setObjectName("detailsCard")
        details_layout = QVBoxLayout(self.details_card)
        details_layout.setContentsMargins(16, 13, 16, 14)
        details_layout.setSpacing(10)
        details_header = QHBoxLayout()
        self.details_title = QLabel("System Details")
        self.details_title.setProperty("class", "serviceName")
        details_header.addWidget(self.details_title)
        details_header.addStretch(1)
        self.details_hint = QLabel("Read-only system information")
        self.details_hint.setProperty("class", "muted")
        details_header.addWidget(self.details_hint)
        details_layout.addLayout(details_header)
        details_grid = QGridLayout()
        details_grid.setHorizontalSpacing(24)
        details_grid.setVerticalSpacing(10)
        self.info_hostname = InfoField("Hostname")
        self.info_os = InfoField("Operating system")
        self.info_kernel = InfoField("Kernel")
        self.info_cpu = InfoField("CPU threads")
        self.info_load = InfoField("Load 1 / 5 / 15 min")
        self.info_memory = InfoField("Memory used / total")
        self.info_disk = InfoField("Root disk used / total")
        self.info_failed = InfoField("Failed systemd units")
        detail_fields = (
            self.info_hostname, self.info_os, self.info_kernel, self.info_cpu,
            self.info_load, self.info_memory, self.info_disk, self.info_failed,
        )
        for index, field in enumerate(detail_fields):
            details_grid.addWidget(field, index // 4, index % 4)
            details_grid.setColumnStretch(index % 4, 1)
        details_layout.addLayout(details_grid)
        outer.addWidget(self.details_card)

        self.operational_card = QFrame()
        self.operational_card.setObjectName("detailsCard")
        operational_layout = QVBoxLayout(self.operational_card)
        operational_layout.setContentsMargins(16, 13, 16, 14)
        operational_layout.setSpacing(10)
        operational_header = QHBoxLayout()
        operational_title = QLabel("Operational Status")
        operational_title.setProperty("class", "serviceName")
        operational_header.addWidget(operational_title)
        operational_header.addStretch(1)
        self.operational_hint = QLabel("Read-only health summary")
        self.operational_hint.setProperty("class", "muted")
        operational_header.addWidget(self.operational_hint)
        operational_layout.addLayout(operational_header)
        operational_grid = QGridLayout()
        operational_grid.setHorizontalSpacing(24)
        operational_grid.setVerticalSpacing(8)
        self.status_system = StatusSummaryField("System")
        self.status_docker = StatusSummaryField("Docker")
        self.status_netbird = StatusSummaryField("NetBird")
        self.status_services = StatusSummaryField("Services")
        for index, field in enumerate((self.status_system, self.status_docker, self.status_netbird, self.status_services)):
            operational_grid.addWidget(field, 0, index)
            operational_grid.setColumnStretch(index, 1)
        operational_layout.addLayout(operational_grid)
        self.attention_label = QLabel("Collecting operational status…")
        self.attention_label.setProperty("class", "muted")
        self.attention_label.setWordWrap(True)
        operational_layout.addWidget(self.attention_label)
        outer.addWidget(self.operational_card)

        services_header = QHBoxLayout()
        services_title = QLabel("Services")
        services_title.setObjectName("sectionTitle")
        services_header.addWidget(services_title)
        services_header.addStretch(1)
        self.services_summary = QLabel("Checking services…")
        self.services_summary.setProperty("class", "muted")
        services_header.addWidget(self.services_summary)
        outer.addLayout(services_header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setObjectName("scrollViewport")
        outer.addWidget(self.scroll, 1)
        self.rebuild_service_cards()
        return tab

    def _summary_card(self, title: str):
        card = QFrame()
        card.setProperty("class", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 13, 16, 13)
        label = QLabel(title)
        label.setProperty("class", "metricLabel")
        value = QLabel("—")
        value.setProperty("class", "metricValue")
        detail = QLabel("Waiting for discovery")
        detail.setProperty("class", "metricDetail")
        detail.setWordWrap(True)
        layout.addWidget(label)
        layout.addWidget(value)
        layout.addWidget(detail)
        return card, value, detail

    def _build_containers_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("scrollBody")
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(4, 12, 4, 4)
        outer.setSpacing(12)

        title_row = QHBoxLayout()
        title = QLabel("Docker Containers")
        title.setObjectName("sectionTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.docker_badge = QLabel("DISCOVERING")
        self.docker_badge.setProperty("class", "statusBadgeNeutral")
        title_row.addWidget(self.docker_badge)
        outer.addLayout(title_row)

        cards = QGridLayout()
        cards.setSpacing(12)
        c1, self.docker_version_value, self.docker_version_detail = self._summary_card("Docker Engine")
        c2, self.docker_running_value, self.docker_running_detail = self._summary_card("Running")
        c3, self.docker_health_value, self.docker_health_detail = self._summary_card("Health checks")
        c4, self.docker_stopped_value, self.docker_stopped_detail = self._summary_card("Stopped")
        for i, card in enumerate((c1, c2, c3, c4)):
            cards.addWidget(card, 0, i)
            cards.setColumnStretch(i, 1)
        outer.addLayout(cards)

        controls = QHBoxLayout()
        self.container_search = QLineEdit()
        self.container_search.setPlaceholderText("Search containers, images, ports…")
        self.container_search.setClearButtonEnabled(True)
        self.container_search.textChanged.connect(self._apply_container_filter)
        controls.addWidget(self.container_search, 1)
        self.container_filter = QComboBox()
        self.container_filter.addItem("All containers", "all")
        self.container_filter.addItem("Running", "running")
        self.container_filter.addItem("Stopped", "stopped")
        self.container_filter.addItem("Needs attention", "attention")
        self.container_filter.addItem("Healthy", "healthy")
        self.container_filter.addItem("Unhealthy", "unhealthy")
        self.container_filter.addItem("Health starting", "starting")
        self.container_filter.addItem("No healthcheck", "no_healthcheck")
        self.container_filter.currentIndexChanged.connect(self._apply_container_filter)
        controls.addWidget(self.container_filter)
        self.container_count = QLabel("0 shown")
        self.container_count.setProperty("class", "muted")
        controls.addWidget(self.container_count)
        outer.addLayout(controls)

        self.docker_message = QLabel("Discovering Docker on the selected metrics source…")
        self.docker_message.setProperty("class", "muted")
        self.docker_message.setWordWrap(True)
        outer.addWidget(self.docker_message)

        self.container_table = QTableWidget(0, 8)
        self.container_table.setHorizontalHeaderLabels(["Name", "Image", "State", "Health", "CPU", "Memory", "Ports", "Status"])
        self.container_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.container_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.container_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.container_table.setAlternatingRowColors(True)
        self.container_table.setSortingEnabled(True)
        self.container_table.verticalHeader().setVisible(False)
        header = self.container_table.horizontalHeader()
        for col in range(7):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.container_table.setColumnWidth(0, 190)
        self.container_table.setColumnWidth(1, 190)
        self.container_table.setColumnWidth(2, 78)
        self.container_table.setColumnWidth(3, 88)
        self.container_table.setColumnWidth(4, 72)
        self.container_table.setColumnWidth(5, 145)
        self.container_table.setColumnWidth(6, 175)
        self.container_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.container_table.itemSelectionChanged.connect(self._update_container_details)
        outer.addWidget(self.container_table, 1)

        self.container_details_card = QFrame()
        self.container_details_card.setObjectName("detailsCard")
        details = self.container_details_card
        detail_layout = QVBoxLayout(details)
        detail_layout.setContentsMargins(16, 12, 16, 13)
        detail_layout.setSpacing(9)
        detail_header = QHBoxLayout()
        detail_title = QLabel("Container Details")
        detail_title.setProperty("class", "serviceName")
        detail_header.addWidget(detail_title)
        detail_header.addStretch(1)
        self.container_detail_hint = QLabel("Select a container")
        self.container_detail_hint.setProperty("class", "muted")
        detail_header.addWidget(self.container_detail_hint)
        self.container_details_toggle = QPushButton("Show details")
        self.container_details_toggle.setCheckable(True)
        self.container_details_toggle.setChecked(False)
        self.container_details_toggle.setEnabled(False)
        self.container_details_toggle.clicked.connect(self._toggle_container_details)
        detail_header.addWidget(self.container_details_toggle)
        detail_layout.addLayout(detail_header)

        self.container_details_body = QWidget()
        self.container_details_body.setObjectName("scrollBody")
        detail_grid = QGridLayout(self.container_details_body)
        detail_grid.setContentsMargins(0, 0, 0, 0)
        detail_grid.setHorizontalSpacing(22)
        detail_grid.setVerticalSpacing(8)
        self.container_detail_id = InfoField("Container ID")
        self.container_detail_image = InfoField("Image")
        self.container_detail_created = InfoField("Created")
        self.container_detail_restarts = InfoField("Restart count")
        self.container_detail_pid = InfoField("PID")
        self.container_detail_exit = InfoField("Exit code")
        self.container_detail_restart_policy = InfoField("Restart policy")
        self.container_detail_oom = InfoField("OOM killed")
        self.container_detail_networks = InfoField("Networks")
        self.container_detail_addresses = InfoField("Network addresses")
        self.container_detail_ports = InfoField("Ports")
        self.container_detail_resource = InfoField("CPU / memory")
        self.container_detail_started = InfoField("Started")
        self.container_detail_finished = InfoField("Finished")
        self.container_detail_status = InfoField("State / health")
        self.container_detail_health_failures = InfoField("Health failures")
        self.container_detail_mounts = InfoField("Mounts")
        detail_fields = (
            self.container_detail_id, self.container_detail_image,
            self.container_detail_created, self.container_detail_restarts,
            self.container_detail_pid, self.container_detail_exit,
            self.container_detail_restart_policy, self.container_detail_oom,
            self.container_detail_networks, self.container_detail_addresses,
            self.container_detail_ports, self.container_detail_resource,
            self.container_detail_started, self.container_detail_finished,
            self.container_detail_status, self.container_detail_health_failures,
        )
        for index, field in enumerate(detail_fields):
            detail_grid.addWidget(field, index // 4, index % 4)
            detail_grid.setColumnStretch(index % 4, 1)
        detail_grid.addWidget(self.container_detail_mounts, 4, 0, 1, 4)
        detail_layout.addWidget(self.container_details_body)
        self.container_details_body.setVisible(False)
        outer.addWidget(details)
        return tab

    def _build_network_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("scrollBody")
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(4, 12, 4, 4)
        outer.setSpacing(12)
        title_row = QHBoxLayout()
        title = QLabel("NetBird Network")
        title.setObjectName("sectionTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.netbird_badge = QLabel("DISCOVERING")
        self.netbird_badge.setProperty("class", "statusBadgeNeutral")
        title_row.addWidget(self.netbird_badge)
        outer.addLayout(title_row)

        cards = QGridLayout()
        cards.setSpacing(12)
        c1, self.netbird_ip_value, self.netbird_ip_detail = self._summary_card("NetBird IP")
        c2, self.netbird_peers_value, self.netbird_peers_detail = self._summary_card("Connected peers")
        c3, self.netbird_version_value, self.netbird_version_detail = self._summary_card("Agent")
        for i, card in enumerate((c1, c2, c3)):
            cards.addWidget(card, 0, i)
            cards.setColumnStretch(i, 1)
        outer.addLayout(cards)

        details = QFrame()
        details.setObjectName("detailsCard")
        details_layout = QGridLayout(details)
        details_layout.setContentsMargins(16, 13, 16, 13)
        details_layout.setHorizontalSpacing(24)
        self.nb_management = InfoField("Management")
        self.nb_signal = InfoField("Signal")
        self.nb_interface = InfoField("Interface type")
        self.nb_daemon = InfoField("Daemon version")
        for i, field in enumerate((self.nb_management, self.nb_signal, self.nb_interface, self.nb_daemon)):
            details_layout.addWidget(field, 0, i)
            details_layout.setColumnStretch(i, 1)
        outer.addWidget(details)

        peer_controls = QHBoxLayout()
        self.peer_search = QLineEdit()
        self.peer_search.setPlaceholderText("Search peers or NetBird IP…")
        self.peer_search.setClearButtonEnabled(True)
        self.peer_search.textChanged.connect(self._apply_peer_filter)
        peer_controls.addWidget(self.peer_search, 1)
        self.peer_filter = QComboBox()
        self.peer_filter.addItem("All peers", "all")
        self.peer_filter.addItem("Needs attention", "attention")
        self.peer_filter.addItem("Connected", "connected")
        self.peer_filter.addItem("Connecting", "connecting")
        self.peer_filter.addItem("Disconnected", "disconnected")
        self.peer_filter.currentIndexChanged.connect(self._apply_peer_filter)
        peer_controls.addWidget(self.peer_filter)
        self.peer_count_label = QLabel("0 shown")
        self.peer_count_label.setProperty("class", "muted")
        peer_controls.addWidget(self.peer_count_label)
        outer.addLayout(peer_controls)

        self.netbird_message = QLabel("Discovering NetBird on the selected metrics source…")
        self.netbird_message.setProperty("class", "muted")
        self.netbird_message.setWordWrap(True)
        outer.addWidget(self.netbird_message)

        self.peer_table = QTableWidget(0, 5)
        self.peer_table.setHorizontalHeaderLabels(["Peer", "NetBird IP", "Status", "Connection", "Latency"])
        self.peer_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.peer_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.peer_table.setAlternatingRowColors(True)
        self.peer_table.setSortingEnabled(True)
        self.peer_table.verticalHeader().setVisible(False)
        header = self.peer_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 5):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        self.peer_table.setColumnWidth(1, 155)
        self.peer_table.setColumnWidth(2, 110)
        self.peer_table.setColumnWidth(3, 105)
        self.peer_table.setColumnWidth(4, 105)
        self.peer_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        outer.addWidget(self.peer_table, 1)
        return tab

    def _apply_container_filter(self):
        docker = self.current_docker
        if docker is None or getattr(docker, "state", "") != "available":
            self.container_table.setRowCount(0)
            self.container_count.setText("0 shown")
            return
        query = self.container_search.text().strip().casefold()
        mode = str(self.container_filter.currentData() or "all")
        filtered = []
        for item in docker.containers:
            state = item.state.casefold()
            health = item.health.casefold()
            if mode == "running" and state != "running":
                continue
            if mode == "stopped" and state == "running":
                continue
            if mode == "attention" and not (health in {"unhealthy", "starting"} or state in {"restarting", "dead"} or item.oom_killed):
                continue
            if mode == "healthy" and health != "healthy":
                continue
            if mode == "unhealthy" and health != "unhealthy":
                continue
            if mode == "starting" and health != "starting":
                continue
            if mode == "no_healthcheck" and health:
                continue
            haystack = " ".join((item.name, item.image, item.state, item.health, item.ports, item.status, item.networks)).casefold()
            if query and query not in haystack:
                continue
            filtered.append(item)

        selected_key = self.selected_container_key
        selected = self._container_for_selected_row()
        if selected is not None:
            selected_key = selected.container_id or selected.name

        sorting = self.container_table.isSortingEnabled()
        self.container_table.setSortingEnabled(False)
        self.container_table.setRowCount(len(filtered))
        for row, item in enumerate(filtered):
            memory = _compact_docker_memory(item.memory, item.memory_percent)
            health = item.health.title() if item.health else "No healthcheck"
            status_text = _clean_docker_status(item.status)
            values = [item.name, item.image, item.state, health, item.cpu, memory, item.ports or "—", status_text]
            sort_values = [
                item.name.casefold(), item.image.casefold(), item.state.casefold(), item.health.casefold(),
                _percent_number(item.cpu), _percent_number(item.memory_percent), item.ports.casefold(), _clean_docker_status(item.status).casefold(),
            ]
            for col, value in enumerate(values):
                cell = _table_item(value, sort_value=sort_values[col])
                if col == 0:
                    cell.setData(int(Qt.ItemDataRole.UserRole) + 1, item.container_id or item.name)
                if col == 2:
                    state_lower = item.state.casefold()
                    if state_lower == "running":
                        cell.setForeground(QColor("#4ade80"))
                    elif state_lower in {"restarting", "paused"}:
                        cell.setForeground(QColor("#fbbf24"))
                    elif state_lower in {"exited", "dead"}:
                        cell.setForeground(QColor("#91a4c2" if state_lower == "exited" else "#fb7185"))
                if col == 3 and item.health:
                    if item.health.casefold() == "healthy":
                        cell.setForeground(QColor("#4ade80"))
                    elif item.health.casefold() == "unhealthy":
                        cell.setForeground(QColor("#fb7185"))
                    elif item.health.casefold() == "starting":
                        cell.setForeground(QColor("#fbbf24"))
                elif col == 3 and not item.health:
                    cell.setForeground(QColor("#91a4c2"))
                self.container_table.setItem(row, col, cell)
        self.container_table.setSortingEnabled(sorting)
        self.container_count.setText(f"{len(filtered)} of {docker.total} shown")
        selected_row = -1
        if selected_key:
            for row in range(self.container_table.rowCount()):
                cell = self.container_table.item(row, 0)
                if cell and cell.data(int(Qt.ItemDataRole.UserRole) + 1) == selected_key:
                    selected_row = row
                    break
        if selected_row >= 0:
            self.container_table.selectRow(selected_row)
        elif filtered:
            self.container_table.selectRow(0)
        else:
            self._clear_container_details("No matching container")

    def _container_for_selected_row(self):
        docker = self.current_docker
        if docker is None:
            return None
        row = self.container_table.currentRow()
        if row < 0:
            return None
        cell = self.container_table.item(row, 0)
        if cell is None:
            return None
        key = cell.data(int(Qt.ItemDataRole.UserRole) + 1)
        for item in docker.containers:
            if (item.container_id or item.name) == key:
                return item
        return None

    def _clear_container_details(self, hint: str = "Select a container"):
        self.container_detail_hint.setText(hint)
        if hasattr(self, "container_details_toggle"):
            self.container_details_toggle.setEnabled(False)
            self.container_details_toggle.setChecked(False)
            self.container_details_toggle.setText("Show details")
        if hasattr(self, "container_details_body"):
            self.container_details_body.setVisible(False)
        for field in (
            self.container_detail_id, self.container_detail_image, self.container_detail_created,
            self.container_detail_restarts, self.container_detail_pid, self.container_detail_exit,
            self.container_detail_restart_policy, self.container_detail_oom,
            self.container_detail_networks, self.container_detail_addresses, self.container_detail_ports,
            self.container_detail_resource, self.container_detail_started, self.container_detail_finished,
            self.container_detail_status, self.container_detail_health_failures, self.container_detail_mounts,
        ):
            field.set_text("—")

    def _update_container_details(self):
        item = self._container_for_selected_row()
        if item is None:
            self._clear_container_details()
            return
        self.selected_container_key = item.container_id or item.name
        self.container_details_toggle.setEnabled(True)
        self.container_detail_hint.setText(item.name)
        short_id = item.container_id[:12] if item.container_id else "—"
        self.container_detail_id.set_text(short_id)
        self.container_detail_id.value.setToolTip(item.container_id or "—")
        self.container_detail_image.set_text(item.image)
        self.container_detail_created.set_text(_format_created(item.created_at))
        self.container_detail_created.value.setToolTip(item.created_at or "—")
        self.container_detail_restarts.set_text(str(item.restart_count))
        self.container_detail_pid.set_text(str(item.pid) if item.pid else "—")
        self.container_detail_exit.set_text(str(item.exit_code))
        self.container_detail_restart_policy.set_text(item.restart_policy or "none")
        self.container_detail_oom.set_text("Yes" if item.oom_killed else "No")
        network_text = item.networks or "—"
        if item.network_mode and item.network_mode not in {"default", ""}:
            network_text = f"{network_text} • mode: {item.network_mode}" if network_text != "—" else f"mode: {item.network_mode}"
        self.container_detail_networks.set_text(network_text)
        self.container_detail_addresses.set_text(item.network_addresses or "—")
        self.container_detail_ports.set_text(item.ports or "—")
        self.container_detail_resource.set_text(f"{item.cpu} • {_compact_docker_memory(item.memory, item.memory_percent)}")
        self.container_detail_started.set_text(_format_created(item.started_at))
        self.container_detail_started.value.setToolTip(item.started_at or "—")
        finished = _format_created(item.finished_at)
        if item.state.casefold() == "running" and (not item.finished_at or item.finished_at.startswith("0001-")):
            finished = "—"
        self.container_detail_finished.set_text(finished)
        self.container_detail_finished.value.setToolTip(item.finished_at or "—")
        state_health = item.state.title() if item.state else "—"
        if item.health:
            state_health += f" • {item.health.title()}"
        status_text = _clean_docker_status(item.status)
        self.container_detail_status.set_text(f"{state_health} • {status_text}" if status_text and status_text != "—" else state_health)
        self.container_detail_health_failures.set_text(str(item.health_failing_streak) if item.health else "Not monitored")
        self.container_detail_mounts.set_text(item.mounts or "No mounts reported")

    def _toggle_container_details(self, checked: bool):
        self.container_details_body.setVisible(bool(checked))
        self.container_details_toggle.setText("Hide details" if checked else "Show details")

    def _apply_peer_filter(self):
        nb = self.current_netbird
        if nb is None or getattr(nb, "state", "") != "available":
            self.peer_table.setRowCount(0)
            self.peer_count_label.setText("0 shown")
            return
        query = self.peer_search.text().strip().casefold()
        mode = str(self.peer_filter.currentData() or "all")
        filtered = []
        for peer in nb.peers:
            status = peer.status.casefold()
            if mode == "attention":
                if status not in {"connecting", "disconnected", "offline", "idle"}:
                    continue
            elif mode != "all" and status != mode:
                continue
            haystack = " ".join((peer.name, peer.ip, peer.status, peer.connection_type)).casefold()
            if query and query not in haystack:
                continue
            filtered.append(peer)

        sorting = self.peer_table.isSortingEnabled()
        self.peer_table.setSortingEnabled(False)
        self.peer_table.setRowCount(len(filtered))
        for row, peer in enumerate(filtered):
            latency = _format_netbird_latency(peer.latency)
            values = [peer.name, peer.ip or "—", peer.status or "—", peer.connection_type or "—", latency]
            sort_values = [peer.name.casefold(), peer.ip, peer.status.casefold(), peer.connection_type.casefold(), self._latency_sort_value(latency)]
            for col, value in enumerate(values):
                cell = _table_item(value, sort_value=sort_values[col])
                if col == 2:
                    status = peer.status.casefold()
                    if status == "connected":
                        cell.setForeground(QColor("#4ade80"))
                    elif status in {"connecting", "idle"}:
                        cell.setForeground(QColor("#fbbf24"))
                    elif status in {"disconnected", "offline"}:
                        cell.setForeground(QColor("#fb7185"))
                self.peer_table.setItem(row, col, cell)
        self.peer_table.setSortingEnabled(sorting)
        self.peer_count_label.setText(f"{len(filtered)} of {len(nb.peers)} shown")

    @staticmethod
    def _latency_sort_value(text: str) -> float:
        if not text or text == "—":
            return float("inf")
        try:
            if text.endswith(" ms"):
                return float(text[:-3].strip())
            if text.endswith(" s"):
                return float(text[:-2].strip()) * 1000.0
        except ValueError:
            pass
        return float("inf")

    def configure_timer(self):
        self.timer.stop()
        seconds = self.config.monitoring.auto_refresh_seconds
        if seconds > 0:
            self.timer.start(seconds * 1000)

    def rebuild_service_cards(self):
        body = QWidget()
        body.setObjectName("scrollBody")
        grid = QGridLayout(body)
        grid.setSpacing(12)
        grid.setContentsMargins(0, 0, 8, 0)
        self.service_cards = []
        enabled_services = [svc for svc in self.config.services if svc.enabled]
        if not enabled_services:
            empty = QFrame()
            empty.setObjectName("emptyState")
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(24, 24, 24, 24)
            empty_layout.setSpacing(8)
            empty_title = QLabel("No GoreeCloud services configured")
            empty_title.setObjectName("emptyTitle")
            empty_text = QLabel("Add a service only when it actually exists in your GoreeCloud environment.")
            empty_text.setWordWrap(True)
            empty_text.setProperty("class", "muted")
            add_service = QPushButton("Add service")
            add_service.clicked.connect(lambda: self.open_settings(1))
            empty_layout.addWidget(empty_title)
            empty_layout.addWidget(empty_text)
            empty_layout.addSpacing(3)
            empty_layout.addWidget(add_service, alignment=Qt.AlignmentFlag.AlignLeft)
            empty_layout.addStretch(1)
            grid.addWidget(empty, 0, 0, 1, 2)
            grid.setRowStretch(1, 1)
            if hasattr(self, "services_summary"):
                self.services_summary.setText("No services configured")
        else:
            for index, service in enumerate(enabled_services):
                card = ServiceCard(service)
                self.service_cards.append(card)
                grid.addWidget(card, index // 2, index % 2)
            grid.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding), (len(enabled_services) + 1) // 2, 0)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self.scroll.setWidget(body)

    def refresh_auto(self):
        # Overview auto-refreshes stay lightweight. Docker stats/inspect can be
        # noticeably expensive with many containers, so only refresh infrastructure
        # automatically while an infrastructure tab is actually being viewed.
        if self.nav_tabs.currentIndex() == 0:
            self.refresh_lightweight()
        else:
            self.refresh_all()

    def refresh_lightweight(self):
        if self.system_check_pending or self.pending_service_checks or self.infrastructure_check_pending:
            return
        self.refresh_button.setEnabled(False)
        self.last_refresh.setText("Refreshing…")
        self.defer_infrastructure_refresh = False
        self.refresh_system_health()
        self.refresh_services()

    def refresh_all(self):
        if self.system_check_pending or self.pending_service_checks or self.infrastructure_check_pending:
            return
        self.refresh_button.setEnabled(False)
        self.last_refresh.setText("Refreshing…")
        # Measure server CPU before Docker/NetBird discovery starts. This prevents
        # the monitoring workload itself from artificially inflating the CPU card.
        self.defer_infrastructure_refresh = True
        self.refresh_system_health()
        self.refresh_services()

    def refresh_system_health(self):
        self.system_check_pending = True
        if self.config.monitoring.mode == "ssh":
            self.details_title.setText("Server Details")
            self.source_name.setText(self.config.server.name)
            self.source_detail.setText(f"Connecting with OpenSSH • Port {self.config.server.port}" if self.config.server.host else "SSH connection is not configured")
            self.set_source_badge("SSH", "sourceBadgeSsh")
        else:
            self.details_title.setText("System Details")
            self.source_name.setText("This computer")
            self.source_detail.setText("Local Linux system")
            self.set_source_badge("LOCAL", "sourceBadgeLocal")
        worker = SystemCheckWorker(self.config)
        worker.signals.finished.connect(self.on_system_check)
        self.thread_pool.start(worker)

    def refresh_services(self):
        self.pending_service_checks = 0
        for index, card in enumerate(self.service_cards):
            if not card.service.url:
                card.set_health(ServiceHealth("unconfigured", "Not configured", "URL not configured"))
                continue
            card.set_checking()
            self.pending_service_checks += 1
            worker = ServiceCheckWorker(index, card.service.health_url or card.service.url)
            worker.signals.finished.connect(self.on_service_check)
            self.thread_pool.start(worker)
        self.update_service_summary()
        self.finish_refresh_if_ready()

    def refresh_infrastructure(self):
        self.infrastructure_check_pending = True
        self._set_badge(self.docker_badge, "DISCOVERING", "statusBadgeNeutral")
        self._set_badge(self.netbird_badge, "DISCOVERING", "statusBadgeNeutral")
        worker = InfrastructureCheckWorker(self.config)
        worker.signals.finished.connect(self.on_infrastructure_check)
        self.thread_pool.start(worker)

    @Slot(object)
    def on_system_check(self, result):
        health, error = result
        self.system_check_pending = False
        if isinstance(health, SystemHealth):
            self.current_system_health = health
            self.cpu_card.set_percent(health.cpu_percent)
            self.memory_card.set_percent(health.memory_percent)
            self.disk_card.set_percent(health.disk_percent, disk=True)
            self.uptime_card.value.setText(format_uptime(health.uptime_seconds))
            self.uptime_card.set_detail("Since last system boot")
            self.cpu_card.set_detail(f"{health.cpu_threads} CPU threads" if health.cpu_threads else "CPU utilization")
            self.memory_card.set_detail(f"{format_bytes(health.memory_used_bytes)} / {format_bytes(health.memory_total_bytes)}" if health.memory_total_bytes else "Memory utilization")
            self.disk_card.set_detail(f"{format_bytes(health.disk_used_bytes)} / {format_bytes(health.disk_total_bytes)} on /" if health.disk_total_bytes else "Root filesystem")
            self.source_name.setText(health.source_name)
            self.source_detail.setText(health.source_detail)
            self.info_hostname.set_text(health.hostname)
            self.info_os.set_text(health.os_name)
            self.info_kernel.set_text(health.kernel)
            self.info_cpu.set_text(str(health.cpu_threads) if health.cpu_threads else "—")
            self.info_load.set_text(f"{health.load_1:.2f} / {health.load_5:.2f} / {health.load_15:.2f}")
            self.info_memory.set_text(f"{format_bytes(health.memory_used_bytes)} / {format_bytes(health.memory_total_bytes)}" if health.memory_total_bytes else "—")
            self.info_disk.set_text(f"{format_bytes(health.disk_used_bytes)} / {format_bytes(health.disk_total_bytes)}" if health.disk_total_bytes else "—")
            if health.failed_units is None:
                self.info_failed.set_text("Unavailable")
            elif health.failed_units == 0:
                self.info_failed.set_text("0 — all clear")
            else:
                self.info_failed.set_text(str(health.failed_units))
            if self.config.monitoring.mode == "ssh":
                self.set_source_badge("SSH CONNECTED", "sourceBadgeSsh")
                self.details_title.setText("Server Details")
            else:
                self.set_source_badge("LOCAL", "sourceBadgeLocal")
                self.details_title.setText("System Details")
        else:
            self.current_system_health = None
            for card in (self.cpu_card, self.memory_card, self.disk_card, self.uptime_card):
                card.clear()
            for field in (self.info_hostname, self.info_os, self.info_kernel, self.info_cpu, self.info_load, self.info_memory, self.info_disk, self.info_failed):
                field.set_text("—")
            self.source_detail.setText(error or "Metrics unavailable")
            self.set_source_badge("METRICS ERROR", "sourceBadgeError")
        self._update_operational_status()
        if self.defer_infrastructure_refresh:
            self.defer_infrastructure_refresh = False
            self.refresh_infrastructure()
        self.finish_refresh_if_ready()

    @Slot(object)
    def on_service_check(self, result):
        index, health = result
        if 0 <= index < len(self.service_cards):
            self.service_cards[index].set_health(health)
        self.pending_service_checks = max(0, self.pending_service_checks - 1)
        self.update_service_summary()
        self._update_operational_status()
        self.finish_refresh_if_ready()

    @Slot(object)
    def on_infrastructure_check(self, result):
        overview, error = result
        self.infrastructure_check_pending = False
        self.infrastructure_last_refresh = datetime.now()
        if isinstance(overview, InfrastructureOverview):
            self.infrastructure_error = ""
            self._render_docker(overview)
            self._render_netbird(overview)
        else:
            self.infrastructure_error = error or "Infrastructure discovery unavailable"
            self._render_infrastructure_error(self.infrastructure_error)
        self._update_operational_status()
        self.finish_refresh_if_ready()

    def _render_docker(self, overview: InfrastructureOverview):
        docker = overview.docker
        self.current_docker = docker
        self.container_table.setRowCount(0)
        if docker.state == "available":
            if docker.unhealthy:
                self._set_badge(self.docker_badge, f"{docker.unhealthy} UNHEALTHY", "statusBadgeBad")
            elif docker.health_starting:
                self._set_badge(self.docker_badge, f"{docker.health_starting} STARTING", "statusBadgeWarn")
            else:
                self._set_badge(self.docker_badge, "AVAILABLE", "statusBadgeGood")
            self.docker_version_value.setText(docker.version or "Installed")
            self.docker_version_detail.setText(f"Docker Engine • {docker.total} total")
            self.docker_running_value.setText(str(docker.running))
            self.docker_running_detail.setText(f"{docker.running} of {docker.total} running")
            self.docker_health_value.setText(str(docker.health_monitored))
            health_parts = [f"{docker.healthy} healthy", f"{docker.unhealthy} unhealthy"]
            if docker.health_starting:
                health_parts.append(f"{docker.health_starting} starting")
            if docker.no_healthcheck:
                health_parts.append(f"{docker.no_healthcheck} without healthcheck")
            self.docker_health_detail.setText(" • ".join(health_parts))
            self.docker_stopped_value.setText(str(docker.stopped))
            self.docker_stopped_detail.setText("not running" if docker.stopped else "all containers running")
            self.docker_message.setText("Read-only Docker inventory. Search, filter, sort columns, and select a row for details.")
            self._apply_container_filter()
        elif docker.state == "not_installed":
            self._set_badge(self.docker_badge, "NOT INSTALLED", "statusBadgeNeutral")
            self.docker_version_value.setText("Not installed")
            self.docker_version_detail.setText("Docker CLI not detected")
            for value, detail in (
                (self.docker_running_value, self.docker_running_detail),
                (self.docker_health_value, self.docker_health_detail),
                (self.docker_stopped_value, self.docker_stopped_detail),
            ):
                value.setText("—")
                detail.setText("Unavailable")
            self.container_count.setText("0 shown")
            self._clear_container_details("Docker not installed")
            self.docker_message.setText("Docker was not detected on this system. GoreeCloud Manager will not assume it exists.")
        else:
            self._set_badge(self.docker_badge, "UNAVAILABLE", "statusBadgeWarn")
            self.docker_version_value.setText("Unavailable")
            self.docker_version_detail.setText("Docker daemon not accessible")
            for value, detail in (
                (self.docker_running_value, self.docker_running_detail),
                (self.docker_health_value, self.docker_health_detail),
                (self.docker_stopped_value, self.docker_stopped_detail),
            ):
                value.setText("—")
                detail.setText("Unavailable")
            self.container_count.setText("0 shown")
            self._clear_container_details("Docker unavailable")
            self.docker_message.setText(docker.detail or "Docker is installed but cannot be queried by this SSH user.")

    def _render_netbird(self, overview: InfrastructureOverview):
        nb = overview.netbird
        self.current_netbird = nb
        self.peer_table.setRowCount(0)
        if nb.state == "available":
            management_ok = nb.management.lower().startswith("connected") if nb.management else True
            if not management_ok:
                self._set_badge(self.netbird_badge, "MANAGEMENT ISSUE", "statusBadgeBad")
            elif nb.peers_disconnected:
                self._set_badge(self.netbird_badge, f"{nb.peers_disconnected} OFFLINE", "statusBadgeBad")
            elif nb.peers_connecting:
                self._set_badge(self.netbird_badge, f"{nb.peers_connecting} CONNECTING", "statusBadgeWarn")
            else:
                self._set_badge(self.netbird_badge, "CONNECTED", "statusBadgeGood")
            self.netbird_ip_value.setText(nb.netbird_ip or "—")
            self.netbird_ip_detail.setText(nb.interface_type or "NetBird interface")
            self.netbird_peers_value.setText(f"{nb.peers_connected}/{nb.peers_total}" if nb.peers_total else str(nb.peers_connected))
            peer_parts = [f"{nb.peers_connected} connected"]
            if nb.peers_connecting:
                peer_parts.append(f"{nb.peers_connecting} connecting")
            if nb.peers_disconnected:
                peer_parts.append(f"{nb.peers_disconnected} disconnected")
            self.netbird_peers_detail.setText(" • ".join(peer_parts))
            self.netbird_version_value.setText(nb.cli_version or "Installed")
            self.netbird_version_detail.setText("NetBird CLI")
            self.nb_management.set_text(_compact_netbird_endpoint(nb.management))
            self.nb_signal.set_text(_compact_netbird_endpoint(nb.signal))
            self.nb_interface.set_text(nb.interface_type)
            self.nb_daemon.set_text(nb.daemon_version)
            self.netbird_message.setText("Read-only NetBird peer status. Search/filter peers; the local VPS is excluded from its own remote-peer list.")
            self._apply_peer_filter()
        elif nb.state == "not_installed":
            self._set_badge(self.netbird_badge, "NOT INSTALLED", "statusBadgeNeutral")
            self.netbird_ip_value.setText("Not installed")
            self.netbird_peers_value.setText("—")
            self.netbird_version_value.setText("—")
            for field in (self.nb_management, self.nb_signal, self.nb_interface, self.nb_daemon):
                field.set_text("—")
            self.peer_count_label.setText("0 shown")
            self.netbird_message.setText("NetBird was not detected on this system.")
        else:
            self._set_badge(self.netbird_badge, "UNAVAILABLE", "statusBadgeWarn")
            self.netbird_ip_value.setText("Unavailable")
            self.netbird_peers_value.setText("—")
            self.netbird_version_value.setText("—")
            for field in (self.nb_management, self.nb_signal, self.nb_interface, self.nb_daemon):
                field.set_text("—")
            self.peer_count_label.setText("0 shown")
            self.netbird_message.setText(nb.detail or "NetBird is installed but the agent status could not be read.")

    def _render_infrastructure_error(self, message: str):
        self.current_docker = None
        self.current_netbird = None
        self._set_badge(self.docker_badge, "ERROR", "statusBadgeBad")
        self._set_badge(self.netbird_badge, "ERROR", "statusBadgeBad")
        self.docker_message.setText(message)
        self.netbird_message.setText(message)
        self.container_table.setRowCount(0)
        self.peer_table.setRowCount(0)
        self.container_count.setText("0 shown")
        self.peer_count_label.setText("0 shown")
        self._clear_container_details("Infrastructure unavailable")

    def _update_operational_status(self):
        alerts: list[str] = []
        if self.infrastructure_error:
            alerts.append("infrastructure discovery unavailable")
        if self.infrastructure_last_refresh is not None:
            self.operational_hint.setText(f"Infrastructure checked {self.infrastructure_last_refresh.strftime('%-I:%M:%S %p')}")
        else:
            self.operational_hint.setText("Read-only health summary")

        health = self.current_system_health
        if health is None:
            self.status_system.set_state("CHECKING", "Waiting for system metrics", "statusBadgeNeutral")
        else:
            system_issues: list[str] = []
            critical = health.cpu_percent >= 85 or health.memory_percent >= 85 or health.disk_percent >= 90
            elevated = health.cpu_percent >= 70 or health.memory_percent >= 70 or health.disk_percent >= 75
            if health.failed_units and health.failed_units > 0:
                system_issues.append(f"{health.failed_units} failed systemd unit{'s' if health.failed_units != 1 else ''}")
            if health.disk_percent >= 90:
                system_issues.append(f"disk {health.disk_percent:.0f}%")
            if health.memory_percent >= 85:
                system_issues.append(f"memory {health.memory_percent:.0f}%")
            if health.cpu_percent >= 85:
                system_issues.append(f"CPU {health.cpu_percent:.0f}%")
            if system_issues or critical:
                detail = " • ".join(system_issues) if system_issues else "Resource threshold exceeded"
                self.status_system.set_state("ATTENTION", detail, "statusBadgeBad")
                alerts.extend(system_issues or ["system resource threshold exceeded"])
            elif elevated:
                detail = f"CPU {health.cpu_percent:.0f}% • Memory {health.memory_percent:.0f}% • Disk {health.disk_percent:.0f}%"
                self.status_system.set_state("ELEVATED", detail, "statusBadgeWarn")
                alerts.append("system resource usage elevated")
            else:
                detail = "0 failed units" if health.failed_units == 0 else "Resource levels normal"
                self.status_system.set_state("HEALTHY", detail, "statusBadgeGood")

        docker = self.current_docker
        if docker is None:
            if self.infrastructure_error:
                self.status_docker.set_state("UNAVAILABLE", self.infrastructure_error, "statusBadgeBad")
            else:
                self.status_docker.set_state("CHECKING", "Waiting for Docker discovery", "statusBadgeNeutral")
        elif docker.state == "not_installed":
            self.status_docker.set_state("NOT INSTALLED", "Docker is not present", "statusBadgeNeutral")
        elif docker.state != "available":
            self.status_docker.set_state("UNAVAILABLE", docker.detail or "Docker cannot be queried", "statusBadgeBad")
            alerts.append("Docker unavailable")
        elif docker.unhealthy:
            self.status_docker.set_state(f"{docker.unhealthy} UNHEALTHY", f"{docker.running} running • {docker.stopped} stopped", "statusBadgeBad")
            alerts.append(f"{docker.unhealthy} unhealthy Docker container{'s' if docker.unhealthy != 1 else ''}")
        elif docker.health_starting:
            self.status_docker.set_state(f"{docker.health_starting} STARTING", f"{docker.healthy} healthy", "statusBadgeWarn")
        else:
            self.status_docker.set_state("HEALTHY", f"{docker.running} running • {docker.stopped} stopped", "statusBadgeGood")

        nb = self.current_netbird
        if nb is None:
            if self.infrastructure_error:
                self.status_netbird.set_state("UNAVAILABLE", self.infrastructure_error, "statusBadgeBad")
            else:
                self.status_netbird.set_state("CHECKING", "Waiting for NetBird discovery", "statusBadgeNeutral")
        elif nb.state == "not_installed":
            self.status_netbird.set_state("NOT INSTALLED", "NetBird is not present", "statusBadgeNeutral")
        elif nb.state != "available":
            self.status_netbird.set_state("UNAVAILABLE", nb.detail or "NetBird cannot be queried", "statusBadgeBad")
            alerts.append("NetBird unavailable")
        else:
            management_ok = nb.management.lower().startswith("connected") if nb.management else True
            if not management_ok:
                self.status_netbird.set_state("DISCONNECTED", "Management connection is not healthy", "statusBadgeBad")
                alerts.append("NetBird management disconnected")
            elif nb.peers_disconnected:
                self.status_netbird.set_state("ATTENTION", f"{nb.peers_disconnected} offline • {nb.peers_connected}/{nb.peers_total} connected", "statusBadgeBad")
                alerts.append(f"{nb.peers_disconnected} NetBird peer{'s' if nb.peers_disconnected != 1 else ''} offline")
            elif nb.peers_connecting:
                self.status_netbird.set_state("PARTIAL", f"{nb.peers_connecting} connecting • {nb.peers_connected}/{nb.peers_total} connected", "statusBadgeWarn")
                alerts.append(f"{nb.peers_connecting} NetBird peer{'s' if nb.peers_connecting != 1 else ''} connecting")
            else:
                self.status_netbird.set_state("CONNECTED", f"{nb.peers_connected}/{nb.peers_total} peers connected", "statusBadgeGood")

        if not self.service_cards:
            self.status_services.set_state("NONE CONFIGURED", "No application endpoints are being checked", "statusBadgeNeutral")
        else:
            counts: dict[str, int] = {}
            for card in self.service_cards:
                counts[card.health.state] = counts.get(card.health.state, 0) + 1
            failing = counts.get("offline", 0) + counts.get("degraded", 0)
            reachable = counts.get("reachable", 0)
            checking = counts.get("checking", 0)
            unconfigured = counts.get("unconfigured", 0)
            healthy = counts.get("healthy", 0)
            if failing:
                self.status_services.set_state("ATTENTION", f"{failing} degraded/offline", "statusBadgeBad")
                alerts.append(f"{failing} configured service{'s' if failing != 1 else ''} degraded or offline")
            elif reachable:
                self.status_services.set_state("REACHABLE", f"{reachable} endpoint{'s' if reachable != 1 else ''} returned a client error", "statusBadgeWarn")
            elif checking:
                self.status_services.set_state("CHECKING", f"{checking} check{'s' if checking != 1 else ''} in progress", "statusBadgeNeutral")
            elif healthy:
                detail = f"{healthy} healthy"
                if unconfigured:
                    detail += f" • {unconfigured} not configured"
                self.status_services.set_state("HEALTHY", detail, "statusBadgeGood")
            else:
                self.status_services.set_state("NOT CONFIGURED", f"{unconfigured} service{'s' if unconfigured != 1 else ''} missing a URL", "statusBadgeNeutral")

        if alerts:
            self.attention_label.setText("Needs attention: " + " • ".join(alerts))
            self.attention_label.setStyleSheet("color: #fbbf24;")
        else:
            self.attention_label.setText("No active infrastructure alerts detected by the current read-only checks.")
            self.attention_label.setStyleSheet("color: #91a4c2;")

    def _set_badge(self, widget: QLabel, text: str, class_name: str):
        widget.setText(text)
        widget.setProperty("class", class_name)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def update_service_summary(self):
        counts = {"healthy": 0, "reachable": 0, "degraded": 0, "offline": 0, "unconfigured": 0, "checking": 0}
        for card in self.service_cards:
            counts[card.health.state] = counts.get(card.health.state, 0) + 1
        parts: list[str] = []
        for key, label in (("healthy", "healthy"), ("reachable", "reachable"), ("degraded", "degraded"), ("offline", "offline"), ("unconfigured", "not configured"), ("checking", "checking")):
            if counts[key]:
                parts.append(f"{counts[key]} {label}")
        self.services_summary.setText(" • ".join(parts) if parts else "No services configured")

    def finish_refresh_if_ready(self):
        if self.system_check_pending or self.pending_service_checks or self.infrastructure_check_pending:
            return
        self.refresh_button.setEnabled(True)
        self.last_refresh.setText(f"Updated {datetime.now().strftime('%-I:%M:%S %p')}")

    def set_source_badge(self, text: str, object_name: str):
        self.source_badge.setText(text)
        self.source_badge.setObjectName(object_name)
        self.source_badge.style().unpolish(self.source_badge)
        self.source_badge.style().polish(self.source_badge)

    def open_settings(self, initial_tab: int = 0):
        dialog = SettingsDialog(self.config, self, initial_tab=initial_tab)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.result_config is None:
            return
        try:
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
        self.refresh_all()

    def open_configuration(self):
        config_path = ensure_user_config()
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(config_path)))
        if not opened:
            QMessageBox.information(self, "Configuration file", f"Configuration is stored here:\n\n{config_path}")


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("GoreeCloud Manager")
    app.setStyleSheet(APP_STYLE)
    try:
        config = load_config()
    except Exception as exc:
        QMessageBox.critical(None, "GoreeCloud Manager", f"Could not load configuration:\n\n{exc}")
        return 1
    window = MainWindow(config)
    window.show()
    return app.exec()
