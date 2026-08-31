import pytest
from fastapi.testclient import TestClient
from main import app, history  # or whatever your app module is
from models import CalculatorLog, Expression

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_history():
    """Every test starts with an empty history."""
    history.clear()
    yield
    history.clear()


# ---------- POST /calculate ----------

def test_basic_division():
    r = client.post("/calculate", json={"expr": "30/4"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert abs(data["result"] - 7.5) < 1e-9


def test_percent_subtraction():
    r = client.post("/calculate", json={"expr": "100 - 6%"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert abs(data["result"] - 94.0) < 1e-9


def test_standalone_percent():
    r = client.post("/calculate", json={"expr": "6%"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert abs(data["result"] - 0.06) < 1e-9


def test_invalid_expr_returns_ok_false():
    r = client.post("/calculate", json={"expr": "2**(3"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is False
    assert "error" in data and data["error"] != ""


def test_calculate_rejects_body_without_expr():
    """The Expression body requires an expr field, otherwise FastAPI returns 422."""
    r = client.post("/calculate", json={})
    assert r.status_code == 422


def test_calculate_rejects_plain_query_param():
    """The old ?expr= query-param form is no longer accepted."""
    r = client.post("/calculate", params={"expr": "1+1"})
    assert r.status_code == 422


# ---------- Expression model ----------

def test_expression_expand_percent_expands_the_symbol():
    """The Expression object expands % through its own method."""
    assert Expression(expr="100 - 6%").expand_percent() == "100 - ((6/100)*100)"


def test_expression_expand_percent_leaves_plain_expression_alone():
    assert Expression(expr="2 + 3 * 4").expand_percent() == "2 + 3 * 4"


# ---------- GET /history ----------

def test_history_is_empty_at_start():
    """With nothing calculated yet, the history comes back empty."""
    r = client.get("/history")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["count"] == 0
    assert data["items"] == []


def test_history_records_calculations_newest_first():
    """Each successful calculation is stored, most recent one first."""
    client.post("/calculate", json={"expr": "1+1"})
    client.post("/calculate", json={"expr": "2+2"})
    client.post("/calculate", json={"expr": "3+3"})

    r = client.get("/history")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 3
    assert [item["expr"] for item in data["items"]] == ["3+3", "2+2", "1+1"]
    assert data["items"][0]["result"] == 6
    assert "timestamp" in data["items"][0]


def test_history_items_are_calculator_logs():
    """Every returned entry validates as a CalculatorLog."""
    client.post("/calculate", json={"expr": "30/4"})

    data = client.get("/history").json()
    logs = [CalculatorLog(**item) for item in data["items"]]
    assert len(logs) == 1
    assert logs[0].expr == "30/4"
    assert logs[0].result == 7.5
    assert logs[0].timestamp != ""


def test_history_entries_expose_only_the_log_fields():
    """A history entry carries exactly timestamp, expr and result."""
    client.post("/calculate", json={"expr": "1+1"})

    item = client.get("/history").json()["items"][0]
    assert set(item) == {"timestamp", "expr", "result"}


def test_history_stores_calculator_log_objects():
    """The in-memory history holds CalculatorLog objects, not plain dicts."""
    client.post("/calculate", json={"expr": "7*6"})

    assert len(history) == 1
    assert isinstance(history[0], CalculatorLog)
    assert history[0].result == 42


def test_history_limit_returns_only_n_items():
    """The limit query parameter caps how many entries are returned."""
    for i in range(5):
        client.post("/calculate", json={"expr": f"{i}+0"})

    r = client.get("/history", params={"limit": 2})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 2
    assert data["total"] == 5
    assert [item["expr"] for item in data["items"]] == ["4+0", "3+0"]


def test_history_skips_failed_calculations():
    """A calculation that fails must not end up in the history."""
    client.post("/calculate", json={"expr": "2**(3"})

    r = client.get("/history")
    assert r.status_code == 200
    assert r.json()["count"] == 0


def test_history_rejects_invalid_limit():
    """limit must be at least 1, otherwise FastAPI returns 422."""
    r = client.get("/history", params={"limit": 0})
    assert r.status_code == 422


# ---------- DELETE /history ----------

def test_delete_history_clears_entries():
    """Deleting removes everything and reports how many were cleared."""
    client.post("/calculate", json={"expr": "1+1"})
    client.post("/calculate", json={"expr": "2+2"})

    r = client.delete("/history")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["cleared"] == 2
    assert data["total"] == 0


def test_history_is_empty_after_delete():
    """A GET right after a DELETE returns nothing."""
    client.post("/calculate", json={"expr": "7*6"})
    client.delete("/history")

    r = client.get("/history")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_delete_empty_history_is_ok():
    """Clearing an already empty history is not an error."""
    r = client.delete("/history")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["cleared"] == 0


def test_delete_then_calculate_starts_fresh():
    """New calculations after a DELETE build a brand new history."""
    client.post("/calculate", json={"expr": "1+1"})
    client.delete("/history")
    client.post("/calculate", json={"expr": "10/2"})

    r = client.get("/history")
    data = r.json()
    assert data["count"] == 1
    assert data["items"][0]["expr"] == "10/2"
    assert data["items"][0]["result"] == 5
