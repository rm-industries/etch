"""Validate the entire condition before observing any machine state."""

from etchlib.versions.constraints import matches

from .results import ConditionError

KEYS = {"os", "distro", "arch", "command", "env", "fact", "not"}


def _name(value):
    return isinstance(value, str) and bool(value.strip()) and "\x00" not in value


def validate(condition):
    if not isinstance(condition, dict) or not condition:
        raise ConditionError("condition must be a nonempty dictionary")
    if any(key not in KEYS for key in condition):
        raise ConditionError(
            "unknown condition key; expected {}".format(", ".join(sorted(KEYS)))
        )
    for key, value in condition.items():
        if key == "not":
            validate(value)
            continue
        alternatives = value if isinstance(value, list) else [value]
        if not alternatives:
            raise ConditionError("{} alternatives cannot be empty".format(key))
        for item in alternatives:
            if key in ("os", "distro", "arch", "command"):
                if not _name(item):
                    raise ConditionError(
                        "{} expects a nonempty string or list of strings".format(key)
                    )
            elif key == "env":
                if not _name(item) and not (
                    isinstance(item, dict)
                    and set(item) == {"name", "equals"}
                    and _name(item["name"])
                    and isinstance(item["equals"], str)
                ):
                    raise ConditionError(
                        "env expects a name or {name, equals} string comparison"
                    )
            else:
                if not isinstance(item, dict) or not _name(item.get("name")):
                    raise ConditionError(
                        "fact expects a dictionary with a nonempty name"
                    )
                if set(item) not in ({"name"}, {"name", "equals"}, {"name", "matches"}):
                    raise ConditionError(
                        "fact accepts name and at most one of equals or matches"
                    )
                if "matches" in item:
                    try:
                        matches("0", item["matches"])
                    except (ValueError, TypeError) as exc:
                        raise ConditionError(
                            "invalid fact version constraint: {}".format(exc)
                        ) from exc
