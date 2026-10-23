# AI usage log

How I used AI on this project, and how I checked its work.

## How I used it
- Drafted the app, fixtures and first-pass tests with an AI assistant, starting from a plain-English list of what to cover.
- I then read every test and asked "if the app had bug X, would this fail?" instead of trusting green checkmarks.

## Where the AI output was wrong or weak (and what I did)
| # | Problem | How it was found | Fix |
|---|---------|------------------|-----|
| 1 | A test ended with `assert second != first or True`, which can never fail. | Code review: asked "can this assertion ever fail?" | Replaced with a real check that the deleted task is gone from the list. |
| 2 | Flaky UI test (`test_delete_task_removes_it`) failed ~1 in 10 runs. | Showed up after a mutation-testing run. Re-ran it in a loop. | Root cause: two quick adds raced, because the first response cleared the input while the second title was being typed. The helper now waits for the visible result of each add. Then 12/12 clean runs. |
| 3 | Green tests don't prove the tests are good. | Mutation check: broke the app on purpose 3 ways. | All 3 bugs were caught, so the assertions do real work. |

## Side finding about the app
The UI race in #2 is a real (minor) bug for fast users: the input is cleared after the server responds, so text typed in the meantime is lost. Fix would be to clear the input on submit and restore it on failure. Left as-is deliberately, since it is what exposed the flaky test.

## Rules I follow
- AI drafts, I review. Every generated test gets the question "what bug would make this fail?"
- No sleeps. Wait for observable state.
- If a test is flaky, find the cause. Never just add retries.
