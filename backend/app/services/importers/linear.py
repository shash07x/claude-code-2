"""Linear CSV export adapter.

Linear exports use ``Title`` + ``Description`` with ``Status`` (workflow state)
and ``Priority``. Priority comes through either as a label
(Urgent/High/Medium/Low/No priority) or, in some exports, as the numeric code
Linear uses internally (0=none, 1=urgent, 2=high, 3=medium, 4=low) — both are
handled.
"""
from __future__ import annotations

from .base import FormatAdapter


class LinearAdapter(FormatAdapter):
    source = "linear"
    label = "Linear"
    detect_field = "title"  # checked after Jira/Trello in the registry

    title_field = "title"
    description_field = "description"
    status_field = "status"
    priority_field = "priority"

    status_map = {
        "backlog": "backlog",
        "todo": "backlog",
        "to do": "backlog",
        "triage": "backlog",
        "unstarted": "backlog",
        "in progress": "in_progress",
        "started": "in_progress",
        "in review": "review",
        "review": "review",
        "done": "done",
        "completed": "done",
        "canceled": "done",
        "cancelled": "done",
        "duplicate": "done",
    }
    priority_map = {
        "urgent": "urgent",
        "high": "high",
        "medium": "medium",
        "low": "low",
        "no priority": "medium",
        "none": "medium",
        # Numeric form (Linear's internal codes).
        "0": "medium",
        "1": "urgent",
        "2": "high",
        "3": "medium",
        "4": "low",
    }
