from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication


APPEARANCE_VALUES = ("system", "light", "dark")


@dataclass(frozen=True)
class ThemeTokens:
    canvas: str
    surface: str
    surface_alt: str
    surface_muted: str
    border: str
    border_strong: str
    text: str
    text_strong: str
    muted: str
    subtle: str
    primary: str
    primary_hover: str
    primary_soft: str
    primary_border: str
    success: str
    success_soft: str
    success_border: str
    warning: str
    warning_soft: str
    warning_border: str
    danger: str
    danger_soft: str
    danger_border: str
    neutral_soft: str
    neutral_border: str
    selection: str
    scrollbar: str
    scrollbar_hover: str


DARK_TOKENS = ThemeTokens(
    canvas="#0b1120",
    surface="#121a2c",
    surface_alt="#0f1729",
    surface_muted="#11192a",
    border="#22304a",
    border_strong="#32415e",
    text="#e5eefc",
    text_strong="#f8fbff",
    muted="#91a4c2",
    subtle="#8193b0",
    primary="#1d4ed8",
    primary_hover="#2563eb",
    primary_soft="#172554",
    primary_border="#1d4ed8",
    success="#4ade80",
    success_soft="#052e16",
    success_border="#15803d",
    warning="#fbbf24",
    warning_soft="#422006",
    warning_border="#a16207",
    danger="#fb7185",
    danger_soft="#4c0519",
    danger_border="#be123c",
    neutral_soft="#1e293b",
    neutral_border="#475569",
    selection="#1d4ed8",
    scrollbar="#334155",
    scrollbar_hover="#475569",
)


LIGHT_TOKENS = ThemeTokens(
    canvas="#f4f7fb",
    surface="#ffffff",
    surface_alt="#f8fafc",
    surface_muted="#eef2f7",
    border="#d9e1ec",
    border_strong="#b8c5d6",
    text="#243247",
    text_strong="#0f172a",
    muted="#61728a",
    subtle="#718198",
    primary="#1d4ed8",
    primary_hover="#1e40af",
    primary_soft="#dbeafe",
    primary_border="#3b82f6",
    success="#15803d",
    success_soft="#dcfce7",
    success_border="#22c55e",
    warning="#a16207",
    warning_soft="#fef3c7",
    warning_border="#d97706",
    danger="#be123c",
    danger_soft="#ffe4e6",
    danger_border="#e11d48",
    neutral_soft="#e2e8f0",
    neutral_border="#94a3b8",
    selection="#2563eb",
    scrollbar="#a8b5c5",
    scrollbar_hover="#7c8da3",
)


def normalize_appearance(value: str | None) -> str:
    normalized = str(value or "system").strip().casefold()
    return normalized if normalized in APPEARANCE_VALUES else "system"


def resolve_appearance(preference: str, app: QGuiApplication | None = None) -> str:
    preference = normalize_appearance(preference)
    if preference != "system":
        return preference

    app = app or QGuiApplication.instance()
    if app is not None and app.styleHints().colorScheme() == Qt.ColorScheme.Dark:
        return "dark"
    return "light"


def theme_tokens(preference: str, app: QGuiApplication | None = None) -> ThemeTokens:
    return DARK_TOKENS if resolve_appearance(preference, app) == "dark" else LIGHT_TOKENS


def semantic_color(preference: str, role: str, app: QGuiApplication | None = None) -> str:
    tokens = theme_tokens(preference, app)
    allowed = {"primary", "success", "warning", "danger", "muted", "text"}
    return getattr(tokens, role if role in allowed else "text")


def stylesheet(preference: str, app: QGuiApplication | None = None) -> str:
    t = theme_tokens(preference, app)
    return f"""
QMainWindow, QDialog, QWidget#root, QWidget#scrollBody, QWidget#scrollViewport,
QWidget#settingsBody, QWidget#settingsViewport {{
    background: {t.canvas};
    color: {t.text};
}}
QMenuBar, QMenu {{
    background: {t.surface};
    color: {t.text};
    border-color: {t.border};
}}
QMenuBar::item:selected, QMenu::item:selected {{
    background: {t.primary_soft};
    color: {t.text_strong};
}}
QLabel#title {{ color: {t.text_strong}; font-size: 29px; font-weight: 700; }}
QLabel#dialogTitle {{ color: {t.text_strong}; font-size: 22px; font-weight: 700; }}
QLabel#subtitle, QLabel.muted {{ color: {t.muted}; font-size: 13px; }}
QLabel.formLabel {{ color: {t.text}; font-size: 12px; font-weight: 600; }}
QLabel#sectionTitle {{ color: {t.text_strong}; font-size: 19px; font-weight: 700; }}
QLabel#sourceName {{ color: {t.text_strong}; font-size: 15px; font-weight: 700; }}
QLabel#sourceBadgeLocal, QLabel#sourceBadgeSsh, QLabel#sourceBadgeError {{
    border-radius: 10px; padding: 4px 9px; font-size: 11px; font-weight: 700;
}}
QLabel#sourceBadgeLocal {{ color: {t.primary}; background: {t.primary_soft}; border: 1px solid {t.primary_border}; }}
QLabel#sourceBadgeSsh {{ color: {t.success}; background: {t.success_soft}; border: 1px solid {t.success_border}; }}
QLabel#sourceBadgeError {{ color: {t.danger}; background: {t.danger_soft}; border: 1px solid {t.danger_border}; }}
QFrame.card, QFrame#sourceCard, QFrame.settingsCard {{
    background: {t.surface}; border: 1px solid {t.border}; border-radius: 14px;
}}
QFrame.card:hover {{ border: 1px solid {t.primary_border}; }}
QFrame#sourceCard {{ background: {t.surface_alt}; }}
QLabel.metricLabel {{ color: {t.muted}; font-size: 12px; }}
QLabel.metricValue {{ color: {t.text_strong}; font-size: 22px; font-weight: 700; }}
QLabel.metricDetail {{ color: {t.muted}; font-size: 11px; }}
QLabel.metricStatusNormal {{ color: {t.success}; font-size: 11px; font-weight: 700; }}
QLabel.metricStatusWarning {{ color: {t.warning}; font-size: 11px; font-weight: 700; }}
QLabel.metricStatusCritical {{ color: {t.danger}; font-size: 11px; font-weight: 700; }}
QLabel.infoLabel {{ color: {t.subtle}; font-size: 11px; }}
QLabel.infoValue {{ color: {t.text_strong}; font-size: 13px; font-weight: 600; }}
QFrame#detailsCard {{ background: {t.surface_alt}; border: 1px solid {t.border}; border-radius: 14px; }}
QLabel.serviceName {{ color: {t.text_strong}; font-size: 16px; font-weight: 700; }}
QLabel.serviceDescription {{ color: {t.muted}; font-size: 12px; }}
QLabel.statusHealthy {{ color: {t.success}; font-weight: 700; }}
QLabel.statusReachable {{ color: {t.primary}; font-weight: 700; }}
QLabel.statusDegraded, QLabel.statusUnknown {{ color: {t.warning}; font-weight: 700; }}
QLabel.statusOffline {{ color: {t.danger}; font-weight: 700; }}
QPushButton {{
    background: {t.primary}; border: none; border-radius: 9px; color: #ffffff;
    padding: 8px 12px; font-weight: 600;
}}
QPushButton:hover {{ background: {t.primary_hover}; }}
QPushButton:disabled {{ background: {t.neutral_soft}; color: {t.muted}; }}
QPushButton.secondary {{ background: {t.surface_muted}; border: 1px solid {t.border_strong}; color: {t.text}; }}
QPushButton.secondary:hover {{ background: {t.primary_soft}; }}
QPushButton.danger {{ background: {t.danger_soft}; border: 1px solid {t.danger_border}; color: {t.danger}; }}
QPushButton.danger:hover {{ background: {t.danger_soft}; }}
QFrame#emptyState {{ background: {t.surface_alt}; border: 1px dashed {t.border_strong}; border-radius: 14px; }}
QLabel#emptyTitle {{ color: {t.text_strong}; font-size: 16px; font-weight: 700; }}
QProgressBar {{
    background: {t.surface_muted}; border: 1px solid {t.border}; border-radius: 5px;
    height: 10px; text-align: center;
}}
QProgressBar::chunk {{ background: {t.primary_border}; border-radius: 4px; }}
QLineEdit, QComboBox, QSpinBox {{
    background: {t.surface_alt}; color: {t.text}; border: 1px solid {t.border_strong};
    border-radius: 8px; padding: 7px 9px; min-height: 20px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1px solid {t.primary_border}; }}
QComboBox QAbstractItemView {{
    background: {t.surface}; color: {t.text}; border: 1px solid {t.border_strong};
    selection-background-color: {t.selection}; selection-color: #ffffff;
}}
QCheckBox {{ color: {t.text}; spacing: 7px; }}
QTabWidget::pane {{ border: 1px solid {t.border}; border-radius: 10px; top: -1px; }}
QTabBar::tab {{
    background: {t.surface_muted}; color: {t.muted}; border: 1px solid {t.border}; padding: 8px 16px;
}}
QTabBar::tab:selected {{ background: {t.primary_soft}; color: {t.text_strong}; border-bottom-color: {t.primary_soft}; }}
QScrollArea {{ border: none; background: {t.canvas}; }}
QScrollBar:vertical {{ background: {t.surface_alt}; width: 11px; margin: 0; border: none; }}
QScrollBar::handle:vertical {{ background: {t.scrollbar}; min-height: 32px; border-radius: 5px; }}
QScrollBar::handle:vertical:hover {{ background: {t.scrollbar_hover}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QTableWidget {{
    background: {t.surface_alt}; color: {t.text}; border: 1px solid {t.border}; border-radius: 10px;
    gridline-color: {t.border}; alternate-background-color: {t.surface_muted};
    selection-background-color: {t.selection}; selection-color: #ffffff;
}}
QHeaderView::section {{
    background: {t.surface}; color: {t.text}; border: none; border-bottom: 1px solid {t.border_strong};
    padding: 8px; font-weight: 600;
}}
QTableCornerButton::section {{ background: {t.surface}; border: none; }}
QLabel.statusBadgeGood, QLabel.statusBadgeWarn, QLabel.statusBadgeBad, QLabel.statusBadgeNeutral {{
    border-radius: 9px; padding: 4px 9px; font-size: 11px; font-weight: 700;
}}
QLabel.statusBadgeGood {{ color: {t.success}; background: {t.success_soft}; border: 1px solid {t.success_border}; }}
QLabel.statusBadgeWarn {{ color: {t.warning}; background: {t.warning_soft}; border: 1px solid {t.warning_border}; }}
QLabel.statusBadgeBad {{ color: {t.danger}; background: {t.danger_soft}; border: 1px solid {t.danger_border}; }}
QLabel.statusBadgeNeutral {{ color: {t.text}; background: {t.neutral_soft}; border: 1px solid {t.neutral_border}; }}
"""


def apply_theme(app: QApplication, preference: str) -> str:
    resolved = resolve_appearance(preference, app)
    app.setStyleSheet(stylesheet(preference, app))
    app.setProperty("goreecloudAppearance", normalize_appearance(preference))
    app.setProperty("goreecloudResolvedAppearance", resolved)
    return resolved
