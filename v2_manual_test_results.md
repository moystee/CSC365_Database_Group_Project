# Example workflows

> Replace `https://YOUR-RENDER-URL` with the actual URL Render assigns
> after deploy. While testing locally, use `http://localhost:8000`.
>
> All three flows below were executed end-to-end against a fresh database
> (`alembic upgrade head` on a clean `foodgraph_test` Postgres). User
> IDs and household IDs in the responses below assume that exact
> sequence — Sarah=1, Mark=2, Leo=3, David=4, household=1.

---

## Flow 1: The College Student with a Nut Allergy

> Sarah signs up, records her peanut allergy, logs the ingredients in her
> kitchen (chicken, rice, broccoli), and asks for safe recipes. The
> response excludes Peanut Chicken because of her allergy.

### Step 1 — Create Sarah's account

```
curl -X 'POST' \
  'https://YOUR-RENDER-URL/users/create' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "first_name": "Sarah",
  "email": "sarah@example.com"
}'
```

Response (201 Created):

```json
{ "user_id": 1 }
```

### Step 2 — Record Sarah's peanut allergy

```
curl -X 'POST' \
  'https://YOUR-RENDER-URL/users/add_allergy' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_id": 1,
  "ingredient_id": 42
}'
```

Response (200 OK):

```json
{ "success": true }
```

### Step 3a — Save chicken (id 1) to Sarah's pantry

```
curl -X 'POST' \
  'https://YOUR-RENDER-URL/ingredients/save' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_id": 1,
  "ingredient_id": 1
}'
```

Response (200 OK):

```json
{ "success": true }
```

### Step 3b — Save rice (id 2)

```
curl -X 'POST' \
  'https://YOUR-RENDER-URL/ingredients/save' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_id": 1,
  "ingredient_id": 2
}'
```

Response (200 OK):

```json
{ "success": true }
```

### Step 3c — Save broccoli (id 3)

```
curl -X 'POST' \
  'https://YOUR-RENDER-URL/ingredients/save' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_id": 1,
  "ingredient_id": 3
}'
```

Response (200 OK):

```json
{ "success": true }
```

### Step 4 — Find compatible recipes (allergy-aware)

```
curl -X 'GET' \
  'https://YOUR-RENDER-URL/recipes/get_compatible?ingredient_ids=1&ingredient_ids=2&ingredient_ids=3&user_id=1' \
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

> Peanut Chicken is excluded because it requires peanuts (id 42) — both
> filters apply: peanuts aren't in Sarah's available list, and even if
> they were, `user_id=1` causes the recipe to be skipped for her allergy.

---

## Flow 2: Roommates Minimizing Food Waste

> Mark already has an account. He creates a household ("The Bachelor
> Pad"). Leo signs up and joins it. They each save one ingredient
> (Mark: eggs, Leo: spinach). When Mark fetches his pantry, both items
> show up automatically because they share the household. He passes the
> merged list to `/recipes/get_compatible` and gets back the Eggs and
> Spinach Scramble.

### Step 1 — Create Mark's account

```
curl -X 'POST' \
  'https://YOUR-RENDER-URL/users/create' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "first_name": "Mark",
  "email": "mark@example.com"
}'
```

Response (201 Created):

```json
{ "user_id": 2 }
```

### Step 2 — Mark creates a household

```
curl -X 'POST' \
  'https://YOUR-RENDER-URL/households/create' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_id": 2,
  "household_name": "The Bachelor Pad"
}'
```

Response (201 Created):

```json
{ "household_id": 1 }
```

### Step 3 — Leo signs up

```
curl -X 'POST' \
  'https://YOUR-RENDER-URL/users/create' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "first_name": "Leo",
  "email": "leo@example.com"
}'
```

Response (201 Created):

```json
{ "user_id": 3 }
```

### Step 4 — Leo joins Mark's household

```
curl -X 'POST' \
  'https://YOUR-RENDER-URL/households/join' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "household_id": 1,
  "user_id": 3
}'
```

Response (200 OK):

```json
{ "success": true }
```

### Step 5a — Mark saves eggs (id 9) to his pantry

```
curl -X 'POST' \
  'https://YOUR-RENDER-URL/ingredients/save' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_id": 2,
  "ingredient_id": 9
}'
```

Response (200 OK):

```json
{ "success": true }
```

### Step 5b — Leo saves spinach (id 10)

```
curl -X 'POST' \
  'https://YOUR-RENDER-URL/ingredients/save' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_id": 3,
  "ingredient_id": 10
}'
```

Response (200 OK):

```json
{ "success": true }
```

### Step 6 — Mark fetches his pantry (household-merged)

```
curl -X 'GET' \
  'https://YOUR-RENDER-URL/pantry/get_ingredients?user_id=2' \
  -H 'accept: application/json'
```

Response (200 OK):

```json
[
  { "ingredient_id": 9,  "name": "egg" },
  { "ingredient_id": 10, "name": "spinach" }
]
```

> Spinach belongs to Leo's pantry, not Mark's — it appears in Mark's
> list because they're in the same household and the items default to
> `is_shared_with_household = true`.

### Step 7 — Find recipes that fit the combined pantry

```
curl -X 'GET' \
  'https://YOUR-RENDER-URL/recipes/get_compatible?ingredient_ids=9&ingredient_ids=10' \
  -H 'accept: application/json'
```

Response (200 OK):

```json
[
  {
    "recipe_id": 6,
    "recipe_name": "Eggs and Spinach Scramble",
    "recipe_steps": "1) Beat eggs in a bowl. 2) Wilt spinach in a hot pan. 3) Pour in eggs and scramble until set."
  }
]
```

---

## Flow 3: The Aspiring Chef Updating Inventory

> David finishes a mushroom risotto. He sets up a pantry with arborio
> rice and chicken broth, removes them after cooking, then adds fresh
> basil and tomatoes from the farmer's market. (`chicken broth` is
> represented by the chicken ingredient and `arborio rice` by rice, since
> the V1/V2 seed catalog uses simplified names.)

### Step 0a — Create David's account

```
curl -X 'POST' \
  'https://YOUR-RENDER-URL/users/create' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "first_name": "David",
  "email": "david@example.com"
}'
```

Response (201 Created):

```json
{ "user_id": 4 }
```

### Step 0b — David's initial pantry (rice + chicken)

```
curl -X 'POST' 'https://YOUR-RENDER-URL/ingredients/save' \
  -H 'Content-Type: application/json' \
  -d '{ "user_id": 4, "ingredient_id": 2 }'

curl -X 'POST' 'https://YOUR-RENDER-URL/ingredients/save' \
  -H 'Content-Type: application/json' \
  -d '{ "user_id": 4, "ingredient_id": 1 }'
```

Both responses (200 OK):

```json
{ "success": true }
```

### Step 1 — David checks his current inventory

```
curl -X 'GET' \
  'https://YOUR-RENDER-URL/pantry/get_ingredients?user_id=4' \
  -H 'accept: application/json'
```

Response (200 OK):

```json
[
  { "ingredient_id": 1, "name": "chicken" },
  { "ingredient_id": 2, "name": "rice" }
]
```

### Step 2a — Remove rice (id 2)

```
curl -X 'POST' \
  'https://YOUR-RENDER-URL/ingredients/delete' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_id": 4,
  "ingredient_id": 2
}'
```

Response (200 OK):

```json
{ "success": true }
```

### Step 2b — Remove chicken (id 1)

```
curl -X 'POST' \
  'https://YOUR-RENDER-URL/ingredients/delete' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_id": 4,
  "ingredient_id": 1
}'
```

Response (200 OK):

```json
{ "success": true }
```

### Step 3a — Add fresh basil (id 8)

```
curl -X 'POST' \
  'https://YOUR-RENDER-URL/ingredients/save' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_id": 4,
  "ingredient_id": 8
}'
```

Response (200 OK):

```json
{ "success": true }
```

### Step 3b — Add tomatoes (id 7)

```
curl -X 'POST' \
  'https://YOUR-RENDER-URL/ingredients/save' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_id": 4,
  "ingredient_id": 7
}'
```

Response (200 OK):

```json
{ "success": true }
```

### Step 4 — David's pantry is now perfectly up to date

```
curl -X 'GET' \
  'https://YOUR-RENDER-URL/pantry/get_ingredients?user_id=4' \
  -H 'accept: application/json'
```

Response (200 OK):

```json
[
  { "ingredient_id": 7, "name": "tomato" },
  { "ingredient_id": 8, "name": "basil" }
]
```

> Pantry contents are exactly what the flow expects — the old inventory
> items are gone and the new produce is recorded. From here David's
> next `/recipes/get_compatible` call would return Tomato Basil
> Spaghetti-Style Rice once he adds the remaining staples (rice,
> garlic, olive oil) back in.
