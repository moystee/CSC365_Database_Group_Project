"""Household creation and membership endpoints."""

from __future__ import annotations

from decimal import Decimal
from typing import List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, delete, insert, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src import database as db
from src.api.helpers import assert_exists, logger, transactional
from src.api.models import SuccessResponse

router = APIRouter(prefix="/households", tags=["households"])


class CreateHouseholdRequest(BaseModel):
    user_id: int
    household_name: str = Field(..., min_length=1, max_length=200)

    @field_validator("household_name")
    @classmethod
    def _sanitize_household_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("household_name must not be blank.")
        return cleaned


class CreateHouseholdResponse(BaseModel):
    household_id: int


@router.post("/create", response_model=CreateHouseholdResponse, status_code=201)
def create_household(payload: CreateHouseholdRequest) -> CreateHouseholdResponse:
    """Create a new household and add the requesting user as the first member.

    The household row and the membership row are written inside the same
    transaction. If the membership insert fails, the household insert is
    rolled back so we never end up with a household that has no creator.
    """
    with db.engine.begin() as conn:
        assert_exists(conn, db.users.c.user_id, payload.user_id, label="User")

        existing_membership = conn.execute(
            select(db.household_members.c.household_id).where(
                db.household_members.c.user_id == payload.user_id
            )
        ).first()
        if existing_membership:
            raise HTTPException(
                status_code=409,
                detail=(
                    "User already belongs to a household. Leave it before "
                    "creating another."
                ),
            )

        try:
            household_id = conn.execute(
                insert(db.households)
                .values(
                    household_name=payload.household_name,
                    created_by=payload.user_id,
                )
                .returning(db.households.c.household_id)
            ).scalar_one()

            conn.execute(
                insert(db.household_members).values(
                    household_id=household_id,
                    user_id=payload.user_id,
                )
            )
        except SQLAlchemyError as exc:
            # `engine.begin()` rolls back automatically when the context
            # exits with an exception. Logging + re-raising makes this
            # behavior explicit and observable in production logs.
            logger.error(
                "create_household failed for user_id=%s name=%r: %s",
                payload.user_id,
                payload.household_name,
                exc,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to create household; transaction rolled back.",
            ) from exc

    return CreateHouseholdResponse(household_id=household_id)


class JoinHouseholdRequest(BaseModel):
    household_id: int
    user_id: int


@router.post("/join", response_model=SuccessResponse)
def join_household(payload: JoinHouseholdRequest) -> SuccessResponse:
    """Add a user to an existing household.

    Idempotent: if the user is already a member, a 200 is returned with a
    `success=true` payload and a `message` explaining that nothing changed,
    instead of silently swallowing an IntegrityError.
    """
    with db.engine.begin() as conn:
        assert_exists(conn, db.users.c.user_id, payload.user_id, label="User")
        assert_exists(
            conn,
            db.households.c.household_id,
            payload.household_id,
            label="Household",
        )

        already_member = conn.execute(
            select(db.household_members.c.user_id).where(
                db.household_members.c.household_id == payload.household_id,
                db.household_members.c.user_id == payload.user_id,
            )
        ).first()
        if already_member:
            return SuccessResponse(
                success=True,
                message="User is already a member of this household.",
            )

        # One household per user keeps pantry-merge semantics predictable
        # (peer review Aaron Lee schema #5).
        other_membership = conn.execute(
            select(db.household_members.c.household_id).where(
                db.household_members.c.user_id == payload.user_id
            )
        ).first()
        if other_membership:
            raise HTTPException(
                status_code=409,
                detail=(
                    "User already belongs to a household. Leave it before "
                    "joining another."
                ),
            )

        try:
            conn.execute(
                insert(db.household_members).values(
                    household_id=payload.household_id,
                    user_id=payload.user_id,
                )
            )
        except IntegrityError as exc:
            logger.warning(
                "Race-condition duplicate household_members insert for "
                "household_id=%s user_id=%s: %s",
                payload.household_id,
                payload.user_id,
                exc,
            )
            return SuccessResponse(
                success=True,
                message="User is already a member of this household.",
            )

    return SuccessResponse(success=True, message="User joined household.")


@router.delete(
    "/{household_id}/members/{user_id}", response_model=SuccessResponse
)
def leave_household(household_id: int, user_id: int) -> SuccessResponse:
    """Remove a user from a household."""
    with db.engine.begin() as conn:
        assert_exists(conn, db.users.c.user_id, user_id, label="User")
        assert_exists(
            conn,
            db.households.c.household_id,
            household_id,
            label="Household",
        )

        result = conn.execute(
            delete(db.household_members).where(
                db.household_members.c.household_id == household_id,
                db.household_members.c.user_id == user_id,
            )
        )
        if result.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="That user is not a member of this household.",
            )

    return SuccessResponse(success=True, message="User left household.")


class ShoppingListIngredient(BaseModel):
    ingredient_id: int
    name: str
    quantity_needed: Decimal | None = None
    unit: str | None = None


class ShoppingListResponse(BaseModel):
    household_id: int
    household_name: str
    recipe_id: int
    recipe_name: str
    have: List[ShoppingListIngredient]
    missing: List[ShoppingListIngredient]
    coverage_pct: int


@router.get(
    "/{household_id}/shopping-list",
    response_model=ShoppingListResponse,
    summary="Complex endpoint: recipe vs combined household pantry",
)
def household_shopping_list(
    household_id: int,
    recipe_id: int = Query(..., description="Recipe the household wants to make."),
    user_id: int = Query(
        ...,
        description=(
            "Member requesting the list. Their own pantry items are always "
            "included; other members' items count only when shared."
        ),
    ),
) -> ShoppingListResponse:
    """Diff a recipe's ingredient list against the household's combined pantry.

    Joins households, household_members, pantry, recipe_ingredients, ingredients,
    and recipes. Runs under REPEATABLE READ so the pantry snapshot and recipe
    requirements stay consistent for the duration of the transaction.
    """
    with transactional(
        db.engine, isolation_level="REPEATABLE READ"
    ) as conn:
        assert_exists(
            conn,
            db.households.c.household_id,
            household_id,
            label="Household",
        )
        assert_exists(conn, db.users.c.user_id, user_id, label="User")
        assert_exists(conn, db.recipes.c.recipe_id, recipe_id, label="Recipe")

        is_member = conn.execute(
            select(db.household_members.c.user_id).where(
                db.household_members.c.household_id == household_id,
                db.household_members.c.user_id == user_id,
            )
        ).first()
        if not is_member:
            raise HTTPException(
                status_code=403,
                detail="user_id is not a member of this household.",
            )

        household_name = conn.execute(
            select(db.households.c.household_name).where(
                db.households.c.household_id == household_id
            )
        ).scalar_one()
        recipe_name = conn.execute(
            select(db.recipes.c.recipe_name).where(
                db.recipes.c.recipe_id == recipe_id
            )
        ).scalar_one()

        # Pantry rows visible to this household: every member's shared items
        # plus the requesting user's private items.
        household_members = select(db.household_members.c.user_id).where(
            db.household_members.c.household_id == household_id
        )
        pantry_visible = and_(
            db.pantry.c.user_id.in_(household_members),
            (
                (db.pantry.c.user_id == user_id)
                | db.pantry.c.is_shared_with_household.is_(True)
            ),
        )

        have_ids = {
            row.ingredient_id
            for row in conn.execute(
                select(db.pantry.c.ingredient_id).where(pantry_visible)
            )
        }

        required = conn.execute(
            select(
                db.ingredients.c.ingredient_id,
                db.ingredients.c.name,
                db.recipe_ingredients.c.quantity,
                db.recipe_ingredients.c.unit,
            )
            .select_from(
                db.recipe_ingredients.join(
                    db.ingredients,
                    db.recipe_ingredients.c.ingredient_id
                    == db.ingredients.c.ingredient_id,
                )
            )
            .where(db.recipe_ingredients.c.recipe_id == recipe_id)
            .order_by(db.ingredients.c.name)
        ).all()

        if not required:
            raise HTTPException(
                status_code=404,
                detail="Recipe has no ingredients on file.",
            )

        have: list[ShoppingListIngredient] = []
        missing: list[ShoppingListIngredient] = []
        for row in required:
            item = ShoppingListIngredient(
                ingredient_id=row.ingredient_id,
                name=row.name,
                quantity_needed=row.quantity,
                unit=row.unit,
            )
            if row.ingredient_id in have_ids:
                have.append(item)
            else:
                missing.append(item)

        coverage_pct = round(100 * len(have) / len(required))

        return ShoppingListResponse(
            household_id=household_id,
            household_name=household_name,
            recipe_id=recipe_id,
            recipe_name=recipe_name,
            have=have,
            missing=missing,
            coverage_pct=coverage_pct,
        )
