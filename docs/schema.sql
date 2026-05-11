-- Food Graph API — full schema + seed catalog.
--
-- This file is an alternative to running `alembic upgrade head`. The
-- canonical source of schema truth is `alembic/versions/`; this script
-- is kept in sync with those migrations as of revision
-- 0003_households_and_v2_seeds.
--
-- Apply with:
--   psql "$POSTGRES_URI" -f schema.sql
--
-- Works on PostgreSQL 14+ (incl. Supabase). Idempotent: drops + recreates
-- everything every run, so it is safe to use during development.

BEGIN;

DROP TABLE IF EXISTS household_members CASCADE;
DROP TABLE IF EXISTS households        CASCADE;
DROP TABLE IF EXISTS user_allergies    CASCADE;
DROP TABLE IF EXISTS pantry            CASCADE;
DROP TABLE IF EXISTS recipe_ingredients CASCADE;
DROP TABLE IF EXISTS recipes           CASCADE;
DROP TABLE IF EXISTS ingredients       CASCADE;
DROP TABLE IF EXISTS users             CASCADE;

------------------------------------------------------------------------
-- Core entities
------------------------------------------------------------------------

CREATE TABLE users (
    user_id    SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    email      VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE ingredients (
    ingredient_id SERIAL PRIMARY KEY,
    name          VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE recipes (
    recipe_id    SERIAL PRIMARY KEY,
    recipe_name  VARCHAR(200) NOT NULL,
    recipe_steps TEXT         NOT NULL
);

------------------------------------------------------------------------
-- Relationships
------------------------------------------------------------------------

-- Which ingredients each recipe needs.
CREATE TABLE recipe_ingredients (
    recipe_id     INTEGER NOT NULL REFERENCES recipes(recipe_id)        ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(ingredient_id) ON DELETE RESTRICT,
    PRIMARY KEY (recipe_id, ingredient_id)
);

-- One row per ingredient owned by one user. Items default to shared
-- with the household; users can opt-out per item to keep a private stash.
CREATE TABLE pantry (
    pantry_id                SERIAL PRIMARY KEY,
    user_id                  INTEGER NOT NULL REFERENCES users(user_id)               ON DELETE CASCADE,
    ingredient_id            INTEGER NOT NULL REFERENCES ingredients(ingredient_id)   ON DELETE RESTRICT,
    is_shared_with_household BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_pantry_user_ingredient UNIQUE (user_id, ingredient_id)
);

CREATE TABLE user_allergies (
    user_id       INTEGER NOT NULL REFERENCES users(user_id)             ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(ingredient_id) ON DELETE RESTRICT,
    PRIMARY KEY (user_id, ingredient_id)
);

------------------------------------------------------------------------
-- Households (V2)
------------------------------------------------------------------------

CREATE TABLE households (
    household_id   SERIAL PRIMARY KEY,
    household_name VARCHAR(200) NOT NULL
);

CREATE TABLE household_members (
    household_id INTEGER NOT NULL REFERENCES households(household_id) ON DELETE CASCADE,
    user_id      INTEGER NOT NULL REFERENCES users(user_id)           ON DELETE CASCADE,
    PRIMARY KEY (household_id, user_id)
);

------------------------------------------------------------------------
-- Seed catalog
--
-- Ingredient IDs are pinned so the example flows in ExampleFlows.md run
-- verbatim (most notably peanuts = 42).
------------------------------------------------------------------------

INSERT INTO ingredients (ingredient_id, name) VALUES
    (1,  'chicken'),
    (2,  'rice'),
    (3,  'broccoli'),
    (4,  'soy sauce'),
    (5,  'garlic'),
    (6,  'olive oil'),
    (7,  'tomato'),
    (8,  'basil'),
    (9,  'egg'),
    (10, 'spinach'),
    (42, 'peanuts');

INSERT INTO recipes (recipe_id, recipe_name, recipe_steps) VALUES
    (1, 'Chicken and Broccoli Stir-Fry',
        '1) Cook rice. 2) Cook chicken in a hot pan until done. 3) Add broccoli, stir-fry until tender. 4) Serve over rice.'),
    (2, 'Peanut Chicken',
        '1) Cook chicken. 2) Toss with crushed peanuts. 3) Serve.'),
    (3, 'Steamed Broccoli',
        '1) Steam broccoli 4-5 minutes. 2) Season and serve.'),
    (4, 'Tomato Basil Spaghetti-Style Rice',
        '1) Cook rice. 2) Saute garlic in olive oil with chopped tomato. 3) Stir in fresh basil. 4) Toss with rice.'),
    (5, 'Spinach Frittata',
        '1) Whisk eggs. 2) Wilt spinach in olive oil with garlic. 3) Pour eggs over, cook until set.'),
    (6, 'Eggs and Spinach Scramble',
        '1) Beat eggs in a bowl. 2) Wilt spinach in a hot pan. 3) Pour in eggs and scramble until set.');

INSERT INTO recipe_ingredients (recipe_id, ingredient_id) VALUES
    (1, 1), (1, 2), (1, 3),
    (2, 1), (2, 42),
    (3, 3),
    (4, 2), (4, 5), (4, 6), (4, 7), (4, 8),
    (5, 5), (5, 6), (5, 9), (5, 10),
    (6, 9), (6, 10);

-- Bump the SERIAL sequences past the pinned IDs so future inserts via
-- the API land on safe new values.
SELECT setval(pg_get_serial_sequence('ingredients', 'ingredient_id'),
              (SELECT MAX(ingredient_id) FROM ingredients));
SELECT setval(pg_get_serial_sequence('recipes', 'recipe_id'),
              (SELECT MAX(recipe_id) FROM recipes));

COMMIT;
