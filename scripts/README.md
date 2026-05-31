# V5 performance scripts

## 1. Local Postgres

```bash
createdb foodgraph_perf

cp .env.example .env
# edit .env:
# POSTGRES_URI=postgresql+psycopg2://localhost/foodgraph_perf

alembic upgrade head
```

## 2. Generate ~1M rows

```bash
python scripts/seed_perf_data.py
```

Takes several minutes. Refuses to run if `POSTGRES_URI` looks like Supabase.

Outputs:

- Row counts printed to the terminal
- `scripts/benchmark_config.json` — IDs for benchmarking (user 50000, etc.)

## 3. Start the API (separate terminal)

```bash
uvicorn src.server:app --reload
```

## 4. Benchmark all endpoints

```bash
python scripts/benchmark_endpoints.py
```

Outputs median ms per endpoint to the terminal and `scripts/benchmark_results.json`.

## 5. EXPLAIN the slowest query

Copy the SQL from the slow handler into `psql`:

```sql
EXPLAIN (ANALYZE, BUFFERS) <query>;
```

Add indexes, `ANALYZE`, re-run benchmark, paste results into `performance_writeup.md`.
