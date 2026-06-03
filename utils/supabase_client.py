"""
Supabase query helper for live order data.

Pulls today's (and recent) orders from the Supabase `orders` table that
the webhook receiver writes to. Returns rows in the JSONL-compatible
schema so performance_data.py can mix historical (JSONL) and live data
seamlessly.

Configuration:
  - On Streamlit Cloud: add SUPABASE_URL + SUPABASE_SERVICE_KEY to the
    app's secrets via Manage app → Settings → Secrets.
  - Locally: set as environment variables, or create
    .streamlit/secrets.toml with the two keys.

If either secret is missing, supabase_enabled() returns False and the
dashboard falls back to JSONL-only mode.
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Optional

import httpx
import pandas as pd
import streamlit as st


def _read_secret(name: str) -> Optional[str]:
    """Read from st.secrets first, then env. Returns None if not found."""
    try:
        val = st.secrets[name]
        if val:
            return str(val)
    except (KeyError, FileNotFoundError, AttributeError, Exception):
        pass
    return os.getenv(name)


def supabase_enabled() -> bool:
    return bool(_read_secret("SUPABASE_URL") and _read_secret("SUPABASE_SERVICE_KEY"))


# Module-level diagnostic state — set by every call to load_orders_from_supabase
_LAST_STATUS: dict = {
    "tried": False,
    "url_present": False,
    "key_present": False,
    "http_status": None,
    "raw_row_count": 0,
    "after_filter_count": 0,
    "error": None,
    "dates_returned": [],
    "is_test_breakdown": {},
}


@st.cache_data(ttl=120, show_spinner=False)
def load_orders_from_supabase(since: Optional[date] = None) -> pd.DataFrame:
    """
    Load fulfilled orders from Supabase since the given date (default: 2 days ago).
    Records diagnostic info to _LAST_STATUS for the Home-page debug panel.
    """
    global _LAST_STATUS
    _LAST_STATUS = {
        "tried": True,
        "url_present": False,
        "key_present": False,
        "http_status": None,
        "raw_row_count": 0,
        "after_filter_count": 0,
        "error": None,
        "dates_returned": [],
        "is_test_breakdown": {},
        "since": None,
    }

    url = _read_secret("SUPABASE_URL")
    key = _read_secret("SUPABASE_SERVICE_KEY")
    _LAST_STATUS["url_present"] = bool(url)
    _LAST_STATUS["key_present"] = bool(key)

    if not url or not key:
        _LAST_STATUS["error"] = "Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in secrets/env"
        return pd.DataFrame()

    if since is None:
        since = date.today() - timedelta(days=2)
    _LAST_STATUS["since"] = since.isoformat()

    cols = ",".join([
        "platform", "platform_order_id", "business_date",
        "canonical_brand", "canonical_channel",
        "gross_revenue", "net_sales", "promo_total_discount",
        "is_fulfilled", "is_test_order", "canonical_status",
    ])
    api_url = f"{url.rstrip('/')}/rest/v1/orders"
    params = {
        "select": cols,
        "business_date": f"gte.{since.isoformat()}",
        "limit": 10000,
    }
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    try:
        with httpx.Client(timeout=15) as client:
            r = client.get(api_url, params=params, headers=headers)
        _LAST_STATUS["http_status"] = r.status_code
        if r.status_code >= 400:
            _LAST_STATUS["error"] = f"HTTP {r.status_code}: {r.text[:200]}"
            return pd.DataFrame()
        rows = r.json()
    except (httpx.HTTPError, ValueError) as e:
        _LAST_STATUS["error"] = f"Request error: {e}"
        return pd.DataFrame()

    _LAST_STATUS["raw_row_count"] = len(rows) if isinstance(rows, list) else 0

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # Diagnostics: breakdown by is_test_order and is_fulfilled
    if "is_test_order" in df.columns:
        _LAST_STATUS["is_test_breakdown"] = {
            "test_true": int((df["is_test_order"] == True).sum()),
            "test_false": int((df["is_test_order"] == False).sum()),
        }
    if "is_fulfilled" in df.columns:
        _LAST_STATUS["is_test_breakdown"]["fulfilled_true"] = int((df["is_fulfilled"] == True).sum())
        _LAST_STATUS["is_test_breakdown"]["fulfilled_false"] = int((df["is_fulfilled"] == False).sum())
    if "business_date" in df.columns:
        _LAST_STATUS["dates_returned"] = sorted(set(str(d) for d in df["business_date"].dropna()))

    # Rename Supabase columns → JSONL schema
    df = df.rename(columns={
        "canonical_brand": "brand",
        "canonical_channel": "channel",
        "gross_revenue": "order_gross",
        "promo_total_discount": "order_discount",
        "net_sales": "order_net",
        "business_date": "biz_date",
        "is_fulfilled": "fulfilled",
        "canonical_status": "status",
    })

    # Compose order_key
    df["order_key"] = "D:" + df["platform_order_id"].astype(str)
    df["source"] = "Supabase (live)"

    for col in ("order_gross", "order_discount", "order_net"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "biz_date" in df.columns:
        df["biz_date"] = pd.to_datetime(df["biz_date"], errors="coerce").dt.date
    df = df[df["biz_date"].notna()]

    # Apply fulfilled + non-test filters
    if "fulfilled" in df.columns:
        df = df[df["fulfilled"] == True]  # noqa: E712
    if "is_test_order" in df.columns:
        df = df[df["is_test_order"] != True]  # noqa: E712

    df = df.reset_index(drop=True)
    _LAST_STATUS["after_filter_count"] = len(df)

    return df


def supabase_health() -> dict:
    """Returns whatever the last query learned, plus current config check."""
    # Trigger a query if we haven't yet
    if not _LAST_STATUS.get("tried"):
        load_orders_from_supabase()
    return {
        "enabled": bool(_read_secret("SUPABASE_URL") and _read_secret("SUPABASE_SERVICE_KEY")),
        **_LAST_STATUS,
    }
