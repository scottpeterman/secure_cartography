# Secure Cartography v2 - PyQt6 Style Guide

A comprehensive design system and styling reference for the SC2 desktop application.

---

## Table of Contents

1. [Design Philosophy](#design-philosophy)
2. [Theme System Architecture](#theme-system-architecture)
3. [Color Palettes](#color-palettes)
4. [Typography](#typography)
5. [Spacing & Layout](#spacing--layout)
6. [Component Patterns](#component-patterns)
7. [QSS Styling Guide](#qss-styling-guide)
8. [Known Issues & Fixes](#known-issues--fixes)
9. [Widget Reference](#widget-reference)
10. [Code Patterns](#code-patterns)

---

## Design Philosophy

### Core Principles

1. **Dark-first design** - Primary themes (Cyber, Dark) assume dark backgrounds with light text. Light theme is provided for accessibility and preference.

2. **Accent-driven identity** - Each theme has a distinct accent color that defines its personality:
   - Cyber: Electric cyan (`#00ffff`) - technical, futuristic
   - Dark: Elegant gold (`#d4af37`) - professional, refined
   - Light: Professional blue (`#2563eb`) - clean, corporate

3. **Consistent hierarchy** - Background colors follow a predictable depth pattern:
   - Primary → Secondary → Tertiary (progressively lighter in dark themes)
   - Creates natural visual layering without explicit borders everywhere

4. **Subtle feedback** - Hover and focus states use border color changes and subtle background shifts rather than dramatic transformations.

5. **QSS-first, palette-fallback** - Style via QSS where possible, but use QPalette for widgets that resist stylesheet control.

---

## Theme System Architecture

### ThemeColors Dataclass

All theme colors are defined in a `ThemeColors` dataclass with semantic naming:

```python
@dataclass
class ThemeColors:
    # Background hierarchy (dark → light in dark themes)
    bg_primary: str      # Main window background
    bg_secondary: str    # Panel backgrounds
    bg_tertiary: str     # Nested elements, table headers
    bg_input: str        # Input field backgrounds
    bg_hover: str        # Hover state backgrounds
    bg_selected: str     # Selected item backgrounds
    bg_disabled: str     # Disabled widget backgrounds
    
    # Accent colors
    accent: str          # Primary accent (buttons, highlights)
    accent_dim: str      # Dimmed accent (gradients, disabled)
    accent_hover: str    # Accent on hover
    accent_pressed: str  # Accent when pressed
    accent_danger: str   # Error/destructive actions
    accent_success: str  # Success states
    accent_warning: str  # Warnings
    accent_info: str     # Informational highlights
    
    # Text hierarchy
    text_primary: str    # Main text
    text_secondary: str  # Labels, descriptions
    text_muted: str      # Hints, timestamps, placeholders
    text_disabled: str   # Disabled text
    text_accent: str     # Accent-colored text
    text_on_accent: str  # Text on accent backgrounds
    
    # Borders
    border_primary: str   # Focused/active borders
    border_secondary: str # Panel borders
    border_dim: str       # Subtle borders
    border_hover: str     # Hover state borders
    
    # Scrollbar
    scrollbar_bg: str
    scrollbar_handle: str
    scrollbar_hover: str
    
    # Metadata
    name: str
    is_dark: bool
```

### ThemeManager Class

Central controller for theme state:

```python
theme_manager = ThemeManager(ThemeName.CYBER)

# Access current theme
colors = theme_manager.theme
stylesheet = theme_manager.stylesheet

# Switch themes
theme_manager.set_theme(ThemeName.DARK)
app.setStyleSheet(theme_manager.stylesheet)

# Query specific colors
accent = theme_manager.get_color("accent")
```

---

## Color Palettes

### Cyber Theme (Default)

| Role | Color | Hex | Usage |
|------|-------|-----|-------|
| Primary Background | ![#0a0a0f](https://via.placeholder.com/16/0a0a0f/0a0a0f) | `#0a0a0f` | Main window |
| Secondary Background | ![#12121a](https://via.placeholder.com/16/12121a/12121a) | `#12121a` | Panels, cards |
| Tertiary Background | ![#1a1a25](https://via.placeholder.com/16/1a1a25/1a1a25) | `#1a1a25` | Headers, nested |
| Input Background | ![#0d1a1a](https://via.placeholder.com/16/0d1a1a/0d1a1a) | `#0d1a1a` | Text fields |
| Hover | ![#0f2626](https://via.placeholder.com/16/0f2626/0f2626) | `#0f2626` | Hover states |
| Selected | ![#0a3333](https://via.placeholder.com/16/0a3333/0a3333) | `#0a3333` | Selected items |
| Accent | ![#00ffff](https://via.placeholder.com/16/00ffff/00ffff) | `#00ffff` | Primary accent |
| Accent Dim | ![#00b3b3](https://via.placeholder.com/16/00b3b3/00b3b3) | `#00b3b3` | Gradient end |
| Danger | ![#ff0055](https://via.placeholder.com/16/ff0055/ff0055) | `#ff0055` | Errors, delete |
| Success | ![#00ff88](https://via.placeholder.com/16/00ff88/00ff88) | `#00ff88` | Success states |
| Warning | ![#ffaa00](https://via.placeholder.com/16/ffaa00/ffaa00) | `#ffaa00` | Warnings |
| Text Primary | ![#e0f7ff](https://via.placeholder.com/16/e0f7ff/e0f7ff) | `#e0f7ff` | Main text |
| Text Secondary | ![#88c8d4](https://via.placeholder.com/16/88c8d4/88c8d4) | `#88c8d4` | Labels |
| Text Muted | ![#5a8a94](https://via.placeholder.com/16/5a8a94/5a8a94) | `#5a8a94` | Hints |
| Border Dim | ![#1a3a3a](https://via.placeholder.com/16/1a3a3a/1a3a3a) | `#1a3a3a` | Subtle borders |
| Border Hover | ![#00cccc](https://via.placeholder.com/16/00cccc/00cccc) | `#00cccc` | Hover borders |

### Dark Theme

Gold accent (`#d4af37`) on pure black (`#000000`). Professional, elegant.

### Light Theme

Blue accent (`#2563eb`) on white (`#ffffff`). Clean, corporate-friendly.

---

## Typography

### Font Stack

```css
font-family: "Segoe UI", "SF Pro Display", -apple-system, "Helvetica Neue", sans-serif;
```

### Monospace (Code/Logs)

```css
font-family: "JetBrains Mono", "Cascadia Code", "Fira Code", "Consolas", monospace;
```

### Size Scale

| Use | Size | Weight |
|-----|------|--------|
| Body text | 13px | 400 |
| Small/captions | 11px | 400 |
| Code | 12px | 400 |
| Section titles | 11px | 600, uppercase |
| Headings | 18px | 700 |
| Subheadings | 14px | 500 |

### Letter Spacing

- Headings: `2px` absolute spacing
- Section titles (uppercase): `1px` spacing
- Body text: Normal

---

## Spacing & Layout

### Base Unit

8px grid system. All spacing should be multiples of 8px.

### Standard Spacing

| Name | Value | Usage |
|------|-------|-------|
| xs | 4px | Tight spacing, icon gaps |
| sm | 8px | Related element spacing |
| md | 12px | Standard padding |
| lg | 16px | Section spacing |
| xl | 24px | Major section breaks |
| xxl | 32px | Card padding, major gaps |

### Border Radius

| Element | Radius |
|---------|--------|
| Buttons, inputs | 6px |
| Cards, dialogs | 12px |
| Small elements (tags) | 4px |
| Circular | 50% |

### Common Patterns

```python
# Card/panel padding
card_layout.setContentsMargins(32, 24, 32, 24)

# Form field spacing
form_layout.setSpacing(10)

# Button padding
padding: 8px 16px;  # Standard
padding: 14px 20px; # Large/primary
```

---

## Component Patterns

### Buttons

**Standard Button**
```css
QPushButton {
    background-color: {bg_tertiary};
    border: 1px solid {border_dim};
    border-radius: 6px;
    padding: 8px 16px;
    color: {text_primary};
    font-weight: 500;
}
```

**Primary Button** (gradient accent)
```css
QPushButton#primary {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 {accent_dim},
        stop:1 {accent}
    );
    border: 1px solid {accent};
    color: {text_on_accent};
    font-weight: 600;
}
```

**Danger Button** (outline style)
```css
QPushButton#danger {
    background-color: transparent;
    border: 1px solid {accent_danger};
    color: {accent_danger};
}
QPushButton#danger:hover {
    background-color: {accent_danger};
    color: white;
}
```

### Input Fields

```css
QLineEdit {
    background-color: {bg_input};
    border: 1px solid {border_dim};
    border-radius: 6px;
    padding: 8px 12px;
    color: {text_primary};
}
QLineEdit:focus {
    border-color: {accent};
}
```

### Cards/Panels

```css
QFrame#card {
    background-color: {bg_secondary};
    border: 1px solid {border_dim};
    border-radius: 12px;
    padding: 16px;
}
QFrame#card:hover {
    border-color: {border_hover};
}
```

### Tables

```css
QTableView {
    background-color: {bg_secondary};
    alternate-background-color: {bg_tertiary};
    gridline-color: {border_dim};
    border: 1px solid {border_dim};
    border-radius: 8px;
}
QHeaderView::section {
    background-color: {bg_tertiary};
    color: {text_secondary};
    font-weight: 600;
    text-transform: uppercase;
    border: none;
    border-bottom: 1px solid {border_dim};
    padding: 10px 12px;
}
```

---

## QSS Styling Guide

### Selector Specificity

QSS follows CSS-like specificity but with quirks:

```css
/* Base widget - lowest specificity */
QPushButton { }

/* Object name - higher specificity */
QPushButton#primary { }

/* Property selector */
QPushButton[primary="true"] { }

/* Child selector */
QComboBox QAbstractItemView { }

/* Pseudo-states */
QPushButton:hover { }
QPushButton:pressed { }
QPushButton:disabled { }
```

### Object Names for Variants

Use `setObjectName()` for style variants:

```python
button = QPushButton("Delete")
button.setObjectName("danger")  # Matches QPushButton#danger
```

### Viewport Styling

Many scrollable widgets have an internal viewport that needs explicit styling:

```css
QTextEdit::viewport {
    background-color: {bg_input};
}
QScrollArea::viewport {
    background-color: transparent;
}
QTableView::viewport {
    background-color: {bg_secondary};
}
```

### Sub-controls

Qt widgets have sub-controls that can be styled:

```css
/* Scrollbar parts */
QScrollBar::handle:vertical { }
QScrollBar::add-line:vertical { }
QScrollBar::sub-line:vertical { }

/* ComboBox parts */
QComboBox::drop-down { }
QComboBox::down-arrow { }

/* SpinBox parts */
QSpinBox::up-button { }
QSpinBox::down-button { }

/* Tab parts */
QTabBar::tab { }
QTabBar::close-button { }
```

---

## Known Issues & Fixes

### 1. QComboBox Popup White Frame

**Problem:** The dropdown popup is a separate top-level window. QSS can't style the native window container, resulting in a white frame.

**Solution:** Use `StyledComboBox` class that overrides `showPopup()`:

```python
from themes import StyledComboBox

combo = StyledComboBox()
combo.addItems(["Option 1", "Option 2"])
combo.set_theme_colors(theme_manager.theme)

# When theme changes:
combo.set_theme_colors(new_theme)
```

**Technical details:** The fix applies `FramelessWindowHint`, `WA_TranslucentBackground`, and palette colors to the popup container at show time.

---

### 2. QCompleter Popup

**Problem:** Autocomplete popups have the same issue as QComboBox.

**Solution:** Style the popup after setting the completer:

```python
def fix_completer_popup(line_edit, theme):
    completer = line_edit.completer()
    if not completer:
        return
    
    popup = completer.popup()
    if popup:
        # Apply palette
        palette = popup.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(theme.bg_secondary))
        palette.setColor(QPalette.ColorRole.Text, QColor(theme.text_primary))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(theme.bg_selected))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(theme.accent))
        popup.setPalette(palette)
        
        # Apply stylesheet
        popup.setStyleSheet(f"""
            QListView {{
                background-color: {theme.bg_secondary};
                border: 1px solid {theme.border_dim};
                border-radius: 6px;
                padding: 4px;
            }}
            QListView::item {{
                padding: 6px 12px;
                border-radius: 4px;
            }}
            QListView::item:hover {{
                background-color: {theme.bg_hover};
            }}
            QListView::item:selected {{
                background-color: {theme.bg_selected};
                color: {theme.accent};
            }}
        """)
```

---

### 3. QCalendarWidget in QDateEdit

**Problem:** Calendar popup is a complex widget with multiple sub-widgets.

**Solution:** Comprehensive QSS plus navigation button fixes:

```css
QCalendarWidget {
    background-color: {bg_secondary};
}
QCalendarWidget QToolButton {
    background-color: {bg_tertiary};
    color: {text_primary};
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
}
QCalendarWidget QMenu {
    background-color: {bg_secondary};
    border: 1px solid {border_dim};
}
QCalendarWidget QSpinBox {
    background-color: {bg_input};
    border: 1px solid {border_dim};
}
QCalendarWidget QTableView {
    background-color: {bg_secondary};
    selection-background-color: {accent};
    selection-color: {text_on_accent};
}
```

---

### 4. QHeaderView Corner Widget

**Problem:** The corner between row and column headers may not style.

**Solution:** Explicit corner styling:

```css
QTableView QTableCornerButton::section {
    background-color: {bg_tertiary};
    border: none;
    border-bottom: 1px solid {border_dim};
    border-right: 1px solid {border_dim};
}
```

Or programmatically:

```python
corner = table.findChild(QAbstractButton)
if corner:
    corner.setStyleSheet(f"background-color: {theme.bg_tertiary};")
```

---

### 5. QMessageBox Native Buttons (macOS)

**Problem:** On macOS, QMessageBox may use native buttons that ignore QSS.

**Solution:** Force non-native dialogs:

```python
msg = QMessageBox()
msg.setStyleSheet(app_stylesheet)

# Or globally:
app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
```

---

### 6. Cell Editors in QTableView

**Problem:** When editing a cell, the QLineEdit may not inherit theme.

**Solution:** Set a styled item delegate:

```python
class ThemedDelegate(QStyledItemDelegate):
    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
    
    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            editor.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {self.theme.bg_input};
                    color: {self.theme.text_primary};
                    border: 2px solid {self.theme.accent};
                    padding: 2px 4px;
                }}
            """)
        return editor

table.setItemDelegate(ThemedDelegate(theme))
```

---

### 7. QToolTip Platform Inconsistency

**Problem:** Tooltips can look different across platforms.

**Solution:** QSS usually works, but add palette fallback:

```python
def set_tooltip_style(app, theme):
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(theme.bg_tertiary))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(theme.text_primary))
    app.setPalette(palette)
```

---

### 8. QMenu Tearoff Handles

**Problem:** Tearoff menus may show unstyled handles.

**Solution:** Disable tearoff or style explicitly:

```python
menu.setTearOffEnabled(False)

# Or style it:
# QMenu::tearoff { background-color: {bg_tertiary}; }
```

---

## Widget Reference

### Widgets Fully Styled by QSS

These widgets work well with pure QSS:

- `QWidget`, `QFrame`, `QDialog`, `QMainWindow`
- `QLabel`
- `QLineEdit`, `QTextEdit`, `QPlainTextEdit`
- `QPushButton`, `QToolButton`
- `QCheckBox`, `QRadioButton`
- `QGroupBox`
- `QTabWidget`, `QTabBar`
- `QScrollBar`
- `QProgressBar`
- `QSlider`
- `QSpinBox`, `QDoubleSpinBox`
- `QMenu`, `QMenuBar`
- `QToolBar`, `QStatusBar`
- `QSplitter`

### Widgets Requiring Extra Attention

| Widget | Issue | Solution |
|--------|-------|----------|
| `QComboBox` | Popup container | `StyledComboBox` class |
| `QCompleter` | Popup styling | `fix_completer_popup()` |
| `QDateEdit` / `QCalendarWidget` | Calendar popup | Comprehensive QSS + palette |
| `QTableView` / `QTreeView` | Corner button, cell editors | Corner QSS + ThemedDelegate |
| `QMessageBox` | Native buttons (macOS) | `AA_DontUseNativeDialogs` |
| `QFileDialog` | Fully native on most platforms | Accept platform styling |
| `QColorDialog` | Partially native | Limited styling possible |
| `QFontDialog` | Partially native | Limited styling possible |

### Widgets Best Left Native

Some dialogs should retain native appearance for user familiarity:

- `QFileDialog` - Users expect system file browser
- `QColorDialog` - Platform color pickers are usually better
- `QPrintDialog` - System print dialogs have necessary features

---

## Code Patterns

### Theme-Aware Widget Creation

```python
class ThemedWidget(QWidget):
    """Base class for theme-aware widgets."""
    
    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._setup_ui()
        self._apply_theme()
    
    def _setup_ui(self):
        """Override to build UI."""
        pass
    
    def _apply_theme(self):
        """Override to apply theme-specific styling."""
        theme = self.theme_manager.theme
        # Apply styles...
    
    def set_theme(self, theme_name: ThemeName):
        """Change theme and reapply styling."""
        self.theme_manager.set_theme(theme_name)
        self._apply_theme()
```

### Dynamic Theme Switching

```python
def switch_theme(self, theme_name: ThemeName):
    # Update manager
    self.theme_manager.set_theme(theme_name)
    
    # Update application stylesheet
    app = QApplication.instance()
    if app:
        app.setStyleSheet(self.theme_manager.stylesheet)
    
    # Update any widgets needing manual fixes
    self.theme_combo.set_theme_colors(self.theme_manager.theme)
    
    # Emit signal for other components
    self.theme_changed.emit(theme_name)
```

### Applying Named Styles

```python
from themes import apply_widget_style

# Create widget
button = QPushButton("Save")

# Apply named style (sets objectName)
apply_widget_style(button, "primary")

# The QSS selector QPushButton#primary now applies
```

### Conditional Styling Based on Theme

```python
def _apply_theme(self):
    theme = self.theme_manager.theme
    
    # Some values may need theme-specific adjustment
    if theme.is_dark:
        button_text = theme.bg_primary  # Dark text on accent
        shadow_opacity = 0.3
    else:
        button_text = "#ffffff"  # White text on accent
        shadow_opacity = 0.15
    
    self.primary_button.setStyleSheet(f"""
        QPushButton {{
            background-color: {theme.accent};
            color: {button_text};
        }}
    """)
```

### Palette Fallback Pattern

```python
def apply_palette_fallback(widget, theme):
    """Apply palette colors as fallback for stubborn widgets."""
    palette = widget.palette()
    
    palette.setColor(QPalette.ColorRole.Window, QColor(theme.bg_primary))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(theme.text_primary))
    palette.setColor(QPalette.ColorRole.Base, QColor(theme.bg_secondary))
    palette.setColor(QPalette.ColorRole.Text, QColor(theme.text_primary))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(theme.accent))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(theme.text_on_accent))
    palette.setColor(QPalette.ColorRole.Button, QColor(theme.bg_tertiary))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme.text_primary))
    
    widget.setPalette(palette)
```

---

## Appendix: QSS Reference

### Pseudo-States

```css
:hover          /* Mouse over */
:pressed        /* Mouse button down */
:focus          /* Has keyboard focus */
:disabled       /* Widget is disabled */
:enabled        /* Widget is enabled */
:checked        /* Checkbox/radio is checked */
:unchecked      /* Checkbox/radio is unchecked */
:selected       /* Item is selected */
:on             /* Toggle button is on */
:off            /* Toggle button is off */
:open           /* ComboBox is open */
:closed         /* ComboBox is closed */
:editable       /* ComboBox is editable */
:read-only      /* Input is read-only */
:first          /* First item in list */
:last           /* Last item in list */
:horizontal     /* Horizontal orientation */
:vertical       /* Vertical orientation */
```

### Gradient Syntax

```css
/* Linear gradient */
background: qlineargradient(
    x1:0, y1:0, x2:1, y2:1,
    stop:0 #color1,
    stop:0.5 #color2,
    stop:1 #color3
);

/* Radial gradient */
background: qradialgradient(
    cx:0.5, cy:0.5, radius:0.5,
    fx:0.5, fy:0.5,
    stop:0 #color1,
    stop:1 #color2
);

/* Conical gradient */
background: qconicalgradient(
    cx:0.5, cy:0.5, angle:0,
    stop:0 #color1,
    stop:1 #color2
);
```

### Border Shorthand

```css
/* Full border */
border: 1px solid #color;

/* Individual sides */
border-top: 1px solid #color;
border-bottom: none;

/* Radius */
border-radius: 6px;
border-top-left-radius: 6px;
```

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01 | Initial style guide |

---

*Secure Cartography v2 - Network Discovery & Mapping*