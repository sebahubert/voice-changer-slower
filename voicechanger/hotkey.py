import threading
from collections.abc import Callable

from pynput import keyboard

VK_ESCAPE = 27
MODIFIERS = (17, 16, 18, 91)

_ALIASES = {160: 16, 161: 16, 162: 17, 163: 17, 164: 18, 165: 18, 92: 91}

_NAMES = {
    16: "Shift", 17: "Ctrl", 18: "Alt", 91: "Win", 8: "Retroceso", 9: "Tab", 13: "Enter",
    19: "Pausa", 20: "Bloq Mayús", 32: "Espacio", 33: "Re Pág", 34: "Av Pág", 35: "Fin",
    36: "Inicio", 37: "←", 38: "↑", 39: "→", 40: "↓", 44: "Impr Pant", 45: "Insert",
    46: "Supr", 93: "Menú", 106: "Num *", 107: "Num +", 109: "Num -", 110: "Num .",
    111: "Num /", 144: "Bloq Num", 145: "Bloq Despl", 186: "´", 187: "+", 188: ",",
    189: "-", 190: ".", 191: "ç", 192: "Ñ", 219: "'", 220: "º", 221: "¡", 222: "{",
    226: "<", 179: "Play/Pausa", 173: "Silencio",
}


def key_to_vk(key) -> int | None:
    vk = getattr(key, "vk", None)
    if vk is None and isinstance(key, keyboard.Key):
        vk = key.value.vk
    if vk is None:
        return None
    return _ALIASES.get(vk, vk)


def vk_label(vk: int) -> str:
    if vk in _NAMES:
        return _NAMES[vk]
    if 0x70 <= vk <= 0x87:
        return f"F{vk - 0x6F}"
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return chr(vk)
    if 0x60 <= vk <= 0x69:
        return f"Num {vk - 0x60}"
    return f"Tecla {vk}"


def format_hotkey(vks) -> str:
    if not vks:
        return "(sin atajo)"
    ordered = [m for m in MODIFIERS if m in vks] + sorted(v for v in vks if v not in MODIFIERS)
    return " + ".join(vk_label(v) for v in ordered)


class GlobalHotkey:
    def __init__(self, on_press: Callable[[], None], on_release: Callable[[], None]):
        self.on_press = on_press
        self.on_release = on_release
        self.vks: frozenset[int] = frozenset()
        self._pressed: set[int] = set()
        self._held = False
        self._capture_cb: Callable[[frozenset[int] | None], None] | None = None
        self._captured: set[int] = set()
        self._lock = threading.Lock()
        self._listener: keyboard.Listener | None = None

    def start(self) -> None:
        self._listener = keyboard.Listener(on_press=self._handle_press, on_release=self._handle_release)
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None

    def set_hotkey(self, vks) -> None:
        with self._lock:
            self.vks = frozenset(vks)
            self._held = False

    def capture(self, callback: Callable[[frozenset[int] | None], None]) -> None:
        with self._lock:
            self._captured = set()
            self._pressed.clear()
            self._capture_cb = callback

    def cancel_capture(self) -> None:
        with self._lock:
            self._capture_cb = None

    def _handle_press(self, key) -> None:
        vk = key_to_vk(key)
        if vk is None:
            return
        fire = False
        with self._lock:
            self._pressed.add(vk)
            if self._capture_cb:
                self._captured.add(vk)
                return
            if self.vks and not self._held and self.vks <= self._pressed:
                self._held = True
                fire = True
        if fire:
            self.on_press()

    def _handle_release(self, key) -> None:
        vk = key_to_vk(key)
        if vk is None:
            return
        fire = False
        done = None
        with self._lock:
            self._pressed.discard(vk)
            if self._capture_cb:
                if not self._pressed and self._captured:
                    captured = frozenset(self._captured)
                    done = (self._capture_cb, None if captured == {VK_ESCAPE} else captured)
                    self._capture_cb = None
            elif self._held and vk in self.vks:
                self._held = False
                fire = True
        if done:
            callback, result = done
            callback(result)
        if fire:
            self.on_release()
