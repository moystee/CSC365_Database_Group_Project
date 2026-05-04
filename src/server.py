"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI

from src.api import ingredients, recipes, users

app = FastAPI(
    title="Food Graph API",
    description=(
        "CSC 365 group project — V1. A recipe/pantry app where ingredients "
        "and recipes form a graph. V1 implements Flow 1 (Sarah's workflow)."
    ),
    version="0.1.0",
)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {
        "service": "Food Graph API",
        "version": "0.1.0",
        "docs": "/docs",
    }


app.include_router(users.router)
app.include_router(ingredients.router)
app.include_router(recipes.router)
