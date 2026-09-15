import os
import unittest
from unittest.mock import patch

from etchlib.conditions.results import ConditionError, Outcome
from etchlib.providers.observations import FactResult, FactState
from tests.condition_fixtures import ConditionFixture


class ConditionTests(ConditionFixture, unittest.TestCase):
    def test_platform_and_list_alternatives(self):
        with (
            patch("etchlib.facts.platform.platform.system", return_value="Linux"),
            patch("etchlib.facts.platform.platform.machine", return_value="x86_64"),
            patch("etchlib.facts.platform.distro_id", return_value="ubuntu"),
        ):
            result = self.evaluator.evaluate(
                {"os": ["macos", "linux"], "distro": "ubuntu", "arch": "x86_64"}
            )
            self.assertEqual(result.outcome, Outcome.TRUE)
            self.assertEqual(
                self.evaluator.evaluate({"os": "macos", "arch": "x86_64"}).outcome,
                Outcome.FALSE,
            )

    def test_command_presence_and_absence(self):
        with patch(
            "etchlib.facts.probes.shutil.which",
            side_effect=lambda name: "/bin/tool" if name == "tool" else None,
        ):
            self.assertEqual(
                self.evaluator.evaluate({"command": ["missing", "tool"]}).outcome,
                Outcome.TRUE,
            )
            self.assertEqual(
                self.evaluator.evaluate({"command": "missing"}).outcome, Outcome.FALSE
            )

    def test_env_presence_empty_and_equality(self):
        with patch.dict(os.environ, {"EMPTY": "", "CI": "yes"}, clear=True):
            for condition, expected in [
                ({"env": "EMPTY"}, True),
                ({"env": "ABSENT"}, False),
                ({"env": {"name": "CI", "equals": "yes"}}, True),
                ({"env": ["ABSENT", {"name": "EMPTY", "equals": ""}]}, True),
            ]:
                self.assertEqual(
                    self.evaluator.evaluate(condition).outcome,
                    Outcome.TRUE if expected else Outcome.FALSE,
                )

    def test_boolean_fact_and_type_sensitive_equality(self):
        self.fact("flag", FactResult(FactState.VALUE, True))
        self.assertEqual(
            self.evaluator.evaluate({"fact": {"name": "flag"}}).outcome, Outcome.TRUE
        )
        self.assertEqual(
            self.evaluator.evaluate({"fact": {"name": "flag", "equals": 1}}).outcome,
            Outcome.FALSE,
        )

    def test_version_branches_are_mutually_exclusive(self):
        self.fact("version", FactResult(FactState.VALUE, "3.5a"))
        self.assertEqual(
            self.evaluator.evaluate(
                {"fact": {"name": "version", "matches": "<2.1"}}
            ).outcome,
            Outcome.FALSE,
        )
        self.assertEqual(
            self.evaluator.evaluate(
                {"fact": {"name": "version", "matches": ">=2.1"}}
            ).outcome,
            Outcome.TRUE,
        )

    def test_negation(self):
        self.fact("flag", FactResult(FactState.VALUE, False))
        self.assertEqual(
            self.evaluator.evaluate({"not": {"fact": {"name": "flag"}}}).outcome,
            Outcome.TRUE,
        )

    def test_invalid_syntax_even_in_short_circuited_branch(self):
        for condition in [
            {},
            {"typo": "linux"},
            {"os": []},
            {"not": []},
            {"env": {"CI": "yes"}},
            {"fact": {"name": "x", "matches": "^2"}},
            {"os": "other", "fact": {"name": "x", "extra": True}},
        ]:
            with self.subTest(condition=condition), self.assertRaises(ConditionError):
                self.evaluator.evaluate(condition)
        self.assertEqual(self.observations.calls, [])

    def test_failed_probe_and_wrong_value_types_are_errors(self):
        self.fact("failed", FactResult(FactState.ERROR, reason="probe exited 7"))
        self.fact("text", FactResult(FactState.VALUE, "hello"))
        for name in ("failed", "text"):
            with self.assertRaises(ConditionError):
                self.evaluator.evaluate({"fact": {"name": name}})

    def test_unknown_fact_is_diagnostic(self):
        with self.assertRaisesRegex(ConditionError, "undeclared fact"):
            self.evaluator.evaluate({"fact": {"name": "unknown"}})

    def test_results_require_explicit_outcome(self):
        with patch.dict(os.environ, {"CI": "yes"}):
            with self.assertRaises(TypeError):
                bool(self.evaluator.evaluate({"env": "CI"}))
