"""Concise apply results, including partial success and blocked work."""

from etchlib.output import action_lines

from .results import ExecutionReport, Status


def render_apply(report: ExecutionReport) -> str:
    lines: list[str] = []
    current_module = None
    for result in report.actions:
        if result.node.module != current_module:
            if lines:
                lines.append("")
            current_module = result.node.module
            lines.append("{}:".format(current_module))
        lines.extend(
            action_lines(result.status.value.upper(), result.description, "  ")
        )
        for ref in result.refreshed:
            lines.append(
                "  REFRESH {}.{}: invalidated; gathered only when requested".format(
                    ref.module or "global", ref.name
                )
            )
    if report.warnings or report.error:
        lines.append("")
    lines.extend("Warning: " + warning for warning in report.warnings)
    if report.error:
        lines.append("FAIL: " + report.error)
    counts = {
        status: sum(result.status is status for result in report.actions)
        for status in Status
    }
    summary = (
        ", ".join(
            "{} {}".format(count, status.value)
            for status, count in counts.items()
            if count
        )
        or "no actions"
    )
    lines.append("")
    lines.append(
        "Apply {}: {}".format(
            "complete" if report.succeeded else "failed",
            summary,
        )
    )
    return "\n".join(lines)
