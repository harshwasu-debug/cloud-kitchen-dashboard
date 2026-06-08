"""
Promo & Discount Analysis.

Live from Supabase (the only source with per-discount detail including
promo codes). Shows what discounts are costing, who's paying for them
(merchant vs aggregator), and which brands are bleeding most.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.supabase_client import (
    load_orders_full,
    load_promo_data,
    supabase_enabled,
)

st.set_page_config(page_title="Promo Analysis", page_icon="🎟️", layout="wide")
st.markdown("# 🎟️ Promo & Discount Analysis")
st.caption("Live from webhook + catch-up. Shows what discounts are costing and who's funding them.")

if not supabase_enabled():
    st.error(
        "Supabase secrets not configured. Add SUPABASE_URL + SUPABASE_SERVICE_KEY "
        "to `.streamlit/secrets.toml` (local) or Streamlit Cloud secrets panel."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Date range
# ---------------------------------------------------------------------------
col_a, col_b = st.columns([1, 3])
with col_a:
    days_back = st.selectbox(
        "Look back",
        options=[7, 14, 30, 60],
        index=2,
        format_func=lambda d: f"Last {d} days",
    )
since = date.today() - timedelta(days=days_back)

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
with st.spinner("Loading from Supabase..."):
    promos = load_promo_data(since=since)
    orders = load_orders_full(since=since)

if orders.empty:
    st.warning("No orders in window. Check Supabase connection.")
    st.stop()

# ---------------------------------------------------------------------------
# Headline KPIs
# ---------------------------------------------------------------------------
total_orders = len(orders)
total_gross = orders["gross_revenue"].sum()
total_net = orders["net_sales"].sum()
total_disc = orders["promo_total_discount"].sum()
orders_w_promo = (orders["promo_total_discount"] > 0).sum()
promo_share = (orders_w_promo / total_orders * 100) if total_orders else 0

# Merchant vs platform funded (from promos detail when available)
merchant_funded = promos["merchant_funded"].sum() if not promos.empty else total_disc
platform_funded = promos["platform_funded"].sum() if not promos.empty else 0

st.markdown("### Headline")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Orders in window", f"{total_orders:,}")
k2.metric("Orders with promo", f"{orders_w_promo:,}", f"{promo_share:.1f}%")
k3.metric("Total discount value", f"AED {total_disc:,.0f}")
k4.metric("You paid (merchant-funded)", f"AED {merchant_funded:,.0f}",
          f"-{(merchant_funded / total_gross * 100):.1f}% of gross" if total_gross else None,
          delta_color="inverse")

st.markdown("---")

# ---------------------------------------------------------------------------
# Section 1 — Top promo codes by spend
# ---------------------------------------------------------------------------
st.markdown("### 1️⃣ Top promo codes by your spend")

if promos.empty:
    st.info("No per-discount detail yet — the orders_discounts view returned no rows.")
else:
    by_code = (promos.groupby(["promo_name", "promo_provider"], dropna=False)
               .agg(uses=("promo_name", "count"),
                    your_cost=("merchant_funded", "sum"),
                    aggregator_cost=("platform_funded", "sum"),
                    total_discount=("promo_amount", "sum"))
               .reset_index()
               .sort_values("your_cost", ascending=False))
    by_code["avg_you_pay"] = (by_code["your_cost"] / by_code["uses"]).round(2)
    by_code["uses"] = by_code["uses"].astype(int)

    show = by_code.head(20).copy()
    show.columns = ["Promo name", "Provider", "Uses", "Your cost (AED)",
                    "Aggregator cost (AED)", "Total discount (AED)", "Avg you pay (AED)"]
    st.dataframe(
        show.style.format({
            "Your cost (AED)": "{:,.0f}",
            "Aggregator cost (AED)": "{:,.0f}",
            "Total discount (AED)": "{:,.0f}",
            "Avg you pay (AED)": "{:.2f}",
        }),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "**Provider** tells you who set up the promo: `restaurant` = your team, "
        "`channel` = the aggregator. `restaurant`-provider promos with high spend are "
        "the first place to look for waste."
    )

st.markdown("---")

# ---------------------------------------------------------------------------
# Section 2 — Merchant vs platform funding split (by channel)
# ---------------------------------------------------------------------------
st.markdown("### 2️⃣ Who's paying for promos — by channel")

if not promos.empty:
    by_channel = (promos.groupby("canonical_channel")
                  .agg(merchant=("merchant_funded", "sum"),
                       platform=("platform_funded", "sum"),
                       uses=("promo_name", "count"))
                  .reset_index())
    by_channel["total"] = by_channel["merchant"] + by_channel["platform"]
    by_channel["pct_you_pay"] = (by_channel["merchant"] / by_channel["total"].replace(0, 1) * 100).round(1)
    by_channel = by_channel.sort_values("merchant", ascending=False)

    show = by_channel[["canonical_channel", "uses", "merchant", "platform", "pct_you_pay"]].copy()
    show.columns = ["Channel", "Promo uses", "Your cost (AED)", "Aggregator cost (AED)", "% you pay"]
    st.dataframe(
        show.style.format({
            "Your cost (AED)": "{:,.0f}",
            "Aggregator cost (AED)": "{:,.0f}",
            "% you pay": "{:.1f}%",
        }),
        use_container_width=True,
        hide_index=True,
    )
    if (by_channel["pct_you_pay"] > 95).any():
        st.warning(
            "⚠️ Some channels show ~100% merchant-funded promos. "
            "Either they genuinely don't co-fund, or Deliverect isn't sending the "
            "channel-funded amount and we're undercounting their share."
        )

st.markdown("---")

# ---------------------------------------------------------------------------
# Section 3 — Per-brand promo bleed
# ---------------------------------------------------------------------------
st.markdown("### 3️⃣ Per-brand promo bleed")

brand_orders = (orders.groupby("canonical_brand")
                .agg(orders=("platform_order_id", "count"),
                     gross=("gross_revenue", "sum"),
                     net=("net_sales", "sum"),
                     discount=("promo_total_discount", "sum"))
                .reset_index())
brand_orders["discount_pct"] = (brand_orders["discount"] / brand_orders["gross"].replace(0, 1) * 100).round(1)
brand_orders = brand_orders.sort_values("discount", ascending=False)

show = brand_orders[["canonical_brand", "orders", "gross", "discount", "discount_pct", "net"]].copy()
show.columns = ["Brand", "Orders", "Gross (AED)", "Discount (AED)", "Discount %", "Net (AED)"]
st.dataframe(
    show.style.format({
        "Gross (AED)": "{:,.0f}",
        "Discount (AED)": "{:,.0f}",
        "Net (AED)": "{:,.0f}",
        "Discount %": "{:.1f}%",
    }).background_gradient(subset=["Discount %"], cmap="Reds"),
    use_container_width=True,
    hide_index=True,
    height=420,
)

st.markdown("---")

# ---------------------------------------------------------------------------
# Section 4 — Subscription orders (free delivery pattern)
# ---------------------------------------------------------------------------
st.markdown("### 4️⃣ Subscription-pattern orders (Keeta Plus / Talabat Pro / Careem Plus)")
st.caption(
    "Best signal we have: orders with delivery_fee = 0 on aggregators where delivery "
    "is normally charged. These are likely subscription members."
)

sub_channels = ["Talabat", "Careem", "Keeta"]
sub_candidates = orders[
    (orders["canonical_channel"].isin(sub_channels)) &
    (orders["delivery_fee"] == 0)
].copy()

sub_summary = (sub_candidates.groupby("canonical_channel")
               .agg(likely_sub_orders=("platform_order_id", "count"),
                    sub_net=("net_sales", "sum"))
               .reset_index())
all_summary = (orders[orders["canonical_channel"].isin(sub_channels)]
               .groupby("canonical_channel")
               .agg(total_orders=("platform_order_id", "count"))
               .reset_index())
sub_summary = sub_summary.merge(all_summary, on="canonical_channel")
sub_summary["pct_subscription"] = (sub_summary["likely_sub_orders"] /
                                    sub_summary["total_orders"] * 100).round(1)

show = sub_summary[["canonical_channel", "total_orders", "likely_sub_orders",
                    "pct_subscription", "sub_net"]].copy()
show.columns = ["Channel", "Total orders", "Likely sub orders", "% sub", "Net from sub (AED)"]
st.dataframe(
    show.style.format({"Net from sub (AED)": "{:,.0f}", "% sub": "{:.1f}%"}),
    use_container_width=True,
    hide_index=True,
)
st.caption(
    "Heuristic only. Deliverect doesn't flag subscription orders directly — "
    "we infer from the delivery-fee waiver pattern."
)

st.markdown("---")

# ---------------------------------------------------------------------------
# Section 5 — Promo vs no-promo basket comparison
# ---------------------------------------------------------------------------
st.markdown("### 5️⃣ Do promos drive bigger baskets?")

with_promo = orders[orders["promo_total_discount"] > 0]
no_promo = orders[orders["promo_total_discount"] == 0]

cmp = pd.DataFrame({
    "Metric": ["Order count", "Avg gross basket (AED)", "Avg net to you (AED)", "Total net (AED)"],
    "With promo": [
        len(with_promo),
        round(with_promo["gross_revenue"].mean() if len(with_promo) else 0, 2),
        round(with_promo["net_sales"].mean() if len(with_promo) else 0, 2),
        round(with_promo["net_sales"].sum(), 0),
    ],
    "No promo": [
        len(no_promo),
        round(no_promo["gross_revenue"].mean() if len(no_promo) else 0, 2),
        round(no_promo["net_sales"].mean() if len(no_promo) else 0, 2),
        round(no_promo["net_sales"].sum(), 0),
    ],
})
st.dataframe(cmp, use_container_width=True, hide_index=True)

if len(with_promo) and len(no_promo):
    gross_diff = with_promo["gross_revenue"].mean() - no_promo["gross_revenue"].mean()
    net_diff = with_promo["net_sales"].mean() - no_promo["net_sales"].mean()
    if gross_diff > 5 and net_diff < 0:
        st.info(
            f"Promo orders have **AED {gross_diff:.0f} bigger gross baskets** but net you "
            f"**AED {abs(net_diff):.0f} LESS per order**. The discount more than wipes out "
            f"the basket-size lift on average."
        )
    elif net_diff > 0:
        st.success(
            f"Promo orders net you **AED {net_diff:.0f} MORE per order on average** — "
            f"the basket-size lift exceeds the discount cost."
        )
    else:
        st.caption(f"Net difference per order: AED {net_diff:+.2f}")

st.markdown("---")
st.caption(f"Data range: last {days_back} days · live from Supabase")
