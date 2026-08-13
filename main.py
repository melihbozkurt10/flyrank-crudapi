import os
import sqlite3

from fastapi import FastAPI, Response
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel

DB_PATH = os.environ.get(
    "TASKS_DB", os.path.join(os.path.dirname(__file__), "tasks.db")
)

SEED = [
    {"id": 1, "title": "Read the assignment", "done": True},
    {"id": 2, "title": "Build the CRUD API", "done": False},
    {"id": 3, "title": "Push to GitHub", "done": False},
]


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


db = connect()


def init_db() -> None:
    """Create the tasks table if needed; seed three examples only when empty."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    count = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    if count == 0:
        db.executemany(
            "INSERT INTO tasks (id, title, done) VALUES (?, ?, ?)",
            [(task["id"], task["title"], int(task["done"])) for task in SEED],
        )
    db.commit()


init_db()


def task_from_row(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "title": row["title"], "done": bool(row["done"])}


app = FastAPI(
    title="Task API",
    version="1.0",
    description="A to-do list CRUD API. Tasks live in a SQLite file (tasks.db), "
    "so they survive a server restart.",
)


class Task(BaseModel):
    """A single to-do item."""

    id: int
    title: str
    done: bool


class TaskIn(BaseModel):
    """Body of POST /tasks."""

    title: str


class TaskUpdate(BaseModel):
    """Body of PUT /tasks/{task_id}. Send title, done, or both."""

    title: str | None = None
    done: bool | None = None


class Error(BaseModel):
    """Every error this API returns looks like this."""

    error: str


# Extra responses so Swagger UI documents the failure cases, not just the happy path.
NOT_FOUND = {404: {"model": Error, "description": "No task with that id"}}
BAD_REQUEST = {400: {"model": Error, "description": "Missing or empty title"}}


def get_task_row(task_id: int) -> sqlite3.Row | None:
    return db.execute("SELECT id, title, done FROM tasks WHERE id = ?", (task_id,)).fetchone()


def not_found(task_id: int):
    return JSONResponse(status_code=404, content={"error": f"Task {task_id} not found"})


def bad_request(message: str):
    return JSONResponse(status_code=400, content={"error": message})


@app.exception_handler(RequestValidationError)
def on_validation_error(request, exc: RequestValidationError):
    """FastAPI rejects bad bodies with 422; the spec for this API says 400."""
    first = exc.errors()[0]
    field = ".".join(str(part) for part in first["loc"][1:]) or "body"
    return bad_request(f"{field}: {first['msg']}")


def custom_openapi():
    """Drop FastAPI's automatic 422 entries: this API answers 400 instead."""
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    for operations in schema["paths"].values():
        for operation in operations.values():
            operation["responses"].pop("422", None)
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi


@app.get("/")
def root():
    """What this API is and where to go next."""
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health")
def health():
    """Liveness check. Returns ok as long as the server answers."""
    return {"status": "ok"}


@app.get("/tasks", response_model=list[Task], tags=["tasks"])
def list_tasks(
    done: bool | None = None,
    search: str | None = None,
    limit: int | None = None,
    offset: int = 0,
):
    """List tasks. Optionally filter by done, search titles, and paginate."""
    sql = "SELECT id, title, done FROM tasks WHERE 1=1"
    params: list = []
    if done is not None:
        sql += " AND done = ?"
        params.append(int(done))
    if search:
        sql += " AND title LIKE ?"
        params.append(f"%{search}%")
    sql += " ORDER BY id"
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
    elif offset:
        sql += " LIMIT -1 OFFSET ?"
        params.append(offset)
    return [task_from_row(row) for row in db.execute(sql, params)]


@app.get("/tasks/{task_id}", response_model=Task, tags=["tasks"], responses=NOT_FOUND)
def get_task(task_id: int):
    """Get one task by id. 404 if no task has that id."""
    row = get_task_row(task_id)
    if row is None:
        return not_found(task_id)
    return task_from_row(row)


@app.post(
    "/tasks",
    status_code=201,
    response_model=Task,
    tags=["tasks"],
    responses=BAD_REQUEST,
)
def create_task(payload: TaskIn):
    """Create a task. Empty or missing title is a 400."""
    title = payload.title.strip()
    if not title:
        return bad_request("title must not be empty")
    cur = db.execute("INSERT INTO tasks (title, done) VALUES (?, 0)", (title,))
    db.commit()
    return {"id": cur.lastrowid, "title": title, "done": False}


@app.put(
    "/tasks/{task_id}",
    response_model=Task,
    tags=["tasks"],
    responses=BAD_REQUEST | NOT_FOUND,
)
def update_task(task_id: int, payload: TaskUpdate):
    """Update a task's title and/or done. 404 unknown id, 400 empty body."""
    row = get_task_row(task_id)
    if row is None:
        return not_found(task_id)
    if payload.title is None and payload.done is None:
        return bad_request("body must contain title and/or done")
    title = row["title"]
    done = row["done"]
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            return bad_request("title must not be empty")
    if payload.done is not None:
        done = int(payload.done)
    db.execute(
        "UPDATE tasks SET title = ?, done = ? WHERE id = ?",
        (title, done, task_id),
    )
    db.commit()
    return {"id": task_id, "title": title, "done": bool(done)}


@app.delete("/tasks/{task_id}", status_code=204, tags=["tasks"], responses=NOT_FOUND)
def delete_task(task_id: int):
    """Delete a task. 204 with no body on success, 404 on unknown id."""
    cur = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    if cur.rowcount == 0:
        return not_found(task_id)
    return Response(status_code=204)


@app.get("/stats", tags=["extras"])
def stats():
    """Counts from SQL, not from a list in memory."""
    row = db.execute(
        "SELECT COUNT(*) AS total, COALESCE(SUM(done), 0) AS done FROM tasks"
    ).fetchone()
    total = row["total"]
    done = row["done"]
    return {"total": total, "done": done, "open": total - done}


@app.post("/reset", tags=["extras"])
def reset():
    """Throw away everything and put the three example tasks back."""
    db.execute("DELETE FROM tasks")
    db.executemany(
        "INSERT INTO tasks (id, title, done) VALUES (?, ?, ?)",
        [(task["id"], task["title"], int(task["done"])) for task in SEED],
    )
    db.commit()
    return list(SEED)
