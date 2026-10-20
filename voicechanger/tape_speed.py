import numpy as np


class TapeSpeed:
    def __init__(self, frame_size: int = 1024):
        self.N = frame_size
        self.hop = frame_size // 2
        self.tolerance = frame_size // 4
        self.template = frame_size // 2
        self.window = np.hanning(frame_size + 1)[:-1]
        self.factor = 1.0
        self.reset()

    @property
    def latency_samples(self) -> int:
        return self.N + self.tolerance

    def reset(self) -> None:
        self._in = np.zeros(0)
        self._pos = 0.0
        self._prev: int | None = None
        self._acc = np.zeros(self.N)
        self._mid = np.zeros(0)
        self._phase = 0.0
        self._started = False

    def set_factor(self, factor: float) -> None:
        self.factor = float(factor)

    def process(self, block: np.ndarray) -> np.ndarray:
        n = len(block)
        r = self.factor
        self._in = np.concatenate((self._in, block.astype(np.float64)))

        if not self._started:
            if len(self._in) < self.tolerance + self.N + int(self.hop / r) + n:
                return np.zeros(n)
            self._started = True

        needed = int(np.ceil(self._phase + (n - 1) * r)) + 2
        while len(self._mid) < needed:
            if not self._can_synthesize():
                self._pos = float(len(self._in) - self.tolerance - self.N)
            self._mid = np.concatenate((self._mid, self._synthesize_hop(r)))

        positions = self._phase + np.arange(n) * r
        base = positions.astype(np.int64)
        frac = positions - base
        out = self._mid[base] * (1.0 - frac) + self._mid[base + 1] * frac

        self._phase += n * r
        drop = int(self._phase)
        self._mid = self._mid[drop:]
        self._phase -= drop
        self._trim()
        return out

    def _can_synthesize(self) -> bool:
        return len(self._in) >= int(self._pos) + self.tolerance + self.N

    def _best_start(self, nominal: int) -> int:
        if self._prev is None:
            return nominal
        natural = self._prev + self.hop
        target = self._in[natural:natural + self.template]
        lo = max(0, nominal - self.tolerance)
        region = self._in[lo:nominal + self.tolerance + self.template]
        if len(target) < self.template or len(region) < self.template:
            return nominal
        corr = np.correlate(region, target, mode="valid")
        sq = np.concatenate(([0.0], np.cumsum(region * region)))
        energy = sq[self.template:] - sq[:-self.template]
        return lo + int(np.argmax(corr / np.sqrt(energy + 1e-9)))

    def _synthesize_hop(self, r: float) -> np.ndarray:
        start = self._best_start(int(round(self._pos)))
        self._acc += self._in[start:start + self.N] * self.window
        out = self._acc[:self.hop].copy()
        self._acc[:-self.hop] = self._acc[self.hop:]
        self._acc[-self.hop:] = 0.0
        self._prev = start
        self._pos += self.hop / r
        return out

    def _trim(self) -> None:
        oldest = min(self._pos, self._prev if self._prev is not None else self._pos)
        keep_from = int(oldest) - self.tolerance
        if keep_from > self.N * 4:
            self._in = self._in[keep_from:]
            self._pos -= keep_from
            if self._prev is not None:
                self._prev -= keep_from
