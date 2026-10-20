import json
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    CONFIG_PATH = Path(sys.executable).resolve().parent / "config.json"
else:
    CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

DEFAULTS = {
    "hostapi": None,
    "input_device": None,
    "output_device": None,
    "semitones": 0,
    "speed": 1.0,
    "frame_size": 1024,
    "output_gain": 1.0,
    "effect_active": True,
    "exclusive": True,
    "hotkey": [119],
    "hotkey_mode": "toggle",
}


def load() -> dict:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return {**DEFAULTS, **data}
    except (OSError, ValueError):
        return dict(DEFAULTS)


def save(settings: dict) -> None:
    try:
        CONFIG_PATH.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
