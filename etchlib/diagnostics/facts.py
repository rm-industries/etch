"""Gather and display selected facts without executing actions."""

from typing import Mapping

from etchlib.facts.store import FactStore
from etchlib.providers.observations import FactRef, FactResult, FactState


def label(ref: FactRef) -> str:
    return (
        "global/{}".format(ref.name)
        if ref.module is None
        else "module/{}/{}".format(ref.module, ref.name)
    )


def gather(store: FactStore) -> dict[FactRef, FactResult]:
    return {ref: store.get(ref) for ref in store.references()}


def render_facts(facts: Mapping[FactRef, FactResult]) -> str:
    lines = ["Facts (selected declarations; no actions applied):"]
    for ref, result in facts.items():
        detail = (
            repr(result.value) if result.state is FactState.VALUE else result.reason
        )
        lines.append(
            "  {}: {} — {}".format(label(ref), result.state.value.upper(), detail)
        )
    return "\n".join(lines)
