"""Self-check: runs the whole CRUD cycle in-process. `python check.py`"""

import os
import sqlite3

# Isolate from the real tasks.db so this file never wipes student data.
_DB = os.path.join(os.path.dirname(__file__), "check-tasks.db")
if os.path.exists(_DB):
    os.remove(_DB)
os.environ["TASKS_DB"] = _DB

from fastapi.testclient import TestClient

from main import app, init_db

client = TestClient(app)


def rows_in_file():
    conn = sqlite3.connect(_DB)
    try:
        return conn.execute("SELECT id, title, done FROM tasks ORDER BY id").fetchall()
    finally:
        conn.close()


def check():
    assert client.get("/").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}

    # read
    assert len(client.get("/tasks").json()) == 3
    assert client.get("/tasks/1").status_code == 200
    r = client.get("/tasks/99")
    assert r.status_code == 404 and r.json() == {"error": "Task 99 not found"}

    # seed only if empty — running init again must not duplicate the examples
    init_db()
    init_db()
    assert len(client.get("/tasks").json()) == 3

    # create — and prove the row is in the sqlite file, not just RAM
    r = client.post("/tasks", json={"title": "Buy milk"})
    assert r.status_code == 201, r.status_code
    new_id = r.json()["id"]
    assert r.json() == {"id": new_id, "title": "Buy milk", "done": False}
    assert client.post("/tasks", json={}).status_code == 400
    assert client.post("/tasks", json={"title": "  "}).status_code == 400
    assert len(client.get("/tasks").json()) == 4
    assert (new_id, "Buy milk", 0) in rows_in_file()

    # update
    r = client.put(f"/tasks/{new_id}", json={"done": True})
    assert r.status_code == 200 and r.json()["done"] is True
    assert client.put(f"/tasks/{new_id}", json={}).status_code == 400
    assert client.put("/tasks/99", json={"done": True}).status_code == 404

    # delete
    r = client.delete(f"/tasks/{new_id}")
    assert r.status_code == 204 and r.content == b""
    assert client.delete(f"/tasks/{new_id}").status_code == 404
    assert len(client.get("/tasks").json()) == 3

    # extras
    assert [t["id"] for t in client.get("/tasks?done=true").json()] == [1]
    assert [t["id"] for t in client.get("/tasks?search=GITHUB").json()] == [3]
    assert [t["id"] for t in client.get("/tasks?limit=2&offset=1").json()] == [2, 3]
    assert client.get("/stats").json() == {"total": 3, "done": 1, "open": 2}
    client.delete("/tasks/1")
    assert len(client.post("/reset").json()) == 3
    assert client.get("/tasks/1").status_code == 200

    print("all checks passed")


if __name__ == "__main__":
    check()
