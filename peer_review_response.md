# Peer review response (V4)

Feedback was collected from GitHub issues filed by peer reviewers **Aaron Lee**, **Joe Croney**, and **Anay Agrawal** during the V2 review cycle (issues #3–#10). This document records what we changed, where the behavior lives now, and what we intentionally deferred.

---

## Aaron Lee — Code review (#9)

| # | Feedback | Response |
|---|----------|----------|
| 1 | Extract repeated user-exists checks into a helper | **Addressed.** `assert_exists()` in `src/api/helpers.py`, used across routers. |
| 2 | Reject whitespace-only `first_name` | **Addressed.** Pydantic validator on `CreateUserRequest` in `src/api/users.py`. |
| 3 | Duplicate allergy insert should return a clear response | **Addressed.** Pre-check + idempotent `SuccessResponse` with `message`; race logged and handled. |
| 4 | `get_all_ingredients` should use SQLAlchemy + `ORDER BY` | **Addressed.** Core `select()` with `order_by(ingredient_id)`; legacy path kept as deprecated alias. |
| 5 | Household join duplicate `IntegrityError` should be explicit | **Addressed.** Pre-check + friendly `SuccessResponse` / logged race handler in `households.py`. |
| 6 | Normalize email (trim, lowercase) | **Addressed.** Email validator on create user. |
| 7 | Centralize `SuccessResponse` | **Addressed.** `src/api/models.py`. |
| 8 | Recipe filter should check every required ingredient | **Addressed.** SQL `HAVING` counts in `get_compatible` (all required IDs must be in the supplied set). |
| 9 | Household create rollback should not orphan households | **Addressed.** Single transaction; explicit error logging and 500 on failure. |
| 10 | `delete` ingredient should verify user exists | **Addressed.** `assert_exists` for user and ingredient in `_delete_pantry_item`. |
| 11 | Multi-household pantry ambiguity + no quantities | **Partially addressed.** Quantities/units added in migration `0004_v3_schema_extras` and save payload; **one household per user** enforced on create/join (see schema #5). |

---

## Aaron Lee — Schema / API (#10)

| # | Feedback | Response |
|---|----------|----------|
| 1 | `DELETE` for ingredient removal, `GET` for allergies | **Addressed.** `DELETE /ingredients/{id}?user_id=` and `GET /users/{id}/allergies`; legacy POST routes deprecated. |
| 2 | RESTful pantry path (`/pantry/{user_id}`) | **Partially addressed.** Query-param `GET /pantry/get_ingredients` retained for backward compatibility; documented in APISpec. |
| 3 | Prefer singular JSON objects over arrays for singleton responses | **Not changed.** List endpoints (pantry, recipes, allergies) correctly return arrays; create endpoints return a single object. Wrapping a one-element list in an object would break existing clients. |
| 4 | One household per user | **Addressed.** 409 on create/join if user already has a membership. |
| 5 | Pantry quantity | **Addressed.** Schema + optional fields on save. |
| 6 | Recipe ingredient quantity | **Addressed.** Schema + `POST /recipes` ingredient list. |
| 7 | Timestamps / audit | **Addressed.** `created_at`, `updated_at`, `joined_at` via migration `0004`. |
| 8 | Blank ingredient names | **Addressed.** DB check constraint `ck_ingredient_name_normalized` (lowercase, trimmed, non-empty). |
| 9 | Expiration on pantry items | **Addressed.** `expiry_date`, `purchase_date` on `pantry`. |
| 10 | Leave household endpoint | **Addressed.** `DELETE /households/{id}/members/{user_id}`. |
| 11 | Normalize ingredient name duplicates | **Addressed.** Same check constraint; API does not accept creates with bad names (catalog is seeded). |
| 12 | Ingredient name de-duplication in API | **Deferred.** No `POST /ingredients` create endpoint yet; normalization is enforced at DB layer for future admin tooling. |

---

## Aaron Lee — Product ideas (#12)

| Idea | Response |
|------|----------|
| Allergy-aware recipe recommender with cuisine preferences | **Deferred.** V4 ships ranked coverage via `GET /users/{id}/top-recipes` instead; cuisine prefs need new schema. |
| Nutrition labels per recipe | **Deferred.** Requires external nutrition data and richer quantity modeling beyond course scope. |

---

## Joe Croney — Code review (#5)

| # | Feedback | Response |
|---|----------|----------|
| 1 | Raw SQL in `get_all_ingredients` | **Addressed.** See Aaron #4. |
| 2 | Duplicate `SuccessResponse` | **Addressed.** See Aaron #7. |
| 3 | `engine.begin()` on read-only GETs | **Addressed.** Reads use `engine.connect()`. |
| 4 | Dead code `if not ingredient_ids` in `get_compatible` | **Addressed.** Removed; FastAPI `min_length=1` on query param. |
| 5 | POST for read/delete | **Addressed.** RESTful routes added; legacy deprecated. |
| 6 | Full-table scan recipe filter in Python | **Addressed.** Filter pushed to SQL `HAVING`. |
| 7 | Duplicated existence checks | **Addressed.** `assert_exists` helper. |
| 8 | No logging; silent `IntegrityError` | **Addressed.** Module logger; duplicate paths return messages or log warnings. |
| 9 | `.env.example` missing | **Addressed.** `.env.example` in repo root. |
| 10 | Verb in URL; no pagination on ingredients | **Partially addressed.** `GET /ingredients` alias; pagination deferred (catalog still small). |
| 11 | Unused `pantry_id` surrogate | **Addressed.** Dropped in migration `0004`; composite PK `(user_id, ingredient_id)`. |
| 12 | Dead `array_agg or []` guard | **Addressed.** Removed with SQL rewrite. |
| 13 | Health check should ping DB | **Addressed.** `GET /` runs `SELECT 1`, returns 503 on failure. |

---

## Joe Croney — Schema / API (#6)

| # | Feedback | Response |
|---|----------|----------|
| 1–4 | Quantities, expiry, timestamps | **Addressed.** Migration `0004`. |
| 5 | `last_name` on users | **Addressed.** Optional column + create payload. |
| 6 | Remove allergy endpoint | **Addressed.** `DELETE /users/{id}/allergies/{ingredient_id}`. |
| 7 | Leave/delete household | **Addressed.** Member DELETE; whole-household DELETE deferred. |
| 8 | Delete user account | **Addressed.** `DELETE /users/{id}`. |
| 9 | `GET /users/{id}` profile | **Addressed.** |
| 10 | Users create recipes | **Addressed.** `POST /recipes` with `created_by`. |
| 11 | Browse/search recipes | **Addressed.** `GET /recipes?q=&limit=&offset=`. |
| 12 | `RESTRICT` on recipe_ingredients → ingredients | **Addressed.** FK changed to `ON DELETE CASCADE` in migration `0004`. |
| 13 | Unique household names | **Deferred.** Names are display labels; IDs are canonical. Uniqueness would break independent groups choosing the same name. |
| 14 | `created_by` on households | **Addressed.** Set on create. |
| 15 | Ingredient categories / tags | **Deferred.** Needs new taxonomy tables; out of V4 scope. |

---

## Joe Croney — Product ideas (#8)

| Idea | Response |
|------|----------|
| `GET /households/{id}/shopping-list` | **Addressed (V4 complex endpoint).** |
| `GET /users/{id}/top-recipes` | **Addressed (V4 complex endpoint).** |

---

## Anay Agrawal — Code review (#3)

| # | Feedback | Response |
|---|----------|----------|
| 1 | Already-member message on household join | **Addressed.** `SuccessResponse` with explicit `message`. |
| 2 | Save/delete by ingredient name | **Deferred.** IDs keep referential integrity; name→id resolution needs lookup + ambiguity handling. |
| 3 | Pantry GET mixes own vs shared items | **Documented.** Deletes only affect the caller’s rows (`user_id` in `WHERE`). Shared items are visible but not deletable by other members—see test note in issue #1 step 3.2a. Split response (`my` vs `shared`) deferred to avoid breaking V2 clients. |
| 4 | Pantry query readability | **Partially addressed.** Commented subqueries for housemates vs own items in `pantry.py`. |
| 5 | `get_compatible` should default to user’s pantry | **Deferred.** Callers can use `GET /pantry/get_ingredients` then pass IDs, or use `GET /users/{id}/top-recipes` for pantry-driven ranking. |
| 6 | Order recipe results | **Addressed.** `order_by(recipe_id)` in SQL. |
| 7 | SQL-side recipe filter | **Addressed.** See Joe #6. |
| 8 | Duplicate allergy handling | **Addressed.** See Aaron #3. |
| 9 | Whitespace `first_name` | **Addressed.** See Aaron #2. |
| 10 | User-exists helper | **Addressed.** See Aaron #1. |
| 11 | Delete should validate user/ingredient | **Addressed.** See Aaron #10. |
| 12 | Remove allergy endpoint | **Addressed.** See Joe schema #6. |

---

## Anay Agrawal — Schema / API (#4)

| # | Feedback | Response |
|---|----------|----------|
| 1 | `saved_at` on pantry | **Addressed.** `created_at` / `updated_at` on pantry. |
| 2 | Separate household pantry table | **Deferred.** `is_shared_with_household` + member queries remain the model; less migration risk. |
| 3–4 | Quantities on pantry and recipe_ingredients | **Addressed.** |
| 5 | Add ingredients by name | **Deferred.** Same as Anay code #2. |
| 6 | Compatible recipes should explain matches | **Partially addressed.** `top-recipes` returns `missing_ingredients`; full “why matched” copy deferred. |
| 7–8 | API auth / user scoping | **Deferred.** Course API is intentionally open; production would add auth middleware (out of DB project scope). |
| 9 | Success messages | **Addressed.** `SuccessResponse.message` on mutating endpoints. |
| 10 | Normalize emails | **Addressed.** See Aaron #6. |
| 11 | Remove from household | **Addressed.** |
| 12 | `joined_at` on household membership | **Addressed.** |

---

## Anay Agrawal — Product ideas (#2)

| Idea | Response |
|------|----------|
| Weekly meal plan | **Deferred.** Large feature; needs consume/plan schema. |
| Recipes for full household with all allergies | **Partially addressed.** Shopping list + top-recipes cover overlapping use cases; dedicated household-allergy filter deferred. |

---

## Test / workflow issues (#1, #7, #11)

Peer workflow runs and extra test cases were reviewed. No code changes required for those issues themselves; they informed the fixes above (e.g. allergy filtering, household pantry merge, duplicate email 409).

---

## V4 deliverables cross-reference

| Requirement | Artifact |
|-------------|----------|
| Two complex endpoints | `GET /households/{id}/shopping-list`, `GET /users/{id}/top-recipes` (documented in `docs/APISpec.md`) |
| Concurrency write-up | `concurrency.md` |
| This peer review log | `peer_review_response.md` |
