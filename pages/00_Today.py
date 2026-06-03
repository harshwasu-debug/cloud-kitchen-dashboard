"""
Performance — Today.

Latest business day's orders + projection.

Reads from utils.performance_data (which reads Combined_Orders_clean.jsonl).
All DATA_READING_RULES are applied at the data layer.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.performance_data import (
    BRAND_VIEW_MODES,
    DAY_INFLECTION_NET,
    DAY_INFLECTION_ORDERS,
    DAY_NET_TIERS,
    DAY_ORDERS_TIERS,
    KEETA_CONCENTRATION_WARN,
    aggregate_by_channel,
    all_brands,
    brand_view,
    data_freshness,
    delta_pct,
    fmt_aed,
    fmt_int,
    fmt_pct,
    latest_date,
    load_orders,
    same_weekday_history,
    signed_pct,
    slice_range,
    total_kpis,
    verdict_for,
)


st.set_page_config(page_title="Today · Performance", page_icon="📍", layout="wide")
st.markdown("# 📍 Today")
st.caption("Current pace + same-weekday context. Live to whenever the data file was last refreshed.")


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
df = load_orders()
if df.empty:
    fresh = data_freshness()
    st.error(
        "No order data available. The Combined_Orders_clean.jsonl file wasn't "
        "found at any expected path. Check:\n\n"
        "- Local: `C:\\Users\\harsh\\Desktop\\Order Data Audit\\Combined_Orders_clean.jsonl`\n"
        "- Cloud: copy the file into the repo's `data/` folder before deploying."
    )
    st.stop()


# ---------------------------------------------------------------------------
# Date picker (default: latest)
# ---------------------------------------------------------------------------
latest = latest_date(df)
min_d = df["biz_date"].min()
selected = st.date_input(
    "Business day",
    value=latest,
    min_value=min_d,
    max_value=latest,
    help="Defaults to the most recent business day in the data. Business day runs 03:00–03:00.",
)

# Data freshness banner
days_stale = (date.today() - latest).days
if days_stale > 0:
    st.info(
        f"📅 Latest data is from **{latest.strftime('%a, %d %b %Y')}** "
        f"({days_stale} day{'s' if days_stale != 1 else ''} ago). "
        f"Re-run the data builder to refresh."
    )

today_slice = slice_range(df, selected, selected)
today_k = total_kpis(today_slice)


# ---------------------------------------------------------------------------
# Same-weekday history (last 4) — context for "typical"
# ---------------------------------------------------------------------------
hist_dates = same_weekday_history(df, selected, n=4)
hist_slice = df[df["biz_date"].isin(hist_dates)]

if hist_dates:
    n_hist = len(hist_dates)
    hist_total_k = total_kpis(hist_slice)
    typical = {
        "orders": hist_total_k["orders"] / n_hist,
        "net": hist_total_k["net"] / n_hist,
        "gross": hist_total_k["gross"] / n_hist,
        "discount": hist_total_k["discount"] / n_hist,
        "aov_net": hist_total_k["aov_net"],
        "discount_rate": hist_total_k["discount_rate"],
    }
else:
    typical = {"orders": 0, "net": 0, "gross": 0, "discount": 0,
               "aov_net": 0, "discount_rate": 0}


# ---------------------------------------------------------------------------
# Headline
# ---------------------------------------------------------------------------
st.markdown(f"### {selected.strftime('%A, %d %B %Y')}")

v_net = verdict_for(today_k["net"], DAY_NET_TIERS)
v_ord = verdict_for(today_k["orders"], DAY_ORDERS_TIERS)

c1, c2, c3 = st.columns(3)
with c1:
    st.metric(
        "Net Sales",
        fmt_aed(today_k["net"]),
        delta=(signed_pct(delta_pct(today_k["net"], typical["net"])) + " vs typical") if hist_dates else None,
    )
    st.markdown(f"#### {v_net.emoji} {v_net.tier}")

with c2:
    st.metric(
        "Orders",
        fmt_int(today_k["orders"]),
        delta=(signed_pct(delta_pct(today_k["orders"], typical["orders"])) + " vs typical") if hist_dates else None,
    )
    st.markdown(f"#### {v_ord.emoji} {v_ord.tier}")

with c3:
    st.metric(
        "AOV (net)",
        fmt_aed(today_k["aov_net"]),
        delta=(signed_pct(delta_pct(today_k["aov_net"], typical["aov_net"])) + " vs typical") if hist_dates else None,
    )
    if v_net.tier != v_ord.tier:
        st.caption("⚠️ Volume and revenue tiers disagree — discount issue likely")


# ---------------------------------------------------------------------------
# Context strip
# ---------------------------------------------------------------------------
st.markdown("---")
ctx1, ctx2, ctx3 = st.columns(3)

with ctx1:
    delta_disc = today_k["discount_rate"] - typical["discount_rate"]
    st.metric(
        "Discount rate",
        fmt_pct(today_k["discount_rate"]),
        delta=(f"{delta_disc * 100:+.1f} pts vs typical" if hist_dates else None),
        delta_color="inverse",
    )

with ctx2:
    ch_today = aggregate_by_channel(today_slice)
    keeta_share = 0
    if not ch_today.empty and ch_today["net"].sum() > 0:
        row = ch_today[ch_today["channel"] == "Keeta"]
        if not row.empty:
            keeta_share = row["net"].iloc[0] / ch_today["net"].sum()
    st.metric(
        "Keeta share",
        fmt_pct(keeta_share),
        delta=("⚠️ concentration risk" if keeta_share > KEETA_CONCENTRATION_WARN else "ok"),
        delta_color="off",
    )

with ctx3:
    over_ord = today_k["orders"] >= DAY_INFLECTION_ORDERS
    over_net = today_k["net"] >= DAY_INFLECTION_NET
    if over_ord and over_net:
        st.success(f"✅ Cleared profitability inflection ({DAY_INFLECTION_ORDERS} orders / AED {DAY_INFLECTION_NET:,})")
    elif over_ord or over_net:
        st.warning(f"⚠️ Cleared one side only — target {DAY_INFLECTION_ORDERS} orders / AED {DAY_INFLECTION_NET:,}")
    else:
        st.error(f"🔴 Below inflection — target {DAY_INFLECTION_ORDERS} orders / AED {DAY_INFLECTION_NET:,}")


# ---------------------------------------------------------------------------
# Brand view (toggleable)
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("### Brands today")

bv_mode = st.radio(
    "View",
    BRAND_VIEW_MODES,
    horizontal=True,
    label_visibility="collapsed",
)
single_brand = None
if bv_mode == "Single brand":
    single_brand = st.selectbox("Brand", all_brands(df))

bv_df = brand_view(today_slice, bv_mode, single_brand)

if bv_df.empty:
    st.info("No data for this view.")
else:
    if bv_mode == "Top + Bottom 5":
        st.dataframe(
            bv_df[["brand", "orders", "net", "discount_rate", "aov_net"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "brand": "Brand",
                "orders": st.column_config.NumberColumn("Orders", format="%d"),
                "net": st.column_config.NumberColumn("Net Sales", format="AED %,.0f"),
                "discount_rate": st.column_config.NumberColumn("Disc %", format="%.1f%%"),
                "aov_net": st.column_config.NumberColumn("AOV (net)", format="AED %.1f"),
            },
        )
    elif bv_mode == "7 Cuisine clusters":
        st.dataframe(
            bv_df[["cuisine", "orders", "net", "gross"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "cuisine": "Cuisine",
                "orders": st.column_config.NumberColumn("Orders", format="%d"),
                "net": st.column_config.NumberColumn("Net Sales", format="AED %,.0f"),
                "gross": st.column_config.NumberColumn("Gross", format="AED %,.0f"),
            },
        )
        chart_df = bv_df[["cuisine", "net"]].set_index("cuisine")
        st.bar_chart(chart_df, height=260)
    else:  # Single brand
        st.dataframe(
            bv_df,
            use_container_width=True,
            hide_index=True,
        )


# ---------------------------------------------------------------------------
# Channels today
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("### Channels today")
ch = aggregate_by_channel(today_slice)
if ch.empty:
    st.info("No channel data.")
else:
    cc1, cc2 = st.columns([3, 2])
    with cc1:
        st.dataframe(
            ch[["channel", "orders", "net", "share", "discount_rate"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "channel": "Channel",
                "orders": st.column_config.NumberColumn("Orders", format="%d"),
                "net": st.column_config.NumberColumn("Net Sales", format="AED %,.0f"),
                "share": st.column_config.NumberColumn("Share", format="%.1f%%"),
                "discount_rate": st.column_config.NumberColumn("Disc %", format="%.1f%%"),
            },
        )
    with cc2:
        chart_ch = ch[["channel", "net"]].set_index("channel")
        st.bar_chart(chart_ch, height=260)


# ---------------------------------------------------------------------------
# Trend — last 4 same weekdays + today
# ---------------------------------------------------------------------------
if hist_dates:
    st.markdown("---")
    st.markdown(f"### Last 4 {selected.strftime('%A')}s + today")

    trend_rows = []
    for d in reversed(hist_dates):
        k = total_kpis(slice_range(df, d, d))
        trend_rows.append({"date": d, "net_sales": k["net"], "orders": k["orders"]})
    trend_rows.append({"date": selected, "net_sales": today_k["net"], "orders": today_k["orders"]})
    trend_df = pd.DataFrame(trend_rows).set_index("date")

    tc1, tc2 = st.columns(2)
    with tc1:
        st.markdown("**Net Sales**")
        st.line_chart(trend_df[["net_sales"]], height=240)
    with tc2:
        st.markdown("**Orders**")
        st.line_chart(trend_df[["orders"]], height=240)


# ---------------------------------------------------------------------------
# Footer — data freshness
# ---------------------------------------------------------------------------
fresh = data_freshness()
if fresh:
    st.caption(
        f"Data range: {fresh['min_date']} to {fresh['max_date']} · "
        f"{fresh['total_orders']:,} total fulfilled orders · "
        f"source: {fresh['source_path']}"
    )
