"""Household creation and membership endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from src import database as db

router = APIRouter(prefix="/households", tags=["households"])


class CreateHouseholdRequest(BaseModel):
    user_id: int
    household_name: str = Field(..., min_length=1, max_length=200)


class CreateHouseholdResponse(BaseModel):
    household_id: int


@router.post("/create", response_model=CreateHouseholdResponse, status_code=201)
def create_household(payload: CreateHouseholdRequest) -> CreateHouseholdResponse:
    """Create a new household and add the requesting user as the first member."""
    with db.engine.begin() as conn:
        user_exists = conn.execute(
            select(db.users.c.user_id).where(db.users.c.user_id == payload.user_id)
        ).first()
        if not user_exists:
            raise HTTPException(status_code=404, detail="User not found.")

        household_id = conn.execute(
            insert(db.households)
            .values(household_name=payload.household_name)
            .returning(db.households.c.household_id)
        ).scalar_one()

        conn.execute(
            insert(db.household_members).values(
                household_id=household_id,
                user_id=payload.user_id,
            )
        )

    return CreateHouseholdResponse(household_id=household_id)


class JoinHouseholdRequest(BaseModel):
    household_id: int
    user_id: int


class SuccessResponse(BaseModel):
    success: bool


@router.post("/join", response_model=SuccessResponse)
def join_household(payload: JoinHouseholdRequest) -> SuccessResponse:
    """Add a user to an existing household. Idempotent."""
    with db.engine.begin() as conn:
        user_exists = conn.execute(
            select(db.users.c.user_id).where(db.users.c.user_id == payload.user_id)
        ).first()
        if not user_exists:
            raise HTTPException(status_code=404, detail="User not found.")

        household_exists = conn.execute(
            select(db.households.c.household_id).where(
                db.households.c.household_id == payload.household_id
            )
        ).first()
        if not household_exists:
            raise HTTPException(status_code=404, detail="Household not found.")

        try:
            conn.execute(
                insert(db.household_members).values(
                    household_id=payload.household_id,
                    user_id=payload.user_id,
                )
            )
        except IntegrityError:
            # Already a member — treat as success.
            pass

    return SuccessResponse(success=True)
