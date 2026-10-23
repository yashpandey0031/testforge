# Task App QA — AI-assisted test automation framework

A small task-manager web app (FastAPI + SQLite + one HTML page) and the test framework around it:
**API tests** (pytest + requests), **UI end-to-end tests** (Playwright), **load test** (Locust), and **CI** (GitHub Actions).
The app is intentionally tiny. The project is about the tests: how they are designed, how stable they are, and how AI was used and checked.

## Run it
```bash
pip install -r requirements-test.txt
playwright install chromium
pytest                      # everything (~8s)
pytest -m api               # API only, no browser (~1s)
pytest -m ui --headed       # watch the browser
pytest --html=report.html --self-contained-html
```
Load test: see the docstring at the top of `load/locustfile.py`.

## Layout
```
app/                  system under test (API + static page)
conftest.py           starts the app on a free port with a temp DB; resets data before each test; small API client
tests/api/            CRUD, validation, boundaries, filtering
tests/ui/             add / complete / delete / error state / XSS / API-UI consistency
load/locustfile.py    weighted user flow: 5x list, 2x create->update->delete
.github/workflows/    CI: install, run, upload HTML report
AI_LOG.md             where AI helped, where it was wrong, how I caught it
```

## Design decisions (the "why")
1. **Self-contained suite.** `conftest.py` boots the server itself, so `pytest` works on any machine and in CI with no manual steps.
2. **Independent tests.** Data is reset before every test through a test-only `/_reset` endpoint that exists only when `TASKAPP_TESTING=1`. No test depends on another's leftovers.
3. **Test pyramid.** Most checks are API tests (fast, precise). UI tests cover only what needs a browser: rendering, clicking, persistence after reload, XSS escaping.
4. **Tests grouped by purpose** (happy path, negative, boundary, state), and `parametrize` for table-style cases such as invalid payloads.
5. **Check persistence, not just the response.** After an update the test re-fetches. After a UI action it reloads the page.
6. **Locators by role/label,** not position or styling, so UI tests survive a redesign.
7. **Wait on state, never sleep.** See the flaky-test story in `AI_LOG.md`.
8. **Tests are checked too.** I injected three bugs into the app (blank titles accepted, max length changed, inverted filter). The suite caught all three.

## Results
- 30 tests (23 API cases incl. parametrized, 7 UI), all passing; UI suite run 12 times in a row with 0 failures.
- Load test, 20 users for 15s on a laptop-class container: ~100 req/s, 0 failures, p95 ≤ 11 ms on all endpoints.
  (Numbers are for a tiny SQLite app and only show the setup works; they say nothing about Cvent-scale systems.)

## Possible extensions
Auth tests, contract tests from the OpenAPI spec (`/openapi.json`), a performance gate in CI, an LLM-eval suite if an AI feature is added.
