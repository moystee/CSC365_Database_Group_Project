-- EXPLAIN for GET /users/{user_id}/top-recipes (pass 2: aggregate recipe_ingredients first)
-- user_id=50000, limit=5; pantry IDs resolved in app layer (3 items for this user)

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
WITH coverage AS (
    SELECT
        recipe_id,
        COUNT(ingredient_id) AS total_count,
        COUNT(ingredient_id) FILTER (
            WHERE ingredient_id IN (4872, 1, 636)
        ) AS have_count
    FROM recipe_ingredients
    WHERE recipe_id NOT IN (
        SELECT DISTINCT recipe_id
        FROM recipe_ingredients
        WHERE ingredient_id IN (
            SELECT ingredient_id FROM user_allergies WHERE user_id = 50000
        )
    )
    GROUP BY recipe_id
    HAVING COUNT(ingredient_id) > 0
)
SELECT
    r.recipe_id,
    r.recipe_name,
    r.recipe_steps,
    c.total_count,
    c.have_count
FROM coverage c
JOIN recipes r ON r.recipe_id = c.recipe_id
ORDER BY c.have_count DESC, r.recipe_name
LIMIT 5;
