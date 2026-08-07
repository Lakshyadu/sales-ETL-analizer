"""
report.py
---------
Generates a couple of simple analytical outputs from the warehouse to
prove the pipeline supports downstream BI consumption: monthly revenue
trend and top products by revenue.
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sqlalchemy import create_engine

logger = logging.getLogger(__name__)


def generate_reports(db_path: str | Path, reports_dir: str | Path) -> None:
    db_path = Path(db_path)
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")

    monthly_revenue = pd.read_sql(
        """
        SELECT d.year, d.month, ROUND(SUM(f.LineTotal), 2) AS revenue
        FROM fact_sales f
        JOIN dim_date d ON f.date_key = d.date_key
        GROUP BY d.year, d.month
        ORDER BY d.year, d.month
        """,
        engine,
    )
    monthly_revenue.to_csv(reports_dir / "monthly_revenue.csv", index=False)

    top_products = pd.read_sql(
        """
        SELECT p.product_name, ROUND(SUM(f.LineTotal), 2) AS revenue, SUM(f.Quantity) AS units_sold
        FROM fact_sales f
        JOIN dim_product p ON f.product_key = p.product_key
        GROUP BY p.product_name
        ORDER BY revenue DESC
        LIMIT 10
        """,
        engine,
    )
    top_products.to_csv(reports_dir / "top_products.csv", index=False)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    x_labels = monthly_revenue["year"].astype(str) + "-" + monthly_revenue["month"].astype(str).str.zfill(2)
    ax.plot(x_labels, monthly_revenue["revenue"], marker="o")
    ax.set_title("Monthly Revenue")
    ax.set_ylabel("Revenue ($)")
    ax.tick_params(axis="x", rotation=60)
    fig.tight_layout()
    fig.savefig(reports_dir / "monthly_revenue.png", dpi=120)
    plt.close(fig)

    logger.info("Reports written to %s", reports_dir)
