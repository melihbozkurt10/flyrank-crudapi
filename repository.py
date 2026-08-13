"""Storage behind the API. Routes talk to this, not to SQL or a list."""

from pathlib import Path
from typing import Protocol

import psycopg
from psycopg.rows import dict_row

SEED = [
    {"id": 1, "title": "Read the assignment", "done": True},
    {"id": 2, "title": "Build the CRUD API", "done": False},
    {"id": 3, "title": "Push to GitHub", "done": False},
]

INIT_SQL = Path(__file__).parent / "db" / "init.sql"


def as_task(row: dict) -> dict:
    return {"id": row["id"], "title": row["title"], "done": bool(row["done"])}


class TaskRepository(Protocol):
    def init(self) -> None: ...
    def list(
        self,
        done: bool | None,
        search: str | None,
        limit: int | None,
        offset: int,
    ) -> list[dict]: ...
    def get(self, task_id: int) -> dict | None: ...
    def create(self, title: str) -> dict: ...
    def update(
        self, task_id: int, title: str | None, done: bool | None
    ) -> dict | None: ...
    def delete(self, task_id: int) -> bool: ...
    def stats(self) -> dict: ...
    def reset(self) -> list[dict]: ...


class InMemoryRepository:
    """Same behaviour as Assignment 1. Used by check.py (no Docker needed)."""

    def __init__(self) -> None:
        self.tasks: list[dict] = []

    def init(self) -> None:
        if not self.tasks:
            self.tasks = [dict(task) for task in SEED]

    def list(
        self,
        done: bool | None,
        search: str | None,
        limit: int | None,
        offset: int,
    ) -> list[dict]:
        result = self.tasks
        if done is not None:
            result = [task for task in result if task["done"] == done]
        if search:
            needle = search.lower()
            result = [task for task in result if needle in task["title"].lower()]
        result = result[offset:]
        if limit is not None:
            result = result[:limit]
        return result

    def get(self, task_id: int) -> dict | None:
        for task in self.tasks:
            if task["id"] == task_id:
                return task
        return None

    def create(self, title: str) -> dict:
        next_id = max((task["id"] for task in self.tasks), default=0) + 1
        task = {"id": next_id, "title": title, "done": False}
        self.tasks.append(task)
        return task

    def update(
        self, task_id: int, title: str | None, done: bool | None
    ) -> dict | None:
        task = self.get(task_id)
        if task is None:
            return None
        if title is not None:
            task["title"] = title
        if done is not None:
            task["done"] = done
        return task

    def delete(self, task_id: int) -> bool:
        task = self.get(task_id)
        if task is None:
            return False
        self.tasks.remove(task)
        return True

    def stats(self) -> dict:
        done = sum(1 for task in self.tasks if task["done"])
        total = len(self.tasks)
        return {"total": total, "done": done, "open": total - done}

    def reset(self) -> list[dict]:
        self.tasks = [dict(task) for task in SEED]
        return list(self.tasks)


class PostgresRepository:
    """Same methods as InMemoryRepository. Data lives in Postgres."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def connect(self) -> psycopg.Connection:
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def init(self) -> None:
        sql = INIT_SQL.read_text(encoding="utf-8")
        with self.connect() as conn:
            for stmt in sql.split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(stmt)

    def list(
        self,
        done: bool | None,
        search: str | None,
        limit: int | None,
        offset: int,
    ) -> list[dict]:
        sql = "SELECT id, title, done FROM tasks WHERE TRUE"
        params: list = []
        if done is not None:
            sql += " AND done = %s"
            params.append(done)
        if search:
            sql += " AND title ILIKE %s"
            params.append(f"%{search}%")
        sql += " ORDER BY id"
        if limit is not None:
            sql += " LIMIT %s OFFSET %s"
            params.extend([limit, offset])
        elif offset:
            sql += " OFFSET %s"
            params.append(offset)
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [as_task(row) for row in rows]

    def get(self, task_id: int) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id, title, done FROM tasks WHERE id = %s",
                (task_id,),
            ).fetchone()
        return as_task(row) if row else None

    def create(self, title: str) -> dict:
        with self.connect() as conn:
            row = conn.execute(
                "INSERT INTO tasks (title, done) VALUES (%s, FALSE) "
                "RETURNING id, title, done",
                (title,),
            ).fetchone()
        return as_task(row)

    def update(
        self, task_id: int, title: str | None, done: bool | None
    ) -> dict | None:
        current = self.get(task_id)
        if current is None:
            return None
        if title is not None:
            current["title"] = title
        if done is not None:
            current["done"] = done
        with self.connect() as conn:
            row = conn.execute(
                "UPDATE tasks SET title = %s, done = %s WHERE id = %s "
                "RETURNING id, title, done",
                (current["title"], current["done"], task_id),
            ).fetchone()
        return as_task(row)

    def delete(self, task_id: int) -> bool:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
            return cur.rowcount > 0

    def stats(self) -> dict:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS total, "
                "COUNT(*) FILTER (WHERE done) AS done FROM tasks"
            ).fetchone()
        total = row["total"]
        done = row["done"]
        return {"total": total, "done": done, "open": total - done}

    def reset(self) -> list[dict]:
        with self.connect() as conn:
            conn.execute("DELETE FROM tasks")
            conn.executemany(
                "INSERT INTO tasks (id, title, done) VALUES (%s, %s, %s)",
                [(task["id"], task["title"], task["done"]) for task in SEED],
            )
            conn.execute(
                "SELECT setval(pg_get_serial_sequence('tasks', 'id'), "
                "COALESCE((SELECT MAX(id) FROM tasks), 1))"
            )
        return [dict(task) for task in SEED]
