from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

# The "database": a plain list that lives only while the process runs.
tasks = [
    {"id": 1, "title": "Read the assignment", "done": True},
    {"id": 2, "title": "Build the CRUD API", "done": False},
    {"id": 3, "title": "Push to GitHub", "done": False},
]


def find_task(task_id: int):
    """Return the task dict with this id, or None."""
    for task in tasks:
        if task["id"] == task_id:
            return task
    return None


def not_found(task_id: int):
    return JSONResponse(status_code=404, content={"error": f"Task {task_id} not found"})


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
