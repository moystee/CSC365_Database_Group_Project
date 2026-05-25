"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src import database as db
from src.api import households, ingredients, pantry, recipes, users
from src.api.helpers import logger

API_VERSION = "0.4.0"

OPENAPI_DESCRIPTION = """
CSC 365 **Food Graph API** (V4).

### V4 complex endpoints (submission)
- `GET /households/{household_id}/shopping-list` — recipe vs combined household pantry (`have` / `missing` / `coverage_pct`)
- `GET /users/{user_id}/top-recipes` — recipes ranked by pantry coverage; partial matches + `missing_ingredients`

### Concurrency
- `POST /recipes/{recipe_id}/consume` — deduct pantry quantities (`SERIALIZABLE` + row locks)
- See repo root `concurrency.md` for isolation-level rationale

### Notable V3/V4 additions
- REST aliases: `GET /users/{id}/allergies`, `DELETE /ingredients/{id}`, `GET /ingredients`, `GET /recipes`, `POST /recipes`
- `GET /users/{id}` profile, `DELETE /users/{id}`, leave household, remove allergy
- Pantry quantities, expiry dates, timestamps (schema migration `0004_v3_schema_extras`)

Legacy V2 paths (`POST /users/get_allergies`, `POST /ingredients/delete`, etc.) remain but are marked **deprecated** in this spec.
""".strip()

OPENAPI_TAGS = [
    {
        "name": "meta",
        "description": "Service health (`GET /` pings the database).",
    },
    {
        "name": "users",
        "description": "Accounts, allergies, and **top-recipes** recommendations.",
    },
    {
        "name": "ingredients",
        "description": "Ingredient catalog and pantry upsert/delete.",
    },
    {
        "name": "pantry",
        "description": "Read merged pantry (own + shared household items).",
    },
    {
        "name": "households",
        "description": "Create/join/leave households and **shopping-list** diffs.",
    },
    {
        "name": "recipes",
        "description": "Compatibility search, catalog browse, create, and **consume**.",
    },
]

app = FastAPI(
    title="Food Graph API",
    description=OPENAPI_DESCRIPTION,
    version=API_VERSION,
    openapi_tags=OPENAPI_TAGS,
    servers=[
        {
            "url": "https://foodgraph-api.onrender.com",
            "description": "Render production",
        },
        {"url": "http://localhost:8000", "description": "Local uvicorn"},
    ],
)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    # Render polls this path as a health check. Run a cheap query so we
    # only report healthy when the database is actually reachable —
    # otherwise traffic could be routed to an instance that can't serve
    # any real request.
    try:
        with db.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.error("Health check DB ping failed: %s", exc)
        raise HTTPException(
            status_code=503, detail="Database connection failed."
        ) from exc

    return {
        "service": "Food Graph API",
        "version": API_VERSION,
        "docs": "/docs",
        "openapi": "/openapi.json",
        "database": "ok",
    }


app.include_router(users.router)
app.include_router(ingredients.router)
app.include_router(recipes.router)
app.include_router(households.router)
app.include_router(pantry.router)
