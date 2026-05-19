"""Pantry read endpoint with household-aware merging."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import and_, or_, select

from src import database as db
from src.api.helpers import assert_exists

router = APIRouter(prefix="/pantry", tags=["pantry"])


class PantryIngredient(BaseModel):
    ingredient_id: int
    name: str


@router.get("/get_ingredients", response_model=List[PantryIngredient])
def get_ingredients(user_id: int = Query(..., description="User to fetch the pantry for.")):
    """Return ingredients available to `user_id`.

    Always includes every ingredient in the user's own pantry. If the user
    is a member of any households, also includes ingredients from other
    members of those households whose pantry items are flagged
    `is_shared_with_household = true`. Duplicates across pantries collapse
    to a single entry.
    """
    # Read-only path: `engine.connect()` doesn't hold a write transaction
    # slot the way `engine.begin()` does.
    with db.engine.connect() as conn:
        assert_exists(conn, db.users.c.user_id, user_id, label="User")

        # Every household-mate (other users in any of this user's households).
        my_households = select(db.household_members.c.household_id).where(
            db.household_members.c.user_id == user_id
        )
        housemates = (
            select(db.household_members.c.user_id)
            .where(db.household_members.c.household_id.in_(my_households))
            .where(db.household_members.c.user_id != user_id)
        )

        # Ingredients in my pantry OR in a housemate's shared pantry.
        stmt = (
            select(
                db.ingredients.c.ingredient_id,
                db.ingredients.c.name,
            )
            .select_from(
                db.pantry.join(
                    db.ingredients,
                    db.pantry.c.ingredient_id == db.ingredients.c.ingredient_id,
                )
            )
            .where(
                or_(
                    db.pantry.c.user_id == user_id,
                    and_(
                        db.pantry.c.user_id.in_(housemates),
                        db.pantry.c.is_shared_with_household.is_(True),
                    ),
                )
            )
            .distinct()
            .order_by(db.ingredients.c.ingredient_id)
        )

        return [
            PantryIngredient(ingredient_id=row.ingredient_id, name=row.name)
            for row in conn.execute(stmt)
        ]
