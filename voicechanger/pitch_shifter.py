import numpy as np

TWO_PI = 2.0 * np.pi


class PitchShifter:
    LIFTER = 100

    def __init__(self, frame_size: int = 1024, oversampling: int = 4, preserve_formants: bool = True):
        if frame_size % oversampling:
            raise ValueError("frame_size debe ser múltiplo de oversampling")

        self.preserve_formants = preserve_formants
        self.frame_size = frame_size
        self.oversampling = oversampling
        self.hop = frame_size // oversampling

        self.window = np.hanning(frame_size + 1)[:-1]
        self.ola_gain = np.sum(self.window ** 2) / self.hop

        self.num_bins = frame_size // 2 + 1
        self.bins = np.arange(self.num_bins, dtype=np.float64)
        self.expected_phase_step = TWO_PI * self.hop / frame_size

        self.ratio = 1.0
        self.reset()

    @property
    def latency_samples(self) -> int:
        return self.frame_size - self.hop

    def set_semitones(self, semitones: float) -> None:
        self.ratio = 2.0 ** (semitones / 12.0)

    def reset(self) -> None:
        self._in_frame = np.zeros(self.frame_size)
        self._out_accum = np.zeros(self.frame_size)
        self._last_phase = np.zeros(self.num_bins)
        self._rotation = np.zeros(self.num_bins)
        self._pending = np.zeros(0)
        self._out_fifo = np.zeros(0)

    def process(self, block: np.ndarray) -> np.ndarray:
        n = len(block)
        self._pending = np.concatenate((self._pending, block.astype(np.float64)))

        produced = []
        while len(self._pending) >= self.hop:
            chunk = self._pending[: self.hop]
            self._pending = self._pending[self.hop:]
            produced.append(self._process_hop(chunk))
        if produced:
            self._out_fifo = np.concatenate([self._out_fifo, *produced])

        if len(self._out_fifo) < n:
            self._out_fifo = np.concatenate((np.zeros(n - len(self._out_fifo)), self._out_fifo))

        out = self._out_fifo[:n]
        self._out_fifo = self._out_fifo[n:]
        return out

    def _envelope(self, magnitude: np.ndarray) -> np.ndarray:
        cepstrum = np.fft.irfft(np.log(magnitude + 1e-9), n=self.frame_size)
        lifter = min(self.LIFTER, self.frame_size // 2 - 1)
        cepstrum[lifter:self.frame_size - lifter + 1] = 0.0
        return np.exp(np.fft.rfft(cepstrum, n=self.frame_size).real)

    def _process_hop(self, chunk: np.ndarray) -> np.ndarray:
        hop = self.hop

        self._in_frame[:-hop] = self._in_frame[hop:]
        self._in_frame[-hop:] = chunk

        spectrum = np.fft.rfft(self._in_frame * self.window)
        magnitude = np.abs(spectrum)
        phase = np.angle(spectrum)

        delta = phase - self._last_phase
        self._last_phase = phase
        delta -= self.bins * self.expected_phase_step
        delta = (delta + np.pi) % TWO_PI - np.pi

        true_bin = self.bins + delta * self.oversampling / TWO_PI

        is_peak = np.zeros(self.num_bins, dtype=bool)
        is_peak[1:-1] = (magnitude[1:-1] > magnitude[:-2]) & (magnitude[1:-1] >= magnitude[2:])
        peaks = np.flatnonzero(is_peak)
        if len(peaks) == 0:
            peaks = np.array([int(np.argmax(magnitude))])
        region = np.searchsorted((peaks[:-1] + peaks[1:]) / 2.0, self.bins)

        ratio = self.ratio
        peak_shift = np.rint(peaks * ratio).astype(np.int64) - peaks
        peak_rotation = self._rotation[peaks] + (ratio - 1.0) * true_bin[peaks] * TWO_PI / self.oversampling
        peak_rotation %= TWO_PI

        bin_rotation = peak_rotation[region]
        self._rotation = bin_rotation
        destination = self.bins.astype(np.int64) + peak_shift[region]
        valid = (destination >= 0) & (destination < self.num_bins)

        moved = spectrum[valid] * np.exp(1j * bin_rotation[valid])
        if self.preserve_formants and ratio != 1.0:
            envelope = self._envelope(magnitude)
            source = self.bins[valid].astype(np.int64)
            moved *= np.clip(envelope[destination[valid]] / envelope[source], 0.05, 20.0)

        shifted = np.zeros(self.num_bins, dtype=np.complex128)
        np.add.at(shifted, destination[valid], moved)

        frame = np.fft.irfft(shifted, n=self.frame_size)
        self._out_accum += frame * self.window / self.ola_gain

        out = self._out_accum[:hop].copy()
        self._out_accum[:-hop] = self._out_accum[hop:]
        self._out_accum[-hop:] = 0.0
        return out
