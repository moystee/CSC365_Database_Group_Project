"""User-related endpoints (sign up, allergies, profile)."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError

from src import database as db
from src.api.helpers import assert_exists, logger
from src.api.models import SuccessResponse

router = APIRouter(prefix="/users", tags=["users"])


def _clean_name(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class CreateUserRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    email: EmailStr

    @field_validator("first_name")
    @classmethod
    def _sanitize_first_name(cls, value: str) -> str:
        # Reject pure-whitespace names so users can't sign up as "   ".
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("first_name must not be blank.")
        return cleaned

    @field_validator("last_name")
    @classmethod
    def _sanitize_last_name(cls, value: Optional[str]) -> Optional[str]:
        return _clean_name(value)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        # Email is unique; uppercase variants of the same address should
        # collide, so normalize before insert.
        return value.strip().lower()


class CreateUserResponse(BaseModel):
    user_id: int


@router.post("/create", response_model=CreateUserResponse, status_code=201)
def create_user(payload: CreateUserRequest) -> CreateUserResponse:
    stmt = (
        insert(db.users)
        .values(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
        )
        .returning(db.users.c.user_id)
    )
    with db.engine.begin() as conn:
        try:
            result = conn.execute(stmt)
        except IntegrityError as exc:
            logger.info("Duplicate signup attempt for email=%s", payload.email)
            raise HTTPException(
                status_code=409, detail="A user with that email already exists."
            ) from exc
        user_id = result.scalar_one()
    return CreateUserResponse(user_id=user_id)


class UserProfile(BaseModel):
    user_id: int
    first_name: str
    last_name: Optional[str] = None
    email: str
    created_at: datetime


@router.get("/{user_id}", response_model=UserProfile)
def get_user(user_id: int) -> UserProfile:
    """Return the public profile for a single user."""
    with db.engine.connect() as conn:
        row = conn.execute(
            select(
                db.users.c.user_id,
                db.users.c.first_name,
                db.users.c.last_name,
                db.users.c.email,
                db.users.c.created_at,
            ).where(db.users.c.user_id == user_id)
        ).first()
        if not row:
            raise HTTPException(status_code=404, detail="User not found.")
        return UserProfile(
            user_id=row.user_id,
            first_name=row.first_name,
            last_name=row.last_name,
            email=row.email,
            created_at=row.created_at,
        )


@router.delete("/{user_id}", response_model=SuccessResponse)
def delete_user(user_id: int) -> SuccessResponse:
    """Delete a user account.

    All FK relationships fan out with `ON DELETE CASCADE` (pantry,
    user_allergies, household_members) so the user's pantry items and
    memberships disappear along with the row.
    """
    with db.engine.begin() as conn:
        assert_exists(conn, db.users.c.user_id, user_id, label="User")
        conn.execute(delete(db.users).where(db.users.c.user_id == user_id))
    return SuccessResponse(success=True, message="User account deleted.")


class AddAllergyRequest(BaseModel):
    user_id: int
    ingredient_id: int


@router.post("/add_allergy", response_model=SuccessResponse)
def add_allergy(payload: AddAllergyRequest) -> SuccessResponse:
    with db.engine.begin() as conn:
        assert_exists(conn, db.users.c.user_id, payload.user_id, label="User")
        assert_exists(
            conn,
            db.ingredients.c.ingredient_id,
            payload.ingredient_id,
            label="Ingredient",
        )

        # Check explicitly so we can return a meaningful response instead of
        # silently swallowing the IntegrityError.
        already_recorded = conn.execute(
            select(db.user_allergies.c.ingredient_id).where(
                db.user_allergies.c.user_id == payload.user_id,
                db.user_allergies.c.ingredient_id == payload.ingredient_id,
            )
        ).first()
        if already_recorded:
            return SuccessResponse(
                success=True,
                message="Allergy was already on file; no change made.",
            )

        try:
            conn.execute(
                insert(db.user_allergies).values(
                    user_id=payload.user_id,
                    ingredient_id=payload.ingredient_id,
                )
            )
        except IntegrityError as exc:
            # Race condition: another request inserted the same row between
            # our existence check and this insert. Surface a real response.
            logger.warning(
                "Race-condition duplicate allergy insert for user_id=%s "
                "ingredient_id=%s: %s",
                payload.user_id,
                payload.ingredient_id,
                exc,
            )
            return SuccessResponse(
                success=True,
                message="Allergy was already on file; no change made.",
            )

    return SuccessResponse(
        success=True, message="Allergy recorded."
    )


@router.delete(
    "/{user_id}/allergies/{ingredient_id}", response_model=SuccessResponse
)
def remove_allergy(user_id: int, ingredient_id: int) -> SuccessResponse:
    """Remove an allergy record. Idempotent-ish: 404 if it wasn't set."""
    with db.engine.begin() as conn:
        assert_exists(conn, db.users.c.user_id, user_id, label="User")
        assert_exists(
            conn,
            db.ingredients.c.ingredient_id,
            ingredient_id,
            label="Ingredient",
        )

        result = conn.execute(
            delete(db.user_allergies).where(
                db.user_allergies.c.user_id == user_id,
                db.user_allergies.c.ingredient_id == ingredient_id,
            )
        )
        if result.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="That allergy is not on file for this user.",
            )

    return SuccessResponse(success=True, message="Allergy removed.")


class GetAllergiesRequest(BaseModel):
    user_id: int


class Allergy(BaseModel):
    ingredient_name: str


def _query_allergies(user_id: int) -> list[Allergy]:
    """Shared body for the legacy POST handler and the RESTful GET handler."""
    with db.engine.connect() as conn:
        assert_exists(conn, db.users.c.user_id, user_id, label="User")

        stmt = (
            select(db.ingredients.c.name)
            .select_from(
                db.user_allergies.join(
                    db.ingredients,
                    db.user_allergies.c.ingredient_id
                    == db.ingredients.c.ingredient_id,
                )
            )
            .where(db.user_allergies.c.user_id == user_id)
            .order_by(db.ingredients.c.name)
        )
        return [Allergy(ingredient_name=row.name) for row in conn.execute(stmt)]


@router.post(
    "/get_allergies",
    response_model=list[Allergy],
    deprecated=True,
    summary="Deprecated: use GET /users/{user_id}/allergies instead.",
)
def get_allergies(payload: GetAllergiesRequest) -> list[Allergy]:
    """Return the ingredient names a user has flagged as allergies.

    Kept for backward compatibility with the original V2 spec. New clients
    should call `GET /users/{user_id}/allergies`.
    """
    return _query_allergies(payload.user_id)


@router.get("/{user_id}/allergies", response_model=list[Allergy])
def list_allergies(user_id: int) -> list[Allergy]:
    """Return the ingredient names this user has flagged as allergies."""
    return _query_allergies(user_id)


class MissingIngredient(BaseModel):
    ingredient_id: int
    name: str


class TopRecipe(BaseModel):
    recipe_id: int
    recipe_name: str
    recipe_steps: str
    coverage_pct: int
    have_count: int
    total_count: int
    missing_ingredients: List[MissingIngredient]


@router.get(
    "/{user_id}/top-recipes",
    response_model=List[TopRecipe],
    summary="Complex endpoint: rank recipes by pantry coverage",
)
def top_recipes(
    user_id: int,
    limit: int = Query(default=5, ge=1, le=50),
) -> List[TopRecipe]:
    """Return recipes ranked by how much of each one the user can already make.

    Considers the user's own pantry plus shared items from household members,
    and excludes any recipe that contains one of the user's allergens. Partial
    matches are included (unlike ``GET /recipes/get_compatible``).
    """
    with db.engine.connect() as conn:
        assert_exists(conn, db.users.c.user_id, user_id, label="User")

        my_pantry = select(db.pantry.c.ingredient_id).where(
            db.pantry.c.user_id == user_id
        )
        my_households = select(db.household_members.c.household_id).where(
            db.household_members.c.user_id == user_id
        )
        housemates = (
            select(db.household_members.c.user_id)
            .where(db.household_members.c.household_id.in_(my_households))
            .where(db.household_members.c.user_id != user_id)
        )
        shared_pantry = select(db.pantry.c.ingredient_id).where(
            db.pantry.c.user_id.in_(housemates),
            db.pantry.c.is_shared_with_household.is_(True),
        )
        available_stmt = my_pantry.union(shared_pantry)
        available_ids = list(
            {
                row.ingredient_id
                for row in conn.execute(available_stmt)
            }
        )

        allergen_recipe_ids = [
            row.recipe_id
            for row in conn.execute(
                select(db.recipe_ingredients.c.recipe_id)
                .where(
                    db.recipe_ingredients.c.ingredient_id.in_(
                        select(db.user_allergies.c.ingredient_id).where(
                            db.user_allergies.c.user_id == user_id
                        )
                    )
                )
                .distinct()
            )
        ]

        # Pass 2: aggregate from recipe_ingredients only (650k rows), then join
        # recipes for the top-N names — avoids hashing the full recipes table.
        total_required = func.count(db.recipe_ingredients.c.ingredient_id)
        have_required = func.count(db.recipe_ingredients.c.ingredient_id)
        if available_ids:
            have_required = have_required.filter(
                db.recipe_ingredients.c.ingredient_id.in_(available_ids)
            )

        coverage = (
            select(
                db.recipe_ingredients.c.recipe_id,
                total_required.label("total_count"),
                have_required.label("have_count"),
            )
            .group_by(db.recipe_ingredients.c.recipe_id)
            .having(total_required > 0)
        )
        if allergen_recipe_ids:
            coverage = coverage.where(
                db.recipe_ingredients.c.recipe_id.not_in(allergen_recipe_ids)
            )

        coverage_sq = coverage.subquery("coverage")

        ranked = (
            select(
                db.recipes.c.recipe_id,
                db.recipes.c.recipe_name,
                db.recipes.c.recipe_steps,
                coverage_sq.c.total_count,
                coverage_sq.c.have_count,
            )
            .select_from(
                coverage_sq.join(
                    db.recipes,
                    db.recipes.c.recipe_id == coverage_sq.c.recipe_id,
                )
            )
            .order_by(
                coverage_sq.c.have_count.desc(),
                db.recipes.c.recipe_name,
            )
            .limit(limit)
        )

        rows = conn.execute(ranked).all()
        if not rows:
            return []

        recipe_ids = [row.recipe_id for row in rows]
        missing_stmt = (
            select(
                db.recipe_ingredients.c.recipe_id,
                db.ingredients.c.ingredient_id,
                db.ingredients.c.name,
            )
            .select_from(
                db.recipe_ingredients.join(
                    db.ingredients,
                    db.recipe_ingredients.c.ingredient_id
                    == db.ingredients.c.ingredient_id,
                )
            )
            .where(db.recipe_ingredients.c.recipe_id.in_(recipe_ids))
        )
        if available_ids:
            missing_stmt = missing_stmt.where(
                db.recipe_ingredients.c.ingredient_id.not_in(available_ids)
            )
        missing_rows = conn.execute(
            missing_stmt.order_by(
                db.recipe_ingredients.c.recipe_id, db.ingredients.c.name
            )
        ).all()

    missing_by_recipe: dict[int, list[MissingIngredient]] = {
        rid: [] for rid in recipe_ids
    }
    for row in missing_rows:
        missing_by_recipe[row.recipe_id].append(
            MissingIngredient(ingredient_id=row.ingredient_id, name=row.name)
        )

    results: list[TopRecipe] = []
    for row in rows:
        total = row.total_count or 0
        have = row.have_count or 0
        coverage = round(100 * have / total) if total else 0
        results.append(
            TopRecipe(
                recipe_id=row.recipe_id,
                recipe_name=row.recipe_name,
                recipe_steps=row.recipe_steps,
                coverage_pct=coverage,
                have_count=have,
                total_count=total,
                missing_ingredients=missing_by_recipe[row.recipe_id],
            )
        )
    return results
