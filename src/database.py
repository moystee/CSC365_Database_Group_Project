"""Database engine + table metadata.

We use SQLAlchemy Core (not the ORM) so that the same Table objects can be
imported by both the FastAPI route handlers and the Alembic migrations.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    create_engine,
    text,
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
    Column("last_name", String(100), nullable=True),
    Column("email", String(255), nullable=False, unique=True),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    ),
)

ingredients = Table(
    "ingredients",
    metadata,
    Column("ingredient_id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False, unique=True),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    ),
    CheckConstraint(
        "name = LOWER(name) AND name = TRIM(name) AND length(name) > 0",
        name="ck_ingredient_name_normalized",
    ),
)

recipes = Table(
    "recipes",
    metadata,
    Column("recipe_id", Integer, primary_key=True, autoincrement=True),
    Column("recipe_name", String(200), nullable=False),
    Column("recipe_steps", Text, nullable=False),
    Column(
        "created_by",
        Integer,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    ),
)

# Junction: which ingredients each recipe needs, optionally with how much.
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
        ForeignKey("ingredients.ingredient_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("quantity", Numeric(10, 2), nullable=True),
    Column("unit", String(50), nullable=True),
)

# A user's pantry: each (user_id, ingredient_id) pair is the natural key.
pantry = Table(
    "pantry",
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
    # Default to TRUE: a pantry item is shared with the household by
    # default. Users can opt out per-item to keep a private stash.
    Column("is_shared_with_household", Boolean, nullable=False, server_default="true"),
    Column("quantity", Numeric(10, 2), nullable=True),
    Column("unit", String(50), nullable=True),
    Column("purchase_date", Date, nullable=True),
    Column("expiry_date", Date, nullable=True),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    ),
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
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    ),
)

households = Table(
    "households",
    metadata,
    Column("household_id", Integer, primary_key=True, autoincrement=True),
    Column("household_name", String(200), nullable=False),
    Column(
        "created_by",
        Integer,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    ),
)

# A user can belong to one or more households; each membership is a row.
household_members = Table(
    "household_members",
    metadata,
    Column(
        "household_id",
        Integer,
        ForeignKey("households.household_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "user_id",
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "joined_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    ),
)
