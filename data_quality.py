"""
data_quality.py
----------------
Lightweight data-quality gate that runs after transform and before load.
Fails the pipeline loudly rather than silently loading bad data.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


class DataQualityError(Exception):
    pass


def run_checks(tables: dict[str, pd.DataFrame], min_row_count: int, max_null_fraction: float) -> None:
    fact = tables["fact_sales"]

    if len(fact) < min_row_count:
        raise DataQualityError(
            f"fact_sales has {len(fact)} rows, below minimum threshold of {min_row_count}"
        )

    null_fraction = fact.isnull().mean().max()
    if null_fraction > max_null_fraction:
        raise DataQualityError(
            f"fact_sales has {null_fraction:.2%} nulls in its worst column, "
            f"exceeds allowed {max_null_fraction:.2%}"
        )

    # Referential integrity: every fact key must exist in its dimension
    checks = [
        ("customer_key", "dim_customer"),
        ("product_key", "dim_product"),
        ("date_key", "dim_date"),
    ]
    for fk, dim_name in checks:
        valid_keys = set(tables[dim_name][fk])
        orphaned = ~fact[fk].isin(valid_keys)
        if orphaned.any():
            raise DataQualityError(
                f"{orphaned.sum()} rows in fact_sales reference a {fk} missing from {dim_name}"
            )

    logger.info("Data quality checks passed: %d fact rows, 0 orphaned keys", len(fact))
