import pytest
import requests

# targets bug #7
def test_delete_task_success_status_204(base_url):
    # create a task
    r = requests.post(f"{base_url}/tasks", json={"title": "Task to delete"})
    assert r.status_code == 201
    task = r.json()
    task_id = task["id"]

    # delete it – should return 204
    del_resp = requests.delete(f"{base_url}/tasks/{task_id}")
    assert del_resp.status_code == 204

    # verify it is really gone
    get_resp = requests.get(f"{base_url}/tasks/{task_id}")
    assert get_resp.status_code == 404


# targets bug #9
def test_update_task_without_done_field(base_url):
    # create a task with default done=False
    r = requests.post(f"{base_url}/tasks", json={"title": "Update test"})
    assert r.status_code == 201
    task = r.json()
    task_id = task["id"]
    assert task.get("done") is False

    # patch without providing "done"
    patch_resp = requests.patch(
        f"{base_url}/tasks/{task_id}",
        json={"title": "Updated title"},
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["title"] == "Updated title"
    assert updated.get("done") is False

    # re‑read to be sure the change persisted
    get_resp = requests.get(f"{base_url}/tasks/{task_id}")
    assert get_resp.status_code == 200
    fetched = get_resp.json()
    assert fetched["title"] == "Updated title"
    assert fetched.get("done") is False


# targets bug #10
def test_delete_task_success_raises_no_404(base_url):
    # create a task
    r = requests.post(f"{base_url}/tasks", json={"title": "Another delete"})
    assert r.status_code == 201
    task_id = r.json()["id"]

    # delete it – should succeed, not raise 404
    del_resp = requests.delete(f"{base_url}/tasks/{task_id}")
    assert del_resp.status_code == 204

    # confirm deletion
    assert requests.get(f"{base_url}/tasks/{task_id}").status_code == 404


# targets bug #11
def test_delete_task_returns_204_not_205(base_url):
    r = requests.post(f"{base_url}/tasks", json={"title": "Status code test"})
    assert r.status_code == 201
    task_id = r.json()["id"]

    del_resp = requests.delete(f"{base_url}/tasks/{task_id}")
    # spec says 204; bug returns 205
    assert del_resp.status_code == 204


# targets bug #14
def test_update_task_title_min_length_one(base_url):
    # create a task
    r = requests.post(f"{base_url}/tasks", json={"title": "Original"})
    assert r.status_code == 201
    task_id = r.json()["id"]

    # update title to a single character (min length = 1 per spec)
    patch_resp = requests.patch(
        f"{base_url}/tasks/{task_id}",
        json={"title": "X"},
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["title"] == "X"

    # verify persistence
    get_resp = requests.get(f"{base_url}/tasks/{task_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["title"] == "X"


# targets bug #16
def test_create_task_whitespace_title_is_invalid(base_url):
    # title consisting only of spaces should be rejected with 422
    resp = requests.post(f"{base_url}/tasks", json={"title": "   "})
    assert resp.status_code == 422

    # ensure nothing was created
    list_resp = requests.get(f"{base_url}/tasks")
    assert list_resp.status_code == 200
    assert list_resp.json() == []


# targets bug #18
def test_get_nonexistent_task_returns_404(base_url):
    # assume 9999 does not exist in a fresh DB
    resp = requests.get(f"{base_url}/tasks/9999")
    assert resp.status_code == 404


# targets bug #22
def test_delete_nonexistent_task_returns_404(base_url):
    # delete a task that never existed
    resp = requests.delete(f"{base_url}/tasks/9999")
    assert resp.status_code == 404
