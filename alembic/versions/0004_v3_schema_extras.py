"""Schema additions called out in the V2 code-review issues.

- Quantities + units on `pantry` and `recipe_ingredients` (Joe #1/#2, Aaron #6/#7).
- Purchase / expiry dates on `pantry` (Joe #3, the "minimize waste" use case).
- `created_at` / `joined_at` timestamps on every table (Joe #4, Anay #1/#12, Aaron #8).
- `last_name` on `users` (Joe #5).
- `created_by` ownership FK on `recipes` and `households` (Joe #10/#14).
- `ck_ingredient_name_normalized` CHECK so ingredient names can't be blank /
  mixed case / leading-whitespace (Aaron schema #9/#12).
- Drop the unused `pantry_id` surrogate; the natural `(user_id, ingredient_id)`
  pair becomes the primary key (Joe code-review #11).
- Relax `recipe_ingredients → ingredients` from RESTRICT to CASCADE so the
  ingredient catalog isn't permanently undeletable (Joe schema #12).

Revision ID: 0004_quantities_timestamps_ownership
Revises: 0003_households_and_v2_seeds
Create Date: 2026-05-19 11:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_v3_schema_extras"
down_revision: Union[str, None] = "0003_households_and_v2_seeds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Postgres auto-names FK and PK constraints as <table>_<column>_fkey and
# <table>_pkey respectively. Centralizing them here avoids string typos.
RECIPE_INGREDIENTS_INGREDIENT_FK = "recipe_ingredients_ingredient_id_fkey"
PANTRY_PK = "pantry_pkey"
PANTRY_UQ = "uq_pantry_user_ingredient"


def _now() -> sa.TextClause:
    return sa.text("NOW()")


def upgrade() -> None:
    # ---------- users ----------
    op.add_column(
        "users",
        sa.Column("last_name", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
    )

    # ---------- ingredients ----------
    op.add_column(
        "ingredients",
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
    )
    # Reject blank / whitespace / mixed-case ingredient names so callers can't
    # create "  Tomato " as a distinct entry from "tomato".
    op.create_check_constraint(
        "ck_ingredient_name_normalized",
        "ingredients",
        "name = LOWER(name) AND name = TRIM(name) AND length(name) > 0",
    )

    # ---------- recipes ----------
    op.add_column(
        "recipes",
        sa.Column(
            "created_by",
            sa.Integer,
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "recipes",
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
    )

    # ---------- recipe_ingredients ----------
    op.add_column(
        "recipe_ingredients",
        sa.Column("quantity", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "recipe_ingredients",
        sa.Column("unit", sa.String(length=50), nullable=True),
    )
    # Relax the FK so the ingredient catalog can be managed without
    # hitting a foreign-key violation every time.
    op.drop_constraint(
        RECIPE_INGREDIENTS_INGREDIENT_FK,
        "recipe_ingredients",
        type_="foreignkey",
    )
    op.create_foreign_key(
        RECIPE_INGREDIENTS_INGREDIENT_FK,
        "recipe_ingredients",
        "ingredients",
        ["ingredient_id"],
        ["ingredient_id"],
        ondelete="CASCADE",
    )

    # ---------- pantry ----------
    op.add_column(
        "pantry",
        sa.Column("quantity", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "pantry",
        sa.Column("unit", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "pantry",
        sa.Column("purchase_date", sa.Date, nullable=True),
    )
    op.add_column(
        "pantry",
        sa.Column("expiry_date", sa.Date, nullable=True),
    )
    op.add_column(
        "pantry",
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
    )
    op.add_column(
        "pantry",
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
    )
    # Drop the unused surrogate key and the unique constraint that
    # overlapped it. The natural composite key takes over.
    op.drop_constraint(PANTRY_UQ, "pantry", type_="unique")
    op.drop_constraint(PANTRY_PK, "pantry", type_="primary")
    op.drop_column("pantry", "pantry_id")
    op.create_primary_key(
        PANTRY_PK, "pantry", ["user_id", "ingredient_id"]
    )

    # ---------- user_allergies ----------
    op.add_column(
        "user_allergies",
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
    )

    # ---------- households ----------
    op.add_column(
        "households",
        sa.Column(
            "created_by",
            sa.Integer,
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "households",
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
    )

    # ---------- household_members ----------
    op.add_column(
        "household_members",
        sa.Column(
            "joined_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
    )


def downgrade() -> None:
    # ---------- household_members ----------
    op.drop_column("household_members", "joined_at")

    # ---------- households ----------
    op.drop_column("households", "created_at")
    op.drop_column("households", "created_by")

    # ---------- user_allergies ----------
    op.drop_column("user_allergies", "created_at")

    # ---------- pantry ----------
    # Restore the surrogate key + unique constraint.
    op.drop_constraint(PANTRY_PK, "pantry", type_="primary")
    op.add_column(
        "pantry",
        sa.Column(
            "pantry_id",
            sa.Integer,
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
    )
    op.create_primary_key(PANTRY_PK, "pantry", ["pantry_id"])
    op.create_unique_constraint(
        PANTRY_UQ, "pantry", ["user_id", "ingredient_id"]
    )
    op.drop_column("pantry", "updated_at")
    op.drop_column("pantry", "created_at")
    op.drop_column("pantry", "expiry_date")
    op.drop_column("pantry", "purchase_date")
    op.drop_column("pantry", "unit")
    op.drop_column("pantry", "quantity")

    # ---------- recipe_ingredients ----------
    op.drop_constraint(
        RECIPE_INGREDIENTS_INGREDIENT_FK,
        "recipe_ingredients",
        type_="foreignkey",
    )
    op.create_foreign_key(
        RECIPE_INGREDIENTS_INGREDIENT_FK,
        "recipe_ingredients",
        "ingredients",
        ["ingredient_id"],
        ["ingredient_id"],
        ondelete="RESTRICT",
    )
    op.drop_column("recipe_ingredients", "unit")
    op.drop_column("recipe_ingredients", "quantity")

    # ---------- recipes ----------
    op.drop_column("recipes", "created_at")
    op.drop_column("recipes", "created_by")

    # ---------- ingredients ----------
    op.drop_constraint(
        "ck_ingredient_name_normalized", "ingredients", type_="check"
    )
    op.drop_column("ingredients", "created_at")

    # ---------- users ----------
    op.drop_column("users", "created_at")
    op.drop_column("users", "last_name")
