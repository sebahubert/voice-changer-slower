from pathlib import Path

BG = "#1b1d21"
SURFACE = "#24272c"
SURFACE_HI = "#2f3339"
SURFACE_HOVER = "#3a3f47"
BORDER = "#3a3f47"

TEXT = "#eceef1"
TEXT_MUTED = "#a0a7b1"
TEXT_ON_LIGHT = "#15171a"

PRIMARY = "#eceef1"
PRIMARY_HOVER = "#ffffff"

ACTIVE = "#11733a"
ACTIVE_SUB = "#dcf7e4"
ACTIVE_LIGHT = "#3fd47f"
BYPASS = "#33383f"
BYPASS_SUB = "#bcc3cc"
NEUTRAL_LIGHT = "#c3cad3"
OFF = "#5b6370"

WARN = "#f2b84b"
ERROR = "#ff8a80"
OK = "#5ee08f"
METER_OFF = "#353a41"
METER_HOT = "#f2b84b"
METER_CLIP = "#ff6b6b"

FONT = "ZT Nature"
FALLBACK_FONT = "Segoe UI"
FONTS_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
FONT_FILES = ("ZTNature-Regular.otf", "ZTNature-Bold.otf")


def load_fonts() -> None:
    global FONT
    import customtkinter as ctk
    loaded = [ctk.FontManager.load_font(str(FONTS_DIR / name)) for name in FONT_FILES]
    if not all(loaded):
        FONT = FALLBACK_FONT


def font(size: int, weight: str = "normal"):
    import customtkinter as ctk
    return ctk.CTkFont(family=FONT, size=size, weight=weight)
