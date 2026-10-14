"""Timing reports aggregate concurrent calls without sharing invocation state."""

from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase

from etchlib.diagnostics.timing import Timings


class TimingReportTests(TestCase):
    def test_parallel_call_totals_and_longest_duration(self) -> None:
        timing = Timings()
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(
                pool.map(
                    lambda _: timing.record("demo", "brew", "inspect", 0.25), range(100)
                )
            )
        timing.record("demo", "brew", "apply", 30)
        report = timing.render()
        self.assertIn("100 / 25.000s / 0.250s / demo / brew / inspect", report)
        self.assertLess(
            report.index("demo / brew / apply"), report.index("demo / brew / inspect")
        )
        self.assertNotIn("demo / brew", Timings().render())
