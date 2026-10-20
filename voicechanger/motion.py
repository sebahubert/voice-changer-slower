import ctypes
import time
from collections.abc import Callable

FRAME_MS = 16


def windows_animations_enabled() -> bool:
    try:
        value = ctypes.c_int(1)
        ok = ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(value), 0)
        return bool(value.value) if ok else True
    except (AttributeError, OSError):
        return True


def ease_out_expo(t: float) -> float:
    return 1.0 if t >= 1.0 else 1.0 - 2.0 ** (-10.0 * t)


def _rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def mix(a: str, b: str, t: float) -> str:
    ra, ga, ba = _rgb(a)
    rb, gb, bb = _rgb(b)
    return "#{:02x}{:02x}{:02x}".format(
        round(ra + (rb - ra) * t), round(ga + (gb - ga) * t), round(ba + (bb - ba) * t),
    )


class Animator:
    def __init__(self, root):
        self.root = root
        self.enabled = windows_animations_enabled()
        self._jobs: dict[str, str] = {}

    def cancel(self, key: str) -> None:
        job = self._jobs.pop(key, None)
        if job:
            self.root.after_cancel(job)

    def tween(self, key: str, duration_ms: int, apply: Callable[[float], None],
              start: float = 0.0, end: float = 1.0, on_done: Callable[[], None] | None = None) -> None:
        self.cancel(key)
        if not self.enabled or duration_ms <= 0:
            apply(end)
            if on_done:
                on_done()
            return

        t0 = time.perf_counter()

        def step():
            progress = min(1.0, (time.perf_counter() - t0) * 1000.0 / duration_ms)
            apply(start + (end - start) * ease_out_expo(progress))
            if progress < 1.0:
                self._jobs[key] = self.root.after(FRAME_MS, step)
            else:
                self._jobs.pop(key, None)
                if on_done:
                    on_done()

        step()

    def color(self, key: str, duration_ms: int, apply: Callable[[str], None], start: str, end: str,
              on_done: Callable[[], None] | None = None) -> None:
        self.tween(key, duration_ms, lambda t: apply(mix(start, end, t)), on_done=on_done)
