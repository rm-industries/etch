import unittest

from etchlib.providers.errors import ProviderError
from etchlib.providers.registry import Origin, Registry
from tests.provider_fixtures import MemoryAction, MemoryFact


class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = Registry()
        self.core = Origin("Etch core", "0.1.0", core=True)
        self.plugin = Origin("etch-example", "1.2.0")

    def test_registration_preserves_order_and_origin(self) -> None:
        action, fact = MemoryAction(), MemoryFact()
        self.registry.register(self.core, [action])
        self.registry.register(self.plugin, facts=[fact])
        self.assertEqual(
            [r.name for r in self.registry.entries()], ["memory", "memory_value"]
        )
        self.assertIs(self.registry.action("memory").provider, action)
        self.assertEqual(self.registry.fact("memory_value").origin, self.plugin)

    def test_core_cannot_be_shadowed_and_failure_is_atomic(self) -> None:
        self.registry.register(self.core, [MemoryAction()])
        unique = MemoryAction()
        unique.name = "unique"
        with self.assertRaisesRegex(ProviderError, "conflicts with action Etch core"):
            self.registry.register(self.plugin, [unique, MemoryAction()])
        self.assertEqual(len(self.registry.entries()), 1)
        with self.assertRaisesRegex(ProviderError, "missing action"):
            self.registry.action("unique")

    def test_duplicates_within_bundle_and_across_kinds(self) -> None:
        with self.assertRaises(ProviderError):
            self.registry.register(self.plugin, [MemoryAction(), MemoryAction()])
        self.assertEqual(self.registry.entries(), ())
        fact = MemoryFact()
        fact.name = "memory"
        with self.assertRaises(ProviderError):
            self.registry.register(self.plugin, [MemoryAction()], [fact])
        self.assertEqual(self.registry.entries(), ())

    def test_missing_or_wrong_kind(self) -> None:
        self.registry.register(self.core, facts=[MemoryFact()])
        with self.assertRaisesRegex(ProviderError, "missing action"):
            self.registry.action("missing")
        with self.assertRaisesRegex(ProviderError, "is a fact"):
            self.registry.action("memory_value")

    def test_incomplete_provider(self) -> None:
        action = MemoryAction()
        # Deliberately break the protocol to test runtime plugin validation.
        action.apply = None  # type: ignore[method-assign, assignment]
        with self.assertRaisesRegex(ProviderError, "lacks callable apply"):
            self.registry.register(self.plugin, [action])
        self.assertEqual(self.registry.entries(), ())

    def test_invalid_names(self) -> None:
        for name in [None, "", "has space", "../path", "when", "refresh"]:
            action = MemoryAction()
            action.name = name  # type: ignore[assignment]  # Invalid plugin metadata.
            with self.subTest(name=name), self.assertRaises(ProviderError):
                self.registry.register(self.core, [action])

    def test_registration_never_invokes_lifecycle(self) -> None:
        action = MemoryAction()
        self.registry.register(self.plugin, [action])
        self.assertEqual(action.calls, [])
