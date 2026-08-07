"""
transform.py
------------
Transformation layer: cleans the raw order-line extract and reshapes it
into a small star schema (dim_customer, dim_product, dim_date, fact_sales)
ready for analytical querying.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "SalesOrderNumber",
    "SalesOrderLineNumber",
    "OrderDate",
    "CustomerName",
    "EmailAddress",
    "Item",
    "Quantity",
    "UnitPrice",
    "TaxAmount",
]


def clean_raw(df: pd.DataFrame) -> pd.DataFrame:
    """Type-cast, dedupe, and drop structurally broken rows."""
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Source schema drift detected, missing columns: {missing}")

    df = df.copy()
    before = len(df)

    df["OrderDate"] = pd.to_datetime(df["OrderDate"], errors="coerce")
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
    df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce")
    df["TaxAmount"] = pd.to_numeric(df["TaxAmount"], errors="coerce")

    df = df.drop_duplicates(
        subset=["SalesOrderNumber", "SalesOrderLineNumber"]
    )
    df = df.dropna(subset=["OrderDate", "Quantity", "UnitPrice", "CustomerName", "Item"])

    dropped = before - len(df)
    if dropped:
        logger.warning("Dropped %d/%d rows during cleaning (nulls/duplicates)", dropped, before)

    df["LineTotal"] = (df["Quantity"] * df["UnitPrice"] + df["TaxAmount"]).round(2)
    return df.reset_index(drop=True)


def build_dim_customer(df: pd.DataFrame) -> pd.DataFrame:
    dim = (
        df[["CustomerName", "EmailAddress"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    dim.insert(0, "customer_key", dim.index + 1)
    return dim


def build_dim_product(df: pd.DataFrame) -> pd.DataFrame:
    dim = df[["Item"]].drop_duplicates().reset_index(drop=True)
    # "Mountain-100 Silver, 44" -> product name + size
    split = dim["Item"].str.rsplit(",", n=1, expand=True)
    dim["product_name"] = split[0].str.strip()
    dim["size"] = split[1].str.strip() if split.shape[1] > 1 else None
    dim.insert(0, "product_key", dim.index + 1)
    return dim[["product_key", "Item", "product_name", "size"]]


def build_dim_date(df: pd.DataFrame) -> pd.DataFrame:
    dates = df["OrderDate"].drop_duplicates().sort_values().reset_index(drop=True)
    dim = pd.DataFrame({"OrderDate": dates})
    dim.insert(0, "date_key", dim.index + 1)
    dim["year"] = dim["OrderDate"].dt.year
    dim["quarter"] = dim["OrderDate"].dt.quarter
    dim["month"] = dim["OrderDate"].dt.month
    dim["day_of_week"] = dim["OrderDate"].dt.day_name()
    return dim


def build_fact_sales(
    df: pd.DataFrame,
    dim_customer: pd.DataFrame,
    dim_product: pd.DataFrame,
    dim_date: pd.DataFrame,
) -> pd.DataFrame:
    fact = df.merge(dim_customer, on=["CustomerName", "EmailAddress"], how="left")
    fact = fact.merge(dim_product, on="Item", how="left")
    fact = fact.merge(dim_date, on="OrderDate", how="left")

    fact = fact[
        [
            "SalesOrderNumber",
            "SalesOrderLineNumber",
            "date_key",
            "customer_key",
            "product_key",
            "Quantity",
            "UnitPrice",
            "TaxAmount",
            "LineTotal",
        ]
    ]

    if fact[["date_key", "customer_key", "product_key"]].isnull().any().any():
        raise ValueError("Referential integrity check failed: unresolved dimension keys in fact table")

    return fact


def transform(raw_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    clean = clean_raw(raw_df)
    dim_customer = build_dim_customer(clean)
    dim_product = build_dim_product(clean)
    dim_date = build_dim_date(clean)
    fact_sales = build_fact_sales(clean, dim_customer, dim_product, dim_date)

    logger.info(
        "Built star schema: %d customers, %d products, %d dates, %d fact rows",
        len(dim_customer), len(dim_product), len(dim_date), len(fact_sales),
    )

    return {
        "dim_customer": dim_customer,
        "dim_product": dim_product,
        "dim_date": dim_date,
        "fact_sales": fact_sales,
    }
