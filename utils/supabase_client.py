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


@st.cache_data(ttl=120, show_spinner=False)
def load_orders_from_supabase(since: Optional[date] = None) -> pd.DataFrame:
    """
    Load fulfilled orders from Supabase since the given date (default: 2 days ago).

    Returns a DataFrame in the JSONL-compatible schema:
        order_key, biz_date, channel, brand, order_gross, order_discount,
        order_net, fulfilled, status, source

    Empty DataFrame on any error (missing config, network, etc.) — caller
    can detect via .empty and fall back to JSONL.
    """
    url = _read_secret("SUPABASE_URL")
    key = _read_secret("SUPABASE_SERVICE_KEY")
    if not url or not key:
        return pd.DataFrame()

    if since is None:
        since = date.today() - timedelta(days=2)

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
        "is_test_order": "eq.false",
        "limit": 10000,
    }
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }

    try:
        with httpx.Client(timeout=15) as client:
            r = client.get(api_url, params=params, headers=headers)
        if r.status_code >= 400:
            return pd.DataFrame()
        rows = r.json()
    except (httpx.HTTPError, ValueError):
        return pd.DataFrame()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

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

    # Compose order_key (the JSONL convention)
    df["order_key"] = "D:" + df["platform_order_id"].astype(str)
    df["source"] = "Supabase (live)"

    # Coerce numerics
    for col in ("order_gross", "order_discount", "order_net"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # biz_date → date object
    if "biz_date" in df.columns:
        df["biz_date"] = pd.to_datetime(df["biz_date"], errors="coerce").dt.date

    # Drop rows with no business_date or no brand (incomplete data)
    df = df[df["biz_date"].notna()]

    # Only fulfilled, non-test
    df = df[df["fulfilled"] == True].reset_index(drop=True)  # noqa: E712

    return df


def supabase_health() -> dict:
    """For debugging / health check."""
    if not supabase_enabled():
        return {"enabled": False}
    df = load_orders_from_supabase()
    return {
        "enabled": True,
        "rows_today_window": len(df),
        "dates_covered": sorted(df["biz_date"].unique().tolist()) if not df.empty else [],
    }
