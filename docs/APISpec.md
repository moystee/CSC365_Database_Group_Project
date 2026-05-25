# Food Graph API Specification (V4)

Base URL (deployed): `https://foodgraph-api.onrender.com`  
Interactive docs: `/docs`

Legacy V2 paths remain available but are marked **deprecated** in OpenAPI where RESTful replacements exist.

---

## V4 complex endpoints (submission call-out)

These two endpoints go beyond simple CRUD: they join multiple tables, apply business rules, and return derived aggregates.

### 1. `GET /households/{household_id}/shopping-list`

**Purpose:** Given a household and a target recipe, return which required ingredients the household already has vs still needs to buy.

**Query parameters**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `recipe_id` | int | yes | Recipe to make |
| `user_id` | int | yes | Household member requesting the diff (must be a member) |

**Example**

```bash
curl -s "https://foodgraph-api.onrender.com/households/1/shopping-list?recipe_id=4&user_id=2"
```

**Response (200)**

```json
{
  "household_id": 1,
  "household_name": "The Bachelor Pad",
  "recipe_id": 4,
  "recipe_name": "Tomato Basil Spaghetti-Style Rice",
  "have": [
    {"ingredient_id": 2, "name": "rice", "quantity_needed": null, "unit": null}
  ],
  "missing": [
    {"ingredient_id": 5, "name": "garlic", "quantity_needed": null, "unit": null}
  ],
  "coverage_pct": 20
}
```

**Tables joined:** `households`, `household_members`, `pantry`, `recipe_ingredients`, `ingredients`, `recipes`.

**Concurrency:** Runs under `REPEATABLE READ` (see `concurrency.md`).

---

### 2. `GET /users/{user_id}/top-recipes`

**Purpose:** Rank recipes by pantry coverage (including shared household items), exclude allergen recipes, and list missing ingredients for partial matches.

**Query parameters**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `limit` | int | 5 | Max recipes (1–50) |

**Example**

```bash
curl -s "https://foodgraph-api.onrender.com/users/1/top-recipes?limit=3"
```

**Response (200)**

```json
[
  {
    "recipe_id": 1,
    "recipe_name": "Chicken and Broccoli Stir-Fry",
    "recipe_steps": "…",
    "coverage_pct": 100,
    "have_count": 3,
    "total_count": 3,
    "missing_ingredients": []
  },
  {
    "recipe_id": 4,
    "recipe_name": "Tomato Basil Spaghetti-Style Rice",
    "recipe_steps": "…",
    "coverage_pct": 20,
    "have_count": 1,
    "total_count": 5,
    "missing_ingredients": [
      {"ingredient_id": 5, "name": "garlic"}
    ]
  }
]
```

**Tables joined:** `users`, `user_allergies`, `household_members`, `pantry`, `recipe_ingredients`, `recipes`, `ingredients`.

---

### Related: `POST /recipes/{recipe_id}/consume` (concurrency, not counted as a “complex endpoint”)

Deducts recipe ingredient quantities from a user’s pantry using `SERIALIZABLE` + row locks. Documented in `concurrency.md`.

---

## Users

| Method | Path | Description |
|--------|------|-------------|
| POST | `/users/create` | Create user (201, `{user_id}`) |
| GET | `/users/{user_id}` | Profile |
| DELETE | `/users/{user_id}` | Delete account |
| POST | `/users/add_allergy` | Add allergy |
| DELETE | `/users/{user_id}/allergies/{ingredient_id}` | Remove allergy |
| GET | `/users/{user_id}/allergies` | List allergies |
| GET | `/users/{user_id}/top-recipes` | **Complex:** ranked recipes |
| POST | `/users/get_allergies` | Deprecated → use GET allergies |

**Create user request**

```json
{
  "first_name": "Sarah",
  "last_name": "Smith",
  "email": "sarah@example.com"
}
```

---

## Ingredients & pantry writes

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ingredients/save` | Upsert pantry row (optional quantity, unit, dates) |
| DELETE | `/ingredients/{ingredient_id}?user_id=` | Remove from pantry |
| GET | `/ingredients` | List catalog |
| POST | `/ingredients/delete` | Deprecated |
| GET | `/ingredients/get_all_ingredients` | Deprecated |

**Save request**

```json
{
  "user_id": 1,
  "ingredient_id": 2,
  "is_shared_with_household": true,
  "quantity": 2.0,
  "unit": "cup",
  "purchase_date": "2026-05-01",
  "expiry_date": "2026-05-20"
}
```

**Success response**

```json
{"success": true, "message": "Ingredient saved to pantry."}
```

---

## Pantry read

| Method | Path | Description |
|--------|------|-------------|
| GET | `/pantry/get_ingredients?user_id=` | Own pantry + housemates’ shared items |

**Response:** array of `{ingredient_id, name}`.

---

## Households

| Method | Path | Description |
|--------|------|-------------|
| POST | `/households/create` | Create household (creator auto-joins) |
| POST | `/households/join` | Join (one household per user) |
| DELETE | `/households/{household_id}/members/{user_id}` | Leave household |
| GET | `/households/{household_id}/shopping-list` | **Complex:** shopping diff |

---

## Recipes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/recipes/get_compatible` | Full-match recipes for ingredient list (+ optional allergy filter) |
| GET | `/recipes` | Browse/search catalog |
| POST | `/recipes` | Create user recipe + ingredients |
| POST | `/recipes/{recipe_id}/consume` | Deduct pantry stock for cooking |

**Compatible recipes (query params):** `ingredient_ids` (repeatable), optional `user_id` for allergy exclusion.

---

## Meta

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check (`database: ok` when Postgres is reachable) |

---

## Error conventions

| Code | When |
|------|------|
| 404 | User, ingredient, recipe, pantry row, or membership not found |
| 409 | Duplicate email, already in another household, insufficient pantry for consume |
| 503 | Database unreachable on health check |
