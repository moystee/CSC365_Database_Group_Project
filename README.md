# Food Graph API — CSC 365 Group Project

A FastAPI service backed by Postgres that organizes recipes as a graph of
ingredients. **V1 implements Flow 1 (Sarah's workflow)** end-to-end:

1. `POST /users/create` — sign up
2. `POST /users/add_allergy` — record an allergy
3. `POST /ingredients/save` — log pantry ingredients
4. `GET /recipes/get_compatible` — find recipes that fit the pantry (and skip allergens)

> See `ExampleFlows.md` for the full description and `APISpec.md` for the
> API surface (additional endpoints will arrive in V2).

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
│       └── 0002_seed_data.py
├── alembic.ini
├── render.yaml
├── requirements.txt
├── src/
│   ├── database.py         # engine + table definitions
│   ├── server.py           # FastAPI app entry
│   └── api/
│       ├── users.py        # /users/*
│       ├── ingredients.py  # /ingredients/*
│       └── recipes.py      # /recipes/*
└── v1_manual_test_results.md
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

This runs both migrations:
- `0001_initial_schema` — creates `users`, `ingredients`, `recipes`, `recipe_ingredients`, `pantry`, `user_allergies`.
- `0002_seed_data` — inserts a small ingredient catalog (chicken=1, rice=2, broccoli=3, …, peanuts=42) and 5 recipes including "Chicken and Broccoli Stir-Fry".

### 5. Run the server

```bash
uvicorn src.server:app --reload
```

Open the docs at <http://localhost:8000/docs>.

### 6. Try Flow 1

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

The last call returns "Chicken and Broccoli Stir-Fry" — the peanut recipe
is filtered because (a) Sarah doesn't have peanuts in her pantry, and (b)
even if she did, her recorded allergy would exclude it.

---

## Deploying to Render (production)

Render's Blueprint feature reads `render.yaml` at the repo root and
provisions both the web service and the Postgres database in one step.

1. Push this repo to GitHub.
2. In Render, click **New → Blueprint** and select your repo.
3. Render reads `render.yaml`, then provisions:
   - **`foodgraph-db`** — a free Postgres instance
   - **`foodgraph-api`** — the FastAPI web service, with `POSTGRES_URI`
     wired to the database's connection string automatically
4. The build step runs `pip install -r requirements.txt && alembic upgrade head`,
   so the schema and seed data are created on first deploy.
5. The start command is `uvicorn src.server:app --host 0.0.0.0 --port $PORT`.

Once deployed, your endpoints will be at
`https://foodgraph-api.onrender.com` (or whatever subdomain Render assigns)
and the interactive docs at `/docs`.

---

## Resetting the database

Drop everything and re-run migrations:

```bash
alembic downgrade base
alembic upgrade head
```
