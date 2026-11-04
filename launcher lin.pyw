
import sys
import os
for _stream_name in ("stdout", "stderr"):
    if getattr(sys, _stream_name) is None:
        setattr(sys, _stream_name, open(os.devnull, "w", encoding="utf-8"))

from collections.abc import Callable
import hashlib
import json
from pathlib import Path
import queue
import re
import subprocess
import threading
import requests
import minecraft_launcher_lib

try:
    import flet as ft
except ImportError:  
    import tkinter as _tk
    from tkinter import messagebox as _mb
    _root = _tk.Tk()
    _root.withdraw()
    _mb.showerror(
        "Crackrizon Launcher",
        'Flet is not installed.\n\nRun this command and start the launcher again:\n\n'
        '    pip install "flet==0.28.3"',
    )
    sys.exit(1)

if getattr(sys, 'frozen', False):
    APP_ROOT = Path(sys.executable).resolve().parent
else:
    APP_ROOT = Path(__file__).resolve().parent

HORIZON_DIR = APP_ROOT / "horizon-linux-x86_64"
ASSETS_DIR = Path(getattr(sys, "_MEIPASS", APP_ROOT)) / "assets"
APP_ICON_FILE = ASSETS_DIR / "app_icon.png"

# ───────────────────────────── Design tokens ─────────────────────────────
TAGLINE = "Horizon client"          

BG = "#08090E"                     
SIDEBAR = "#0B0C12"                 
PANEL = "#10121A"                   
RAISED = "#171A25"                  
LINE = "#1E2230"                  
LINE_HI = "#2C3144"                 
TEXT = "#EDEFF5"
MUTED = "#8187A0"
FAINT = "#555B73"
ACCENT = "#8B6CFF"
ACCENT_DEEP = "#5F42E8"
ACCENT_SOFT = "#B7A6FF"
DAWN = "#FFB46B"                    
OK = "#5EE3A1"
WARN = "#F5B85C"
DANGER = "#FF7A85"

TONES = {"ok": OK, "warn": WARN, "danger": DANGER, "accent": ACCENT_SOFT}

CUSTOM_FONT_FILE = ASSETS_DIR / "Inter.ttf"          # необязательный шрифт
FONT = "Inter" if CUSTOM_FONT_FILE.is_file() else "sans-serif"
MONO = "monospace"

HERO_H = 340
GROUND_H = 60
MAX_LOG_LINES = 2000

W = ft.FontWeight
EASE = ft.AnimationCurve.EASE_OUT_CUBIC


def alpha(color: str, opacity: float) -> str:
    return ft.Colors.with_opacity(opacity, color)


def center() -> ft.Alignment:
    return ft.Alignment(0, 0)


def minecraft_directory():
    return Path.home() / ".minecraft"


def launcher_config_directory():
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home and Path(xdg_config_home).is_absolute():
        return Path(xdg_config_home) / "crackrizon"
    return Path.home() / ".config" / "crackrizon"


def is_valid_offline_name(name):
    return re.fullmatch(r"[A-Za-z0-9_]{1,16}", name) is not None


# ───────────────────────────── UI components ─────────────────────────────
class Btn(ft.Container):
    """Кнопка в трёх вариантах: primary (светящаяся), secondary, ghost, danger."""

    SIZES = {
        "sm": dict(h=36, px=16, fs=13, r=11, icon=16),
        "md": dict(h=42, px=20, fs=13.5, r=13, icon=18),
        "lg": dict(h=60, px=36, fs=16, r=18, icon=22),
    }

    def __init__(self, label, on_click=None, *, icon=None, kind="secondary",
                 size="md", tooltip=None):
        super().__init__()
        s = self.SIZES[size]
        self._kind = kind
        self._cb = on_click
        self._on = True
        self._hot = False
        self._icon = ft.Icon(icon, size=s["icon"]) if icon else None
        self._label = ft.Text(label, size=s["fs"], weight=W.W_600)
        self.content = ft.Row(
            [c for c in (self._icon, self._label) if c is not None],
            spacing=10, tight=True, alignment=ft.MainAxisAlignment.CENTER,
        )
        self.height = s["h"]
        self.padding = ft.padding.symmetric(horizontal=s["px"])
        self.border_radius = s["r"]
        self.alignment = center()
        self.animate = ft.Animation(200, EASE)
        self.animate_scale = ft.Animation(200, EASE)
        self.tooltip = tooltip
        self.on_click = self._clicked
        self.on_hover = self._hovered
        self._style()

    def _style(self):
        kind, on, hot = self._kind, self._on, self._hot and self._on
        bg, border, fg = None, None, TEXT
        self.gradient = None
        self.shadow = None
        self.scale = 1

        if kind == "primary":
            if on:
                self.gradient = ft.LinearGradient(
                    begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1),
                    colors=["#A892FF" if hot else ACCENT, ACCENT_DEEP],
                )
                self.shadow = ft.BoxShadow(
                    blur_radius=46 if hot else 30,
                    color=alpha(ACCENT, 0.55 if hot else 0.35),
                    offset=ft.Offset(0, 10),
                )
                self.scale = 1.03 if hot else 1
                fg = "#FFFFFF"
            else:
                bg, fg = RAISED, FAINT
        elif kind == "secondary":
            if on:
                bg = alpha("#FFFFFF", 0.08 if hot else 0.035)
                border = alpha("#FFFFFF", 0.24 if hot else 0.10)
            else:
                border, fg = LINE, FAINT
        elif kind == "ghost":
            bg = alpha("#FFFFFF", 0.06) if hot else None
            fg = TEXT if hot else (MUTED if on else FAINT)
        elif kind == "danger":
            if on:
                fg = DANGER
                bg = alpha(DANGER, 0.12) if hot else None
                border = alpha(DANGER, 0.5 if hot else 0.28)
            else:
                border, fg = LINE, FAINT

        self.bgcolor = bg
        self.border = ft.border.all(1, border) if border else None
        self._label.color = fg
        if self._icon:
            self._icon.color = fg
        self.ink = on

    def _clicked(self, _e):
        if self._on and self._cb:
            self._cb()

    def _hovered(self, e):
        self._hot = str(e.data).lower() == "true"
        self._style()
        try:
            self.update()
        except Exception:
            pass

    # Изменения без page.update(): его вызывает владелец (одним разом на пачку правок).
    def set_enabled(self, enabled: bool):
        self._on = bool(enabled)
        if not self._on:
            self._hot = False
        self._style()

    def set_label(self, text: str):
        self._label.value = text


class NavItem(ft.Container):
    def __init__(self, icon, tooltip, on_click):
        super().__init__(
            width=48, height=48, border_radius=15, alignment=center(),
            tooltip=tooltip, ink=True, animate=ft.Animation(200, EASE),
        )
        self._icon = ft.Icon(icon, size=22)
        self.content = self._icon
        self._cb = on_click
        self._active = False
        self._hot = False
        self.on_click = lambda _e: self._cb()
        self.on_hover = self._hovered
        self._style()

    def _style(self):
        if self._active:
            self.bgcolor = alpha(ACCENT, 0.16)
            self._icon.color = ACCENT_SOFT
        elif self._hot:
            self.bgcolor = alpha("#FFFFFF", 0.05)
            self._icon.color = TEXT
        else:
            self.bgcolor = None
            self._icon.color = FAINT

    def _hovered(self, e):
        self._hot = str(e.data).lower() == "true"
        self._style()
        try:
            self.update()
        except Exception:
            pass

    def set_active(self, active: bool):
        self._active = active
        self._style()


class WinButton(ft.Container):
    def __init__(self, icon, on_click, danger=False):
        super().__init__(
            width=44, height=32, border_radius=9, alignment=center(),
            ink=True, animate=ft.Animation(150, EASE),
        )
        self._danger = danger
        self._icon = ft.Icon(icon, size=16, color=MUTED)
        self.content = self._icon
        self.on_click = lambda _e: on_click()
        self.on_hover = self._hovered

    def _hovered(self, e):
        hot = str(e.data).lower() == "true"
        if self._danger:
            self.bgcolor = alpha(DANGER, 0.9) if hot else None
            self._icon.color = "#FFFFFF" if hot else MUTED
        else:
            self.bgcolor = alpha("#FFFFFF", 0.07) if hot else None
            self._icon.color = TEXT if hot else MUTED
        try:
            self.update()
        except Exception:
            pass


def hairline():
    return ft.Container(height=1, bgcolor=LINE)


def make_field(**kwargs) -> ft.TextField:
    options = dict(
        text_size=14, color=TEXT, cursor_color=ACCENT,
        filled=True, fill_color=alpha("#FFFFFF", 0.03),
        border_radius=13, border_color=LINE_HI, focused_border_color=ACCENT,
        border_width=1,
        content_padding=ft.padding.symmetric(horizontal=18, vertical=15),
        hint_style=ft.TextStyle(color=FAINT, size=14),
    )
    options.update(kwargs)
    return ft.TextField(**options)


# ───────────────────────────── Launcher ─────────────────────────────
class HorizonLauncher:
    def __init__(self, page: ft.Page):
        self.page = page
        self.events = queue.Queue()
        self.busy = False
        self.offline_profiles_file = launcher_config_directory() / "offline-profiles.json"
        self.current_page = None
        self._log_buffer = []

        self._configure_page()

        try:
            self.lock = json.loads((HORIZON_DIR / "research-lock.json").read_text(encoding="utf-8"))
            self.version = self.lock["minecraft"]["version"]
            self.java_major = self.lock["minecraft"]["java_major"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
            self._fatal(
                "Horizon load error",
                f"Could not find a valid research-lock.json in the Horizon folder.\n\n{error}",
            )
            return

        try:
            if self.offline_profiles_file.exists():
                profile_data = json.loads(self.offline_profiles_file.read_text(encoding="utf-8"))
                profiles = profile_data["profiles"]
                selected_profile = profile_data["selected"]
                if (
                    not isinstance(profiles, list)
                    or not profiles
                    or any(not isinstance(name, str) or not is_valid_offline_name(name) for name in profiles)
                    or len({name.casefold() for name in profiles}) != len(profiles)
                    or selected_profile not in profiles
                ):
                    raise ValueError("Offline profile settings have an invalid format.")
                self.offline_profiles = profiles
            else:
                self.offline_profiles = ["Player"]
                selected_profile = "Player"
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            self._fatal("Profile load error", f"Could not load offline profiles.\n\n{error}")
            return

        self.selected_profile = selected_profile
        self.resources_dir = HORIZON_DIR / ".local" / "horizon-client" / self.version

        self._build_ui()
        self._show_page("home")
        self._refresh_state()
        if self._is_prepared():
            self._set_status("Ready to play", "ok")
        else:
            self._set_status("Click Prepare to download and set up the game automatically", "warn")
        self.page.update()
        threading.Thread(target=self._event_loop, daemon=True).start()

    # ───────────── page / window ─────────────
    def _configure_page(self):
        page = self.page
        page.title = "Crackrizon Launcher"
        page.bgcolor = BG
        page.padding = 0
        page.spacing = 0
        page.theme_mode = ft.ThemeMode.DARK
        if CUSTOM_FONT_FILE.is_file():
            page.fonts = {"Inter": "Inter.ttf"}
        page.theme = self._make_theme()

        win = page.window
        win.width, win.height = 1120, 760
        win.min_width, win.min_height = 980, 660
        win.title_bar_hidden = True
        win.title_bar_buttons_hidden = True
        if APP_ICON_FILE.is_file():
            win.icon = str(APP_ICON_FILE)
        try:
            win.center()
        except Exception:
            pass

    @staticmethod
    def _make_theme():
        base = dict(font_family=FONT, use_material3=True, color_scheme_seed=ACCENT)
        try:
            return ft.Theme(
                **base,
                scrollbar_theme=ft.ScrollbarTheme(
                    thickness=4, radius=8, thumb_color=alpha("#FFFFFF", 0.16),
                ),
                popup_menu_theme=ft.PopupMenuTheme(
                    color=RAISED,
                    shape=ft.RoundedRectangleBorder(radius=16),
                    text_style=ft.TextStyle(color=TEXT, size=13.5),
                ),
            )
        except (TypeError, AttributeError):
            return ft.Theme(**base)

    def _titlebar(self):
        page = self.page

        def minimize():
            page.window.minimized = True
            page.update()

        def maximize():
            page.window.maximized = not page.window.maximized
            page.update()

        def close():
            page.window.close()

        return ft.Row(
            [
                ft.WindowDragArea(content=ft.Container(height=44), expand=True),
                ft.Container(
                    padding=ft.padding.only(right=10),
                    content=ft.Row(
                        [
                            WinButton(ft.Icons.MINIMIZE_ROUNDED, minimize),
                            WinButton(ft.Icons.CROP_SQUARE_ROUNDED, maximize),
                            WinButton(ft.Icons.CLOSE_ROUNDED, close, danger=True),
                        ],
                        spacing=2,
                    ),
                ),
            ],
            spacing=0,
        )

    def _fatal(self, title, message):
        page = self.page
        page.controls.clear()
        card = ft.Container(
            width=520, padding=36, bgcolor=PANEL, border_radius=24,
            border=ft.border.all(1, LINE),
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=30, color=DANGER),
                    ft.Text(title, size=22, weight=W.W_600, color=TEXT),
                    ft.Text(message, size=13.5, color=MUTED, selectable=True),
                    ft.Container(height=6),
                    Btn("Close", lambda: page.window.close(), size="md"),
                ],
                spacing=12, tight=True,
            ),
        )
        page.add(
            ft.Column(
                [self._titlebar(), ft.Container(expand=True, alignment=center(), content=card)],
                spacing=0, expand=True,
            )
        )
        page.update()

    # ───────────── dialogs ─────────────
    def _dialog(self, title, message, actions):
        dlg = ft.AlertDialog(
            modal=True, bgcolor=RAISED,
            shape=ft.RoundedRectangleBorder(radius=22),
            title=ft.Text(title, size=18, weight=W.W_600, color=TEXT),
            content=ft.Container(width=440, content=ft.Text(message, size=13.5, color=MUTED, selectable=True)),
            actions_alignment=ft.MainAxisAlignment.END,
        )
        dlg.actions = [
            ft.TextButton(
                text=label,
                style=ft.ButtonStyle(color=color),
                on_click=lambda _e, cb=callback: (self.page.close(dlg), cb() if cb else None),
            )
            for label, color, callback in actions
        ]
        self.page.open(dlg)

    def _alert(self, title, message):
        self._dialog(title, message, [("OK", ACCENT_SOFT, None)])

    def _confirm(self, title, message, on_yes, yes_label="Confirm", danger=False):
        self._dialog(title, message, [
            ("Cancel", MUTED, None),
            (yes_label, DANGER if danger else ACCENT_SOFT, on_yes),
        ])

    # ───────────── layout ─────────────
    def _build_ui(self):
        self.dir_picker = ft.FilePicker(on_result=self._on_directory_picked)
        self.page.overlay.append(self.dir_picker)

        self.nav = {
            "home": NavItem(ft.Icons.HOME_ROUNDED, "Home", lambda: self._go("home")),
            "settings": NavItem(ft.Icons.SETTINGS_ROUNDED, "Settings", lambda: self._go("settings")),
            "log": NavItem(ft.Icons.TERMINAL_ROUNDED, "Log", lambda: self._go("log")),
        }
        self.side_dot = ft.Container(
            width=9, height=9, border_radius=5, bgcolor=WARN,
            animate=ft.Animation(400, EASE),
        )
        logo = ft.Container(
            width=42, height=42, border_radius=14, alignment=center(),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1), colors=[ACCENT, DAWN],
            ),
            shadow=ft.BoxShadow(blur_radius=26, color=alpha(ACCENT, 0.35), offset=ft.Offset(0, 6)),
            content=ft.Text("C", size=20, weight=W.W_700, color="#FFFFFF"),
        )
        sidebar = ft.Container(
            width=78, bgcolor=SIDEBAR, padding=ft.padding.symmetric(vertical=24),
            border=ft.border.only(right=ft.BorderSide(1, LINE)),
            content=ft.Column(
                [
                    logo,
                    ft.Container(height=22),
                    *self.nav.values(),
                    ft.Container(expand=True),
                    self.side_dot,
                    ft.Container(height=4),
                ],
                spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        self.pages = {
            "home": self._build_home(),
            "settings": self._build_settings(),
            "log": self._build_log(),
        }
        self.host = ft.Container(expand=True)
        self.action_buttons = [
            self.play_button, self.prepare_button,
            self.sounds_button, self.download_libs_button,
        ]

        self.page.add(
            ft.Row(
                [
                    sidebar,
                    ft.Column([self._titlebar(), self.host], spacing=0, expand=True),
                ],
                spacing=0, expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            )
        )

    @staticmethod
    def _page_shell(*controls, scroll=True):
        return ft.Container(
            expand=True,
            padding=ft.padding.only(left=44, right=44, top=2, bottom=32),
            content=ft.Column(
                list(controls), spacing=0, expand=True,
                scroll=ft.ScrollMode.AUTO if scroll else None,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

    @staticmethod
    def _heading(text):
        return ft.Text(text, size=30, weight=W.W_300, color=TEXT,
                       style=ft.TextStyle(letter_spacing=-0.8))

    # ───────────── home ─────────────
    def _build_home(self):
        # — hero —
        self.play_button = Btn("Play", self._play, icon=ft.Icons.PLAY_ARROW_ROUNDED,
                               kind="primary", size="lg")

        self.profile_label = ft.Text(self.selected_profile, size=14.5, weight=W.W_600, color=TEXT)
        self.profile_menu = ft.PopupMenuButton(
            tooltip="Switch profile",
            items=self._profile_menu_items(),
            content=ft.Container(
                height=60, padding=ft.padding.symmetric(horizontal=20), border_radius=18,
                bgcolor=alpha("#FFFFFF", 0.05),
                border=ft.border.all(1, alpha("#FFFFFF", 0.12)),
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.PERSON_ROUNDED, size=20, color=ACCENT_SOFT),
                        ft.Column(
                            [ft.Text("Playing as", size=11, color=alpha("#FFFFFF", 0.45)),
                             self.profile_label],
                            spacing=0, tight=True,
                        ),
                        ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED, size=18, color=MUTED),
                    ],
                    spacing=14, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
        )

        self.status_dot = ft.Container(
            width=8, height=8, border_radius=4, bgcolor=WARN, animate=ft.Animation(300, EASE),
        )
        self.status_text = ft.Text("", size=13.5, color=TEXT, max_lines=1,
                                   overflow=ft.TextOverflow.ELLIPSIS)
        self.progress = ft.ProgressBar(
            value=None, height=2, color=ACCENT_SOFT, bgcolor=ft.Colors.TRANSPARENT, visible=False,
        )

        def layer(**kwargs):
            return ft.Container(left=0, right=0, top=0, bottom=0, **kwargs)

        sun_glow = layer(gradient=ft.RadialGradient(
            center=ft.Alignment(0.62, 0.62), radius=0.95,
            colors=[alpha(DAWN, 0.50), alpha("#FF7A8A", 0.20), alpha(ACCENT, 0.08), ft.Colors.TRANSPARENT],
            stops=[0.0, 0.34, 0.68, 1.0],
        ))
        violet_wash = layer(gradient=ft.RadialGradient(
            center=ft.Alignment(-0.95, -0.2), radius=1.15,
            colors=[alpha(ACCENT, 0.30), ft.Colors.TRANSPARENT],
        ))
        ground = ft.Container(
            left=0, right=0, bottom=0, height=GROUND_H,
            padding=ft.padding.symmetric(horizontal=44),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(0, -1), end=ft.Alignment(0, 1),
                colors=[alpha("#06070B", 0.78), alpha("#06070B", 0.96)],
            ),
            content=ft.Row(
                [self.status_dot, ft.Container(content=self.status_text, expand=True)],
                spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        horizon_line = ft.Container(
            left=0, right=0, bottom=GROUND_H, height=1,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, 0), end=ft.Alignment(1, 0),
                colors=[ft.Colors.TRANSPARENT, alpha(ACCENT_SOFT, 0.35),
                        alpha(DAWN, 0.85), alpha(ACCENT_SOFT, 0.25), ft.Colors.TRANSPARENT],
                stops=[0.0, 0.25, 0.62, 0.85, 1.0],
            ),
        )
        version_pill = ft.Container(
            padding=ft.padding.symmetric(horizontal=14, vertical=7), border_radius=20,
            bgcolor=alpha("#FFFFFF", 0.06), border=ft.border.all(1, alpha("#FFFFFF", 0.10)),
            content=ft.Text(f"Minecraft {self.version}", size=12.5, weight=W.W_500,
                            color=alpha("#FFFFFF", 0.75)),
        )
        hero_content = ft.Container(
            left=0, right=0, top=0, bottom=GROUND_H,
            padding=ft.padding.only(left=44, right=44, top=30, bottom=26),
            content=ft.Column(
                [
                    ft.Column(
                        [
                            version_pill,
                            ft.Container(height=14),
                            ft.Text("Crackrizon", size=62, weight=W.W_200, color="#FFFFFF",
                                    style=ft.TextStyle(letter_spacing=-2.5)),
                            ft.Text(TAGLINE, size=15, color=alpha("#FFFFFF", 0.55)),
                        ],
                        spacing=0, tight=True,
                    ),
                    ft.Row([self.play_button, self.profile_menu], spacing=16,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
        )
        progress_layer = ft.Container(left=0, right=0, bottom=0, content=self.progress)

        hero = ft.Container(
            height=HERO_H, border_radius=26, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            border=ft.border.all(1, LINE),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(0, -1), end=ft.Alignment(0, 1),
                colors=["#0D0E17", "#15112A"],
            ),
            content=ft.Stack(
                [sun_glow, violet_wash, ground, horizon_line, hero_content, progress_layer],
                expand=True,
            ),
        )

        # — components list —
        self.resources_desc = ft.Text("", size=13, color=MUTED)
        self.prepare_button = Btn("Prepare", self._prepare, size="sm")
        self.sounds_button = Btn("Add", self._prepare_sounds, size="sm")
        self.download_libs_button = Btn("Download", self._download_all_libs, size="sm")

        rows = ft.Column(
            [
                self._component_row(ft.Icons.LAYERS_ROUNDED, "Resources",
                                    self.resources_desc, self.prepare_button),
                hairline(),
                self._component_row(
                    ft.Icons.VOLUME_UP_ROUNDED, "Sounds",
                    ft.Text("Copies sounds from the Minecraft folder (~380 MB). "
                            "Available after preparing resources.", size=13, color=MUTED),
                    self.sounds_button),
                hairline(),
                self._component_row(
                    ft.Icons.EXTENSION_ROUNDED, "Libraries",
                    ft.Text("Additional libraries: Vineflower, Jadx, and Java runtime.",
                            size=13, color=MUTED),
                    self.download_libs_button),
            ],
            spacing=0,
        )
        components = ft.Container(
            bgcolor=PANEL, border_radius=22, border=ft.border.all(1, LINE),
            padding=ft.padding.symmetric(vertical=6), content=rows,
        )

        return self._page_shell(
            hero,
            ft.Container(height=30),
            ft.Text("Components", size=16, weight=W.W_600, color=TEXT),
            ft.Container(height=12),
            components,
            ft.Container(height=14),
            ft.Text(
                f"Minecraft {self.version} and all components are downloaded automatically — "
                "the official client is not required.",
                size=12.5, color=FAINT,
            ),
        )

    @staticmethod
    def _component_row(icon, title, description, button):
        tile = ft.Container(
            width=44, height=44, border_radius=14, alignment=center(),
            bgcolor=alpha("#FFFFFF", 0.04), border=ft.border.all(1, LINE),
            content=ft.Icon(icon, size=21, color=ACCENT_SOFT),
        )
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=22, vertical=16),
            content=ft.Row(
                [
                    tile,
                    ft.Column(
                        [ft.Text(title, size=14.5, weight=W.W_600, color=TEXT), description],
                        spacing=3, expand=True,
                    ),
                    button,
                ],
                spacing=18, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _profile_menu_items(self):
        items = [
            ft.PopupMenuItem(
                text=name,
                icon=ft.Icons.CHECK_ROUNDED if name == self.selected_profile
                else ft.Icons.PERSON_OUTLINE_ROUNDED,
                on_click=lambda _e, n=name: self._select_offline_profile(n),
            )
            for name in self.offline_profiles
        ]
        items.append(ft.PopupMenuItem())
        items.append(ft.PopupMenuItem(
            text="Manage profiles", icon=ft.Icons.TUNE_ROUNDED,
            on_click=lambda _e: self._go("settings"),
        ))
        return items

    # ───────────── settings ─────────────
    def _build_settings(self):
        self.minecraft_field = make_field(value=str(minecraft_directory()), expand=True)
        folder_panel = self._panel(
            "Minecraft directory",
            "Folder with the installed Minecraft and its game files.",
            ft.Row(
                [self.minecraft_field,
                 Btn("Browse", self._choose_minecraft_directory,
                     icon=ft.Icons.FOLDER_OPEN_ROUNDED, size="md")],
                spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        self.chips_row = ft.Row(wrap=True, spacing=10, run_spacing=10)
        self.new_profile_field = make_field(
            hint_text="New nickname", max_length=16, counter_text="", width=260,
            on_submit=self._add_offline_profile, on_change=self._clear_profile_error,
        )
        self.remove_offline_profile_button = Btn(
            "Remove", self._remove_offline_profile, kind="danger",
            icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
        )
        profile_panel = self._panel(
            "Offline profiles",
            "Player names for multiplayer servers in offline mode. "
            "No Microsoft account is used. Click a profile to make it active.",
            self.chips_row,
            ft.Container(height=14),
            hairline(),
            ft.Container(height=18),
            ft.Row(
                [
                    self.new_profile_field,
                    Btn("Add profile", self._add_offline_profile,
                        icon=ft.Icons.ADD_ROUNDED, size="md"),
                    ft.Container(expand=True),
                    self.remove_offline_profile_button,
                ],
                spacing=12, vertical_alignment=ft.CrossAxisAlignment.START,
            ),
        )
        self._render_profiles()

        return self._page_shell(
            self._heading("Settings"),
            ft.Container(height=22),
            folder_panel,
            ft.Container(height=18),
            profile_panel,
        )

    @staticmethod
    def _panel(title, subtitle, *body):
        return ft.Container(
            bgcolor=PANEL, border_radius=22, border=ft.border.all(1, LINE), padding=28,
            content=ft.Column(
                [
                    ft.Text(title, size=16, weight=W.W_600, color=TEXT),
                    ft.Text(subtitle, size=13, color=MUTED),
                    ft.Container(height=10),
                    *body,
                ],
                spacing=3,
            ),
        )

    def _render_profiles(self):
        chips = []
        for name in self.offline_profiles:
            selected = name == self.selected_profile
            row = []
            if selected:
                row.append(ft.Icon(ft.Icons.CHECK_ROUNDED, size=16, color=ACCENT_SOFT))
            row.append(ft.Text(name, size=13.5, weight=W.W_600 if selected else W.W_500,
                               color=TEXT if selected else MUTED))
            chips.append(ft.Container(
                padding=ft.padding.symmetric(horizontal=18, vertical=11), border_radius=22,
                bgcolor=alpha(ACCENT, 0.15) if selected else alpha("#FFFFFF", 0.03),
                border=ft.border.all(1, alpha(ACCENT, 0.65) if selected else LINE_HI),
                ink=True, on_click=lambda _e, n=name: self._select_offline_profile(n),
                content=ft.Row(row, spacing=8, tight=True),
            ))
        self.chips_row.controls = chips
        self.profile_label.value = self.selected_profile
        self.profile_menu.items = self._profile_menu_items()
        self.remove_offline_profile_button.set_label(f"Remove {self.selected_profile}")
        self.remove_offline_profile_button.set_enabled(len(self.offline_profiles) > 1)

    def _clear_profile_error(self, _e=None):
        if self.new_profile_field.error_text:
            self.new_profile_field.error_text = None
            self.page.update()

    def _write_offline_profiles(self, profiles, selected):
        self.offline_profiles_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = self.offline_profiles_file.with_suffix(".tmp")
        temporary_file.write_text(
            json.dumps({"profiles": profiles, "selected": selected}, indent=2),
            encoding="utf-8",
        )
        temporary_file.replace(self.offline_profiles_file)

    def _select_offline_profile(self, name):
        if name == self.selected_profile:
            return
        try:
            self._write_offline_profiles(self.offline_profiles, name)
        except OSError as error:
            self._alert("Profile save error",
                        f"Could not save the selected offline profile.\n\n{error}")
            return
        self.selected_profile = name
        self._render_profiles()
        self.page.update()

    def _add_offline_profile(self, _e=None):
        name = (self.new_profile_field.value or "").strip()
        problem = None
        if not is_valid_offline_name(name):
            problem = "Use 1–16 ASCII letters, numbers or underscores."
        elif any(existing.casefold() == name.casefold() for existing in self.offline_profiles):
            problem = "A profile with that name already exists."
        if problem:
            self.new_profile_field.error_text = problem
            self.page.update()
            return

        profiles = [*self.offline_profiles, name]
        try:
            self._write_offline_profiles(profiles, name)
        except OSError as error:
            self._alert("Profile save error", f"Could not save the new offline profile.\n\n{error}")
            return
        self.offline_profiles = profiles
        self.selected_profile = name
        self.new_profile_field.value = ""
        self.new_profile_field.error_text = None
        self._render_profiles()
        self.page.update()

    def _remove_offline_profile(self):
        selected = self.selected_profile
        if len(self.offline_profiles) <= 1:
            return
        self._confirm(
            "Remove profile", f"Remove the profile “{selected}”?",
            lambda: self._do_remove_profile(selected), yes_label="Remove", danger=True,
        )

    def _do_remove_profile(self, selected):
        profiles = [name for name in self.offline_profiles if name != selected]
        next_selected = profiles[0]
        try:
            self._write_offline_profiles(profiles, next_selected)
        except OSError as error:
            self._alert("Profile save error", f"Could not remove the offline profile.\n\n{error}")
            return
        self.offline_profiles = profiles
        self.selected_profile = next_selected
        self._render_profiles()
        self.page.update()

    def _choose_minecraft_directory(self):
        self.dir_picker.get_directory_path(
            dialog_title="Select Minecraft directory",
            initial_directory=self.minecraft_field.value or str(Path.home()),
        )

    def _on_directory_picked(self, e):
        if e.path:
            self.minecraft_field.value = e.path
            self.page.update()

    # ───────────── log ─────────────
    def _build_log(self):
        self.log_view = ft.ListView(expand=True, spacing=3, auto_scroll=True)
        self._append_log("Horizon Launcher is ready.")

        header = ft.Row(
            [
                self._heading("Log"),
                ft.Container(expand=True),
                Btn("Copy", self._copy_log, icon=ft.Icons.CONTENT_COPY_ROUNDED,
                    kind="ghost", size="sm"),
                Btn("Clear", self._clear_log, icon=ft.Icons.DELETE_SWEEP_ROUNDED,
                    kind="ghost", size="sm"),
            ],
            spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        panel = ft.Container(
            expand=True, bgcolor="#090A0F", border_radius=22, border=ft.border.all(1, LINE),
            padding=ft.padding.symmetric(horizontal=22, vertical=18),
            content=self.log_view,
        )
        return self._page_shell(header, ft.Container(height=18), panel, scroll=False)

    def _append_log(self, text, tag=None):
        color = {"success": OK, "error": DANGER}.get(tag, MUTED)
        self.log_view.controls.append(
            ft.Text(text, size=12, color=color, font_family=MONO, selectable=True)
        )
        self._log_buffer.append(text)
        overflow = len(self.log_view.controls) - MAX_LOG_LINES
        if overflow > 0:
            del self.log_view.controls[:overflow]
            del self._log_buffer[:overflow]

    def _copy_log(self):
        self.page.set_clipboard("\n".join(self._log_buffer))
        self.page.open(ft.SnackBar(
            content=ft.Text("Log copied to clipboard", color=TEXT, size=13),
            bgcolor=RAISED, duration=1800,
        ))

    def _clear_log(self):
        self.log_view.controls.clear()
        self._log_buffer.clear()
        self.page.update()

    # ───────────── navigation / state ─────────────
    def _go(self, key):
        self._show_page(key)
        self.page.update()

    def _show_page(self, key):
        self.current_page = key
        self.host.content = self.pages[key]
        for name, item in self.nav.items():
            item.set_active(name == key)

    def _set_status(self, text, tone="ok"):
        color = TONES[tone]
        self.status_text.value = text
        self.status_text.color = color if tone in ("warn", "danger") else TEXT
        self.status_dot.bgcolor = color

    def _refresh_state(self):
        prepared = self._is_prepared()
        if self.busy:
            label, color = "Working…", ACCENT_SOFT
        elif prepared:
            label, color = "Ready to play", OK
        else:
            label, color = "Preparation needed", WARN

        self.side_dot.bgcolor = color
        self.side_dot.tooltip = label
        self.resources_desc.value = (
            "Prepared and ready to launch." if prepared
            else "Click Prepare to automatically download the game and resources."
        )
        self.prepare_button.set_label("Update" if prepared else "Prepare")
        self.play_button.set_label("Working…" if self.busy else ("Play" if prepared else "Install and play"))
        self.progress.visible = self.busy

    # ───────────── backend (без изменений) ─────────────
    def _selected_paths(self):
        minecraft_dir = Path(self.minecraft_field.value.strip()).expanduser()
        minecraft_dir.mkdir(parents=True, exist_ok=True)
        return minecraft_dir.resolve()

    def _download_file(self, url: str, dest: Path, timeout: int = 300) -> None:
        try:
            response = requests.get(url, timeout=timeout, stream=True)
            response.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            self.events.put(("log_success", f"Downloaded: {dest.name}"))
        except requests.exceptions.Timeout:
            raise TimeoutError("Request timed out. Please try again.")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Download error: {e}")

    def _download_verified(self, key: str, title: str, dest: Path) -> None:
        url = self.lock[key]["url"]
        expected = self.lock[key]["sha256"]
        self.events.put(("log", f"Downloading {title} {self.lock[key]['version']}..."))
        self._download_file(url, dest)

        sha = hashlib.sha256()
        with open(dest, "rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                sha.update(block)
        actual = sha.hexdigest()
        if actual != expected:
            dest.unlink(missing_ok=True)
            raise RuntimeError(f"Hash mismatch for {title}. Expected: {expected}, got: {actual}")
        self.events.put(("log_success", f"{title} downloaded and verified."))

    def _download_vineflower(self, dest: Path) -> None:
        self._download_verified("vineflower", "Vineflower", dest)

    def _download_jadx(self, dest: Path) -> None:
        self._download_verified("jadx_headless_mcp", "Jadx", dest)

    def _minecraft_manifest_url(self):
        manifest_sha1 = self.lock["minecraft"]["manifest_sha1"]
        return (
            "https://piston-meta.mojang.com/v1/packages/"
            f"{manifest_sha1}/{self.version}.json"
        )

    def _check_or_java(self, minecraft_dir: Path) -> None:
        version_json = minecraft_dir / "versions" / self.version / f"{self.version}.json"
        if not version_json.is_file():
            version_json.parent.mkdir(parents=True, exist_ok=True)
            self._download_file(self._minecraft_manifest_url(), version_json)

        try:
            version_data = json.loads(version_json.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Could not read Minecraft version manifest: {error}") from error

        minecraft_lock = self.lock["minecraft"]
        accepted_hashes = {
            minecraft_lock["manifest_sha1"],
            *minecraft_lock.get("accepted_manifest_sha1", []),
        }
        actual_hash = hashlib.sha1(version_json.read_bytes()).hexdigest()
        if actual_hash not in accepted_hashes:
            raise RuntimeError(
                f"Unexpected Minecraft version manifest hash: {actual_hash}"
            )

        java_version = version_data.get("javaVersion")
        if not isinstance(java_version, dict):
            raise RuntimeError("Minecraft version manifest does not declare a Java runtime.")
        if java_version.get("majorVersion") != self.java_major:
            raise RuntimeError(
                f"Minecraft requires Java {self.java_major}, but its version manifest "
                f"declares Java {java_version.get('majorVersion')}."
            )
        component = java_version.get("component")
        if not isinstance(component, str) or not component:
            raise RuntimeError("Minecraft version manifest has no Java runtime component.")

        self.events.put(("log", f"Installing Minecraft Java runtime {component}..."))
        callbacks = {
            "setStatus": lambda status: self.events.put(("log", f"[{status}]")),
            "setProgress": lambda _progress: None,
            "setMax": lambda _maximum: None,
        }
        minecraft_launcher_lib.runtime.install_jvm_runtime(
            component, minecraft_dir, callback=callbacks,
        )

    def _check_or_download_vineflower(self) -> Path:
        dest = HORIZON_DIR / ".local" / "vineflower" / "vineflower.jar"
        if not dest.exists():
            self._download_vineflower(dest)
        return dest

    def _check_or_download_jadx(self) -> Path:
        dest = HORIZON_DIR / ".local" / "jadx" / "jadx-headless-mcp.jar"
        if not dest.exists():
            self._download_jadx(dest)
        return dest

    def _download_all_libs(self):
        minecraft_dir = self._selected_paths()

        def task():
            self.events.put(("status", "Downloading libraries..."))
            self._check_or_download_vineflower()
            self._check_or_download_jadx()
            self._check_or_java(minecraft_dir)
            self.events.put(("status", "All libraries downloaded"))
            self.events.put(("log_success", "Ready to launch."))

        self._start_task(task)

    def _is_prepared(self):
        return (self.resources_dir / "horizon-resources.json").is_file()

    def _play(self):
        player_name = self.selected_profile
        if self._is_prepared():
            self._start_task(lambda: self._launch_client(player_name))
            return

        minecraft_dir = self._selected_paths()
        self._start_task(
            lambda: self._prepare_resources(minecraft_dir, launch=True, player_name=player_name)
        )

    def _prepare(self):
        minecraft_dir = self._selected_paths()
        self._start_task(
            lambda: self._prepare_resources(minecraft_dir, launch=False)
        )

    def _prepare_sounds(self):
        if not self._is_prepared():
            self._alert("Resources not prepared", "Please click Play or Prepare first.")
            return
        minecraft_dir = self._selected_paths()
        self._start_task(lambda: self._copy_sounds(minecraft_dir))

    def _start_task(self, task: Callable[[], None]) -> None:
        if self.busy:
            return
        self.busy = True
        for button in self.action_buttons:
            button.set_enabled(False)
        self._set_status("Preparing...", "accent")
        self._refresh_state()
        self.page.update()
        threading.Thread(target=self._run_task, args=(task,), daemon=True).start()

    def _run_task(self, task):
        try:
            task()
        except Exception as error:
            self.events.put(("error", str(error)))
        finally:
            self.events.put(("done", None))

    def _ensure_minecraft_and_server(self, minecraft_dir: Path) -> Path:
        self.events.put(("log", f"Checking for Minecraft {self.version}..."))

        version_dir = minecraft_dir / "versions" / self.version
        version_jar = version_dir / f"{self.version}.jar"
        version_json = version_dir / f"{self.version}.json"

        if not version_jar.is_file() or not version_json.is_file():
            self.events.put(("log", f"Minecraft {self.version} files missing. Downloading via launcher library..."))
            version_dir.mkdir(parents=True, exist_ok=True)

            cbs = {
                "setStatus": lambda t: self.events.put(("log", f"[{t}]")),
                "setProgress": lambda v: None,
                "setMax": lambda v: None
            }

            minecraft_launcher_lib.install.install_minecraft_version(self.version, minecraft_dir, callback=cbs)


            self.events.put(("log", f"Applying required Horizon manifest for {self.version}..."))
            if version_json.is_file():
                version_json.unlink()
            self._download_file(self._minecraft_manifest_url(), version_json)

            self.events.put(("log_success", f"Minecraft {self.version} setup complete!"))
        else:
            self.events.put(("log", f"Minecraft {self.version} is already installed."))

        server_jar_dir = HORIZON_DIR / ".local" / "minecraft" / self.version / "jars"
        server_jar = server_jar_dir / "server.jar"
        if not server_jar.is_file():
            self.events.put(("log", f"Downloading server.jar for version {self.version}..."))
            try:
                manifest_url = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
                manifest = requests.get(manifest_url, timeout=30).json()
                version_url = next((v["url"] for v in manifest["versions"] if v["id"] == self.version), None)
                if version_url:
                    v_data = requests.get(version_url, timeout=30).json()
                    server_url = v_data.get("downloads", {}).get("server", {}).get("url")
                    if server_url:
                        self._download_file(server_url, server_jar)
            except Exception as e:
                raise RuntimeError(f"Failed to automatically download server.jar: {e}")

        return server_jar

    @staticmethod
    def _require_executable(path: Path) -> Path:
        if not path.is_file():
            raise RuntimeError(f"Horizon executable not found: {path}")
        if not os.access(path, os.X_OK):
            raise RuntimeError(
                f"{path.name} is not executable. From a terminal, run "
                f"`chmod +x \"{path}\"` and try again."
            )
        return path

    def _prepare_resources(self, minecraft_dir, launch, player_name=None):
        server_jar = self._ensure_minecraft_and_server(minecraft_dir)
        self._check_or_java(minecraft_dir)

        preparer = self._require_executable(HORIZON_DIR / "horizon-prepare")

        command = [
            str(preparer), "--prepare",
            "--root", str(HORIZON_DIR),
            "--minecraft-dir", str(minecraft_dir),
            "--server-jar", str(server_jar),
        ]
        self.events.put(("log", "Preparing Horizon resources..."))
        self._run_logged_command(command)
        if not self._is_prepared():
            raise RuntimeError("Preparer finished without Horizon resource manifest.")
        self.events.put(("status", "Resources prepared"))
        self.events.put(("log_success", "Preparation completed."))
        if launch:
            self._launch_client(player_name)

    def _copy_sounds(self, minecraft_dir):
        preparer = self._require_executable(HORIZON_DIR / "horizon-prepare")
        command = [
            str(preparer), "sounds",
            "--root", str(HORIZON_DIR),
            "--minecraft-dir", str(minecraft_dir),
        ]
        self.events.put(("log", "Copying and verifying sounds from the Minecraft folder..."))
        self._run_logged_command(command)
        self.events.put(("status", "Sounds added"))
        self.events.put(("log_success", "Sound preparation completed."))

    def _run_logged_command(self, command):
        process = subprocess.Popen(
            command, cwd=HORIZON_DIR,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        if process.stdout is not None:
            for line in process.stdout:
                self.events.put(("log", line.rstrip()))
        return_code = process.wait()
        if return_code:
            raise RuntimeError(
                f"Preparation ended with code {return_code}. Check log for details."
            )

    def _launch_client(self, player_name):
        client = self._require_executable(HORIZON_DIR / "horizon-client")
        if not self._is_prepared():
            raise RuntimeError("Please prepare Horizon resources first.")

        command = [str(client), "--resources", str(self.resources_dir), "--name", player_name]
        process = subprocess.Popen(
            command, cwd=HORIZON_DIR,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        self.events.put(("status", "Horizon launched"))
        self.events.put(("log_success", "Game launched."))
        threading.Thread(target=self._watch_client, args=(process,), daemon=True).start()

    def _watch_client(self, process):
        if process.stdout is not None:
            for line in process.stdout:
                self.events.put(("log", line.rstrip()))
        return_code = process.wait()
        if return_code:
            self.events.put(("client_error", return_code))
        else:
            self.events.put(("status", "Game closed"))

    # ───────────── event pump ─────────────
    def _event_loop(self):
        """Забирает события из фоновых потоков и обновляет UI пачками."""
        while True:
            try:
                batch = [self.events.get(timeout=0.2)]
            except queue.Empty:
                continue
            while True:
                try:
                    batch.append(self.events.get_nowait())
                except queue.Empty:
                    break

            for event, value in batch:
                try:
                    self._handle_event(event, value)
                except Exception as error:  
                    self._append_log(f"UI error: {error}", "error")
            try:
                self.page.update()
            except Exception:
                pass

    def _handle_event(self, event, value):
        if event == "log":
            if value:
                self._append_log(value)
        elif event == "log_success":
            self._append_log(value, "success")
        elif event == "status":
            self._set_status(value, "ok")
        elif event == "error":
            self._set_status("Action failed", "danger")
            self._append_log(value, "error")
            self._show_page("log")
            self._alert("Horizon error", value)
        elif event == "client_error":
            self._set_status(f"Game exited with code {value}", "danger")
            self._append_log(f"Client finished with code {value}.", "error")
            self._show_page("log")
        elif event == "done":
            self.busy = False
            for button in self.action_buttons:
                button.set_enabled(True)
            self._refresh_state()


def main(page: ft.Page):
    HorizonLauncher(page)


if __name__ == "__main__":
    ft.app(target=main, assets_dir=str(ASSETS_DIR))
