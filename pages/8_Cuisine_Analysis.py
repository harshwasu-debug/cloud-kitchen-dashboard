"""
Cuisine Analysis Page — Cloud Kitchen Analytics Dashboard
Cross-cuisine performance comparison: revenue, orders, AOV, growth trends,
channel mix, operational metrics, cancellations, and brand leaderboards.
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
    load_operations_orders,
    load_cancelled_orders,
    load_menu_orders,
    add_cuisine_column,
    get_all_cuisines,
    get_cuisine_brand_df,
    get_all_locations,
    CUISINE_BRAND_MAP,
)

# ─── PAGE CONFIG ────────────────────────────────────────────────────────────
st.set_page_config(page_title="Cuisine Analysis", page_icon="🍽️", layout="wide")

# ─── THEME CONSTANTS ─────────────────────────────────────────────────────────
PRIMARY   = "#FF6B35"
SECONDARY = "#4ECDC4"
ACCENT    = "#FFE66D"
TEMPLATE  = "plotly_white"
CHART_BG  = "rgba(255,255,255,0)"

CUISINE_COLORS = {
    "American":  "#FF6B35",
    "Breakfast": "#FFE66D",
    "Chinese":   "#E63946",
    "Indian":    "#F4A261",
    "Korean":    "#4ECDC4",
    "Mexican":   "#A8DADC",
    "Poke":      "#457B9D",
    "Sushi":     "#2A9D8F",
    "Other":     "#6D6875",
}

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
        background: #1E1E2E;
        border-radius: 10px;
        padding: 18px 20px;
        border-left: 4px solid #FF6B35;
        margin-bottom: 8px;
    }
    .kpi-label { color: #9E9E9E; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; }
    .kpi-value { color: #FFFFFF; font-size: 1.75rem; font-weight: 700; margin: 4px 0 2px; }
    .kpi-sub   { color: #9E9E9E; font-size: 0.78rem; }
    .section-header {
        color: #FF6B35;
        font-size: 1.05rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin: 24px 0 12px;
        border-bottom: 1px solid #2A2A3E;
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
    if abs(val) >= 1_000_000:
        return f"AED {val/1_000_000:.2f}M"
    if abs(val) >= 1_000:
        return f"AED {val/1_000:.1f}K"
    return f"AED {val:,.0f}"


def _layout(fig, height=400):
    """Apply standard dark layout to a figure."""
    fig.update_layout(
        template=TEMPLATE,
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        height=height,
        margin=dict(l=20, r=20, t=40, b=20),
        font=dict(size=12),
    )
    return fig


def cuisine_color(cuisine: str) -> str:
    return CUISINE_COLORS.get(cuisine, "#6D6875")


def cuisine_color_map(cuisines):
    return {c: cuisine_color(c) for c in cuisines}


# ─── LOAD DATA ───────────────────────────────────────────────────────────────
try:
    with st.spinner("Loading data for cuisine analysis…"):
        df_orders = load_sales_orders()
        df_orders = add_cuisine_column(df_orders, "Brand")
except Exception as e:
    st.error(f"Failed to load sales orders: {e}")
    st.stop()

try:
    df_ops = load_operations_orders()
    df_ops = add_cuisine_column(df_ops, "Brand")
except Exception:
    df_ops = pd.DataFrame()

try:
    df_cancel = load_cancelled_orders()
    df_cancel = add_cuisine_column(df_cancel, "Brand")
except Exception:
    df_cancel = pd.DataFrame()

try:
    df_menu_orders = load_menu_orders()
    df_menu_orders = add_cuisine_column(df_menu_orders, "Brand")
except Exception:
    df_menu_orders = pd.DataFrame()

all_cuisines  = get_all_cuisines()
all_locations = sorted(df_orders["Location"].dropna().unique()) if "Location" in df_orders.columns else []

# ─── SIDEBAR FILTERS ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎛️ Filters")
    st.markdown("---")

    sel_cuisines = st.multiselect(
        "Cuisine",
        options=all_cuisines,
        default=[],
        placeholder="All cuisines",
    )
    sel_locations = st.multiselect(
        "Location",
        options=all_locations,
        default=[],
        placeholder="All locations",
    )

    st.markdown("---")
    st.markdown("**Date Range**")
    _dates_ca = df_orders["Received At"].dropna() if "Received At" in df_orders.columns else pd.Series(dtype="datetime64[ns]")
    _min_ca = _dates_ca.min().date() if not _dates_ca.empty else None
    _max_ca = _dates_ca.max().date() if not _dates_ca.empty else None
    sel_start_ca = sel_end_ca = None
    if _min_ca and _max_ca:
        _dr_ca = st.date_input("Period", value=(_min_ca, _max_ca), min_value=_min_ca, max_value=_max_ca, label_visibility="collapsed")
        sel_start_ca, sel_end_ca = (_dr_ca[0], _dr_ca[1]) if isinstance(_dr_ca, (list, tuple)) and len(_dr_ca) == 2 else (_min_ca, _max_ca)
    st.markdown("**Time Range**")
    from datetime import time as _time
    _tc1_ca, _tc2_ca = st.columns(2)
    with _tc1_ca:
        sel_time_from_ca = st.time_input("From", value=_time(0, 0), step=1800, key="tf_ca")
    with _tc2_ca:
        sel_time_to_ca = st.time_input("To", value=_time(23, 59), step=1800, key="tt_ca")
    st.markdown("---")
    st.caption("Data source: Grubtech + Deliverect")

# ─── APPLY FILTERS ───────────────────────────────────────────────────────────
df = df_orders.copy()
if sel_cuisines:
    df = df[df["Cuisine"].isin(sel_cuisines)]
if sel_locations and "Location" in df.columns:
    df = df[df["Location"].isin(sel_locations)]
if sel_start_ca and sel_end_ca and "Date" in df.columns:
    df["_date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
    df = df[(df["_date"] >= sel_start_ca) & (df["_date"] <= sel_end_ca)]
    df = df.drop(columns=["_date"])
if "Received At" in df.columns and (sel_time_from_ca != _time(0, 0) or sel_time_to_ca != _time(23, 59)):
    _t = pd.to_datetime(df["Received At"], errors="coerce").dt.time
    df = df[(_t >= sel_time_from_ca) & (_t <= sel_time_to_ca)]

if df.empty:
    st.warning("No data matches the selected filters. Please adjust your selections.")
    st.stop()

# Also filter ops / cancellation frames
df_ops_f = df_ops.copy()
if sel_cuisines and "Cuisine" in df_ops_f.columns:
    df_ops_f = df_ops_f[df_ops_f["Cuisine"].isin(sel_cuisines)]
if sel_locations and "Location" in df_ops_f.columns:
    df_ops_f = df_ops_f[df_ops_f["Location"].isin(sel_locations)]

df_cancel_f = df_cancel.copy()
if sel_cuisines and "Cuisine" in df_cancel_f.columns:
    df_cancel_f = df_cancel_f[df_cancel_f["Cuisine"].isin(sel_cuisines)]

# ─── PAGE HEADER ─────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <h1 style='color:{PRIMARY}; margin-bottom:0;'>🍽️ Cuisine Analysis</h1>
    <p style='color:#555; margin-top:4px;'>
        Cross-cuisine performance comparison · {len(df):,} orders
    </p>
    """,
    unsafe_allow_html=True,
)
st.markdown("---")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — CUISINE OVERVIEW KPIs
# ═══════════════════════════════════════════════════════════════════════════════
section("Cuisine Overview")

revenue_col = "Gross Price" if "Gross Price" in df.columns else ("Total(Receipt Total)" if "Total(Receipt Total)" in df.columns else "Net Sales")
total_revenue = df[revenue_col].sum()
order_id_col = "Unique Order ID" if "Unique Order ID" in df.columns else "Order ID"
total_orders  = df[order_id_col].nunique() if order_id_col in df.columns else len(df)
active_cuisines = df["Cuisine"].nunique()
active_brands   = df["Brand"].nunique()
avg_aov = total_revenue / total_orders if total_orders > 0 else 0

cuisine_rev = df.groupby("Cuisine")[revenue_col].sum()
best_cuisine = cuisine_rev.idxmax() if not cuisine_rev.empty else "N/A"
best_cuisine_rev = cuisine_rev.max() if not cuisine_rev.empty else 0

k1, k2, k3, k4, k5, k6 = st.columns(6)
with k1:
    kpi_card("Cuisines Active", str(active_cuisines))
with k2:
    kpi_card("Total Brands", str(active_brands))
with k3:
    kpi_card("Total Orders", f"{total_orders:,}")
with k4:
    kpi_card("Total Revenue", fmt_aed(total_revenue))
with k5:
    kpi_card("Avg AOV", fmt_aed(avg_aov))
with k6:
    kpi_card("Top Cuisine", best_cuisine, sub=fmt_aed(best_cuisine_rev))

st.markdown("---")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — CUISINE REVENUE & ORDERS COMPARISON
# ═══════════════════════════════════════════════════════════════════════════════
section("Cuisine Revenue & Orders Comparison")

cuis_summary = (
    df.groupby("Cuisine")
    .agg(
        Revenue=(revenue_col, "sum"),
        Orders=(revenue_col, "count"),
    )
    .reset_index()
    .sort_values("Revenue", ascending=True)
)

col_l, col_r = st.columns(2)

with col_l:
    fig_rev = go.Figure(go.Bar(
        x=cuis_summary["Revenue"],
        y=cuis_summary["Cuisine"],
        orientation="h",
        marker_color=[cuisine_color(c) for c in cuis_summary["Cuisine"]],
        text=[fmt_aed(v) for v in cuis_summary["Revenue"]],
        textposition="auto",
    ))
    fig_rev.update_layout(
        title=dict(text="Revenue by Cuisine", font=dict(size=14)),
        xaxis=dict(title=dict(text="Revenue (AED)", font=dict(size=11))),
        yaxis=dict(title=dict(text="", font=dict(size=11))),
    )
    _layout(fig_rev, height=380)
    st.plotly_chart(fig_rev, use_container_width=True)

with col_r:
    fig_ord = go.Figure(go.Bar(
        x=cuis_summary["Orders"],
        y=cuis_summary["Cuisine"],
        orientation="h",
        marker_color=[cuisine_color(c) for c in cuis_summary["Cuisine"]],
        text=cuis_summary["Orders"].apply(lambda v: f"{v:,}"),
        textposition="auto",
    ))
    fig_ord.update_layout(
        title=dict(text="Orders by Cuisine", font=dict(size=14)),
        xaxis=dict(title=dict(text="Order Count", font=dict(size=11))),
        yaxis=dict(title=dict(text="", font=dict(size=11))),
    )
    _layout(fig_ord, height=380)
    st.plotly_chart(fig_ord, use_container_width=True)

st.markdown("---")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — CUISINE PERFORMANCE TABLE
# ═══════════════════════════════════════════════════════════════════════════════
section("Cuisine Performance Table")

perf = df.groupby("Cuisine").agg(
    Orders=(revenue_col, "count"),
    Revenue=(revenue_col, "sum"),
    Discount=("Discount", "sum") if "Discount" in df.columns else (revenue_col, "count"),
    Brands=("Brand", "nunique"),
).reset_index()

perf["AOV"] = (perf["Revenue"] / perf["Orders"]).round(2)
if "Discount" in df.columns:
    perf["Discount %"] = ((perf["Discount"] / perf["Revenue"].replace(0, np.nan)) * 100).round(1)
else:
    perf["Discount %"] = 0.0
perf["Avg Orders/Brand"] = (perf["Orders"] / perf["Brands"].replace(0, np.nan)).round(0).astype(int)
perf = perf.sort_values("Revenue", ascending=False)

display_perf = perf[["Cuisine", "Orders", "Revenue", "AOV", "Discount %", "Brands", "Avg Orders/Brand"]].copy()
display_perf["Revenue"] = display_perf["Revenue"].apply(lambda v: f"AED {v:,.0f}")
display_perf["AOV"] = display_perf["AOV"].apply(lambda v: f"AED {v:,.2f}")

st.dataframe(
    display_perf,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Cuisine": st.column_config.TextColumn("Cuisine", width="medium"),
        "Orders": st.column_config.NumberColumn("Orders", format="%d"),
        "Revenue": st.column_config.TextColumn("Revenue"),
        "AOV": st.column_config.TextColumn("AOV"),
        "Discount %": st.column_config.NumberColumn("Discount %", format="%.1f%%"),
        "Brands": st.column_config.NumberColumn("Brands", format="%d"),
        "Avg Orders/Brand": st.column_config.NumberColumn("Avg Orders/Brand", format="%d"),
    },
)

st.markdown("---")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — REVENUE SHARE TREEMAP
# ═══════════════════════════════════════════════════════════════════════════════
section("Revenue Share Treemap — Cuisine → Brand")

tree_data = (
    df.groupby(["Cuisine", "Brand"])[revenue_col]
    .sum()
    .reset_index()
    .rename(columns={revenue_col: "Revenue"})
)
tree_data = tree_data[tree_data["Revenue"] > 0]

if not tree_data.empty:
    fig_tree = px.treemap(
        tree_data,
        path=["Cuisine", "Brand"],
        values="Revenue",
        color="Cuisine",
        color_discrete_map=CUISINE_COLORS,
    )
    fig_tree.update_layout(
        title=dict(text="Revenue Distribution: Cuisine → Brand", font=dict(size=14)),
    )
    _layout(fig_tree, height=500)
    fig_tree.update_traces(textinfo="label+value+percent parent")
    st.plotly_chart(fig_tree, use_container_width=True)
else:
    st.info("No revenue data available for treemap.")

st.markdown("---")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — AOV BY CUISINE
# ═══════════════════════════════════════════════════════════════════════════════
section("Average Order Value by Cuisine")

aov_data = (
    df.groupby("Cuisine")
    .agg(Revenue=(revenue_col, "sum"), Orders=(revenue_col, "count"))
    .reset_index()
)
aov_data["AOV"] = (aov_data["Revenue"] / aov_data["Orders"]).round(2)
aov_data = aov_data.sort_values("AOV", ascending=False)
overall_aov = total_revenue / total_orders if total_orders > 0 else 0

col_a, col_b = st.columns(2)

with col_a:
    fig_aov = go.Figure()
    fig_aov.add_trace(go.Bar(
        x=aov_data["Cuisine"],
        y=aov_data["AOV"],
        marker_color=[cuisine_color(c) for c in aov_data["Cuisine"]],
        text=[f"AED {v:.1f}" for v in aov_data["AOV"]],
        textposition="outside",
    ))
    fig_aov.add_hline(
        y=overall_aov, line_dash="dash", line_color=ACCENT, line_width=2,
        annotation_text=f"Avg: AED {overall_aov:.1f}",
        annotation_position="top right",
        annotation_font_color=ACCENT,
    )
    fig_aov.update_layout(
        title=dict(text="AOV by Cuisine", font=dict(size=14)),
        yaxis=dict(title=dict(text="AOV (AED)", font=dict(size=11))),
        xaxis=dict(title=dict(text="", font=dict(size=11))),
    )
    _layout(fig_aov, height=380)
    st.plotly_chart(fig_aov, use_container_width=True)

with col_b:
    # AOV by cuisine x channel
    if "Channel" in df.columns:
        aov_cc = (
            df.groupby(["Cuisine", "Channel"])
            .agg(Revenue=(revenue_col, "sum"), Orders=(revenue_col, "count"))
            .reset_index()
        )
        aov_cc["AOV"] = (aov_cc["Revenue"] / aov_cc["Orders"]).round(2)

        fig_aov_ch = px.bar(
            aov_cc,
            x="Cuisine",
            y="AOV",
            color="Channel",
            barmode="group",
            color_discrete_sequence=PALETTE,
            text_auto=".1f",
        )
        fig_aov_ch.update_layout(
            title=dict(text="AOV by Cuisine × Channel", font=dict(size=14)),
            yaxis=dict(title=dict(text="AOV (AED)", font=dict(size=11))),
            xaxis=dict(title=dict(text="", font=dict(size=11))),
        )
        _layout(fig_aov_ch, height=380)
        st.plotly_chart(fig_aov_ch, use_container_width=True)
    else:
        st.info("Channel data not available.")

st.markdown("---")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — CUISINE GROWTH TRENDS
# ═══════════════════════════════════════════════════════════════════════════════
section("Cuisine Growth Trends")

if "Month" in df.columns:
    monthly = (
        df.groupby(["Month", "Cuisine"])[revenue_col]
        .sum()
        .reset_index()
        .rename(columns={revenue_col: "Revenue"})
        .sort_values("Month")
    )

    fig_trend = px.line(
        monthly,
        x="Month",
        y="Revenue",
        color="Cuisine",
        color_discrete_map=CUISINE_COLORS,
        markers=True,
    )
    fig_trend.update_layout(
        title=dict(text="Monthly Revenue by Cuisine", font=dict(size=14)),
        yaxis=dict(title=dict(text="Revenue (AED)", font=dict(size=11))),
        xaxis=dict(title=dict(text="Month", font=dict(size=11))),
    )
    _layout(fig_trend, height=400)
    st.plotly_chart(fig_trend, use_container_width=True)

    # MoM growth rate table
    pivot_monthly = monthly.pivot(index="Month", columns="Cuisine", values="Revenue").fillna(0)
    mom_growth = pivot_monthly.pct_change() * 100
    mom_growth = mom_growth.iloc[1:]  # drop first row (NaN)

    if not mom_growth.empty:
        st.markdown("**Month-over-Month Growth Rate (%)**")
        display_mom = mom_growth.round(1).reset_index()
        st.dataframe(display_mom, use_container_width=True, hide_index=True)
else:
    st.info("Month column not available for trend analysis.")

st.markdown("---")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — CUISINE × LOCATION HEATMAP
# ═══════════════════════════════════════════════════════════════════════════════
section("Cuisine × Location Heatmap")

if "Location" in df.columns:
    heat_data = (
        df.groupby(["Cuisine", "Location"])[revenue_col]
        .sum()
        .reset_index()
        .rename(columns={revenue_col: "Revenue"})
    )
    heat_pivot = heat_data.pivot(index="Cuisine", columns="Location", values="Revenue").fillna(0)

    fig_heat = go.Figure(go.Heatmap(
        z=heat_pivot.values,
        x=heat_pivot.columns.tolist(),
        y=heat_pivot.index.tolist(),
        colorscale=[[0, "#FFFFFF"], [0.5, "#FF6B35"], [1, "#FFE66D"]],
        text=[[fmt_aed(v) for v in row] for row in heat_pivot.values],
        texttemplate="%{text}",
        hovertemplate="Cuisine: %{y}<br>Location: %{x}<br>Revenue: %{text}<extra></extra>",
    ))
    fig_heat.update_layout(
        title=dict(text="Revenue by Cuisine × Location", font=dict(size=14)),
        xaxis=dict(title=dict(text="", font=dict(size=11))),
        yaxis=dict(title=dict(text="", font=dict(size=11))),
    )
    _layout(fig_heat, height=max(350, len(heat_pivot) * 50))
    st.plotly_chart(fig_heat, use_container_width=True)
else:
    st.info("Location data not available.")

st.markdown("---")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — CUISINE × CHANNEL ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════
section("Cuisine × Channel Analysis")

if "Channel" in df.columns:
    chan_data = (
        df.groupby(["Cuisine", "Channel"])[revenue_col]
        .sum()
        .reset_index()
        .rename(columns={revenue_col: "Revenue"})
    )

    col_c1, col_c2 = st.columns(2)

    with col_c1:
        fig_stack = px.bar(
            chan_data,
            x="Cuisine",
            y="Revenue",
            color="Channel",
            color_discrete_sequence=PALETTE,
            text_auto=".2s",
        )
        fig_stack.update_layout(
            title=dict(text="Channel Distribution per Cuisine", font=dict(size=14)),
            yaxis=dict(title=dict(text="Revenue (AED)", font=dict(size=11))),
            xaxis=dict(title=dict(text="", font=dict(size=11))),
            barmode="stack",
        )
        _layout(fig_stack, height=400)
        st.plotly_chart(fig_stack, use_container_width=True)

    with col_c2:
        cuisine_for_donut = st.selectbox(
            "Select cuisine for channel breakdown",
            options=sorted(df["Cuisine"].unique()),
            key="donut_cuisine",
        )
        donut_data = chan_data[chan_data["Cuisine"] == cuisine_for_donut]

        if not donut_data.empty:
            fig_donut = go.Figure(go.Pie(
                labels=donut_data["Channel"],
                values=donut_data["Revenue"],
                hole=0.5,
                marker=dict(colors=PALETTE[:len(donut_data)]),
                textinfo="label+percent",
            ))
            fig_donut.update_layout(
                title=dict(text=f"Channel Share — {cuisine_for_donut}", font=dict(size=14)),
            )
            _layout(fig_donut, height=400)
            st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("No channel data for the selected cuisine.")
else:
    st.info("Channel data not available.")

st.markdown("---")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9 — OPERATIONAL PERFORMANCE BY CUISINE
# ═══════════════════════════════════════════════════════════════════════════════
section("Operational Performance by Cuisine")

delivery_col = "Order Received to Delivered (min)"

if not df_ops_f.empty and delivery_col in df_ops_f.columns and "Cuisine" in df_ops_f.columns:
    ops_cuis = (
        df_ops_f.groupby("Cuisine")[delivery_col]
        .agg(["mean", "median", "count"])
        .reset_index()
        .rename(columns={"mean": "Avg Delivery (min)", "median": "Median Delivery (min)", "count": "Orders"})
    )
    ops_cuis["Avg Delivery (min)"] = ops_cuis["Avg Delivery (min)"].round(1)
    ops_cuis["Median Delivery (min)"] = ops_cuis["Median Delivery (min)"].round(1)
    ops_cuis = ops_cuis.sort_values("Avg Delivery (min)")

    col_o1, col_o2 = st.columns(2)

    with col_o1:
        fig_del = go.Figure()
        fig_del.add_trace(go.Bar(
            x=ops_cuis["Cuisine"],
            y=ops_cuis["Avg Delivery (min)"],
            marker_color=[cuisine_color(c) for c in ops_cuis["Cuisine"]],
            text=[f"{v:.1f} min" for v in ops_cuis["Avg Delivery (min)"]],
            textposition="outside",
            name="Avg Delivery Time",
        ))
        fig_del.update_layout(
            title=dict(text="Avg Delivery Time by Cuisine", font=dict(size=14)),
            yaxis=dict(title=dict(text="Minutes", font=dict(size=11))),
            xaxis=dict(title=dict(text="", font=dict(size=11))),
        )
        _layout(fig_del, height=380)
        st.plotly_chart(fig_del, use_container_width=True)

    with col_o2:
        # On-time rate: orders delivered within 45 minutes threshold
        ON_TIME_THRESHOLD = 45
        if not df_ops_f.empty:
            ot = df_ops_f.dropna(subset=[delivery_col]).copy()
            ot["On Time"] = ot[delivery_col] <= ON_TIME_THRESHOLD
            ot_rate = (
                ot.groupby("Cuisine")["On Time"]
                .mean()
                .reset_index()
                .rename(columns={"On Time": "On-Time Rate"})
            )
            ot_rate["On-Time Rate"] = (ot_rate["On-Time Rate"] * 100).round(1)
            ot_rate = ot_rate.sort_values("On-Time Rate", ascending=True)

            fig_ot = go.Figure(go.Bar(
                x=ot_rate["On-Time Rate"],
                y=ot_rate["Cuisine"],
                orientation="h",
                marker_color=[cuisine_color(c) for c in ot_rate["Cuisine"]],
                text=[f"{v:.1f}%" for v in ot_rate["On-Time Rate"]],
                textposition="auto",
            ))
            fig_ot.update_layout(
                title=dict(text=f"On-Time Rate (≤ {ON_TIME_THRESHOLD} min)", font=dict(size=14)),
                xaxis=dict(title=dict(text="On-Time %", font=dict(size=11)), range=[0, 105]),
                yaxis=dict(title=dict(text="", font=dict(size=11))),
            )
            _layout(fig_ot, height=380)
            st.plotly_chart(fig_ot, use_container_width=True)
else:
    st.info("Operations data not available for cuisine-level analysis.")

st.markdown("---")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 10 — CANCELLATION ANALYSIS BY CUISINE
# ═══════════════════════════════════════════════════════════════════════════════
section("Cancellation Analysis by Cuisine")

if not df_cancel_f.empty and "Cuisine" in df_cancel_f.columns:
    cancel_cuis = (
        df_cancel_f.groupby("Cuisine")
        .agg(
            Cancellations=("Cuisine", "count"),
            Lost_Revenue=("Sales Amount", "sum") if "Sales Amount" in df_cancel_f.columns else ("Cuisine", "count"),
        )
        .reset_index()
    )

    # Compute cancellation rate using total order counts from main df
    orders_by_cuisine = df.groupby("Cuisine")[revenue_col].count().reset_index().rename(columns={revenue_col: "Total Orders"})
    cancel_cuis = cancel_cuis.merge(orders_by_cuisine, on="Cuisine", how="left")
    cancel_cuis["Cancel Rate %"] = ((cancel_cuis["Cancellations"] / cancel_cuis["Total Orders"].replace(0, np.nan)) * 100).round(2)
    cancel_cuis = cancel_cuis.sort_values("Cancellations", ascending=True)

    col_x1, col_x2 = st.columns(2)

    with col_x1:
        fig_canc = go.Figure()
        fig_canc.add_trace(go.Bar(
            x=cancel_cuis["Cancellations"],
            y=cancel_cuis["Cuisine"],
            orientation="h",
            marker_color=[cuisine_color(c) for c in cancel_cuis["Cuisine"]],
            text=cancel_cuis["Cancellations"],
            textposition="auto",
            name="Cancellations",
        ))
        fig_canc.update_layout(
            title=dict(text="Cancellations by Cuisine", font=dict(size=14)),
            xaxis=dict(title=dict(text="Cancellations", font=dict(size=11))),
            yaxis=dict(title=dict(text="", font=dict(size=11))),
        )
        _layout(fig_canc, height=380)
        st.plotly_chart(fig_canc, use_container_width=True)

    with col_x2:
        # Top reasons per cuisine
        if "Reason" in df_cancel_f.columns:
            top_reasons = (
                df_cancel_f.groupby(["Cuisine", "Reason"])
                .size()
                .reset_index(name="Count")
                .sort_values(["Cuisine", "Count"], ascending=[True, False])
            )
            # Top 3 reasons per cuisine
            top_reasons = top_reasons.groupby("Cuisine").head(3).reset_index(drop=True)

            fig_reasons = px.bar(
                top_reasons,
                x="Count",
                y="Reason",
                color="Cuisine",
                orientation="h",
                color_discrete_map=CUISINE_COLORS,
                barmode="group",
            )
            fig_reasons.update_layout(
                title=dict(text="Top Cancellation Reasons by Cuisine", font=dict(size=14)),
                xaxis=dict(title=dict(text="Count", font=dict(size=11))),
                yaxis=dict(title=dict(text="", font=dict(size=11))),
            )
            _layout(fig_reasons, height=380)
            st.plotly_chart(fig_reasons, use_container_width=True)
        else:
            st.info("Cancellation reason data not available.")
else:
    st.info("Cancellation data not available for cuisine analysis.")

st.markdown("---")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 11 — BRAND LEADERBOARD WITHIN CUISINE
# ═══════════════════════════════════════════════════════════════════════════════
section("Brand Leaderboard within Cuisine")

selected_cuisine = st.selectbox(
    "Select a cuisine to view brand leaderboard",
    options=sorted(df["Cuisine"].unique()),
    key="brand_leaderboard_cuisine",
)

df_cuis = df[df["Cuisine"] == selected_cuisine]
brand_perf = (
    df_cuis.groupby("Brand")
    .agg(
        Revenue=(revenue_col, "sum"),
        Orders=(revenue_col, "count"),
    )
    .reset_index()
)
brand_perf["AOV"] = (brand_perf["Revenue"] / brand_perf["Orders"]).round(2)
brand_perf = brand_perf.sort_values("Revenue", ascending=True)

if not brand_perf.empty:
    fig_leader = make_subplots(specs=[[{"secondary_y": True}]])

    fig_leader.add_trace(
        go.Bar(
            x=brand_perf["Revenue"],
            y=brand_perf["Brand"],
            orientation="h",
            marker_color=cuisine_color(selected_cuisine),
            name="Revenue",
            text=[fmt_aed(v) for v in brand_perf["Revenue"]],
            textposition="auto",
            opacity=0.85,
        ),
        secondary_y=False,
    )

    fig_leader.add_trace(
        go.Scatter(
            x=brand_perf["AOV"],
            y=brand_perf["Brand"],
            mode="markers",
            marker=dict(
                symbol="diamond",
                size=12,
                color=ACCENT,
                line=dict(width=1, color="#fff"),
            ),
            name="AOV (AED)",
        ),
        secondary_y=True,
    )

    fig_leader.update_layout(
        title=dict(text=f"Brand Leaderboard — {selected_cuisine}", font=dict(size=14)),
        xaxis=dict(title=dict(text="Revenue (AED)", font=dict(size=11))),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig_leader.update_yaxes(title=dict(text="", font=dict(size=11)), secondary_y=False)
    fig_leader.update_xaxes(title=dict(text="Revenue (AED)", font=dict(size=11)), secondary_y=False)
    fig_leader.update_yaxes(title=dict(text="AOV (AED)", font=dict(size=11)), secondary_y=True)
    _layout(fig_leader, height=max(350, len(brand_perf) * 50))
    st.plotly_chart(fig_leader, use_container_width=True)
else:
    st.info(f"No brand data for {selected_cuisine}.")

st.markdown("---")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 12 — CUISINE PROFITABILITY MATRIX
# ═══════════════════════════════════════════════════════════════════════════════
section("Cuisine Profitability Matrix")

matrix_data = (
    df.groupby("Cuisine")
    .agg(
        Revenue=(revenue_col, "sum"),
        Orders=(revenue_col, "count"),
    )
    .reset_index()
)
matrix_data["AOV"] = (matrix_data["Revenue"] / matrix_data["Orders"]).round(2)

median_orders = matrix_data["Orders"].median()
median_aov    = matrix_data["AOV"].median()

fig_matrix = go.Figure()

for _, row in matrix_data.iterrows():
    fig_matrix.add_trace(go.Scatter(
        x=[row["Orders"]],
        y=[row["AOV"]],
        mode="markers+text",
        marker=dict(
            size=max(10, row["Revenue"] / matrix_data["Revenue"].max() * 60),
            color=cuisine_color(row["Cuisine"]),
            opacity=0.8,
            line=dict(width=1, color="#fff"),
        ),
        text=[row["Cuisine"]],
        textposition="top center",
        textfont=dict(size=11, color="#fff"),
        name=row["Cuisine"],
        hovertemplate=(
            f"<b>{row['Cuisine']}</b><br>"
            f"Orders: {row['Orders']:,}<br>"
            f"AOV: AED {row['AOV']:.2f}<br>"
            f"Revenue: {fmt_aed(row['Revenue'])}<extra></extra>"
        ),
    ))

# Quadrant lines at medians
fig_matrix.add_vline(x=median_orders, line_dash="dot", line_color="#555", line_width=1,
                     annotation_text=f"Median Orders: {median_orders:,.0f}",
                     annotation_position="top", annotation_font_color="#888", annotation_font_size=10)
fig_matrix.add_hline(y=median_aov, line_dash="dot", line_color="#555", line_width=1,
                     annotation_text=f"Median AOV: AED {median_aov:.1f}",
                     annotation_position="right", annotation_font_color="#888", annotation_font_size=10)

# Quadrant labels
x_range = matrix_data["Orders"].max() - matrix_data["Orders"].min()
y_range = matrix_data["AOV"].max() - matrix_data["AOV"].min()

annotations = [
    dict(x=median_orders + x_range * 0.25, y=median_aov + y_range * 0.35,
         text="Stars", showarrow=False, font=dict(size=13, color="#4ECDC4"), opacity=0.5),
    dict(x=median_orders - x_range * 0.25, y=median_aov + y_range * 0.35,
         text="Niche", showarrow=False, font=dict(size=13, color="#FFE66D"), opacity=0.5),
    dict(x=median_orders + x_range * 0.25, y=median_aov - y_range * 0.35,
         text="Volume", showarrow=False, font=dict(size=13, color="#FF6B35"), opacity=0.5),
    dict(x=median_orders - x_range * 0.25, y=median_aov - y_range * 0.35,
         text="Underperformers", showarrow=False, font=dict(size=13, color="#6D6875"), opacity=0.5),
]

fig_matrix.update_layout(
    title=dict(text="Cuisine Profitability Matrix (Bubble size = Revenue)", font=dict(size=14)),
    xaxis=dict(title=dict(text="Order Volume", font=dict(size=11))),
    yaxis=dict(title=dict(text="AOV (AED)", font=dict(size=11))),
    showlegend=False,
    annotations=annotations,
)
_layout(fig_matrix, height=500)
st.plotly_chart(fig_matrix, use_container_width=True)

st.markdown("---")
st.caption("Cuisine Analysis · Cloud Kitchen Analytics Dashboard · Data source: Grubtech")
