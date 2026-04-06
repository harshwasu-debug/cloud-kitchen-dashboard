"""
Channel Analysis Page — Cloud Kitchen Analytics Dashboard
Performance breakdown by delivery channel: Deliveroo, Keeta, Careem, Talabat,
Noon Food, and others. Covers revenue, orders, AOV, trends, discounts,
cancellations, payment methods, and channel growth rates.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.data_loader import (
    load_sales_orders,
    load_cancelled_orders,
    get_all_brands,
    get_all_locations,
    get_all_channels,
    get_cuisine_for_brand,
    CUISINE_BRAND_MAP,
)

# ─── PAGE CONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Channel Analysis", page_icon="📡", layout="wide")

# ─── THEME CONSTANTS ─────────────────────────────────────────────────────────
PRIMARY   = "#FF6B35"
SECONDARY = "#4ECDC4"
ACCENT    = "#FFE66D"
TEMPLATE  = "plotly_white"
CHART_BG  = "rgba(255,255,255,0)"

PALETTE = [
    PRIMARY, SECONDARY, ACCENT,
    "#A8DADC", "#457B9D", "#E63946",
    "#F4A261", "#2A9D8F", "#E9C46A",
    "#264653", "#6D6875", "#B5838D",
]

# ─── STYLES ──────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .kpi-card {
        background: #F8F9FA;
        border-radius: 10px;
        padding: 18px 20px;
        border-left: 4px solid #FF6B35;
        margin-bottom: 8px;
    }
    .kpi-label { color: #6C757D; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; }
    .kpi-value { color: #1A1A2E; font-size: 1.75rem; font-weight: 700; margin: 4px 0 2px; }
    .kpi-sub   { color: #6C757D; font-size: 0.78rem; }
    .section-header {
        color: #FF6B35;
        font-size: 1.05rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin: 24px 0 12px;
        border-bottom: 1px solid #DEE2E6;
        padding-bottom: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─── HELPERS ─────────────────────────────────────────────────────────────────
def kpi_card(label: str, value: str, sub: str = ""):
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    st.markdown(
        f'<div class="kpi-card">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'{sub_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def section(title: str):
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)


def fmt_aed(val: float) -> str:
    try:
        if abs(val) >= 1_000_000:
            return f"AED {val/1_000_000:.2f}M"
        if abs(val) >= 1_000:
            return f"AED {val/1_000:.1f}K"
        return f"AED {val:,.0f}"
    except Exception:
        return "AED —"


def fmt_pct(val: float) -> str:
    try:
        return f"{val:.1f}%"
    except Exception:
        return "—"


def _layout(fig, height=400):
    fig.update_layout(
        template=TEMPLATE,
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        height=height,
        margin=dict(l=20, r=20, t=40, b=20),
        font=dict(size=12),
    )
    return fig


def channel_color_map(channels):
    return {ch: PALETTE[i % len(PALETTE)] for i, ch in enumerate(sorted(channels))}


# ─── LOAD DATA ───────────────────────────────────────────────────────────────
try:
    with st.spinner("Loading data for channel analysis…"):
        df_raw = load_sales_orders()
except Exception as e:
    st.error(f"Failed to load sales orders: {e}")
    st.stop()

try:
    df_cancel_raw = load_cancelled_orders()
except Exception:
    df_cancel_raw = pd.DataFrame()

if df_raw is None or df_raw.empty:
    st.info("No sales order data available.")
    st.stop()

# Ensure datetime
if "Received At" in df_raw.columns:
    df_raw["Received At"] = pd.to_datetime(df_raw["Received At"], errors="coerce")

# Ensure numeric
for _col in ["Gross Price", "Discount", "Net Sales", "VAT", "Total(Receipt Total)", "Tips"]:
    if _col in df_raw.columns:
        df_raw[_col] = pd.to_numeric(df_raw[_col], errors="coerce").fillna(0)

# Add derived columns
df_raw["Cuisine"] = df_raw["Brand"].apply(get_cuisine_for_brand)

# Ensure date-part columns exist
if "Month" not in df_raw.columns and "Received At" in df_raw.columns:
    df_raw["Month"] = df_raw["Received At"].dt.to_period("M").astype(str)
if "Day" not in df_raw.columns and "Received At" in df_raw.columns:
    df_raw["Day"] = df_raw["Received At"].dt.day_name()
if "Hour" not in df_raw.columns and "Received At" in df_raw.columns:
    df_raw["Hour"] = df_raw["Received At"].dt.hour
if "Date" not in df_raw.columns and "Received At" in df_raw.columns:
    df_raw["Date"] = df_raw["Received At"].dt.date

# ─── SIDEBAR FILTERS ─────────────────────────────────────────────────────────
st.sidebar.header("📡 Channel Analysis Filters")

# Date range
try:
    min_date = df_raw["Received At"].dropna().min().date()
    max_date = df_raw["Received At"].dropna().max().date()
except Exception:
    import datetime
    min_date = datetime.date.today()
    max_date = datetime.date.today()

date_range = st.sidebar.date_input(
    "Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

# Channel
all_channels = sorted(df_raw["Channel"].dropna().unique().tolist()) if "Channel" in df_raw.columns else []
sel_channels = st.sidebar.multiselect("Channel", options=all_channels, default=all_channels)

# Brand
all_brands = sorted(df_raw["Brand"].dropna().unique().tolist()) if "Brand" in df_raw.columns else []
sel_brands = st.sidebar.multiselect("Brand", options=all_brands, default=all_brands)

# Location
all_locations = sorted(df_raw["Location"].dropna().unique().tolist()) if "Location" in df_raw.columns else []
sel_locations = st.sidebar.multiselect("Location", options=all_locations, default=all_locations)

# Time Range
st.sidebar.markdown("**Time Range**")
from datetime import time as _time
_tc1_ch, _tc2_ch = st.sidebar.columns(2)
with _tc1_ch:
    sel_time_from_ch = st.time_input("From", value=_time(0, 0), step=1800, key="tf_ch")
with _tc2_ch:
    sel_time_to_ch = st.time_input("To", value=_time(23, 59), step=1800, key="tt_ch")

# Apply filters
df = df_raw.copy()
if len(date_range) == 2:
    start_dt, end_dt = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1]) + pd.Timedelta(days=1)
    df = df[df["Received At"].between(start_dt, end_dt, inclusive="left")]
if sel_channels:
    df = df[df["Channel"].isin(sel_channels)]
if sel_brands:
    df = df[df["Brand"].isin(sel_brands)]
if sel_locations:
    df = df[df["Location"].isin(sel_locations)]
if "Received At" in df.columns and (sel_time_from_ch != _time(0, 0) or sel_time_to_ch != _time(23, 59)):
    _t = pd.to_datetime(df["Received At"], errors="coerce").dt.time
    df = df[(_t >= sel_time_from_ch) & (_t <= sel_time_to_ch)]

if df.empty:
    st.info("No data matches the selected filters. Please adjust your filters.")
    st.stop()

# Filtered cancellations
df_cancel = pd.DataFrame()
if not df_cancel_raw.empty:
    df_cancel = df_cancel_raw.copy()
    if "Channel" in df_cancel.columns and sel_channels:
        df_cancel = df_cancel[df_cancel["Channel"].isin(sel_channels)]
    if "Brand" in df_cancel.columns and sel_brands:
        df_cancel = df_cancel[df_cancel["Brand"].isin(sel_brands)]
    if "Location" in df_cancel.columns and sel_locations:
        df_cancel = df_cancel[df_cancel["Location"].isin(sel_locations)]

cmap = channel_color_map(df["Channel"].dropna().unique())

# ─── PAGE TITLE ──────────────────────────────────────────────────────────────
st.title("📡 Channel Analysis")
st.markdown("Performance breakdown by delivery platform across all brands and locations.")

# ─── SECTION 1: KPIs ─────────────────────────────────────────────────────────
section("Key Performance Indicators")

total_orders   = df["Unique Order ID"].nunique() if "Unique Order ID" in df.columns else len(df)
total_revenue  = df["Gross Price"].sum()
aov            = total_revenue / total_orders if total_orders > 0 else 0
active_channels = df["Channel"].nunique() if "Channel" in df.columns else 0

# Top channel by revenue
ch_rev = df.groupby("Channel")["Gross Price"].sum()
top_ch_rev_name  = ch_rev.idxmax() if not ch_rev.empty else "—"
top_ch_rev_val   = ch_rev.max() if not ch_rev.empty else 0

# Channel with best AOV
if "Unique Order ID" in df.columns:
    ch_orders = df.groupby("Channel")["Unique Order ID"].nunique()
else:
    ch_orders = df.groupby("Channel").size()
ch_aov = (ch_rev / ch_orders).dropna()
best_aov_ch   = ch_aov.idxmax() if not ch_aov.empty else "—"
best_aov_val  = ch_aov.max() if not ch_aov.empty else 0

c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    kpi_card("Total Orders", f"{total_orders:,}", "unique orders")
with c2:
    kpi_card("Total Revenue", fmt_aed(total_revenue), "gross price")
with c3:
    kpi_card("AOV", fmt_aed(aov), "avg order value")
with c4:
    kpi_card("Active Channels", str(active_channels), "distinct platforms")
with c5:
    kpi_card("Top Channel (Revenue)", str(top_ch_rev_name), fmt_aed(top_ch_rev_val))
with c6:
    kpi_card("Best AOV Channel", str(best_aov_ch), fmt_aed(best_aov_val))

# ─── SECTION 2: CHANNEL PERFORMANCE TABLE ────────────────────────────────────
section("Channel Performance Summary")

if "Unique Order ID" in df.columns:
    ch_tbl_orders = df.groupby("Channel")["Unique Order ID"].nunique().rename("Orders")
else:
    ch_tbl_orders = df.groupby("Channel").size().rename("Orders")

ch_tbl_rev  = df.groupby("Channel")["Gross Price"].sum().rename("Revenue")
ch_tbl_disc = df.groupby("Channel")["Discount"].sum().rename("Discount") if "Discount" in df.columns else pd.Series(dtype=float)

ch_tbl = pd.concat([ch_tbl_orders, ch_tbl_rev], axis=1).fillna(0)
if not ch_tbl_disc.empty:
    ch_tbl = ch_tbl.join(ch_tbl_disc, how="left").fillna(0)
else:
    ch_tbl["Discount"] = 0.0

ch_tbl["AOV"] = (ch_tbl["Revenue"] / ch_tbl["Orders"].replace(0, np.nan)).fillna(0)
ch_tbl["Discount Rate %"] = (ch_tbl["Discount"] / ch_tbl["Revenue"].replace(0, np.nan) * 100).fillna(0)
total_rev_sum = ch_tbl["Revenue"].sum()
ch_tbl["Revenue Share %"] = (ch_tbl["Revenue"] / total_rev_sum * 100).fillna(0) if total_rev_sum > 0 else 0.0
ch_tbl = ch_tbl.sort_values("Revenue", ascending=False).reset_index()

display_tbl = ch_tbl.copy()
display_tbl["Revenue"]       = display_tbl["Revenue"].apply(fmt_aed)
display_tbl["AOV"]           = display_tbl["AOV"].apply(fmt_aed)
display_tbl["Discount"]      = display_tbl["Discount"].apply(fmt_aed)
display_tbl["Discount Rate %"] = display_tbl["Discount Rate %"].apply(fmt_pct)
display_tbl["Revenue Share %"] = display_tbl["Revenue Share %"].apply(fmt_pct)

st.dataframe(display_tbl, use_container_width=True, hide_index=True)

# ─── SECTION 3: REVENUE BY CHANNEL ───────────────────────────────────────────
section("Revenue by Channel")

col_l, col_r = st.columns(2)

with col_l:
    fig_hbar = px.bar(
        ch_tbl.sort_values("Revenue"),
        x="Revenue",
        y="Channel",
        orientation="h",
        title="Revenue by Channel",
        color="Channel",
        color_discrete_map=cmap,
        text="Revenue",
    )
    fig_hbar.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig_hbar = _layout(fig_hbar, height=380)
    st.plotly_chart(fig_hbar, use_container_width=True)

with col_r:
    fig_pie = px.pie(
        ch_tbl,
        names="Channel",
        values="Revenue",
        title="Revenue Share by Channel",
        color="Channel",
        color_discrete_map=cmap,
        hole=0.4,
    )
    fig_pie = _layout(fig_pie, height=380)
    st.plotly_chart(fig_pie, use_container_width=True)

# ─── SECTION 4: ORDERS BY CHANNEL ────────────────────────────────────────────
section("Orders by Channel")

col_l2, col_r2 = st.columns(2)

with col_l2:
    fig_ord_bar = px.bar(
        ch_tbl.sort_values("Orders", ascending=False),
        x="Channel",
        y="Orders",
        title="Order Count by Channel",
        color="Channel",
        color_discrete_map=cmap,
        text="Orders",
    )
    fig_ord_bar.update_traces(textposition="outside")
    fig_ord_bar = _layout(fig_ord_bar, height=380)
    st.plotly_chart(fig_ord_bar, use_container_width=True)

with col_r2:
    fig_ord_pie = px.pie(
        ch_tbl,
        names="Channel",
        values="Orders",
        title="Order Share by Channel",
        color="Channel",
        color_discrete_map=cmap,
        hole=0.4,
    )
    fig_ord_pie = _layout(fig_ord_pie, height=380)
    st.plotly_chart(fig_ord_pie, use_container_width=True)

# ─── SECTION 5: AOV BY CHANNEL ───────────────────────────────────────────────
section("Average Order Value by Channel")

overall_aov = total_revenue / total_orders if total_orders > 0 else 0
fig_aov = px.bar(
    ch_tbl.sort_values("AOV", ascending=False),
    x="Channel",
    y="AOV",
    title="AOV by Channel",
    color="Channel",
    color_discrete_map=cmap,
    text="AOV",
)
fig_aov.update_traces(texttemplate="AED %{text:,.0f}", textposition="outside")
fig_aov.add_hline(
    y=overall_aov,
    line_dash="dash",
    line_color=ACCENT,
    annotation_text=f"Overall AOV: AED {overall_aov:,.0f}",
    annotation_position="top right",
)
fig_aov = _layout(fig_aov, height=400)
st.plotly_chart(fig_aov, use_container_width=True)

# ─── SECTION 6: CHANNEL TRENDS ───────────────────────────────────────────────
section("Channel Trends Over Time")

if "Month" in df.columns:
    # Monthly revenue
    monthly_rev = (
        df.groupby(["Month", "Channel"])["Gross Price"]
        .sum()
        .reset_index()
        .rename(columns={"Gross Price": "Revenue"})
    )
    if not monthly_rev.empty:
        fig_trend_rev = px.line(
            monthly_rev.sort_values("Month"),
            x="Month",
            y="Revenue",
            color="Channel",
            title="Monthly Revenue by Channel",
            color_discrete_map=cmap,
            markers=True,
        )
        fig_trend_rev = _layout(fig_trend_rev, height=400)
        st.plotly_chart(fig_trend_rev, use_container_width=True)
    else:
        st.info("No monthly revenue trend data available.")

    # Monthly order count
    if "Unique Order ID" in df.columns:
        monthly_ord = (
            df.groupby(["Month", "Channel"])["Unique Order ID"]
            .nunique()
            .reset_index()
            .rename(columns={"Unique Order ID": "Orders"})
        )
    else:
        monthly_ord = (
            df.groupby(["Month", "Channel"])
            .size()
            .reset_index(name="Orders")
        )

    if not monthly_ord.empty:
        fig_trend_ord = px.line(
            monthly_ord.sort_values("Month"),
            x="Month",
            y="Orders",
            color="Channel",
            title="Monthly Order Count by Channel",
            color_discrete_map=cmap,
            markers=True,
        )
        fig_trend_ord = _layout(fig_trend_ord, height=400)
        st.plotly_chart(fig_trend_ord, use_container_width=True)
    else:
        st.info("No monthly order trend data available.")
else:
    st.info("Month column not available for trend analysis.")

# ─── SECTION 7: CHANNEL × CUISINE ────────────────────────────────────────────
section("Channel × Cuisine Analysis")

if "Cuisine" in df.columns:
    ch_cuis_rev = (
        df.groupby(["Channel", "Cuisine"])["Gross Price"]
        .sum()
        .reset_index()
        .rename(columns={"Gross Price": "Revenue"})
    )

    if not ch_cuis_rev.empty:
        col_a, col_b = st.columns(2)

        with col_a:
            fig_stacked = px.bar(
                ch_cuis_rev,
                x="Channel",
                y="Revenue",
                color="Cuisine",
                title="Revenue by Channel (colored by Cuisine)",
                barmode="stack",
            )
            fig_stacked = _layout(fig_stacked, height=420)
            st.plotly_chart(fig_stacked, use_container_width=True)

        with col_b:
            pivot_ch_cuis = ch_cuis_rev.pivot_table(
                index="Cuisine", columns="Channel", values="Revenue", aggfunc="sum", fill_value=0
            )
            fig_hm = px.imshow(
                pivot_ch_cuis,
                title="Channel × Cuisine Revenue Heatmap",
                color_continuous_scale="Oranges",
                aspect="auto",
            )
            fig_hm = _layout(fig_hm, height=420)
            st.plotly_chart(fig_hm, use_container_width=True)
    else:
        st.info("No channel × cuisine data available.")
else:
    st.info("Cuisine data not available.")

# ─── SECTION 8: CHANNEL × LOCATION ───────────────────────────────────────────
section("Channel × Location Revenue")

if "Location" in df.columns:
    ch_loc_rev = (
        df.groupby(["Location", "Channel"])["Gross Price"]
        .sum()
        .reset_index()
        .rename(columns={"Gross Price": "Revenue"})
    )

    if not ch_loc_rev.empty:
        fig_loc = px.bar(
            ch_loc_rev,
            x="Location",
            y="Revenue",
            color="Channel",
            barmode="group",
            title="Revenue by Location per Channel",
            color_discrete_map=cmap,
        )
        fig_loc = _layout(fig_loc, height=420)
        st.plotly_chart(fig_loc, use_container_width=True)
    else:
        st.info("No channel × location data available.")
else:
    st.info("Location data not available.")

# ─── SECTION 9: HOURLY PATTERNS ──────────────────────────────────────────────
section("Hourly Order Patterns by Channel")

if "Hour" in df.columns:
    if "Unique Order ID" in df.columns:
        hourly_ch = (
            df.groupby(["Hour", "Channel"])["Unique Order ID"]
            .nunique()
            .reset_index()
            .rename(columns={"Unique Order ID": "Orders"})
        )
    else:
        hourly_ch = (
            df.groupby(["Hour", "Channel"])
            .size()
            .reset_index(name="Orders")
        )

    if not hourly_ch.empty:
        pivot_hour = hourly_ch.pivot_table(
            index="Hour", columns="Channel", values="Orders", aggfunc="sum", fill_value=0
        )
        fig_hm_hour = px.imshow(
            pivot_hour.T,
            title="Order Count Heatmap — Hour × Channel",
            labels=dict(x="Hour of Day", y="Channel", color="Orders"),
            color_continuous_scale="OrRd",
            aspect="auto",
        )
        fig_hm_hour = _layout(fig_hm_hour, height=400)
        st.plotly_chart(fig_hm_hour, use_container_width=True)
    else:
        st.info("No hourly data available.")
else:
    st.info("Hour column not available.")

# ─── SECTION 10: DAY OF WEEK BY CHANNEL ──────────────────────────────────────
section("Day of Week by Channel")

if "Day" in df.columns:
    DOW_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    if "Unique Order ID" in df.columns:
        dow_ch = (
            df.groupby(["Day", "Channel"])["Unique Order ID"]
            .nunique()
            .reset_index()
            .rename(columns={"Unique Order ID": "Orders"})
        )
    else:
        dow_ch = (
            df.groupby(["Day", "Channel"])
            .size()
            .reset_index(name="Orders")
        )

    if not dow_ch.empty:
        dow_ch["Day"] = pd.Categorical(dow_ch["Day"], categories=DOW_ORDER, ordered=True)
        dow_ch = dow_ch.sort_values("Day")
        fig_dow = px.bar(
            dow_ch,
            x="Day",
            y="Orders",
            color="Channel",
            barmode="group",
            title="Orders by Day of Week per Channel",
            color_discrete_map=cmap,
        )
        fig_dow = _layout(fig_dow, height=420)
        st.plotly_chart(fig_dow, use_container_width=True)
    else:
        st.info("No day-of-week data available.")
else:
    st.info("Day column not available.")

# ─── SECTION 11: DISCOUNT ANALYSIS ───────────────────────────────────────────
section("Discount Analysis by Channel")

if "Discount" in df.columns:
    disc_ch = (
        df.groupby("Channel")
        .agg(Revenue=("Gross Price", "sum"), Discount=("Discount", "sum"))
        .reset_index()
    )
    disc_ch["Discount Rate %"] = (
        disc_ch["Discount"] / disc_ch["Revenue"].replace(0, np.nan) * 100
    ).fillna(0)

    if not disc_ch.empty:
        col_d1, col_d2 = st.columns(2)

        with col_d1:
            fig_dr = px.bar(
                disc_ch.sort_values("Discount Rate %", ascending=False),
                x="Channel",
                y="Discount Rate %",
                title="Discount Rate % by Channel",
                color="Channel",
                color_discrete_map=cmap,
                text="Discount Rate %",
            )
            fig_dr.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_dr = _layout(fig_dr, height=380)
            st.plotly_chart(fig_dr, use_container_width=True)

        with col_d2:
            fig_disc_abs = px.bar(
                disc_ch.sort_values("Discount", ascending=False),
                x="Channel",
                y="Discount",
                title="Total Discounts by Channel (AED)",
                color="Channel",
                color_discrete_map=cmap,
                text="Discount",
            )
            fig_disc_abs.update_traces(texttemplate="AED %{text:,.0f}", textposition="outside")
            fig_disc_abs = _layout(fig_disc_abs, height=380)
            st.plotly_chart(fig_disc_abs, use_container_width=True)
    else:
        st.info("No discount data available.")
else:
    st.info("Discount column not available.")

# ─── SECTION 12: PAYMENT METHOD BY CHANNEL ───────────────────────────────────
section("Payment Method by Channel")

pay_col = None
for _c in ["Payment Method", "Payment Type", "Delivery Partner Name"]:
    if _c in df.columns:
        pay_col = _c
        break

if pay_col:
    if "Unique Order ID" in df.columns:
        pay_ch = (
            df.groupby(["Channel", pay_col])["Unique Order ID"]
            .nunique()
            .reset_index()
            .rename(columns={"Unique Order ID": "Orders"})
        )
    else:
        pay_ch = (
            df.groupby(["Channel", pay_col])
            .size()
            .reset_index(name="Orders")
        )

    if not pay_ch.empty:
        fig_pay = px.bar(
            pay_ch,
            x="Channel",
            y="Orders",
            color=pay_col,
            barmode="stack",
            title=f"Orders by Channel — split by {pay_col}",
        )
        fig_pay = _layout(fig_pay, height=420)
        st.plotly_chart(fig_pay, use_container_width=True)
    else:
        st.info("No payment method data available.")
else:
    st.info("No payment method / type column found in data.")

# ─── SECTION 13: CANCELLATION RATE BY CHANNEL ────────────────────────────────
section("Cancellation Rate by Channel")

if not df_cancel.empty and "Channel" in df_cancel.columns:
    cancel_ch = df_cancel.groupby("Channel").size().reset_index(name="Cancellations")

    if "Unique Order ID" in df.columns:
        delivered_ch = df.groupby("Channel")["Unique Order ID"].nunique().reset_index(name="Delivered")
    else:
        delivered_ch = df.groupby("Channel").size().reset_index(name="Delivered")

    cancel_merged = cancel_ch.merge(delivered_ch, on="Channel", how="outer").fillna(0)
    cancel_merged["Total"] = cancel_merged["Cancellations"] + cancel_merged["Delivered"]
    cancel_merged["Cancel Rate %"] = (
        cancel_merged["Cancellations"] / cancel_merged["Total"].replace(0, np.nan) * 100
    ).fillna(0)

    if not cancel_merged.empty:
        col_c1, col_c2 = st.columns(2)

        with col_c1:
            fig_can_cnt = px.bar(
                cancel_merged.sort_values("Cancellations", ascending=False),
                x="Channel",
                y="Cancellations",
                title="Cancellation Count by Channel",
                color="Channel",
                color_discrete_map=cmap,
                text="Cancellations",
            )
            fig_can_cnt.update_traces(textposition="outside")
            fig_can_cnt = _layout(fig_can_cnt, height=380)
            st.plotly_chart(fig_can_cnt, use_container_width=True)

        with col_c2:
            fig_can_rate = px.bar(
                cancel_merged.sort_values("Cancel Rate %", ascending=False),
                x="Channel",
                y="Cancel Rate %",
                title="Cancellation Rate % by Channel",
                color="Channel",
                color_discrete_map=cmap,
                text="Cancel Rate %",
            )
            fig_can_rate.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_can_rate = _layout(fig_can_rate, height=380)
            st.plotly_chart(fig_can_rate, use_container_width=True)
    else:
        st.info("No cancellation data available for channels.")
else:
    st.info("No cancellation data available or Channel column missing.")

# ─── SECTION 14: CHANNEL GROWTH RATES ────────────────────────────────────────
section("Channel Month-over-Month Growth Rates")

if "Month" in df.columns:
    monthly_rev_ch = (
        df.groupby(["Month", "Channel"])["Gross Price"]
        .sum()
        .reset_index()
        .rename(columns={"Gross Price": "Revenue"})
    )

    if not monthly_rev_ch.empty:
        pivot_growth = monthly_rev_ch.pivot_table(
            index="Month", columns="Channel", values="Revenue", aggfunc="sum"
        ).sort_index()

        growth_pct = pivot_growth.pct_change() * 100

        if not growth_pct.empty:
            # Style: green for positive, red for negative
            def color_growth(val):
                try:
                    if pd.isna(val):
                        return "color: #6C757D"
                    return "color: #2ECC71; font-weight:600" if val >= 0 else "color: #E74C3C; font-weight:600"
                except Exception:
                    return ""

            display_growth = growth_pct.applymap(
                lambda v: f"{v:+.1f}%" if pd.notna(v) else "—"
            )
            styled = display_growth.style.applymap(color_growth)
            st.markdown("**Month-over-Month Revenue Growth % per Channel**")
            st.dataframe(styled, use_container_width=True)

            # Line chart of MoM growth
            growth_long = growth_pct.reset_index().melt(
                id_vars="Month", var_name="Channel", value_name="MoM Growth %"
            ).dropna()

            if not growth_long.empty:
                fig_growth = px.line(
                    growth_long.sort_values("Month"),
                    x="Month",
                    y="MoM Growth %",
                    color="Channel",
                    title="MoM Revenue Growth % by Channel",
                    color_discrete_map=cmap,
                    markers=True,
                )
                fig_growth.add_hline(y=0, line_dash="dash", line_color="#6C757D")
                fig_growth = _layout(fig_growth, height=400)
                st.plotly_chart(fig_growth, use_container_width=True)
        else:
            st.info("Not enough monthly data to calculate growth rates.")
    else:
        st.info("No monthly revenue data available for growth analysis.")
else:
    st.info("Month column not available for growth rate calculation.")

# ─── FOOTER ──────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f"<small style='color:#666;'>Channel Analysis · "
    f"{len(df):,} orders · "
    f"{df['Channel'].nunique()} channels · "
    f"Filtered to {date_range[0] if len(date_range) >= 1 else 'N/A'} → "
    f"{date_range[1] if len(date_range) == 2 else 'N/A'}"
    f"</small>",
    unsafe_allow_html=True,
)
