"""Opt-in, invocation-local provider timings; never capture arguments or output."""

from threading import Lock
from time import perf_counter
from typing import Callable

TimingSink = Callable[[str, str, str, float], None]


class Timings:
    def __init__(self) -> None:
        self.started = perf_counter()
        self._lock = Lock()
        self._rows: dict[tuple[str, str, str], tuple[int, float, float]] = {}

    def record(self, module: str, provider: str, method: str, seconds: float) -> None:
        key = (module or "global", provider, method)
        with self._lock:
            count, total, longest = self._rows.get(key, (0, 0.0, 0.0))
            self._rows[key] = count + 1, total + seconds, max(longest, seconds)

    def render(self) -> str:
        with self._lock:
            rows = sorted(self._rows.items(), key=lambda row: (-row[1][1], row[0]))
        lines = [
            "Provider timings — elapsed {:.3f}s".format(perf_counter() - self.started),
            "  calls / total / longest / module / provider / phase",
        ]
        for key, (count, total, longest) in rows:
            lines.append(
                "  {} / {:.3f}s / {:.3f}s / {}".format(
                    count, total, longest, " / ".join(key)
                )
            )
        lines.append(
            "Includes external work; parallel durations overlap. Arguments and output are omitted."
        )
        return "\n".join(lines)
