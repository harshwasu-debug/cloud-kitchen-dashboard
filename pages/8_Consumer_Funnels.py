"""
Consumer Funnels — Cloud Kitchen Analytics Dashboard
Three funnel views: Order Funnel, Retention Funnel, Marketing Funnel.
Tracks conversion drop-offs across the full customer journey.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import time as _time, datetime as _dt

from utils.data_loader import (
    load_sales_orders, load_operations_orders, load_cancelled_orders,
    load_cpc_data, load_marketing,
    add_cuisine_column, get_all_brands, get_all_locations,
    get_all_channels, get_all_cuisines,
)

# ─── PAGE CONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Consumer Funnels", page_icon="🔄", layout="wide")

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

AGG_COLORS = {"Talabat": "#FF5A00", "Careem": "#00B140", "Noon": "#FEEE00"}
ROAS_GREEN  = "#2ECC71"
ROAS_YELLOW = "#F39C12"
ROAS_RED    = "#E74C3C"

SEG_COLORS = {
    "New": "#457B9D", "Repeat": SECONDARY, "Loyal": PRIMARY,
    "At Risk": "#F39C12", "Churned": "#E63946",
}

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.kpi-card {
    background: #F8F9FA;
    border-radius: 10px;
    padding: 18px 20px;
    border-left: 4px solid #FF6B35;
    margin-bottom: 8px;
}
.kpi-card.warning { border-left-color: #F39C12; }
.kpi-card.danger  { border-left-color: #E74C3C; }
.kpi-card.success { border-left-color: #2ECC71; }
.kpi-label { color: #555; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; }
.kpi-value { color: #1A1A2E; font-size: 1.75rem; font-weight: 700; margin: 4px 0 2px; }
.kpi-sub   { color: #888; font-size: 0.78rem; }
.section-header {
    font-size: 1.1rem; font-weight: 700; color: #1A1A2E;
    border-bottom: 2px solid #FF6B35;
    padding-bottom: 6px; margin: 24px 0 16px;
}
</style>
""", unsafe_allow_html=True)

# ─── HELPERS ─────────────────────────────────────────────────────────────────
def kpi_card(label, value, sub="", css_class=""):
    st.markdown(f"""
    <div class="kpi-card {css_class}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)

def section(title):
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)

def fmt_num(val, decimals=0):
    try:
        if abs(val) >= 1_000_000:
            return f"{val/1_000_000:.1f}M"
        if abs(val) >= 1_000:
            return f"{val/1_000:.1f}K"
        return f"{val:,.{decimals}f}"
    except Exception:
        return "N/A"

def fmt_aed(val):
    try:
        if abs(val) >= 1_000_000:
            return f"AED {val/1_000_000:.2f}M"
        if abs(val) >= 1_000:
            return f"AED {val/1_000:.1f}K"
        return f"AED {val:,.0f}"
    except Exception:
        return "N/A"

def fmt_pct(val, decimals=1):
    try:
        return f"{val:.{decimals}f}%"
    except Exception:
        return "N/A"

def safe_div(num, den, fallback=0):
    return num / den if den and den > 0 else fallback

def chart_layout(**kwargs):
    base = dict(template=TEMPLATE, paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG)
    base.update(kwargs)
    return base

def roas_color(val):
    if val >= 3:
        return ROAS_GREEN
    elif val >= 1:
        return ROAS_YELLOW
    return ROAS_RED

# ─── LOAD DATA ───────────────────────────────────────────────────────────────
with st.spinner("Loading funnel data…"):
    df_sales_raw = load_sales_orders()
    df_ops_raw   = load_operations_orders()
    df_cancel_raw = load_cancelled_orders()
    df_cpc_raw   = load_cpc_data()
    df_mkt_raw   = load_marketing()

df_sales_raw = add_cuisine_column(df_sales_raw, "Brand")

all_brands    = get_all_brands(df_sales_raw)
all_locations = get_all_locations(df_sales_raw)
all_channels  = get_all_channels(df_sales_raw)
all_cuisines  = get_all_cuisines()

# ─── SIDEBAR FILTERS ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔄 Funnel Filters")
    st.markdown("---")

    sel_brands = st.multiselect("Brand", options=all_brands, default=[], placeholder="All brands", key="b_fn")
    sel_locations = st.multiselect("Location", options=all_locations, default=[], placeholder="All locations", key="l_fn")
    sel_channels = st.multiselect("Channel", options=all_channels, default=[], placeholder="All channels", key="ch_fn")
    sel_cuisines = st.multiselect("Cuisine", options=all_cuisines, default=[], placeholder="All cuisines", key="cu_fn")

    st.markdown("---")
    st.markdown("**Date Range**")
    if "Received At" in df_sales_raw.columns:
        _dates = df_sales_raw["Received At"].dropna()
        _min = _dates.min().date() if not _dates.empty else None
        _max = _dates.max().date() if not _dates.empty else None
        if _min and _max:
            _dr = st.date_input("Period", value=(_min, _max), min_value=_min, max_value=_max,
                                label_visibility="collapsed", key="dr_fn")
            sel_start, sel_end = (_dr[0], _dr[1]) if isinstance(_dr, (list, tuple)) and len(_dr) == 2 else (_min, _max)
        else:
            sel_start = sel_end = None
    else:
        sel_start = sel_end = None

    st.markdown("**Time Range**")
    _tc1, _tc2 = st.columns(2)
    with _tc1:
        sel_time_from = st.time_input("From", value=_time(0, 0), step=1800, key="tf_fn")
    with _tc2:
        sel_time_to = st.time_input("To", value=_time(23, 59), step=1800, key="tt_fn")
    st.markdown("---")
    st.caption("Data: Grubtech + Deliverect + CPC")

# ─── FILTER APPLICATION ──────────────────────────────────────────────────────
def apply_common_filters(df, date_col="Received At"):
    """Apply Brand/Location/Channel/Cuisine/Date+Time filters."""
    if df.empty:
        return df
    d = df.copy()
    if sel_brands and "Brand" in d.columns:
        d = d[d["Brand"].isin(sel_brands)]
    if sel_locations and "Location" in d.columns:
        d = d[d["Location"].isin(sel_locations)]
    if sel_channels and "Channel" in d.columns:
        d = d[d["Channel"].isin(sel_channels)]
    if sel_cuisines and "Cuisine" in d.columns:
        d = d[d["Cuisine"].isin(sel_cuisines)]
    if sel_start and sel_end and date_col in d.columns:
        d[date_col] = pd.to_datetime(d[date_col], errors="coerce")
        _s = pd.Timestamp(_dt.combine(sel_start, sel_time_from))
        _e = pd.Timestamp(_dt.combine(sel_end, sel_time_to))
        d = d[(d[date_col] >= _s) & (d[date_col] <= _e)]
    return d

df_s = apply_common_filters(df_sales_raw, "Received At")
df_o = apply_common_filters(df_ops_raw, "Received At")
df_c = apply_common_filters(df_cancel_raw, "Date")

# CPC: Brand filter uses "Brand" column (mapped from brand_name in loader)
df_cpc_f = df_cpc_raw.copy() if not df_cpc_raw.empty else pd.DataFrame()
if not df_cpc_f.empty:
    if sel_brands and "Brand" in df_cpc_f.columns:
        df_cpc_f = df_cpc_f[df_cpc_f["Brand"].isin(sel_brands)]
    if sel_cuisines and "Cuisine" in df_cpc_f.columns:
        df_cpc_f = df_cpc_f[df_cpc_f["Cuisine"].isin(sel_cuisines)]
    if sel_start and sel_end and "date_value" in df_cpc_f.columns:
        df_cpc_f["date_value"] = pd.to_datetime(df_cpc_f["date_value"], errors="coerce")
        _s = pd.Timestamp(_dt.combine(sel_start, sel_time_from))
        _e = pd.Timestamp(_dt.combine(sel_end, sel_time_to))
        df_cpc_f = df_cpc_f[(df_cpc_f["date_value"] >= _s) & (df_cpc_f["date_value"] <= _e)]

# Marketing data has no Date column — only Brand/Channel filters apply
df_mkt_f = df_mkt_raw.copy() if not df_mkt_raw.empty else pd.DataFrame()
if not df_mkt_f.empty:
    if sel_brands and "Brand" in df_mkt_f.columns:
        df_mkt_f = df_mkt_f[df_mkt_f["Brand"].isin(sel_brands)]
    if sel_channels and "Channel" in df_mkt_f.columns:
        df_mkt_f = df_mkt_f[df_mkt_f["Channel"].isin(sel_channels)]

# ─── GUARD ───────────────────────────────────────────────────────────────────
if df_s.empty and df_cpc_f.empty:
    st.warning("No data matches the selected filters. Please adjust your selections.")
    st.stop()

# ─── PAGE HEADER ─────────────────────────────────────────────────────────────
st.title("🔄 Consumer Funnels")
st.markdown("Track conversion drop-offs across order, retention, and marketing funnels.")

tab_order, tab_retention, tab_marketing = st.tabs([
    "📦 Order Funnel", "🔄 Retention Funnel", "📣 Marketing Funnel"
])

# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — ORDER FUNNEL
# ═════════════════════════════════════════════════════════════════════════════
with tab_order:
    # Data assembly
    total_imp    = int(df_cpc_f["impressions"].sum()) if "impressions" in df_cpc_f.columns else 0
    total_clicks = int(df_cpc_f["clicks"].sum()) if "clicks" in df_cpc_f.columns else 0
    total_placed = int(df_s["Unique Order ID"].nunique()) if "Unique Order ID" in df_s.columns else len(df_s)
    total_cancelled = len(df_c)

    # Delivered: operations orders with non-null Completed On (Delivered At is often empty)
    _del_col = "Completed On" if "Completed On" in df_o.columns else "Delivered At"
    if _del_col in df_o.columns:
        delivered_mask = df_o[_del_col].notna()
        oid_col = "Unique Order ID" if "Unique Order ID" in df_o.columns else df_o.columns[0]
        total_delivered = int(df_o.loc[delivered_mask, oid_col].nunique()) if oid_col in df_o.columns else int(delivered_mask.sum())
    else:
        total_delivered = max(0, total_placed - total_cancelled)

    ctr = safe_div(total_clicks, total_imp) * 100
    click_to_order = safe_div(total_placed, total_clicks) * 100 if total_clicks else 0
    delivery_rate = safe_div(total_delivered, total_placed) * 100

    # KPI row
    section("Key Metrics")
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1: kpi_card("Impressions", fmt_num(total_imp))
    with k2: kpi_card("Clicks", fmt_num(total_clicks), f"CTR: {fmt_pct(ctr)}")
    with k3: kpi_card("Orders Placed", fmt_num(total_placed), f"Conv: {fmt_pct(click_to_order)}")
    with k4: kpi_card("Delivered", fmt_num(total_delivered), f"Delivery: {fmt_pct(delivery_rate)}", "success")
    with k5: kpi_card("Cancelled", fmt_num(total_cancelled), f"{fmt_pct(safe_div(total_cancelled, total_placed)*100)} of placed", "danger")

    # Main funnel
    section("Order Conversion Funnel")
    funnel_stages = ["Impressions", "Clicks", "Orders Placed", "Orders Delivered"]
    funnel_values = [total_imp, total_clicks, total_placed, total_delivered]
    funnel_colors = [PALETTE[0], PALETTE[1], PALETTE[2], PALETTE[3]]

    fc1, fc2 = st.columns([3, 2])
    with fc1:
        if total_imp > 0:
            fig_funnel = go.Figure(go.Funnel(
                y=funnel_stages, x=funnel_values,
                textinfo="value+percent initial",
                marker=dict(color=funnel_colors),
                connector=dict(line=dict(color="#ccc", width=1)),
            ))
            fig_funnel.update_layout(**chart_layout(height=380, margin=dict(l=10, r=10, t=20, b=20)))
            st.plotly_chart(fig_funnel, use_container_width=True)
        else:
            st.info("No CPC impression data available for the selected filters.")

    with fc2:
        st.markdown("**Stage Conversion Rates**")
        stages_data = [
            ("Impressions → Clicks", ctr),
            ("Clicks → Orders", click_to_order),
            ("Orders → Delivered", delivery_rate),
        ]
        for label, rate in stages_data:
            color = ROAS_GREEN if rate >= 50 else (ROAS_YELLOW if rate >= 10 else ROAS_RED)
            st.markdown(f"**{label}**: <span style='color:{color};font-weight:700'>{fmt_pct(rate)}</span>",
                        unsafe_allow_html=True)
        st.markdown("---")
        st.caption("Impressions & Clicks from CPC advertising data. Orders & Deliveries from actual order data.")

    # Supporting: Conversion by Aggregator
    section("Conversion by Aggregator")
    if not df_cpc_f.empty and "Aggregator" in df_cpc_f.columns:
        agg_grp = df_cpc_f.groupby("Aggregator").agg(
            impressions=("impressions", "sum"), clicks=("clicks", "sum"), orders=("orders", "sum")
        ).reset_index()
        agg_grp["CTR"] = agg_grp.apply(lambda r: safe_div(r["clicks"], r["impressions"]) * 100, axis=1)
        agg_grp["Conv Rate"] = agg_grp.apply(lambda r: safe_div(r["orders"], r["clicks"]) * 100, axis=1)

        ac1, ac2 = st.columns(2)
        with ac1:
            fig_ctr = go.Figure(go.Bar(
                x=agg_grp["Aggregator"], y=agg_grp["CTR"],
                marker_color=[AGG_COLORS.get(a, PRIMARY) for a in agg_grp["Aggregator"]],
                text=agg_grp["CTR"].apply(lambda v: f"{v:.2f}%"), textposition="outside",
                hovertemplate="%{x}<br>CTR: %{y:.2f}%<extra></extra>",
            ))
            fig_ctr.update_layout(**chart_layout(height=320, title="Click-Through Rate by Aggregator",
                                                  yaxis_title="CTR (%)", margin=dict(l=10, r=10, t=40, b=10)))
            st.plotly_chart(fig_ctr, use_container_width=True)

        with ac2:
            fig_conv = go.Figure(go.Bar(
                x=agg_grp["Aggregator"], y=agg_grp["Conv Rate"],
                marker_color=[AGG_COLORS.get(a, PRIMARY) for a in agg_grp["Aggregator"]],
                text=agg_grp["Conv Rate"].apply(lambda v: f"{v:.2f}%"), textposition="outside",
                hovertemplate="%{x}<br>Conv: %{y:.2f}%<extra></extra>",
            ))
            fig_conv.update_layout(**chart_layout(height=320, title="Conversion Rate by Aggregator",
                                                    yaxis_title="Conversion Rate (%)", margin=dict(l=10, r=10, t=40, b=10)))
            st.plotly_chart(fig_conv, use_container_width=True)
    else:
        st.info("No CPC data available for aggregator breakdown.")

    # Supporting: Daily Conversion Trend
    section("Daily Conversion Trend")
    if not df_cpc_f.empty and "date_value" in df_cpc_f.columns:
        daily_cpc = df_cpc_f.groupby("date_value").agg(
            impressions=("impressions", "sum"), clicks=("clicks", "sum"), orders=("orders", "sum")
        ).reset_index().sort_values("date_value")
        daily_cpc["CTR"] = daily_cpc.apply(lambda r: safe_div(r["clicks"], r["impressions"]) * 100, axis=1)
        daily_cpc["Conv Rate"] = daily_cpc.apply(lambda r: safe_div(r["orders"], r["clicks"]) * 100, axis=1)

        fig_trend = make_subplots(specs=[[{"secondary_y": True}]])
        fig_trend.add_trace(go.Scatter(
            x=daily_cpc["date_value"], y=daily_cpc["CTR"],
            name="CTR (%)", line=dict(color=PRIMARY, width=2),
            hovertemplate="%{x}<br>CTR: %{y:.2f}%<extra></extra>",
        ), secondary_y=False)
        fig_trend.add_trace(go.Scatter(
            x=daily_cpc["date_value"], y=daily_cpc["Conv Rate"],
            name="Conv Rate (%)", line=dict(color=SECONDARY, width=2),
            hovertemplate="%{x}<br>Conv: %{y:.2f}%<extra></extra>",
        ), secondary_y=True)
        fig_trend.update_layout(**chart_layout(height=350, legend=dict(orientation="h", y=1.05),
                                                hovermode="x unified", margin=dict(l=10, r=10, t=30, b=10)))
        fig_trend.update_yaxes(title_text="CTR (%)", secondary_y=False)
        fig_trend.update_yaxes(title_text="Conversion Rate (%)", secondary_y=True)
        st.plotly_chart(fig_trend, use_container_width=True)

    # Drop-off by Brand (top 15)
    section("Order Drop-off by Brand (Top 15)")
    if "Brand" in df_s.columns and not df_s.empty:
        oid_col_s = "Unique Order ID" if "Unique Order ID" in df_s.columns else "Order ID"
        brand_placed = df_s.groupby("Brand")[oid_col_s].nunique().reset_index(name="Placed")
        _del_col_b = "Completed On" if "Completed On" in df_o.columns else "Delivered At"
        if _del_col_b in df_o.columns and "Brand" in df_o.columns:
            oid_col_o = "Unique Order ID" if "Unique Order ID" in df_o.columns else df_o.columns[0]
            brand_delivered = df_o[df_o[_del_col_b].notna()].groupby("Brand")[oid_col_o].nunique().reset_index(name="Delivered")
            brand_drop = brand_placed.merge(brand_delivered, on="Brand", how="left").fillna(0)
        else:
            brand_drop = brand_placed.copy()
            brand_drop["Delivered"] = brand_drop["Placed"] - (
                df_c.groupby("Brand").size().reindex(brand_drop["Brand"]).fillna(0).values if "Brand" in df_c.columns else 0
            )
        brand_drop = brand_drop.nlargest(15, "Placed").sort_values("Placed", ascending=True)

        fig_drop = go.Figure()
        fig_drop.add_trace(go.Bar(y=brand_drop["Brand"], x=brand_drop["Placed"], name="Placed",
                                   orientation="h", marker_color=PRIMARY, opacity=0.7))
        fig_drop.add_trace(go.Bar(y=brand_drop["Brand"], x=brand_drop["Delivered"], name="Delivered",
                                   orientation="h", marker_color=SECONDARY, opacity=0.7))
        fig_drop.update_layout(**chart_layout(height=450, barmode="group",
                                              legend=dict(orientation="h", y=1.05),
                                              xaxis_title="Orders", margin=dict(l=10, r=10, t=30, b=10)))
        st.plotly_chart(fig_drop, use_container_width=True)

# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — RETENTION FUNNEL
# ═════════════════════════════════════════════════════════════════════════════
with tab_retention:
    if df_s.empty:
        st.warning("No order data available for retention analysis.")
        st.stop()

    # Customer segmentation
    df_ret = df_s.copy()

    def get_customer_id(row):
        tel = str(row.get("Telephone", "")).strip()
        if tel and tel not in ("", "nan", "None"):
            return tel
        return str(row.get("Customer Name", "")).strip()

    df_ret["customer_id"] = df_ret.apply(get_customer_id, axis=1)
    df_ret = df_ret[df_ret["customer_id"].str.strip() != ""]

    if df_ret.empty:
        st.warning("No customer-identifiable orders found.")
        st.stop()

    order_id_col = "Unique Order ID" if "Unique Order ID" in df_ret.columns else "customer_id"
    ref_date = pd.to_datetime(df_ret["Received At"]).max()

    cust = df_ret.groupby("customer_id").agg(
        order_count=(order_id_col, "nunique"),
        total_spend=("Net Sales", "sum") if "Net Sales" in df_ret.columns else ("Total(Receipt Total)", "sum"),
        first_order=("Received At", "min"),
        last_order=("Received At", "max"),
    ).reset_index()
    cust["recency_days"] = (ref_date - pd.to_datetime(cust["last_order"])).dt.days

    def assign_segment(row):
        if row["recency_days"] > 60 and row["order_count"] >= 2:
            return "Churned"
        if row["recency_days"] > 30 and row["order_count"] >= 2:
            return "At Risk"
        if row["order_count"] >= 4:
            return "Loyal"
        if row["order_count"] >= 2:
            return "Repeat"
        return "New"

    cust["segment"] = cust.apply(assign_segment, axis=1)

    total_cust = len(cust)
    seg_counts = cust["segment"].value_counts()
    n_new     = seg_counts.get("New", 0)
    n_repeat  = seg_counts.get("Repeat", 0)
    n_loyal   = seg_counts.get("Loyal", 0)
    n_atrisk  = seg_counts.get("At Risk", 0)
    n_churned = seg_counts.get("Churned", 0)

    # KPIs
    section("Customer Retention Metrics")
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1: kpi_card("Total Customers", fmt_num(total_cust))
    with k2: kpi_card("New", fmt_num(n_new), f"{fmt_pct(safe_div(n_new, total_cust)*100)} of total")
    with k3: kpi_card("Repeat", fmt_num(n_repeat), f"{fmt_pct(safe_div(n_repeat, total_cust)*100)} of total")
    with k4: kpi_card("Loyal", fmt_num(n_loyal), f"{fmt_pct(safe_div(n_loyal, total_cust)*100)} — 4+ orders", "success")
    with k5: kpi_card("At Risk + Churned", fmt_num(n_atrisk + n_churned),
                       f"At Risk: {n_atrisk} | Churned: {n_churned}", "danger")

    # Main funnel
    section("Retention Funnel")
    fc1, fc2 = st.columns([3, 2])
    with fc1:
        funnel_y = ["New", "Repeat", "Loyal"]
        funnel_x = [n_new, n_repeat, n_loyal]
        fig_ret = go.Figure(go.Funnel(
            y=funnel_y, x=funnel_x,
            textinfo="value+percent initial",
            marker=dict(color=[SEG_COLORS["New"], SEG_COLORS["Repeat"], SEG_COLORS["Loyal"]]),
            connector=dict(line=dict(color="#ccc", width=1)),
        ))
        fig_ret.update_layout(**chart_layout(height=360, margin=dict(l=10, r=10, t=20, b=20)))
        st.plotly_chart(fig_ret, use_container_width=True)

    with fc2:
        st.markdown("**Conversion Rates**")
        new_to_repeat = safe_div(n_repeat + n_loyal + n_atrisk + n_churned, total_cust) * 100
        repeat_to_loyal = safe_div(n_loyal, n_repeat + n_loyal + n_atrisk + n_churned) * 100 if (n_repeat + n_loyal + n_atrisk + n_churned) > 0 else 0
        st.markdown(f"**New → Repeat+**: <span style='color:{ROAS_GREEN if new_to_repeat >= 30 else ROAS_YELLOW};font-weight:700'>{fmt_pct(new_to_repeat)}</span>",
                    unsafe_allow_html=True)
        st.markdown(f"**Repeat+ → Loyal**: <span style='color:{ROAS_GREEN if repeat_to_loyal >= 20 else ROAS_YELLOW};font-weight:700'>{fmt_pct(repeat_to_loyal)}</span>",
                    unsafe_allow_html=True)
        st.markdown("---")
        kpi_card("At Risk", fmt_num(n_atrisk), f"Last order 30-60 days ago", "warning")
        kpi_card("Churned", fmt_num(n_churned), f"Last order 60+ days ago", "danger")

    # Revenue by Segment
    section("Revenue by Customer Segment")
    spend_col = "Net Sales" if "Net Sales" in df_ret.columns else "Total(Receipt Total)"
    seg_rev = cust.groupby("segment")["total_spend"].sum().reindex(
        ["New", "Repeat", "Loyal", "At Risk", "Churned"]
    ).fillna(0)

    fig_seg_rev = go.Figure(go.Bar(
        x=seg_rev.values, y=seg_rev.index, orientation="h",
        marker_color=[SEG_COLORS.get(s, PRIMARY) for s in seg_rev.index],
        text=[fmt_aed(v) for v in seg_rev.values], textposition="outside",
        hovertemplate="%{y}<br>Revenue: AED %{x:,.0f}<extra></extra>",
    ))
    fig_seg_rev.update_layout(**chart_layout(height=320, xaxis_title="Revenue (AED)",
                                             margin=dict(l=10, r=10, t=20, b=10)))
    st.plotly_chart(fig_seg_rev, use_container_width=True)

    # Retention Trend (weekly new vs repeat)
    section("Weekly New vs Returning Customers")
    if "Received At" in df_ret.columns:
        df_ret["_week"] = pd.to_datetime(df_ret["Received At"]).dt.to_period("W").dt.start_time
        # Determine first-order week per customer
        first_weeks = df_ret.groupby("customer_id")["_week"].min().reset_index(name="first_week")
        weekly_orders = df_ret.merge(first_weeks, on="customer_id")
        weekly_orders["cust_type"] = np.where(
            weekly_orders["_week"] == weekly_orders["first_week"], "New", "Returning"
        )
        wk_trend = weekly_orders.groupby(["_week", "cust_type"])["customer_id"].nunique().reset_index(name="customers")
        wk_pivot = wk_trend.pivot(index="_week", columns="cust_type", values="customers").fillna(0).sort_index()

        fig_wk = go.Figure()
        if "New" in wk_pivot.columns:
            fig_wk.add_trace(go.Bar(x=wk_pivot.index, y=wk_pivot["New"], name="New",
                                     marker_color=SEG_COLORS["New"]))
        if "Returning" in wk_pivot.columns:
            fig_wk.add_trace(go.Bar(x=wk_pivot.index, y=wk_pivot["Returning"], name="Returning",
                                     marker_color=SECONDARY))
        fig_wk.update_layout(**chart_layout(height=350, barmode="stack",
                                            legend=dict(orientation="h", y=1.05),
                                            xaxis_title="Week", yaxis_title="Unique Customers",
                                            margin=dict(l=10, r=10, t=30, b=10)))
        st.plotly_chart(fig_wk, use_container_width=True)

    # CPC Acquisition Split
    section("CPC User Acquisition Split")
    if not df_cpc_f.empty:
        new_orders = df_cpc_f["newuser_orders"].sum() if "newuser_orders" in df_cpc_f.columns else 0
        repeat_orders = df_cpc_f["repeatuser_orders"].sum() if "repeatuser_orders" in df_cpc_f.columns else 0
        lapsed_orders = df_cpc_f["lapseduser_orders"].sum() if "lapseduser_orders" in df_cpc_f.columns else 0

        if new_orders + repeat_orders + lapsed_orders > 0:
            labels = ["New Users", "Repeat Users", "Lapsed Users"]
            values = [new_orders, repeat_orders, lapsed_orders]
            colors = [SEG_COLORS["New"], SEG_COLORS["Repeat"], SEG_COLORS["At Risk"]]

            pc1, pc2 = st.columns([1, 1])
            with pc1:
                fig_acq = go.Figure(go.Pie(
                    labels=labels, values=values,
                    marker=dict(colors=colors),
                    hole=0.45, textinfo="label+percent",
                    hovertemplate="%{label}<br>Orders: %{value:,.0f}<br>%{percent}<extra></extra>",
                ))
                fig_acq.update_layout(**chart_layout(height=350, margin=dict(l=10, r=10, t=20, b=20),
                                                      showlegend=False))
                st.plotly_chart(fig_acq, use_container_width=True)
            with pc2:
                total_acq = new_orders + repeat_orders + lapsed_orders
                kpi_card("New User Orders", fmt_num(new_orders), f"{fmt_pct(safe_div(new_orders, total_acq)*100)} of CPC orders")
                kpi_card("Repeat User Orders", fmt_num(repeat_orders), f"{fmt_pct(safe_div(repeat_orders, total_acq)*100)} of CPC orders")
                kpi_card("Lapsed User Orders", fmt_num(lapsed_orders), f"{fmt_pct(safe_div(lapsed_orders, total_acq)*100)} — reactivated", "warning")
        else:
            st.info("No CPC user acquisition data available.")
    else:
        st.info("No CPC data available for acquisition analysis.")

# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — MARKETING FUNNEL
# ═════════════════════════════════════════════════════════════════════════════
with tab_marketing:
    if df_cpc_f.empty:
        st.warning("No CPC data available for the selected filters.")
        st.stop()

    # Data assembly
    total_spend = df_cpc_f["netbasket_amount"].sum() if "netbasket_amount" in df_cpc_f.columns else 0
    total_imp_m = int(df_cpc_f["impressions"].sum()) if "impressions" in df_cpc_f.columns else 0
    total_clk_m = int(df_cpc_f["clicks"].sum()) if "clicks" in df_cpc_f.columns else 0
    total_ord_m = int(df_cpc_f["orders"].sum()) if "orders" in df_cpc_f.columns else 0
    total_rev_m = df_cpc_f["gmv_local"].sum() if "gmv_local" in df_cpc_f.columns else 0

    ctr_m = safe_div(total_clk_m, total_imp_m) * 100
    conv_m = safe_div(total_ord_m, total_clk_m) * 100
    roas_m = safe_div(total_rev_m, total_spend)

    # KPIs
    section("Marketing Performance")
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1: kpi_card("Ad Spend", fmt_aed(total_spend))
    with k2: kpi_card("Impressions", fmt_num(total_imp_m))
    with k3: kpi_card("CTR", fmt_pct(ctr_m), f"{fmt_num(total_clk_m)} clicks")
    with k4: kpi_card("Conversion Rate", fmt_pct(conv_m), f"{fmt_num(total_ord_m)} orders")
    roas_c = "success" if roas_m >= 3 else ("warning" if roas_m >= 1 else "danger")
    with k5: kpi_card("ROAS", f"{roas_m:.2f}x", f"Revenue: {fmt_aed(total_rev_m)}", roas_c)

    # Main funnel (counts only — revenue shown separately)
    section("Marketing Conversion Funnel")
    mc1, mc2 = st.columns([3, 2])
    with mc1:
        fig_mkt = go.Figure(go.Funnel(
            y=["Impressions", "Clicks", "Orders"],
            x=[total_imp_m, total_clk_m, total_ord_m],
            textinfo="value+percent initial",
            marker=dict(color=[PRIMARY, SECONDARY, ACCENT]),
            connector=dict(line=dict(color="#ccc", width=1)),
        ))
        fig_mkt.update_layout(**chart_layout(height=350, margin=dict(l=10, r=10, t=20, b=20)))
        st.plotly_chart(fig_mkt, use_container_width=True)

    with mc2:
        st.markdown("**Revenue & Efficiency**")
        kpi_card("Revenue from Ads", fmt_aed(total_rev_m), f"ROAS: {roas_m:.2f}x", roas_c)
        cpc_val = safe_div(total_spend, total_clk_m)
        cpo_val = safe_div(total_spend, total_ord_m)
        kpi_card("Cost Per Click", fmt_aed(cpc_val), f"From {fmt_num(total_clk_m)} clicks")
        kpi_card("Cost Per Order", fmt_aed(cpo_val), f"From {fmt_num(total_ord_m)} orders")

    # Funnel by Aggregator
    section("Funnel by Aggregator")
    if "Aggregator" in df_cpc_f.columns:
        aggs = df_cpc_f["Aggregator"].dropna().unique().tolist()
        agg_cols = st.columns(min(len(aggs), 4))
        for i, agg_name in enumerate(sorted(aggs)):
            agg_data = df_cpc_f[df_cpc_f["Aggregator"] == agg_name]
            a_imp = int(agg_data["impressions"].sum())
            a_clk = int(agg_data["clicks"].sum())
            a_ord = int(agg_data["orders"].sum())
            a_rev = agg_data["gmv_local"].sum()
            a_spend = agg_data["netbasket_amount"].sum()
            a_roas = safe_div(a_rev, a_spend)

            with agg_cols[i % len(agg_cols)]:
                st.markdown(f"**{agg_name}**")
                fig_a = go.Figure(go.Funnel(
                    y=["Impressions", "Clicks", "Orders"],
                    x=[a_imp, a_clk, a_ord],
                    textinfo="value+percent initial",
                    marker=dict(color=[AGG_COLORS.get(agg_name, PRIMARY)] * 3),
                    connector=dict(line=dict(color="#ccc", width=1)),
                ))
                fig_a.update_layout(**chart_layout(height=280, margin=dict(l=5, r=5, t=10, b=10),
                                                    showlegend=False))
                st.plotly_chart(fig_a, use_container_width=True)
                st.markdown(f"ROAS: **{a_roas:.2f}x** | Spend: **{fmt_aed(a_spend)}**")

    # ROAS by Brand
    section("ROAS by Brand")
    if "Brand" in df_cpc_f.columns:
        brand_roas = df_cpc_f.groupby("Brand").agg(
            spend=("netbasket_amount", "sum"), revenue=("gmv_local", "sum")
        ).reset_index()
        brand_roas["ROAS"] = brand_roas.apply(lambda r: safe_div(r["revenue"], r["spend"]), axis=1)
        brand_roas = brand_roas[brand_roas["spend"] > 0].sort_values("ROAS", ascending=True)

        if not brand_roas.empty:
            fig_br = go.Figure(go.Bar(
                y=brand_roas["Brand"], x=brand_roas["ROAS"], orientation="h",
                marker_color=[roas_color(v) for v in brand_roas["ROAS"]],
                text=brand_roas["ROAS"].apply(lambda v: f"{v:.2f}x"), textposition="outside",
                hovertemplate="%{y}<br>ROAS: %{x:.2f}x<extra></extra>",
            ))
            fig_br.update_layout(**chart_layout(height=max(320, len(brand_roas) * 28),
                                                 xaxis_title="ROAS", margin=dict(l=10, r=10, t=20, b=10)))
            st.plotly_chart(fig_br, use_container_width=True)

    # Spend Efficiency Trend
    section("Spend Efficiency Trend")
    if "date_value" in df_cpc_f.columns:
        daily_mkt = df_cpc_f.groupby("date_value").agg(
            spend=("netbasket_amount", "sum"), revenue=("gmv_local", "sum")
        ).reset_index().sort_values("date_value")
        daily_mkt["ROAS"] = daily_mkt.apply(lambda r: safe_div(r["revenue"], r["spend"]), axis=1)

        fig_eff = make_subplots(specs=[[{"secondary_y": True}]])
        fig_eff.add_trace(go.Bar(
            x=daily_mkt["date_value"], y=daily_mkt["spend"], name="Ad Spend (AED)",
            marker_color=PRIMARY, opacity=0.6,
            hovertemplate="%{x}<br>Spend: AED %{y:,.0f}<extra></extra>",
        ), secondary_y=False)
        fig_eff.add_trace(go.Scatter(
            x=daily_mkt["date_value"], y=daily_mkt["ROAS"], name="ROAS",
            line=dict(color=SECONDARY, width=2.5),
            hovertemplate="%{x}<br>ROAS: %{y:.2f}x<extra></extra>",
        ), secondary_y=True)
        fig_eff.update_layout(**chart_layout(height=380, legend=dict(orientation="h", y=1.05),
                                              hovermode="x unified", margin=dict(l=10, r=60, t=30, b=10)))
        fig_eff.update_yaxes(title_text="Ad Spend (AED)", secondary_y=False)
        fig_eff.update_yaxes(title_text="ROAS", secondary_y=True)
        st.plotly_chart(fig_eff, use_container_width=True)
