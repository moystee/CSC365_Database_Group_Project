"""Recipe lookup endpoints."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from typing import List
from src import database as db

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
    if not ingredient_ids:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one ingredient_id.",
        )

    available = set(ingredient_ids)

    with db.engine.begin() as conn:
        allergen_ids: set[int] = set()
        if user_id is not None:
            user_exists = conn.execute(
                select(db.users.c.user_id).where(db.users.c.user_id == user_id)
            ).first()
            if not user_exists:
                raise HTTPException(status_code=404, detail="User not found.")
            allergen_ids = {
                row.ingredient_id
                for row in conn.execute(
                    select(db.user_allergies.c.ingredient_id).where(
                        db.user_allergies.c.user_id == user_id
                    )
                )
            }

        # Pull every recipe with the full ingredient list aggregated, then
        # filter in Python. The recipe catalog is small for V1, so this is
        # plenty fast and far easier to read than a pure-SQL set-difference.
        stmt = (
            select(
                db.recipes.c.recipe_id,
                db.recipes.c.recipe_name,
                db.recipes.c.recipe_steps,
                func.array_agg(db.recipe_ingredients.c.ingredient_id).label(
                    "needed_ingredients"
                ),
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
        )

        results: list[CompatibleRecipe] = []
        for row in conn.execute(stmt):
            needed = set(row.needed_ingredients or [])
            if not needed.issubset(available):
                continue
            if needed & allergen_ids:
                continue
            results.append(
                CompatibleRecipe(
                    recipe_id=row.recipe_id,
                    recipe_name=row.recipe_name,
                    recipe_steps=row.recipe_steps,
                )
            )

    return results
