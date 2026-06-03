"""
Performance data loader.

Reads Combined_Orders_clean.jsonl (the canonical clean master from
Desktop\\Order Data Audit\\) and exposes helpers for the three
Performance pages (Today / This Week / This Month).

All DATA_READING_RULES are already applied in the JSONL:
  - Business day (Rule 3) is the biz_date column
  - Net Sales (Rule 7) is the order_net column (= order_gross - order_discount)
  - Brand & channel are normalised (Rule 9)
  - Fulfilled / cancelled is the fulfilled column (Rule 5/11)
  - One line per item; dedup on order_key for order-level analytics (Rule 12)

The 5-tier verdict scale + benchmarks are the owner-set calibration from
the live session — these live in this module so all three pages reuse them.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from utils.supabase_client import load_orders_from_supabase, supabase_enabled

# Asia/Dubai (no DST, fixed UTC+4)
DUBAI_TZ = timezone(timedelta(hours=4))


# ---------------------------------------------------------------------------
# File location — checks multiple candidates so local laptop and Streamlit
# Cloud both work. Order matters: laptop master first, then repo copy.
# ---------------------------------------------------------------------------

CANDIDATE_PATHS = [
    Path("E:/Cloud Kitchen/Order Data/Combined_Orders_clean.jsonl"),
    Path(__file__).resolve().parent.parent / "data" / "Combined_Orders_clean.jsonl",
]


def _find_master() -> Optional[Path]:
    for p in CANDIDATE_PATHS:
        if p.exists():
            return p
    return None


# ---------------------------------------------------------------------------
# Owner-set calibration — 5-tier verdict scale
# Tiers: (lower_bound_inclusive, label, emoji)
# ---------------------------------------------------------------------------

DAY_ORDERS_TIERS = [
    (215, "Exceptional", "🟢🟢"),
    (200, "Good", "🟢"),
    (180, "On-trend", "🟡"),
    (160, "Soft", "🟠"),
    (0, "Bad", "🔴"),
]
DAY_NET_TIERS = [
    (11800, "Exceptional", "🟢🟢"),
    (11000, "Good", "🟢"),
    (9900, "On-trend", "🟡"),
    (8800, "Soft", "🟠"),
    (0, "Bad", "🔴"),
]

WEEK_ORDERS_TIERS = [
    (1500, "Exceptional", "🟢🟢"),
    (1400, "Good", "🟢"),
    (1300, "On-trend", "🟡"),
    (1100, "Soft", "🟠"),
    (0, "Bad", "🔴"),
]
WEEK_NET_TIERS = [
    (80000, "Exceptional", "🟢🟢"),
    (74000, "Good", "🟢"),
    (68000, "On-trend", "🟡"),
    (60000, "Soft", "🟠"),
    (0, "Bad", "🔴"),
]

# Month tiers — derive from day tiers × 30
MONTH_ORDERS_TIERS = [(t[0] * 30, t[1], t[2]) for t in DAY_ORDERS_TIERS]
MONTH_NET_TIERS = [(t[0] * 30, t[1], t[2]) for t in DAY_NET_TIERS]

# Profitability inflection (owner-stated)
DAY_INFLECTION_ORDERS = 185
DAY_INFLECTION_NET = 10000

# Concentration risk threshold
KEETA_CONCENTRATION_WARN = 0.40


@dataclass
class Verdict:
    tier: str
    emoji: str
    threshold: int


def verdict_for(value: float, tiers: list[tuple[int, str, str]]) -> Verdict:
    for lo, label, emoji in tiers:
        if value >= lo:
            return Verdict(tier=label, emoji=emoji, threshold=lo)
    return Verdict(tier="Bad", emoji="🔴", threshold=0)


# ---------------------------------------------------------------------------
# Cuisine cluster — for the 7-clusters brand view
# ---------------------------------------------------------------------------

CUISINE_CLUSTER = {
    # Korean
    "Hungry Oppa": "Korean", "Annyeong": "Korean", "Seoul Food": "Korean",
    "Jinjja": "Korean", "Noona": "Korean", "K-Bap": "Korean",
    # Japanese
    "Oneesan": "Japanese", "Norii": "Japanese", "Hikari": "Japanese",
    # Poke
    "PokeMan": "Poke", "The Big Kahuna": "Poke", "Big Kahuna": "Poke",
    # American
    "Wings of Fury": "American", "Wings of Fire": "American",
    "Winging It": "American", "Smashville Burgers": "American",
    "Smashville": "American", "Big Dawg's Burgers": "American",
    "Big Dawg’s Burgers": "American", "Bronx Burger House": "American",
    "Juicy Buns": "American", "Slider Shack": "American",
    # Mexican
    "Mexigo": "Mexican", "Loco Taco": "Mexican", "Picante": "Mexican",
    "Fiesta": "Mexican", "Casa Del Queso": "Mexican",
    # Indian
    "Patiala Plate": "Indian", "Tandoori Tribe": "Indian",
    "The Curry Club": "Indian", "Zaika Punjab": "Indian",
    # Chinese
    "Wok Street": "Chinese", "Shanghai Spice": "Chinese",
    # Breakfast
    "Breakfast Counter": "Breakfast", "Before Noon": "Breakfast",
    "Sunrise & Co": "Breakfast", "Toast & Co": "Breakfast",
    # Healthy
    "Bowl & Soul": "Healthy", "LowCal": "Healthy", "MACROS": "Healthy",
}


# ---------------------------------------------------------------------------
# Data load (cached)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner="Loading order data...")
def load_orders_items() -> pd.DataFrame:
    """Load item-level rows from Combined_Orders_clean.jsonl.

    One row per dish-line. Order fields repeat across an order's items.
    Caller dedups on order_key for order-level metrics.
    """
    path = _find_master()
    if path is None:
        return pd.DataFrame()

    # Stream-read (file is >30MB per the data audit rules)
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Parse business date once
    df["biz_date"] = pd.to_datetime(df["biz_date"], errors="coerce").dt.date

    # Defensive: coerce numerics
    for col in ("qty", "item_gross", "item_discount", "order_gross",
                "order_discount", "order_net", "item_net_est"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df


@st.cache_data(ttl=3600)
def _load_orders_jsonl_dedup() -> pd.DataFrame:
    """Order-level from JSONL only — internal use."""
    df = load_orders_items()
    if df.empty:
        return df
    df = df[df["fulfilled"] == True].copy()  # noqa: E712
    df = df.drop_duplicates(subset=["order_key"]).reset_index(drop=True)
    return df


@st.cache_data(ttl=120)
def load_orders() -> pd.DataFrame:
    """
    Combined order-level view — UNION of JSONL historical + Supabase live.

    Both sources are unioned and deduped by order_key. JSONL is kept as the
    canonical row when an order appears in both (preserves the richer JSONL
    schema). Supabase rows only add value where they fill gaps — typically
    orders that arrived via webhook AFTER the JSONL was last built.

    Falls back to JSONL only if Supabase isn't configured or unreachable.
    """
    df_hist = _load_orders_jsonl_dedup()

    if not supabase_enabled():
        return df_hist

    df_live = load_orders_from_supabase()
    if df_live.empty:
        return df_hist
    if df_hist.empty:
        return df_live.reset_index(drop=True)

    # Align column sets — keep all columns from both; missing get NaN
    all_cols = sorted(set(df_hist.columns) | set(df_live.columns))
    for col in all_cols:
        if col not in df_hist.columns:
            df_hist[col] = None
        if col not in df_live.columns:
            df_live[col] = None

    # Union, then dedup by order_key keeping JSONL row when both have it
    df_combined = pd.concat(
        [df_hist[all_cols], df_live[all_cols]],
        ignore_index=True, sort=False,
    )
    df_combined = df_combined.drop_duplicates(subset=["order_key"], keep="first")

    return df_combined.reset_index(drop=True)


def data_freshness() -> Optional[dict]:
    """Tell the page what data we have."""
    df = load_orders()
    if df.empty:
        return None
    return {
        "min_date": df["biz_date"].min(),
        "max_date": df["biz_date"].max(),
        "total_orders": len(df),
        "total_net": float(df["order_net"].sum()),
        "source_path": str(_find_master()) if _find_master() else "missing",
    }


# ---------------------------------------------------------------------------
# Slicing helpers
# ---------------------------------------------------------------------------

def slice_range(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    return df[(df["biz_date"] >= start) & (df["biz_date"] <= end)].copy()


def latest_date(df: pd.DataFrame) -> Optional[date]:
    if df.empty:
        return None
    return df["biz_date"].max()


def same_weekday_history(df: pd.DataFrame, target: date, n: int = 4) -> list[date]:
    weekday = target.weekday()
    dates = sorted(
        {d for d in df["biz_date"].unique() if d.weekday() == weekday and d < target},
        reverse=True,
    )
    return dates[:n]


# ---------------------------------------------------------------------------
# Aggregations
# ---------------------------------------------------------------------------

def total_kpis(df: pd.DataFrame) -> dict:
    """Total KPIs across the slice. Assumes df is already order-level."""
    if df.empty:
        return {"orders": 0, "gross": 0.0, "discount": 0.0, "net": 0.0,
                "aov_gross": 0.0, "aov_net": 0.0, "discount_rate": 0.0}
    orders = len(df)
    gross = float(df["order_gross"].sum())
    discount = float(df["order_discount"].sum())
    net = float(df["order_net"].sum())
    return {
        "orders": orders,
        "gross": gross,
        "discount": discount,
        "net": net,
        "aov_gross": gross / orders if orders else 0,
        "aov_net": net / orders if orders else 0,
        "discount_rate": discount / gross if gross else 0,
    }


def aggregate_by_brand(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    g = df.groupby("brand", as_index=False).agg(
        orders=("order_key", "count"),
        gross=("order_gross", "sum"),
        discount=("order_discount", "sum"),
        net=("order_net", "sum"),
    )
    g["discount_rate"] = g.apply(
        lambda r: r["discount"] / r["gross"] if r["gross"] else 0, axis=1
    )
    g["aov_net"] = g.apply(
        lambda r: r["net"] / r["orders"] if r["orders"] else 0, axis=1
    )
    return g.sort_values("net", ascending=False).reset_index(drop=True)


def aggregate_by_channel(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    g = df.groupby("channel", as_index=False).agg(
        orders=("order_key", "count"),
        gross=("order_gross", "sum"),
        discount=("order_discount", "sum"),
        net=("order_net", "sum"),
    )
    g["discount_rate"] = g.apply(
        lambda r: r["discount"] / r["gross"] if r["gross"] else 0, axis=1
    )
    g["share"] = g["net"] / g["net"].sum() if g["net"].sum() else 0
    return g.sort_values("net", ascending=False).reset_index(drop=True)


def aggregate_by_cuisine(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    g = df.copy()
    g["cuisine"] = g["brand"].map(CUISINE_CLUSTER).fillna("Other")
    out = g.groupby("cuisine", as_index=False).agg(
        orders=("order_key", "count"),
        net=("order_net", "sum"),
        gross=("order_gross", "sum"),
    )
    return out.sort_values("net", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Brand view modes — used by all three pages
# ---------------------------------------------------------------------------

BRAND_VIEW_MODES = ["Top + Bottom 5", "7 Cuisine clusters", "Single brand"]


def brand_view(df: pd.DataFrame, mode: str, single_brand: Optional[str] = None) -> pd.DataFrame:
    if mode == "Top + Bottom 5":
        g = aggregate_by_brand(df)
        if len(g) <= 10:
            return g
        return pd.concat([g.head(5), g.tail(5)], ignore_index=True)
    if mode == "7 Cuisine clusters":
        return aggregate_by_cuisine(df)
    if mode == "Single brand":
        if not single_brand:
            return pd.DataFrame()
        return aggregate_by_brand(df[df["brand"] == single_brand])
    return pd.DataFrame()


def all_brands(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return []
    return sorted(df["brand"].dropna().unique().tolist())


# ---------------------------------------------------------------------------
# Projection — additive method per the rules doc
# ---------------------------------------------------------------------------

def project_period_end(period_to_date_kpis: dict, days_so_far: int,
                       total_days: int, typical_daily_kpis: dict) -> dict:
    """Project full-period kpis from PTD + typical daily.

    days_so_far should be a FRACTIONAL value if the current day is partial
    (e.g., 3.5 means Mon + Tue + Wed + 50% of today).
    """
    if days_so_far >= total_days:
        return period_to_date_kpis
    days_remaining = total_days - days_so_far
    out = {}
    for k in ("orders", "net", "gross", "discount"):
        actual = period_to_date_kpis.get(k, 0)
        remaining = typical_daily_kpis.get(k, 0) * days_remaining
        out[k] = actual + remaining
    out["orders"] = round(out["orders"])
    return out


# ---------------------------------------------------------------------------
# Day fraction + EOD projection (the in-day pace logic)
# ---------------------------------------------------------------------------

def now_dubai() -> datetime:
    """Current time in Asia/Dubai (UTC+4, no DST)."""
    return datetime.now(DUBAI_TZ)


def day_fraction(at_time: Optional[datetime] = None) -> float:
    """Fraction of business day elapsed (0.0 to 1.0).

    Business day runs 03:00 → 03:00 (per Rule 3). 24-hour denominator.
    Returns 0.0 for "just started" (03:00) and 1.0 for "ended" (next 03:00).
    """
    if at_time is None:
        at_time = now_dubai()
    h = at_time.hour + at_time.minute / 60.0
    # Map hours [3, 27) → [0, 24)
    bd_hours = (h - 3) if h >= 3 else (h + 21)
    return min(max(bd_hours / 24.0, 0.0), 1.0)


def project_eod_additive(actual_kpis: dict, typical_full_day_kpis: dict,
                         frac: float) -> dict:
    """Project end-of-day numbers using additive method.

    Logic: take what we've done so far + assume the rest of the day
    matches the typical pattern. Capped to avoid wild projections at
    very low fractions.
    """
    # Below 15% of the day, projection is unreliable — return typical
    if frac < 0.15:
        return {k: typical_full_day_kpis.get(k, 0) for k in ("orders", "net", "gross", "discount")}
    if frac >= 0.95:
        return actual_kpis
    out = {}
    for k in ("orders", "net", "gross", "discount"):
        actual = actual_kpis.get(k, 0)
        typical_remaining = typical_full_day_kpis.get(k, 0) * (1 - frac)
        out[k] = actual + typical_remaining
    out["orders"] = round(out["orders"])
    return out


def latest_order_time_today(df: pd.DataFrame, target_date: date) -> Optional[datetime]:
    """Return the latest order's local time for the given business date,
    or None if no orders yet. Used to compute day_fraction from data, not
    wall-clock.
    """
    if df.empty or "created_local" not in df.columns:
        return None
    today_rows = df[df["biz_date"] == target_date]
    if today_rows.empty:
        return None
    ts = pd.to_datetime(today_rows["created_local"], errors="coerce").max()
    if pd.isna(ts):
        return None
    return ts.to_pydatetime()


def should_project(selected_date: date, today_in_data: bool = True) -> bool:
    """Project only if the selected day might be incomplete.

    Returns True if selected_date is today (Dubai) or later.
    """
    if not today_in_data:
        return False
    return selected_date >= now_dubai().date()


def projection_caption(actual_kpis: dict, projected_kpis: dict, frac: float) -> str:
    """One-line summary of the projection — "on pace to land at X by EOD"."""
    if frac >= 0.95:
        return ""
    if frac < 0.15:
        return f"⏱️ Early in the day (~{frac*100:.0f}% elapsed) — projection based on typical"
    return (
        f"⏱️ At ~{frac*100:.0f}% of the business day. "
        f"On pace to land at AED {projected_kpis['net']:,.0f} / "
        f"{projected_kpis['orders']:,} orders by 3am."
    )


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------

def fmt_aed(v: float) -> str:
    return f"AED {v:,.0f}"


def fmt_pct(v: float, decimals: int = 1) -> str:
    return f"{v * 100:.{decimals}f}%"


def fmt_int(v: float) -> str:
    return f"{int(v):,}"


def delta_pct(now: float, prior: float) -> Optional[float]:
    if prior == 0:
        return None
    return (now - prior) / prior


def signed_pct(d: Optional[float]) -> str:
    if d is None:
        return "—"
    return f"{d * 100:+.1f}%"
