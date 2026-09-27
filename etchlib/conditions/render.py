"""Probe-free descriptions of condition requirements."""

from typing import Any, Mapping


def describe_condition(condition: Mapping[str, Any]) -> str:
    """Name requirements without showing observed fact or environment values."""
    clauses = []
    for key, raw in condition.items():
        if key == "not":
            clauses.append("Excludes: " + describe_condition(raw))
            continue
        values = raw if isinstance(raw, list) else [raw]
        if key in ("os", "distro", "arch"):
            label = {"os": "OS", "distro": "distribution", "arch": "architecture"}[key]
            names = ["macOS" if value == "macos" else value for value in values]
            clauses.append("Needs {} {}".format(label, " or ".join(names)))
        elif key == "command":
            clauses.append("Needs command {}".format(" or ".join(values)))
        elif key == "env":
            clauses.append(
                "Needs environment variable {}".format(
                    " or ".join(
                        value["name"] if isinstance(value, dict) else value
                        for value in values
                    )
                )
            )
        elif key == "fact":
            clauses.append(
                "Needs fact {} to match".format(
                    " or ".join(value["name"] for value in values)
                )
            )
    return "; ".join(clauses) or "Condition not met"
