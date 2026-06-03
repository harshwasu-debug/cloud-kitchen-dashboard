"""
Performance — This Month.

MTD + month-end projection. Adds W1+W2 vs W3+W4 rhythm split.
"""
import calendar
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.performance_data import (
    BRAND_VIEW_MODES,
    DAY_INFLECTION_ORDERS,
    KEETA_CONCENTRATION_WARN,
    MONTH_NET_TIERS,
    MONTH_ORDERS_TIERS,
    aggregate_by_channel,
    all_brands,
    brand_view,
    data_freshness,
    day_fraction,
    delta_pct,
    fmt_aed,
    fmt_int,
    fmt_pct,
    latest_date,
    latest_order_time_today,
    load_orders,
    now_dubai,
    project_period_end,
    should_project,
    signed_pct,
    slice_range,
    total_kpis,
    verdict_for,
)


st.set_page_config(page_title="This Month · Performance", page_icon="🗓️", layout="wide")
st.markdown("# 🗓️ This Month")
st.caption("Month-to-date + month-end projection. W1+W2 vs W3+W4 rhythm split.")


df = load_orders()
if df.empty:
    st.error("No order data available.")
    st.stop()


latest = latest_date(df)
min_d = df["biz_date"].min()
selected = st.date_input(
    "Through (any day in the month)",
    value=latest,
    min_value=min_d,
    max_value=latest,
)

days_stale = (date.today() - latest).days
if days_stale > 0:
    st.info(f"📅 Latest data is from **{latest.strftime('%a, %d %b %Y')}** ({days_stale} day(s) ago).")

month_start = selected.replace(day=1)
days_in_month = calendar.monthrange(selected.year, selected.month)[1]
days_so_far = (selected - month_start).days + 1

month_slice = slice_range(df, month_start, selected)
mtd = total_kpis(month_slice)


# ---------------------------------------------------------------------------
# Last month — same MTD window + full month for projection baseline
# ---------------------------------------------------------------------------
prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
prev_month_days = calendar.monthrange(prev_month_start.year, prev_month_start.month)[1]
prev_month_end = prev_month_start.replace(day=prev_month_days)

prev_same_point = prev_month_start + timedelta(days=days_so_far - 1)
prev_same_point = min(prev_same_point, prev_month_end)

last_month_mtd_slice = slice_range(df, prev_month_start, prev_same_point)
last_month_mtd = total_kpis(last_month_mtd_slice)

last_month_full_slice = slice_range(df, prev_month_start, prev_month_end)
last_month_full = total_kpis(last_month_full_slice)

typical_daily = {
    k: last_month_full[k] / prev_month_days if prev_month_days else 0
    for k in ("orders", "net", "gross", "discount")
}

# Fractional days_so_far if today is partial
today_dubai = now_dubai().date()
if selected == today_dubai and should_project(selected):
    latest_in_data = latest_order_time_today(df, selected)
    today_frac = day_fraction(latest_in_data) if latest_in_data else day_fraction(now_dubai())
    effective_days_so_far = (days_so_far - 1) + today_frac
else:
    effective_days_so_far = float(days_so_far)

projected = project_period_end(mtd, effective_days_so_far, days_in_month, typical_daily)


# ---------------------------------------------------------------------------
# Headline
# ---------------------------------------------------------------------------
st.markdown(
    f"### {selected.strftime('%B %Y')} — MTD through {selected.strftime('%a %d %b')}  "
    f"({days_so_far} of {days_in_month} days)"
)

v_net = verdict_for(mtd["net"], MONTH_NET_TIERS)
v_ord = verdict_for(mtd["orders"], MONTH_ORDERS_TIERS)

c1, c2, c3 = st.columns(3)
with c1:
    st.metric(
        "MTD Net Sales",
        fmt_aed(mtd["net"]),
        delta=signed_pct(delta_pct(mtd["net"], last_month_mtd["net"])) + " vs same point last month",
    )
    st.markdown(f"#### {v_net.emoji} {v_net.tier} pace")
with c2:
    st.metric(
        "MTD Orders",
        fmt_int(mtd["orders"]),
        delta=signed_pct(delta_pct(mtd["orders"], last_month_mtd["orders"])) + " vs same point last month",
    )
    st.markdown(f"#### {v_ord.emoji} {v_ord.tier} pace")
with c3:
    daily_avg = mtd["orders"] / days_so_far if days_so_far else 0
    st.metric(
        "Daily avg orders",
        f"{daily_avg:.0f}",
        delta=f"inflection at {DAY_INFLECTION_ORDERS}",
        delta_color="off",
    )


# ---------------------------------------------------------------------------
# Month-end projection
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("### Projected month-end landing")

v_net_proj = verdict_for(projected["net"], MONTH_NET_TIERS)
v_ord_proj = verdict_for(projected["orders"], MONTH_ORDERS_TIERS)

p1, p2, p3 = st.columns(3)
with p1:
    st.metric(
        "Projected Net Sales",
        fmt_aed(projected["net"]),
        delta=signed_pct(delta_pct(projected["net"], last_month_full["net"])) + " vs last month",
    )
    st.markdown(f"#### {v_net_proj.emoji} {v_net_proj.tier}")
with p2:
    st.metric(
        "Projected Orders",
        fmt_int(projected["orders"]),
        delta=signed_pct(delta_pct(projected["orders"], last_month_full["orders"])) + " vs last month",
    )
    st.markdown(f"#### {v_ord_proj.emoji} {v_ord_proj.tier}")
with p3:
    projected_avg = projected["orders"] / days_in_month
    if projected_avg >= DAY_INFLECTION_ORDERS:
        st.success(f"✅ Projecting above inflection ({projected_avg:.0f}/day vs {DAY_INFLECTION_ORDERS})")
    else:
        st.error(f"🔴 Projecting below inflection ({projected_avg:.0f}/day vs {DAY_INFLECTION_ORDERS})")


# ---------------------------------------------------------------------------
# W1+W2 vs W3+W4 rhythm
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("### Month rhythm — W1+W2 vs W3+W4")

halfway = days_in_month // 2
first_half_end = month_start + timedelta(days=halfway - 1)
second_half_start = month_start + timedelta(days=halfway)

first_half = slice_range(df, month_start, min(first_half_end, selected))
second_half = (
    slice_range(df, second_half_start, selected) if second_half_start <= selected else pd.DataFrame(columns=df.columns)
)

fh_k = total_kpis(first_half)
sh_k = total_kpis(second_half)

mc1, mc2 = st.columns(2)
with mc1:
    st.markdown("**W1 + W2** (first half)")
    st.markdown(f"- Orders: **{fh_k['orders']:,}**")
    st.markdown(f"- Net Sales: **{fmt_aed(fh_k['net'])}**")
    st.markdown(f"- Discount: **{fmt_pct(fh_k['discount_rate'])}**")
with mc2:
    st.markdown("**W3 + W4** (second half so far)")
    if sh_k["orders"] == 0:
        st.caption("(month not past halfway yet)")
    else:
        st.markdown(f"- Orders: **{sh_k['orders']:,}**")
        st.markdown(f"- Net Sales: **{fmt_aed(sh_k['net'])}**")
        st.markdown(f"- Discount: **{fmt_pct(sh_k['discount_rate'])}**")
        fh_dr = fh_k["orders"] / halfway if halfway else 0
        sh_days = (selected - second_half_start).days + 1
        sh_dr = sh_k["orders"] / sh_days if sh_days else 0
        if sh_dr > fh_dr * 1.05:
            st.success(f"📈 Second half stronger ({sh_dr:.0f}/day vs {fh_dr:.0f}/day)")
        elif sh_dr < fh_dr * 0.95:
            st.warning(f"📉 Second half weaker ({sh_dr:.0f}/day vs {fh_dr:.0f}/day)")
        else:
            st.info(f"➡️ Roughly even ({sh_dr:.0f}/day vs {fh_dr:.0f}/day)")


# ---------------------------------------------------------------------------
# Brand view
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("### Brands this month")

bv_mode = st.radio(
    "View", BRAND_VIEW_MODES, horizontal=True, label_visibility="collapsed",
    key="month_bv_mode",
)
single_brand = None
if bv_mode == "Single brand":
    single_brand = st.selectbox("Brand", all_brands(df), key="month_single_brand")

bv_df = brand_view(month_slice, bv_mode, single_brand)
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
        )
        st.bar_chart(bv_df[["cuisine", "net"]].set_index("cuisine"), height=260)
    else:
        st.dataframe(bv_df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("### Channels this month")
ch = aggregate_by_channel(month_slice)
if not ch.empty:
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
# Trend — last 3 full months + this MTD
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("### Last 3 months + this MTD")

trend_rows = []
m = month_start
for _ in range(3):
    m = (m - timedelta(days=1)).replace(day=1)
    m_end_d = calendar.monthrange(m.year, m.month)[1]
    m_end = m.replace(day=m_end_d)
    if m < min_d:
        break
    k = total_kpis(slice_range(df, m, m_end))
    trend_rows.append({"label": m.strftime("%b %Y"), "net_sales": k["net"], "orders": k["orders"]})

trend_rows.reverse()
trend_rows.append({"label": f"{selected.strftime('%b')} MTD", "net_sales": mtd["net"], "orders": mtd["orders"]})
trend_df = pd.DataFrame(trend_rows).set_index("label")

tc1, tc2 = st.columns(2)
with tc1:
    st.markdown("**Net Sales**")
    st.bar_chart(trend_df[["net_sales"]], height=240)
with tc2:
    st.markdown("**Orders**")
    st.bar_chart(trend_df[["orders"]], height=240)


fresh = data_freshness()
if fresh:
    st.caption(
        f"Data range: {fresh['min_date']} to {fresh['max_date']} · "
        f"{fresh['total_orders']:,} total fulfilled orders"
    )
