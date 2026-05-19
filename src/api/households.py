"""Household creation and membership endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src import database as db
from src.api.helpers import assert_exists, logger
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
