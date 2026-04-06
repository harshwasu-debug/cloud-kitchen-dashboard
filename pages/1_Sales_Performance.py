"""
Sales Performance Analytics Page
Cloud Kitchen Business Analytics Dashboard
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.data_loader import *

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─── PAGE CONFIG ────────────────────────────────────────────────────────────
st.set_page_config(page_title="Sales Performance", page_icon="💰", layout="wide")

# ─── THEME CONSTANTS ─────────────────────────────────────────────────────────
PRIMARY   = "#FF6B35"
SECONDARY = "#4ECDC4"
ACCENT    = "#FFE66D"
TEMPLATE  = "plotly_white"
CHART_BG  = "rgba(255,255,255,0)"

# Multi-series colour palette
PALETTE = [
    PRIMARY, SECONDARY, ACCENT,
    "#A8DADC", "#457B9D", "#E63946",
    "#F4A261", "#2A9D8F", "#E9C46A",
    "#264653", "#6D6875", "#B5838D",
]

# ─── LOAD DATA ───────────────────────────────────────────────────────────────
with st.spinner("Loading sales data…"):
    df_orders   = load_sales_orders()
    df_brand    = load_sales_brand()
    df_channels = load_sales_channels()
    df_location = load_sales_location()

all_brands    = get_all_brands(df_orders)
all_locations = get_all_locations(df_orders)
all_channels  = get_all_channels(df_orders)

# ─── SIDEBAR FILTERS ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎛️ Filters")
    st.markdown("---")

    sel_brands = st.multiselect(
        "Brand",
        options=all_brands,
        default=[],
        placeholder="All brands",
    )
    sel_locations = st.multiselect(
        "Location",
        options=all_locations,
        default=[],
        placeholder="All locations",
    )
    sel_channels = st.multiselect(
        "Channel",
        options=all_channels,
        default=[],
        placeholder="All channels",
    )

    st.markdown("---")
    st.markdown("**Date Range**")
    if "Received At" in df_orders.columns:
        _dates = df_orders["Received At"].dropna()
        _min = _dates.min().date() if not _dates.empty else None
        _max = _dates.max().date() if not _dates.empty else None
        if _min and _max:
            _dr = st.date_input("Period", value=(_min, _max), min_value=_min, max_value=_max, label_visibility="collapsed")
            sel_start, sel_end = (_dr[0], _dr[1]) if isinstance(_dr, (list, tuple)) and len(_dr) == 2 else (_min, _max)
        else:
            sel_start = sel_end = None
    else:
        sel_start = sel_end = None
    st.markdown("**Time Range**")
    from datetime import time as _time
    _tc1, _tc2 = st.columns(2)
    with _tc1:
        sel_time_from = st.time_input("From", value=_time(0, 0), step=1800)
    with _tc2:
        sel_time_to = st.time_input("To", value=_time(23, 59), step=1800)
    st.markdown("---")
    st.caption("Data source: Grubtech + Deliverect")

# ─── APPLY FILTERS ───────────────────────────────────────────────────────────
df = df_orders.copy()
if sel_brands:
    df = df[df["Brand"].isin(sel_brands)]
if sel_locations:
    df = df[df["Location"].isin(sel_locations)]
if sel_channels:
    df = df[df["Channel"].isin(sel_channels)]
if sel_start and sel_end and "Date" in df.columns:
    df["_date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
    df = df[(df["_date"] >= sel_start) & (df["_date"] <= sel_end)]
    df = df.drop(columns=["_date"])
if "Received At" in df.columns and (sel_time_from != _time(0, 0) or sel_time_to != _time(23, 59)):
    _t = pd.to_datetime(df["Received At"], errors="coerce").dt.time
    df = df[(_t >= sel_time_from) & (_t <= sel_time_to)]

# Filter aggregated tables by brand/channel/location where applicable
df_brand_f = df_brand.copy()
if sel_brands and "Brand" in df_brand_f.columns:
    df_brand_f = df_brand_f[df_brand_f["Brand"].isin(sel_brands)]

df_channels_f = df_channels.copy()
if sel_channels and "Channel" in df_channels_f.columns:
    df_channels_f = df_channels_f[df_channels_f["Channel"].isin(sel_channels)]

df_location_f = df_location.copy()
if sel_locations and "Location Name" in df_location_f.columns:
    df_location_f = df_location_f[df_location_f["Location Name"].isin(sel_locations)]
if sel_brands and "Brand" in df_location_f.columns:
    df_location_f = df_location_f[df_location_f["Brand"].isin(sel_brands)]

# ─── GUARD: EMPTY DATA ────────────────────────────────────────────────────────
if df.empty:
    st.warning("No data matches the selected filters. Please adjust your selections.")
    st.stop()

# ─── HELPERS ─────────────────────────────────────────────────────────────────
def fmt_aed(val: float) -> str:
    if abs(val) >= 1_000_000:
        return f"AED {val/1_000_000:.2f}M"
    if abs(val) >= 1_000:
        return f"AED {val/1_000:.1f}K"
    return f"AED {val:.0f}"


def delta_pct(new: float, old: float):
    if old == 0:
        return None
    return round((new - old) / abs(old) * 100, 1)


def rolling_mean(series: pd.Series, window: int = 7) -> pd.Series:
    return series.rolling(window=window, min_periods=1).mean()


# ─── KPI CALCULATIONS ────────────────────────────────────────────────────────
total_revenue   = df["Gross Price"].sum()
total_orders    = df["Unique Order ID"].nunique() if "Unique Order ID" in df.columns else len(df)
total_net_sales = df["Net Sales"].sum()
total_discounts = df["Discount"].sum()
aov             = total_revenue / total_orders if total_orders > 0 else 0

# First-half vs second-half split for period deltas
df_sorted = df.dropna(subset=["Received At"]).sort_values("Received At")
midpoint  = len(df_sorted) // 2
df_h1     = df_sorted.iloc[:midpoint]
df_h2     = df_sorted.iloc[midpoint:]

rev_h1 = df_h1["Gross Price"].sum()
rev_h2 = df_h2["Gross Price"].sum()

ord_h1 = df_h1["Unique Order ID"].nunique() if "Unique Order ID" in df_h1.columns else len(df_h1)
ord_h2 = df_h2["Unique Order ID"].nunique() if "Unique Order ID" in df_h2.columns else len(df_h2)

aov_h1 = rev_h1 / ord_h1 if ord_h1 > 0 else 0
aov_h2 = rev_h2 / ord_h2 if ord_h2 > 0 else 0

disc_h1 = df_h1["Discount"].sum()
disc_h2 = df_h2["Discount"].sum()

net_h1 = df_h1["Net Sales"].sum()
net_h2 = df_h2["Net Sales"].sum()

# ─── PAGE HEADER ─────────────────────────────────────────────────────────────
filter_note = ""
if sel_brands:
    filter_note = f" · {', '.join(sel_brands)}"
elif sel_channels:
    filter_note = f" · {', '.join(sel_channels)}"

st.markdown(
    f"""
    <h1 style='color:{PRIMARY}; margin-bottom:0;'>💰 Sales Performance</h1>
    <p style='color:#555; margin-top:4px;'>
        Cloud Kitchen Analytics · {total_orders:,} orders{filter_note}
    </p>
    """,
    unsafe_allow_html=True,
)
st.markdown("---")

# ─── SECTION 1 — KPI METRICS ─────────────────────────────────────────────────
st.subheader("Key Performance Indicators")
k1, k2, k3, k4, k5 = st.columns(5)

with k1:
    d = delta_pct(rev_h2, rev_h1)
    st.metric(
        "Total Revenue",
        fmt_aed(total_revenue),
        delta=f"{d:+.1f}%" if d is not None else None,
        help="Gross sales before discounts. Delta = H2 vs H1 of the period.",
    )
with k2:
    d = delta_pct(ord_h2, ord_h1)
    st.metric(
        "Total Orders",
        f"{total_orders:,}",
        delta=f"{d:+.1f}%" if d is not None else None,
        help="Unique orders. Delta = H2 vs H1.",
    )
with k3:
    d = delta_pct(aov_h2, aov_h1)
    st.metric(
        "Avg. Order Value",
        fmt_aed(aov),
        delta=f"{d:+.1f}%" if d is not None else None,
        help="Revenue ÷ Orders. Delta = H2 vs H1.",
    )
with k4:
    d = delta_pct(disc_h2, disc_h1)
    st.metric(
        "Total Discounts",
        fmt_aed(total_discounts),
        delta=f"{d:+.1f}%" if d is not None else None,
        delta_color="inverse",
        help="Sum of all discounts applied. Delta = H2 vs H1.",
    )
with k5:
    d = delta_pct(net_h2, net_h1)
    st.metric(
        "Net Sales",
        fmt_aed(total_net_sales),
        delta=f"{d:+.1f}%" if d is not None else None,
        help="Net revenue after discounts. Delta = H2 vs H1.",
    )

st.markdown("---")

# ─── SECTION 2 — REVENUE TREND ───────────────────────────────────────────────
st.subheader("Revenue Trend — Daily with 7-Day Moving Average")

daily_rev = (
    df.groupby("Date")["Total(Receipt Total)"]
    .sum()
    .reset_index()
    .sort_values("Date")
)
daily_rev["7-Day MA"] = rolling_mean(daily_rev["Total(Receipt Total)"])

fig_trend = go.Figure()
fig_trend.add_trace(go.Bar(
    x=daily_rev["Date"],
    y=daily_rev["Total(Receipt Total)"],
    name="Daily Revenue",
    marker_color=PRIMARY,
    opacity=0.7,
    hovertemplate="<b>%{x}</b><br>Revenue: AED %{y:,.0f}<extra></extra>",
))
fig_trend.add_trace(go.Scatter(
    x=daily_rev["Date"],
    y=daily_rev["7-Day MA"],
    name="7-Day MA",
    line=dict(color=ACCENT, width=2.5),
    hovertemplate="<b>%{x}</b><br>7-Day MA: AED %{y:,.0f}<extra></extra>",
))
fig_trend.update_layout(
    template=TEMPLATE,
    paper_bgcolor=CHART_BG,
    plot_bgcolor=CHART_BG,
    legend=dict(orientation="h", y=1.05),
    xaxis_title="Date",
    yaxis_title="Revenue (AED)",
    hovermode="x unified",
    height=380,
    margin=dict(l=10, r=10, t=30, b=10),
)
st.plotly_chart(fig_trend, use_container_width=True)

st.markdown("---")

# ─── SECTION 3 — GROWTH RATES ────────────────────────────────────────────────
st.subheader("Growth Rates")

tab_wow, tab_mom, tab_daily = st.tabs(["Week-over-Week", "Month-over-Month", "Daily Growth Rate"])

# ── WoW ──────────────────────────────────────────────────────────────────────
with tab_wow:
    weekly = (
        df.groupby("Week")
        .agg(Revenue=("Total(Receipt Total)", "sum"), Orders=("Unique Order ID", "nunique"))
        .reset_index()
        .sort_values("Week")
    )
    weekly["Rev WoW %"]   = weekly["Revenue"].pct_change() * 100
    weekly["Order WoW %"] = weekly["Orders"].pct_change() * 100

    col_tbl, col_spark = st.columns([1, 1])

    with col_tbl:
        st.markdown("**Weekly Revenue & Orders**")
        display_wow = weekly.copy()
        display_wow["Revenue"]     = display_wow["Revenue"].apply(fmt_aed)
        display_wow["Rev WoW %"]   = display_wow["Rev WoW %"].apply(
            lambda x: f"{x:+.1f}%" if pd.notna(x) else "—"
        )
        display_wow["Order WoW %"] = display_wow["Order WoW %"].apply(
            lambda x: f"{x:+.1f}%" if pd.notna(x) else "—"
        )
        st.dataframe(
            display_wow[["Week", "Revenue", "Orders", "Rev WoW %", "Order WoW %"]],
            use_container_width=True,
            hide_index=True,
        )

    with col_spark:
        st.markdown("**WoW Revenue Growth (%)**")
        wow_plot = weekly.dropna(subset=["Rev WoW %"])
        fig_wow = go.Figure()
        fig_wow.add_trace(go.Bar(
            x=wow_plot["Week"].astype(str),
            y=wow_plot["Rev WoW %"],
            marker_color=[PRIMARY if v >= 0 else "#E63946" for v in wow_plot["Rev WoW %"]],
            hovertemplate="Week %{x}<br>WoW: %{y:+.1f}%<extra></extra>",
            name="WoW Growth %",
        ))
        fig_wow.add_hline(y=0, line_dash="dot", line_color="#888")
        fig_wow.update_layout(
            template=TEMPLATE,
            paper_bgcolor=CHART_BG,
            plot_bgcolor=CHART_BG,
            xaxis_title="Week #",
            yaxis_title="Growth %",
            height=320,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig_wow, use_container_width=True)

# ── MoM ──────────────────────────────────────────────────────────────────────
with tab_mom:
    monthly = (
        df.groupby("Month")
        .agg(Revenue=("Total(Receipt Total)", "sum"), Orders=("Unique Order ID", "nunique"))
        .reset_index()
        .sort_values("Month")
    )
    monthly["Rev MoM %"]   = monthly["Revenue"].pct_change() * 100
    monthly["Order MoM %"] = monthly["Orders"].pct_change() * 100
    monthly["AOV"]         = monthly["Revenue"] / monthly["Orders"].replace(0, np.nan)

    display_mom = monthly.copy()
    display_mom["Revenue"]     = display_mom["Revenue"].apply(fmt_aed)
    display_mom["AOV"]         = display_mom["AOV"].apply(fmt_aed)
    display_mom["Rev MoM %"]   = display_mom["Rev MoM %"].apply(
        lambda x: f"{x:+.1f}%" if pd.notna(x) else "—"
    )
    display_mom["Order MoM %"] = display_mom["Order MoM %"].apply(
        lambda x: f"{x:+.1f}%" if pd.notna(x) else "—"
    )
    st.markdown("**Monthly Revenue Summary**")
    st.dataframe(
        display_mom[["Month", "Revenue", "Orders", "AOV", "Rev MoM %", "Order MoM %"]],
        use_container_width=True,
        hide_index=True,
    )

    fig_mom = go.Figure()
    fig_mom.add_trace(go.Bar(
        x=monthly["Month"],
        y=monthly["Revenue"],
        name="Revenue",
        marker_color=PRIMARY,
        yaxis="y",
        hovertemplate="<b>%{x}</b><br>Revenue: AED %{y:,.0f}<extra></extra>",
    ))
    fig_mom.add_trace(go.Scatter(
        x=monthly["Month"],
        y=monthly["Rev MoM %"],
        name="MoM Growth %",
        line=dict(color=ACCENT, width=2.5),
        yaxis="y2",
        hovertemplate="<b>%{x}</b><br>MoM: %{y:+.1f}%<extra></extra>",
    ))
    fig_mom.update_layout(
        template=TEMPLATE,
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        yaxis=dict(title="Revenue (AED)"),
        yaxis2=dict(title="MoM Growth %", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", y=1.05),
        height=350,
        margin=dict(l=10, r=10, t=30, b=10),
    )
    st.plotly_chart(fig_mom, use_container_width=True)

# ── Daily Growth Rate ─────────────────────────────────────────────────────────
with tab_daily:
    daily_rev_sorted = daily_rev.sort_values("Date").copy()
    daily_rev_sorted["Daily Growth %"] = daily_rev_sorted["Total(Receipt Total)"].pct_change() * 100
    daily_rev_sorted["Growth MA 7d"]   = rolling_mean(
        daily_rev_sorted["Daily Growth %"].fillna(0)
    )

    fig_dgr = go.Figure()
    fig_dgr.add_trace(go.Scatter(
        x=daily_rev_sorted["Date"],
        y=daily_rev_sorted["Daily Growth %"],
        name="Daily Growth %",
        mode="lines",
        line=dict(color=SECONDARY, width=1),
        opacity=0.6,
        hovertemplate="<b>%{x}</b><br>Growth: %{y:+.1f}%<extra></extra>",
    ))
    fig_dgr.add_trace(go.Scatter(
        x=daily_rev_sorted["Date"],
        y=daily_rev_sorted["Growth MA 7d"],
        name="7-Day MA",
        mode="lines",
        line=dict(color=ACCENT, width=2.5),
        hovertemplate="<b>%{x}</b><br>7-Day MA: %{y:+.1f}%<extra></extra>",
    ))
    fig_dgr.add_hline(y=0, line_dash="dot", line_color="#888")
    fig_dgr.update_layout(
        template=TEMPLATE,
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        xaxis_title="Date",
        yaxis_title="Daily Growth %",
        legend=dict(orientation="h", y=1.05),
        hovermode="x unified",
        height=350,
        margin=dict(l=10, r=10, t=30, b=10),
    )
    st.plotly_chart(fig_dgr, use_container_width=True)

st.markdown("---")

# ─── SECTION 4 — REVENUE BREAKDOWN ───────────────────────────────────────────
st.subheader("Revenue Breakdown")

rb_brand, rb_channel, rb_location = st.tabs(["By Brand", "By Channel", "By Location"])

# ── By Brand — Horizontal bar chart sorted descending ─────────────────────────
with rb_brand:
    if "Total Earnings" in df_brand_f.columns and not df_brand_f.empty:
        brand_rev = df_brand_f[["Brand", "Total Earnings"]].sort_values("Total Earnings", ascending=True)
    else:
        brand_rev = (
            df.groupby("Brand")["Total(Receipt Total)"]
            .sum()
            .reset_index()
            .rename(columns={"Total(Receipt Total)": "Total Earnings"})
            .sort_values("Total Earnings", ascending=True)
        )

    fig_brand = go.Figure(go.Bar(
        x=brand_rev["Total Earnings"],
        y=brand_rev["Brand"],
        orientation="h",
        marker=dict(
            color=brand_rev["Total Earnings"],
            colorscale=[[0, "#2b2b2b"], [1, PRIMARY]],
            showscale=False,
        ),
        hovertemplate="<b>%{y}</b><br>Revenue: AED %{x:,.0f}<extra></extra>",
        text=brand_rev["Total Earnings"].apply(fmt_aed),
        textposition="outside",
    ))
    fig_brand.update_layout(
        template=TEMPLATE,
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        xaxis_title="Revenue (AED)",
        yaxis_title="",
        height=max(350, len(brand_rev) * 28 + 80),
        margin=dict(l=10, r=90, t=10, b=10),
    )
    st.plotly_chart(fig_brand, use_container_width=True)

# ── By Channel — Donut/Pie chart ──────────────────────────────────────────────
with rb_channel:
    if "Total Earnings" in df_channels_f.columns and not df_channels_f.empty:
        ch_rev = df_channels_f[["Channel", "Total Earnings"]]
    else:
        ch_rev = (
            df.groupby("Channel")["Total(Receipt Total)"]
            .sum()
            .reset_index()
            .rename(columns={"Total(Receipt Total)": "Total Earnings"})
        )

    fig_ch = go.Figure(go.Pie(
        labels=ch_rev["Channel"],
        values=ch_rev["Total Earnings"],
        hole=0.45,
        marker=dict(colors=PALETTE[:len(ch_rev)]),
        hovertemplate="<b>%{label}</b><br>Revenue: AED %{value:,.0f}<br>Share: %{percent}<extra></extra>",
        textinfo="label+percent",
    ))
    fig_ch.update_layout(
        template=TEMPLATE,
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        legend=dict(orientation="h", y=-0.1),
        height=420,
        margin=dict(l=10, r=10, t=10, b=40),
        annotations=[dict(text="Revenue", x=0.5, y=0.5, font_size=14, showarrow=False)],
    )
    st.plotly_chart(fig_ch, use_container_width=True)

# ── By Location — Treemap ─────────────────────────────────────────────────────
with rb_location:
    if not df_location_f.empty and "Total Earnings" in df_location_f.columns:
        loc_rev = df_location_f[["Location Name", "Brand", "Total Earnings"]].copy()
    else:
        loc_rev = (
            df.groupby(["Location", "Brand"])["Total(Receipt Total)"]
            .sum()
            .reset_index()
            .rename(columns={"Location": "Location Name", "Total(Receipt Total)": "Total Earnings"})
        )
    loc_rev = loc_rev[loc_rev["Total Earnings"] > 0]

    fig_tree = px.treemap(
        loc_rev,
        path=["Brand", "Location Name"],
        values="Total Earnings",
        color="Total Earnings",
        color_continuous_scale=["#1a1a2e", PRIMARY],
        hover_data={"Total Earnings": ":,.0f"},
    )
    fig_tree.update_traces(
        hovertemplate="<b>%{label}</b><br>Revenue: AED %{value:,.0f}<extra></extra>"
    )
    fig_tree.update_layout(
        template=TEMPLATE,
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        coloraxis_showscale=False,
        height=460,
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(fig_tree, use_container_width=True)

st.markdown("---")

# ─── SECTION 5 — AOV ANALYSIS ────────────────────────────────────────────────
st.subheader("Average Order Value (AOV) Analysis")

# Daily AOV with 7-day MA
daily_aov = (
    df.groupby("Date")
    .agg(
        Revenue=("Total(Receipt Total)", "sum"),
        Orders=("Unique Order ID", "nunique"),
    )
    .reset_index()
    .sort_values("Date")
)
daily_aov["AOV"]      = daily_aov["Revenue"] / daily_aov["Orders"].replace(0, np.nan)
daily_aov["AOV 7d MA"] = rolling_mean(daily_aov["AOV"])

fig_aov_trend = go.Figure()
fig_aov_trend.add_trace(go.Scatter(
    x=daily_aov["Date"],
    y=daily_aov["AOV"],
    name="Daily AOV",
    mode="lines",
    line=dict(color=SECONDARY, width=1.5),
    opacity=0.7,
    hovertemplate="<b>%{x}</b><br>AOV: AED %{y:,.2f}<extra></extra>",
))
fig_aov_trend.add_trace(go.Scatter(
    x=daily_aov["Date"],
    y=daily_aov["AOV 7d MA"],
    name="7-Day MA",
    mode="lines",
    line=dict(color=ACCENT, width=2.5),
    hovertemplate="<b>%{x}</b><br>AOV 7d MA: AED %{y:,.2f}<extra></extra>",
))
fig_aov_trend.update_layout(
    template=TEMPLATE,
    paper_bgcolor=CHART_BG,
    plot_bgcolor=CHART_BG,
    xaxis_title="Date",
    yaxis_title="AOV (AED)",
    legend=dict(orientation="h", y=1.05),
    hovermode="x unified",
    height=320,
    margin=dict(l=10, r=10, t=30, b=10),
)
st.plotly_chart(fig_aov_trend, use_container_width=True)

aov_c1, aov_c2 = st.columns(2)

# ── AOV by Brand ──────────────────────────────────────────────────────────────
with aov_c1:
    st.markdown("**AOV by Brand**")
    if "Avg. Order Value" in df_brand_f.columns and not df_brand_f.empty:
        aov_brand = df_brand_f[["Brand", "Avg. Order Value"]].rename(columns={"Avg. Order Value": "AOV"})
    else:
        aov_brand = (
            df.groupby("Brand")
            .apply(
                lambda x: x["Total(Receipt Total)"].sum() / x["Unique Order ID"].nunique()
                if x["Unique Order ID"].nunique() > 0 else 0
            )
            .reset_index(name="AOV")
        )
    aov_brand = aov_brand.sort_values("AOV", ascending=False)

    fig_ab = px.bar(
        aov_brand, x="Brand", y="AOV",
        color="AOV",
        color_continuous_scale=[[0, "#2b2b2b"], [1, SECONDARY]],
        text=aov_brand["AOV"].apply(lambda v: f"AED {v:,.0f}"),
    )
    fig_ab.update_traces(
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>AOV: AED %{y:,.2f}<extra></extra>",
    )
    fig_ab.update_layout(
        template=TEMPLATE,
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        showlegend=False,
        coloraxis_showscale=False,
        xaxis_title="",
        yaxis_title="AOV (AED)",
        xaxis_tickangle=-35,
        height=370,
        margin=dict(l=10, r=10, t=20, b=80),
    )
    st.plotly_chart(fig_ab, use_container_width=True)

# ── AOV by Channel ────────────────────────────────────────────────────────────
with aov_c2:
    st.markdown("**AOV by Channel**")
    if "Avg. Order Value" in df_channels_f.columns and not df_channels_f.empty:
        aov_channel = df_channels_f[["Channel", "Avg. Order Value"]].rename(columns={"Avg. Order Value": "AOV"})
    else:
        aov_channel = (
            df.groupby("Channel")
            .apply(
                lambda x: x["Total(Receipt Total)"].sum() / x["Unique Order ID"].nunique()
                if x["Unique Order ID"].nunique() > 0 else 0
            )
            .reset_index(name="AOV")
        )
    aov_channel = aov_channel.sort_values("AOV", ascending=False)

    fig_ac = px.bar(
        aov_channel, x="Channel", y="AOV",
        color="AOV",
        color_continuous_scale=[[0, "#2b2b2b"], [1, PRIMARY]],
        text=aov_channel["AOV"].apply(lambda v: f"AED {v:,.0f}"),
    )
    fig_ac.update_traces(
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>AOV: AED %{y:,.2f}<extra></extra>",
    )
    fig_ac.update_layout(
        template=TEMPLATE,
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        showlegend=False,
        coloraxis_showscale=False,
        xaxis_title="",
        yaxis_title="AOV (AED)",
        xaxis_tickangle=-35,
        height=370,
        margin=dict(l=10, r=10, t=20, b=80),
    )
    st.plotly_chart(fig_ac, use_container_width=True)

aov_c3, aov_c4 = st.columns(2)

# ── AOV by Day of Week ────────────────────────────────────────────────────────
with aov_c3:
    st.markdown("**AOV by Day of Week**")
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    aov_dow = (
        df.groupby("Day")
        .apply(
            lambda x: x["Total(Receipt Total)"].sum() / x["Unique Order ID"].nunique()
            if x["Unique Order ID"].nunique() > 0 else 0
        )
        .reset_index(name="AOV")
    )
    aov_dow["Day"] = pd.Categorical(aov_dow["Day"], categories=day_order, ordered=True)
    aov_dow = aov_dow.sort_values("Day")

    fig_dow = px.bar(
        aov_dow, x="Day", y="AOV",
        color="AOV",
        color_continuous_scale=[[0, "#2b2b2b"], [1, ACCENT]],
        text=aov_dow["AOV"].apply(lambda v: f"AED {v:,.0f}"),
    )
    fig_dow.update_traces(
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>AOV: AED %{y:,.2f}<extra></extra>",
    )
    fig_dow.update_layout(
        template=TEMPLATE,
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        showlegend=False,
        coloraxis_showscale=False,
        xaxis_title="",
        yaxis_title="AOV (AED)",
        height=350,
        margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(fig_dow, use_container_width=True)

# ── AOV by Hour of Day — Peak Hours ──────────────────────────────────────────
with aov_c4:
    st.markdown("**AOV by Hour of Day (Peak Hours)**")
    aov_hour = (
        df.groupby("Hour")
        .apply(
            lambda x: x["Total(Receipt Total)"].sum() / x["Unique Order ID"].nunique()
            if x["Unique Order ID"].nunique() > 0 else 0
        )
        .reset_index(name="AOV")
    )
    orders_by_hour = df.groupby("Hour")["Unique Order ID"].nunique().reset_index(name="Orders")
    aov_hour = aov_hour.merge(orders_by_hour, on="Hour")

    peak_hour = None
    if not aov_hour.empty:
        peak_hour = int(aov_hour.loc[aov_hour["Orders"].idxmax(), "Hour"])

    fig_hour = go.Figure()
    fig_hour.add_trace(go.Scatter(
        x=aov_hour["Hour"],
        y=aov_hour["AOV"],
        mode="lines+markers",
        name="AOV",
        line=dict(color=SECONDARY, width=2),
        marker=dict(
            size=8,
            color=[PRIMARY if h == peak_hour else SECONDARY for h in aov_hour["Hour"]],
        ),
        hovertemplate="<b>%{x}:00</b><br>AOV: AED %{y:,.2f}<br>Orders: %{customdata}<extra></extra>",
        customdata=aov_hour["Orders"],
    ))
    if peak_hour is not None and not aov_hour.empty:
        peak_aov_row = aov_hour.loc[aov_hour["Hour"] == peak_hour, "AOV"]
        if not peak_aov_row.empty:
            peak_aov_val = float(peak_aov_row.iloc[0])
            fig_hour.add_annotation(
                x=peak_hour, y=peak_aov_val,
                text=f"Peak: {peak_hour}:00",
                showarrow=True,
                arrowhead=2,
                arrowcolor=PRIMARY,
                font=dict(color=PRIMARY, size=12),
                bgcolor="rgba(0,0,0,0.5)",
            )
    fig_hour.update_layout(
        template=TEMPLATE,
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        xaxis=dict(title="Hour of Day", tickmode="linear", dtick=2),
        yaxis_title="AOV (AED)",
        height=350,
        margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(fig_hour, use_container_width=True)

st.markdown("---")

# ─── SECTION 6 — PAYMENT ANALYSIS ────────────────────────────────────────────
st.subheader("Payment Analysis")

pay_c1, pay_c2 = st.columns(2)

with pay_c1:
    st.markdown("**Payment Method Distribution**")
    if "Payment Method" in df.columns and df["Payment Method"].notna().any():
        pm = df["Payment Method"].value_counts().reset_index()
        pm.columns = ["Payment Method", "Count"]
        fig_pm = go.Figure(go.Pie(
            labels=pm["Payment Method"],
            values=pm["Count"],
            hole=0.4,
            marker=dict(colors=PALETTE[:len(pm)]),
            hovertemplate="<b>%{label}</b><br>Orders: %{value:,}<br>Share: %{percent}<extra></extra>",
            textinfo="label+percent",
        ))
        fig_pm.update_layout(
            template=TEMPLATE,
            paper_bgcolor=CHART_BG,
            plot_bgcolor=CHART_BG,
            showlegend=True,
            legend=dict(orientation="h", y=-0.15),
            height=380,
            margin=dict(l=10, r=10, t=10, b=40),
            annotations=[dict(text="Methods", x=0.5, y=0.5, font_size=12, showarrow=False)],
        )
        st.plotly_chart(fig_pm, use_container_width=True)
    else:
        st.info("Payment Method data not available in the selected filter.")

with pay_c2:
    st.markdown("**Revenue by Payment Type**")
    if "Payment Type" in df.columns and df["Payment Type"].notna().any():
        pt = df.groupby("Payment Type")["Total(Receipt Total)"].sum().reset_index()
        pt.columns = ["Payment Type", "Revenue"]
        pt = pt.sort_values("Revenue", ascending=False)
        fig_pt = px.bar(
            pt,
            x="Payment Type",
            y="Revenue",
            color="Payment Type",
            color_discrete_sequence=PALETTE,
            text=pt["Revenue"].apply(fmt_aed),
        )
        fig_pt.update_traces(
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Revenue: AED %{y:,.0f}<extra></extra>",
        )
        fig_pt.update_layout(
            template=TEMPLATE,
            paper_bgcolor=CHART_BG,
            plot_bgcolor=CHART_BG,
            showlegend=False,
            xaxis_title="",
            yaxis_title="Revenue (AED)",
            height=380,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig_pt, use_container_width=True)
    else:
        st.info("Payment Type data not available in the selected filter.")

st.markdown("---")

# ─── SECTION 7 — DISCOUNT ANALYSIS ───────────────────────────────────────────
st.subheader("Discount Analysis")

gross_total         = df["Gross Price"].sum()
disc_rate           = (total_discounts / gross_total * 100) if gross_total > 0 else 0
avg_disc_per_order  = total_discounts / total_orders if total_orders > 0 else 0

disc_k1, disc_k2, disc_k3 = st.columns(3)
with disc_k1:
    st.metric("Total Discounts", fmt_aed(total_discounts))
with disc_k2:
    st.metric("Discount Rate", f"{disc_rate:.1f}%", help="Discount / Gross Sales")
with disc_k3:
    st.metric("Avg. Discount / Order", fmt_aed(avg_disc_per_order))

disc_c1, disc_c2 = st.columns([3, 2])

with disc_c1:
    st.markdown("**Discount Amount & Rate by Brand**")
    if "Discounts" in df_brand_f.columns and not df_brand_f.empty:
        disc_brand = df_brand_f[["Brand", "Discounts", "Gross Sales"]].copy()
        disc_brand["Discount Rate %"] = (
            disc_brand["Discounts"] / disc_brand["Gross Sales"].replace(0, np.nan) * 100
        ).fillna(0)
        disc_brand = disc_brand.sort_values("Discounts", ascending=False)
    else:
        disc_brand = (
            df.groupby("Brand")
            .agg(Discounts=("Discount", "sum"), Gross_Sales=("Gross Price", "sum"))
            .reset_index()
            .rename(columns={"Gross_Sales": "Gross Sales"})
        )
        disc_brand["Discount Rate %"] = (
            disc_brand["Discounts"] / disc_brand["Gross Sales"].replace(0, np.nan) * 100
        ).fillna(0)
        disc_brand = disc_brand.sort_values("Discounts", ascending=False)

    fig_disc = go.Figure()
    fig_disc.add_trace(go.Bar(
        name="Discount Amount",
        x=disc_brand["Brand"],
        y=disc_brand["Discounts"],
        marker_color=PRIMARY,
        yaxis="y",
        hovertemplate="<b>%{x}</b><br>Discount: AED %{y:,.0f}<extra></extra>",
        text=disc_brand["Discounts"].apply(fmt_aed),
        textposition="outside",
    ))
    fig_disc.add_trace(go.Scatter(
        name="Discount Rate %",
        x=disc_brand["Brand"],
        y=disc_brand["Discount Rate %"],
        mode="lines+markers",
        line=dict(color=ACCENT, width=2),
        marker=dict(size=7),
        yaxis="y2",
        hovertemplate="<b>%{x}</b><br>Rate: %{y:.1f}%<extra></extra>",
    ))
    fig_disc.update_layout(
        template=TEMPLATE,
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        yaxis=dict(title="Discount Amount (AED)"),
        yaxis2=dict(title="Discount Rate %", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", y=1.05),
        xaxis_tickangle=-35,
        height=370,
        margin=dict(l=10, r=10, t=30, b=80),
    )
    st.plotly_chart(fig_disc, use_container_width=True)

with disc_c2:
    st.markdown("**Discount vs. Gross Sales (Bubble)**")
    if not disc_brand.empty:
        fig_disc2 = px.scatter(
            disc_brand,
            x="Gross Sales",
            y="Discounts",
            size="Discount Rate %",
            text="Brand",
            color="Discount Rate %",
            color_continuous_scale=[[0, SECONDARY], [1, PRIMARY]],
            size_max=32,
        )
        fig_disc2.update_traces(
            textposition="top center",
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Gross: AED %{x:,.0f}<br>"
                "Discount: AED %{y:,.0f}<extra></extra>"
            ),
        )
        fig_disc2.update_layout(
            template=TEMPLATE,
            paper_bgcolor=CHART_BG,
            plot_bgcolor=CHART_BG,
            coloraxis_showscale=False,
            xaxis_title="Gross Sales (AED)",
            yaxis_title="Discounts (AED)",
            height=370,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig_disc2, use_container_width=True)

st.markdown("---")

# ─── SECTION 8 — DETAILED DATA TABLE ─────────────────────────────────────────
st.subheader("Detailed Orders Data")

with st.expander("Show / Hide Data Table", expanded=False):
    search_term = st.text_input(
        "Search orders (Brand, Channel, Location, Order ID)",
        placeholder="Type to filter…",
        key="orders_search",
    )

    display_cols = [
        c for c in [
            "Unique Order ID", "Order ID", "Received At",
            "Brand", "Channel", "Location",
            "Total(Receipt Total)", "Net Sales", "Gross Price",
            "Discount", "VAT", "Item Price", "Delivery",
            "Payment Method", "Payment Type", "Tips", "Surcharge",
        ]
        if c in df.columns
    ]
    df_display = df[display_cols].copy()

    if search_term:
        mask = pd.Series(False, index=df_display.index)
        sl = search_term.lower()
        for col in ["Brand", "Channel", "Location", "Unique Order ID", "Order ID"]:
            if col in df_display.columns:
                mask |= df_display[col].astype(str).str.lower().str.contains(sl, na=False)
        df_display = df_display[mask]

    st.caption(f"Showing {len(df_display):,} of {len(df):,} orders")

    col_cfg = {}
    if "Total(Receipt Total)" in df_display.columns:
        col_cfg["Total(Receipt Total)"] = st.column_config.NumberColumn("Total (AED)", format="AED %.2f")
    if "Net Sales" in df_display.columns:
        col_cfg["Net Sales"] = st.column_config.NumberColumn("Net Sales (AED)", format="AED %.2f")
    if "Gross Price" in df_display.columns:
        col_cfg["Gross Price"] = st.column_config.NumberColumn("Gross (AED)", format="AED %.2f")
    if "Discount" in df_display.columns:
        col_cfg["Discount"] = st.column_config.NumberColumn("Discount (AED)", format="AED %.2f")
    if "VAT" in df_display.columns:
        col_cfg["VAT"] = st.column_config.NumberColumn("VAT (AED)", format="AED %.2f")
    if "Item Price" in df_display.columns:
        col_cfg["Item Price"] = st.column_config.NumberColumn("Item Price (AED)", format="AED %.2f")
    if "Delivery" in df_display.columns:
        col_cfg["Delivery"] = st.column_config.NumberColumn("Delivery (AED)", format="AED %.2f")
    if "Tips" in df_display.columns:
        col_cfg["Tips"] = st.column_config.NumberColumn("Tips (AED)", format="AED %.2f")
    if "Surcharge" in df_display.columns:
        col_cfg["Surcharge"] = st.column_config.NumberColumn("Surcharge (AED)", format="AED %.2f")
    if "Received At" in df_display.columns:
        col_cfg["Received At"] = st.column_config.DatetimeColumn(
            "Received At", format="DD MMM YYYY, HH:mm"
        )

    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        height=440,
        column_config=col_cfg,
    )

# ─── FOOTER ──────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "Sales Performance · Grubtech Cloud Kitchen Dashboard · "
    "Data refreshes every 60 min · Powered by Streamlit & Plotly"
)
