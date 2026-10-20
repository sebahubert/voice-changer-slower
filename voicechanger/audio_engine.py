import threading

import numpy as np
import sounddevice as sd

from . import devices
from .pitch_shifter import PitchShifter
from .tape_speed import TapeSpeed

SAMPLERATE = 48_000
BLOCKSIZE = 256


class RingBuffer:
    MAX_SAFETY = 2048
    MAX_DRIFT = 0.003
    EXCESS_LIMIT = 1024
    SAFETY_STEP = 128
    DRIFT_SMOOTHING = 16

    def __init__(self, capacity: int = SAMPLERATE, safety: int = 256, window: int = SAMPLERATE // 4):
        self.capacity = capacity
        self.data = np.zeros(capacity, dtype=np.float32)
        self.safety = safety
        self.window = window
        self.read_pos = 0
        self.available = 0
        self.primed = False
        self.avg_fill = 0.0
        self.rate = 1.0
        self.underflows = 0
        self.drops = 0
        self._frac = 0.0
        self._min_left = capacity
        self._window_count = 0
        self._error_avg = 0.0
        self.lock = threading.Lock()

    def write(self, samples: np.ndarray) -> None:
        with self.lock:
            n = len(samples)
            if self.available + n > self.capacity:
                drop = self.available + n - self.capacity
                self.read_pos = (self.read_pos + drop) % self.capacity
                self.available -= drop
            write_pos = (self.read_pos + self.available) % self.capacity
            first = min(n, self.capacity - write_pos)
            self.data[write_pos:write_pos + first] = samples[:first]
            self.data[: n - first] = samples[first:]
            self.available += n

    def _pop(self, count: int) -> np.ndarray:
        first = min(count, self.capacity - self.read_pos)
        raw = np.concatenate((self.data[self.read_pos:self.read_pos + first], self.data[: count - first]))
        self.read_pos = (self.read_pos + count) % self.capacity
        self.available -= count
        return raw

    def read(self, n: int) -> np.ndarray:
        with self.lock:
            if not self.primed:
                if self.available < n + self.safety:
                    return np.zeros(n, dtype=np.float32)
                self.primed = True
                self.avg_fill = float(self.available)

            exact = n * self.rate + self._frac
            want = int(exact)
            self._frac = exact - want
            self.avg_fill = 0.98 * self.avg_fill + 0.02 * self.available

            if want > self.available:
                out = np.zeros(n, dtype=np.float32)
                left = self._pop(min(n, self.available))
                out[: len(left)] = left
                self.primed = False
                self.underflows += 1
                self.safety = min(self.safety + self.SAFETY_STEP, self.MAX_SAFETY)
                self.rate = 1.0
                self._error_avg = 0.0
                self._min_left, self._window_count = self.capacity, 0
                return out

            raw = self._pop(want)
            if want == n:
                out = raw
            else:
                out = np.interp(np.linspace(0.0, want - 1, n), np.arange(want), raw).astype(np.float32)

            self._min_left = min(self._min_left, self.available)
            self._window_count += n
            if self._window_count >= self.window:
                error = self._min_left - self.safety
                if error > self.EXCESS_LIMIT:
                    self._pop(error)
                    self.drops += 1
                    error = 0
                self._error_avg = 0.6 * self._error_avg + 0.4 * error
                correction = self._error_avg / (self.DRIFT_SMOOTHING * self._window_count)
                self.rate = 1.0 + max(-self.MAX_DRIFT, min(self.MAX_DRIFT, correction))
                self._min_left, self._window_count = self.capacity, 0
        return out


class AudioEngine:
    def __init__(self):
        self.effect_active = True
        self.semitones = 0.0
        self.speed = 1.0
        self.output_gain = 1.0
        self.input_level = 0.0

        self.mode_description = ""
        self._shifter: PitchShifter | None = None
        self._tape: TapeSpeed | None = None
        self._ring: RingBuffer | None = None
        self._in_stream: sd.InputStream | None = None
        self._out_stream: sd.OutputStream | None = None
        self._mix = 1.0

    @property
    def running(self) -> bool:
        return self._in_stream is not None

    @property
    def underflows(self) -> int:
        return self._ring.underflows if self._ring else 0

    @property
    def exclusive(self) -> bool:
        return self.mode_description == "WASAPI exclusivo"

    def set_semitones(self, semitones: float) -> None:
        self.semitones = semitones
        if self._shifter:
            self._shifter.set_semitones(semitones)

    def set_speed(self, speed: float) -> None:
        self.speed = speed
        if self._tape:
            self._tape.set_factor(speed)

    @property
    def pitch_on(self) -> bool:
        return round(self.semitones) != 0

    @property
    def speed_on(self) -> bool:
        return abs(self.speed - 1.0) > 1e-3

    def start(self, hostapi: str, input_name: str, output_name: str,
              frame_size: int = 1024, exclusive: bool = True) -> None:
        self.stop()

        in_idx = devices.device_index(hostapi, "input", input_name)
        out_idx = devices.device_index(hostapi, "output", output_name)

        self._shifter = PitchShifter(frame_size=frame_size, oversampling=4)
        self._shifter.set_semitones(self.semitones)
        self._tape = TapeSpeed()
        self._tape.set_factor(self.speed)
        self._ring = RingBuffer()
        self._mix = 1.0 if self.effect_active else 0.0

        if not devices.is_wasapi(hostapi):
            self._open_streams(in_idx, out_idx, BLOCKSIZE, None, None)
            self.mode_description = hostapi
            return

        if exclusive:
            try:
                self._open_streams(in_idx, out_idx, BLOCKSIZE,
                                   sd.WasapiSettings(exclusive=True), sd.WasapiSettings(exclusive=True))
                self.mode_description = "WASAPI exclusivo"
                return
            except Exception:
                pass

        shared = sd.WasapiSettings(auto_convert=True)
        self._open_streams(in_idx, out_idx, 0, shared, shared)
        self.mode_description = "WASAPI compartido" + (" (exclusivo no disponible)" if exclusive else "")

    def stop(self) -> None:
        for stream in (self._in_stream, self._out_stream):
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
        self._in_stream = None
        self._out_stream = None
        self.input_level = 0.0

    def estimated_latency_ms(self) -> float:
        if not self.running:
            return 0.0
        seconds = self._in_stream.latency + self._out_stream.latency
        seconds += self._ring.avg_fill / SAMPLERATE
        if self.effect_active and self.pitch_on:
            seconds += self._shifter.latency_samples / SAMPLERATE
        if self.effect_active and self.speed_on:
            seconds += self._tape.latency_samples / SAMPLERATE
        return seconds * 1000.0

    def _open_streams(self, in_idx, out_idx, blocksize, in_extra, out_extra):
        in_channels = min(2, sd.query_devices(in_idx)["max_input_channels"])
        out_channels = min(2, sd.query_devices(out_idx)["max_output_channels"])
        try:
            self._out_stream = sd.OutputStream(
                device=out_idx, samplerate=SAMPLERATE, blocksize=blocksize,
                channels=out_channels, dtype="float32", latency="low",
                extra_settings=out_extra, callback=self._output_callback,
            )
            self._in_stream = sd.InputStream(
                device=in_idx, samplerate=SAMPLERATE, blocksize=blocksize,
                channels=in_channels, dtype="float32", latency="low",
                extra_settings=in_extra, callback=self._input_callback,
            )
            self._out_stream.start()
            self._in_stream.start()
        except Exception:
            self.stop()
            raise

    def _input_callback(self, indata, frames, time, status):
        dry = indata.mean(axis=1) if indata.shape[1] > 1 else indata[:, 0]

        peak = float(np.max(np.abs(dry))) if frames else 0.0
        self.input_level = max(peak, self.input_level * 0.85)

        pitched = self._shifter.process(dry)
        stage = pitched if self.pitch_on else dry.astype(np.float64)
        taped = self._tape.process(stage)
        wet = (taped if self.speed_on else stage).astype(np.float32)

        target = 1.0 if self.effect_active else 0.0
        if target != self._mix:
            mix = np.linspace(self._mix, target, frames, dtype=np.float32)
            out = dry * (1.0 - mix) + wet * mix
            self._mix = target
        elif target == 1.0:
            out = wet
        else:
            out = dry

        out = np.clip(out * self.output_gain, -1.0, 1.0)
        self._ring.write(out.astype(np.float32))

    def _output_callback(self, outdata, frames, time, status):
        outdata[:] = self._ring.read(frames)[:, None]
