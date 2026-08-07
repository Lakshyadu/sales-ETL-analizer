"""
extract.py
----------
Extraction layer of the ETL pipeline.

Pulls raw order-line data from a remote CSV endpoint (simulating a source
system / API export). Falls back to a local cached copy if the network
call fails, and retries transient failures with exponential backoff.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """Raised when the source data cannot be retrieved at all."""


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(requests.RequestException),
)
def _download(url: str) -> bytes:
    logger.info("Downloading source file from %s", url)
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return response.content


def extract(source_url: str, local_fallback: str | Path) -> pd.DataFrame:
    """
    Extract raw sales data.

    Tries the remote source first (with retries on transient network
    errors). If that fails outright, falls back to the last known-good
    local snapshot so the pipeline can still run offline.
    """
    local_fallback = Path(local_fallback)

    try:
        raw_bytes = _download(source_url)
        local_fallback.parent.mkdir(parents=True, exist_ok=True)
        local_fallback.write_bytes(raw_bytes)
        logger.info("Source download succeeded, cached snapshot updated at %s", local_fallback)
    except requests.RequestException as exc:
        logger.warning("Remote extraction failed (%s). Falling back to local snapshot.", exc)
        if not local_fallback.exists():
            raise ExtractionError(
                f"No cached snapshot available at {local_fallback} and remote fetch failed"
            ) from exc

    df = pd.read_csv(local_fallback)
    logger.info("Extracted %d raw rows, %d columns", len(df), df.shape[1])
    return df
