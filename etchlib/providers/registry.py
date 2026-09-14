"""Deterministic registration with no discovery or provider-specific dispatch."""
from dataclasses import dataclass
import re
from typing import Any, Dict, Iterable, Tuple

from .errors import ProviderError


@dataclass(frozen=True)
class Origin:
    name: str
    version: str
    core: bool = False

    def __post_init__(self):
        if any(not isinstance(v, str) or not v.strip() for v in (self.name, self.version)):
            raise ValueError("provider origin requires a name and version")
        if type(self.core) is not bool:
            raise ValueError("origin core flag must be boolean")


@dataclass(frozen=True)
class Registration:
    name: str
    kind: str
    provider: Any
    origin: Origin


class Registry:
    def __init__(self):
        self._entries: Dict[str, Registration] = {}

    def register(self, origin: Origin, actions: Iterable[Any] = (),
                 facts: Iterable[Any] = ()) -> None:
        """Register a complete bundle atomically, preserving declaration order."""
        if not isinstance(origin, Origin):
            raise ProviderError("registration requires Origin metadata")
        pending: Dict[str, Registration] = {}
        for kind, providers, methods in (
            ("action", actions, ("validate", "inspect", "plan", "apply")),
            ("fact", facts, ("validate", "gather")),
        ):
            for provider in providers:
                name = getattr(provider, "name", None)
                if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_.-]*", name):
                    raise ProviderError("{}: invalid {} provider name {!r}".format(origin.name, kind, name))
                if kind == "action" and name in ("when", "requires", "after", "refresh"):
                    raise ProviderError("action provider name {!r} is reserved for metadata".format(name))
                previous = pending.get(name) or self._entries.get(name)
                if previous is not None:
                    raise ProviderError("provider {!r} from {} conflicts with {} {} ({})".format(
                        name, origin.name, previous.kind, previous.origin.name, previous.origin.version))
                missing = [method for method in methods if not callable(getattr(provider, method, None))]
                if missing:
                    raise ProviderError("{}: {} provider {!r} lacks callable {}".format(
                        origin.name, kind, name, ", ".join(missing)))
                pending[name] = Registration(name, kind, provider, origin)
        self._entries.update(pending)

    def lookup(self, name: str, kind: str) -> Registration:
        entry = self._entries.get(name)
        if entry is None:
            raise ProviderError("missing {} provider {!r}".format(kind, name))
        if entry.kind != kind:
            raise ProviderError("provider {!r} is a {}, not an {}".format(name, entry.kind, kind))
        return entry

    def action(self, name: str) -> Registration:
        return self.lookup(name, "action")

    def fact(self, name: str) -> Registration:
        return self.lookup(name, "fact")

    def entries(self) -> Tuple[Registration, ...]:
        return tuple(self._entries.values())

    def copy(self) -> "Registry":
        """Copy registrations, retaining the same trusted provider instances."""
        registry = Registry()
        registry._entries = self._entries.copy()
        return registry
