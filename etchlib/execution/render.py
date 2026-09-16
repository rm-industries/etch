"""Concise apply results, including partial success and blocked work."""

from .results import ExecutionReport, Status


def render_apply(report: ExecutionReport) -> str:
    lines = []
    for result in report.actions:
        lines.append(
            "{} {}: {}".format(
                result.status.value.upper(), result.node, result.description
            )
        )
        for ref in result.refreshed:
            lines.append(
                "  REFRESH {}.{}: invalidated; gathered only when requested".format(
                    ref.module or "global", ref.name
                )
            )
    lines.extend("Warning: " + warning for warning in report.warnings)
    if report.error:
        lines.append("FAIL: " + report.error)
    counts = {
        status: sum(result.status is status for result in report.actions)
        for status in Status
    }
    lines.append(
        "Apply {}: {}".format(
            "complete" if report.succeeded else "failed",
            ", ".join(
                "{} {}".format(count, status.value) for status, count in counts.items()
            ),
        )
    )
    return "\n".join(lines)
