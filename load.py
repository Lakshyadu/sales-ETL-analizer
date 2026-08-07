"""
load.py
-------
Load layer: writes the transformed star schema into a SQLite warehouse.
Uses a full-refresh strategy inside a single transaction so the warehouse
is never left in a half-written state if something fails midway.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


def load(tables: dict[str, pd.DataFrame], db_path: str | Path, chunksize: int = 5000) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")

    with engine.begin() as conn:
        for name, df in tables.items():
            df.to_sql(name, conn, if_exists="replace", index=False, chunksize=chunksize)
            logger.info("Loaded %d rows into table '%s'", len(df), name)

        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_fact_customer ON fact_sales(customer_key)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_fact_product ON fact_sales(product_key)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_fact_date ON fact_sales(date_key)"
        ))

    logger.info("Load complete. Warehouse written to %s", db_path)
