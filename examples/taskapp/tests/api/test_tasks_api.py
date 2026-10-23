"""API tests. Organised by what we're checking, not by endpoint:
happy path -> validation (negative) -> boundaries -> state/side effects."""
import pytest

pytestmark = pytest.mark.api


# ---------- happy path ----------
def test_create_task_returns_201_and_defaults(api):
    r = api.create("Buy milk")
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Buy milk"
    assert body["priority"] == "medium"  # default
    assert body["done"] is False
    assert isinstance(body["id"], int)


def test_get_task_returns_what_was_created(api):
    created = api.create("Read book", priority="low").json()
    r = api.get(created["id"])
    assert r.status_code == 200
    assert r.json() == created


def test_list_returns_tasks_in_creation_order(api):
    for t in ["a", "b", "c"]:
        api.create(t)
    assert [t["title"] for t in api.list().json()] == ["a", "b", "c"]


def test_update_marks_task_done(api):
    tid = api.create("Write tests").json()["id"]
    r = api.patch(tid, done=True)
    assert r.status_code == 200
    assert r.json()["done"] is True
    assert api.get(tid).json()["done"] is True  # persisted, not just echoed


def test_delete_removes_task(api):
    tid = api.create("Temp").json()["id"]
    assert api.delete(tid).status_code == 204
    assert api.get(tid).status_code == 404


# ---------- validation (negative tests) ----------
@pytest.mark.parametrize(
    "payload",
    [
        {},                                 # missing title
        {"title": ""},                      # empty
        {"title": "   "},                   # whitespace only
        {"title": "x" * 101},               # too long
        {"title": "ok", "priority": "urgent"},  # not in allowed set
        {"title": 123},                     # wrong type
    ],
    ids=["missing-title", "empty", "whitespace", "too-long", "bad-priority", "wrong-type"],
)
def test_create_rejects_invalid_payload(api, payload):
    r = api.s.post(api._u("/tasks"), json=payload)
    assert r.status_code == 422
    assert api.list().json() == []  # and nothing was saved


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_unknown_id_returns_404(api, method):
    r = {"get": lambda: api.get(9999), "patch": lambda: api.patch(9999, done=True), "delete": lambda: api.delete(9999)}[method]()
    assert r.status_code == 404


def test_non_integer_id_returns_422(api):
    assert api.s.get(api._u("/tasks/abc")).status_code == 422


def test_update_rejects_invalid_priority(api):
    tid = api.create("x").json()["id"]
    assert api.patch(tid, priority="nope").status_code == 422
    assert api.get(tid).json()["priority"] == "medium"  # unchanged


# ---------- boundaries ----------
@pytest.mark.parametrize("length", [1, 100])
def test_title_length_boundaries_accepted(api, length):
    assert api.create("x" * length).status_code == 201


def test_title_is_trimmed(api):
    assert api.create("  padded  ").json()["title"] == "padded"


def test_special_characters_stored_verbatim(api):
    title = "<script>alert(1)</script> & 'quotes' \"double\" ünïcödé 🚀"
    assert api.get(api.create(title).json()["id"]).json()["title"] == title


# ---------- filtering & state ----------
def test_filter_by_done(api):
    a = api.create("open").json()["id"]
    b = api.create("closed").json()["id"]
    api.patch(b, done=True)
    assert [t["id"] for t in api.list(done="true").json()] == [b]
    assert [t["id"] for t in api.list(done="false").json()] == [a]


def test_partial_update_does_not_touch_other_fields(api):
    t = api.create("keep me", priority="high").json()
    after = api.patch(t["id"], done=True).json()
    assert after["title"] == "keep me" and after["priority"] == "high"


def test_deleted_task_not_in_listing(api):
    first = api.create("one").json()["id"]
    api.create("two")
    api.delete(first)
    assert [t["title"] for t in api.list().json()] == ["two"]


# ---------- gaps found by TestForge mutation run (hand-written v1 scored 82.6%) ----------
def test_update_priority_alone(api):
    """Survivor: no test patched a task WITHOUT sending 'done'."""
    tid = api.create("x").json()["id"]
    r = api.patch(tid, priority="high")
    assert r.status_code == 200 and r.json()["priority"] == "high"


def test_update_title_alone(api):
    tid = api.create("old").json()["id"]
    assert api.patch(tid, title="new").json()["title"] == "new"


@pytest.mark.parametrize("title,expected", [("x", 200), ("x" * 100, 200), ("", 422), ("x" * 101, 422)])
def test_update_title_length_rules(api, title, expected):
    """Survivor: length limits were only tested on create, not on update."""
    tid = api.create("x").json()["id"]
    assert api.patch(tid, title=title).status_code == expected
