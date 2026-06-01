# Live demo — Food Graph API (Render + Supabase)

**Base URL:** `https://foodgraph-api.onrender.com`  
**Interactive docs:** https://foodgraph-api.onrender.com/docs  
**Database:** Supabase Postgres (schema via `alembic upgrade head`; **no** 1M-row perf seed on hosted DB)

Copy-paste helpers (run in terminal):

```bash
BASE=https://foodgraph-api.onrender.com
# Unique email per demo run (avoids 409 duplicate signup)
TS=$(date +%s)
```

**Before you present:** wake the service (cold start ~30–60s):

```bash
curl -s "$BASE/" | python3 -m json.tool
# Expect: "database": "ok", "version": "0.4.0"
```

Optional pretty-print for any command below:

```bash
# append to curl:  | python3 -m json.tool
```

---

## Seeded catalog (always present after migrations)

Migrations seed **ingredients** and **recipes** only. **Users and households are created by your demo** (IDs depend on what already exists in Supabase).

| ingredient_id | name |
|---------------|------|
| 1 | chicken |
| 2 | rice |
| 3 | broccoli |
| 4 | soy sauce |
| 5 | garlic |
| 6 | olive oil |
| 7 | tomato |
| 8 | basil |
| 9 | egg |
| 10 | spinach |
| 42 | peanuts |

| recipe_id | name | ingredient_ids |
|-----------|------|------------------|
| 1 | Chicken and Broccoli Stir-Fry | 1, 2, 3 |
| 2 | Peanut Chicken | 1, 42 |
| 3 | Steamed Broccoli | 3 |
| 4 | Tomato Basil Spaghetti-Style Rice | 2, 5, 6, 7, 8 |
| 5 | Spinach Frittata | 5, 6, 9, 10 |
| 6 | Eggs and Spinach Scramble | 9, 10 |

**User IDs on a fresh Supabase DB:** first signup is usually `user_id: 1`, second `2`, etc. If the DB already has users, capture IDs from each `POST /users/create` response and export them:

```bash
export SARAH=1   # replace with actual user_id from JSON
export MARK=2
export LEO=3
export DAVID=4
export HH=1      # household_id from POST /households/create
```

---

## Flow 1 — Sarah (nut allergy + compatible recipes)

Narrative: sign up → record peanut allergy → stock pantry → find **safe** full-match recipes (excludes recipe 2 “Peanut Chicken”).

### 1. Health check

```bash
curl -s "$BASE/"
```

### 2. Create Sarah

```bash
curl -s -X POST "$BASE/users/create" \
  -H "Content-Type: application/json" \
  -d "{\"first_name\":\"Sarah\",\"last_name\":\"Smith\",\"email\":\"sarah-${TS}@example.com\"}"
```

Save `user_id` → `SARAH`.

### 3. Add peanut allergy (ingredient 42)

```bash
curl -s -X POST "$BASE/users/add_allergy" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":$SARAH,\"ingredient_id\":42}"
```

### 4. Save pantry: chicken, rice, broccoli

```bash
for IID in 1 2 3; do
  curl -s -X POST "$BASE/ingredients/save" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\":$SARAH,\"ingredient_id\":$IID,\"is_shared_with_household\":false,\"quantity\":2,\"unit\":\"lb\"}"
  echo
done
```

### 5. Compatible recipes (with allergy filter)

Expect recipe **1**, not **2** (peanuts):

```bash
curl -s "$BASE/recipes/get_compatible?ingredient_ids=1&ingredient_ids=2&ingredient_ids=3&user_id=$SARAH"
```

### 6. Profile + list allergies

```bash
curl -s "$BASE/users/$SARAH"
curl -s "$BASE/users/$SARAH/allergies"
```

---

## Flow 2 — Mark & Leo (household + shared pantry)

Narrative: Mark creates household → Leo signs up → Leo joins → combined pantry → compatible recipes for eggs + spinach.

### 1. Create Mark

```bash
curl -s -X POST "$BASE/users/create" \
  -H "Content-Type: application/json" \
  -d "{\"first_name\":\"Mark\",\"email\":\"mark-${TS}@example.com\"}"
```

Save `user_id` → `MARK`.

### 2. Create household “The Bachelor Pad”

```bash
curl -s -X POST "$BASE/households/create" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":$MARK,\"household_name\":\"The Bachelor Pad\"}"
```

Save `household_id` → `HH`.

### 3. Create Leo

```bash
curl -s -X POST "$BASE/users/create" \
  -H "Content-Type: application/json" \
  -d "{\"first_name\":\"Leo\",\"email\":\"leo-${TS}@example.com\"}"
```

Save `user_id` → `LEO`.

### 4. Leo joins household

```bash
curl -s -X POST "$BASE/households/join" \
  -H "Content-Type: application/json" \
  -d "{\"household_id\":$HH,\"user_id\":$LEO}"
```

### 5. Mark saves eggs (shared); Leo saves spinach (shared)

```bash
curl -s -X POST "$BASE/ingredients/save" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":$MARK,\"ingredient_id\":9,\"is_shared_with_household\":true,\"quantity\":6,\"unit\":\"each\"}"

curl -s -X POST "$BASE/ingredients/save" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":$LEO,\"ingredient_id\":10,\"is_shared_with_household\":true,\"quantity\":1,\"unit\":\"bunch\"}"
```

### 6. Mark’s pantry view (sees housemate shared items)

```bash
curl -s "$BASE/pantry/get_ingredients?user_id=$MARK"
```

### 7. Compatible recipes for eggs + spinach

Expect recipe **5** or **6**:

```bash
curl -s "$BASE/recipes/get_compatible?ingredient_ids=9&ingredient_ids=10&user_id=$MARK"
```

---

## Flow 3 — David (pantry tidy-up)

Narrative: check pantry → remove items → add new groceries → search compatible recipes.

Uses rice (2) and garlic (5) as stand-ins for “arborio” / “broth” from the story; basil (8) and tomato (7) for farmer’s market.

### 1. Create David

```bash
curl -s -X POST "$BASE/users/create" \
  -H "Content-Type: application/json" \
  -d "{\"first_name\":\"David\",\"email\":\"david-${TS}@example.com\"}"
```

Save `user_id` → `DAVID`.

### 2. Seed pantry (rice + garlic) then read

```bash
curl -s -X POST "$BASE/ingredients/save" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":$DAVID,\"ingredient_id\":2,\"quantity\":1,\"unit\":\"cup\"}"

curl -s -X POST "$BASE/ingredients/save" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":$DAVID,\"ingredient_id\":5,\"quantity\":2,\"unit\":\"clove\"}"

curl -s "$BASE/pantry/get_ingredients?user_id=$DAVID"
```

### 3. Remove rice (RESTful DELETE)

```bash
curl -s -X DELETE "$BASE/ingredients/2?user_id=$DAVID"
```

### 4. Remove garlic (deprecated POST — still supported)

```bash
curl -s -X POST "$BASE/ingredients/delete" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":$DAVID,\"ingredient_id\":5}"
```

### 5. Add basil + tomato

```bash
curl -s -X POST "$BASE/ingredients/save" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":$DAVID,\"ingredient_id\":8,\"quantity\":1,\"unit\":\"bunch\"}"

curl -s -X POST "$BASE/ingredients/save" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":$DAVID,\"ingredient_id\":7,\"quantity\":4,\"unit\":\"each\"}"
```

### 6. Compatible recipes with new pantry

```bash
curl -s "$BASE/recipes/get_compatible?ingredient_ids=7&ingredient_ids=8&user_id=$DAVID"
```

---

## V4 “hard” endpoints (complex reads)

Run **after Flow 1 and/or Flow 2** so users have pantry + (for shopping-list) household data.

### `GET /users/{user_id}/top-recipes`

Partial coverage ranking + `missing_ingredients` (unlike `get_compatible`, which requires 100% match).

**After Flow 1 (Sarah):**

```bash
curl -s "$BASE/users/$SARAH/top-recipes?limit=5"
```

**After Flow 2 (Mark):**

```bash
curl -s "$BASE/users/$MARK/top-recipes?limit=5"
```

**Talking point:** excludes allergen recipes; includes shared household pantry when user is in a household.

### `GET /households/{household_id}/shopping-list`

Recipe vs combined household pantry → `have`, `missing`, `coverage_pct`. Uses `REPEATABLE READ` (see `docs/concurrency.md`).

**After Flow 2 — recipe 4 (needs rice, garlic, olive oil, tomato, basil):**

```bash
curl -s "$BASE/households/$HH/shopping-list?recipe_id=4&user_id=$MARK"
```

Mark has eggs; Leo has spinach — expect most of recipe 4 in `missing`, eggs not required for recipe 4.

**After stocking Mark’s pantry for recipe 4 (optional richer demo):**

```bash
for IID in 2 5 6 7 8; do
  curl -s -X POST "$BASE/ingredients/save" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\":$MARK,\"ingredient_id\":$IID,\"is_shared_with_household\":true,\"quantity\":10,\"unit\":\"unit\"}"
done

curl -s "$BASE/households/$HH/shopping-list?recipe_id=4&user_id=$MARK"
```

### `POST /recipes/{recipe_id}/consume` (concurrency)

`SERIALIZABLE` + `FOR UPDATE` on pantry rows.

**Success path (after Flow 1 — Sarah has chicken, rice, broccoli with quantity):**

```bash
curl -s -X POST "$BASE/recipes/1/consume" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":$SARAH}"
```

**Failure path — insufficient / missing pantry (409):**

```bash
# New user, no pantry
curl -s -X POST "$BASE/users/create" \
  -H "Content-Type: application/json" \
  -d "{\"first_name\":\"Empty\",\"email\":\"empty-${TS}@example.com\"}"
# export EMPTY=<user_id from response>

curl -s -X POST "$BASE/recipes/1/consume" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":$EMPTY}"
```

Read `detail` in the JSON — e.g. `Missing pantry item: chicken …` or `Insufficient …`.

---

## Edge cases (demo these on purpose)

### 404 — not found

```bash
curl -s "$BASE/users/999999"
# → "User not found."

curl -s -X DELETE "$BASE/ingredients/1?user_id=$SARAH"
# Run twice: second time → not in pantry (if you deleted it in Flow 3)

curl -s -X DELETE "$BASE/users/$SARAH/allergies/999"
# → allergy not on file (if 999 not an allergen)
```

### 409 — business rule conflicts

**Duplicate email** (run Flow 1 create twice with the **same** email):

```bash
curl -s -X POST "$BASE/users/create" \
  -H "Content-Type: application/json" \
  -d "{\"first_name\":\"Sarah\",\"email\":\"sarah-${TS}@example.com\"}"
```

**User already in a household** (Mark creates again without leaving):

```bash
curl -s -X POST "$BASE/households/create" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":$MARK,\"household_name\":\"Second Home\"}"
```

**Join second household** (Leo already in `$HH`, try another household id if one exists, or create a second household with a third user first):

```bash
# After Leo is in HH — create another household with a throwaway user, then:
curl -s -X POST "$BASE/households/join" \
  -H "Content-Type: application/json" \
  -d "{\"household_id\":OTHER_HH,\"user_id\":$LEO}"
```

**Consume without stock** — see consume failure path above.

### 403 — not a household member

```bash
curl -s "$BASE/households/$HH/shopping-list?recipe_id=4&user_id=$DAVID"
# David was never in Mark's household → 403
```

### 200 — idempotent / soft success

**Duplicate allergy:**

```bash
curl -s -X POST "$BASE/users/add_allergy" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":$SARAH,\"ingredient_id\":42}"
# → "already on file; no change made"
```

**Join when already a member:**

```bash
curl -s -X POST "$BASE/households/join" \
  -H "Content-Type: application/json" \
  -d "{\"household_id\":$HH,\"user_id\":$LEO}"
# → already a member message
```

### Deprecated routes (if asked)

```bash
curl -s -X POST "$BASE/users/get_allergies" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":$SARAH}"

curl -s "$BASE/ingredients/get_all_ingredients"
```

Same data as `GET /users/{id}/allergies` and `GET /ingredients`.

---

## Other endpoints (quick reference)

```bash
# Catalog
curl -s "$BASE/ingredients"
curl -s "$BASE/recipes?limit=50"

# Create recipe
curl -s -X POST "$BASE/recipes" \
  -H "Content-Type: application/json" \
  -d "{\"created_by\":$SARAH,\"recipe_name\":\"Demo Bowl\",\"recipe_steps\":\"Mix and serve.\",\"ingredients\":[{\"ingredient_id\":1,\"quantity\":1,\"unit\":\"lb\"},{\"ingredient_id\":3}]}"

# Leave household
curl -s -X DELETE "$BASE/households/$HH/members/$LEO"

# Delete user (destructive — use a throwaway account only)
curl -s -X DELETE "$BASE/users/$EMPTY"
```

---

## Suggested 15-minute live order

1. `GET /` — prove deploy + DB  
2. **Flow 1** — allergy + `get_compatible`  
3. **Hard:** `top-recipes` for Sarah  
4. **Flow 2** — household + shared `pantry/get_ingredients`  
5. **Hard:** `shopping-list` for recipe 4  
6. **Edge:** 409 duplicate email, 403 non-member shopping-list, 409 consume empty user  
7. **Optional:** successful `consume` on recipe 1  
8. **V5 (30s):** “1M rows tested locally; writeup in `docs/performance_writeup.md`” — do **not** run perf seed on Supabase  

---

## Swagger UI

Open **https://foodgraph-api.onrender.com/docs** — every route has “Try it out”. Use the same bodies as above; paste `user_id` / `household_id` from responses.

---

## Related docs

| Doc | Purpose |
|-----|---------|
| [docs/ExampleFlows.md](docs/ExampleFlows.md) | Story narratives |
| [docs/APISpec.md](docs/APISpec.md) | Full API reference |
| [docs/concurrency.md](docs/concurrency.md) | consume + shopping-list isolation |
| [docs/performance_writeup.md](docs/performance_writeup.md) | V5 local 1M-row benchmark (not Render) |
| [docs/v2_manual_test_results.md](docs/v2_manual_test_results.md) | Example responses on a fresh DB |
