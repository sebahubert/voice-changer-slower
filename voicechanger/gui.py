import time

import customtkinter as ctk
import sounddevice as sd

from . import config, devices, theme
from .audio_engine import AudioEngine
from .hotkey import GlobalHotkey, format_hotkey
from .motion import Animator, mix
from .widgets import LevelMeter, LiveDot, TogglePanel

FRAME_OPTIONS = {"Rápida": 512, "Equilibrada": 1024, "Natural": 2048}
FRAME_HELP = {
    512: "Para Tono: suma 8 ms de retraso y suena un poco más robótico.",
    1024: "Para Tono: suma 16 ms de retraso. Es la opción recomendada.",
    2048: "Para Tono: suma 32 ms de retraso y suena más natural.",
}
HOTKEY_MODES = {"Alternar": "toggle", "Mantener": "hold"}
NO_DEVICE = "(ninguno)"
TICK_MS = 33
WRAP = 380


def speed_text(speed: float) -> str:
    return f"{speed:.2f}".replace(".", ",") + "×"


def signed(value: int) -> str:
    return f"+{value}" if value > 0 else f"−{-value}" if value < 0 else "0"


class VoiceChangerApp(ctk.CTk):
    def __init__(self):
        theme.load_fonts()
        super().__init__(fg_color=theme.BG)
        ctk.set_appearance_mode("dark")

        self.title("Voice Changer RT")
        self.geometry("920x760")
        self.minsize(860, 740)

        self.settings = config.load()
        self.animator = Animator(self)
        self._ready = False
        self._ticks = 0
        self._last_tick = time.perf_counter()
        self._note = ""
        self._error = ""
        self._health: list[int] = []
        self._last_underflows = 0
        self._capturing = False
        self._capture_phase = 0.0
        self._captured_hotkey = None

        self.engine = AudioEngine()
        self.engine.effect_active = bool(self.settings["effect_active"])
        self.engine.output_gain = float(self.settings["output_gain"])
        self.engine.set_semitones(float(self.settings["semitones"]))
        self.engine.set_speed(float(self.settings["speed"]))
        if self.settings["hotkey_mode"] == "hold":
            self.engine.effect_active = False
        self._shown_active = self.engine.effect_active

        self._build_ui()
        self._load_hostapis()
        self._refresh_voice()
        self._refresh_hotkey()
        self._refresh_toggle(animate=False)
        self._refresh_status()

        self.hotkey = GlobalHotkey(self._on_hotkey_press, self._on_hotkey_release)
        self.hotkey.set_hotkey(self.settings["hotkey"])
        self.hotkey.start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(TICK_MS, self._tick)
        self._ready = True

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(18, 4))
        ctk.CTkLabel(header, text="Voice Changer RT", font=theme.font(20, "bold"),
                     text_color=theme.TEXT).pack(anchor="w")
        ctk.CTkLabel(header, text="Tu micrófono con otro tono, directo a Discord, Zoom u OBS.",
                     font=theme.font(13), text_color=theme.TEXT_MUTED).pack(anchor="w")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(4, 18))
        body.grid_columnconfigure((0, 1), weight=1, uniform="col")
        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew")
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")

        self._build_live(right)
        self._build_voice(right)
        self._build_hotkey(right)
        self._build_devices(left)
        self._build_settings(left)

    def _build_live(self, parent):
        live = ctk.CTkFrame(parent, fg_color=theme.SURFACE, corner_radius=16)
        live.pack(fill="x", padx=8, pady=(10, 0))

        row = ctk.CTkFrame(live, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(16, 14))
        self.live_dot = LiveDot(row, self.animator)
        self.live_dot.pack(side="left", padx=(2, 10))
        texts = ctk.CTkFrame(row, fg_color="transparent")
        texts.pack(side="left", fill="x", expand=True)
        self.status_title = ctk.CTkLabel(texts, text="", font=theme.font(14, "bold"), anchor="w", height=20)
        self.status_title.pack(fill="x")
        self.status_detail = ctk.CTkLabel(texts, text="", font=theme.font(13), anchor="w", height=18,
                                          text_color=theme.TEXT_MUTED)
        self.status_detail.pack(fill="x")
        self.power_button = ctk.CTkButton(row, text="", width=112, height=36, corner_radius=10,
                                          font=theme.font(13, "bold"), command=self.toggle_engine)
        self.power_button.pack(side="right")

        self.toggle_panel = TogglePanel(live, self.animator, self.toggle_effect)
        self.toggle_panel.pack(fill="x", padx=18)

        meter_row = ctk.CTkFrame(live, fg_color="transparent")
        meter_row.pack(fill="x", padx=18, pady=(14, 16))
        ctk.CTkLabel(meter_row, text="Micrófono", font=theme.font(13), height=18,
                     text_color=theme.TEXT_MUTED).pack(side="left", padx=(0, 12))
        self.meter = LevelMeter(meter_row, bg=theme.SURFACE)
        self.meter.pack(side="left", fill="x", expand=True)
        self.note_label = ctk.CTkLabel(live, text="", font=theme.font(13), anchor="w", justify="left",
                                       wraplength=WRAP, text_color=theme.WARN)

    def _build_voice(self, parent):
        card = self._card(parent, "Efecto de voz")
        self.speed_value, self.speed_desc = self._value_row(card, "Velocidad")
        self.speed_slider = self._slider(card, 0.5, 1.5, 20, self._on_speed_slider)
        self.speed_slider.set(self.engine.speed)
        self.speed_slider.pack(fill="x", padx=12, pady=(2, 10))

        self.pitch_value, self.pitch_desc = self._value_row(card, "Tono")
        self.pitch_slider = self._slider(card, -12, 12, 24, self._on_pitch_slider)
        self.pitch_slider.set(self.engine.semitones)
        self.pitch_slider.pack(fill="x", padx=12, pady=(2, 4))

        presets = ctk.CTkFrame(card, fg_color="transparent")
        presets.pack(fill="x", padx=18, pady=(8, 16))
        presets.grid_columnconfigure((0, 1), weight=1, uniform="preset")
        self._button(presets, "Original", lambda: self._apply_preset(1.0, 0)).grid(
            row=0, column=0, sticky="ew", padx=(0, 4))
        self._button(presets, "Voz 0.7×", lambda: self._apply_preset(0.7, 0)).grid(
            row=0, column=1, sticky="ew", padx=(4, 0))

    def _value_row(self, parent, label: str):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=18)
        ctk.CTkLabel(row, text=label, font=theme.font(13), text_color=theme.TEXT_MUTED).pack(side="left")
        desc = ctk.CTkLabel(row, text="", font=theme.font(13), text_color=theme.TEXT_MUTED)
        desc.pack(side="right")
        value = ctk.CTkLabel(row, text="", font=theme.font(18, "bold"), text_color=theme.TEXT)
        value.pack(side="right", padx=(0, 8))
        return value, desc

    def _build_hotkey(self, parent):
        card = self._card(parent, "Atajo de teclado")
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=18)
        self.keycaps = ctk.CTkFrame(row, fg_color=theme.SURFACE_HI, corner_radius=10, height=40)
        self.keycaps.pack(side="left", fill="x", expand=True)
        self.keycaps.pack_propagate(False)
        self.hotkey_button = self._button(row, "Cambiar", self._capture_hotkey, width=96)
        self.hotkey_button.configure(height=40)
        self.hotkey_button.pack(side="left", padx=(8, 0))

        self.hotkey_mode_selector = self._segmented(card, list(HOTKEY_MODES), self._on_hotkey_mode_change)
        self.hotkey_mode_selector.pack(fill="x", padx=18, pady=(10, 6))
        self.hotkey_help = ctk.CTkLabel(card, text="", font=theme.font(13), anchor="w", justify="left",
                                        wraplength=WRAP, text_color=theme.TEXT_MUTED)
        self.hotkey_help.pack(fill="x", padx=18, pady=(0, 14))

    def _build_devices(self, parent):
        card = self._card(parent, "Dispositivos")
        self.hostapi_menu = self._labeled_menu(card, "Driver de audio", self._on_hostapi_change)
        self.input_menu = self._labeled_menu(card, "Micrófono", self._on_device_change)
        self.output_menu = self._labeled_menu(card, "Enviar la voz a", self._on_device_change)
        self.cable_hint = ctk.CTkLabel(card, text="", font=theme.font(13), anchor="w", justify="left",
                                       wraplength=WRAP)
        self.cable_hint.pack(fill="x", padx=18, pady=(2, 0))
        self._button(card, "Actualizar dispositivos", lambda: self._refresh_devices(reinit=True)).pack(
            anchor="w", padx=18, pady=(8, 16))

    def _build_settings(self, parent):
        card = self._card(parent, "Ajustes")
        self._field_label(card, "Calidad del efecto")
        self.frame_selector = self._segmented(card, list(FRAME_OPTIONS), self._on_frame_change)
        current = next((k for k, v in FRAME_OPTIONS.items() if v == self.settings["frame_size"]), "Equilibrada")
        self.frame_selector.set(current)
        self.frame_selector.pack(fill="x", padx=18, pady=(4, 2))
        self.frame_help = ctk.CTkLabel(card, text="", font=theme.font(13), anchor="w",
                                       text_color=theme.TEXT_MUTED)
        self.frame_help.pack(fill="x", padx=18)
        self._refresh_frame_help()

        self.exclusive_var = ctk.BooleanVar(value=bool(self.settings["exclusive"]))
        self.exclusive_check = ctk.CTkCheckBox(
            card, text="Modo exclusivo (menos retraso)", variable=self.exclusive_var,
            command=self._on_exclusive_change, font=theme.font(13), text_color=theme.TEXT,
            text_color_disabled=theme.TEXT_MUTED, fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
            checkmark_color=theme.TEXT_ON_LIGHT, border_color=theme.OFF, corner_radius=5,
        )
        self.exclusive_check.pack(anchor="w", padx=18, pady=(12, 0))
        self.exclusive_help = ctk.CTkLabel(card, text="", font=theme.font(13), anchor="w", justify="left",
                                           wraplength=WRAP, text_color=theme.TEXT_MUTED)
        self.exclusive_help.pack(fill="x", padx=18)

        gain_row = ctk.CTkFrame(card, fg_color="transparent")
        gain_row.pack(fill="x", padx=18, pady=(10, 0))
        ctk.CTkLabel(gain_row, text="Volumen de salida", font=theme.font(13),
                     text_color=theme.TEXT_MUTED).pack(side="left")
        self.gain_value = ctk.CTkLabel(gain_row, text="", font=theme.font(13, "bold"), text_color=theme.TEXT)
        self.gain_value.pack(side="right")
        self.gain_slider = self._slider(card, 0, 2, 40, self._on_gain)
        self.gain_slider.set(self.engine.output_gain)
        self.gain_slider.pack(fill="x", padx=12, pady=(2, 16))
        self._on_gain(self.engine.output_gain)

    def _card(self, parent, title: str) -> ctk.CTkFrame:
        return self._card_with_header(parent, title)[0]

    def _card_with_header(self, parent, title: str) -> tuple[ctk.CTkFrame, ctk.CTkFrame]:
        card = ctk.CTkFrame(parent, fg_color=theme.SURFACE, corner_radius=16)
        card.pack(fill="x", padx=8, pady=(10, 0))
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(14, 4))
        ctk.CTkLabel(header, text=title, font=theme.font(14, "bold"), text_color=theme.TEXT,
                     anchor="w").pack(side="left")
        return card, header

    def _field_label(self, parent, text: str):
        ctk.CTkLabel(parent, text=text, font=theme.font(13), text_color=theme.TEXT_MUTED, anchor="w",
                     height=20).pack(fill="x", padx=18, pady=(2, 0))

    def _labeled_menu(self, parent, label: str, command) -> ctk.CTkOptionMenu:
        self._field_label(parent, label)
        menu = ctk.CTkOptionMenu(
            parent, values=[NO_DEVICE], command=command, dynamic_resizing=False, height=34, corner_radius=8,
            font=theme.font(13), dropdown_font=theme.font(13), text_color=theme.TEXT,
            fg_color=theme.SURFACE_HI, button_color=theme.SURFACE_HOVER, button_hover_color="#454c55",
            dropdown_fg_color=theme.SURFACE_HI, dropdown_hover_color=theme.SURFACE_HOVER,
            dropdown_text_color=theme.TEXT,
        )
        menu.pack(fill="x", padx=18, pady=(4, 6))
        return menu

    def _button(self, parent, text: str, command, width: int = 0) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent, text=text, command=command, height=34, corner_radius=8, font=theme.font(13),
            fg_color=theme.SURFACE_HI, hover_color=theme.SURFACE_HOVER, text_color=theme.TEXT,
            text_color_disabled=theme.TEXT_MUTED, **({"width": width} if width else {}),
        )

    def _segmented(self, parent, values, command) -> ctk.CTkSegmentedButton:
        return ctk.CTkSegmentedButton(
            parent, values=values, command=command, height=34, corner_radius=8, font=theme.font(13),
            fg_color=theme.SURFACE_HI, unselected_color=theme.SURFACE_HI,
            unselected_hover_color=theme.SURFACE_HOVER, selected_color="#5a626e",
            selected_hover_color="#646d7a", text_color=theme.TEXT,
        )

    def _slider(self, parent, from_, to, steps, command) -> ctk.CTkSlider:
        return ctk.CTkSlider(
            parent, from_=from_, to=to, number_of_steps=steps, command=command, height=18,
            fg_color=theme.SURFACE_HI, progress_color="#6b7380", button_color=theme.TEXT,
            button_hover_color="#ffffff",
        )

    def _on_hotkey_press(self):
        if self.settings["hotkey_mode"] == "hold":
            self.engine.effect_active = True
        else:
            self.engine.effect_active = not self.engine.effect_active

    def _on_hotkey_release(self):
        if self.settings["hotkey_mode"] == "hold":
            self.engine.effect_active = False

    def _capture_hotkey(self):
        if self._capturing:
            self.hotkey.cancel_capture()
            self._end_capture()
            return
        self._capturing = True
        self._capture_phase = 0.0
        self.hotkey_button.configure(text="Cancelar")
        self._render_keycaps(None)
        self.hotkey_help.configure(text="Presioná la combinación nueva y soltala. Esc también cancela.")
        self.hotkey.capture(self._on_hotkey_captured)

    def _on_hotkey_captured(self, vks):
        self._captured_hotkey = ("ok", vks)

    def _apply_captured_hotkey(self, vks):
        if not self._capturing:
            return
        if vks:
            self.settings["hotkey"] = sorted(vks)
            self.hotkey.set_hotkey(vks)
            self._save()
        self._end_capture(confirm=bool(vks))

    def _end_capture(self, confirm: bool = False):
        self._capturing = False
        self.hotkey_button.configure(text="Cambiar")
        self._refresh_hotkey()
        self._refresh_toggle()
        start = mix(theme.SURFACE_HI, theme.TEXT, 0.35) if confirm else self.keycaps.cget("fg_color")
        self.animator.color("keycaps", 600 if confirm else 120, lambda c: self.keycaps.configure(fg_color=c),
                            start, theme.SURFACE_HI)

    def _render_keycaps(self, vks):
        for child in self.keycaps.winfo_children():
            child.destroy()
        if vks is None:
            ctk.CTkLabel(self.keycaps, text="Esperando teclas…", font=theme.font(13),
                         text_color=theme.TEXT).pack(side="left", padx=12)
            return
        keys = format_hotkey(vks).split(" + ")
        for i, key in enumerate(keys):
            if i:
                ctk.CTkLabel(self.keycaps, text="+", font=theme.font(13), width=10,
                             text_color=theme.TEXT_MUTED).pack(side="left", padx=2)
            ctk.CTkLabel(self.keycaps, text=key, font=theme.font(13, "bold"), text_color=theme.TEXT,
                         fg_color="#454c55", corner_radius=6, height=26).pack(
                side="left", padx=(8 if i == 0 else 2, 0), pady=7, ipadx=6)

    def _on_hotkey_mode_change(self, value):
        self.settings["hotkey_mode"] = HOTKEY_MODES[value]
        if self.settings["hotkey_mode"] == "hold":
            self.engine.effect_active = False
        self._refresh_hotkey()
        self._refresh_toggle()
        self._save()

    def _refresh_hotkey(self):
        keys = format_hotkey(self.settings["hotkey"])
        self._render_keycaps(self.settings["hotkey"])
        mode = self.settings["hotkey_mode"]
        self.hotkey_mode_selector.set(next(k for k, v in HOTKEY_MODES.items() if v == mode))
        if mode == "hold":
            text = f"El efecto suena sólo mientras mantenés {keys}."
        else:
            text = f"Cada vez que apretás {keys}, el efecto se prende o se apaga."
        self.hotkey_help.configure(text=text + " Funciona aunque la ventana esté minimizada.")

    def _load_hostapis(self):
        names = devices.list_hostapis()
        self.hostapi_menu.configure(values=names)
        saved = self.settings["hostapi"]
        self.hostapi_menu.set(saved if saved in names else devices.default_hostapi())
        self._populate_devices()

    def _populate_devices(self):
        hostapi = self.hostapi_menu.get()
        inputs = [name for _, name in devices.list_devices(hostapi, "input")]
        outputs = [name for _, name in devices.list_devices(hostapi, "output")]

        self.input_menu.configure(values=inputs or [NO_DEVICE])
        self.output_menu.configure(values=outputs or [NO_DEVICE])

        mic = devices.pick_microphone(
            inputs, [self.settings["input_device"], devices.default_device_name(hostapi, "input")])
        self.input_menu.set(mic or NO_DEVICE)

        saved_out = self.settings["output_device"]
        cable = devices.find_virtual_cable(outputs)
        default_out = devices.default_device_name(hostapi, "output")
        self.output_menu.set(
            saved_out if saved_out in outputs
            else cable if cable
            else default_out if default_out in outputs
            else (outputs[0] if outputs else NO_DEVICE)
        )
        self._refresh_cable_hint()
        self._refresh_exclusive_option()

    def _refresh_devices(self, reinit: bool = False):
        was_running = self.engine.running
        if reinit:
            self.engine.stop()
            sd._terminate()
            sd._initialize()
        self._load_hostapis()
        if was_running:
            self._start_engine()
        else:
            self._refresh_status()

    def _refresh_cable_hint(self):
        outputs = [name for _, name in devices.list_devices(self.hostapi_menu.get(), "output")]
        selected = self.output_menu.get()
        if devices.is_virtual(self.input_menu.get()):
            text, color = ("El micrófono elegido es el cable virtual: la app se escucharía a sí misma. "
                           "Elegí tu micrófono real.", theme.ERROR)
        elif devices.find_virtual_cable(outputs) is None:
            text, color = ("No encontramos un cable virtual. Instalá VB-CABLE (ver README) "
                           "y tocá «Actualizar dispositivos».", theme.WARN)
        elif devices.find_virtual_cable([selected]) is None:
            text, color = ("Esta salida no es un cable virtual: Discord y Zoom no van a recibir tu voz. "
                           "Elegí «CABLE Input».", theme.WARN)
        else:
            text, color = "Listo. En Discord o Zoom elegí «CABLE Output» como micrófono.", theme.OK
        self.cable_hint.configure(text=text, text_color=color)

    def _refresh_exclusive_option(self):
        if devices.is_wasapi(self.hostapi_menu.get()):
            self.exclusive_check.configure(state="normal")
            self.exclusive_help.configure(text="Si da cortes con tus dispositivos, la app vuelve sola al modo normal.")
        else:
            self.exclusive_check.configure(state="disabled")
            self.exclusive_help.configure(text="Disponible sólo con el driver Windows WASAPI.")

    def _on_hostapi_change(self, _value):
        self._populate_devices()
        self._save()
        if self.engine.running:
            self._start_engine()

    def _on_device_change(self, _value):
        self._refresh_cable_hint()
        self._save()
        if self.engine.running:
            self._start_engine()

    def toggle_engine(self):
        if self.engine.running:
            self.engine.stop()
            self._note = ""
        else:
            self._start_engine()
        self._refresh_status()

    def _start_engine(self, exclusive: bool | None = None, note: str = ""):
        self._error = ""
        in_name, out_name = self.input_menu.get(), self.output_menu.get()
        if NO_DEVICE in (in_name, out_name):
            self._error = "Elegí un micrófono y una salida en «Dispositivos»."
            self._refresh_status()
            return
        if devices.is_virtual(in_name) and devices.is_virtual(out_name):
            self._error = ("El micrófono y la salida son el mismo cable virtual: se armaría un bucle. "
                           "En «Micrófono» elegí tu micrófono real.")
            self._refresh_status()
            return
        if exclusive is None:
            exclusive = self.exclusive_var.get() and devices.is_wasapi(self.hostapi_menu.get())
        try:
            self.engine.start(self.hostapi_menu.get(), in_name, out_name, self._frame_size(), exclusive)
            self._note = note
            self._health = []
            self._last_underflows = 0
        except Exception as exc:
            detail = str(exc).split("[")[0].strip()
            self._error = ("No se pudo abrir el micrófono o la salida. Puede que otro programa los esté usando: "
                           f"cerralo o desactivá «Modo exclusivo» y probá de nuevo. (Detalle: {detail})")
        self._refresh_status()

    def _refresh_status(self):
        running = self.engine.running
        self.live_dot.set_live(running)
        if running:
            mode = self.engine.mode_description.split(" (")[0]
            self.status_title.configure(text="En vivo", text_color=theme.TEXT)
            self.status_detail.configure(
                text=f"Retraso ≈ {self.engine.estimated_latency_ms():.0f} ms · {mode}")
            self.power_button.configure(text="Detener audio", fg_color=theme.SURFACE_HI,
                                        hover_color=theme.SURFACE_HOVER, text_color=theme.TEXT)
        else:
            failed = bool(self._error)
            self.status_title.configure(text="No se pudo iniciar" if failed else "Audio apagado",
                                        text_color=theme.ERROR if failed else theme.TEXT)
            self.status_detail.configure(text="Revisá el aviso de abajo." if failed
                                         else "Tocá «Iniciar audio» para empezar.")
            self.power_button.configure(text="Iniciar audio", fg_color=theme.PRIMARY,
                                        hover_color=theme.PRIMARY_HOVER, text_color=theme.TEXT_ON_LIGHT)
        message = self._error or self._note
        self.note_label.configure(text=message, text_color=theme.ERROR if self._error else theme.WARN)
        if message and not self.note_label.winfo_ismapped():
            self.note_label.pack(fill="x", padx=18, pady=(0, 14))
        elif not message and self.note_label.winfo_manager():
            self.note_label.pack_forget()

    def _check_health(self):
        count = self.engine.underflows
        self._health.append(count - self._last_underflows)
        self._last_underflows = count
        recent = sum(self._health[2:][-3:])
        if recent >= 4:
            if self.engine.exclusive:
                self._start_engine(exclusive=False, note=(
                    "El modo exclusivo daba cortes con estos dispositivos, así que la app pasó al modo normal."))
                return
            self._note = "Hay cortes en el audio. Probá con otro driver de audio."
            self._health.clear()
        self._refresh_status()

    def _on_exclusive_change(self):
        self._save()
        if self.engine.running:
            self._start_engine()

    def toggle_effect(self):
        self.engine.effect_active = not self.engine.effect_active
        self._refresh_toggle()
        self._save()

    def _refresh_toggle(self, animate: bool = True):
        active = self.engine.effect_active
        changed = active != self._shown_active
        self._shown_active = active

        keys = format_hotkey(self.settings["hotkey"])
        hold = self.settings["hotkey_mode"] == "hold"
        if active:
            parts = []
            if self.engine.speed_on:
                parts.append(f"Velocidad {speed_text(self.engine.speed)}")
            if self.engine.pitch_on:
                parts.append(f"{signed(round(self.engine.semitones))} semitonos")
            tone = " · ".join(parts) or "Sin cambios (Velocidad 1× y Tono 0)"
            action = f"soltá {keys} para volver a tu voz" if hold else f"{keys} para apagar"
            self.toggle_panel.set_state(True, "Voz modificada", f"{tone} · {action}", animate and changed)
        else:
            action = f"mantené {keys} para activar el efecto" if hold else f"{keys} para activar el efecto"
            self.toggle_panel.set_state(False, "Voz normal", f"Sin efecto · {action}", animate and changed)

    def _on_speed_slider(self, value):
        self.animator.cancel("speed-slider")
        speed = round(value * 20) / 20
        if abs(speed - self.engine.speed) > 1e-6:
            self.engine.set_speed(speed)
            self._refresh_voice()
            self._save()

    def _on_pitch_slider(self, value):
        self.animator.cancel("pitch-slider")
        st = round(value)
        if st != round(self.engine.semitones):
            self.engine.set_semitones(st)
            self._refresh_voice()
            self._save()

    def _apply_preset(self, speed: float, semitones: int):
        self.engine.set_speed(speed)
        self.engine.set_semitones(semitones)
        self._refresh_voice()
        self._save()
        self._glide(self.speed_slider, "speed-slider", speed, 20)
        self._glide(self.pitch_slider, "pitch-slider", semitones, 24)

    def _glide(self, slider, key: str, target: float, steps: int):
        start = float(slider.get())
        slider.configure(number_of_steps=None)

        def done():
            slider.configure(number_of_steps=steps)
            slider.set(target)

        self.animator.tween(key, 220, slider.set, start, float(target), on_done=done)

    def _refresh_voice(self):
        speed = self.engine.speed
        self.speed_value.configure(text=speed_text(speed))
        self.speed_desc.configure(text="tu voz" if not self.engine.speed_on else (
            "más gruesa" if speed < 1 else "más fina"))

        st = round(self.engine.semitones)
        self.pitch_value.configure(text=signed(st))
        self.pitch_desc.configure(text="semitonos" if st == 0 else (
            "semitonos · más grave" if st < 0 else "semitonos · más aguda"))
        self._refresh_toggle()

    def _on_frame_change(self, _value):
        self._refresh_frame_help()
        self._save()
        if self.engine.running:
            self._start_engine()

    def _refresh_frame_help(self):
        self.frame_help.configure(text=FRAME_HELP[self._frame_size()])

    def _frame_size(self) -> int:
        return FRAME_OPTIONS.get(self.frame_selector.get(), 1024)

    def _on_gain(self, value):
        self.engine.output_gain = float(value)
        self.gain_value.configure(text=f"{value * 100:.0f} %")
        self._save()

    def _tick(self):
        now = time.perf_counter()
        dt, self._last_tick = now - self._last_tick, now

        if self.engine.effect_active != self._shown_active:
            self._refresh_toggle()
        if self._captured_hotkey:
            _, vks = self._captured_hotkey
            self._captured_hotkey = None
            self._apply_captured_hotkey(vks)

        if self.state() != "iconic":
            lit = None
            if self.engine.running:
                lit = theme.ACTIVE_LIGHT if self.engine.effect_active else theme.NEUTRAL_LIGHT
            self.meter.update_level(self.engine.input_level, dt, lit)
            self.live_dot.update_pulse(dt)
            if self._capturing and self.animator.enabled:
                self._capture_phase = (self._capture_phase + dt / 1.2) % 1.0
                t = abs(self._capture_phase * 2 - 1)
                self.keycaps.configure(fg_color=mix(theme.SURFACE_HI, theme.SURFACE_HOVER, 1 - t))

        self._ticks += 1
        if self._ticks % 30 == 0 and self.engine.running:
            self._check_health()
        self.after(TICK_MS, self._tick)

    def _save(self):
        if not self._ready:
            return
        self.settings.update(
            hostapi=self.hostapi_menu.get(),
            input_device=self.input_menu.get(),
            output_device=self.output_menu.get(),
            semitones=round(self.engine.semitones),
            speed=self.engine.speed,
            frame_size=self._frame_size(),
            output_gain=round(self.engine.output_gain, 2),
            effect_active=self.engine.effect_active,
            exclusive=self.exclusive_var.get(),
        )
        if self.settings["hotkey_mode"] == "hold":
            self.settings["effect_active"] = False
        config.save(self.settings)

    def _on_close(self):
        self._save()
        self.hotkey.stop()
        self.engine.stop()
        self.destroy()


def run():
    VoiceChangerApp().mainloop()
