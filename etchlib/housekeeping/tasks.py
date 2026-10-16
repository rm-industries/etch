"""Planned retirement and housekeeping recheck the live destination before removal."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from etchlib.config import destination
from etchlib.providers.filesystem.receipts import identity
from etchlib.providers.filesystem.state import kind

from .records import Record


def matches(record: Record, target: Path) -> bool:
    if kind(target) != "link":
        return False
    current = identity(target)
    return (
        current is not None
        and record.data is not None
        and all(record.data.get(key) == value for key, value in current.items())
    )


@dataclass(frozen=True)
class Task:
    record: Record
    operation: str
    module: str
    target: Optional[Path] = None
    removed_owner: bool = False

    @property
    def description(self) -> str:
        labels = {
            "retire": "Retire link",
            "stale": "Prune stale link receipt",
            "missing": "Prune missing-download receipt",
            "invalid": "Prune invalid receipt",
            "legacy": "Prune unused legacy download receipt",
            "upgrade": "Update download receipt",
        }
        return "{}: {}".format(
            labels[self.operation], self.target or self.record.path.name
        )

    def apply(self, root: Path) -> bool:
        if not self.record.current():
            return False
        if (
            self.target is not None
            and destination(str(self.target), root) != self.target
        ):
            raise ValueError("housekeeping destination parent changed since planning")
        if self.operation == "upgrade":
            assert self.target is not None
            return self.record.upgrade(self.target)
        if self.operation in ("retire", "stale"):
            assert self.target is not None
            if self.operation == "retire" and matches(self.record, self.target):
                self.target.unlink()
                self.record.forget()
                return True
            if matches(self.record, self.target):
                return False
        if (
            self.operation == "missing"
            and self.target is not None
            and kind(self.target) != "missing"
        ):
            return False
        return self.record.forget()
