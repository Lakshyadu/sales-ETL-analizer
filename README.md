# Sales ETL Pipeline → Star Schema Warehouse

A small end-to-end batch ETL pipeline that extracts raw order-line data,
cleans and models it into a star schema, loads it into a SQL warehouse,
and generates downstream business reports — built to practice the core
data engineering workflow (extract → transform → quality-gate → load →
serve).

## Architecture

```
            ┌───────────┐      ┌─────────────┐      ┌──────────────┐      ┌────────────┐      ┌──────────┐
 CSV source │  extract  │ ───► │  transform  │ ───► │ data_quality │ ───► │    load    │ ───► │  report  │
 (HTTP, w/  │  .py      │      │  .py        │      │  .py         │      │  .py       │      │  .py     │
 retry +    └───────────┘      └─────────────┘      └──────────────┘      └────────────┘      └──────────┘
 local                                                                          │
 fallback)                                                                      ▼
                                                                          SQLite warehouse
                                                                     (star schema, indexed)
```

**Star schema:**

- `fact_sales` — one row per order line (quantity, unit price, tax, line total, FKs)
- `dim_customer` — customer name + email, surrogate key
- `dim_product` — product name/size parsed out of the raw item string, surrogate key
- `dim_date` — calendar attributes (year, quarter, month, day of week), surrogate key

## What each stage does

| Stage | File | Responsibility |
|---|---|---|
| Extract | `src/extract.py` | Downloads the raw CSV over HTTP with exponential-backoff retries (`tenacity`); falls back to the last cached snapshot if the network call fails, so the pipeline can still run offline. |
| Transform | `src/transform.py` | Type casting, deduplication, null handling, and reshaping the flat extract into the star schema above. |
| Quality gate | `src/data_quality.py` | Row-count and null-fraction thresholds, plus referential-integrity checks (every fact FK must resolve to a dimension row). Raises and halts the pipeline instead of loading bad data. |
| Load | `src/load.py` | Writes all tables into SQLite inside a single transaction (full-refresh), then builds indexes on the fact table's foreign keys. |
| Report | `src/report.py` | Runs SQL against the warehouse to produce `monthly_revenue.csv`, `top_products.csv`, and a revenue trend chart — proving the warehouse is actually queryable for BI. |
| Orchestration | `src/pipeline.py` | Wires the stages together, handles logging (console + file) and config (`config.yaml`). |

## Running it

```bash
pip install -r requirements.txt
python -m src.pipeline --config config.yaml
```

Outputs:
- `data/warehouse/sales_warehouse.db` — SQLite warehouse
- `reports/monthly_revenue.csv`, `reports/top_products.csv`, `reports/monthly_revenue.png`
- `logs/pipeline.log` — structured run log

## Tests

```bash
pytest tests/ -v
```

7 unit tests cover cleaning logic, dimension-building, and fact-table
referential integrity.

## Data source

Sample order-line data (`sales.csv`) is the publicly available
AdventureWorks-style dataset from Microsoft Learning's
[`dp-data`](https://github.com/MicrosoftLearning/dp-data) repository,
used here for learning/demo purposes.

## Possible extensions

- Swap the full-refresh load for incremental/merge loads keyed on `SalesOrderNumber`
- Containerize with Docker and schedule via Airflow/Prefect instead of a plain CLI run
- Swap SQLite for Postgres/BigQuery for a closer-to-production warehouse target
