"""V2: households + Flow 2/3 seeds; default pantry items to shared.

Adds the `households` and `household_members` tables that power Flow 2
(Mark + Leo sharing a pantry), flips the `pantry.is_shared_with_household`
default to TRUE so newly-saved items are visible to housemates without
extra ceremony, and seeds an additional recipe that matches Flow 2 with
just eggs + spinach.

Revision ID: 0003_households_and_v2_seeds
Revises: 0002_seed_data
Create Date: 2026-05-11 10:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_households_and_v2_seeds"
down_revision: Union[str, None] = "0002_seed_data"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Recipe added for Flow 2 (Mark + Leo cooking with eggs and spinach).
EXTRA_RECIPES: list[tuple[int, str, str, list[int]]] = [
    (
        6,
        "Eggs and Spinach Scramble",
        "1) Beat eggs in a bowl. 2) Wilt spinach in a hot pan. "
        "3) Pour in eggs and scramble until set.",
        [9, 10],  # egg + spinach
    ),
]


def upgrade() -> None:
    op.create_table(
        "households",
        sa.Column("household_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("household_name", sa.String(length=200), nullable=False),
    )

    op.create_table(
        "household_members",
        sa.Column(
            "household_id",
            sa.Integer,
            sa.ForeignKey("households.household_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # Pantry items default to shared with the household from V2 onwards.
    op.alter_column(
        "pantry",
        "is_shared_with_household",
        server_default=sa.text("true"),
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )

    # Backfill any rows that were inserted under the old default (false)
    # so existing pantries become household-visible. Safe to run on a
    # fresh DB — affects 0 rows.
    op.execute("UPDATE pantry SET is_shared_with_household = TRUE")

    bind = op.get_bind()
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
        sa.insert(recipes),
        [
            {
                "recipe_id": recipe_id,
                "recipe_name": name,
                "recipe_steps": steps,
            }
            for recipe_id, name, steps, _ in EXTRA_RECIPES
        ],
    )

    bind.execute(
        sa.insert(recipe_ingredients),
        [
            {"recipe_id": recipe_id, "ingredient_id": ing_id}
            for recipe_id, _, _, ing_ids in EXTRA_RECIPES
            for ing_id in ing_ids
        ],
    )

    if bind.dialect.name == "postgresql":
        max_recipe_id = max(r for r, *_ in EXTRA_RECIPES)
        bind.execute(
            sa.text(
                "SELECT setval(pg_get_serial_sequence('recipes', 'recipe_id'), "
                "GREATEST(:v, (SELECT MAX(recipe_id) FROM recipes)))"
            ),
            {"v": max_recipe_id},
        )


def downgrade() -> None:
    bind = op.get_bind()
    extra_ids = [r for r, *_ in EXTRA_RECIPES]
    bind.execute(
        sa.text("DELETE FROM recipe_ingredients WHERE recipe_id = ANY(:ids)"),
        {"ids": extra_ids},
    )
    bind.execute(
        sa.text("DELETE FROM recipes WHERE recipe_id = ANY(:ids)"),
        {"ids": extra_ids},
    )

    op.alter_column(
        "pantry",
        "is_shared_with_household",
        server_default=sa.text("false"),
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )

    op.drop_table("household_members")
    op.drop_table("households")
