import math
import tkinter as tk

import customtkinter as ctk

from . import theme
from .motion import Animator, mix


class TogglePanel(ctk.CTkFrame):
    HEIGHT = 96

    def __init__(self, master, animator: Animator, command):
        super().__init__(master, corner_radius=16, border_width=2, height=self.HEIGHT,
                         fg_color=theme.BYPASS, border_color=theme.BYPASS)
        self.pack_propagate(False)
        self.animator = animator
        self.command = command
        self._active = False
        self._color = theme.BYPASS
        self._hover = False
        self._focus = False

        self.title = ctk.CTkLabel(self, text="", font=theme.font(26, "bold"), anchor="w", text_color=theme.TEXT)
        self.title.pack(fill="x", padx=22, pady=(18, 0))
        self.sub = ctk.CTkLabel(self, text="", font=theme.font(13), anchor="w", text_color=theme.BYPASS_SUB)
        self.sub.pack(fill="x", padx=22, pady=(0, 0))

        self._canvas.configure(takefocus=1, cursor="hand2")
        for widget in (self, self.title, self.sub):
            widget.bind("<Button-1>", self._on_click)
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)
        self.title.configure(cursor="hand2")
        self.sub.configure(cursor="hand2")
        self._canvas.bind("<FocusIn>", lambda _e: self._set_focus(True))
        self._canvas.bind("<FocusOut>", lambda _e: self._set_focus(False))
        self._canvas.bind("<space>", self._on_click)
        self._canvas.bind("<Return>", self._on_click)

    def set_state(self, active: bool, title: str, sub: str, animate: bool = True) -> None:
        self._active = active
        self.title.configure(text=title)
        self.sub.configure(text=sub, text_color=theme.ACTIVE_SUB if active else theme.BYPASS_SUB)
        self._retint(180 if active else 140, animate)

    def _target_color(self) -> str:
        base = theme.ACTIVE if self._active else theme.BYPASS
        return mix(base, "#ffffff", 0.07) if self._hover else base

    def _retint(self, duration: int, animate: bool = True) -> None:
        self.animator.color("toggle-panel", duration if animate else 0, self._paint, self._color, self._target_color())

    def _paint(self, color: str) -> None:
        self._color = color
        self.configure(fg_color=color, border_color=theme.TEXT if self._focus else color)

    def _on_click(self, _event=None):
        self._canvas.focus_set()
        self.command()
        return "break"

    def _pointer_inside(self) -> bool:
        widget = self.winfo_containing(*self.winfo_pointerxy())
        return widget is not None and str(widget).startswith(str(self))

    def _on_enter(self, _event=None):
        if not self._hover:
            self._hover = True
            self._retint(120)

    def _on_leave(self, _event=None):
        if self._hover and not self._pointer_inside():
            self._hover = False
            self._retint(120)

    def _set_focus(self, focused: bool) -> None:
        self._focus = focused
        self._paint(self._color)


class LevelMeter(tk.Canvas):
    FLOOR_DB = -54.0
    FALL_PER_S = 1.4
    PEAK_HOLD_S = 0.9

    def __init__(self, master, bg: str, segments: int = 36, height: int = 12):
        super().__init__(master, height=height, bg=bg, highlightthickness=0, bd=0)
        self.segments = segments
        self._rects: list[int] = []
        self._fills: list[str | None] = []
        self._level = 0.0
        self._peak = 0.0
        self._peak_age = 0.0
        self.bind("<Configure>", self._layout)

    def _layout(self, _event=None):
        self.delete("all")
        width, height = self.winfo_width(), int(self["height"])
        gap = 3
        seg_w = (width - gap * (self.segments - 1)) / self.segments
        self._rects = []
        for i in range(self.segments):
            x0 = i * (seg_w + gap)
            self._rects.append(self.create_rectangle(x0, 0, x0 + seg_w, height, width=0, fill=theme.METER_OFF))
        self._fills = [theme.METER_OFF] * self.segments

    def update_level(self, peak_linear: float, dt: float, lit: str | None) -> None:
        if lit is None:
            target = 0.0
        else:
            db = 20.0 * math.log10(max(peak_linear, 1e-6))
            target = min(1.0, max(0.0, (db - self.FLOOR_DB) / -self.FLOOR_DB))

        self._level = max(target, self._level - self.FALL_PER_S * dt)
        if self._level >= self._peak:
            self._peak, self._peak_age = self._level, 0.0
        else:
            self._peak_age += dt
            if self._peak_age > self.PEAK_HOLD_S:
                self._peak = max(self._level, self._peak - self.FALL_PER_S * dt)

        if not self._rects:
            return
        lit_count = round(self._level * self.segments)
        peak_index = round(self._peak * self.segments) - 1
        for i, rect in enumerate(self._rects):
            position = (i + 1) / self.segments
            if i < lit_count or (i == peak_index and peak_index > 0 and lit is not None):
                color = theme.METER_CLIP if position > 0.94 else theme.METER_HOT if position > 0.83 else lit
                if i >= lit_count:
                    color = mix(color, theme.METER_OFF, 0.45)
            else:
                color = theme.METER_OFF
            if self._fills[i] != color:
                self._fills[i] = color
                self.itemconfigure(rect, fill=color)


class LiveDot(ctk.CTkFrame):
    SIZE = 10

    def __init__(self, master, animator: Animator):
        super().__init__(master, width=self.SIZE, height=self.SIZE, corner_radius=self.SIZE // 2,
                         fg_color=theme.OFF)
        self.animator = animator
        self._live = False
        self._phase = 0.0

    def set_live(self, live: bool) -> None:
        if live != self._live:
            self._live = live
            self._phase = 0.0
            self.configure(fg_color=theme.ACTIVE_LIGHT if live else theme.OFF)

    def update_pulse(self, dt: float) -> None:
        if not self._live or not self.animator.enabled:
            return
        self._phase = (self._phase + dt / 1.8) % 1.0
        t = 0.5 - 0.5 * math.cos(self._phase * 2 * math.pi)
        self.configure(fg_color=mix(theme.ACTIVE_LIGHT, "#1d6b3d", t * 0.7))
