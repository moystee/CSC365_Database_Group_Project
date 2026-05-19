"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src import database as db
from src.api import households, ingredients, pantry, recipes, users
from src.api.helpers import logger

app = FastAPI(
    title="Food Graph API",
    description=(
        "CSC 365 group project — V2. A recipe/pantry app where ingredients "
        "and recipes form a graph. V2 covers all three example flows: "
        "(1) Sarah managing allergies, (2) Mark + Leo sharing a household "
        "pantry, (3) David tidying his pantry inventory."
    ),
    version="0.2.0",
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
        "version": "0.2.0",
        "docs": "/docs",
        "database": "ok",
    }


app.include_router(users.router)
app.include_router(ingredients.router)
app.include_router(recipes.router)
app.include_router(households.router)
app.include_router(pantry.router)
