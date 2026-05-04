"""Database engine + table metadata.

We use SQLAlchemy Core (not the ORM) so that the same Table objects can be
imported by both the FastAPI route handlers and the Alembic migrations.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
)

load_dotenv()

POSTGRES_URI = os.environ.get("POSTGRES_URI")
if not POSTGRES_URI:
    raise RuntimeError(
        "POSTGRES_URI is not set. Copy .env.example to .env and fill it in."
    )

engine = create_engine(POSTGRES_URI, pool_pre_ping=True)

metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("user_id", Integer, primary_key=True, autoincrement=True),
    Column("first_name", String(100), nullable=False),
    Column("email", String(255), nullable=False, unique=True),
)

ingredients = Table(
    "ingredients",
    metadata,
    Column("ingredient_id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False, unique=True),
)

recipes = Table(
    "recipes",
    metadata,
    Column("recipe_id", Integer, primary_key=True, autoincrement=True),
    Column("recipe_name", String(200), nullable=False),
    Column("recipe_steps", Text, nullable=False),
)

# Junction: which ingredients each recipe needs.
recipe_ingredients = Table(
    "recipe_ingredients",
    metadata,
    Column(
        "recipe_id",
        Integer,
        ForeignKey("recipes.recipe_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "ingredient_id",
        Integer,
        ForeignKey("ingredients.ingredient_id", ondelete="RESTRICT"),
        primary_key=True,
    ),
)

# A user's pantry: each row is one ingredient owned by one user.
pantry = Table(
    "pantry",
    metadata,
    Column("pantry_id", Integer, primary_key=True, autoincrement=True),
    Column(
        "user_id",
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "ingredient_id",
        Integer,
        ForeignKey("ingredients.ingredient_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("is_shared_with_household", Boolean, nullable=False, server_default="false"),
    UniqueConstraint("user_id", "ingredient_id", name="uq_pantry_user_ingredient"),
)

user_allergies = Table(
    "user_allergies",
    metadata,
    Column(
        "user_id",
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "ingredient_id",
        Integer,
        ForeignKey("ingredients.ingredient_id", ondelete="RESTRICT"),
        primary_key=True,
    ),
)
