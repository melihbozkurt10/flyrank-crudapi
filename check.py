"""Self-check: runs the whole CRUD cycle in-process. `python check.py`"""

import os

# Force the in-memory repository so this file does not need Docker or Postgres.
os.environ["DATABASE_URL"] = ""

from fastapi.testclient import TestClient

from main import app, repo

client = TestClient(app)


def check():
    assert client.get("/").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}

    # read
    assert len(client.get("/tasks").json()) == 3
    assert client.get("/tasks/1").status_code == 200
    r = client.get("/tasks/99")
    assert r.status_code == 404 and r.json() == {"error": "Task 99 not found"}

    # seed only if empty — running init again must not duplicate the examples
    repo.init()
    repo.init()
    assert len(client.get("/tasks").json()) == 3

    # create
    r = client.post("/tasks", json={"title": "Buy milk"})
    assert r.status_code == 201, r.status_code
    new_id = r.json()["id"]
    assert r.json() == {"id": new_id, "title": "Buy milk", "done": False}
    assert client.post("/tasks", json={}).status_code == 400
    assert client.post("/tasks", json={"title": "  "}).status_code == 400
    assert len(client.get("/tasks").json()) == 4

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

    # auth gates (no Supabase needed for these)
    assert client.get("/public/info").json() == {
        "message": "Welcome stranger! This info is public."
    }
    r = client.get("/protected/profile")
    assert r.status_code == 401 and r.json() == {"error": "Access token required"}
    r = client.get("/protected/dashboard")
    assert r.status_code == 401 and r.json() == {"error": "Access token required"}
    r = client.get("/protected/profile", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401 and r.json() == {"error": "Invalid or expired token"}
    r = client.post("/auth/logout")
    assert r.status_code == 401 and r.json() == {"error": "Access token required"}
    assert client.post("/auth/signup", json={}).status_code == 400
    assert client.post("/auth/login", json={"email": "", "password": ""}).status_code == 400
    assert client.post("/auth/login", json={"email": "a@b.c", "password": "wrong"}).status_code == 401

    print("all checks passed")


if __name__ == "__main__":
    check()
