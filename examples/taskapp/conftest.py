"""Shared fixtures.

Idea: tests should never depend on a server someone started by hand.
So the suite starts the app itself on a free port, with a throwaway DB,
and resets the data before every test so tests are independent.
"""
import os
import socket
import subprocess
import sys
import tempfile
import time

import pytest
import requests


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def base_url():  # also overrides pytest-playwright's base_url, so page.goto("/") works
    port = _free_port()
    # ignore_cleanup_errors: on Windows the DB file can stay locked for a moment after the server stops
    tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    env = {**os.environ, "TASKAPP_DB": os.path.join(tmp.name, "test.db"), "TASKAPP_TESTING": "1"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
        env=env,
    )
    url = f"http://127.0.0.1:{port}"
    for _ in range(50):  # wait until the server answers (max ~10s)
        try:
            requests.get(url + "/tasks", timeout=0.5)
            break
        except requests.ConnectionError:
            time.sleep(0.2)
    else:
        proc.kill()
        raise RuntimeError("app did not start")
    yield url
    proc.terminate()
    proc.wait()
    tmp.cleanup()


@pytest.fixture(autouse=True)
def clean_db(base_url):
    requests.post(base_url + "/_reset")


@pytest.fixture
def api(base_url):
    """Tiny API client so tests read like sentences."""
    class Api:
        def __init__(self):
            self.s = requests.Session()

        def _u(self, p):
            return base_url + p

        def create(self, title="Buy milk", **kw):
            return self.s.post(self._u("/tasks"), json={"title": title, **kw})

        def list(self, **params):
            return self.s.get(self._u("/tasks"), params=params)

        def get(self, i):
            return self.s.get(self._u(f"/tasks/{i}"))

        def patch(self, i, **body):
            return self.s.patch(self._u(f"/tasks/{i}"), json=body)

        def delete(self, i):
            return self.s.delete(self._u(f"/tasks/{i}"))

    return Api()
