-- Seed recipes 1–6 + recipe_ingredients (matches alembic 0002 + 0003).
-- Run in Supabase SQL Editor after ingredients 1–10 and 42 exist.
-- Safe to re-run: ON CONFLICT DO NOTHING.

BEGIN;

INSERT INTO recipes (recipe_id, recipe_name, recipe_steps)
VALUES
  (
    1,
    'Chicken and Broccoli Stir-Fry',
    '1) Cook rice. 2) Cook chicken in a hot pan until done. 3) Add broccoli, stir-fry until tender. 4) Serve over rice.'
  ),
  (
    2,
    'Peanut Chicken',
    '1) Cook chicken. 2) Toss with crushed peanuts. 3) Serve.'
  ),
  (
    3,
    'Steamed Broccoli',
    '1) Steam broccoli 4-5 minutes. 2) Season and serve.'
  ),
  (
    4,
    'Tomato Basil Spaghetti-Style Rice',
    '1) Cook rice. 2) Saute garlic in olive oil with chopped tomato. 3) Stir in fresh basil. 4) Toss with rice.'
  ),
  (
    5,
    'Spinach Frittata',
    '1) Whisk eggs. 2) Wilt spinach in olive oil with garlic. 3) Pour eggs over, cook until set.'
  ),
  (
    6,
    'Eggs and Spinach Scramble',
    '1) Beat eggs in a bowl. 2) Wilt spinach in a hot pan. 3) Pour in eggs and scramble until set.'
  )
ON CONFLICT (recipe_id) DO NOTHING;

INSERT INTO recipe_ingredients (recipe_id, ingredient_id)
VALUES
  (1, 1), (1, 2), (1, 3),
  (2, 1), (2, 42),
  (3, 3),
  (4, 2), (4, 5), (4, 6), (4, 7), (4, 8),
  (5, 5), (5, 6), (5, 9), (5, 10),
  (6, 9), (6, 10)
ON CONFLICT (recipe_id, ingredient_id) DO NOTHING;

-- Keep auto-increment past hand-picked IDs
SELECT setval(
  pg_get_serial_sequence('recipes', 'recipe_id'),
  GREATEST(6, COALESCE((SELECT MAX(recipe_id) FROM recipes), 0))
);

COMMIT;

-- Verify
SELECT recipe_id, recipe_name FROM recipes ORDER BY recipe_id;
SELECT recipe_id, ingredient_id FROM recipe_ingredients ORDER BY recipe_id, ingredient_id;
