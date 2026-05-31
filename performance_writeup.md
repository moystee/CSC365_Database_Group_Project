# Performance Writeup (V5)

Local database: `foodgraph_perf` (~1.1M rows)  
Benchmark server: `uvicorn src.server:app` on `http://127.0.0.1:8000`  
Test IDs: `scripts/benchmark_config.json` (user `50000`, household `25000`, recipe `40000`)

---

## Fake Data Modeling

**Seed script:** [scripts/seed_perf_data.py](scripts/seed_perf_data.py)

### Final row counts

| Table | Rows |
|-------|------|
| users | 100,000 |
| ingredients | 5,000 |
| recipes | 80,000 |
| recipe_ingredients | 650,000 |
| households | 25,000 |
| household_members | 100,000 |
| pantry | 140,000 |
| user_allergies | 25,000 |
| **Total** | **1,125,000** |

### Why this distribution is realistic

Food Graph is a recipe/pantry graph. At production scale:

- **Users** grow steadily (100k active accounts).
- **Recipes** and **recipe_ingredients** dominate storage — every recipe links to ~8 ingredients on average, so the junction table is the largest (650k rows). This matches user-generated catalog growth.
- **Pantry** rows (~1.4 per user on average) reflect that many users are inactive or have sparse inventories; a power-law style load is more realistic than every user having hundreds of items.
- **Households** (25k) and **members** (100k) model ~4 members per household on average, with one membership per user for predictable pantry-merge semantics.

Alembic seed data (ingredients 1–10, 42, recipes 1–6) is preserved; perf rows are appended on top.

---

## Performance Results (before indexes)

Benchmark tool: [scripts/benchmark_endpoints.py](scripts/benchmark_endpoints.py)  
Method: 5 HTTP requests per endpoint, **median** latency reported.

The benchmark covers all read-heavy and complex endpoints plus representative writes; remaining routes are simple CRUD or deprecated aliases of already-tested code paths (see [docs/APISpec.md](docs/APISpec.md) for the full route list).

| Method | Endpoint | Status | Median (ms) |
|--------|----------|--------|-------------|
| GET | `/` | 200 | 1.0 |
| GET | `/users/50000` | 200 | 1.0 |
| GET | `/users/50000/allergies` | 200 | 1.5 |
| GET | `/users/50000/top-recipes?limit=5` | 200 | **181.9** |
| GET | `/pantry/get_ingredients?user_id=50000` | 200 | 16.6 |
| GET | `/ingredients` | 200 | 12.8 |
| GET | `/recipes?limit=50` | 200 | 1.1 |
| GET | `/recipes/get_compatible?...&user_id=50000` | 200 | 81.7 |
| GET | `/households/25000/shopping-list?recipe_id=40000&user_id=50000` | 200 | 2.6 |
| POST | `/users/add_allergy` | 200 | 1.2 |
| POST | `/ingredients/save` | 200 | 1.4 |
| POST | `/recipes/40000/consume` | 409 | 1.5 |

**Slowest endpoint:** `GET /users/{user_id}/top-recipes` at **181.9 ms** median.

This endpoint joins all recipes to all `recipe_ingredients`, aggregates coverage against the user's available pantry (own + shared household items), excludes allergen recipes, sorts, and limits — the heaviest read in the API.

---

## Performance Tuning

Target: `GET /users/{user_id}/top-recipes`  
EXPLAIN script: [scripts/explain_top_recipes.sql](scripts/explain_top_recipes.sql)

### Iteration 1 — baseline EXPLAIN (before indexes)

```
Execution Time: 249.740 ms
```

Key plan nodes:

```
Hash Join  (actual time=47.540..130.113 rows=648666.00 loops=1)
  ->  Seq Scan on recipe_ingredients ri  (rows=650000)
  ->  Hash  (rows=79852)
        ->  Seq Scan on recipes r
              Filter: NOT (recipe in allergen recipes)

HashAggregate  (actual time=212.622..241.684 rows=72073.00 loops=1)
  Group Key: r.recipe_id
  Batches: 5  Memory Usage: 8249kB  Disk Usage: 15304kB

Seq Scan on household_members  (rows removed by filter: 99999)
  Filter: (user_id = 50000)
```

**Interpretation:**

1. **Full scan of `recipe_ingredients` (650k rows)** — required to score every recipe; dominates join cost.
2. **HashAggregate spilling to disk** — grouping all recipe/ingredient pairs is memory-heavy.
3. **Sequential scan on `household_members` for `user_id = 50000`** — no index on `user_id`; Postgres reads all 100k membership rows to find one household.

### Indexes added (migration `0005_perf_indexes`)

File: [alembic/versions/0005_perf_indexes.py](alembic/versions/0005_perf_indexes.py)

```sql
CREATE INDEX idx_household_members_user_id ON household_members (user_id);
CREATE INDEX idx_recipe_ingredients_ingredient_id ON recipe_ingredients (ingredient_id);
CREATE INDEX idx_pantry_user_id ON pantry (user_id);
CREATE INDEX idx_pantry_user_shared ON pantry (user_id)
  WHERE is_shared_with_household = true;
```

Apply locally:

```bash
alembic upgrade head
psql -d foodgraph_perf -c "ANALYZE;"
```

**Why these indexes:**

| Index | Addresses |
|-------|-----------|
| `idx_household_members_user_id` | Household lookup in available-pantry CTE (was seq scan 100k rows) |
| `idx_recipe_ingredients_ingredient_id` | Allergen exclusion subquery (`ingredient_id IN allergens`) |
| `idx_pantry_user_id` | User's own pantry rows |
| `idx_pantry_user_shared` (partial) | Shared housemate pantry rows |

### Iteration 1 — EXPLAIN after indexes

```
Execution Time: 211.043 ms   (~15% faster)
```

Improvements observed:

```
Index Scan using idx_household_members_user_id on household_members
  (actual time=0.015..0.016 rows=1.00 loops=3)
  -- was: Seq Scan, 99999 rows removed by filter

Index Scan using idx_pantry_user_shared on pantry p
  -- was: Index Scan on pantry_pkey with filter on is_shared_with_household
```

The **Hash Join + HashAggregate over 650k `recipe_ingredients` rows** remains the bottleneck. That is inherent to “rank every recipe in the catalog” unless we add caching or pre-aggregated tables. At ~177 ms end-to-end for 80k recipes / 650k edges on a laptop, the endpoint is acceptable for an interactive read API (<200 ms).

### Results after indexes

| Method | Endpoint | Median before (ms) | Median after (ms) |
|--------|----------|--------------------|-------------------|
| GET | `/users/50000/top-recipes` | **181.9** | **177.4** |
| GET | `/recipes/get_compatible` | 81.7 | 83.7 |
| GET | `/pantry/get_ingredients` | 16.6 | 13.0 |
| GET | `/ingredients` | 12.8 | 13.3 |

**Slowest endpoint after tuning:** still `GET /users/{user_id}/top-recipes` at **177.4 ms** — improved but still the heaviest query by design.

### Iteration 2 — query rewrite (aggregate `recipe_ingredients` first)

After indexes, the remaining cost was a **Hash Join of `recipes` × `recipe_ingredients`** before aggregation. Pass 2 restructures the query in [src/api/users.py](src/api/users.py):

1. Resolve **available pantry IDs** and **allergen recipe IDs** in small upfront queries (indexed paths from iteration 1).
2. **Aggregate only `recipe_ingredients`** (650k rows) into per-recipe `total_count` / `have_count`.
3. **Join `recipes` only for the top-N** rows after `ORDER BY … LIMIT 5`.

This removes the full-table hash join on `recipes` and lets Postgres use a bound `IN (...)` list for pantry coverage instead of a correlated subquery.

**EXPLAIN after rewrite:**

```
Execution Time: 125.273 ms   (~41% faster than post-index plan)
```

Key plan change: single `HashAggregate` on `recipe_ingredients` only, then a small nested-loop join to `recipes` for 5 rows.

### Results after query rewrite

| Method | Endpoint | Before indexes | After indexes | After rewrite |
|--------|----------|----------------|---------------|---------------|
| GET | `/users/50000/top-recipes` | **181.9** | **177.4** | **103.0** |

**Slowest endpoint after both passes:** still `GET /users/{user_id}/top-recipes` at **103.0 ms** — now under the 200 ms interactive threshold with meaningful headroom.

### Conclusion

Indexes removed the obvious planner mistakes (household membership seq scan, unindexed allergen/pantry paths). The query rewrite removed the redundant `recipes` hash join, cutting end-to-end latency by ~43% on top of indexes. Remaining cost is the core algorithm: aggregate the full recipe–ingredient graph. Further gains would require architectural changes (materialized coverage scores, pagination of recipe catalog, or background precomputation).

For production, **103 ms at 1.1M rows locally** is solid; Supabase/Render with a smaller dataset will be faster.

---

## Commands reference

```bash
# One-time: local DB + seed
createdb foodgraph_perf
alembic upgrade head
python scripts/seed_perf_data.py

# Benchmark
uvicorn src.server:app --reload   # terminal 1
python scripts/benchmark_endpoints.py   # terminal 2

# Apply perf indexes
alembic upgrade head
psql -d foodgraph_perf -c "ANALYZE;"

# EXPLAIN
psql -d foodgraph_perf -f scripts/explain_top_recipes.sql
```
