from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()

# The "database": a plain list that lives only while the process runs.
tasks = [
    {"id": 1, "title": "Read the assignment", "done": True},
    {"id": 2, "title": "Build the CRUD API", "done": False},
    {"id": 3, "title": "Push to GitHub", "done": False},
]


class TaskIn(BaseModel):
    """Body of POST /tasks."""

    title: str


def find_task(task_id: int):
    """Return the task dict with this id, or None."""
    for task in tasks:
        if task["id"] == task_id:
            return task
    return None


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


@app.get("/")
def root():
    """What this API is and where to go next."""
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health")
def health():
    """Liveness check. Returns ok as long as the server answers."""
    return {"status": "ok"}


@app.get("/tasks")
def list_tasks():
    """List every task."""
    return tasks


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    """Get one task by id. 404 if no task has that id."""
    task = find_task(task_id)
    if task is None:
        return not_found(task_id)
    return task


@app.post("/tasks", status_code=201)
def create_task(payload: TaskIn):
    """Create a task. Empty or missing title is a 400."""
    title = payload.title.strip()
    if not title:
        return bad_request("title must not be empty")
    next_id = max((task["id"] for task in tasks), default=0) + 1
    task = {"id": next_id, "title": title, "done": False}
    tasks.append(task)
    return task
