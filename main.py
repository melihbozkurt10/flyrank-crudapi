import os

from dotenv import load_dotenv
from fastapi import FastAPI, Response
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from repository import InMemoryRepository, PostgresRepository, TaskRepository

load_dotenv()


def build_repo() -> TaskRepository:
    """The only place storage is chosen. Routes never import Postgres or a list."""
    dsn = os.getenv("DATABASE_URL", "").strip()
    if dsn:
        return PostgresRepository(dsn)
    return InMemoryRepository()


repo = build_repo()
repo.init()

app = FastAPI(
    title="Task API",
    version="1.0",
    description="A to-do list CRUD API. Storage is a TaskRepository — Postgres "
    "when DATABASE_URL is set, otherwise an in-memory list.",
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
    return repo.list(done, search, limit, offset)


@app.get("/tasks/{task_id}", response_model=Task, tags=["tasks"], responses=NOT_FOUND)
def get_task(task_id: int):
    """Get one task by id. 404 if no task has that id."""
    task = repo.get(task_id)
    if task is None:
        return not_found(task_id)
    return task


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
    return repo.create(title)


@app.put(
    "/tasks/{task_id}",
    response_model=Task,
    tags=["tasks"],
    responses=BAD_REQUEST | NOT_FOUND,
)
def update_task(task_id: int, payload: TaskUpdate):
    """Update a task's title and/or done. 404 unknown id, 400 empty body."""
    if repo.get(task_id) is None:
        return not_found(task_id)
    if payload.title is None and payload.done is None:
        return bad_request("body must contain title and/or done")
    title = payload.title
    if title is not None:
        title = title.strip()
        if not title:
            return bad_request("title must not be empty")
    return repo.update(task_id, title, payload.done)


@app.delete("/tasks/{task_id}", status_code=204, tags=["tasks"], responses=NOT_FOUND)
def delete_task(task_id: int):
    """Delete a task. 204 with no body on success, 404 on unknown id."""
    if not repo.delete(task_id):
        return not_found(task_id)
    return Response(status_code=204)


@app.get("/stats", tags=["extras"])
def stats():
    """Counts from the repository, not from a list in this file."""
    return repo.stats()


@app.post("/reset", tags=["extras"])
def reset():
    """Throw away everything and put the three example tasks back."""
    return repo.reset()
