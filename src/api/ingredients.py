"""Pantry ingredient management."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src import database as db

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


class SaveIngredientRequest(BaseModel):
    user_id: int
    ingredient_id: int
    # Default TRUE — items are visible to housemates unless the user
    # explicitly opts out for that ingredient.
    is_shared_with_household: bool = Field(default=True)


class SuccessResponse(BaseModel):
    success: bool


@router.post("/save", response_model=SuccessResponse)
def save_ingredient(payload: SaveIngredientRequest) -> SuccessResponse:
    with db.engine.begin() as conn:
        user_exists = conn.execute(
            select(db.users.c.user_id).where(db.users.c.user_id == payload.user_id)
        ).first()
        if not user_exists:
            raise HTTPException(status_code=404, detail="User not found.")

        ingredient_exists = conn.execute(
            select(db.ingredients.c.ingredient_id).where(
                db.ingredients.c.ingredient_id == payload.ingredient_id
            )
        ).first()
        if not ingredient_exists:
            raise HTTPException(status_code=404, detail="Ingredient not found.")

        # Idempotent save: re-saving the same ingredient just refreshes the
        # is_shared_with_household flag rather than erroring.
        stmt = (
            pg_insert(db.pantry)
            .values(
                user_id=payload.user_id,
                ingredient_id=payload.ingredient_id,
                is_shared_with_household=payload.is_shared_with_household,
            )
            .on_conflict_do_update(
                constraint="uq_pantry_user_ingredient",
                set_={"is_shared_with_household": payload.is_shared_with_household},
            )
        )
        conn.execute(stmt)
    return SuccessResponse(success=True)


class DeleteIngredientRequest(BaseModel):
    user_id: int
    ingredient_id: int


@router.post("/delete", response_model=SuccessResponse)
def delete_ingredient(payload: DeleteIngredientRequest) -> SuccessResponse:
    """Remove an ingredient from the user's pantry.

    Returns 404 if the user has no such ingredient — otherwise the caller
    can't tell whether the delete actually did anything, which makes
    Flow 3 (David tidying his pantry) harder to reason about.
    """
    with db.engine.begin() as conn:
        result = conn.execute(
            delete(db.pantry).where(
                db.pantry.c.user_id == payload.user_id,
                db.pantry.c.ingredient_id == payload.ingredient_id,
            )
        )
        if result.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="That ingredient is not in this user's pantry.",
            )
    return SuccessResponse(success=True)

@router.get("/get_all_ingredients", response_model=List[Ingredient])
def get_all_ingredients() -> List[Ingredient]:
    """Return list of all ingredients.
    """
    with db.engine.begin() as conn:
        results = conn.execute(
                """
                SELECT *
                FROM ingredients
                """
        )

        all_ingredients: list[Ingredient] = []
        for row in results:
            all_ingredients.append(
                Ingredient(
                    ingredient_id=row.ingredient_id,
                    ingredient_name=row.name,
                )
            )

    return all_ingredients