"""V5 performance indexes for top-recipes and pantry queries.

Revision ID: 0005_perf_indexes
Revises: 0004_v3_schema_extras
Create Date: 2026-05-31 16:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0005_perf_indexes"
down_revision: Union[str, None] = "0004_v3_schema_extras"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # household_members: top-recipes scans by user_id (was Seq Scan 100k rows).
    op.create_index(
        "idx_household_members_user_id",
        "household_members",
        ["user_id"],
    )
    # recipe_ingredients: allergen filter uses ingredient_id; join uses recipe_id.
    op.create_index(
        "idx_recipe_ingredients_ingredient_id",
        "recipe_ingredients",
        ["ingredient_id"],
    )
    # pantry: user's own items + shared housemate lookups by user_id.
    op.create_index(
        "idx_pantry_user_id",
        "pantry",
        ["user_id"],
    )
    op.create_index(
        "idx_pantry_user_shared",
        "pantry",
        ["user_id"],
        postgresql_where="is_shared_with_household = true",
    )


def downgrade() -> None:
    op.drop_index("idx_pantry_user_shared", table_name="pantry")
    op.drop_index("idx_pantry_user_id", table_name="pantry")
    op.drop_index(
        "idx_recipe_ingredients_ingredient_id", table_name="recipe_ingredients"
    )
    op.drop_index("idx_household_members_user_id", table_name="household_members")
