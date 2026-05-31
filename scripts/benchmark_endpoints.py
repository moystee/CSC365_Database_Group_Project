#!/usr/bin/env python3
"""Time every API endpoint against a running local server.

Terminal 1:
    POSTGRES_URI=postgresql+psycopg2://localhost/foodgraph_perf uvicorn src.server:app

Terminal 2:
    python scripts/benchmark_endpoints.py

Requires scripts/benchmark_config.json from seed_perf_data.py.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000"
RUNS = 5


@dataclass
class Case:
    method: str
    path: str
    body: dict | None = None


def load_config() -> dict:
    path = ROOT / "scripts" / "benchmark_config.json"
    if not path.exists():
        sys.exit(
            f"Missing {path}. Run `python scripts/seed_perf_data.py` first."
        )
    return json.loads(path.read_text())


def build_cases(cfg: dict) -> list[Case]:
    uid = cfg["user_id"]
    hid = cfg["household_id"]
    rid = cfg["recipe_id"]
    ids = cfg["ingredient_ids"]
    allergen = cfg["allergen_ingredient_id"]
    q = "&".join(f"ingredient_ids={i}" for i in ids)

    return [
        Case("GET", "/"),
        Case("GET", f"/users/{uid}"),
        Case("GET", f"/users/{uid}/allergies"),
        Case("GET", f"/users/{uid}/top-recipes?limit=5"),
        Case("GET", f"/pantry/get_ingredients?user_id={uid}"),
        Case("GET", f"/ingredients"),
        Case("GET", f"/recipes?limit=50"),
        Case("GET", f"/recipes/get_compatible?{q}&user_id={uid}"),
        Case(
            "GET",
            f"/households/{hid}/shopping-list?recipe_id={rid}&user_id={uid}",
        ),
        Case("POST", "/users/add_allergy", {"user_id": uid, "ingredient_id": allergen}),
        Case(
            "POST",
            "/ingredients/save",
            {
                "user_id": uid,
                "ingredient_id": ids[0],
                "is_shared_with_household": True,
                "quantity": 2,
                "unit": "kg",
            },
        ),
        Case("POST", f"/recipes/{rid}/consume", {"user_id": uid}),
    ]


def request_once(method: str, path: str, body: dict | None) -> tuple[int, float]:
    url = BASE + path
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        exc.read()
        status = exc.code
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return status, elapsed_ms


def benchmark(case: Case) -> dict:
    # Warm-up
    request_once(case.method, case.path, case.body)
    times: list[float] = []
    status = 0
    for _ in range(RUNS):
        status, ms = request_once(case.method, case.path, case.body)
        times.append(ms)
    return {
        "method": case.method,
        "path": case.path.split("?")[0],
        "status": status,
        "median_ms": round(statistics.median(times), 1),
        "min_ms": round(min(times), 1),
        "max_ms": round(max(times), 1),
    }


def main() -> None:
    cfg = load_config()
    cases = build_cases(cfg)
    log_lines = [
        f"Benchmarking {BASE} ({RUNS} runs each, median reported)\n",
        f"{'Method':<6} {'Path':<45} {'Status':>6} {'Median ms':>10}",
        "-" * 72,
    ]
    results = []
    for case in cases:
        row = benchmark(case)
        results.append(row)
        log_lines.append(
            f"{row['method']:<6} {row['path']:<45} {row['status']:>6} {row['median_ms']:>10.1f}"
        )

    slowest = max(results, key=lambda r: r["median_ms"])
    log_lines.append("-" * 72)
    log_lines.append(
        f"\nSlowest: {slowest['method']} {slowest['path']} ({slowest['median_ms']} ms median)"
    )

    out = ROOT / "scripts" / "benchmark_results.json"
    out.write_text(json.dumps(results, indent=2) + "\n")
    log_lines.append(f"\nWrote {out}")

    print("\n".join(log_lines))


if __name__ == "__main__":
    main()
