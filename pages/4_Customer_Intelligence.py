"""
Customer Intelligence Page
Cloud Kitchen Analytics Dashboard
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from utils.data_loader import (
    load_customers,
    load_sales_orders,
    get_all_brands,
    get_all_locations,
    get_all_channels,
)

# ── PAGE CONFIG ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Customer Intelligence", page_icon="👥", layout="wide")

# ── CONSTANTS ─────────────────────────────────────────────────────────────────
COLORS    = ["#FF6B35", "#4ECDC4", "#FFE66D", "#FF6B6B", "#845EC2", "#00C9A7"]
PRIMARY   = COLORS[0]
SECONDARY = COLORS[1]
TEMPLATE  = "plotly_white"
BG        = "rgba(255,255,255,0)"
SEG_ORDER = ["Champions", "Loyal", "At Risk", "New", "One-time"]


# ── HELPERS ───────────────────────────────────────────────────────────────────

def fmt_currency(val: float, decimals: int = 0) -> str:
    if abs(val) >= 1_000_000:
        return f"AED {val/1_000_000:.2f}M"
    if abs(val) >= 1_000:
        return f"AED {val/1_000:.1f}K"
    return f"AED {val:,.{decimals}f}"


def fmt_num(val: float) -> str:
    if abs(val) >= 1_000_000:
        return f"{val/1_000_000:.2f}M"
    if abs(val) >= 1_000:
        return f"{val/1_000:.1f}K"
    return f"{val:,.0f}"


def extract_area(address: str) -> str:
    """Best-effort area extraction from a Dubai address string."""
    if not isinstance(address, str) or not address.strip():
        return "Unknown"
    parts = [p.strip() for p in address.replace(",", " - ").split(" - ") if p.strip()]
    if len(parts) >= 2:
        return parts[-2]
    if len(parts) == 1:
        return parts[0]
    return "Unknown"


def assign_rfm_segment(row) -> str:
    r, f = row["R_score"], row["F_score"]
    m    = row["M_score"]
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    if r >= 3 and f >= 3:
        return "Loyal"
    if r <= 2 and f >= 3:
        return "At Risk"
    if r >= 4 and f == 1:
        return "New"
    return "One-time"


def qcut_safe(series, q, labels):
    try:
        return pd.qcut(series, q=q, labels=labels, duplicates="drop")
    except Exception:
        return pd.Series([labels[len(labels) // 2]] * len(series), index=series.index)


# ── TITLE ─────────────────────────────────────────────────────────────────────
st.title("👥 Customer Intelligence")
st.markdown(
    "Deep-dive into customer behaviour, segmentation, loyalty, and lifetime value "
    "across brands and channels."
)

# ── DATA LOAD ─────────────────────────────────────────────────────────────────
with st.spinner("Loading data…"):
    df_orders_raw = load_sales_orders()
    df_customers  = load_customers()

all_brands    = get_all_brands(df_orders_raw)
all_locations = get_all_locations(df_orders_raw)

# ── SIDEBAR FILTERS ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")
    sel_brands = st.multiselect("Brand",    options=all_brands,    default=[], placeholder="All brands")
    sel_locations = st.multiselect("Location", options=all_locations, default=[], placeholder="All locations")
    all_channels_ci = sorted(df_orders_raw["Channel"].dropna().unique().tolist()) if "Channel" in df_orders_raw.columns else []
    sel_channels_ci = st.multiselect("Channel", options=all_channels_ci, default=[], placeholder="All channels")
    all_cuisines_ci = sorted(df_orders_raw["Cuisine"].dropna().unique().tolist()) if "Cuisine" in df_orders_raw.columns else []
    sel_cuisines_ci = st.multiselect("Cuisine", options=all_cuisines_ci, default=[], placeholder="All cuisines")
    st.divider()
    st.markdown("**Date Range**")
    _dates_ci = df_orders_raw["Received At"].dropna() if "Received At" in df_orders_raw.columns else pd.Series(dtype="datetime64[ns]")
    _min_ci = _dates_ci.min().date() if not _dates_ci.empty else None
    _max_ci = _dates_ci.max().date() if not _dates_ci.empty else None
    sel_start_ci = sel_end_ci = None
    if _min_ci and _max_ci:
        _dr_ci = st.date_input("Period", value=(_min_ci, _max_ci), min_value=_min_ci, max_value=_max_ci, label_visibility="collapsed")
        sel_start_ci, sel_end_ci = (_dr_ci[0], _dr_ci[1]) if isinstance(_dr_ci, (list, tuple)) and len(_dr_ci) == 2 else (_min_ci, _max_ci)
    st.markdown("**Time Range**")
    from datetime import time as _time
    _tc1_ci, _tc2_ci = st.columns(2)
    with _tc1_ci:
        sel_time_from_ci = st.time_input("From", value=_time(0, 0), step=1800, key="tf_ci")
    with _tc2_ci:
        sel_time_to_ci = st.time_input("To", value=_time(23, 59), step=1800, key="tt_ci")
    st.divider()
    st.caption("Leave blank to include all values.")

# ── FILTER APPLICATION ────────────────────────────────────────────────────────
df = df_orders_raw.copy()
if sel_brands    and "Brand"    in df.columns: df = df[df["Brand"].isin(sel_brands)]
if sel_locations and "Location" in df.columns: df = df[df["Location"].isin(sel_locations)]
if sel_channels_ci and "Channel" in df.columns: df = df[df["Channel"].isin(sel_channels_ci)]
if sel_cuisines_ci and "Cuisine" in df.columns: df = df[df["Cuisine"].isin(sel_cuisines_ci)]
if sel_start_ci and sel_end_ci:
    from datetime import datetime as _dt
    _s = pd.Timestamp(_dt.combine(sel_start_ci, sel_time_from_ci))
    _e = pd.Timestamp(_dt.combine(sel_end_ci, sel_time_to_ci))
    if "Received At" in df.columns:
        df = df[(df["Received At"] >= _s) & (df["Received At"] <= _e)]
    elif "Date" in df.columns:
        df["_date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
        df = df[(df["_date"] >= sel_start_ci) & (df["_date"] <= sel_end_ci)]
        df = df.drop(columns=["_date"])

if df.empty:
    st.warning("No data matches the selected filters. Please adjust your selections.")
    st.stop()

# ── CUSTOMER KEY ──────────────────────────────────────────────────────────────
def get_customer_id(row):
    tel = str(row.get("Telephone", "")).strip()
    if tel and tel not in ("", "nan", "None"):
        return tel
    return str(row.get("Customer Name", "")).strip()

df = df.copy()
df["customer_id"] = df.apply(get_customer_id, axis=1)
df = df[df["customer_id"].str.strip() != ""]

order_id_col = "Unique Order ID" if "Unique Order ID" in df.columns else "customer_id"
ref_date     = pd.to_datetime(df["Received At"]).max()

# ── CUSTOMER-LEVEL AGGREGATION ────────────────────────────────────────────────
agg_dict = {
    "first_order":  ("Received At", "min"),
    "last_order":   ("Received At", "max"),
    "order_count":  (order_id_col,  "nunique"),
    "total_spend":  ("Net Sales",   "sum"),
    "avg_spend":    ("Net Sales",   "mean"),
    "brand_set":    ("Brand",       lambda x: set(x.dropna())),
}
if "Channel" in df.columns:
    agg_dict["channel_set"] = ("Channel", lambda x: set(x.dropna()))

cust_agg = df.groupby("customer_id").agg(**agg_dict).reset_index()

cust_agg["first_order"]  = pd.to_datetime(cust_agg["first_order"])
cust_agg["last_order"]   = pd.to_datetime(cust_agg["last_order"])
cust_agg["recency_days"] = (ref_date - cust_agg["last_order"]).dt.days
cust_agg["num_brands"]   = cust_agg["brand_set"].apply(len)
if "channel_set" in cust_agg.columns:
    cust_agg["num_channels"] = cust_agg["channel_set"].apply(len)
else:
    cust_agg["num_channels"] = 0

# RFM
cust_agg["R_score"] = qcut_safe(-cust_agg["recency_days"], q=5, labels=[1,2,3,4,5]).astype(int)
cust_agg["F_score"] = qcut_safe( cust_agg["order_count"],  q=5, labels=[1,2,3,4,5]).astype(int)
cust_agg["M_score"] = qcut_safe( cust_agg["total_spend"],  q=5, labels=[1,2,3,4,5]).astype(int)
cust_agg["segment"] = cust_agg.apply(assign_rfm_segment, axis=1)
SEG_COLORS = dict(zip(SEG_ORDER, COLORS))

# ── KPI ROW ───────────────────────────────────────────────────────────────────
st.subheader("Key Metrics")

total_unique = cust_agg["customer_id"].nunique()
avg_orders   = cust_agg["order_count"].mean()
avg_revenue  = cust_agg["total_spend"].mean()
repeat_rate  = (cust_agg["order_count"] > 1).sum() / total_unique * 100 if total_unique else 0
clv_estimate = cust_agg["total_spend"].mean()

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Unique Customers", fmt_num(total_unique))
k2.metric("Avg Orders / Customer",  f"{avg_orders:.1f}")
k3.metric("Avg Revenue / Customer", fmt_currency(avg_revenue, 2))
k4.metric("Repeat Customer Rate",   f"{repeat_rate:.1f}%")
k5.metric("Avg Lifetime Value",     fmt_currency(clv_estimate, 2))

st.divider()

# ── SECTION 1: NEW vs RETURNING ───────────────────────────────────────────────
st.subheader("New vs Returning Customers")

if "Received At" in df.columns:
    df_ts = df.copy()
    df_ts["Received At"] = pd.to_datetime(df_ts["Received At"])
    df_ts["iso_week"]    = df_ts["Received At"].dt.to_period("W")
    first_week           = df_ts.groupby("customer_id")["Received At"].min().dt.to_period("W").rename("first_week")
    df_ts                = df_ts.join(first_week, on="customer_id")
    df_ts["cust_type"]   = np.where(df_ts["iso_week"] == df_ts["first_week"], "New", "Returning")

    weekly_type = (
        df_ts.groupby(["iso_week", "cust_type"])["customer_id"]
        .nunique().reset_index(name="customers")
    )
    weekly_type["week_str"] = weekly_type["iso_week"].astype(str)
    weeks_sorted = sorted(weekly_type["week_str"].unique())

    new_vals, ret_vals, pct_ret = [], [], []
    for w in weeks_sorted:
        wdf = weekly_type[weekly_type["week_str"] == w]
        n = int(wdf.loc[wdf["cust_type"] == "New",       "customers"].sum())
        r = int(wdf.loc[wdf["cust_type"] == "Returning", "customers"].sum())
        new_vals.append(n); ret_vals.append(r)
        pct_ret.append(r / (n + r) * 100 if (n + r) > 0 else 0)

    fig_nr = make_subplots(specs=[[{"secondary_y": True}]])
    fig_nr.add_trace(go.Bar(x=weeks_sorted, y=new_vals, name="New",       marker_color=SECONDARY, opacity=0.85), secondary_y=False)
    fig_nr.add_trace(go.Bar(x=weeks_sorted, y=ret_vals, name="Returning", marker_color=PRIMARY,   opacity=0.85), secondary_y=False)
    fig_nr.add_trace(go.Scatter(x=weeks_sorted, y=pct_ret, name="% Returning",
                                mode="lines+markers", line=dict(color=COLORS[2], width=2), marker=dict(size=5)), secondary_y=True)
    fig_nr.update_layout(barmode="stack", template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
                         height=360, margin=dict(l=0,r=0,t=10,b=0), xaxis_title="Week",
                         legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig_nr.update_yaxes(title_text="Unique Customers", secondary_y=False)
    fig_nr.update_yaxes(title_text="% Returning", secondary_y=True, ticksuffix="%", range=[0,100], showgrid=False)
    st.plotly_chart(fig_nr, use_container_width=True)

    nr1, nr2, nr3 = st.columns(3)
    nr1.metric("New Customer Appearances",       fmt_num(sum(new_vals)))
    nr2.metric("Returning Customer Appearances", fmt_num(sum(ret_vals)))
    nr3.metric("Avg Weekly % Returning",         f"{np.mean(pct_ret):.1f}%")
else:
    st.info("Timestamp data not available.")

st.divider()

# ── SECTION 2: RFM SEGMENTATION ───────────────────────────────────────────────
st.subheader("Customer Segmentation (RFM)")

seg_counts = cust_agg["segment"].value_counts().reset_index()
seg_counts.columns = ["Segment", "Customers"]
seg_counts["color"] = seg_counts["Segment"].map(SEG_COLORS)
seg_present = [s for s in SEG_ORDER if s in seg_counts["Segment"].values]
seg_counts  = seg_counts.set_index("Segment").reindex(seg_present).reset_index()

sc1, sc2 = st.columns([1, 2])

with sc1:
    fig_donut = go.Figure(go.Pie(
        labels=seg_counts["Segment"], values=seg_counts["Customers"],
        hole=0.55, marker=dict(colors=seg_counts["color"].tolist()),
        textinfo="label+percent", textfont=dict(size=12),
        hovertemplate="%{label}: %{value:,} customers (%{percent})<extra></extra>",
    ))
    fig_donut.update_layout(template=TEMPLATE, paper_bgcolor=BG, height=340,
                            margin=dict(l=0,r=0,t=10,b=0), showlegend=False)
    st.plotly_chart(fig_donut, use_container_width=True)

with sc2:
    seg_detail = (
        cust_agg.groupby("segment").agg(
            Customers     = ("customer_id",  "count"),
            Avg_Recency   = ("recency_days", "mean"),
            Avg_Orders    = ("order_count",  "mean"),
            Avg_Spend     = ("total_spend",  "mean"),
            Total_Revenue = ("total_spend",  "sum"),
        ).reset_index()
    )
    seg_detail.columns = ["Segment","Customers","Avg Recency (days)","Avg Orders","Avg Spend (AED)","Total Revenue (AED)"]
    seg_detail = seg_detail.set_index("Segment").reindex(
        [s for s in SEG_ORDER if s in seg_detail["Segment"].values if s in seg_detail.index]
    ).reset_index()
    seg_detail["Avg Recency (days)"]  = seg_detail["Avg Recency (days)"].round(0).astype("Int64")
    seg_detail["Avg Orders"]          = seg_detail["Avg Orders"].round(1)
    seg_detail["Avg Spend (AED)"]     = seg_detail["Avg Spend (AED)"].round(2)
    seg_detail["Total Revenue (AED)"] = seg_detail["Total Revenue (AED)"].round(2)
    st.dataframe(seg_detail, use_container_width=True, hide_index=True)

st.divider()

# ── SECTION 3: ORDER FREQUENCY ────────────────────────────────────────────────
st.subheader("Order Frequency")

of1, of2 = st.columns(2)

with of1:
    fig_hist = go.Figure(go.Histogram(
        x=cust_agg["order_count"].clip(upper=20), nbinsx=20,
        marker_color=PRIMARY, opacity=0.85,
        hovertemplate="Orders: %{x}<br>Customers: %{y}<extra></extra>",
    ))
    fig_hist.update_layout(
        template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG, height=320,
        margin=dict(l=0,r=0,t=10,b=0), xaxis_title="Orders per Customer (capped at 20)",
        yaxis_title="# Customers", title="Order Count Distribution", title_font=dict(size=13),
    )
    st.plotly_chart(fig_hist, use_container_width=True)

with of2:
    if "Received At" in df.columns:
        df_w = df.copy()
        df_w["Received At"] = pd.to_datetime(df_w["Received At"])
        df_w["iso_week"]    = df_w["Received At"].dt.to_period("W")
        wf = df_w.groupby("iso_week").agg(
            unique_orders = (order_id_col, "nunique"),
            unique_custs  = ("customer_id", "nunique"),
        ).reset_index()
        wf["week_str"]        = wf["iso_week"].astype(str)
        wf["orders_per_cust"] = wf["unique_orders"] / wf["unique_custs"].replace(0, np.nan)
        fig_ft = go.Figure(go.Scatter(
            x=wf["week_str"], y=wf["orders_per_cust"], mode="lines+markers",
            line=dict(color=SECONDARY, width=2), marker=dict(size=5),
            fill="tozeroy", fillcolor="rgba(78,205,196,0.12)",
            hovertemplate="Week: %{x}<br>Orders/Customer: %{y:.2f}<extra></extra>",
        ))
        fig_ft.update_layout(
            template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG, height=320,
            margin=dict(l=0,r=0,t=10,b=0), xaxis_title="Week",
            yaxis_title="Orders per Customer", title="Avg Order Frequency per Week",
            title_font=dict(size=13),
        )
        st.plotly_chart(fig_ft, use_container_width=True)
    else:
        st.info("Timestamp data not available.")

st.markdown("**Power Users — Top 20 Customers by Order Count**")
top20 = (
    cust_agg.nlargest(20, "order_count")
    [["customer_id","order_count","total_spend","recency_days","num_brands","segment"]]
    .rename(columns={
        "customer_id":"Customer ID", "order_count":"Orders",
        "total_spend":"Total Spend (AED)", "recency_days":"Recency (days)",
        "num_brands":"Brands Ordered From", "segment":"Segment",
    }).reset_index(drop=True)
)
top20["Total Spend (AED)"] = top20["Total Spend (AED)"].round(2)
st.dataframe(top20, use_container_width=True, hide_index=True)

st.divider()

# ── SECTION 4: REVENUE PER CUSTOMER ──────────────────────────────────────────
st.subheader("Revenue per Customer")

rc1, rc2 = st.columns(2)

with rc1:
    if "Brand" in df.columns:
        brc = (
            df.groupby("Brand").agg(unique_custs=("customer_id","nunique"), total_rev=("Net Sales","sum"))
            .reset_index()
        )
        brc["avg_rev"] = brc["total_rev"] / brc["unique_custs"].replace(0, np.nan)
        brc = brc.sort_values("avg_rev", ascending=True)
        fig_brc = go.Figure(go.Bar(
            x=brc["avg_rev"], y=brc["Brand"], orientation="h", marker_color=PRIMARY,
            text=[f"AED {v:.0f}" for v in brc["avg_rev"]], textposition="outside",
            textfont=dict(color="white", size=11),
            hovertemplate="%{y}: AED %{x:.2f}<extra></extra>",
        ))
        fig_brc.update_layout(
            template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
            height=max(300, len(brc)*30), margin=dict(l=0,r=70,t=10,b=0),
            xaxis_title="Avg Revenue per Customer (AED)",
            title="Avg Spend per Customer by Brand", title_font=dict(size=13),
        )
        st.plotly_chart(fig_brc, use_container_width=True)

with rc2:
    cs = cust_agg.sort_values("total_spend", ascending=False).reset_index(drop=True)
    cs["cumrev"]        = cs["total_spend"].cumsum()
    tot_rev             = cs["total_spend"].sum()
    cs["cum_pct_rev"]   = cs["cumrev"] / tot_rev * 100
    cs["cum_pct_custs"] = (np.arange(1, len(cs)+1) / len(cs)) * 100
    idx10               = min(int(len(cs)*0.10), len(cs)-1)
    idx20               = min(int(len(cs)*0.20), len(cs)-1)
    p10                 = cs["cum_pct_rev"].iloc[idx10]
    p20                 = cs["cum_pct_rev"].iloc[idx20]

    fig_par = go.Figure()
    fig_par.add_trace(go.Scatter(
        x=cs["cum_pct_custs"], y=cs["cum_pct_rev"], mode="lines",
        line=dict(color=PRIMARY, width=2), fill="tozeroy",
        fillcolor="rgba(255,107,53,0.15)", name="Cumulative Revenue",
        hovertemplate="Top %{x:.1f}% → %{y:.1f}% revenue<extra></extra>",
    ))
    fig_par.add_vline(x=10, line_dash="dash", line_color=COLORS[2], line_width=1.5,
                      annotation_text=f"Top 10% → {p10:.0f}% rev",
                      annotation_font_color=COLORS[2], annotation_position="top right")
    fig_par.add_shape(type="line", x0=0, x1=100, y0=0, y1=100,
                      line=dict(dash="dot", color="rgba(255,255,255,0.3)", width=1))
    fig_par.update_layout(
        template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG, height=340,
        margin=dict(l=0,r=0,t=10,b=0), xaxis_title="% of Customers (ranked by spend)",
        yaxis_title="% of Revenue", title="Revenue Concentration (Pareto)",
        title_font=dict(size=13), showlegend=False,
    )
    st.plotly_chart(fig_par, use_container_width=True)
    st.markdown(
        f"<div style='background:rgba(255,107,53,0.12);border-left:3px solid {PRIMARY};"
        f"padding:10px 14px;border-radius:4px;'>"
        f"Top <b>10%</b> of customers generate <b>{p10:.0f}%</b> of revenue.<br>"
        f"Top <b>20%</b> of customers generate <b>{p20:.0f}%</b> of revenue.</div>",
        unsafe_allow_html=True,
    )

st.divider()

# ── SECTION 5: GEOGRAPHIC ANALYSIS ───────────────────────────────────────────
st.subheader("Geographic Analysis")

if "Address" in df.columns:
    df["area"] = df["Address"].apply(extract_area)
    area_agg = (
        df.groupby("area").agg(
            orders    = (order_id_col, "nunique"),
            revenue   = ("Net Sales",  "sum"),
            customers = ("customer_id","nunique"),
        ).reset_index().sort_values("orders", ascending=False)
    )
    area_agg = area_agg[area_agg["area"] != "Unknown"].head(25)

    ga1, ga2 = st.columns(2)
    with ga1:
        t = area_agg.head(15).sort_values("orders", ascending=True)
        fig_ao = go.Figure(go.Bar(
            x=t["orders"], y=t["area"], orientation="h",
            marker=dict(color=t["orders"], colorscale=[[0,"rgba(255,107,53,0.4)"],[1,PRIMARY]], showscale=False),
            text=t["orders"].apply(lambda v: f"{v:,}"), textposition="outside",
            textfont=dict(color="white", size=10),
            hovertemplate="%{y}: %{x:,} orders<extra></extra>",
        ))
        fig_ao.update_layout(template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
                             height=440, margin=dict(l=0,r=60,t=10,b=0),
                             xaxis_title="Orders", title="Top 15 Areas by Order Volume",
                             title_font=dict(size=13))
        st.plotly_chart(fig_ao, use_container_width=True)

    with ga2:
        t2 = area_agg.head(15).sort_values("revenue", ascending=True)
        fig_ar = go.Figure(go.Bar(
            x=t2["revenue"], y=t2["area"], orientation="h",
            marker=dict(color=t2["revenue"], colorscale=[[0,"rgba(78,205,196,0.4)"],[1,SECONDARY]], showscale=False),
            text=[f"AED {v:,.0f}" for v in t2["revenue"]], textposition="outside",
            textfont=dict(color="white", size=10),
            hovertemplate="%{y}: AED %{x:,.0f}<extra></extra>",
        ))
        fig_ar.update_layout(template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
                             height=440, margin=dict(l=0,r=90,t=10,b=0),
                             xaxis_title="Revenue (AED)", title="Top 15 Areas by Revenue",
                             title_font=dict(size=13))
        st.plotly_chart(fig_ar, use_container_width=True)

    with st.expander("Full Area Table"):
        ad = area_agg.copy()
        ad.columns = ["Area","Orders","Revenue (AED)","Unique Customers"]
        ad["Revenue (AED)"] = ad["Revenue (AED)"].round(2)
        st.dataframe(ad.reset_index(drop=True), use_container_width=True, hide_index=True)
else:
    st.info("Address column not found in orders data.")

st.divider()

# ── SECTION 6: BRAND AFFINITY ─────────────────────────────────────────────────
st.subheader("Brand Affinity")

if "Brand" in df.columns:
    ba1, ba2, ba3 = st.columns(3)

    with ba1:
        cpb = df.groupby("Brand")["customer_id"].nunique().reset_index(name="Unique Customers").sort_values("Unique Customers", ascending=True)
        fig_cpb = go.Figure(go.Bar(
            x=cpb["Unique Customers"], y=cpb["Brand"], orientation="h",
            marker_color=COLORS[4],
            text=cpb["Unique Customers"].apply(lambda v: f"{v:,}"),
            textposition="outside", textfont=dict(color="white", size=10),
        ))
        fig_cpb.update_layout(template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
                              height=max(300, len(cpb)*30), margin=dict(l=0,r=60,t=10,b=0),
                              xaxis_title="Unique Customers", title="Customers per Brand",
                              title_font=dict(size=13))
        st.plotly_chart(fig_cpb, use_container_width=True)

    with ba2:
        mb = cust_agg[cust_agg["num_brands"] > 1]["num_brands"].value_counts().sort_index().reset_index()
        mb.columns = ["Brands","Customers"]
        single_n = int((cust_agg["num_brands"] == 1).sum())
        pl = ["Single Brand"] + [f"{b} Brands" for b in mb["Brands"]]
        pv = [single_n]      + mb["Customers"].tolist()
        fig_mb = go.Figure(go.Pie(
            labels=pl, values=pv, hole=0.5,
            marker=dict(colors=COLORS[:len(pl)]),
            textinfo="label+percent", textfont=dict(size=11),
        ))
        fig_mb.update_layout(template=TEMPLATE, paper_bgcolor=BG, height=320,
                             margin=dict(l=0,r=0,t=10,b=0), showlegend=False,
                             title="Cross-Brand Ordering", title_font=dict(size=13))
        st.plotly_chart(fig_mb, use_container_width=True)
        mp = cust_agg[cust_agg["num_brands"] > 1].shape[0] / total_unique * 100
        st.markdown(
            f"<div style='background:rgba(132,94,194,0.15);border-left:3px solid {COLORS[4]};"
            f"padding:8px 12px;border-radius:4px;'>"
            f"<b>{mp:.1f}%</b> of customers order from multiple brands.</div>",
            unsafe_allow_html=True,
        )

    with ba3:
        bl = df.groupby(["Brand","customer_id"]).agg(orders=(order_id_col,"nunique")).reset_index()
        bls = (
            bl.groupby("Brand").agg(
                Avg_Orders_Per_Customer = ("orders","mean"),
                Median_Orders           = ("orders","median"),
                Pct_Repeat              = ("orders", lambda x: (x>1).mean()*100),
            ).round(2).reset_index().sort_values("Avg_Orders_Per_Customer", ascending=False)
        )
        bls.columns = ["Brand","Avg Orders/Customer","Median Orders","% Repeat Buyers"]
        st.markdown("**Brand Loyalty Matrix**")
        st.dataframe(bls, use_container_width=True, hide_index=True)

st.divider()

# ── SECTION 7: CHANNEL PREFERENCES ───────────────────────────────────────────
st.subheader("Channel Preferences")

if "Channel" in df.columns:
    ch1, ch2 = st.columns(2)

    with ch1:
        cc = df.groupby("Channel")["customer_id"].nunique().reset_index(name="Unique Customers").sort_values("Unique Customers", ascending=False)
        fig_cc = go.Figure(go.Pie(
            labels=cc["Channel"], values=cc["Unique Customers"],
            hole=0.5, marker=dict(colors=COLORS[:len(cc)]),
            textinfo="label+percent", textfont=dict(size=12),
        ))
        fig_cc.update_layout(template=TEMPLATE, paper_bgcolor=BG, height=320,
                             margin=dict(l=0,r=0,t=10,b=0), showlegend=False,
                             title="Customers by Channel", title_font=dict(size=13))
        st.plotly_chart(fig_cc, use_container_width=True)

    with ch2:
        sc_df = (
            df.merge(cust_agg[["customer_id","segment"]], on="customer_id", how="left")
            .groupby(["segment","Channel"])["customer_id"].nunique().reset_index(name="customers")
        )
        sc_piv = sc_df.pivot(index="segment", columns="Channel", values="customers").fillna(0)
        sc_piv = sc_piv.reindex([s for s in SEG_ORDER if s in sc_piv.index])
        fig_sc = go.Figure()
        for i, ch in enumerate(sc_piv.columns):
            fig_sc.add_trace(go.Bar(name=ch, x=sc_piv.index.tolist(), y=sc_piv[ch],
                                    marker_color=COLORS[i % len(COLORS)]))
        fig_sc.update_layout(barmode="stack", template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
                             height=320, margin=dict(l=0,r=0,t=10,b=0),
                             xaxis_title="Segment", yaxis_title="Customers",
                             title="Channel Preference by Segment", title_font=dict(size=13),
                             legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_sc, use_container_width=True)
else:
    st.info("Channel column not found in orders data.")

st.divider()

# ── SECTION 8: TIPS ANALYSIS ──────────────────────────────────────────────────
st.subheader("Tips Analysis")

if "Tips" in df.columns:
    dt = df.copy()
    dt["has_tip"] = dt["Tips"] > 0

    tipping_rate = dt["has_tip"].mean() * 100
    avg_tip_all  = dt["Tips"].mean()
    avg_tip_when = dt.loc[dt["has_tip"], "Tips"].mean() if dt["has_tip"].any() else 0

    t1, t2, t3 = st.columns(3)
    t1.metric("Tipping Rate",          f"{tipping_rate:.1f}%")
    t2.metric("Avg Tip (all orders)",  fmt_currency(avg_tip_all, 2))
    t3.metric("Avg Tip (when tipped)", fmt_currency(avg_tip_when, 2))

    tip1, tip2 = st.columns(2)

    with tip1:
        if "Brand" in dt.columns:
            tbb = dt.groupby("Brand").agg(
                tipping_rate=("has_tip","mean"), avg_tip=("Tips","mean"), total_tips=("Tips","sum")
            ).reset_index()
            tbb["tipping_rate"] *= 100
            tbb = tbb.sort_values("tipping_rate", ascending=True)
            fig_tb = go.Figure(go.Bar(
                x=tbb["tipping_rate"], y=tbb["Brand"], orientation="h",
                marker_color=COLORS[2],
                text=[f"{v:.1f}%" for v in tbb["tipping_rate"]],
                textposition="outside", textfont=dict(color="white", size=10),
            ))
            fig_tb.update_layout(template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
                                 height=max(300, len(tbb)*30), margin=dict(l=0,r=70,t=10,b=0),
                                 xaxis_title="Tipping Rate (%)", title="Tipping Rate by Brand",
                                 title_font=dict(size=13))
            st.plotly_chart(fig_tb, use_container_width=True)

    with tip2:
        if "Channel" in dt.columns:
            tbc = dt.groupby("Channel").agg(
                tipping_rate=("has_tip","mean"), avg_tip=("Tips","mean"), total_tips=("Tips","sum")
            ).reset_index()
            tbc["tipping_rate"] *= 100
            tbc = tbc.sort_values("avg_tip", ascending=False)
            fig_tc = make_subplots(specs=[[{"secondary_y": True}]])
            fig_tc.add_trace(go.Bar(
                x=tbc["Channel"], y=tbc["avg_tip"], name="Avg Tip (AED)",
                marker_color=COLORS[5],
                text=[f"AED {v:.2f}" for v in tbc["avg_tip"]],
                textposition="outside", textfont=dict(color="white", size=11),
            ), secondary_y=False)
            fig_tc.add_trace(go.Scatter(
                x=tbc["Channel"], y=tbc["tipping_rate"], name="Tipping Rate %",
                mode="markers+lines", marker=dict(size=10, color=COLORS[2]),
                line=dict(color=COLORS[2], dash="dot"),
            ), secondary_y=True)
            fig_tc.update_layout(template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
                                 height=320, margin=dict(l=0,r=0,t=10,b=0),
                                 xaxis_title="Channel", title="Avg Tip & Tipping Rate by Channel",
                                 title_font=dict(size=13),
                                 legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            fig_tc.update_yaxes(title_text="Avg Tip (AED)",    secondary_y=False)
            fig_tc.update_yaxes(title_text="Tipping Rate (%)", secondary_y=True,
                                ticksuffix="%", showgrid=False)
            st.plotly_chart(fig_tc, use_container_width=True)

    tips_nonzero = dt.loc[dt["has_tip"] & (dt["Tips"] < 100), "Tips"]
    if not tips_nonzero.empty:
        fig_td = go.Figure(go.Histogram(
            x=tips_nonzero, nbinsx=30,
            marker_color=COLORS[5], opacity=0.85,
            hovertemplate="Tip: AED %{x:.1f}<br>Count: %{y}<extra></extra>",
        ))
        fig_td.update_layout(template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
                             height=260, margin=dict(l=0,r=0,t=10,b=0),
                             xaxis_title="Tip Amount (AED, capped at 100)",
                             yaxis_title="# Orders", title="Tip Amount Distribution",
                             title_font=dict(size=13))
        st.plotly_chart(fig_td, use_container_width=True)
else:
    st.info("Tips column not found in orders data.")

st.divider()

# ── FOOTER ────────────────────────────────────────────────────────────────────
min_d = pd.to_datetime(df["Received At"]).min().date()
max_d = pd.to_datetime(df["Received At"]).max().date()
st.caption(
    f"Data period: {min_d} → {max_d} "
    f"| {total_unique:,} unique customers | {len(df):,} filtered orders"
)
