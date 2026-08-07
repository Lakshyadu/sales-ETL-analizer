"""
pipeline.py
-----------
Orchestrates the full ETL run: extract -> transform -> quality gate ->
load -> report. Run directly:

    python -m src.pipeline --config config.yaml
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.extract import extract, ExtractionError
from src.transform import transform
from src.data_quality import run_checks, DataQualityError
from src.load import load
from src.report import generate_reports


def setup_logging(logs_dir: str) -> None:
    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(Path(logs_dir) / "pipeline.log"),
        ],
    )


def run(config_path: str) -> None:
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    setup_logging(cfg["paths"]["logs_dir"])
    logger = logging.getLogger("pipeline")
    start = time.time()
    logger.info("=== Starting pipeline run: %s ===", cfg["pipeline"]["name"])

    try:
        raw_df = extract(cfg["source"]["url"], cfg["source"]["local_fallback"])
        tables = transform(raw_df)
        run_checks(
            tables,
            min_row_count=cfg["quality_checks"]["min_row_count"],
            max_null_fraction=cfg["quality_checks"]["max_null_fraction"],
        )
        load(tables, cfg["paths"]["warehouse_db"], chunksize=cfg["load"]["chunksize"])
        generate_reports(cfg["paths"]["warehouse_db"], cfg["paths"]["reports_dir"])
    except (ExtractionError, DataQualityError) as exc:
        logger.error("Pipeline failed: %s", exc)
        sys.exit(1)

    elapsed = time.time() - start
    logger.info("=== Pipeline run completed successfully in %.2fs ===", elapsed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()
    run(args.config)
