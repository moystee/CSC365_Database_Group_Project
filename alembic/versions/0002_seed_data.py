"""Seed a small ingredient + recipe catalog.

We pin specific IDs (notably peanuts=42) so the example flows in
ExampleFlows.md run verbatim. After inserting we bump each table's identity
sequence so future inserts keep climbing past the seeded values.

Revision ID: 0002_seed_data
Revises: 0001_initial_schema
Create Date: 2026-05-04 12:05:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_seed_data"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (ingredient_id, name)
SEED_INGREDIENTS: list[tuple[int, str]] = [
    (1, "chicken"),
    (2, "rice"),
    (3, "broccoli"),
    (4, "soy sauce"),
    (5, "garlic"),
    (6, "olive oil"),
    (7, "tomato"),
    (8, "basil"),
    (9, "egg"),
    (10, "spinach"),
    (42, "peanuts"),
]

# (recipe_id, name, steps, [ingredient_id, ...])
SEED_RECIPES: list[tuple[int, str, str, list[int]]] = [
    (
        1,
        "Chicken and Broccoli Stir-Fry",
        "1) Cook rice. 2) Cook chicken in a hot pan until done. "
        "3) Add broccoli, stir-fry until tender. 4) Serve over rice.",
        [1, 2, 3],
    ),
    (
        2,
        "Peanut Chicken",
        "1) Cook chicken. 2) Toss with crushed peanuts. 3) Serve.",
        [1, 42],
    ),
    (
        3,
        "Steamed Broccoli",
        "1) Steam broccoli 4-5 minutes. 2) Season and serve.",
        [3],
    ),
    (
        4,
        "Tomato Basil Spaghetti-Style Rice",
        "1) Cook rice. 2) Saute garlic in olive oil with chopped tomato. 3) Stir in "
        "fresh basil. 4) Toss with rice.",
        [2, 5, 6, 7, 8],
    ),
    (
        5,
        "Spinach Frittata",
        "1) Whisk eggs. 2) Wilt spinach in olive oil with garlic. 3) Pour eggs over, "
        "cook until set.",
        [5, 6, 9, 10],
    ),
]


def upgrade() -> None:
    bind = op.get_bind()

    ingredients = sa.table(
        "ingredients",
        sa.column("ingredient_id", sa.Integer),
        sa.column("name", sa.String),
    )
    recipes = sa.table(
        "recipes",
        sa.column("recipe_id", sa.Integer),
        sa.column("recipe_name", sa.String),
        sa.column("recipe_steps", sa.Text),
    )
    recipe_ingredients = sa.table(
        "recipe_ingredients",
        sa.column("recipe_id", sa.Integer),
        sa.column("ingredient_id", sa.Integer),
    )

    bind.execute(
        sa.insert(ingredients),
        [
            {"ingredient_id": ing_id, "name": name}
            for ing_id, name in SEED_INGREDIENTS
        ],
    )

    bind.execute(
        sa.insert(recipes),
        [
            {
                "recipe_id": recipe_id,
                "recipe_name": name,
                "recipe_steps": steps,
            }
            for recipe_id, name, steps, _ in SEED_RECIPES
        ],
    )

    bind.execute(
        sa.insert(recipe_ingredients),
        [
            {"recipe_id": recipe_id, "ingredient_id": ing_id}
            for recipe_id, _, _, ing_ids in SEED_RECIPES
            for ing_id in ing_ids
        ],
    )

    # Bump identity sequences past the hand-picked IDs so future inserts get
    # safe new values. Postgres-only; harmless to skip on other dialects.
    if bind.dialect.name == "postgresql":
        max_ingredient_id = max(i for i, _ in SEED_INGREDIENTS)
        max_recipe_id = max(r for r, *_ in SEED_RECIPES)
        bind.execute(
            sa.text(
                "SELECT setval(pg_get_serial_sequence('ingredients', "
                "'ingredient_id'), :v)"
            ),
            {"v": max_ingredient_id},
        )
        bind.execute(
            sa.text(
                "SELECT setval(pg_get_serial_sequence('recipes', 'recipe_id'), :v)"
            ),
            {"v": max_recipe_id},
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM recipe_ingredients"))
    bind.execute(sa.text("DELETE FROM recipes"))
    bind.execute(sa.text("DELETE FROM ingredients"))
