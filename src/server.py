"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI

from src.api import households, ingredients, pantry, recipes, users

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
    return {
        "service": "Food Graph API",
        "version": "0.2.0",
        "docs": "/docs",
    }


app.include_router(users.router)
app.include_router(ingredients.router)
app.include_router(recipes.router)
app.include_router(households.router)
app.include_router(pantry.router)
