"""Theme definitions for SwiftDownloader."""


DARK_THEME = {
    "name": "dark",
    "bg_primary": "#0D1117",
    "bg_secondary": "#161B22",
    "bg_card": "#1C2333",
    "bg_hover": "#21283B",
    "bg_input": "#0D1117",
    "border": "#30363D",
    "text_primary": "#E6EDF3",
    "text_secondary": "#8B949E",
    "text_muted": "#484F58",
    "accent": "#2F81F7",
    "accent_hover": "#388BFD",
    "accent_light": "rgba(47, 129, 247, 0.15)",
    "success": "#3FB950",
    "warning": "#D29922",
    "error": "#F85149",
    "progress_bg": "#21262D",
    "scrollbar": "#30363D",
    "shadow": "rgba(0, 0, 0, 0.3)",
}

LIGHT_THEME = {
    "name": "light",
    "bg_primary": "#FFFFFF",
    "bg_secondary": "#F6F8FA",
    "bg_card": "#FFFFFF",
    "bg_hover": "#F3F4F6",
    "bg_input": "#FFFFFF",
    "border": "#D0D7DE",
    "text_primary": "#1F2328",
    "text_secondary": "#656D76",
    "text_muted": "#8C959F",
    "accent": "#0969DA",
    "accent_hover": "#0550AE",
    "accent_light": "rgba(9, 105, 218, 0.1)",
    "success": "#1A7F37",
    "warning": "#9A6700",
    "error": "#CF222E",
    "progress_bg": "#E1E4E8",
    "scrollbar": "#C1C8CD",
    "shadow": "rgba(0, 0, 0, 0.1)",
}


def get_theme(name: str) -> dict:
    """Get theme by name."""
    return DARK_THEME if name == "dark" else LIGHT_THEME


def get_stylesheet(theme: dict) -> str:
    """Generate Qt stylesheet from theme."""
    t = theme
    return f"""
    /* === Global === */
    QMainWindow, QDialog {{
        background-color: {t['bg_primary']};
        color: {t['text_primary']};
    }}
    QWidget {{
        color: {t['text_primary']};
        font-family: 'Segoe UI', 'Inter', sans-serif;
        font-size: 13px;
    }}

    /* === Sidebar === */
    #sidebar {{
        background-color: {t['bg_secondary']};
        border-right: 1px solid {t['border']};
    }}
    #sidebarButton {{
        background: transparent;
        color: {t['text_secondary']};
        border: none;
        border-radius: 8px;
        padding: 10px 16px;
        text-align: left;
        font-size: 13px;
        font-weight: 500;
    }}
    #sidebarButton:hover {{
        background-color: {t['bg_hover']};
        color: {t['text_primary']};
    }}
    #sidebarButton[active="true"] {{
        background-color: {t['accent_light']};
        color: {t['accent']};
        font-weight: 600;
    }}

    /* === Cards === */
    #card {{
        background-color: {t['bg_card']};
        border: 1px solid {t['border']};
        border-radius: 12px;
        padding: 16px;
    }}
    #statCard {{
        background-color: {t['bg_card']};
        border: 1px solid {t['border']};
        border-radius: 10px;
        padding: 14px 18px;
    }}

    /* === Buttons === */
    QPushButton {{
        background-color: {t['accent']};
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        padding: 8px 20px;
        font-weight: 600;
        font-size: 13px;
    }}
    QPushButton:hover {{
        background-color: {t['accent_hover']};
    }}
    QPushButton:pressed {{
        background-color: {t['accent']};
        opacity: 0.8;
    }}
    QPushButton:disabled {{
        background-color: {t['bg_hover']};
        color: {t['text_muted']};
    }}
    QPushButton#secondaryBtn {{
        background-color: transparent;
        color: {t['text_primary']};
        border: 1px solid {t['border']};
    }}
    QPushButton#secondaryBtn:hover {{
        background-color: {t['bg_hover']};
    }}
    QPushButton#dangerBtn {{
        background-color: {t['error']};
    }}
    QPushButton#dangerBtn:hover {{
        background-color: #DA3633;
    }}

    /* === Input === */
    QLineEdit, QSpinBox, QComboBox {{
        background-color: {t['bg_input']};
        color: {t['text_primary']};
        border: 1px solid {t['border']};
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 13px;
    }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
        border-color: {t['accent']};
    }}
    QComboBox::drop-down {{
        border: none;
        padding-right: 8px;
    }}

    /* === Table === */
    QTableWidget {{
        background-color: {t['bg_primary']};
        border: 1px solid {t['border']};
        border-radius: 8px;
        gridline-color: {t['border']};
        selection-background-color: {t['accent_light']};
    }}
    QTableWidget::item {{
        padding: 8px;
        border-bottom: 1px solid {t['border']};
    }}
    QHeaderView::section {{
        background-color: {t['bg_secondary']};
        color: {t['text_secondary']};
        border: none;
        border-bottom: 1px solid {t['border']};
        padding: 8px 12px;
        font-weight: 600;
        font-size: 12px;
        text-transform: uppercase;
    }}

    /* === Progress Bar === */
    QProgressBar {{
        background-color: {t['progress_bg']};
        border: none;
        border-radius: 4px;
        text-align: center;
        height: 8px;
        font-size: 0px;
    }}
    QProgressBar::chunk {{
        background-color: {t['accent']};
        border-radius: 4px;
    }}

    /* === Scrollbar === */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {t['scrollbar']};
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 8px;
    }}
    QScrollBar::handle:horizontal {{
        background: {t['scrollbar']};
        border-radius: 4px;
    }}

    /* === Menu === */
    QMenu {{
        background-color: {t['bg_card']};
        border: 1px solid {t['border']};
        border-radius: 8px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 8px 24px;
        border-radius: 4px;
    }}
    QMenu::item:selected {{
        background-color: {t['accent_light']};
        color: {t['accent']};
    }}
    QMenu::separator {{
        height: 1px;
        background: {t['border']};
        margin: 4px 8px;
    }}

    /* === Tab Widget === */
    QTabWidget::pane {{
        border: 1px solid {t['border']};
        border-radius: 8px;
        background: {t['bg_primary']};
    }}
    QTabBar::tab {{
        background: transparent;
        color: {t['text_secondary']};
        padding: 10px 20px;
        border-bottom: 2px solid transparent;
        font-weight: 500;
    }}
    QTabBar::tab:selected {{
        color: {t['accent']};
        border-bottom: 2px solid {t['accent']};
    }}

    /* === Tooltips === */
    QToolTip {{
        background-color: {t['bg_card']};
        color: {t['text_primary']};
        border: 1px solid {t['border']};
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 12px;
    }}

    /* === Labels === */
    #titleLabel {{
        font-size: 20px;
        font-weight: 700;
        color: {t['text_primary']};
    }}
    #subtitleLabel {{
        font-size: 14px;
        color: {t['text_secondary']};
    }}
    #statValue {{
        font-size: 24px;
        font-weight: 700;
        color: {t['text_primary']};
    }}
    #statLabel {{
        font-size: 12px;
        color: {t['text_secondary']};
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}

    /* === Checkbox & Radio === */
    QCheckBox, QRadioButton {{
        spacing: 8px;
        color: {t['text_primary']};
    }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 18px;
        height: 18px;
    }}

    /* === Group Box === */
    QGroupBox {{
        border: 1px solid {t['border']};
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 24px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 8px;
        color: {t['text_secondary']};
    }}
    """
