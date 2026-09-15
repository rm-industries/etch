import unittest
from pathlib import Path

from etchlib.facts.core import core_registry
from etchlib.facts.store import FactStore
from etchlib.providers.contracts import Context
from etchlib.providers.errors import ProviderError
from etchlib.providers.observations import FactRef, FactResult, FactState
from etchlib.providers.registry import Origin


class CountingFact:
    name = "counting"

    def __init__(self):
        self.calls = 0
        self.fail = False

    def validate(self, config, context):
        pass

    def gather(self, config, context):
        self.calls += 1
        if self.fail:
            raise RuntimeError("probe broke")
        return FactResult(FactState.VALUE, [context.module_name, config])


class FactStoreTests(unittest.TestCase):
    def setUp(self):
        self.registry = core_registry()
        self.provider = CountingFact()
        self.registry.register(Origin("example", "1"), facts=[self.provider])
        self.store = FactStore(self.registry)
        self.context = Context(Path("/repo"), Path("/repo/modules/one"), "one", {})
        self.ref = FactRef("one", "version")
        self.store.declare(self.ref, "counting", "config", self.context)

    def test_cache_is_lazy_and_detached(self):
        self.assertIsNone(self.store.peek(self.ref))
        self.assertEqual(self.provider.calls, 0)
        result = self.store.get(self.ref)
        result.value.append("mutated")
        self.assertEqual(self.store.get(self.ref).value, ["one", "config"])
        self.assertEqual(self.provider.calls, 1)

    def test_scopes_never_share_cached_values(self):
        second = FactRef("two", "version")
        context = Context(Path("/repo"), Path("/repo/modules/two"), "two", {})
        self.store.declare(second, "counting", "other", context)
        self.assertEqual(self.store.get(self.ref).value, ["one", "config"])
        self.assertEqual(self.store.get(second).value, ["two", "other"])
        self.assertEqual(self.provider.calls, 2)

    def test_invalidation_is_selective_and_lazy(self):
        self.store.get(self.ref)
        self.store.invalidate(self.ref)
        self.assertEqual(self.store.peek(self.ref).state, FactState.STALE)
        self.assertEqual(self.provider.calls, 1)
        self.assertEqual(self.store.get(self.ref).state, FactState.VALUE)
        self.assertEqual(self.provider.calls, 2)

    def test_probe_failure_is_cached_error_with_context(self):
        self.provider.fail = True
        result = self.store.get(self.ref)
        self.assertEqual(result.state, FactState.ERROR)
        self.assertIn("counting", result.reason)
        self.assertIn("probe broke", result.reason)
        self.store.get(self.ref)
        self.assertEqual(self.provider.calls, 1)
        self.provider.fail = False
        self.store.invalidate(self.ref)
        self.assertEqual(self.store.get(self.ref).state, FactState.VALUE)

    def test_unavailable_unused_fact_never_probes(self):
        ref = FactRef("one", "missing")
        self.store.declare(
            ref, "command", "etch-command-that-does-not-exist-1234", self.context
        )
        self.assertIsNone(self.store.peek(ref))
        self.assertEqual(self.store.get(ref).state, FactState.UNAVAILABLE)

    def test_declaration_failures(self):
        with self.assertRaisesRegex(ProviderError, "duplicate"):
            self.store.declare(self.ref, "counting", {}, self.context)
        with self.assertRaisesRegex(ProviderError, "missing fact provider"):
            self.store.declare(
                FactRef("one", "other"), "shell", "echo hello", self.context
            )
        with self.assertRaisesRegex(ProviderError, "undeclared"):
            self.store.invalidate(FactRef("other", "unknown"))

    def test_global_scope_cannot_collide_with_module_names(self):
        self.assertNotEqual(FactRef(None, "os"), FactRef("builtin", "os"))
