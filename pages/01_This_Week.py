"""
Performance — This Week.

WTD position + week-end projection. Same shape as Today, scaled to 7 days.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.performance_data import (
    BRAND_VIEW_MODES,
    KEETA_CONCENTRATION_WARN,
    WEEK_NET_TIERS,
    WEEK_ORDERS_TIERS,
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
    project_period_end,
    signed_pct,
    slice_range,
    total_kpis,
    verdict_for,
)


st.set_page_config(page_title="This Week · Performance", page_icon="📆", layout="wide")
st.markdown("# 📆 This Week")
st.caption("Week-to-date + week-end projection. Week = Monday → Sunday.")


df = load_orders()
if df.empty:
    st.error("No order data available. Check Combined_Orders_clean.jsonl path.")
    st.stop()


latest = latest_date(df)
min_d = df["biz_date"].min()
selected = st.date_input(
    "Through (any day in the week)",
    value=latest,
    min_value=min_d,
    max_value=latest,
    help="The week containing this date is shown. Defaults to most recent day.",
)


def week_bounds(end_d: date) -> tuple[date, date]:
    """Monday → end_d (WTD). If end_d is e.g. Wednesday, range is Mon-Wed."""
    monday = end_d - timedelta(days=end_d.weekday())
    return monday, end_d


week_start, week_end = week_bounds(selected)
days_so_far = (week_end - week_start).days + 1
FULL_WEEK = 7

days_stale = (date.today() - latest).days
if days_stale > 0:
    st.info(
        f"📅 Latest data is from **{latest.strftime('%a, %d %b %Y')}** "
        f"({days_stale} day{'s' if days_stale != 1 else ''} ago)."
    )

week_slice = slice_range(df, week_start, week_end)
wtd = total_kpis(week_slice)


# ---------------------------------------------------------------------------
# Last 4 same-window (same days of prior weeks) for context
# ---------------------------------------------------------------------------
hist_kpis = []
for i in range(1, 5):
    h_end = week_start - timedelta(days=1) - timedelta(days=7 * (i - 1))
    h_start = h_end - timedelta(days=days_so_far - 1)
    if h_start >= min_d:
        hist_kpis.append(total_kpis(slice_range(df, h_start, h_end)))

if hist_kpis:
    typical_wtd = {
        "orders": sum(h["orders"] for h in hist_kpis) / len(hist_kpis),
        "net": sum(h["net"] for h in hist_kpis) / len(hist_kpis),
        "gross": sum(h["gross"] for h in hist_kpis) / len(hist_kpis),
        "discount": sum(h["discount"] for h in hist_kpis) / len(hist_kpis),
    }
    if typical_wtd["gross"]:
        typical_wtd["discount_rate"] = typical_wtd["discount"] / typical_wtd["gross"]
    else:
        typical_wtd["discount_rate"] = 0
else:
    typical_wtd = {"orders": 0, "net": 0, "gross": 0, "discount": 0, "discount_rate": 0}

# Average full-week (4 prior weeks) for projection
prior_full_weeks = []
for i in range(1, 5):
    s = week_start - timedelta(days=7 * i)
    e = s + timedelta(days=6)
    if s >= min_d:
        prior_full_weeks.append(total_kpis(slice_range(df, s, e)))

if prior_full_weeks:
    typical_daily = {
        k: sum(w[k] for w in prior_full_weeks) / (len(prior_full_weeks) * 7)
        for k in ("orders", "net", "gross", "discount")
    }
else:
    typical_daily = {"orders": 0, "net": 0, "gross": 0, "discount": 0}

projected = project_period_end(wtd, days_so_far, FULL_WEEK, typical_daily)


# ---------------------------------------------------------------------------
# Headline
# ---------------------------------------------------------------------------
st.markdown(
    f"### Week of {week_start.strftime('%a %d %b')} — {week_end.strftime('%a %d %b')}  "
    f"({days_so_far} of 7 days)"
)

v_net = verdict_for(wtd["net"], WEEK_NET_TIERS)
v_ord = verdict_for(wtd["orders"], WEEK_ORDERS_TIERS)

c1, c2, c3 = st.columns(3)
with c1:
    st.metric(
        "WTD Net Sales",
        fmt_aed(wtd["net"]),
        delta=(signed_pct(delta_pct(wtd["net"], typical_wtd["net"])) + " vs 4-wk avg") if hist_kpis else None,
    )
    st.markdown(f"#### {v_net.emoji} {v_net.tier}")

with c2:
    st.metric(
        "WTD Orders",
        fmt_int(wtd["orders"]),
        delta=(signed_pct(delta_pct(wtd["orders"], typical_wtd["orders"])) + " vs 4-wk avg") if hist_kpis else None,
    )
    st.markdown(f"#### {v_ord.emoji} {v_ord.tier}")

with c3:
    st.metric(
        "WTD Discount rate",
        fmt_pct(wtd["discount_rate"]),
        delta=(f"{(wtd['discount_rate'] - typical_wtd['discount_rate']) * 100:+.1f} pts" if hist_kpis else None),
        delta_color="inverse",
    )


# ---------------------------------------------------------------------------
# Week-end projection
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("### Projected full-week landing")

v_net_proj = verdict_for(projected["net"], WEEK_NET_TIERS)
v_ord_proj = verdict_for(projected["orders"], WEEK_ORDERS_TIERS)

p1, p2, p3 = st.columns(3)
with p1:
    st.metric("Projected Net Sales (full week)", fmt_aed(projected["net"]))
    st.markdown(f"#### {v_net_proj.emoji} {v_net_proj.tier}")
with p2:
    st.metric("Projected Orders (full week)", fmt_int(projected["orders"]))
    st.markdown(f"#### {v_ord_proj.emoji} {v_ord_proj.tier}")
with p3:
    weekend_left = days_so_far < 5
    if weekend_left:
        st.info(f"📅 Fri/Sat/Sun still to come — weekend uplift expected")
    elif days_so_far < 7:
        st.warning(f"📅 Weekend partially in WTD ({days_so_far} of 7 days)")
    else:
        st.success("📅 Full week in WTD")


# ---------------------------------------------------------------------------
# Brand view
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("### Brands this week")

bv_mode = st.radio(
    "View",
    BRAND_VIEW_MODES,
    horizontal=True,
    label_visibility="collapsed",
    key="week_bv_mode",
)
single_brand = None
if bv_mode == "Single brand":
    single_brand = st.selectbox("Brand", all_brands(df), key="week_single_brand")

bv_df = brand_view(week_slice, bv_mode, single_brand)
if not bv_df.empty:
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
        st.bar_chart(bv_df[["cuisine", "net"]].set_index("cuisine"), height=260)
    else:
        st.dataframe(bv_df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("### Channels this week")
ch = aggregate_by_channel(week_slice)
if not ch.empty:
    keeta_share = 0
    if ch["net"].sum() > 0:
        row = ch[ch["channel"] == "Keeta"]
        if not row.empty:
            keeta_share = row["net"].iloc[0] / ch["net"].sum()
    if keeta_share > KEETA_CONCENTRATION_WARN:
        st.warning(f"⚠️ Keeta is {keeta_share * 100:.1f}% of net sales this week — concentration risk")

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
        st.bar_chart(ch[["channel", "net"]].set_index("channel"), height=260)


# ---------------------------------------------------------------------------
# Trend — last 4 full weeks + this week's WTD
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("### Last 4 weeks + this week's WTD")

trend_rows = []
for i in range(4, 0, -1):
    s = week_start - timedelta(days=7 * i)
    e = s + timedelta(days=6)
    if s >= min_d:
        k = total_kpis(slice_range(df, s, e))
        trend_rows.append({"label": e.strftime("Wk %d %b"), "net_sales": k["net"], "orders": k["orders"]})
trend_rows.append({"label": "This wk WTD", "net_sales": wtd["net"], "orders": wtd["orders"]})
trend_df = pd.DataFrame(trend_rows).set_index("label")

tc1, tc2 = st.columns(2)
with tc1:
    st.markdown("**Net Sales**")
    st.line_chart(trend_df[["net_sales"]], height=240)
with tc2:
    st.markdown("**Orders**")
    st.line_chart(trend_df[["orders"]], height=240)


fresh = data_freshness()
if fresh:
    st.caption(
        f"Data range: {fresh['min_date']} to {fresh['max_date']} · "
        f"{fresh['total_orders']:,} total fulfilled orders"
    )
