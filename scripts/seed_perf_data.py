#!/usr/bin/env python3
"""Bulk-load ~1M realistic rows into a local Postgres DB for V5 perf testing.

Run after `alembic upgrade head` on a dedicated local database (NOT Supabase).

    POSTGRES_URI=postgresql+psycopg2://localhost/foodgraph_perf python scripts/seed_perf_data.py

Writes scripts/benchmark_config.json with IDs to use in benchmark_endpoints.py.
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

# Project root on sys.path so `import src` works when run as a script.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from src import database as db  # noqa: E402

# Final row-count targets (includes rows already inserted by Alembic seeds).
TARGETS = {
    "users": 100_000,
    "ingredients": 5_000,
    "recipes": 80_000,
    "recipe_ingredients": 650_000,
    "households": 25_000,
    "household_members": 100_000,
    "pantry": 140_000,
    "user_allergies": 25_000,
}

BATCH = 5_000
RNG = random.Random(365)


def log(msg: str) -> None:
    print(msg, flush=True)


def count_table(conn, table: str) -> int:
    return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()


def load_ids(conn, table: str, column: str) -> list[int]:
    """Return every PK value currently in `table` (handles Alembic ID gaps)."""
    rows = conn.execute(text(f"SELECT {column} FROM {table} ORDER BY {column}"))
    return [row[0] for row in rows]


def bump_sequence(conn, table: str, column: str) -> None:
    conn.execute(
        text(
            f"""
            SELECT setval(
                pg_get_serial_sequence('{table}', '{column}'),
                COALESCE((SELECT MAX({column}) FROM {table}), 1)
            )
            """
        )
    )


def insert_users(conn, target: int) -> None:
    existing = count_table(conn, "users")
    if existing >= target:
        log(f"users: already {existing:,} rows, skipping")
        return
    log(f"users: inserting {target - existing:,} rows...")
    batch: list[dict] = []
    for user_id in range(existing + 1, target + 1):
        batch.append(
            {
                "user_id": user_id,
                "first_name": f"user{user_id}",
                "last_name": "perf",
                "email": f"user{user_id}@perf.test",
            }
        )
        if len(batch) >= BATCH:
            conn.execute(
                text(
                    """
                    INSERT INTO users (user_id, first_name, last_name, email)
                    VALUES (:user_id, :first_name, :last_name, :email)
                    ON CONFLICT DO NOTHING
                    """
                ),
                batch,
            )
            batch.clear()
    if batch:
        conn.execute(
            text(
                """
                INSERT INTO users (user_id, first_name, last_name, email)
                VALUES (:user_id, :first_name, :last_name, :email)
                ON CONFLICT DO NOTHING
                """
            ),
            batch,
        )
    bump_sequence(conn, "users", "user_id")


def insert_ingredients(conn, target: int) -> None:
    existing = count_table(conn, "ingredients")
    if existing >= target:
        log(f"ingredients: already {existing:,} rows, skipping")
        return
    need = target - existing
    log(f"ingredients: inserting {need:,} rows...")
    next_id = conn.execute(
        text("SELECT COALESCE(MAX(ingredient_id), 0) FROM ingredients")
    ).scalar_one() + 1
    batch: list[dict] = []
    inserted = 0
    while inserted < need:
        batch.append(
            {
                "ingredient_id": next_id,
                "name": f"perf_ingredient_{next_id:06d}",
            }
        )
        next_id += 1
        inserted += 1
        if len(batch) >= BATCH:
            conn.execute(
                text(
                    """
                    INSERT INTO ingredients (ingredient_id, name)
                    VALUES (:ingredient_id, :name)
                    ON CONFLICT DO NOTHING
                    """
                ),
                batch,
            )
            batch.clear()
    if batch:
        conn.execute(
            text(
                """
                INSERT INTO ingredients (ingredient_id, name)
                VALUES (:ingredient_id, :name)
                ON CONFLICT DO NOTHING
                """
            ),
            batch,
        )
    bump_sequence(conn, "ingredients", "ingredient_id")


def insert_recipes(conn, target: int) -> None:
    existing = count_table(conn, "recipes")
    if existing >= target:
        log(f"recipes: already {existing:,} rows, skipping")
        return
    log(f"recipes: inserting {target - existing:,} rows...")
    batch: list[dict] = []
    for recipe_id in range(existing + 1, target + 1):
        batch.append(
            {
                "recipe_id": recipe_id,
                "recipe_name": f"perf recipe {recipe_id}",
                "recipe_steps": f"1) prep  2) cook  3) serve ({recipe_id})",
                "created_by": RNG.randint(1, TARGETS["users"]),
            }
        )
        if len(batch) >= BATCH:
            conn.execute(
                text(
                    """
                    INSERT INTO recipes (recipe_id, recipe_name, recipe_steps, created_by)
                    VALUES (:recipe_id, :recipe_name, :recipe_steps, :created_by)
                    ON CONFLICT DO NOTHING
                    """
                ),
                batch,
            )
            batch.clear()
    if batch:
        conn.execute(
            text(
                """
                INSERT INTO recipes (recipe_id, recipe_name, recipe_steps, created_by)
                VALUES (:recipe_id, :recipe_name, :recipe_steps, :created_by)
                ON CONFLICT DO NOTHING
                """
            ),
            batch,
        )
    bump_sequence(conn, "recipes", "recipe_id")


def insert_recipe_ingredients(
    conn, target: int, recipe_ids: list[int], ingredient_ids: list[int]
) -> None:
    existing = count_table(conn, "recipe_ingredients")
    if existing >= target:
        log(f"recipe_ingredients: already {existing:,} rows, skipping")
        return
    need = target - existing
    log(f"recipe_ingredients: inserting ~{need:,} rows...")
    # ~8 ingredients per recipe is realistic and avoids a slow random loop.
    per_recipe = max(8, (need // len(recipe_ids)) + 1)
    batch: list[dict] = []
    inserted = existing
    for i, recipe_id in enumerate(recipe_ids, start=1):
        if inserted >= target:
            break
        picks = RNG.sample(
            ingredient_ids, k=min(per_recipe, len(ingredient_ids))
        )
        for ingredient_id in picks:
            if inserted >= target:
                break
            batch.append(
                {
                    "recipe_id": recipe_id,
                    "ingredient_id": ingredient_id,
                    "quantity": round(RNG.uniform(0.5, 4.0), 2),
                    "unit": RNG.choice(["cup", "g", "oz", "whole"]),
                }
            )
            inserted += 1
            if len(batch) >= BATCH:
                conn.execute(
                    text(
                        """
                        INSERT INTO recipe_ingredients
                            (recipe_id, ingredient_id, quantity, unit)
                        VALUES (:recipe_id, :ingredient_id, :quantity, :unit)
                        ON CONFLICT DO NOTHING
                        """
                    ),
                    batch,
                )
                batch.clear()
        if i % 10_000 == 0:
            log(f"  recipe_ingredients: processed {i:,}/{len(recipe_ids):,} recipes")
    if batch:
        conn.execute(
            text(
                """
                INSERT INTO recipe_ingredients
                    (recipe_id, ingredient_id, quantity, unit)
                VALUES (:recipe_id, :ingredient_id, :quantity, :unit)
                ON CONFLICT DO NOTHING
                """
            ),
            batch,
        )
    log(f"  recipe_ingredients: done ({count_table(conn, 'recipe_ingredients'):,} rows)")


def insert_households(conn, target: int) -> None:
    existing = count_table(conn, "households")
    if existing >= target:
        log(f"households: already {existing:,} rows, skipping")
        return
    log(f"households: inserting {target - existing:,} rows...")
    batch: list[dict] = []
    for household_id in range(existing + 1, target + 1):
        batch.append(
            {
                "household_id": household_id,
                "household_name": f"perf household {household_id}",
                "created_by": RNG.randint(1, TARGETS["users"]),
            }
        )
        if len(batch) >= BATCH:
            conn.execute(
                text(
                    """
                    INSERT INTO households (household_id, household_name, created_by)
                    VALUES (:household_id, :household_name, :created_by)
                    ON CONFLICT DO NOTHING
                    """
                ),
                batch,
            )
            batch.clear()
    if batch:
        conn.execute(
            text(
                """
                INSERT INTO households (household_id, household_name, created_by)
                VALUES (:household_id, :household_name, :created_by)
                ON CONFLICT DO NOTHING
                """
            ),
            batch,
        )
    bump_sequence(conn, "households", "household_id")


def insert_household_members(conn, target: int, household_count: int) -> None:
    existing = count_table(conn, "household_members")
    if existing >= target:
        log(f"household_members: already {existing:,} rows, skipping")
        return
    log(f"household_members: inserting {target - existing:,} rows...")
    batch: list[dict] = []
    for user_id in range(1, target + 1):
        household_id = ((user_id - 1) % household_count) + 1
        batch.append({"household_id": household_id, "user_id": user_id})
        if len(batch) >= BATCH:
            conn.execute(
                text(
                    """
                    INSERT INTO household_members (household_id, user_id)
                    VALUES (:household_id, :user_id)
                    ON CONFLICT DO NOTHING
                    """
                ),
                batch,
            )
            batch.clear()
    if batch:
        conn.execute(
            text(
                """
                INSERT INTO household_members (household_id, user_id)
                VALUES (:household_id, :user_id)
                ON CONFLICT DO NOTHING
                """
            ),
            batch,
        )


def insert_pantry(
    conn, target: int, ingredient_ids: list[int], user_max: int
) -> None:
    existing = count_table(conn, "pantry")
    if existing >= target:
        log(f"pantry: already {existing:,} rows, skipping")
        return
    log(f"pantry: inserting {target - existing:,} rows...")
    batch: list[dict] = []
    seen: set[tuple[int, int]] = set()
    today = date.today()
    inserted = existing
    while inserted < target:
        user_id = RNG.randint(1, user_max)
        ingredient_id = RNG.choice(ingredient_ids)
        key = (user_id, ingredient_id)
        if key in seen:
            continue
        seen.add(key)
        batch.append(
            {
                "user_id": user_id,
                "ingredient_id": ingredient_id,
                "is_shared_with_household": RNG.random() < 0.7,
                "quantity": round(RNG.uniform(0.5, 5.0), 2),
                "unit": RNG.choice(["cup", "g", "kg", "whole"]),
                "purchase_date": today - timedelta(days=RNG.randint(0, 30)),
                "expiry_date": today + timedelta(days=RNG.randint(1, 60)),
            }
        )
        inserted += 1
        if len(batch) >= BATCH:
            conn.execute(
                text(
                    """
                    INSERT INTO pantry
                        (user_id, ingredient_id, is_shared_with_household,
                         quantity, unit, purchase_date, expiry_date)
                    VALUES
                        (:user_id, :ingredient_id, :is_shared_with_household,
                         :quantity, :unit, :purchase_date, :expiry_date)
                    ON CONFLICT DO NOTHING
                    """
                ),
                batch,
            )
            batch.clear()
            if inserted % 50_000 < BATCH:
                log(f"  pantry: ~{inserted:,} / {target:,}")
    if batch:
        conn.execute(
            text(
                """
                INSERT INTO pantry
                    (user_id, ingredient_id, is_shared_with_household,
                     quantity, unit, purchase_date, expiry_date)
                VALUES
                    (:user_id, :ingredient_id, :is_shared_with_household,
                     :quantity, :unit, :purchase_date, :expiry_date)
                ON CONFLICT DO NOTHING
                """
            ),
            batch,
        )


def insert_allergies(
    conn, target: int, ingredient_ids: list[int], user_max: int
) -> None:
    existing = count_table(conn, "user_allergies")
    if existing >= target:
        log(f"user_allergies: already {existing:,} rows, skipping")
        return
    log(f"user_allergies: inserting {target - existing:,} rows...")
    batch: list[dict] = []
    inserted = existing
    for user_id in range(1, user_max + 1):
        if inserted >= target:
            break
        if RNG.random() > 0.25:
            continue
        n = RNG.randint(1, 3)
        picks = RNG.sample(ingredient_ids, k=min(n, len(ingredient_ids)))
        for ingredient_id in picks:
            if inserted >= target:
                break
            batch.append({"user_id": user_id, "ingredient_id": ingredient_id})
            inserted += 1
            if len(batch) >= BATCH:
                conn.execute(
                    text(
                        """
                        INSERT INTO user_allergies (user_id, ingredient_id)
                        VALUES (:user_id, :ingredient_id)
                        ON CONFLICT DO NOTHING
                        """
                    ),
                    batch,
                )
                batch.clear()
    if batch:
        conn.execute(
            text(
                """
                INSERT INTO user_allergies (user_id, ingredient_id)
                VALUES (:user_id, :ingredient_id)
                ON CONFLICT DO NOTHING
                """
            ),
            batch,
        )


def write_benchmark_config(conn) -> None:
    user_id = 50_000
    household_id = ((user_id - 1) % TARGETS["households"]) + 1
    recipe_id = 40_000
    pantry_rows = conn.execute(
        text(
            """
            SELECT ingredient_id FROM pantry
            WHERE user_id = :user_id
            LIMIT 5
            """
        ),
        {"user_id": user_id},
    ).all()
    ingredient_ids = [row.ingredient_id for row in pantry_rows] or [1, 2, 3]
    config = {
        "user_id": user_id,
        "household_id": household_id,
        "recipe_id": recipe_id,
        "ingredient_ids": ingredient_ids,
        "allergen_ingredient_id": 42,
    }
    path = ROOT / "scripts" / "benchmark_config.json"
    path.write_text(json.dumps(config, indent=2) + "\n")
    log(f"Wrote benchmark IDs to {path}")


def print_counts(conn) -> None:
    log("\nFinal row counts:")
    total = 0
    for table in [
        "users",
        "ingredients",
        "recipes",
        "recipe_ingredients",
        "households",
        "household_members",
        "pantry",
        "user_allergies",
    ]:
        n = count_table(conn, table)
        total += n
        log(f"  {table:20} {n:>10,}")
    log(f"  {'TOTAL':20} {total:>10,}")


def main() -> None:
    uri = os.environ.get("POSTGRES_URI", "")
    if not uri or "supabase" in uri.lower():
        sys.exit(
            "Refusing to run against Supabase. Point POSTGRES_URI at a local DB, "
            "e.g. postgresql+psycopg2://localhost/foodgraph_perf"
        )

    t0 = time.perf_counter()
    log(f"Seeding perf data using {uri.split('@')[-1]}")

    def run_phase(name: str, fn) -> None:
        log(f"\n--- {name} ---")
        phase_t0 = time.perf_counter()
        with db.engine.begin() as conn:
            fn(conn)
        log(f"--- {name} done in {time.perf_counter() - phase_t0:.1f}s ---")

    run_phase("users", lambda c: insert_users(c, TARGETS["users"]))
    run_phase("ingredients", lambda c: insert_ingredients(c, TARGETS["ingredients"]))
    run_phase("recipes", lambda c: insert_recipes(c, TARGETS["recipes"]))
    run_phase("households", lambda c: insert_households(c, TARGETS["households"]))
    run_phase(
        "household_members",
        lambda c: insert_household_members(
            c, TARGETS["household_members"], TARGETS["households"]
        ),
    )

    with db.engine.begin() as conn:
        recipe_ids = load_ids(conn, "recipes", "recipe_id")
        ingredient_ids = load_ids(conn, "ingredients", "ingredient_id")
    log(
        f"Loaded {len(recipe_ids):,} recipe IDs and "
        f"{len(ingredient_ids):,} ingredient IDs"
    )

    run_phase(
        "recipe_ingredients",
        lambda c: insert_recipe_ingredients(
            c, TARGETS["recipe_ingredients"], recipe_ids, ingredient_ids
        ),
    )
    run_phase(
        "pantry",
        lambda c: insert_pantry(c, TARGETS["pantry"], ingredient_ids, TARGETS["users"]),
    )
    run_phase(
        "user_allergies",
        lambda c: insert_allergies(
            c, TARGETS["user_allergies"], ingredient_ids, TARGETS["users"]
        ),
    )

    with db.engine.begin() as conn:
        conn.execute(text("ANALYZE"))
        write_benchmark_config(conn)
        print_counts(conn)

    log(f"\nDone in {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
