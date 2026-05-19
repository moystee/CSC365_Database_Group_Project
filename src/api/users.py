"""User-related endpoints (sign up, allergies, profile)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import delete, insert, select
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
