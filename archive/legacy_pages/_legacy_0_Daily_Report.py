"""
Daily Report — yesterday's performance at a glance.
What went well, what didn't, what to watch.

All figures use Deliverect-canonical framing:
- PickupTime as the timestamp
- Business day = 03:00 to 03:00 next morning (matches Deliverect dashboard)
- Includes both successful and cancelled orders for total counts
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from utils.data_loader import (
    load_sales_orders, load_cancelled_orders, add_cuisine_column,
)

st.set_page_config(page_title="Daily Report", page_icon="📋", layout="wide")

# ─── THEME ────────────────────────────────────────────────────────────────────
PRIMARY   = "#FF6B35"
SECONDARY = "#4ECDC4"
ACCENT    = "#FFE66D"
GREEN     = "#2A9D8F"
RED       = "#E63946"
TEMPLATE  = "plotly_white"

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def biz_date(t):
    """Map a timestamp to its business day (03:00→03:00 cycle)."""
    if pd.isna(t):
        return None
    if t.hour < 3:
        return (t - pd.Timedelta(days=1)).date()
    return t.date()


def fmt_aed(x):
    return f"AED {x:,.0f}"


def fmt_pct(x, digits=1):
    if pd.isna(x):
        return "—"
    return f"{x:+.{digits}f}%"


def kpi(label, value, delta=None, delta_color="normal", help_text=None):
    st.metric(label, value, delta=delta, delta_color=delta_color, help=help_text)


# ─── LOAD + PREPARE DATA ──────────────────────────────────────────────────────
with st.spinner("Loading data…"):
    df_sales = load_sales_orders()
    df_canc  = load_cancelled_orders()
df_sales = add_cuisine_column(df_sales, "Brand")

# Use Pickup Time where available (Deliverect post-cutover); fallback to Received At
df_sales["_pickup"] = df_sales["Pickup Time"].fillna(df_sales["Received At"])
df_sales["_biz_date"] = df_sales["_pickup"].apply(biz_date)
df_sales["_biz_date"] = pd.to_datetime(df_sales["_biz_date"], errors="coerce").dt.date
df_sales["_dow"] = pd.to_datetime(df_sales["_biz_date"]).dt.day_name()
df_sales["_hour"] = df_sales["_pickup"].dt.hour
df_sales["_status"] = "successful"

# Cancellations: use Pickup Time if present (Deliverect), else Date (Grubtech)
if "Pickup Time" in df_canc.columns:
    df_canc["_pickup"] = df_canc["Pickup Time"].fillna(df_canc["Date"])
else:
    df_canc["_pickup"] = df_canc["Date"]
df_canc["_biz_date"] = df_canc["_pickup"].apply(biz_date)
df_canc["_biz_date"] = pd.to_datetime(df_canc["_biz_date"], errors="coerce").dt.date
df_canc["_dow"] = pd.to_datetime(df_canc["_biz_date"]).dt.day_name()
df_canc["_hour"] = df_canc["_pickup"].dt.hour
df_canc["_status"] = "cancelled"

# ─── PICK YESTERDAY (most recent COMPLETED business day) ──────────────────────
all_dates = sorted([d for d in df_sales["_biz_date"].dropna().unique()])
if not all_dates:
    st.error("No data available.")
    st.stop()

today_dubai = pd.Timestamp.now(tz="Asia/Dubai").tz_localize(None)
today_biz = biz_date(today_dubai)

default_yesterday = all_dates[-1]
if default_yesterday == today_biz and len(all_dates) > 1:
    default_yesterday = all_dates[-2]


# ═════════════════════════════════════════════════════════════════════════════
# LIVE "TODAY" PANEL — shown if today's biz_date exists in data
# ═════════════════════════════════════════════════════════════════════════════
today_sales = df_sales[df_sales["_biz_date"] == today_biz]
today_canc  = df_canc[df_canc["_biz_date"] == today_biz]

if len(today_sales) > 0:
    st.markdown("## 🔴 Live — Today")

    # Latest pickup in our data
    latest_pickup = today_sales["_pickup"].max()
    minutes_since_open = int((latest_pickup - (pd.Timestamp(today_biz) + pd.Timedelta(hours=3))).total_seconds() / 60)
    # If now is past last pickup, show how recent the data is
    age_min = int((today_dubai - latest_pickup).total_seconds() / 60)

    current_total = len(today_sales) + len(today_canc)
    current_dow = pd.Timestamp(today_biz).day_name()
    current_dom = pd.Timestamp(today_biz).day

    # Compute historical post-cutoff tail by current biz minute
    completed = df_sales[df_sales["_biz_date"] != today_biz].copy()
    completed_c = df_canc[df_canc["_biz_date"] != today_biz].copy()
    # Combined per day totals
    completed["_biz_minute"] = ((completed["_pickup"] -
                                  pd.to_datetime(completed["_biz_date"]) - pd.Timedelta(hours=3)).dt.total_seconds() / 60).clip(lower=0)
    completed_c["_biz_minute"] = ((completed_c["_pickup"] -
                                    pd.to_datetime(completed_c["_biz_date"]) - pd.Timedelta(hours=3)).dt.total_seconds() / 60).clip(lower=0)

    # Recent 14 completed days
    recent_dates = sorted([d for d in completed["_biz_date"].dropna().unique()])[-14:]
    recent_completed = completed[completed["_biz_date"].isin(recent_dates)]
    recent_completed_c = completed_c[completed_c["_biz_date"].isin(recent_dates)]
    # Same-DOW last 4
    dow_dates = [d for d in recent_dates if pd.Timestamp(d).day_name() == current_dow][-4:]
    dow_completed = completed[completed["_biz_date"].isin(dow_dates)]
    dow_completed_c = completed_c[completed_c["_biz_date"].isin(dow_dates)]

    # Compute by-cutoff and post-cutoff for each historical day
    def agg_by_cut(s_df, c_df, cut_min, dates):
        if not dates:
            return None, None
        n = len(dates)
        # By-cutoff orders per day
        by_cut_total = (
            (s_df["_biz_minute"] < cut_min).sum() + (c_df["_biz_minute"] < cut_min).sum()
        ) / n
        total_avg = (len(s_df) + len(c_df)) / n
        post_cut = total_avg - by_cut_total
        return by_cut_total, post_cut

    by14, post14 = agg_by_cut(recent_completed, recent_completed_c, minutes_since_open, recent_dates)
    by_dow, post_dow = agg_by_cut(dow_completed, dow_completed_c, minutes_since_open, dow_dates)

    # Projection
    if post14 is not None and post14 > 0:
        proj_14 = current_total + post14
        proj_dow = current_total + post_dow if post_dow else proj_14
        proj_best = (proj_14 + proj_dow) / 2 if post_dow else proj_14
    else:
        proj_best = current_total
        proj_14 = proj_dow = None

    # Header row
    c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
    with c1:
        st.metric(
            f"Today ({current_dow}, day {current_dom})",
            f"{current_total} orders",
            delta=f"As of {latest_pickup.strftime('%H:%M') if pd.notna(latest_pickup) else 'n/a'} · data {age_min}m old",
            delta_color="off",
        )
    with c2:
        if proj_best:
            st.metric("EOD projection", f"~{proj_best:.0f}",
                      delta=f"Range {min(proj_14 or proj_best, proj_dow or proj_best):.0f}–{max(proj_14 or proj_best, proj_dow or proj_best):.0f}",
                      delta_color="off")
    with c3:
        if by_dow is not None and by_dow > 0:
            pace = (current_total - by_dow) / by_dow * 100
            st.metric(f"vs {current_dow} avg (last {len(dow_dates)})",
                      f"{pace:+.0f}%",
                      delta=f"{int(by_dow)} typical at this hour",
                      delta_color="off")
    with c4:
        cancel_today = len(today_canc)
        cancel_rate = cancel_today / current_total * 100 if current_total else 0
        st.metric("Cancellations today", f"{cancel_today}",
                  delta=f"{cancel_rate:.1f}% rate",
                  delta_color="off")

    # Pace narrative
    if proj_best and by14:
        post_orders_expected = post14
        st.caption(
            f"**Pace:** ~{post_orders_expected:.0f} more orders expected from {latest_pickup.strftime('%H:%M')} → 02:00. "
            f"Best estimate {proj_best:.0f}. "
            f"Same-DOW basis ({len(dow_dates)} samples): {proj_dow:.0f}. "
            f"Last-14-day basis: {proj_14:.0f}."
        )

    # Hourly orders chart for today
    st.markdown("##### Hour-by-hour progress")
    today_combined = pd.concat([
        today_sales[["_pickup"]].assign(_status="successful"),
        today_canc[["_pickup"]].assign(_status="cancelled"),
    ], ignore_index=True)
    today_combined["_hour"] = today_combined["_pickup"].dt.hour
    hours_order = list(range(7, 24)) + [0, 1, 2]
    by_hr = today_combined.groupby("_hour").size().reindex(hours_order, fill_value=0)
    hr_labels = [f"{h:02d}:00" for h in hours_order]
    fig = go.Figure(go.Bar(x=hr_labels, y=by_hr.values, marker_color=PRIMARY))
    fig.update_layout(template=TEMPLATE, height=220, margin=dict(l=10, r=10, t=10, b=10),
                      yaxis_title="Orders", xaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")


# ═════════════════════════════════════════════════════════════════════════════
# YESTERDAY / HISTORICAL DAILY REPORT
# ═════════════════════════════════════════════════════════════════════════════
st.title("📋 Daily Report")
left, right = st.columns([3, 1])
with left:
    yesterday = st.date_input(
        "Report date (business day, 03:00–03:00)",
        value=default_yesterday,
        min_value=all_dates[0],
        max_value=all_dates[-1],
        help="A 'business day' runs from 03:00 of the date shown to 03:00 the next morning, matching how Deliverect counts daily totals.",
    )
with right:
    st.markdown(f"<div style='padding-top:30px;'><h3>{pd.Timestamp(yesterday).strftime('%A, %b %d %Y')}</h3></div>", unsafe_allow_html=True)

dow = pd.Timestamp(yesterday).day_name()

# ─── BUILD COMPARISONS ────────────────────────────────────────────────────────
# Yesterday's data (sales + cancellations)
sales_y = df_sales[df_sales["_biz_date"] == yesterday].copy()
canc_y  = df_canc[df_canc["_biz_date"] == yesterday].copy()
total_y = len(sales_y) + len(canc_y)

# Prior 7 same-DOW days as DOW-baseline
all_dow = sorted([d for d in df_sales["_biz_date"].dropna().unique()
                  if pd.Timestamp(d).day_name() == dow and d < yesterday])
dow_baseline_dates = all_dow[-4:] if len(all_dow) >= 4 else all_dow

# Prior 7 calendar days as 7d-baseline
recent_dates = sorted([d for d in all_dates if d < yesterday])[-7:]

sales_dow = df_sales[df_sales["_biz_date"].isin(dow_baseline_dates)]
canc_dow  = df_canc[df_canc["_biz_date"].isin(dow_baseline_dates)]
sales_7   = df_sales[df_sales["_biz_date"].isin(recent_dates)]
canc_7    = df_canc[df_canc["_biz_date"].isin(recent_dates)]

# Per-day count baselines
def per_day_count(df, dates):
    if not dates:
        return 0.0
    return df.groupby("_biz_date").size().reindex(dates, fill_value=0).mean()

dow_avg_total = per_day_count(sales_dow, dow_baseline_dates) + per_day_count(canc_dow, dow_baseline_dates)
last7_avg_total = per_day_count(sales_7, recent_dates) + per_day_count(canc_7, recent_dates)

# Revenue
rev_col = "Net Sales" if "Net Sales" in sales_y.columns else "Total(Receipt Total)"
rev_y = sales_y[rev_col].sum()
rev_dow_avg = sales_dow.groupby("_biz_date")[rev_col].sum().reindex(dow_baseline_dates, fill_value=0).mean() if dow_baseline_dates else 0
aov_y = rev_y / max(len(sales_y), 1)
aov_dow_avg = (sales_dow[rev_col].sum() / max(len(sales_dow), 1)) if len(sales_dow) else 0

# Cancellation rate
canc_rate_y = (len(canc_y) / total_y * 100) if total_y else 0
canc_rate_7 = ((len(canc_7) / (len(sales_7) + len(canc_7))) * 100) if (len(sales_7) + len(canc_7)) else 0

# ─── KPI ROW ──────────────────────────────────────────────────────────────────
st.markdown("### At a glance")
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    delta = total_y - dow_avg_total
    pct = (delta / dow_avg_total * 100) if dow_avg_total else 0
    kpi("Orders", f"{total_y}", delta=f"{delta:+.0f} vs {dow}s", delta_color="normal" if delta == 0 else ("normal" if delta > 0 else "inverse"))
with c2:
    delta_rev = rev_y - rev_dow_avg
    kpi("Revenue", fmt_aed(rev_y), delta=f"{delta_rev/rev_dow_avg*100:+.1f}%" if rev_dow_avg else None)
with c3:
    aov_delta_pct = (aov_y - aov_dow_avg) / aov_dow_avg * 100 if aov_dow_avg else 0
    kpi("AOV", fmt_aed(aov_y), delta=fmt_pct(aov_delta_pct))
with c4:
    canc_delta = canc_rate_y - canc_rate_7
    kpi("Cancellation rate", f"{canc_rate_y:.1f}%",
        delta=f"{canc_delta:+.1f}pp vs 7d", delta_color="inverse" if canc_delta > 0 else "normal")
with c5:
    kpi("Cancelled orders", f"{len(canc_y)}",
        delta=f"AED {canc_y[ 'Sales Amount' ].sum():,.0f} lost" if "Sales Amount" in canc_y.columns and len(canc_y) else None,
        delta_color="off")

st.caption(f"Comparisons: vs avg of last {len(dow_baseline_dates)} {dow}s ({', '.join(str(d) for d in dow_baseline_dates) if dow_baseline_dates else 'none'}) and last 7 days for cancellation rate.")

st.markdown("---")

# ─── WHAT WENT WELL / DID NOT ─────────────────────────────────────────────────
# Brand-level deltas vs DOW baseline
def brand_deltas(sales_today, sales_baseline, baseline_n_days):
    if baseline_n_days == 0:
        return pd.DataFrame()
    today_b = sales_today.groupby("Brand").size()
    base_b = sales_baseline.groupby("Brand").size() / baseline_n_days
    cmp = pd.DataFrame({"today": today_b, "baseline_avg": base_b}).fillna(0)
    cmp["delta"] = cmp["today"] - cmp["baseline_avg"]
    cmp["pct"] = (cmp["delta"] / cmp["baseline_avg"].replace(0, float("nan"))) * 100
    return cmp.sort_values("delta", ascending=False)

brand_cmp = brand_deltas(sales_y, sales_dow, len(dow_baseline_dates))

def channel_deltas(sales_today, canc_today, sales_baseline, canc_baseline, baseline_n_days):
    if baseline_n_days == 0:
        return pd.DataFrame()
    t = pd.concat([sales_today, canc_today]).groupby("Channel").size()
    b = pd.concat([sales_baseline, canc_baseline]).groupby("Channel").size() / baseline_n_days
    cmp = pd.DataFrame({"today": t, "baseline_avg": b}).fillna(0)
    cmp["delta"] = cmp["today"] - cmp["baseline_avg"]
    cmp["pct"] = (cmp["delta"] / cmp["baseline_avg"].replace(0, float("nan"))) * 100
    return cmp.sort_values("delta", ascending=False)

ch_cmp = channel_deltas(sales_y, canc_y, sales_dow, canc_dow, len(dow_baseline_dates))

col_g, col_b = st.columns(2)
with col_g:
    st.markdown(f"### 🟢 What went well")
    bullets = []
    # Total volume vs DOW
    if total_y > dow_avg_total and dow_avg_total > 0:
        bullets.append(f"**{total_y} orders** — best {dow} in {len(dow_baseline_dates)} weeks (+{(total_y-dow_avg_total)/dow_avg_total*100:.0f}% vs avg)")
    # Top brand winners
    if not brand_cmp.empty:
        top_b = brand_cmp.head(3)
        for brand, row in top_b.iterrows():
            if row["delta"] > 0.5:
                bullets.append(f"**{brand}**: {int(row['today'])} orders ({fmt_pct(row['pct'])} vs {dow}s)")
    # Top channel winners
    if not ch_cmp.empty:
        top_ch = ch_cmp.head(2)
        for ch, row in top_ch.iterrows():
            if row["delta"] > 1:
                bullets.append(f"**{ch}**: {int(row['today'])} orders ({fmt_pct(row['pct'])} vs baseline)")
    # Revenue
    if rev_y > rev_dow_avg and rev_dow_avg > 0:
        bullets.append(f"**Revenue {fmt_aed(rev_y)}** — {fmt_pct((rev_y-rev_dow_avg)/rev_dow_avg*100)} vs {dow} avg")
    if not bullets:
        bullets = ["Below baseline today — see right column for detail."]
    for b in bullets[:6]:
        st.markdown(f"- {b}")

with col_b:
    st.markdown(f"### 🔴 What didn't go well")
    bullets = []
    # Volume miss
    if total_y < dow_avg_total and dow_avg_total > 0:
        bullets.append(f"**{total_y} orders** — {fmt_pct((total_y-dow_avg_total)/dow_avg_total*100)} vs {dow} avg")
    # Top brand losers
    if not brand_cmp.empty:
        bottom_b = brand_cmp.tail(3).iloc[::-1]
        for brand, row in bottom_b.iterrows():
            if row["delta"] < -0.5:
                bullets.append(f"**{brand}**: {int(row['today'])} orders ({fmt_pct(row['pct'])})")
    # Cancellation spike
    if canc_rate_y > canc_rate_7 + 0.5:
        bullets.append(f"**Cancellation rate {canc_rate_y:.1f}%** — {fmt_pct(canc_rate_y - canc_rate_7, 1).replace('%','pp')} vs 7d avg")
    # Brands at zero today that had volume in baseline
    if not brand_cmp.empty:
        zeroed = brand_cmp[(brand_cmp["today"] == 0) & (brand_cmp["baseline_avg"] >= 1)]
        for brand, row in zeroed.head(2).iterrows():
            bullets.append(f"🚩 **{brand}** at zero — usually {row['baseline_avg']:.1f}/day. Check listing/availability.")
    # Brand cancellations clustered
    if not canc_y.empty and "Brand" in canc_y.columns:
        clusters = canc_y.groupby("Brand").size()
        big_cluster = clusters[clusters >= 2]
        for brand, n in big_cluster.items():
            bullets.append(f"🚩 **{brand}**: {int(n)} cancellations — possible kitchen/stockout issue")
    if not bullets:
        bullets = ["No notable issues — clean day."]
    for b in bullets[:6]:
        st.markdown(f"- {b}")

st.markdown("---")

# ─── HOURLY SHAPE ─────────────────────────────────────────────────────────────
st.markdown(f"### Hourly shape vs typical {dow}")

# Build hour distribution for yesterday and DOW baseline
def hour_dist(df, n_days):
    if n_days == 0:
        return pd.Series(dtype=float)
    h = df.groupby("_hour").size() / n_days
    return h

hours_order = list(range(7, 24)) + [0, 1, 2]  # match kitchen 7am-2am window
y_hours = pd.concat([sales_y, canc_y]).groupby("_hour").size().reindex(hours_order, fill_value=0)
b_hours = pd.concat([sales_dow, canc_dow]).groupby("_hour").size()
b_hours = (b_hours / max(len(dow_baseline_dates), 1)).reindex(hours_order, fill_value=0)

hour_labels = [f"{h:02d}:00" for h in hours_order]
fig = go.Figure()
fig.add_trace(go.Bar(
    x=hour_labels, y=b_hours.values,
    name=f"{dow} avg ({len(dow_baseline_dates)} weeks)",
    marker_color="#CCCCCC", opacity=0.7,
))
fig.add_trace(go.Bar(
    x=hour_labels, y=y_hours.values,
    name=f"This {dow}",
    marker_color=PRIMARY,
))
fig.update_layout(
    template=TEMPLATE, barmode="group", height=320,
    margin=dict(l=10, r=10, t=10, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    yaxis_title="Orders", xaxis_title=None,
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ─── BRAND WINNERS / LOSERS TABLES ────────────────────────────────────────────
col_w, col_l = st.columns(2)

with col_w:
    st.markdown("### Brand winners")
    if not brand_cmp.empty:
        winners = brand_cmp[brand_cmp["delta"] > 0].head(8).copy()
        winners["today"] = winners["today"].astype(int)
        winners["baseline_avg"] = winners["baseline_avg"].round(1)
        winners["delta"] = winners["delta"].round(1)
        winners["pct"] = winners["pct"].round(1)
        winners = winners.rename(columns={
            "today": "Today",
            "baseline_avg": f"{dow} avg",
            "delta": "Δ orders",
            "pct": "Δ %",
        })
        st.dataframe(winners, use_container_width=True, height=320)
    else:
        st.info("No baseline comparison available.")

with col_l:
    st.markdown("### Brand losers")
    if not brand_cmp.empty:
        losers = brand_cmp[brand_cmp["delta"] < 0].tail(8).iloc[::-1].copy()
        losers["today"] = losers["today"].astype(int)
        losers["baseline_avg"] = losers["baseline_avg"].round(1)
        losers["delta"] = losers["delta"].round(1)
        losers["pct"] = losers["pct"].round(1)
        losers = losers.rename(columns={
            "today": "Today",
            "baseline_avg": f"{dow} avg",
            "delta": "Δ orders",
            "pct": "Δ %",
        })
        st.dataframe(losers, use_container_width=True, height=320)
    else:
        st.info("No baseline comparison available.")

# ─── CHANNEL TABLE ────────────────────────────────────────────────────────────
st.markdown("### Channel performance")
if not ch_cmp.empty:
    ch_show = ch_cmp.copy()
    ch_show["today"] = ch_show["today"].astype(int)
    ch_show["baseline_avg"] = ch_show["baseline_avg"].round(1)
    ch_show["delta"] = ch_show["delta"].round(1)
    ch_show["pct"] = ch_show["pct"].round(1)
    ch_show = ch_show.rename(columns={
        "today": "Today",
        "baseline_avg": f"{dow} avg",
        "delta": "Δ orders",
        "pct": "Δ %",
    })
    st.dataframe(ch_show, use_container_width=True)

# ─── CANCELLATION DETAILS ─────────────────────────────────────────────────────
if not canc_y.empty:
    st.markdown("### Cancellations")
    canc_show_cols = [c for c in ["Pickup Time", "Cancellation Time", "Channel", "Brand", "Sales Amount", "Reason"] if c in canc_y.columns]
    canc_display = canc_y[canc_show_cols].copy()
    if "Pickup Time" in canc_display.columns:
        canc_display = canc_display.sort_values("Pickup Time")
    elif "Cancellation Time" in canc_display.columns:
        canc_display = canc_display.sort_values("Cancellation Time")
    st.dataframe(canc_display, use_container_width=True)

# ─── FOOTER ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    f"All times Asia/Dubai. Business day {pd.Timestamp(yesterday).strftime('%Y-%m-%d')} = "
    f"03:00 to 03:00 next morning (matches Deliverect dashboard). "
    f"Comparisons use {len(dow_baseline_dates)} prior {dow}s for like-for-like."
)
