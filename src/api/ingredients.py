"""Pantry ingredient management."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select, text as sql_text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src import database as db
from src.api.helpers import assert_exists
from src.api.models import SuccessResponse

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


class SaveIngredientRequest(BaseModel):
    user_id: int
    ingredient_id: int
    is_shared_with_household: bool = Field(default=True)

    # Optional quantity tracking. All four fields are nullable in the schema,
    # so a save with just the IDs continues to work exactly as before.
    quantity: Optional[Decimal] = Field(default=None, ge=0)
    unit: Optional[str] = Field(default=None, max_length=50)
    purchase_date: Optional[date] = None
    expiry_date: Optional[date] = None

    @field_validator("unit")
    @classmethod
    def _clean_unit(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip().lower()
        return cleaned or None


@router.post("/save", response_model=SuccessResponse)
def save_ingredient(payload: SaveIngredientRequest) -> SuccessResponse:
    with db.engine.begin() as conn:
        assert_exists(conn, db.users.c.user_id, payload.user_id, label="User")
        assert_exists(
            conn,
            db.ingredients.c.ingredient_id,
            payload.ingredient_id,
            label="Ingredient",
        )

        # On conflict we always bump updated_at to NOW() so the row tracks
        # the latest write, even if every other field is unchanged.
        stmt = (
            pg_insert(db.pantry)
            .values(
                user_id=payload.user_id,
                ingredient_id=payload.ingredient_id,
                is_shared_with_household=payload.is_shared_with_household,
                quantity=payload.quantity,
                unit=payload.unit,
                purchase_date=payload.purchase_date,
                expiry_date=payload.expiry_date,
            )
            .on_conflict_do_update(
                constraint="pantry_pkey",
                set_={
                    "is_shared_with_household": payload.is_shared_with_household,
                    "quantity": payload.quantity,
                    "unit": payload.unit,
                    "purchase_date": payload.purchase_date,
                    "expiry_date": payload.expiry_date,
                    "updated_at": sql_text("NOW()"),
                },
            )
        )
        conn.execute(stmt)

    return SuccessResponse(success=True, message="Ingredient saved to pantry.")


class DeleteIngredientRequest(BaseModel):
    user_id: int
    ingredient_id: int


def _delete_pantry_item(user_id: int, ingredient_id: int) -> SuccessResponse:
    """Shared deletion logic for both the legacy POST and RESTful DELETE."""
    with db.engine.begin() as conn:
        # Explicit existence checks so callers get a distinct error when
        # the user or ingredient row doesn't exist (versus when the pantry
        # link just isn't there).
        assert_exists(conn, db.users.c.user_id, user_id, label="User")
        assert_exists(
            conn,
            db.ingredients.c.ingredient_id,
            ingredient_id,
            label="Ingredient",
        )

        result = conn.execute(
            delete(db.pantry).where(
                db.pantry.c.user_id == user_id,
                db.pantry.c.ingredient_id == ingredient_id,
            )
        )

        if result.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="That ingredient is not in this user's pantry.",
            )

    return SuccessResponse(success=True, message="Ingredient removed from pantry.")


@router.post(
    "/delete",
    response_model=SuccessResponse,
    deprecated=True,
    summary="Deprecated: use DELETE /ingredients/{ingredient_id} instead.",
)
def delete_ingredient(payload: DeleteIngredientRequest) -> SuccessResponse:
    return _delete_pantry_item(payload.user_id, payload.ingredient_id)


@router.delete("/{ingredient_id}", response_model=SuccessResponse)
def remove_ingredient(ingredient_id: int, user_id: int) -> SuccessResponse:
    """Remove an ingredient from `user_id`'s pantry.

    `user_id` is passed as a query parameter rather than in the path because
    pantry items are conceptually scoped to the calling user.
    """
    return _delete_pantry_item(user_id, ingredient_id)


class Ingredient(BaseModel):
    ingredient_id: int
    ingredient_name: str


def _query_ingredients() -> List[Ingredient]:
    """Shared read-side body for the legacy + RESTful list endpoints."""
    with db.engine.connect() as conn:
        stmt = select(
            db.ingredients.c.ingredient_id, db.ingredients.c.name
        ).order_by(db.ingredients.c.ingredient_id)
        return [
            Ingredient(
                ingredient_id=row.ingredient_id,
                ingredient_name=row.name,
            )
            for row in conn.execute(stmt)
        ]


@router.get(
    "/get_all_ingredients",
    response_model=List[Ingredient],
    deprecated=True,
    summary="Deprecated: use GET /ingredients instead.",
)
def get_all_ingredients() -> List[Ingredient]:
    """Return the full ingredient catalog (legacy path)."""
    return _query_ingredients()


@router.get("", response_model=List[Ingredient])
def list_ingredients() -> List[Ingredient]:
    """Return the full ingredient catalog, ordered by ingredient_id."""
    return _query_ingredients()
