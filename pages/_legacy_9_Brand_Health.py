"""
Brand Health — performance, trend, and sunset tracker for all 35+ brands.

Surfaces which brands are pulling weight, which are coasting, and which
should be sunset. Eliminates the need for ad-hoc brand-concentration
queries.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from utils.data_loader import (
    load_sales_orders, load_cancelled_orders, add_cuisine_column,
)

st.set_page_config(page_title="Brand Health", page_icon="🩺", layout="wide")

# ─── THEME ────────────────────────────────────────────────────────────────────
PRIMARY  = "#FF6B35"
GREEN    = "#2A9D8F"
YELLOW   = "#E9C46A"
RED      = "#E63946"
TEMPLATE = "plotly_white"

# Thresholds (orders per day, last 14d)
THRESHOLD_HEALTHY = 5.0
THRESHOLD_REVIEW  = 2.0
THRESHOLD_SUNSET  = 1.0

# Locked unit economics from analysis
COMMISSION_RATE = 0.30   # % of net food
COGS_RATE       = 0.15   # % of gross
DELIVERY_CHARGE = 4.00   # AED per order on Talabat+Keeta only
DELIVERY_SHARE  = 0.658  # 65.8% of orders are Talabat+Keeta

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def biz_date(t):
    if pd.isna(t): return None
    if t.hour < 3: return (t - pd.Timedelta(days=1)).date()
    return t.date()

# ─── LOAD ─────────────────────────────────────────────────────────────────────
with st.spinner("Loading data…"):
    df = load_sales_orders()
df = add_cuisine_column(df, "Brand")

df["_pickup"] = df["Pickup Time"].fillna(df["Received At"])
df["_biz_date"] = df["_pickup"].apply(biz_date)
df["_biz_date"] = pd.to_datetime(df["_biz_date"], errors="coerce")

max_date = df["_biz_date"].max()
window_14 = df[df["_biz_date"] >= max_date - pd.Timedelta(days=14)]
window_28 = df[(df["_biz_date"] >= max_date - pd.Timedelta(days=28)) &
                (df["_biz_date"] < max_date - pd.Timedelta(days=14))]
n_days_14 = window_14["_biz_date"].nunique()
n_days_28 = window_28["_biz_date"].nunique()

# ─── HEADER ───────────────────────────────────────────────────────────────────
st.title("🩺 Brand Health")
st.caption(
    f"Analysis window: last {n_days_14} days "
    f"({(max_date - pd.Timedelta(days=14)).date()} → {max_date.date()}) "
    f"vs prior {n_days_28} days ({(max_date - pd.Timedelta(days=28)).date()} → {(max_date - pd.Timedelta(days=14)).date()})"
)

# ─── COMPUTE PER-BRAND METRICS ────────────────────────────────────────────────
def brand_stats(window, n_days):
    if n_days == 0:
        return pd.DataFrame()
    g = window.groupby("Brand").agg(
        orders=("Brand", "count"),
        gross=("Item Price", "sum"),
        discount=("Discount", "sum"),
    ).reset_index()
    g["orders_per_day"] = g["orders"] / n_days
    g["aov_gross"] = (g["gross"] / g["orders"]).round(1)
    g["disc_rate"] = (g["discount"] / g["gross"] * 100).round(1)
    g["net_food_aov"] = g["aov_gross"] - (g["discount"] / g["orders"]).round(1)
    return g

cur = brand_stats(window_14, n_days_14)
prev = brand_stats(window_28, n_days_28)
brand_cuisine = window_14.groupby("Brand")["Cuisine"].first().to_dict()

# Merge for trend
df_brand = cur.merge(
    prev[["Brand", "orders_per_day"]].rename(columns={"orders_per_day": "prior_per_day"}),
    on="Brand", how="left",
).fillna({"prior_per_day": 0})
df_brand["trend_pct"] = ((df_brand["orders_per_day"] - df_brand["prior_per_day"]) /
                          df_brand["prior_per_day"].replace(0, float("nan")) * 100).round(1)
df_brand["Cuisine"] = df_brand["Brand"].map(brand_cuisine).fillna("Unknown")

# Per-order contribution (weighted delivery charge)
df_brand["commission_per_order"] = (df_brand["net_food_aov"] * COMMISSION_RATE).round(2)
df_brand["cogs_per_order"] = (df_brand["aov_gross"] * COGS_RATE).round(2)
df_brand["delivery_per_order"] = DELIVERY_CHARGE * DELIVERY_SHARE
df_brand["contribution_per_order"] = (
    df_brand["net_food_aov"] - df_brand["commission_per_order"]
    - df_brand["cogs_per_order"] - df_brand["delivery_per_order"]
).round(2)
df_brand["weekly_contribution"] = (df_brand["contribution_per_order"] * df_brand["orders_per_day"] * 7).round(0)

# Status flag
def status_flag(opd):
    if opd >= THRESHOLD_HEALTHY: return "🟢 Healthy"
    if opd >= THRESHOLD_REVIEW:  return "🟡 Review"
    if opd >= THRESHOLD_SUNSET:  return "🟠 At risk"
    return "🔴 Sunset"

df_brand["Status"] = df_brand["orders_per_day"].apply(status_flag)

# Sort
df_brand = df_brand.sort_values("orders_per_day", ascending=False)

# ─── PORTFOLIO SUMMARY ────────────────────────────────────────────────────────
st.markdown("### Portfolio at a glance")
c1, c2, c3, c4, c5 = st.columns(5)
total_brands = len(df_brand)
healthy = (df_brand["orders_per_day"] >= THRESHOLD_HEALTHY).sum()
review = ((df_brand["orders_per_day"] >= THRESHOLD_REVIEW) & (df_brand["orders_per_day"] < THRESHOLD_HEALTHY)).sum()
at_risk = ((df_brand["orders_per_day"] >= THRESHOLD_SUNSET) & (df_brand["orders_per_day"] < THRESHOLD_REVIEW)).sum()
sunset = (df_brand["orders_per_day"] < THRESHOLD_SUNSET).sum()

with c1: st.metric("Total brands selling", total_brands)
with c2: st.metric("🟢 Healthy (≥5/day)", int(healthy))
with c3: st.metric("🟡 Review (2-5/day)", int(review))
with c4: st.metric("🟠 At risk (1-2/day)", int(at_risk))
with c5: st.metric("🔴 Sunset (<1/day)", int(sunset))

# ─── PARETO ───────────────────────────────────────────────────────────────────
top10_share = df_brand.head(10)["orders"].sum() / df_brand["orders"].sum() * 100
bottom16_share = df_brand.iloc[20:]["orders"].sum() / df_brand["orders"].sum() * 100 if len(df_brand) > 20 else 0
st.caption(
    f"**Top 10 brands carry {top10_share:.0f}% of orders.** "
    f"Bottom {max(len(df_brand) - 20, 0)} brands carry {bottom16_share:.1f}%."
)

st.markdown("---")

# ─── MAIN TABLE ───────────────────────────────────────────────────────────────
st.markdown("### Brand performance (last 14 days)")

show_cols = [
    "Status", "Brand", "Cuisine",
    "orders_per_day", "trend_pct",
    "aov_gross", "net_food_aov", "disc_rate",
    "contribution_per_order", "weekly_contribution",
]
df_display = df_brand[show_cols].rename(columns={
    "orders_per_day": "Orders/day",
    "trend_pct": "Trend % (vs prior 14d)",
    "aov_gross": "Gross AOV",
    "net_food_aov": "Net food AOV",
    "disc_rate": "Discount %",
    "contribution_per_order": "Contribution/order (AED)",
    "weekly_contribution": "Weekly contribution (AED)",
})
df_display["Orders/day"] = df_display["Orders/day"].round(2)

st.dataframe(
    df_display,
    use_container_width=True,
    height=600,
    column_config={
        "Orders/day": st.column_config.NumberColumn(format="%.2f"),
        "Trend % (vs prior 14d)": st.column_config.NumberColumn(format="%+.1f%%"),
        "Gross AOV": st.column_config.NumberColumn(format="AED %.1f"),
        "Net food AOV": st.column_config.NumberColumn(format="AED %.1f"),
        "Discount %": st.column_config.NumberColumn(format="%.1f%%"),
        "Contribution/order (AED)": st.column_config.NumberColumn(format="AED %.2f"),
        "Weekly contribution (AED)": st.column_config.NumberColumn(format="AED %.0f"),
    },
)

st.markdown("---")

# ─── SUNSET RECOMMENDATIONS ───────────────────────────────────────────────────
sunset_brands = df_brand[df_brand["orders_per_day"] < THRESHOLD_SUNSET].copy()
if not sunset_brands.empty:
    st.markdown(f"### 🔴 Sunset candidates ({len(sunset_brands)} brands)")
    st.caption("Brands averaging less than 1 order/day. Combined volume is small but operational overhead is real.")
    sunset_show = sunset_brands[["Brand", "Cuisine", "orders_per_day", "trend_pct", "weekly_contribution"]].copy()
    sunset_show["orders_per_day"] = sunset_show["orders_per_day"].round(2)
    sunset_show.columns = ["Brand", "Cuisine", "Orders/day", "Trend %", "Weekly contribution (AED)"]
    st.dataframe(sunset_show, use_container_width=True, height=min(400, 40 + 35 * len(sunset_brands)))

    total_sunset_orders = sunset_brands["orders"].sum()
    total_sunset_contrib = sunset_brands["weekly_contribution"].sum()
    st.caption(
        f"**Combined sunset impact:** {total_sunset_orders:.0f} orders over 14 days "
        f"(~{total_sunset_orders/14:.1f}/day, ~AED {total_sunset_contrib:.0f}/week contribution). "
        f"Free up listing slots, marketing budget, and menu engineering effort."
    )

st.markdown("---")

# ─── BIGGEST MOVERS ───────────────────────────────────────────────────────────
st.markdown("### Biggest movers vs prior 14 days")
movers = df_brand[(df_brand["orders_per_day"] >= 1) | (df_brand["prior_per_day"] >= 1)].copy()
movers["abs_delta"] = (movers["orders_per_day"] - movers["prior_per_day"]) * 7  # weekly change
movers = movers.sort_values("abs_delta", ascending=False)

col_g, col_l = st.columns(2)
with col_g:
    st.markdown("#### 🟢 Top growth")
    growth = movers.head(8)[["Brand", "Cuisine", "orders_per_day", "prior_per_day", "abs_delta", "trend_pct"]].copy()
    growth["orders_per_day"] = growth["orders_per_day"].round(2)
    growth["prior_per_day"] = growth["prior_per_day"].round(2)
    growth["abs_delta"] = growth["abs_delta"].round(0)
    growth.columns = ["Brand", "Cuisine", "Now /day", "Prior /day", "Δ orders/week", "Trend %"]
    st.dataframe(growth, use_container_width=True, height=320)

with col_l:
    st.markdown("#### 🔴 Top decline")
    decline = movers.tail(8).iloc[::-1][["Brand", "Cuisine", "orders_per_day", "prior_per_day", "abs_delta", "trend_pct"]].copy()
    decline["orders_per_day"] = decline["orders_per_day"].round(2)
    decline["prior_per_day"] = decline["prior_per_day"].round(2)
    decline["abs_delta"] = decline["abs_delta"].round(0)
    decline.columns = ["Brand", "Cuisine", "Now /day", "Prior /day", "Δ orders/week", "Trend %"]
    st.dataframe(decline, use_container_width=True, height=320)

st.markdown("---")

# ─── CUISINE ROLLUP ───────────────────────────────────────────────────────────
st.markdown("### Cuisine roll-up")
cui = df_brand.groupby("Cuisine").agg(
    brands=("Brand", "count"),
    orders_per_day=("orders_per_day", "sum"),
    weekly_contribution=("weekly_contribution", "sum"),
).reset_index()
cui["per_brand_per_day"] = (cui["orders_per_day"] / cui["brands"]).round(2)
cui["orders_per_day"] = cui["orders_per_day"].round(2)
cui = cui.sort_values("orders_per_day", ascending=False)
cui.columns = ["Cuisine", "Brands", "Orders/day", "Weekly contribution (AED)", "Orders/brand/day"]

st.dataframe(
    cui,
    use_container_width=True,
    column_config={
        "Weekly contribution (AED)": st.column_config.NumberColumn(format="AED %.0f"),
    },
)
st.caption(
    "**Orders/brand/day** is the key health metric per cuisine. Below 2.0 = over-branded for that cuisine "
    "or weak product-market-fit at this location."
)

# ─── FOOTER ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    f"**Unit economics assumed:** Commission 30% of net food · COGS+packaging 15% of gross · "
    f"Aggregator delivery charge AED 4 (Talabat+Keeta only, 66% of orders). "
    f"Thresholds: 🟢 ≥5/day · 🟡 2-5/day · 🟠 1-2/day · 🔴 <1/day."
)
