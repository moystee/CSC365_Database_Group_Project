#!/usr/bin/env python3
"""Run Example Flows 1–3 and V4 hard endpoints against the Food Graph API.

Matches the curl steps in live_demo.md (Flows 1–3 + V4 hard endpoints).

Usage:
    python scripts/run_live_demo_flows.py

Set BASE_URI below before running (Render deployment).
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
# Set your deployment base URL here (no trailing slash).
# ---------------------------------------------------------------------------
BASE_URI = "https://foodgraph-api.onrender.com"
# BASE_URI = "http://127.0.0.1:8000"

REQUEST_TIMEOUT_SEC = 120


def _request(
    method: str,
    path: str,
    body: dict | None = None,
) -> tuple[int, object]:
    """Call the API; return (status_code, parsed JSON or raw text)."""
    url = BASE_URI.rstrip("/") + path
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
            raw = resp.read().decode()
            status = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        status = exc.code

    try:
        parsed: object = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        parsed = raw

    return status, parsed


def _step(label: str, method: str, path: str, body: dict | None = None) -> tuple[int, object]:
    print(f"\n--- {label} ---")
    print(f"{method} {path}")
    status, data = _request(method, path, body)
    print(f"Status: {status}")
    print(json.dumps(data, indent=2) if isinstance(data, (dict, list)) else data)
    return status, data


def _user_id(data: object) -> int:
    if not isinstance(data, dict) or "user_id" not in data:
        raise ValueError(f"Expected {{user_id}} in response, got: {data!r}")
    return int(data["user_id"])


def _household_id(data: object) -> int:
    if not isinstance(data, dict) or "household_id" not in data:
        raise ValueError(f"Expected {{household_id}} in response, got: {data!r}")
    return int(data["household_id"])


def _compatible_query(ingredient_ids: list[int], user_id: int) -> str:
    params: list[tuple[str, str]] = [
        ("ingredient_ids", str(i)) for i in ingredient_ids
    ]
    params.append(("user_id", str(user_id)))
    return "/recipes/get_compatible?" + urllib.parse.urlencode(params)


def flow1(ts: str) -> int:
    """Flow 1: Sarah — allergy + compatible recipes."""
    print("\n" + "=" * 60)
    print("FLOW 1 — Sarah (nut allergy + compatible recipes)")
    print("=" * 60)

    _step("Health check", "GET", "/")

    status, data = _step(
        "Create Sarah",
        "POST",
        "/users/create",
        {
            "first_name": "Sarah",
            "last_name": "Smith",
            "email": f"sarah-{ts}@example.com",
        },
    )
    if status != 201:
        sys.exit(f"Flow 1 failed at create user (status {status})")
    sarah = _user_id(data)

    _step(
        "Add peanut allergy (ingredient 42)",
        "POST",
        "/users/add_allergy",
        {"user_id": sarah, "ingredient_id": 42},
    )

    for iid in (1, 2, 3):
        _step(
            f"Save pantry ingredient {iid}",
            "POST",
            "/ingredients/save",
            {
                "user_id": sarah,
                "ingredient_id": iid,
                "is_shared_with_household": False,
                "quantity": 2,
                "unit": "lb",
            },
        )

    _step(
        "Compatible recipes (expect recipe 1, not Peanut Chicken)",
        "GET",
        _compatible_query([1, 2, 3], sarah),
    )

    _step("Profile", "GET", f"/users/{sarah}")
    _step("List allergies", "GET", f"/users/{sarah}/allergies")

    return sarah


def flow2(ts: str) -> tuple[int, int]:
    """Flow 2: Mark & Leo — household + shared pantry."""
    print("\n" + "=" * 60)
    print("FLOW 2 — Mark & Leo (household + shared pantry)")
    print("=" * 60)

    status, data = _step(
        "Create Mark",
        "POST",
        "/users/create",
        {"first_name": "Mark", "email": f"mark-{ts}@example.com"},
    )
    if status != 201:
        sys.exit(f"Flow 2 failed at create Mark (status {status})")
    mark = _user_id(data)

    status, data = _step(
        "Create household",
        "POST",
        "/households/create",
        {"user_id": mark, "household_name": "The Bachelor Pad"},
    )
    if status != 201:
        sys.exit(f"Flow 2 failed at create household (status {status})")
    hh = _household_id(data)

    status, data = _step(
        "Create Leo",
        "POST",
        "/users/create",
        {"first_name": "Leo", "email": f"leo-{ts}@example.com"},
    )
    if status != 201:
        sys.exit(f"Flow 2 failed at create Leo (status {status})")
    leo = _user_id(data)

    _step(
        "Leo joins household",
        "POST",
        "/households/join",
        {"household_id": hh, "user_id": leo},
    )

    _step(
        "Mark saves eggs (shared)",
        "POST",
        "/ingredients/save",
        {
            "user_id": mark,
            "ingredient_id": 9,
            "is_shared_with_household": True,
            "quantity": 6,
            "unit": "each",
        },
    )

    _step(
        "Leo saves spinach (shared)",
        "POST",
        "/ingredients/save",
        {
            "user_id": leo,
            "ingredient_id": 10,
            "is_shared_with_household": True,
            "quantity": 1,
            "unit": "bunch",
        },
    )

    _step("Mark pantry (includes Leo shared items)", "GET", f"/pantry/get_ingredients?user_id={mark}")

    _step(
        "Compatible recipes for eggs + spinach",
        "GET",
        _compatible_query([9, 10], mark),
    )

    return mark, hh


def flow3(ts: str) -> int:
    """Flow 3: David — pantry tidy-up."""
    print("\n" + "=" * 60)
    print("FLOW 3 — David (pantry tidy-up)")
    print("=" * 60)

    status, data = _step(
        "Create David",
        "POST",
        "/users/create",
        {"first_name": "David", "email": f"david-{ts}@example.com"},
    )
    if status != 201:
        sys.exit(f"Flow 3 failed at create David (status {status})")
    david = _user_id(data)

    _step(
        "Save rice",
        "POST",
        "/ingredients/save",
        {"user_id": david, "ingredient_id": 2, "quantity": 1, "unit": "cup"},
    )

    _step(
        "Save garlic",
        "POST",
        "/ingredients/save",
        {"user_id": david, "ingredient_id": 5, "quantity": 2, "unit": "clove"},
    )

    _step("Pantry before deletes", "GET", f"/pantry/get_ingredients?user_id={david}")

    _step("Remove rice (DELETE)", "DELETE", f"/ingredients/2?user_id={david}")

    _step(
        "Remove garlic (deprecated POST)",
        "POST",
        "/ingredients/delete",
        {"user_id": david, "ingredient_id": 5},
    )

    _step(
        "Add basil",
        "POST",
        "/ingredients/save",
        {"user_id": david, "ingredient_id": 8, "quantity": 1, "unit": "bunch"},
    )

    _step(
        "Add tomato",
        "POST",
        "/ingredients/save",
        {"user_id": david, "ingredient_id": 7, "quantity": 4, "unit": "each"},
    )

    _step(
        "Compatible recipes (tomato + basil)",
        "GET",
        _compatible_query([7, 8], david),
    )

    return david


def v4_hard_endpoints(
    sarah: int,
    mark: int,
    hh: int,
    ts: str,
) -> int:
    """V4 complex endpoints: top-recipes, shopping-list, consume."""
    print("\n" + "=" * 60)
    print("V4 HARD ENDPOINTS")
    print("=" * 60)

    _step(
        "top-recipes — Sarah (partial coverage, allergy exclusion)",
        "GET",
        f"/users/{sarah}/top-recipes?limit=5",
    )

    _step(
        "top-recipes — Mark (includes shared household pantry)",
        "GET",
        f"/users/{mark}/top-recipes?limit=5",
    )

    _step(
        "shopping-list — recipe 4 before stocking Mark pantry",
        "GET",
        f"/households/{hh}/shopping-list?recipe_id=4&user_id={mark}",
    )

    for iid in (2, 5, 6, 7, 8):
        _step(
            f"Stock Mark pantry for recipe 4 — ingredient {iid}",
            "POST",
            "/ingredients/save",
            {
                "user_id": mark,
                "ingredient_id": iid,
                "is_shared_with_household": True,
                "quantity": 10,
                "unit": "unit",
            },
        )

    _step(
        "shopping-list — recipe 4 after stocking (higher coverage)",
        "GET",
        f"/households/{hh}/shopping-list?recipe_id=4&user_id={mark}",
    )

    status, _ = _step(
        "consume recipe 1 — Sarah (expect 200, SERIALIZABLE + row locks)",
        "POST",
        "/recipes/1/consume",
        {"user_id": sarah},
    )
    if status == 200:
        print("  -> consume succeeded")
    elif status == 409:
        print("  -> 409 (pantry short — OK if Sarah already consumed in a prior run)")

    status, data = _step(
        "Create empty user (no pantry)",
        "POST",
        "/users/create",
        {"first_name": "Empty", "email": f"empty-{ts}@example.com"},
    )
    if status != 201:
        sys.exit(f"V4 failed at create empty user (status {status})")
    empty = _user_id(data)

    _step(
        "consume recipe 1 — empty user (expect 409 missing/insufficient pantry)",
        "POST",
        "/recipes/1/consume",
        {"user_id": empty},
    )

    return empty


def main() -> None:
    ts = str(int(time.time()))
    print(f"Base URL: {BASE_URI}")
    print(f"Run id (email suffix): {ts}")

    sarah = flow1(ts)
    mark, hh = flow2(ts)
    david = flow3(ts)
    empty = v4_hard_endpoints(sarah, mark, hh, ts)

    print("\n" + "=" * 60)
    print("SUMMARY — IDs from this run")
    print("=" * 60)
    print(f"  SARAH (Flow 1):     user_id={sarah}")
    print(f"  MARK  (Flow 2):     user_id={mark}")
    print(f"  HH    (Flow 2):     household_id={hh}")
    print(f"  DAVID (Flow 3):     user_id={david}")
    print(f"  EMPTY (V4 consume): user_id={empty}")
    print("\nDone.")


if __name__ == "__main__":
    main()
