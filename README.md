# Task API — Auth + Postgres

A to-do CRUD API with **Supabase Auth**. Anyone can hit `/public/info` and the
task list. `/protected/*` and `/auth/logout` require
`Authorization: Bearer <access_token>`.

Passwords never land in this server. The client talks to Supabase; this API
only checks the JWT Supabase issued.

```
Client -> POST /auth/login -> Supabase -> JWT
Client -> GET /protected/profile + Bearer JWT -> this API -> supabase.auth.get_user
```

`.env` is gitignored. Copy `.env.example` and paste your own Supabase URL and
anon key. Never commit those values.

## Setup

1. Create a free project at [supabase.com](https://supabase.com).
2. **Authentication → Providers → Email**: turn **off** "Confirm email" so
   `POST /auth/login` works immediately after signup (otherwise the mailbox
   has to confirm first).
3. **Project Settings → API**: copy Project URL and `anon` `public` key.

```bash
copy .env.example .env          # Windows;  cp .env.example .env on macOS/Linux
```

Fill in:

```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=eyJ...
```

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

The terminal should print `Server running and connected to Supabase`.

- API: <http://localhost:8000>
- Swagger: <http://localhost:8000/docs> — click **Authorize**, paste the
  `access_token` from `/auth/login`, then Try it out on `/protected/profile`.

```bash
python check.py     # prints "all checks passed"
```

### Auth smoke test

```bash
curl -i -X POST http://localhost:8000/auth/signup -H "Content-Type: application/json" -d "{\"email\":\"test@example.com\",\"password\":\"password123\"}"

curl -s -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d "{\"email\":\"test@example.com\",\"password\":\"password123\"}"

curl -i http://localhost:8000/public/info
curl -i http://localhost:8000/protected/profile
curl -i http://localhost:8000/protected/profile -H "Authorization: Bearer PASTE_ACCESS_TOKEN"
```

## API reference

| Method | Path | Auth | Success | Errors |
| ------ | ---- | ---- | ------- | ------ |
| POST | `/auth/signup` | no | 201 | 400 |
| POST | `/auth/login` | no | 200 (`access_token`, `refresh_token`) | 400, 401 |
| POST | `/auth/logout` | Bearer | 204 | 401 |
| GET | `/public/info` | no | 200 | — |
| GET | `/protected/profile` | Bearer | 200 (id, email, created_at) | 401 |
| GET | `/protected/dashboard` | Bearer | 200 | 401 |
| GET | `/tasks` | no | 200 | — |
| GET | `/tasks/{id}` | no | 200 | 404 |
| POST | `/tasks` | no | 201 | 400 |
| PUT | `/tasks/{id}` | no | 200 | 400, 404 |
| DELETE | `/tasks/{id}` | no | 204 | 404 |

Missing/malformed Bearer → `401 {"error":"Access token required"}`.  
Bad or expired JWT → `401 {"error":"Invalid or expired token"}`.  
Wrong password → `401 {"error":"Invalid login credentials"}`.

Token checks live in one FastAPI dependency (`require_user` in `auth.py`).
`/protected/profile`, `/protected/dashboard`, and `/auth/logout` all use it.

![Swagger UI with Bearer auth](docs/swagger-ui.png)

## Postgres (optional)

Task rows can live in Postgres via Docker. `python check.py` uses the
in-memory repository and does not need Docker.

```bash
docker compose up --build
```

`DATABASE_URL` and `POSTGRES_*` are in `.env.example`. Data is on the `pgdata`
volume, so `docker compose restart` keeps rows.
