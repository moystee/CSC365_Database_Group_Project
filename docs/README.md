# Food Graph API — CSC 365 Group Project

A FastAPI service backed by Postgres that organizes recipes as a graph of
ingredients. **V2 implements all three example flows** end-to-end (see
`ExampleFlows.md`):

| Flow | Persona | Endpoints exercised |
|---|---|---|
| 1 | Sarah (peanut allergy) | `POST /users/create`, `POST /users/add_allergy`, `POST /ingredients/save`, `GET /recipes/get_compatible` |
| 2 | Mark + Leo (shared household) | `POST /households/create`, `POST /households/join`, `POST /ingredients/save`, `GET /pantry/get_ingredients`, `GET /recipes/get_compatible` |
| 3 | David (inventory tidy-up) | `POST /ingredients/save`, `POST /ingredients/delete`, `GET /pantry/get_ingredients` |

Manual test results for V1 live in `v1_manual_test_results.md`; the V2
runs (all three flows) are documented in `v2_manual_test_results.md`.

## Team
Victor Wu, Jared Moy, Avery Robinson, Daniel Pineda

---

## Tech stack

- Python 3.11+
- FastAPI + Uvicorn
- SQLAlchemy Core (no ORM models — tables defined once in `src/database.py`)
- Alembic (schema + seed migrations)
- PostgreSQL
- Hosted on Render

## Project layout

```
.
├── alembic/
│   ├── env.py
│   └── versions/
│       ├── 0001_initial_schema.py
│       ├── 0002_seed_data.py
│       └── 0003_households_and_v2_seeds.py
├── alembic.ini
├── schema.sql              # alternative to alembic (raw CREATE + INSERTs)
├── render.yaml
├── requirements.txt
├── src/
│   ├── database.py         # engine + table definitions
│   ├── server.py           # FastAPI app entry
│   └── api/
│       ├── users.py        # /users/*
│       ├── ingredients.py  # /ingredients/*
│       ├── recipes.py      # /recipes/*
│       ├── households.py   # /households/* (V2)
│       └── pantry.py       # /pantry/* (V2)
├── v1_manual_test_results.md
└── v2_manual_test_results.md
```

---

## Running locally

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start a local Postgres and create a database

If you have Postgres installed locally:

```bash
createdb foodgraph
```

Or with Docker:

```bash
docker run --name foodgraph-pg -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=foodgraph -p 5432:5432 -d postgres:16
```

### 3. Configure your environment

```bash
cp .env.example .env
# then edit .env so POSTGRES_URI points at your local DB, e.g.:
# POSTGRES_URI=postgresql://postgres:postgres@localhost:5432/foodgraph
```

### 4. Apply migrations (creates tables + seeds the catalog)

```bash
alembic upgrade head
```

This runs all three migrations:
- `0001_initial_schema` — creates `users`, `ingredients`, `recipes`, `recipe_ingredients`, `pantry`, `user_allergies`.
- `0002_seed_data` — inserts the ingredient catalog (chicken=1, rice=2, broccoli=3, …, peanuts=42) and 5 recipes.
- `0003_households_and_v2_seeds` — adds `households` + `household_members`, flips `pantry.is_shared_with_household` to default TRUE, and adds the "Eggs and Spinach Scramble" recipe used in Flow 2.

> Alternative without Alembic: `psql "$POSTGRES_URI" -f schema.sql`.
> The `schema.sql` file in the repo root contains the same `CREATE TABLE`
> and seed `INSERT` statements as the migrations, hand-written to stay
> portable across Postgres versions (works on Supabase / PG14+). It is
> idempotent — it drops and recreates everything.

### 5. Run the server

```bash
uvicorn src.server:app --reload
```

Open the docs at <http://localhost:8000/docs>.

### 6. Try the flows

The full curl-by-curl runs (with real responses) for all three example
flows are recorded in `v2_manual_test_results.md`. A quick smoke test
for Flow 1:

```bash
# 1. Create Sarah
curl -X POST http://localhost:8000/users/create \
  -H 'Content-Type: application/json' \
  -d '{"first_name":"Sarah","email":"sarah@example.com"}'

# 2. Record her peanut allergy (peanuts seeded as ingredient_id=42)
curl -X POST http://localhost:8000/users/add_allergy \
  -H 'Content-Type: application/json' \
  -d '{"user_id":1,"ingredient_id":42}'

# 3. Save chicken (1), rice (2), and broccoli (3)
for ID in 1 2 3; do
  curl -X POST http://localhost:8000/ingredients/save \
    -H 'Content-Type: application/json' \
    -d "{\"user_id\":1,\"ingredient_id\":$ID}"
done

# 4. Find safe recipes
curl "http://localhost:8000/recipes/get_compatible?ingredient_ids=1&ingredient_ids=2&ingredient_ids=3&user_id=1"
```

---

## Deploying to production (Supabase + Render)

The production setup splits responsibilities:

| Component         | Hosted on     |
|-------------------|---------------|
| Postgres database | **Supabase**  |
| FastAPI web app   | **Render**    |

### 1. Provision Supabase Postgres

1. Sign in at <https://supabase.com> and click **New project**.
2. Pick an org, set a project name (e.g. `foodgraph`), pick a region close
   to you, and **save the database password** somewhere safe — Supabase
   only shows it once.
3. Wait ~1 minute for the project to provision.
4. In the Supabase dashboard go to **Project Settings → Database →
   Connection string**. You'll see two URLs:
   - **Direct connection** on port `5432` — used for migrations.
   - **Transaction pooler** on port `6543` — used by the running app.

   Copy both. They look like:
   ```
   # Direct (for alembic):
   postgresql://postgres:<PASSWORD>@db.<REF>.supabase.co:5432/postgres

   # Pooler (for the app at runtime):
   postgresql://postgres.<REF>:<PASSWORD>@aws-0-<REGION>.pooler.supabase.com:6543/postgres
   ```

### 2. Apply migrations against Supabase (one-time, from your laptop)

We do migrations from a developer machine using the **direct** URL,
because the transaction pooler can't run all of Alembic's statements.

```bash
# From the project root, with your venv activated:
echo 'POSTGRES_URI=postgresql://postgres:<PASSWORD>@db.<REF>.supabase.co:5432/postgres' > .env.prod

# Run migrations against Supabase (note --env-file overrides .env)
POSTGRES_URI="postgresql://postgres:<PASSWORD>@db.<REF>.supabase.co:5432/postgres" \
  alembic upgrade head
```

You should see:

```
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_initial_schema
INFO  [alembic.runtime.migration] Running upgrade 0001_initial_schema -> 0002_seed_data
```

Verify in the Supabase dashboard under **Table Editor** — you should see
`users`, `ingredients`, `recipes`, `recipe_ingredients`, `pantry`, and
`user_allergies`, with the seeded ingredient + recipe rows.

### 3. Deploy the FastAPI app to Render

1. Push this repo to GitHub.
2. In Render, click **New → Blueprint** and select the repo. Render reads
   `render.yaml` and creates the `foodgraph-api` web service. (No DB is
   provisioned by Render — `render.yaml` is configured for the Supabase
   setup.)
3. After the service appears, open it and go to **Environment**. Set:
   - `POSTGRES_URI` → the **transaction pooler** URL from Supabase (port `6543`).
4. Click **Save Changes**, then **Manual Deploy → Clear build cache & deploy**.
5. The build runs `pip install -r requirements.txt` and the start
   command is `uvicorn src.server:app --host 0.0.0.0 --port $PORT`.

Your service will be live at
`https://foodgraph-api.onrender.com` (or whatever subdomain Render gives
you). Interactive docs at `/docs`.

### Python version

Render defaults to the latest Python, which is sometimes too new for some
dependencies' prebuilt wheels (notably `pydantic-core`, which falls back
to compiling from Rust if no wheel matches). To avoid that, this repo
pins **Python 3.13.4** three ways so every Render detection mechanism
finds it:

- `PYTHON_VERSION=3.13.4` env var in `render.yaml`
- `.python-version` file at repo root
- `runtime.txt` with `python-3.13.4`

If a new Render build still picks up the wrong Python, set
`PYTHON_VERSION=3.13.4` directly in **Environment** in the Render
dashboard and choose **Manual Deploy → Clear build cache & deploy**.

### Re-running migrations later

Whenever you add a new Alembic revision, apply it to Supabase the same
way as in step 2 (using the **direct** connection, not the pooler):

```bash
POSTGRES_URI="postgresql://postgres:<PASSWORD>@db.<REF>.supabase.co:5432/postgres" \
  alembic upgrade head
```

Then redeploy Render so the FastAPI code matches the new schema.

---

## Resetting the database

Drop everything and re-run migrations:

```bash
alembic downgrade base
alembic upgrade head
```
