# Example workflow

> Flow 1: The College Student with a Nut Allergy
>
> Sarah, a college student on a budget, signs up for the application because
> she wants to know what recipes she can make given the ingredients already
> sitting in her pantry. She also has a severe nut allergy and needs to be
> certain her meals are safe.
>
> 1. Sarah creates a new account by calling `POST /users/create` with
>    `"first_name": "Sarah"` and `"email": "sarah@example.com"`, and
>    receives a `user_id`.
> 2. She records her allergy by calling `POST /users/add_allergy` with her
>    `user_id` and the `ingredient_id` for peanuts (42).
> 3. She logs the groceries she has on hand — chicken, rice, and broccoli —
>    by calling `POST /ingredients/save` three times.
> 4. She finds dinner options by calling `GET /recipes/get_compatible` with
>    the IDs of chicken, rice, and broccoli. The app returns safe,
>    peanut-free recipes like "Chicken and Broccoli Stir-Fry".

# Testing results

## Step 1 — Create Sarah's account

```
curl -X 'POST' \
  'https://foodgraph-api.onrender.com/users/create' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "first_name": "Sarah",
  "email": "sarah@example.com"
}'
```

Response (201 Created):

```json
{
  "user_id": 1
}
```

> _If you see `409 Conflict` with `"A user with that email already exists."`,
> the test was already run against this database — drop and re-create the DB
> (or `alembic downgrade base && alembic upgrade head`) and try again._

## Step 2 — Record Sarah's peanut allergy

```
curl -X 'POST' \
  'https://foodgraph-api.onrender.com/users/add_allergy' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_id": 1,
  "ingredient_id": 42
}'
```

Response (200 OK):

```json
{
  "success": true
}
```

## Step 3a — Save chicken to Sarah's pantry

```
curl -X 'POST' \
  'https://foodgraph-api.onrender.com/ingredients/save' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_id": 1,
  "ingredient_id": 1,
  "is_shared_with_household": false
}'
```

Response (200 OK):

```json
{
  "success": true
}
```

## Step 3b — Save rice to Sarah's pantry

```
curl -X 'POST' \
  'https://foodgraph-api.onrender.com/ingredients/save' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_id": 1,
  "ingredient_id": 2,
  "is_shared_with_household": false
}'
```

Response (200 OK):

```json
{
  "success": true
}
```

## Step 3c — Save broccoli to Sarah's pantry

```
curl -X 'POST' \
  'https://foodgraph-api.onrender.com/ingredients/save' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_id": 1,
  "ingredient_id": 3,
  "is_shared_with_household": false
}'
```

Response (200 OK):

```json
{
  "success": true
}
```

## Step 4 — Find compatible recipes (peanut-free)

```
curl -X 'GET' \
  'https://foodgraph-api.onrender.com/recipes/get_compatible?ingredient_ids=1&ingredient_ids=2&ingredient_ids=3&user_id=1' \
  -H 'accept: application/json'
```

Response (200 OK):

```json
[
  {
    "recipe_id": 3,
    "recipe_name": "Steamed Broccoli",
    "recipe_steps": "1) Steam broccoli 4-5 minutes. 2) Season and serve."
  },
  {
    "recipe_id": 1,
    "recipe_name": "Chicken and Broccoli Stir-Fry",
    "recipe_steps": "1) Cook rice. 2) Cook chicken in a hot pan until done. 3) Add broccoli, stir-fry until tender. 4) Serve over rice."
  }
]
```

> Sarah gets her stir-fry (and a steamed broccoli option). The "Peanut Chicken"
> recipe in the catalog is filtered out — Sarah doesn't have peanuts in her
> pantry, and even if she did her recorded allergy on `user_id=1` would
> exclude it. Verified with a follow-up call passing peanuts AND `user_id=1`,
> which returns `[]`; the same call without `user_id` returns Peanut Chicken,
> proving the allergy filter is what excluded it.
