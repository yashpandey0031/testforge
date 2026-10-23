import pytest
import requests

def _list_tasks(base_url, params=None):
    """Return the JSON list of tasks."""
    resp = requests.get(f'{base_url}/tasks', params=params or {})
    assert resp.status_code == 200
    return resp.json()

def _create_task(base_url, payload):
    """Create a task and return the response."""
    return requests.post(f'{base_url}/tasks', json=payload)

def _get_task(base_url, task_id):
    """Get a single task."""
    return requests.get(f'{base_url}/tasks/{task_id}')

def _patch_task(base_url, task_id, payload):
    """Patch a task."""
    return requests.patch(f'{base_url}/tasks/{task_id}', json=payload)

def _delete_task(base_url, task_id):
    """Delete a task."""
    return requests.delete(f'{base_url}/tasks/{task_id}')

def test_create_task_success_minimal(base_url):
    payload = {'title': 'A task'}
    resp = _create_task(base_url, payload)
    assert resp.status_code == 201
    assert isinstance(resp.json(), dict)
    tasks = _list_tasks(base_url)
    assert any((t.get('title') == 'A task' and t.get('priority') == 'medium' for t in tasks))

def test_create_task_success_full(base_url):
    payload = {'title': 'Full task', 'priority': 'high'}
    resp = _create_task(base_url, payload)
    assert resp.status_code == 201
    tasks = _list_tasks(base_url)
    assert any((t.get('title') == 'Full task' and t.get('priority') == 'high' for t in tasks))

def test_create_task_title_boundary_min(base_url):
    payload = {'title': 'x'}
    resp = _create_task(base_url, payload)
    assert resp.status_code == 201
    tasks = _list_tasks(base_url)
    assert any((t.get('title') == 'x' for t in tasks))

def test_create_task_title_boundary_max(base_url):
    payload = {'title': 'a' * 100}
    resp = _create_task(base_url, payload)
    assert resp.status_code == 201
    tasks = _list_tasks(base_url)
    assert any((t.get('title') == 'a' * 100 for t in tasks))

def test_create_task_title_too_short(base_url):
    payload = {'title': ''}
    resp = _create_task(base_url, payload)
    assert resp.status_code == 422
    assert 'detail' in resp.json()
    assert _list_tasks(base_url) == []

def test_create_task_title_too_long(base_url):
    payload = {'title': 'b' * 101}
    resp = _create_task(base_url, payload)
    assert resp.status_code == 422
    assert 'detail' in resp.json()
    assert _list_tasks(base_url) == []

def test_create_task_missing_title(base_url):
    payload = {'priority': 'low'}
    resp = _create_task(base_url, payload)
    assert resp.status_code == 422
    assert 'detail' in resp.json()
    assert _list_tasks(base_url) == []

def test_create_task_invalid_priority(base_url):
    payload = {'title': 'Invalid priority', 'priority': 'urgent'}
    resp = _create_task(base_url, payload)
    assert resp.status_code == 422
    assert 'detail' in resp.json()
    assert _list_tasks(base_url) == []

def test_list_tasks_filter_done(base_url):
    t1 = _create_task(base_url, {'title': 'Task 1'}).json()
    t2 = _create_task(base_url, {'title': 'Task 2'}).json()
    task_id = _list_tasks(base_url)[0]['id']
    _patch_task(base_url, task_id, {'done': True})
    done_tasks = _list_tasks(base_url, params={'done': 'true'})
    assert all((task.get('done') is True for task in done_tasks))
    not_done_tasks = _list_tasks(base_url, params={'done': 'false'})
    assert all((task.get('done') is False for task in not_done_tasks))

def test_list_tasks_invalid_done_param(base_url):
    resp = requests.get(f'{base_url}/tasks', params={'done': 'notabool'})
    assert resp.status_code == 422
    assert 'detail' in resp.json()

def test_get_task_success(base_url):
    payload = {'title': 'Get me'}
    _create_task(base_url, payload)
    task = _list_tasks(base_url)[0]
    resp = _get_task(base_url, task['id'])
    assert resp.status_code == 200
    data = resp.json()
    assert data.get('title') == 'Get me'

def test_get_task_invalid_id_type(base_url):
    resp = requests.get(f'{base_url}/tasks/not-an-int')
    assert resp.status_code == 422
    assert 'detail' in resp.json()

def test_update_task_success(base_url):
    _create_task(base_url, {'title': 'Old', 'priority': 'low'})
    task = _list_tasks(base_url)[0]
    resp = _patch_task(base_url, task['id'], {'title': 'New', 'priority': 'high', 'done': True})
    assert resp.status_code == 200
    updated = _get_task(base_url, task['id']).json()
    assert updated.get('title') == 'New'
    assert updated.get('priority') == 'high'
    assert updated.get('done') is True

def test_update_task_partial_fields(base_url):
    _create_task(base_url, {'title': 'Partial'})
    task = _list_tasks(base_url)[0]
    resp = _patch_task(base_url, task['id'], {'done': True})
    assert resp.status_code == 200
    updated = _get_task(base_url, task['id']).json()
    assert updated.get('done') is True
    assert updated.get('title') == 'Partial'

def test_update_task_invalid_title_too_long(base_url):
    _create_task(base_url, {'title': 'Short'})
    task = _list_tasks(base_url)[0]
    resp = _patch_task(base_url, task['id'], {'title': 'c' * 101})
    assert resp.status_code == 422
    assert 'detail' in resp.json()
    unchanged = _get_task(base_url, task['id']).json()
    assert unchanged.get('title') == 'Short'

def test_update_task_invalid_priority(base_url):
    _create_task(base_url, {'title': 'Bad priority'})
    task = _list_tasks(base_url)[0]
    resp = _patch_task(base_url, task['id'], {'priority': 'urgent'})
    assert resp.status_code == 422
    assert 'detail' in resp.json()
    unchanged = _get_task(base_url, task['id']).json()
    assert unchanged.get('priority') == 'medium'

def test_update_task_invalid_id_type(base_url):
    resp = requests.patch(f'{base_url}/tasks/abc', json={'title': 'X'})
    assert resp.status_code == 422
    assert 'detail' in resp.json()

def test_delete_task_invalid_id_type(base_url):
    resp = requests.delete(f'{base_url}/tasks/xyz')
    assert resp.status_code == 422
    assert 'detail' in resp.json()
