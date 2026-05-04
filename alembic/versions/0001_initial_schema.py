"""Initial schema: users, ingredients, recipes, recipe_ingredients, pantry, user_allergies.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-04 12:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
    )

    op.create_table(
        "ingredients",
        sa.Column("ingredient_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
    )

    op.create_table(
        "recipes",
        sa.Column("recipe_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("recipe_name", sa.String(length=200), nullable=False),
        sa.Column("recipe_steps", sa.Text, nullable=False),
    )

    op.create_table(
        "recipe_ingredients",
        sa.Column(
            "recipe_id",
            sa.Integer,
            sa.ForeignKey("recipes.recipe_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "ingredient_id",
            sa.Integer,
            sa.ForeignKey("ingredients.ingredient_id", ondelete="RESTRICT"),
            primary_key=True,
        ),
    )

    op.create_table(
        "pantry",
        sa.Column("pantry_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ingredient_id",
            sa.Integer,
            sa.ForeignKey("ingredients.ingredient_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "is_shared_with_household",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.UniqueConstraint(
            "user_id", "ingredient_id", name="uq_pantry_user_ingredient"
        ),
    )

    op.create_table(
        "user_allergies",
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "ingredient_id",
            sa.Integer,
            sa.ForeignKey("ingredients.ingredient_id", ondelete="RESTRICT"),
            primary_key=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("user_allergies")
    op.drop_table("pantry")
    op.drop_table("recipe_ingredients")
    op.drop_table("recipes")
    op.drop_table("ingredients")
    op.drop_table("users")
