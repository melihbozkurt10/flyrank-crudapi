# Task API — Postgres in Docker

A to-do CRUD API. The URLs, bodies, and status codes are the same as
Assignment 1 and 2. Storage is a `TaskRepository`. With `DATABASE_URL` it
talks to Postgres; without it, an in-memory list. Switching storage is one
function in `main.py` (`build_repo`). Routes still validate input and map
404/400 — they do not contain SQL.

Honest note: Assignment 2 had SQL inside the route handlers (SQLite). Those
handlers now call `repo.list` / `repo.create` / … instead. The HTTP contract
did not change. The database did.

```
Client -> API (main.py) -> TaskRepository -> Postgres  (docker compose)
                         -> in-memory list  (python check.py)
```

## Why this stack

Postgres is a real database server. SQLite was a file on disk; this is a
process you connect to with a connection string. Docker runs that process
for you, with a volume so the data outlives the container.

`.env` holds the connection string and is gitignored. `.env.example` is
committed so a clone knows which variables to set.

## Start the whole stack

Needs [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
copy .env.example .env          # Windows;  cp .env.example .env on macOS/Linux
docker compose up --build
```

- API: <http://localhost:8000>
- Swagger: <http://localhost:8000/docs>
- Postgres: `localhost:5432` (user/password/db: `tasks`)

First boot runs `db/init.sql`: creates `tasks` and inserts three example rows
only if the table is empty. Later boots skip that script (the volume already
exists) and keep your data.

Stop with Ctrl-C, or `docker compose down`. `down -v` deletes the volume and
the data.

## Persistence check

This is how it was verified conceptually; run it after `docker compose up`:

```bash
curl -s -X POST http://localhost:8000/tasks -H "Content-Type: application/json" -d "{\"title\":\"Will I survive a restart?\"}"
curl -s http://localhost:8000/tasks

docker compose restart

curl -s http://localhost:8000/tasks
```

The new task is still there after both the app container and the database
container restart. It lives on the `pgdata` volume, not in the API process.

Without Docker, `python check.py` uses the in-memory repository and cannot
prove this — that is expected.

## Without Docker (self-check only)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python check.py     # prints "all checks passed"
```

`check.py` sets `DATABASE_URL` empty so it never touches Postgres.

## Files that matter

| File | Role |
| --- | --- |
| `main.py` | Routes + `build_repo()` (the swap) |
| `repository.py` | `InMemoryRepository` and `PostgresRepository` — same methods |
| `db/init.sql` | `CREATE TABLE` + seed (mounted into Postgres on first boot) |
| `.env` | Secrets / connection string (not in git) |
| `.env.example` | Same keys, dummy values |
| `docker-compose.yml` | `app` + `db` + named volume `pgdata` |

## Endpoints

| Method | Path              | Does                     | Success | Errors |
| ------ | ----------------- | ------------------------ | ------- | ------ |
| GET    | `/`               | What this API is         | 200     | —      |
| GET    | `/health`         | Liveness check           | 200     | —      |
| GET    | `/tasks`          | List all tasks           | 200     | —      |
| GET    | `/tasks/{id}`     | Get one task             | 200     | 404    |
| POST   | `/tasks`          | Create a task            | 201     | 400    |
| PUT    | `/tasks/{id}`     | Update title and/or done | 200     | 400, 404 |
| DELETE | `/tasks/{id}`     | Delete a task            | 204     | 404    |

Every error returns JSON in the same shape: `{"error": "Task 99 not found"}`.

| Method | Path                        | Does                          |
| ------ | --------------------------- | ----------------------------- |
| GET    | `/tasks?done=true`          | Filter                        |
| GET    | `/tasks?search=milk`        | Case-insensitive title search |
| GET    | `/tasks?limit=2&offset=1`   | Pagination                    |
| GET    | `/stats`                    | `{total, done, open}`         |
| POST   | `/reset`                    | Restore the three examples    |

![Swagger UI listing every endpoint](docs/swagger-ui.png)
