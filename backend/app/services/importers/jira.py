"""Jira CSV export adapter.

Jira's "Export to CSV" uses ``Summary`` for the title and a ``Description``
column, with workflow ``Status`` and ``Priority`` columns. The default Jira
priority scheme is Highest/High/Medium/Low/Lowest; statuses are workflow-defined
but the common defaults map cleanly onto our four columns.
"""
from __future__ import annotations

from .base import FormatAdapter


class JiraAdapter(FormatAdapter):
    source = "jira"
    label = "Jira"
    detect_field = "summary"  # Jira-specific (Linear uses "title")

    title_field = "summary"
    description_field = "description"
    status_field = "status"
    priority_field = "priority"

    status_map = {
        "to do": "backlog",
        "to-do": "backlog",
        "todo": "backlog",
        "open": "backlog",
        "reopened": "backlog",
        "backlog": "backlog",
        "selected for development": "backlog",
        "in progress": "in_progress",
        "in development": "in_progress",
        "in review": "review",
        "code review": "review",
        "review": "review",
        "in qa": "review",
        "qa": "review",
        "done": "done",
        "closed": "done",
        "resolved": "done",
        "complete": "done",
        "completed": "done",
    }
    priority_map = {
        "highest": "urgent",
        "blocker": "urgent",
        "critical": "urgent",
        "high": "high",
        "medium": "medium",
        "low": "low",
        "lowest": "low",
        "trivial": "low",
        "minor": "low",
    }
