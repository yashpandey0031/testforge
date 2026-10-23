"""Pipeline logic tested with a FAKE LLM (no network, no API key)."""
import json
import shutil
from pathlib import Path

import pytest
from testforge.generate import extract_code, validate
from testforge.pipeline import auto

EX = Path(__file__).resolve().parent.parent / "examples" / "taskapp"

ROUND1 = '''```python
import pytest, requests

def test_create_returns_201(base_url):
    r = requests.post(base_url + "/tasks", json={"title": "a"})
    assert r.status_code == 201 and r.json()["title"] == "a"

def test_create_blank_rejected(base_url):
    assert requests.post(base_url + "/tasks", json={"title": ""}).status_code == 422

def test_hallucinated_wrong_status(base_url):
    # WRONG on purpose: real API returns 201. The validator must throw this one away.
    assert requests.post(base_url + "/tasks", json={"title": "a"}).status_code == 200
```'''

ROUND2 = '''```python
import pytest, requests

# targets bug #N
def test_patch_priority_alone(base_url):
    t = requests.post(base_url + "/tasks", json={"title": "a"}).json()
    r = requests.patch(f"{base_url}/tasks/{t['id']}", json={"priority": "high"})
    assert r.status_code == 200 and r.json()["priority"] == "high"

def test_delete_then_404(base_url):
    t = requests.post(base_url + "/tasks", json={"title": "a"}).json()
    assert requests.delete(f"{base_url}/tasks/{t['id']}").status_code == 204
    assert requests.get(f"{base_url}/tasks/{t['id']}").status_code == 404

def test_patch_done_persists(base_url):
    t = requests.post(base_url + "/tasks", json={"title": "a"}).json()
    requests.patch(f"{base_url}/tasks/{t['id']}", json={"done": True})
    assert requests.get(f"{base_url}/tasks/{t['id']}").json()["done"] is True

def test_unknown_id_404(base_url):
    assert requests.get(base_url + "/tasks/999").status_code == 404
```'''


class FakeProvider:
    name = "fake"

    def __init__(self):
        self.prompts = []

    def complete(self, prompt):
        self.prompts.append(prompt)
        return ROUND2 if "SURVIVING BUGS" in prompt else ROUND1


@pytest.fixture
def project(tmp_path):
    dst = tmp_path / "taskapp"
    shutil.copytree(EX, dst, ignore=shutil.ignore_patterns("__pycache__", "*.db", ".pytest_cache"))
    shutil.rmtree(dst / "tests" / "api"); shutil.rmtree(dst / "tests" / "ui")  # start with NO tests of its own
    return dst


def test_extract_code_strips_markdown_fence():
    assert extract_code("blah\n```python\nx = 1\n```\nbye") == "x = 1\n"
    assert extract_code("x = 1") == "x = 1\n"


def test_full_loop_discards_bad_test_and_improves_score(project):
    fake = FakeProvider()
    out = auto(fake, project, "app/main.py", json.load(open(project / "openapi.json")),
               max_mutants=12, seed=3, report_path=str(project / "r.html"), progress=lambda *_: None)
    assert out["round1"]["discarded"] == ["test_hallucinated_wrong_status"]   # validator caught it
    assert out["round1"]["kept"] == 2
    assert out["after"] > out["before"]                                       # feedback loop helped
    assert "SURVIVING BUGS" in fake.prompts[1] and "line" in fake.prompts[1]  # survivors reached the model
    assert (project / "r.html").read_text().count("class='card'") == 2        # report shows before + after


def test_validate_reports_unparseable_output(project):
    p = project / "tests" / "generated"; p.mkdir(parents=True); (p / "__init__.py").touch()
    f = p / "test_x.py"; f.write_text("def test_a(:\n")
    assert "not valid Python" in validate(str(project), str(f))["error"]
