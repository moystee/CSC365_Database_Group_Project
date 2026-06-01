#!/usr/bin/env python3
"""Run edge-case API calls from live_demo.md against Render / Supabase.

Self-contained: creates fresh users for this run, then exercises 404 / 409 /
403 / idempotent 200s and deprecated routes.

Usage:
    python scripts/run_live_edge_cases.py

Set BASE_URI below (same as run_live_demo_flows.py).
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


def _step(
    label: str,
    method: str,
    path: str,
    body: dict | None = None,
    *,
    expect: int | tuple[int, ...] | None = None,
) -> tuple[int, object]:
    print(f"\n--- {label} ---")
    if expect is not None:
        exp = (expect,) if isinstance(expect, int) else expect
        print(f"(expect HTTP {', '.join(map(str, exp))})")
    print(f"{method} {path}")
    status, data = _request(method, path, body)
    print(f"Status: {status}")
    print(json.dumps(data, indent=2) if isinstance(data, (dict, list)) else data)
    if expect is not None:
        exp_set = (expect,) if isinstance(expect, int) else expect
        if status not in exp_set:
            print(f"  !! unexpected status (wanted {exp_set})", file=sys.stderr)
    return status, data


def _user_id(data: object) -> int:
    if not isinstance(data, dict) or "user_id" not in data:
        raise ValueError(f"Expected {{user_id}} in response, got: {data!r}")
    return int(data["user_id"])


def _household_id(data: object) -> int:
    if not isinstance(data, dict) or "household_id" not in data:
        raise ValueError(f"Expected {{household_id}} in response, got: {data!r}")
    return int(data["household_id"])


def _setup_fixtures(ts: str) -> dict[str, int | str]:
    """Minimal state for edge cases (matches live_demo.md prerequisites)."""
    print("\n" + "=" * 60)
    print("SETUP — fixture users for this run")
    print("=" * 60)

    email_sarah = f"edge-sarah-{ts}@example.com"

    status, data = _step(
        "Create Sarah",
        "POST",
        "/users/create",
        {
            "first_name": "Sarah",
            "email": email_sarah,
        },
        expect=201,
    )
    if status != 201:
        sys.exit("Setup failed: create Sarah")
    sarah = _user_id(data)

    _step(
        "Sarah — peanut allergy",
        "POST",
        "/users/add_allergy",
        {"user_id": sarah, "ingredient_id": 42},
        expect=200,
    )

    _step(
        "Sarah — save chicken to pantry",
        "POST",
        "/ingredients/save",
        {"user_id": sarah, "ingredient_id": 1, "quantity": 1, "unit": "lb"},
        expect=200,
    )

    status, data = _step(
        "Create Mark",
        "POST",
        "/users/create",
        {"first_name": "Mark", "email": f"edge-mark-{ts}@example.com"},
        expect=201,
    )
    mark = _user_id(data)

    status, data = _step(
        "Mark — create household",
        "POST",
        "/households/create",
        {"user_id": mark, "household_name": "Edge Case Pad"},
        expect=201,
    )
    hh = _household_id(data)

    status, data = _step(
        "Create Leo",
        "POST",
        "/users/create",
        {"first_name": "Leo", "email": f"edge-leo-{ts}@example.com"},
        expect=201,
    )
    leo = _user_id(data)

    _step(
        "Leo — join household",
        "POST",
        "/households/join",
        {"household_id": hh, "user_id": leo},
        expect=200,
    )

    status, data = _step(
        "Create David (not in Mark's household)",
        "POST",
        "/users/create",
        {"first_name": "David", "email": f"edge-david-{ts}@example.com"},
        expect=201,
    )
    david = _user_id(data)

    status, data = _step(
        "Create Alt (for second household)",
        "POST",
        "/users/create",
        {"first_name": "Alt", "email": f"edge-alt-{ts}@example.com"},
        expect=201,
    )
    alt = _user_id(data)

    status, data = _step(
        "Alt — create other household",
        "POST",
        "/households/create",
        {"user_id": alt, "household_name": "Other Home"},
        expect=201,
    )
    other_hh = _household_id(data)

    return {
        "ts": ts,
        "email_sarah": email_sarah,
        "sarah": sarah,
        "mark": mark,
        "leo": leo,
        "david": david,
        "hh": hh,
        "other_hh": other_hh,
    }


def run_edge_cases(fix: dict[str, int | str]) -> None:
    sarah = int(fix["sarah"])
    mark = int(fix["mark"])
    leo = int(fix["leo"])
    david = int(fix["david"])
    hh = int(fix["hh"])
    other_hh = int(fix["other_hh"])
    email_sarah = str(fix["email_sarah"])
    ts = str(fix["ts"])

    print("\n" + "=" * 60)
    print("404 — NOT FOUND")
    print("=" * 60)

    _step("Unknown user", "GET", "/users/999999", expect=404)

    _step(
        "Delete pantry item David does not have",
        "DELETE",
        f"/ingredients/1?user_id={david}",
        expect=404,
    )

    _step(
        "Remove allergy Sarah does not have (ingredient 999)",
        "DELETE",
        f"/users/{sarah}/allergies/999",
        expect=404,
    )

    print("\n" + "=" * 60)
    print("409 — BUSINESS RULE CONFLICTS")
    print("=" * 60)

    _step(
        "Duplicate email signup",
        "POST",
        "/users/create",
        {"first_name": "Sarah", "email": email_sarah},
        expect=409,
    )

    _step(
        "Mark create second household (already in one)",
        "POST",
        "/households/create",
        {"user_id": mark, "household_name": "Second Home"},
        expect=409,
    )

    _step(
        "Leo join second household (one household per user)",
        "POST",
        "/households/join",
        {"household_id": other_hh, "user_id": leo},
        expect=409,
    )

    status, data = _step(
        "Create empty user (no pantry)",
        "POST",
        "/users/create",
        {"first_name": "Empty", "email": f"edge-empty-{ts}@example.com"},
        expect=201,
    )
    empty = _user_id(data)

    _step(
        "Consume recipe 1 — no pantry stock",
        "POST",
        "/recipes/1/consume",
        {"user_id": empty},
        expect=409,
    )

    print("\n" + "=" * 60)
    print("403 — NOT A HOUSEHOLD MEMBER")
    print("=" * 60)

    _step(
        "David requests Mark's household shopping-list",
        "GET",
        f"/households/{hh}/shopping-list?recipe_id=4&user_id={david}",
        expect=403,
    )

    print("\n" + "=" * 60)
    print("200 — IDEMPOTENT / SOFT SUCCESS")
    print("=" * 60)

    _step(
        "Duplicate allergy (already on file)",
        "POST",
        "/users/add_allergy",
        {"user_id": sarah, "ingredient_id": 42},
        expect=200,
    )

    _step(
        "Leo join same household again",
        "POST",
        "/households/join",
        {"household_id": hh, "user_id": leo},
        expect=200,
    )

    print("\n" + "=" * 60)
    print("DEPRECATED ROUTES (still 200)")
    print("=" * 60)

    _step(
        "POST /users/get_allergies",
        "POST",
        "/users/get_allergies",
        {"user_id": sarah},
        expect=200,
    )

    _step(
        "GET /ingredients/get_all_ingredients",
        "GET",
        "/ingredients/get_all_ingredients",
        expect=200,
    )

    print("\n" + "=" * 60)
    print("EXTRA — PANTRY DELETE TWICE")
    print("=" * 60)

    status, data = _step(
        "Throwaway user for double-delete",
        "POST",
        "/users/create",
        {"first_name": "Tmp", "email": f"edge-tmp-{ts}@example.com"},
        expect=201,
    )
    tmp = _user_id(data)

    _step(
        "Save then remove ingredient 2",
        "POST",
        "/ingredients/save",
        {"user_id": tmp, "ingredient_id": 2, "quantity": 1, "unit": "cup"},
        expect=200,
    )

    _step(
        "First DELETE ingredient 2",
        "DELETE",
        f"/ingredients/2?user_id={tmp}",
        expect=200,
    )

    _step(
        "Second DELETE ingredient 2 (not in pantry)",
        "DELETE",
        f"/ingredients/2?user_id={tmp}",
        expect=404,
    )

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  SARAH:    user_id={sarah}")
    print(f"  MARK:     user_id={mark}")
    print(f"  LEO:      user_id={leo}")
    print(f"  DAVID:    user_id={david}")
    print(f"  HH:       household_id={hh}")
    print(f"  OTHER_HH: household_id={other_hh}")
    print(f"  EMPTY:    user_id={empty}")
    print(f"  TMP:      user_id={tmp}")
    print("\nDone.")


def main() -> None:
    ts = str(int(time.time()))
    print(f"Base URL: {BASE_URI}")
    print(f"Run id: {ts}")

    fix = _setup_fixtures(ts)
    run_edge_cases(fix)


if __name__ == "__main__":
    main()
