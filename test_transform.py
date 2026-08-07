import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.transform import (
    clean_raw,
    build_dim_customer,
    build_dim_product,
    build_dim_date,
    build_fact_sales,
    transform,
)


@pytest.fixture
def sample_raw():
    return pd.DataFrame(
        {
            "SalesOrderNumber": ["SO1", "SO1", "SO2", "SO2"],
            "SalesOrderLineNumber": [1, 2, 1, 1],  # last row is a duplicate order/line combo below
            "OrderDate": ["2024-01-01", "2024-01-01", "2024-02-15", None],
            "CustomerName": ["Alice", "Alice", "Bob", "Bob"],
            "EmailAddress": ["alice@x.com", "alice@x.com", "bob@x.com", "bob@x.com"],
            "Item": ["Widget-100 Red, 10", "Gadget-200 Blue, 20", "Widget-100 Red, 10", "Widget-100 Red, 10"],
            "Quantity": [2, 1, 3, 3],
            "UnitPrice": [10.0, 20.0, 10.0, 10.0],
            "TaxAmount": [1.0, 2.0, 1.5, 1.5],
        }
    )


def test_clean_raw_drops_null_dates(sample_raw):
    cleaned = clean_raw(sample_raw)
    assert cleaned["OrderDate"].isnull().sum() == 0
    assert len(cleaned) == 3  # the null-date row is dropped


def test_clean_raw_computes_line_total(sample_raw):
    cleaned = clean_raw(sample_raw)
    row = cleaned.iloc[0]
    assert row["LineTotal"] == pytest.approx(row["Quantity"] * row["UnitPrice"] + row["TaxAmount"])


def test_clean_raw_missing_column_raises():
    bad_df = pd.DataFrame({"foo": [1, 2]})
    with pytest.raises(ValueError):
        clean_raw(bad_df)


def test_dim_customer_dedupes(sample_raw):
    cleaned = clean_raw(sample_raw)
    dim = build_dim_customer(cleaned)
    assert len(dim) == dim["CustomerName"].nunique()
    assert set(dim.columns) == {"customer_key", "CustomerName", "EmailAddress"}


def test_dim_product_splits_name_and_size(sample_raw):
    cleaned = clean_raw(sample_raw)
    dim = build_dim_product(cleaned)
    row = dim[dim["Item"] == "Widget-100 Red, 10"].iloc[0]
    assert row["product_name"] == "Widget-100 Red"
    assert row["size"] == "10"


def test_fact_sales_has_no_orphaned_keys(sample_raw):
    cleaned = clean_raw(sample_raw)
    dim_customer = build_dim_customer(cleaned)
    dim_product = build_dim_product(cleaned)
    dim_date = build_dim_date(cleaned)
    fact = build_fact_sales(cleaned, dim_customer, dim_product, dim_date)

    assert fact["customer_key"].isin(dim_customer["customer_key"]).all()
    assert fact["product_key"].isin(dim_product["product_key"]).all()
    assert fact["date_key"].isin(dim_date["date_key"]).all()


def test_transform_end_to_end_row_counts(sample_raw):
    tables = transform(sample_raw)
    assert len(tables["fact_sales"]) == 3
    assert len(tables["dim_customer"]) == 2
    assert len(tables["dim_product"]) == 2
