"""
Marketing ROI Analytics Page
Cloud Kitchen Analytics Dashboard
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from utils.data_loader import (
    get_all_brands,
    get_all_channels,
    load_marketing,
    load_sales_brand,
    load_sales_orders,
)

# ─── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Marketing ROI", page_icon="📢", layout="wide")

# ─── CONSTANTS ────────────────────────────────────────────────────────────────
C1 = "#FF6B35"
C2 = "#4ECDC4"
C3 = "#FFE66D"
C4 = "#845EC2"
PALETTE = [C1, C2, C3, C4, "#A8DADC", "#E63946", "#457B9D", "#2EC4B6"]
TEMPLATE = "plotly_dark"
BG = "rgba(0,0,0,0)"


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def fmt_currency(val: float, decimals: int = 0) -> str:
    if abs(val) >= 1_000_000:
        return f"AED {val / 1_000_000:.2f}M"
    if abs(val) >= 1_000:
        return f"AED {val / 1_000:.1f}K"
    return f"AED {val:,.{decimals}f}"


def safe_ratio(num: float, den: float, fallback: float = 0.0) -> float:
    return num / den if den and den != 0 else fallback


def color_seq(n: int) -> list:
    """Cycle through palette for n items."""
    return [PALETTE[i % len(PALETTE)] for i in range(n)]


def base_layout(height: int = 340, title: str = "", margins: dict = None) -> dict:
    m = margins or dict(l=0, r=0, t=30 if title else 10, b=0)
    layout = dict(
        template=TEMPLATE,
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        height=height,
        margin=m,
        showlegend=True,
    )
    if title:
        layout["title"] = title
        layout["title_font"] = dict(size=13)
    return layout


# ─── PAGE HEADER ──────────────────────────────────────────────────────────────
st.title("Marketing ROI Analytics")
st.markdown("Campaign performance, discount efficiency, and return on ad spend across brands and channels.")

# ─── DATA LOAD ────────────────────────────────────────────────────────────────
with st.spinner("Loading marketing data…"):
    df_mkt_raw = load_marketing()
    df_orders = load_sales_orders()
    df_brand_sales = load_sales_brand()

if df_mkt_raw.empty:
    st.error("Marketing data could not be loaded. Please verify the data file exists.")
    st.stop()

all_brands_mkt = sorted(df_mkt_raw["Brand"].dropna().unique().tolist()) if "Brand" in df_mkt_raw.columns else []
all_channels_mkt = sorted(df_mkt_raw["Channel"].dropna().unique().tolist()) if "Channel" in df_mkt_raw.columns else []
all_types_mkt = sorted(df_mkt_raw["Type"].dropna().unique().tolist()) if "Type" in df_mkt_raw.columns else []

# ─── SIDEBAR FILTERS ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")

    sel_brands = st.multiselect(
        "Brand",
        options=all_brands_mkt,
        default=[],
        placeholder="All brands",
    )
    sel_channels = st.multiselect(
        "Channel",
        options=all_channels_mkt,
        default=[],
        placeholder="All channels",
    )
    sel_types = st.multiselect(
        "Campaign Type",
        options=all_types_mkt,
        default=[],
        placeholder="All types",
    )

    st.divider()
    st.markdown("**Date Range**")
    _dates_mkt = df_mkt_raw["Date"].dropna() if "Date" in df_mkt_raw.columns else pd.Series(dtype="datetime64[ns]")
    _dates_mkt = pd.to_datetime(_dates_mkt, errors="coerce").dropna()
    _min_mkt = _dates_mkt.min().date() if not _dates_mkt.empty else None
    _max_mkt = _dates_mkt.max().date() if not _dates_mkt.empty else None
    sel_start_mkt = sel_end_mkt = None
    if _min_mkt and _max_mkt:
        _dr_mkt = st.date_input("Period", value=(_min_mkt, _max_mkt), min_value=_min_mkt, max_value=_max_mkt, label_visibility="collapsed")
        sel_start_mkt, sel_end_mkt = (_dr_mkt[0], _dr_mkt[1]) if isinstance(_dr_mkt, (list, tuple)) and len(_dr_mkt) == 2 else (_min_mkt, _max_mkt)
    st.divider()
    st.caption("Leave blank to include all values.")

# ─── FILTER APPLICATION ───────────────────────────────────────────────────────
df = df_mkt_raw.copy()
if sel_brands:
    df = df[df["Brand"].isin(sel_brands)]
if sel_channels and "Channel" in df.columns:
    df = df[df["Channel"].isin(sel_channels)]
if sel_types and "Type" in df.columns:
    df = df[df["Type"].isin(sel_types)]

if df.empty:
    st.warning("No data matches the selected filters. Please adjust your selections.")
    st.stop()

# ─── DERIVED METRICS ──────────────────────────────────────────────────────────
df = df.copy()
df["ROI"] = df.apply(lambda r: safe_ratio(r["Sales Amount"], r["Discount"]), axis=1)
df["Discount Depth %"] = df.apply(
    lambda r: safe_ratio(r["Discount"], r["Original Amount"]) * 100, axis=1
)
df["Orders per AED"] = df.apply(
    lambda r: safe_ratio(r["No of Orders"], r["Discount"]), axis=1
)

# ─── SECTION 1: KPI ROW ───────────────────────────────────────────────────────
st.subheader("Key Performance Indicators")

total_campaigns = df["Campaign"].nunique() if "Campaign" in df.columns else len(df)
total_orders = int(df["No of Orders"].sum())
total_discount = df["Discount"].sum()
total_sales = df["Sales Amount"].sum()
total_original = df["Original Amount"].sum()
avg_discount_per_order = safe_ratio(total_discount, total_orders)
roas = safe_ratio(total_sales, total_discount)
campaign_efficiency = safe_ratio(total_orders, total_discount)

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Total Campaigns", f"{total_campaigns:,}")
k2.metric("Marketing-Driven Orders", f"{total_orders:,}")
k3.metric("Total Discount Spent", fmt_currency(total_discount))
k4.metric("Avg Discount / Order", fmt_currency(avg_discount_per_order, 2))
k5.metric("ROAS", f"{roas:.2f}x", help="Sales Amount / Discount Spent")
k6.metric(
    "Campaign Efficiency",
    f"{campaign_efficiency:.3f}",
    help="Orders generated per AED of discount spent",
)

st.divider()

# ─── SECTION 2: CAMPAIGN OVERVIEW ─────────────────────────────────────────────
st.subheader("Campaign Overview")

# ── 2a. Performance table ────────────────────────────────────────────────────
with st.expander("Campaign Performance Table", expanded=True):
    table_cols = [c for c in ["Campaign", "Type", "Brand", "Channel",
                               "No of Orders", "Original Amount", "Discount",
                               "Sales Amount", "ROI"] if c in df.columns]
    numeric_sort_cols = [c for c in table_cols if c not in ("Campaign", "Type", "Brand", "Channel")]
    sort_by = st.selectbox(
        "Sort by",
        options=numeric_sort_cols,
        index=numeric_sort_cols.index("No of Orders") if "No of Orders" in numeric_sort_cols else 0,
        key="camp_sort",
    )
    sort_asc = st.checkbox("Ascending order", value=False, key="camp_sort_asc")
    tbl = (
        df[table_cols]
        .sort_values(sort_by, ascending=sort_asc)
        .reset_index(drop=True)
    )
    tbl_display = tbl.copy()
    for col in ["Original Amount", "Discount", "Sales Amount"]:
        if col in tbl_display.columns:
            tbl_display[col] = tbl_display[col].apply(lambda v: f"AED {v:,.0f}")
    if "ROI" in tbl_display.columns:
        tbl_display["ROI"] = tbl_display["ROI"].apply(lambda v: f"{v:.2f}x")
    st.dataframe(tbl_display, use_container_width=True, hide_index=True)

# ── 2b. Top 10 by orders and by ROAS ─────────────────────────────────────────
camp_agg = (
    df.groupby("Campaign", as_index=False)
    .agg(
        Orders=("No of Orders", "sum"),
        Discount=("Discount", "sum"),
        Sales=("Sales Amount", "sum"),
        Type=("Type", "first") if "Type" in df.columns else ("No of Orders", "count"),
    )
)
camp_agg["ROAS"] = camp_agg.apply(lambda r: safe_ratio(r["Sales"], r["Discount"]), axis=1)

top10_orders = camp_agg.nlargest(10, "Orders").sort_values("Orders")
top10_roas = camp_agg[camp_agg["Discount"] > 0].nlargest(10, "ROAS").sort_values("ROAS")

col_ord, col_roas = st.columns(2)

with col_ord:
    fig_top_ord = go.Figure(go.Bar(
        x=top10_orders["Orders"],
        y=top10_orders["Campaign"],
        orientation="h",
        marker_color=C1,
        text=top10_orders["Orders"].apply(lambda v: f"{int(v):,}"),
        textposition="outside",
        textfont=dict(color="white", size=10),
    ))
    fig_top_ord.update_layout(
        **base_layout(height=360, title="Top 10 Campaigns by Orders", margins=dict(l=0, r=60, t=30, b=0)),
        xaxis_title="Orders",
        yaxis=dict(tickfont=dict(size=9)),
        showlegend=False,
    )
    st.plotly_chart(fig_top_ord, use_container_width=True)

with col_roas:
    fig_top_roas = go.Figure(go.Bar(
        x=top10_roas["ROAS"],
        y=top10_roas["Campaign"],
        orientation="h",
        marker_color=C2,
        text=top10_roas["ROAS"].apply(lambda v: f"{v:.2f}x"),
        textposition="outside",
        textfont=dict(color="white", size=10),
    ))
    fig_top_roas.update_layout(
        **base_layout(height=360, title="Top 10 Campaigns by ROAS", margins=dict(l=0, r=60, t=30, b=0)),
        xaxis_title="ROAS (Sales / Discount)",
        yaxis=dict(tickfont=dict(size=9)),
        showlegend=False,
    )
    st.plotly_chart(fig_top_roas, use_container_width=True)

st.divider()

# ─── SECTION 3: CAMPAIGN TYPE ANALYSIS ────────────────────────────────────────
st.subheader("Campaign Type Analysis")

if "Type" in df.columns:
    type_agg = (
        df.groupby("Type", as_index=False)
        .agg(
            Orders=("No of Orders", "sum"),
            Sales=("Sales Amount", "sum"),
            Discount=("Discount", "sum"),
            Campaigns=("Campaign", "nunique"),
        )
    )
    type_agg["ROI"] = type_agg.apply(lambda r: safe_ratio(r["Sales"], r["Discount"]), axis=1)
    type_agg = type_agg.sort_values("Orders", ascending=False)

    t1, t2, t3 = st.columns(3)

    with t1:
        fig_type_bar = go.Figure()
        fig_type_bar.add_trace(go.Bar(
            name="Orders",
            x=type_agg["Type"],
            y=type_agg["Orders"],
            marker_color=C1,
            text=type_agg["Orders"].apply(lambda v: f"{int(v):,}"),
            textposition="outside",
            textfont=dict(size=9, color="white"),
        ))
        fig_type_bar.add_trace(go.Bar(
            name="Sales (AED)",
            x=type_agg["Type"],
            y=type_agg["Sales"],
            marker_color=C2,
            yaxis="y2",
            text=type_agg["Sales"].apply(fmt_currency),
            textposition="outside",
            textfont=dict(size=9, color="white"),
        ))
        fig_type_bar.add_trace(go.Bar(
            name="Discount (AED)",
            x=type_agg["Type"],
            y=type_agg["Discount"],
            marker_color=C3,
            yaxis="y2",
            text=type_agg["Discount"].apply(fmt_currency),
            textposition="outside",
            textfont=dict(size=9, color="white"),
        ))
        fig_type_bar.update_layout(
            **base_layout(height=360, title="Performance by Campaign Type"),
            barmode="group",
            yaxis=dict(title="Orders"),
            yaxis2=dict(title="AED", overlaying="y", side="right"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(tickfont=dict(size=10)),
        )
        st.plotly_chart(fig_type_bar, use_container_width=True)

    with t2:
        fig_type_roi = go.Figure(go.Bar(
            x=type_agg["Type"],
            y=type_agg["ROI"],
            marker_color=color_seq(len(type_agg)),
            text=type_agg["ROI"].apply(lambda v: f"{v:.2f}x"),
            textposition="outside",
            textfont=dict(color="white", size=11),
        ))
        fig_type_roi.update_layout(
            **base_layout(height=360, title="ROI by Campaign Type"),
            yaxis_title="ROI (Sales / Discount)",
            showlegend=False,
            xaxis=dict(tickfont=dict(size=10)),
        )
        st.plotly_chart(fig_type_roi, use_container_width=True)

    with t3:
        fig_type_pie = go.Figure(go.Pie(
            labels=type_agg["Type"],
            values=type_agg["Orders"],
            hole=0.50,
            marker=dict(colors=color_seq(len(type_agg))),
            textinfo="label+percent",
            textfont=dict(size=11),
        ))
        fig_type_pie.update_layout(
            **base_layout(height=360, title="Order Distribution by Type"),
            showlegend=False,
        )
        st.plotly_chart(fig_type_pie, use_container_width=True)
else:
    st.info("Campaign Type column not available in marketing data.")

st.divider()

# ─── SECTION 4: BRAND MARKETING PERFORMANCE ───────────────────────────────────
st.subheader("Brand Marketing Performance")

if "Brand" in df.columns:
    brand_agg = (
        df.groupby("Brand", as_index=False)
        .agg(
            Orders=("No of Orders", "sum"),
            Sales=("Sales Amount", "sum"),
            Discount=("Discount", "sum"),
            Campaigns=("Campaign", "nunique"),
        )
    )
    brand_agg["ROI"] = brand_agg.apply(lambda r: safe_ratio(r["Sales"], r["Discount"]), axis=1)
    brand_agg = brand_agg.sort_values("Sales", ascending=False)

    b1, b2, b3 = st.columns(3)

    with b1:
        b_sorted = brand_agg.sort_values("Discount", ascending=True)
        fig_b_spend = go.Figure(go.Bar(
            x=b_sorted["Discount"],
            y=b_sorted["Brand"],
            orientation="h",
            marker_color=C3,
            text=b_sorted["Discount"].apply(fmt_currency),
            textposition="outside",
            textfont=dict(color="white", size=10),
        ))
        fig_b_spend.update_layout(
            **base_layout(height=max(300, len(b_sorted) * 34), title="Marketing Spend (Discounts) by Brand", margins=dict(l=0, r=70, t=30, b=0)),
            xaxis_title="Discount (AED)",
            yaxis=dict(tickfont=dict(size=10)),
            showlegend=False,
        )
        st.plotly_chart(fig_b_spend, use_container_width=True)

    with b2:
        b_sorted2 = brand_agg.sort_values("Sales", ascending=True)
        fig_b_rev = go.Figure(go.Bar(
            x=b_sorted2["Sales"],
            y=b_sorted2["Brand"],
            orientation="h",
            marker_color=C1,
            text=b_sorted2["Sales"].apply(fmt_currency),
            textposition="outside",
            textfont=dict(color="white", size=10),
        ))
        fig_b_rev.update_layout(
            **base_layout(height=max(300, len(b_sorted2) * 34), title="Marketing-Driven Revenue by Brand", margins=dict(l=0, r=70, t=30, b=0)),
            xaxis_title="Sales Amount (AED)",
            yaxis=dict(tickfont=dict(size=10)),
            showlegend=False,
        )
        st.plotly_chart(fig_b_rev, use_container_width=True)

    with b3:
        b_sorted3 = brand_agg.sort_values("ROI", ascending=True)
        roi_colors = [C2 if v >= 1 else C1 for v in b_sorted3["ROI"]]
        fig_b_roi = go.Figure(go.Bar(
            x=b_sorted3["ROI"],
            y=b_sorted3["Brand"],
            orientation="h",
            marker_color=roi_colors,
            text=b_sorted3["ROI"].apply(lambda v: f"{v:.2f}x"),
            textposition="outside",
            textfont=dict(color="white", size=10),
        ))
        fig_b_roi.add_vline(
            x=1.0,
            line_dash="dash",
            line_color="rgba(255,255,255,0.4)",
            annotation_text="Break-even",
            annotation_position="top",
        )
        fig_b_roi.update_layout(
            **base_layout(height=max(300, len(b_sorted3) * 34), title="ROI by Brand (Sales / Discount)", margins=dict(l=0, r=70, t=30, b=0)),
            xaxis_title="ROI",
            yaxis=dict(tickfont=dict(size=10)),
            showlegend=False,
        )
        st.plotly_chart(fig_b_roi, use_container_width=True)
else:
    st.info("Brand column not available in marketing data.")

st.divider()

# ─── SECTION 5: CHANNEL ANALYSIS ──────────────────────────────────────────────
st.subheader("Channel Analysis")

if "Channel" in df.columns:
    ch_agg = (
        df.groupby("Channel", as_index=False)
        .agg(
            Orders=("No of Orders", "sum"),
            Sales=("Sales Amount", "sum"),
            Discount=("Discount", "sum"),
            Campaigns=("Campaign", "nunique"),
        )
    )
    ch_agg["ROI"] = ch_agg.apply(lambda r: safe_ratio(r["Sales"], r["Discount"]), axis=1)
    ch_agg["Efficiency"] = ch_agg.apply(lambda r: safe_ratio(r["Orders"], r["Discount"]), axis=1)
    ch_agg = ch_agg.sort_values("Sales", ascending=False)

    ch1, ch2, ch3 = st.columns(3)

    with ch1:
        fig_ch_perf = go.Figure()
        fig_ch_perf.add_trace(go.Bar(
            name="Orders",
            x=ch_agg["Channel"],
            y=ch_agg["Orders"],
            marker_color=C1,
            text=ch_agg["Orders"].apply(lambda v: f"{int(v):,}"),
            textposition="outside",
            textfont=dict(size=10, color="white"),
        ))
        fig_ch_perf.add_trace(go.Bar(
            name="Discount (AED)",
            x=ch_agg["Channel"],
            y=ch_agg["Discount"],
            marker_color=C3,
            yaxis="y2",
            text=ch_agg["Discount"].apply(fmt_currency),
            textposition="outside",
            textfont=dict(size=10, color="white"),
        ))
        fig_ch_perf.update_layout(
            **base_layout(height=340, title="Channel Performance"),
            barmode="group",
            yaxis=dict(title="Orders"),
            yaxis2=dict(title="Discount (AED)", overlaying="y", side="right"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_ch_perf, use_container_width=True)

    with ch2:
        ch_roi_sorted = ch_agg.sort_values("ROI", ascending=True)
        roi_ch_colors = [C2 if v >= 1 else C1 for v in ch_roi_sorted["ROI"]]
        fig_ch_roi = go.Figure(go.Bar(
            x=ch_roi_sorted["ROI"],
            y=ch_roi_sorted["Channel"],
            orientation="h",
            marker_color=roi_ch_colors,
            text=ch_roi_sorted["ROI"].apply(lambda v: f"{v:.2f}x"),
            textposition="outside",
            textfont=dict(color="white", size=11),
        ))
        fig_ch_roi.add_vline(
            x=1.0,
            line_dash="dash",
            line_color="rgba(255,255,255,0.4)",
            annotation_text="Break-even",
            annotation_position="top",
        )
        fig_ch_roi.update_layout(
            **base_layout(height=340, title="Best Marketing ROI by Channel", margins=dict(l=0, r=70, t=30, b=0)),
            xaxis_title="ROI (Sales / Discount)",
            yaxis=dict(tickfont=dict(size=10)),
            showlegend=False,
        )
        st.plotly_chart(fig_ch_roi, use_container_width=True)

    with ch3:
        max_disc_ch = ch_agg["Discount"].max() or 1
        bubble_sizes = (ch_agg["Discount"] / max_disc_ch * 50 + 10).tolist()
        fig_ch_bubble = go.Figure(go.Scatter(
            x=ch_agg["Orders"],
            y=ch_agg["ROI"],
            mode="markers+text",
            marker=dict(
                size=bubble_sizes,
                color=color_seq(len(ch_agg)),
                opacity=0.85,
                line=dict(width=1, color="white"),
                sizemode="diameter",
            ),
            text=ch_agg["Channel"],
            textposition="top center",
            textfont=dict(size=10),
            customdata=ch_agg[["Discount", "Sales"]].values,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Orders: %{x:,}<br>"
                "ROI: %{y:.2f}x<br>"
                "Discount: AED %{customdata[0]:,.0f}<br>"
                "Sales: AED %{customdata[1]:,.0f}<extra></extra>"
            ),
        ))
        fig_ch_bubble.update_layout(
            **base_layout(height=340, title="Channel Effectiveness (Bubble Size = Discount)"),
            xaxis_title="Orders",
            yaxis_title="ROI",
            showlegend=False,
        )
        st.plotly_chart(fig_ch_bubble, use_container_width=True)
else:
    st.info("Channel column not available in marketing data.")

st.divider()

# ─── SECTION 6: DISCOUNT EFFICIENCY ──────────────────────────────────────────
st.subheader("Discount Efficiency")

de1, de2, de3 = st.columns(3)

with de1:
    if "Type" in df.columns:
        dd_agg = (
            df.groupby("Type", as_index=False)
            .agg(
                Original=("Original Amount", "sum"),
                Discount=("Discount", "sum"),
            )
        )
        dd_agg["Depth %"] = dd_agg.apply(
            lambda r: safe_ratio(r["Discount"], r["Original"]) * 100, axis=1
        )
        dd_agg = dd_agg.sort_values("Depth %", ascending=True)
        fig_depth = go.Figure(go.Bar(
            x=dd_agg["Depth %"],
            y=dd_agg["Type"],
            orientation="h",
            marker_color=C4,
            text=dd_agg["Depth %"].apply(lambda v: f"{v:.1f}%"),
            textposition="outside",
            textfont=dict(color="white", size=11),
        ))
        fig_depth.update_layout(
            **base_layout(height=340, title="Discount Depth % by Campaign Type", margins=dict(l=0, r=60, t=30, b=0)),
            xaxis_title="Discount as % of Original Amount",
            yaxis=dict(tickfont=dict(size=10)),
            showlegend=False,
        )
        st.plotly_chart(fig_depth, use_container_width=True)
    else:
        overall_depth = safe_ratio(total_discount, total_original) * 100
        st.metric(
            "Overall Discount Depth",
            f"{overall_depth:.1f}%",
            help="Total discount as % of total original amount",
        )

with de2:
    scatter_df = df[df["Discount"] > 0].copy()
    fig_scatter = go.Figure(go.Scatter(
        x=scatter_df["Discount"],
        y=scatter_df["No of Orders"],
        mode="markers",
        marker=dict(
            color=C1,
            size=7,
            opacity=0.65,
            line=dict(width=0.5, color="white"),
        ),
        customdata=scatter_df[["Campaign"]].values if "Campaign" in scatter_df.columns else None,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Discount: AED %{x:,.0f}<br>"
            "Orders: %{y:,}<extra></extra>"
        ) if "Campaign" in scatter_df.columns else (
            "Discount: AED %{x:,.0f}<br>Orders: %{y:,}<extra></extra>"
        ),
    ))
    if len(scatter_df) > 2:
        x_vals = scatter_df["Discount"].values.astype(float)
        y_vals = scatter_df["No of Orders"].values.astype(float)
        z = np.polyfit(x_vals, y_vals, 1)
        p = np.poly1d(z)
        x_line = np.linspace(x_vals.min(), x_vals.max(), 100)
        fig_scatter.add_trace(go.Scatter(
            x=x_line,
            y=p(x_line),
            mode="lines",
            name="Linear Trend",
            line=dict(color=C2, dash="dash", width=2),
        ))
    fig_scatter.update_layout(
        **base_layout(height=340, title="Discount Amount vs Orders Generated"),
        xaxis_title="Discount (AED)",
        yaxis_title="No of Orders",
        showlegend=False,
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

with de3:
    if len(scatter_df) > 5:
        try:
            scatter_df["Discount Bucket"] = pd.qcut(
                scatter_df["Discount"], q=8, duplicates="drop"
            )
            bucket_agg = (
                scatter_df.groupby("Discount Bucket", observed=True)
                .agg(
                    Avg_Orders=("No of Orders", "mean"),
                    Median_Discount=("Discount", "median"),
                    Count=("Discount", "count"),
                )
                .reset_index()
                .sort_values("Median_Discount")
            )
            fig_dim = go.Figure()
            fig_dim.add_trace(go.Scatter(
                x=bucket_agg["Median_Discount"],
                y=bucket_agg["Avg_Orders"],
                mode="lines+markers",
                line=dict(color=C2, width=2),
                marker=dict(color=C2, size=9, line=dict(width=1, color="white")),
                fill="tozeroy",
                fillcolor="rgba(78,205,196,0.12)",
                hovertemplate=(
                    "Median Discount: AED %{x:,.0f}<br>"
                    "Avg Orders: %{y:.1f}<extra></extra>"
                ),
            ))
            fig_dim.update_layout(
                **base_layout(height=340, title="Diminishing Returns: Discount Level vs Avg Orders"),
                xaxis_title="Median Discount in Bucket (AED)",
                yaxis_title="Avg Orders per Campaign",
                showlegend=False,
            )
            st.plotly_chart(fig_dim, use_container_width=True)
        except Exception:
            st.info("Could not compute diminishing returns buckets for this filter selection.")
    else:
        st.info("Not enough data points for diminishing returns analysis.")

st.divider()

# ─── SECTION 7: CAMPAIGN COMPARISON MATRIX ────────────────────────────────────
st.subheader("Campaign Comparison Matrix")
st.caption(
    "Bubble chart — X = Orders, Y = Sales Amount, Size = Discount, Color = Campaign Type. "
    "Ideal campaigns sit top-right with small bubbles (high output, low cost)."
)

type_list = sorted(df["Type"].dropna().unique().tolist()) if "Type" in df.columns else []
type_color_map = {t: PALETTE[i % len(PALETTE)] for i, t in enumerate(type_list)}

fig_bubble = go.Figure()
max_d_global = df["Discount"].max() or 1

if type_list:
    for t in type_list:
        sub = df[df["Type"] == t].copy()
        sizes = (sub["Discount"] / max_d_global * 60 + 8).tolist()
        fig_bubble.add_trace(go.Scatter(
            x=sub["No of Orders"],
            y=sub["Sales Amount"],
            mode="markers",
            name=t,
            marker=dict(
                size=sizes,
                color=type_color_map[t],
                opacity=0.75,
                line=dict(width=0.8, color="white"),
                sizemode="diameter",
            ),
            customdata=sub[["Campaign", "Discount", "ROI"]].values,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Type: " + str(t) + "<br>"
                "Orders: %{x:,}<br>"
                "Sales: AED %{y:,.0f}<br>"
                "Discount: AED %{customdata[1]:,.0f}<br>"
                "ROI: %{customdata[2]:.2f}x<extra></extra>"
            ),
        ))
else:
    sizes = (df["Discount"] / max_d_global * 60 + 8).tolist()
    fig_bubble.add_trace(go.Scatter(
        x=df["No of Orders"],
        y=df["Sales Amount"],
        mode="markers",
        marker=dict(
            size=sizes,
            color=C1,
            opacity=0.75,
            line=dict(width=0.8, color="white"),
            sizemode="diameter",
        ),
        customdata=df[["Discount", "ROI"]].values,
        hovertemplate=(
            "Orders: %{x:,}<br>"
            "Sales: AED %{y:,.0f}<br>"
            "Discount: AED %{customdata[0]:,.0f}<br>"
            "ROI: %{customdata[1]:.2f}x<extra></extra>"
        ),
    ))

fig_bubble.update_layout(
    **base_layout(height=500, title="Campaign Comparison Matrix"),
    xaxis_title="No of Orders",
    yaxis_title="Sales Amount (AED)",
    legend=dict(
        title="Campaign Type",
        orientation="v",
        yanchor="top",
        y=1,
        xanchor="left",
        x=1.01,
    ),
    margin=dict(l=0, r=160, t=30, b=0),
)
st.plotly_chart(fig_bubble, use_container_width=True)

st.divider()

# ─── FOOTER ───────────────────────────────────────────────────────────────────
st.caption(
    f"Marketing data: {len(df_mkt_raw):,} records total | Filtered view: {len(df):,} records | "
    "Metrics: ROAS = Sales Amount / Discount Spent. ROI shown as revenue multiple (>1x = profitable)."
)
