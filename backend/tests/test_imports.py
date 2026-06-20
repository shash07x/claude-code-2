"""Tests for the CSV bulk importer (Jira / Linear / Trello)."""
from __future__ import annotations

from app.core.config import settings

BASE = settings.API_V1_PREFIX + "/imports"
ISSUES_BASE = settings.API_V1_PREFIX + "/issues"
AUTH_BASE = settings.API_V1_PREFIX + "/auth"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _signup(client, email="user@example.com", password="Password123"):
    r = await client.post(
        f"{AUTH_BASE}/signup",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _preview(client, token, csv_text, source=None):
    return await client.post(
        f"{BASE}/preview",
        headers=_headers(token),
        json={"csv_text": csv_text, "source": source},
    )


async def _commit(client, token, csv_text, source=None):
    return await client.post(
        f"{BASE}/commit",
        headers=_headers(token),
        json={"csv_text": csv_text, "source": source},
    )


async def _board(client, token) -> dict[str, list[dict]]:
    r = await client.get(f"{ISSUES_BASE}/board", headers=_headers(token))
    assert r.status_code == 200, r.text
    return {col["status"]: col["items"] for col in r.json()["columns"]}


# Sample exports -------------------------------------------------------------

JIRA_CSV = (
    "Issue key,Summary,Description,Status,Priority,Assignee\n"
    "PROJ-1,Build login,Implement auth,In Progress,High,alice\n"
    "PROJ-2,Fix navbar,,Done,Lowest,bob\n"
    "PROJ-3,Write docs,Cover the API,To Do,Medium,carol\n"
)

LINEAR_CSV = (
    "ID,Title,Description,Status,Priority,Estimate\n"
    "TEA-1,Refactor store,Split reducers,In Progress,Urgent,3\n"
    "TEA-2,Add dark mode,,Backlog,No priority,2\n"
)

TRELLO_CSV = (
    "Card Name,Card Description,List Name,Labels\n"
    "Design header,Mockups,In Review,high\n"
    "Plan sprint,,Backlog,urgent\n"
    "Ship release,Cut v1,Done Column,\n"
)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

async def test_preview_requires_auth(client, db_session):
    r = await client.post(f"{BASE}/preview", json={"csv_text": JIRA_CSV})
    assert r.status_code == 401


async def test_commit_requires_auth(client, db_session):
    r = await client.post(f"{BASE}/commit", json={"csv_text": JIRA_CSV})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Auto-detection
# ---------------------------------------------------------------------------

async def test_detect_jira(client, db_session):
    token = await _signup(client)
    r = await _preview(client, token, JIRA_CSV)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "jira"
    assert body["detected"] is True


async def test_detect_linear(client, db_session):
    token = await _signup(client)
    r = await _preview(client, token, LINEAR_CSV)
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "linear"


async def test_detect_trello(client, db_session):
    token = await _signup(client)
    r = await _preview(client, token, TRELLO_CSV)
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "trello"


async def test_undetectable_source_is_422(client, db_session):
    token = await _signup(client)
    r = await _preview(client, token, "Foo,Bar\n1,2\n")
    assert r.status_code == 422


async def test_explicit_source_overrides_detection(client, db_session):
    token = await _signup(client)
    # Force trello parsing of a generic CSV; no "card name" → titles missing.
    r = await _preview(client, token, "Card Name,List Name\nHello,Done\n", source="trello")
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "trello"
    assert body["detected"] is False


# ---------------------------------------------------------------------------
# Mapping correctness — per format
# ---------------------------------------------------------------------------

async def test_jira_mapping(client, db_session):
    token = await _signup(client)
    rows = (await _preview(client, token, JIRA_CSV)).json()["rows"]
    by_title = {r["title"]: r for r in rows}
    assert by_title["Build login"]["status"] == "in_progress"
    assert by_title["Build login"]["priority"] == "high"
    assert by_title["Build login"]["description"] == "Implement auth"
    assert by_title["Fix navbar"]["status"] == "done"
    assert by_title["Fix navbar"]["priority"] == "low"  # Lowest → low
    assert by_title["Fix navbar"]["description"] is None
    assert by_title["Write docs"]["status"] == "backlog"  # To Do → backlog


async def test_linear_mapping_handles_numeric_and_text_priority(client, db_session):
    token = await _signup(client)
    rows = (await _preview(client, token, LINEAR_CSV)).json()["rows"]
    by_title = {r["title"]: r for r in rows}
    assert by_title["Refactor store"]["status"] == "in_progress"
    assert by_title["Refactor store"]["priority"] == "urgent"
    # "No priority" → medium default.
    assert by_title["Add dark mode"]["priority"] == "medium"
    assert by_title["Add dark mode"]["status"] == "backlog"


async def test_trello_status_from_list_and_priority_from_labels(client, db_session):
    token = await _signup(client)
    rows = (await _preview(client, token, TRELLO_CSV)).json()["rows"]
    by_title = {r["title"]: r for r in rows}
    assert by_title["Design header"]["status"] == "review"  # "In Review"
    assert by_title["Design header"]["priority"] == "high"  # label
    assert by_title["Plan sprint"]["status"] == "backlog"
    assert by_title["Plan sprint"]["priority"] == "urgent"
    assert by_title["Ship release"]["status"] == "done"  # "Done Column"
    assert by_title["Ship release"]["priority"] == "medium"  # no label → default


# ---------------------------------------------------------------------------
# Validation + diagnostics
# ---------------------------------------------------------------------------

async def test_missing_title_row_is_invalid(client, db_session):
    token = await _signup(client)
    csv = "Summary,Status\n,Done\nReal title,To Do\n"
    body = (await _preview(client, token, csv, source="jira")).json()
    assert body["total_rows"] == 2
    assert body["valid_rows"] == 1
    assert body["invalid_rows"] == 1
    invalid = [r for r in body["rows"] if not r["valid"]]
    assert len(invalid) == 1
    assert invalid[0]["errors"]


async def test_unknown_status_warns_and_defaults(client, db_session):
    token = await _signup(client)
    csv = "Summary,Status\nThing,Frozen\n"
    row = (await _preview(client, token, csv, source="jira")).json()["rows"][0]
    assert row["status"] == "backlog"
    assert row["valid"] is True
    assert any("status" in w.lower() for w in row["warnings"])


async def test_title_truncated_with_warning(client, db_session):
    token = await _signup(client)
    long = "x" * 300
    csv = f"Summary,Status\n{long},To Do\n"
    row = (await _preview(client, token, csv, source="jira")).json()["rows"][0]
    assert len(row["title"]) == 255
    assert any("truncat" in w.lower() for w in row["warnings"])


async def test_unmapped_columns_reported(client, db_session):
    token = await _signup(client)
    body = (await _preview(client, token, JIRA_CSV)).json()
    # "Assignee" and "Issue key" have no home in the Issue model.
    assert "Assignee" in body["unmapped_columns"]
    assert "Issue key" in body["unmapped_columns"]
    # Mapped columns are not reported as unmapped.
    assert "Summary" not in body["unmapped_columns"]


async def test_blank_lines_skipped(client, db_session):
    token = await _signup(client)
    csv = "Summary,Status\nA,To Do\n,\nB,Done\n"
    body = (await _preview(client, token, csv, source="jira")).json()
    assert body["total_rows"] == 2


async def test_preview_does_not_write(client, db_session):
    token = await _signup(client)
    await _preview(client, token, JIRA_CSV)
    board = await _board(client, token)
    assert all(items == [] for items in board.values())


# ---------------------------------------------------------------------------
# Commit
# ---------------------------------------------------------------------------

async def test_commit_creates_issues_on_board(client, db_session):
    token = await _signup(client)
    r = await _commit(client, token, JIRA_CSV)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 3
    assert body["skipped"] == 0

    board = await _board(client, token)
    assert [i["title"] for i in board["in_progress"]] == ["Build login"]
    assert [i["title"] for i in board["done"]] == ["Fix navbar"]
    assert [i["title"] for i in board["backlog"]] == ["Write docs"]


async def test_commit_appends_and_reindexes_within_column(client, db_session):
    token = await _signup(client)
    # Seed an existing backlog card, then import two more backlog rows.
    await client.post(
        ISSUES_BASE, headers=_headers(token), json={"title": "Existing"}
    )
    csv = "Summary,Status\nFirst,To Do\nSecond,To Do\n"
    await _commit(client, token, csv, source="jira")

    backlog = (await _board(client, token))["backlog"]
    assert [i["title"] for i in backlog] == ["Existing", "First", "Second"]
    assert [i["position"] for i in backlog] == [0, 1, 2]


async def test_commit_skips_invalid_rows(client, db_session):
    token = await _signup(client)
    csv = "Summary,Status\n,Done\nGood,To Do\n"
    body = (await _commit(client, token, csv, source="jira")).json()
    assert body["imported"] == 1
    assert body["skipped"] == 1
    board = await _board(client, token)
    assert [i["title"] for i in board["backlog"]] == ["Good"]


async def test_commit_isolated_per_user(client, db_session):
    token_a = await _signup(client, "a@example.com")
    token_b = await _signup(client, "b@example.com", password="Password456")
    await _commit(client, token_a, JIRA_CSV)

    board_b = await _board(client, token_b)
    assert all(items == [] for items in board_b.values())
