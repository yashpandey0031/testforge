"""Load test: simulates users who create, read, complete and delete tasks.
Run headless:  TASKAPP_TESTING=1 uvicorn app.main:app &
               locust -f load/locustfile.py --headless -u 20 -r 5 -t 20s --host http://127.0.0.1:8000
"""
import random

from locust import HttpUser, between, task


class TaskUser(HttpUser):
    wait_time = between(0.1, 0.5)  # think time between actions, like a real user

    @task(5)  # weight: reads are the most common action
    def list_tasks(self):
        self.client.get("/tasks", name="GET /tasks")

    @task(2)
    def create_then_complete(self):
        r = self.client.post("/tasks", json={"title": f"load-{random.randint(1, 10**6)}"}, name="POST /tasks")
        if r.ok:
            tid = r.json()["id"]
            self.client.patch(f"/tasks/{tid}", json={"done": True}, name="PATCH /tasks/{id}")
            self.client.delete(f"/tasks/{tid}", name="DELETE /tasks/{id}")
