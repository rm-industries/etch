from unittest.mock import patch

from etchlib.conditions.results import ConditionError, Outcome
from etchlib.graph.model import GraphError, NodeId
from tests.planning_fixtures import PlanningFixture


class PlanningConditionsTests(PlanningFixture):
    def declare(self, actions: list[dict[str, object]]) -> None:
        self.module(
            facts={
                "tool": {
                    "version": {"command": [str(self.root / "missing"), "--version"]}
                }
            },
            actions=actions,
        )

    def consumer(self) -> dict[str, object]:
        return {
            "script": {"path": "not-created-yet"},
            "when": {"fact": {"name": "tool", "matches": ">=1"}},
        }

    def test_installer_refresh_justifies_uninspected_deferred_action(self) -> None:
        self.declare(
            [
                {
                    "installer": {"url": "https://example.org/install"},
                    "refresh": ["tool"],
                },
                self.consumer(),
            ]
        )
        with patch.object(
            self.registry.action("script").provider,
            "inspect",
            side_effect=AssertionError("deferred action inspected"),
        ):
            report = self.plan()
        self.assertEqual(report.selections["demo"].actions[1].outcome, Outcome.DEFERRED)
        self.assertNotIn(NodeId("demo", "action", 1), report.plans)
        status, output, error = self.cli()
        self.assertEqual(status, 0, error)
        for text in (
            "DEFERRED",
            "unavailable",
            "waiting for demo:action[0]",
            "refresh",
            "fresh conditions",
        ):
            self.assertIn(text, output)

    def test_absent_later_self_and_skipped_producers_cannot_justify_deferral(
        self,
    ) -> None:
        consumer = self.consumer()
        producers: list[list[dict[str, object]]] = [
            [consumer],
            [consumer, {"shell": {"command": "true"}, "refresh": ["tool"]}],
            [dict(consumer, refresh=["tool"])],
            [
                {
                    "shell": {
                        "command": "true",
                        "check": {"directory_exists": str(self.root)},
                    },
                    "refresh": ["tool"],
                },
                consumer,
            ],
            [
                {
                    "shell": {"command": "true"},
                    "when": {"os": "never"},
                    "refresh": ["tool"],
                },
                consumer,
            ],
        ]
        for actions in producers:
            with self.subTest(actions=actions):
                self.declare(actions)
                with self.assertRaisesRegex(ConditionError, "no earlier producer"):
                    self.plan()

    def test_false_branches_ignore_providers_and_dependencies(self) -> None:
        self.module(
            actions=[{"missing": {}, "when": {"os": "never"}, "requires": ["absent"]}]
        )
        report = self.plan()
        self.assertEqual(len(report.plans), 0)
        self.assertIn("SKIP (condition false)", self.cli()[1])

    def test_invalid_condition_in_false_module_still_fails(self) -> None:
        self.module(
            when={"os": "never"}, actions=[{"shell": {}, "when": {"typo": True}}]
        )
        self.assertEqual(self.cli()[0], 1)

    def test_unused_bad_fact_is_not_gathered(self) -> None:
        self.module(facts={"unused": {"version": {"invalid": True}}})
        self.assertTrue(all(value is None for value in self.plan().facts.values()))
        self.assertIn("demo.unused: not requested", self.cli()[1])

    def test_dependency_order_and_cycles(self) -> None:
        self.module("a", requires=["z"], actions=[{"shell": {"command": "true"}}])
        self.module("z", actions=[{"shell": {"command": "true"}}])
        order = self.plan().graph.order()
        self.assertLess(
            order.index(NodeId("z", "finish")), order.index(NodeId("a", "start"))
        )
        self.module("z", requires=["a"])
        with self.assertRaises(GraphError):
            self.plan()

    def test_missing_hard_dependency_fails_soft_dependency_warns(self) -> None:
        self.module(requires=["missing"])
        self.assertEqual(self.cli()[0], 1)
        self.module(after=["missing"])
        self.assertIn("Warning:", self.cli()[1])
