"""Recipe lookup endpoints."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, func, insert, select

from src import database as db
from src.api.helpers import assert_exists, logger

router = APIRouter(prefix="/recipes", tags=["recipes"])


class CompatibleRecipe(BaseModel):
    recipe_id: int
    recipe_name: str
    recipe_steps: str


@router.get("/get_compatible", response_model=List[CompatibleRecipe])
def get_compatible(
    ingredient_ids: List[int] = Query(
        ...,
        description=(
            "Ingredient IDs the user has on hand. Pass repeated query params, "
            "e.g. ?ingredient_ids=1&ingredient_ids=2&ingredient_ids=3"
        ),
        min_length=1,
    ),
    user_id: Optional[int] = Query(
        default=None,
        description=(
            "Optional. If provided, recipes containing any of the user's "
            "recorded allergens are excluded from the results."
        ),
    ),
) -> List[CompatibleRecipe]:
    """Return recipes whose required ingredients are all in `ingredient_ids`.

    A recipe is "compatible" if every ingredient it requires appears in the
    caller-supplied list. If `user_id` is given, recipes that include any
    ingredient flagged as an allergy for that user are filtered out, even
    when the user happens to have the allergen in their pantry.
    """
    # Deduplicate so repeated query params (?ingredient_ids=1&ingredient_ids=1)
    # don't inflate the parameter binding unnecessarily.
    available = list(set(ingredient_ids))

    with db.engine.connect() as conn:
        allergen_ids: list[int] = []
        if user_id is not None:
            assert_exists(conn, db.users.c.user_id, user_id, label="User")
            allergen_ids = [
                row.ingredient_id
                for row in conn.execute(
                    select(db.user_allergies.c.ingredient_id).where(
                        db.user_allergies.c.user_id == user_id
                    )
                )
            ]

        # A recipe is compatible iff:
        #   1) Every required ingredient is in `available`, i.e. the count of
        #      required rows equals the count of required rows that are
        #      members of `available`.
        #   2) None of its required ingredients is in `allergen_ids`.
        # Both checks live in a HAVING clause so the DB does the filtering
        # and we don't ship every recipe + ingredient list back to Python.
        total_required = func.count(db.recipe_ingredients.c.ingredient_id)
        available_required = func.count(db.recipe_ingredients.c.ingredient_id).filter(
            db.recipe_ingredients.c.ingredient_id.in_(available)
        )

        having_clauses = [total_required == available_required]
        if allergen_ids:
            allergen_required = func.count(
                db.recipe_ingredients.c.ingredient_id
            ).filter(db.recipe_ingredients.c.ingredient_id.in_(allergen_ids))
            having_clauses.append(allergen_required == 0)

        stmt = (
            select(
                db.recipes.c.recipe_id,
                db.recipes.c.recipe_name,
                db.recipes.c.recipe_steps,
            )
            .select_from(
                db.recipes.join(
                    db.recipe_ingredients,
                    db.recipes.c.recipe_id == db.recipe_ingredients.c.recipe_id,
                )
            )
            .group_by(
                db.recipes.c.recipe_id,
                db.recipes.c.recipe_name,
                db.recipes.c.recipe_steps,
            )
            .having(and_(*having_clauses))
            .order_by(db.recipes.c.recipe_id)
        )

        return [
            CompatibleRecipe(
                recipe_id=row.recipe_id,
                recipe_name=row.recipe_name,
                recipe_steps=row.recipe_steps,
            )
            for row in conn.execute(stmt)
        ]


class RecipeSummary(BaseModel):
    recipe_id: int
    recipe_name: str
    recipe_steps: str
    created_by: Optional[int] = None
    created_at: datetime


@router.get("", response_model=List[RecipeSummary])
def list_recipes(
    q: Optional[str] = Query(
        default=None,
        description="Case-insensitive substring search on recipe_name.",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> List[RecipeSummary]:
    """Browse / search the recipe catalog with paging."""
    with db.engine.connect() as conn:
        stmt = select(
            db.recipes.c.recipe_id,
            db.recipes.c.recipe_name,
            db.recipes.c.recipe_steps,
            db.recipes.c.created_by,
            db.recipes.c.created_at,
        )
        if q:
            # `ILIKE` is case-insensitive in Postgres.
            stmt = stmt.where(db.recipes.c.recipe_name.ilike(f"%{q}%"))
        stmt = (
            stmt.order_by(db.recipes.c.recipe_id).limit(limit).offset(offset)
        )

        return [
            RecipeSummary(
                recipe_id=row.recipe_id,
                recipe_name=row.recipe_name,
                recipe_steps=row.recipe_steps,
                created_by=row.created_by,
                created_at=row.created_at,
            )
            for row in conn.execute(stmt)
        ]


class RecipeIngredientInput(BaseModel):
    ingredient_id: int
    quantity: Optional[Decimal] = Field(default=None, ge=0)
    unit: Optional[str] = Field(default=None, max_length=50)

    @field_validator("unit")
    @classmethod
    def _clean_unit(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip().lower()
        return cleaned or None


class CreateRecipeRequest(BaseModel):
    created_by: int = Field(
        ..., description="user_id of the user authoring this recipe."
    )
    recipe_name: str = Field(..., min_length=1, max_length=200)
    recipe_steps: str = Field(..., min_length=1)
    ingredients: List[RecipeIngredientInput] = Field(..., min_length=1)

    @field_validator("recipe_name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("recipe_name must not be blank.")
        return cleaned

    @field_validator("recipe_steps")
    @classmethod
    def _clean_steps(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("recipe_steps must not be blank.")
        return cleaned

    @field_validator("ingredients")
    @classmethod
    def _no_duplicate_ingredients(
        cls, value: List["RecipeIngredientInput"]
    ) -> List["RecipeIngredientInput"]:
        seen: set[int] = set()
        for item in value:
            if item.ingredient_id in seen:
                raise ValueError(
                    f"Duplicate ingredient_id={item.ingredient_id} in ingredients."
                )
            seen.add(item.ingredient_id)
        return value


class CreateRecipeResponse(BaseModel):
    recipe_id: int


@router.post("", response_model=CreateRecipeResponse, status_code=201)
def create_recipe(payload: CreateRecipeRequest) -> CreateRecipeResponse:
    """Create a user-authored recipe and its ingredient list atomically."""
    with db.engine.begin() as conn:
        assert_exists(conn, db.users.c.user_id, payload.created_by, label="User")

        # Validate every referenced ingredient up front so the recipe row
        # never gets created without a complete ingredient list.
        requested_ids = [item.ingredient_id for item in payload.ingredients]
        found_ids = {
            row.ingredient_id
            for row in conn.execute(
                select(db.ingredients.c.ingredient_id).where(
                    db.ingredients.c.ingredient_id.in_(requested_ids)
                )
            )
        }
        missing = sorted(set(requested_ids) - found_ids)
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown ingredient_id(s): {missing}",
            )

        try:
            recipe_id = conn.execute(
                insert(db.recipes)
                .values(
                    recipe_name=payload.recipe_name,
                    recipe_steps=payload.recipe_steps,
                    created_by=payload.created_by,
                )
                .returning(db.recipes.c.recipe_id)
            ).scalar_one()

            conn.execute(
                insert(db.recipe_ingredients),
                [
                    {
                        "recipe_id": recipe_id,
                        "ingredient_id": item.ingredient_id,
                        "quantity": item.quantity,
                        "unit": item.unit,
                    }
                    for item in payload.ingredients
                ],
            )
        except Exception as exc:
            logger.error(
                "create_recipe failed for user_id=%s name=%r: %s",
                payload.created_by,
                payload.recipe_name,
                exc,
            )
            raise

    return CreateRecipeResponse(recipe_id=recipe_id)
