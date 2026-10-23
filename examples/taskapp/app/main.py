"""Tiny task-manager app. This is the *system under test* (SUT).
Kept deliberately small: the project is about the TESTS, not the app."""
import os
import sqlite3
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

DB_PATH = os.environ.get("TASKAPP_DB", "tasks.db")
app = FastAPI(title="Task App")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'medium',
            done INTEGER NOT NULL DEFAULT 0)"""
    )
    return conn


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    priority: Literal["low", "medium", "high"] = "medium"


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=100)
    priority: Optional[Literal["low", "medium", "high"]] = None
    done: Optional[bool] = None


def row_to_dict(r):
    return {"id": r["id"], "title": r["title"], "priority": r["priority"], "done": bool(r["done"])}


@app.get("/")
def home():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


@app.post("/tasks", status_code=201)
def create_task(task: TaskIn):
    title = task.title.strip()
    if not title:  # whitespace-only titles are invalid too
        raise HTTPException(422, "title must not be blank")
    with db() as c:
        cur = c.execute("INSERT INTO tasks (title, priority) VALUES (?, ?)", (title, task.priority))
        return row_to_dict(c.execute("SELECT * FROM tasks WHERE id=?", (cur.lastrowid,)).fetchone())


@app.get("/tasks")
def list_tasks(done: Optional[bool] = None):
    q, args = "SELECT * FROM tasks", ()
    if done is not None:
        q, args = q + " WHERE done=?", (int(done),)
    with db() as c:
        return [row_to_dict(r) for r in c.execute(q + " ORDER BY id", args).fetchall()]


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    with db() as c:
        r = c.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not r:
        raise HTTPException(404, "task not found")
    return row_to_dict(r)


@app.patch("/tasks/{task_id}")
def update_task(task_id: int, upd: TaskUpdate):
    fields = upd.model_dump(exclude_none=True)
    with db() as c:
        if not c.execute("SELECT 1 FROM tasks WHERE id=?", (task_id,)).fetchone():
            raise HTTPException(404, "task not found")
        if fields:
            if "done" in fields:
                fields["done"] = int(fields["done"])
            sets = ", ".join(f"{k}=?" for k in fields)
            c.execute(f"UPDATE tasks SET {sets} WHERE id=?", (*fields.values(), task_id))
        return row_to_dict(c.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    with db() as c:
        if c.execute("DELETE FROM tasks WHERE id=?", (task_id,)).rowcount == 0:
            raise HTTPException(404, "task not found")


# Test-support endpoint: only exists when TASKAPP_TESTING=1, so tests start from a clean DB.
if os.environ.get("TASKAPP_TESTING") == "1":  # pragma: no mutate

    @app.post("/_reset", status_code=204)
    def reset():
        with db() as c:
            c.execute("DELETE FROM tasks")
            c.execute("DELETE FROM sqlite_sequence WHERE name='tasks'")
