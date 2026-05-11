"""User-related endpoints (sign up, allergies)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from src import database as db

router = APIRouter(prefix="/users", tags=["users"])


class CreateUserRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr


class CreateUserResponse(BaseModel):
    user_id: int


@router.post("/create", response_model=CreateUserResponse, status_code=201)
def create_user(payload: CreateUserRequest) -> CreateUserResponse:
    stmt = (
        insert(db.users)
        .values(first_name=payload.first_name, email=payload.email)
        .returning(db.users.c.user_id)
    )
    with db.engine.begin() as conn:
        try:
            result = conn.execute(stmt)
        except IntegrityError as exc:
            raise HTTPException(
                status_code=409, detail="A user with that email already exists."
            ) from exc
        user_id = result.scalar_one()
    return CreateUserResponse(user_id=user_id)


class AddAllergyRequest(BaseModel):
    user_id: int
    ingredient_id: int


class SuccessResponse(BaseModel):
    success: bool


@router.post("/add_allergy", response_model=SuccessResponse)
def add_allergy(payload: AddAllergyRequest) -> SuccessResponse:
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

        try:
            conn.execute(
                insert(db.user_allergies).values(
                    user_id=payload.user_id,
                    ingredient_id=payload.ingredient_id,
                )
            )
        except IntegrityError:
            # Allergy already recorded — idempotent success.
            pass
    return SuccessResponse(success=True)


class GetAllergiesRequest(BaseModel):
    user_id: int


class Allergy(BaseModel):
    ingredient_name: str


@router.post("/get_allergies", response_model=list[Allergy])
def get_allergies(payload: GetAllergiesRequest) -> list[Allergy]:
    """Return the ingredient names a user has flagged as allergies.

    Spec uses POST despite this being a read — we match the spec.
    """
    with db.engine.begin() as conn:
        user_exists = conn.execute(
            select(db.users.c.user_id).where(db.users.c.user_id == payload.user_id)
        ).first()
        if not user_exists:
            raise HTTPException(status_code=404, detail="User not found.")

        stmt = (
            select(db.ingredients.c.name)
            .select_from(
                db.user_allergies.join(
                    db.ingredients,
                    db.user_allergies.c.ingredient_id
                    == db.ingredients.c.ingredient_id,
                )
            )
            .where(db.user_allergies.c.user_id == payload.user_id)
            .order_by(db.ingredients.c.name)
        )
        return [Allergy(ingredient_name=row.name) for row in conn.execute(stmt)]
