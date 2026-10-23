"""UI end-to-end tests with Playwright.
Rule used: find elements by role/label/stable CSS class, never by position or text that may change."""
import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.ui


def add_task(page: Page, title: str, priority: str = "medium"):
    """Add a task and WAIT until the page has finished reacting (input cleared or error shown).
    Without this wait, back-to-back adds raced: the first response cleared the input
    while the second title was being typed (found as a flaky test, ~1 in 10 runs)."""
    box = page.get_by_label("Task title")
    box.fill(title)
    page.get_by_label("Priority").select_option(priority)
    page.get_by_role("button", name="Add").click()
    if title.strip():
        expect(box).to_have_value("")
        expect(page.locator("#task-list li", has_text=title.strip()).first).to_be_visible()
    else:
        expect(page.get_by_role("alert")).not_to_be_empty()


def test_empty_state_is_shown(page: Page, base_url):
    page.goto(base_url)
    expect(page.locator("#empty")).to_be_visible()


def test_add_task_appears_in_list_and_clears_input(page: Page, base_url):
    page.goto(base_url)
    add_task(page, "Buy milk", "high")
    item = page.locator("#task-list li")
    expect(item).to_have_count(1)
    expect(item.locator(".title")).to_have_text("Buy milk")
    expect(item.locator(".prio")).to_have_text("[high]")
    expect(page.get_by_label("Task title")).to_have_value("")
    expect(page.locator("#empty")).to_be_hidden()


def test_blank_title_shows_error_and_adds_nothing(page: Page, base_url):
    page.goto(base_url)
    add_task(page, "   ")
    expect(page.get_by_role("alert")).to_contain_text("Title is required")
    expect(page.locator("#task-list li")).to_have_count(0)


def test_complete_task_strikes_it_through_and_persists(page: Page, base_url):
    page.goto(base_url)
    add_task(page, "Write tests")
    page.get_by_label("Complete").check()
    expect(page.locator("#task-list li")).to_have_class("done")
    page.reload()  # proves it was saved on the server, not just styled in the browser
    expect(page.get_by_label("Complete")).to_be_checked()


def test_delete_task_removes_it(page: Page, base_url):
    page.goto(base_url)
    add_task(page, "one")
    add_task(page, "two")
    expect(page.locator("#task-list li")).to_have_count(2)
    page.locator("#task-list li", has_text="one").get_by_role("button", name="Delete").click()
    expect(page.locator("#task-list li")).to_have_count(1)
    expect(page.locator(".title")).to_have_text("two")


def test_html_in_title_is_escaped_not_executed(page: Page, base_url):
    """Security-minded check: titles must render as text (no XSS)."""
    page.goto(base_url)
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    add_task(page, "<img src=x onerror=alert(1)>")
    expect(page.locator(".title")).to_have_text("<img src=x onerror=alert(1)>")
    assert dialogs == []


def test_tasks_created_via_api_show_in_ui(page: Page, base_url, api):
    """Cross-layer check: API and UI see the same data."""
    api.create("from api", priority="low")
    page.goto(base_url)
    expect(page.locator(".title")).to_have_text("from api")
