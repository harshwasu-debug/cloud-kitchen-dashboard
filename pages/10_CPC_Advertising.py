"""
CPC & Advertising Page — Cloud Kitchen Analytics Dashboard
Analyzes Careem CPC (Cost Per Click) paid advertising campaign performance:
spend, impressions, clicks, orders, ROAS, CPC, CPO, CTR, conversion rates,
and user acquisition split (new / repeat / lapsed).
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

from utils.data_loader import load_cpc_data

# ─── PAGE CONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="CPC & Advertising", page_icon="📣", layout="wide")

# ─── THEME CONSTANTS ─────────────────────────────────────────────────────────
PRIMARY   = "#FF6B35"
SECONDARY = "#4ECDC4"
ACCENT    = "#845EC2"
TEMPLATE  = "plotly_white"
PAPER_BG  = "white"
PLOT_BG   = "white"

PALETTE = [
    PRIMARY, SECONDARY, ACCENT,
    "#F4A261", "#2A9D8F", "#457B9D",
    "#E63946", "#A8DADC", "#E9C46A",
    "#264653", "#6D6875", "#B5838D",
]

ROAS_GREEN  = "#2ECC71"
ROAS_YELLOW = "#F39C12"
ROAS_RED    = "#E74C3C"

# ─── CSS ─────────────────────────────────────────────────────────────────────
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
    .kpi-label { color: #555; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; }
    .kpi-value { color: #1A1A2E; font-size: 1.75rem; font-weight: 700; margin: 4px 0 2px; }
    .kpi-sub   { color: #888; font-size: 0.78rem; }
    .section-header {
        font-size: 1.1rem;
        font-weight: 700;
        color: #1A1A2E;
        border-bottom: 2px solid #FF6B35;
        padding-bottom: 6px;
        margin: 24px 0 16px;
    }
    .campaign-card {
        background: #F8F9FA;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 6px;
        border-left: 4px solid #4ECDC4;
    }
    .top-card   { border-left-color: #2ECC71 !important; }
    .bottom-card{ border-left-color: #E74C3C !important; }
    .insight-box {
        background: #FFF3EE;
        border-radius: 8px;
        padding: 14px 18px;
        border-left: 4px solid #FF6B35;
        margin-bottom: 8px;
        color: #333;
        font-size: 0.92rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── HELPERS ─────────────────────────────────────────────────────────────────
def fmt_currency(val, decimals=0):
    try:
        return f"AED {val:,.{decimals}f}"
    except Exception:
        return "N/A"

def fmt_number(val, decimals=0):
    try:
        return f"{val:,.{decimals}f}"
    except Exception:
        return "N/A"

def fmt_pct(val, decimals=1):
    try:
        return f"{val:.{decimals}f}%"
    except Exception:
        return "N/A"

def fmt_x(val, decimals=2):
    try:
        return f"{val:.{decimals}f}x"
    except Exception:
        return "N/A"

def kpi_card(label, value, sub=""):
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def section(title):
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)

def roas_color(val):
    try:
        v = float(val)
        if v >= 3:
            return ROAS_GREEN
        elif v >= 1:
            return ROAS_YELLOW
        return ROAS_RED
    except Exception:
        return ROAS_YELLOW

# ─── LOAD DATA ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_data():
    return load_cpc_data()

raw_df = get_data()

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
st.sidebar.header("📣 CPC Advertising Filters")

if raw_df is None or raw_df.empty:
    st.info("No CPC advertising data available. Please check your data source.")
    st.stop()

df_work = raw_df.copy()

# Ensure date column is datetime
if "date_value" in df_work.columns:
    df_work["date_value"] = pd.to_datetime(df_work["date_value"], errors="coerce")

# Brand filter
all_brands = sorted(df_work["Brand"].dropna().unique().tolist()) if "Brand" in df_work.columns else []
sel_brands = st.sidebar.multiselect("Brand", all_brands, default=all_brands)

# Cuisine filter
all_cuisines = sorted(df_work["Cuisine"].dropna().unique().tolist()) if "Cuisine" in df_work.columns else []
sel_cuisines = st.sidebar.multiselect("Cuisine", all_cuisines, default=all_cuisines)

# Date range filter
if "date_value" in df_work.columns and df_work["date_value"].notna().any():
    min_date = df_work["date_value"].min().date()
    max_date = df_work["date_value"].max().date()
    sel_dates = st.sidebar.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    if isinstance(sel_dates, (list, tuple)) and len(sel_dates) == 2:
        start_date, end_date = sel_dates
    else:
        start_date, end_date = min_date, max_date
else:
    start_date, end_date = None, None

# Time range filter
st.sidebar.markdown("**Time Range**")
time_col1, time_col2 = st.sidebar.columns(2)
with time_col1:
    from_time = st.time_input("From", value=None, step=1800)
with time_col2:
    to_time = st.time_input("To", value=None, step=1800)

# ─── APPLY FILTERS ───────────────────────────────────────────────────────────
df = df_work.copy()

if sel_brands:
    df = df[df["Brand"].isin(sel_brands)]
if sel_cuisines:
    df = df[df["Cuisine"].isin(sel_cuisines)]
if start_date and end_date and "date_value" in df.columns:
    df = df[
        (df["date_value"].dt.date >= start_date)
        & (df["date_value"].dt.date <= end_date)
    ]

if df.empty:
    st.info("No data matches the selected filters. Please adjust your filters.")
    st.stop()

# ─── PAGE TITLE ──────────────────────────────────────────────────────────────
st.title("📣 CPC & Advertising Performance")
st.caption("Careem Cost-Per-Click campaign analysis — spend, reach, ROAS, and user acquisition.")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — KPIs
# ═══════════════════════════════════════════════════════════════════════════════
section("Key Performance Indicators")

try:
    total_spend       = df["netbasket_amount"].sum()
    total_impressions = df["impressions"].sum()
    total_clicks      = df["clicks"].sum()
    total_orders      = df["orders"].sum()
    overall_roas      = df["gmv_local"].sum() / total_spend if total_spend > 0 else 0
    avg_cpc           = df["CPC"].mean() if "CPC" in df.columns else 0
except Exception:
    total_spend = total_impressions = total_clicks = total_orders = overall_roas = avg_cpc = 0

k1, k2, k3, k4, k5, k6 = st.columns(6)
with k1:
    kpi_card("Total Spend", fmt_currency(total_spend), "net basket amount")
with k2:
    kpi_card("Total Impressions", fmt_number(total_impressions), "ad views")
with k3:
    kpi_card("Total Clicks", fmt_number(total_clicks), "link clicks")
with k4:
    kpi_card("Total Orders", fmt_number(total_orders), "conversions")
with k5:
    kpi_card("Overall ROAS", fmt_x(overall_roas), "return on ad spend")
with k6:
    kpi_card("Avg CPC", fmt_currency(avg_cpc, 2), "cost per click")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Campaign Performance Table
# ═══════════════════════════════════════════════════════════════════════════════
section("Campaign Performance Table")

try:
    camp_cols = [
        c for c in [
            "campaign_name", "campaign_type", "Brand", "Cuisine",
            "impressions", "clicks", "orders", "netbasket_amount",
            "gmv_local", "ROAS", "CPC", "CPO", "CTR", "Conversion Rate",
        ]
        if c in df.columns
    ]
    camp_df = (
        df[camp_cols]
        .groupby([c for c in ["campaign_name", "campaign_type", "Brand", "Cuisine"] if c in camp_cols])
        .agg({
            **{c: "sum" for c in ["impressions", "clicks", "orders", "netbasket_amount", "gmv_local"] if c in camp_cols},
            **{c: "mean" for c in ["ROAS", "CPC", "CPO", "CTR", "Conversion Rate"] if c in camp_cols},
        })
        .reset_index()
        .sort_values("ROAS" if "ROAS" in camp_cols else camp_cols[0], ascending=False)
    )

    sort_by = st.selectbox(
        "Sort campaigns by",
        options=[c for c in ["ROAS", "netbasket_amount", "orders", "impressions"] if c in camp_df.columns],
        index=0,
    )
    camp_df = camp_df.sort_values(sort_by, ascending=False)

    fmt_map = {}
    for c in ["netbasket_amount", "gmv_local", "CPC", "CPO"]:
        if c in camp_df.columns:
            fmt_map[c] = "AED {:,.2f}"
    for c in ["ROAS"]:
        if c in camp_df.columns:
            fmt_map[c] = "{:.2f}x"
    for c in ["CTR", "Conversion Rate"]:
        if c in camp_df.columns:
            fmt_map[c] = "{:.2f}%"

    st.dataframe(
        camp_df.style.format(fmt_map),
        use_container_width=True,
        height=350,
    )
except Exception as e:
    st.info(f"Campaign table unavailable: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — ROAS by Brand
# ═══════════════════════════════════════════════════════════════════════════════
section("ROAS by Brand")

try:
    roas_brand = (
        df.groupby("Brand")
        .agg(spend=("netbasket_amount", "sum"), revenue=("gmv_local", "sum"))
        .reset_index()
    )
    roas_brand["ROAS"] = roas_brand.apply(
        lambda r: r["revenue"] / r["spend"] if r["spend"] > 0 else 0, axis=1
    )
    roas_brand = roas_brand.sort_values("ROAS", ascending=True)
    roas_brand["color"] = roas_brand["ROAS"].apply(roas_color)

    fig_roas = go.Figure(
        go.Bar(
            x=roas_brand["ROAS"],
            y=roas_brand["Brand"],
            orientation="h",
            marker_color=roas_brand["color"],
            text=roas_brand["ROAS"].apply(lambda v: f"{v:.2f}x"),
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>ROAS: %{x:.2f}x<extra></extra>",
        )
    )
    fig_roas.add_vline(x=3, line_dash="dash", line_color=ROAS_GREEN, annotation_text="3x target")
    fig_roas.add_vline(x=1, line_dash="dot",  line_color=ROAS_RED,   annotation_text="break-even")
    fig_roas.update_layout(
        template=TEMPLATE,
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        xaxis_title="ROAS",
        yaxis_title="",
        height=max(350, len(roas_brand) * 38),
        margin=dict(l=10, r=60, t=20, b=40),
    )
    st.plotly_chart(fig_roas, use_container_width=True)
except Exception as e:
    st.info(f"ROAS by Brand chart unavailable: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Spend vs Revenue Scatter
# ═══════════════════════════════════════════════════════════════════════════════
section("Spend vs Revenue")

try:
    scatter_df = (
        df.groupby("Brand")
        .agg(
            spend=("netbasket_amount", "sum"),
            revenue=("gmv_local", "sum"),
            orders=("orders", "sum"),
        )
        .reset_index()
    )
    fig_scatter = px.scatter(
        scatter_df,
        x="spend",
        y="revenue",
        size="orders",
        color="Brand",
        color_discrete_sequence=PALETTE,
        labels={"spend": "Ad Spend (AED)", "revenue": "GMV Revenue (AED)"},
        hover_data={"orders": ":,"},
        template=TEMPLATE,
        size_max=60,
    )
    # break-even line
    max_val = max(scatter_df["spend"].max(), scatter_df["revenue"].max()) * 1.1
    fig_scatter.add_trace(
        go.Scatter(
            x=[0, max_val], y=[0, max_val],
            mode="lines",
            line=dict(dash="dash", color="#888", width=1),
            name="Break-even",
            hoverinfo="skip",
        )
    )
    fig_scatter.update_layout(
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        height=420,
        margin=dict(l=10, r=10, t=20, b=40),
    )
    st.plotly_chart(fig_scatter, use_container_width=True)
except Exception as e:
    st.info(f"Spend vs Revenue chart unavailable: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — Monthly Trends
# ═══════════════════════════════════════════════════════════════════════════════
section("Monthly Trends — Spend, GMV & ROAS")

try:
    monthly_df = (
        df.groupby("Month")
        .agg(spend=("netbasket_amount", "sum"), gmv=("gmv_local", "sum"), orders=("orders", "sum"))
        .reset_index()
        .sort_values("Month")
    )
    monthly_df["ROAS"] = monthly_df.apply(
        lambda r: r["gmv"] / r["spend"] if r["spend"] > 0 else 0, axis=1
    )

    fig_monthly = make_subplots(specs=[[{"secondary_y": True}]])
    fig_monthly.add_trace(
        go.Bar(x=monthly_df["Month"], y=monthly_df["spend"], name="Spend (AED)",
               marker_color=PRIMARY, opacity=0.75),
        secondary_y=False,
    )
    fig_monthly.add_trace(
        go.Scatter(x=monthly_df["Month"], y=monthly_df["gmv"], name="GMV (AED)",
                   mode="lines+markers", line=dict(color=SECONDARY, width=2)),
        secondary_y=False,
    )
    fig_monthly.add_trace(
        go.Scatter(x=monthly_df["Month"], y=monthly_df["ROAS"], name="ROAS",
                   mode="lines+markers", line=dict(color=ACCENT, width=2, dash="dot")),
        secondary_y=True,
    )
    fig_monthly.update_layout(
        template=TEMPLATE,
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=60, t=40, b=40),
    )
    fig_monthly.update_yaxes(title_text="Amount (AED)", secondary_y=False)
    fig_monthly.update_yaxes(title_text="ROAS", secondary_y=True)
    st.plotly_chart(fig_monthly, use_container_width=True)
except Exception as e:
    st.info(f"Monthly Trends chart unavailable: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — Impressions Funnel
# ═══════════════════════════════════════════════════════════════════════════════
section("Impressions Funnel: Impressions → Clicks → Orders")

try:
    total_imp = df["impressions"].sum()
    total_clk = df["clicks"].sum()
    total_ord = df["orders"].sum()

    ctr_pct  = (total_clk / total_imp * 100) if total_imp > 0 else 0
    conv_pct = (total_ord / total_clk * 100) if total_clk > 0 else 0

    fig_funnel = go.Figure(
        go.Funnel(
            y=["Impressions", "Clicks", "Orders"],
            x=[total_imp, total_clk, total_ord],
            textinfo="value+percent initial",
            marker=dict(color=[PRIMARY, SECONDARY, ACCENT]),
            connector=dict(line=dict(color="#ccc", width=1)),
        )
    )
    fig_funnel.update_layout(
        template=TEMPLATE,
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        height=350,
        margin=dict(l=10, r=10, t=20, b=20),
    )

    fc1, fc2, fc3 = st.columns([2, 1, 1])
    with fc1:
        st.plotly_chart(fig_funnel, use_container_width=True)
    with fc2:
        kpi_card("Click-Through Rate", fmt_pct(ctr_pct), f"{fmt_number(total_clk)} of {fmt_number(total_imp)}")
    with fc3:
        kpi_card("Conversion Rate", fmt_pct(conv_pct), f"{fmt_number(total_ord)} of {fmt_number(total_clk)}")
except Exception as e:
    st.info(f"Impressions Funnel unavailable: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — CTR & Conversion Rate by Brand
# ═══════════════════════════════════════════════════════════════════════════════
section("CTR & Conversion Rate by Brand")

try:
    rate_df = (
        df.groupby("Brand")
        .agg(impressions=("impressions", "sum"), clicks=("clicks", "sum"), orders=("orders", "sum"))
        .reset_index()
    )
    rate_df["CTR"]  = rate_df.apply(lambda r: r["clicks"] / r["impressions"] * 100 if r["impressions"] > 0 else 0, axis=1)
    rate_df["Conv"] = rate_df.apply(lambda r: r["orders"] / r["clicks"] * 100 if r["clicks"] > 0 else 0, axis=1)
    rate_df = rate_df.sort_values("CTR", ascending=True)

    fig_rates = make_subplots(rows=1, cols=2, subplot_titles=["CTR (%)", "Conversion Rate (%)"])
    fig_rates.add_trace(
        go.Bar(y=rate_df["Brand"], x=rate_df["CTR"], orientation="h",
               marker_color=PRIMARY, name="CTR",
               text=rate_df["CTR"].apply(lambda v: f"{v:.2f}%"), textposition="outside"),
        row=1, col=1,
    )
    fig_rates.add_trace(
        go.Bar(y=rate_df["Brand"], x=rate_df["Conv"], orientation="h",
               marker_color=SECONDARY, name="Conv Rate",
               text=rate_df["Conv"].apply(lambda v: f"{v:.2f}%"), textposition="outside"),
        row=1, col=2,
    )
    fig_rates.update_layout(
        template=TEMPLATE,
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        showlegend=False,
        height=max(350, len(rate_df) * 38),
        margin=dict(l=10, r=60, t=40, b=20),
    )
    st.plotly_chart(fig_rates, use_container_width=True)
except Exception as e:
    st.info(f"CTR & Conversion Rate chart unavailable: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — CPC & CPO by Brand
# ═══════════════════════════════════════════════════════════════════════════════
section("CPC & CPO by Brand")

try:
    cost_df = (
        df.groupby("Brand")
        .agg(CPC=("CPC", "mean"), CPO=("CPO", "mean"))
        .reset_index()
        .sort_values("CPC", ascending=False)
    )

    cc1, cc2 = st.columns(2)
    with cc1:
        fig_cpc = px.bar(
            cost_df, x="Brand", y="CPC", color_discrete_sequence=[PRIMARY],
            labels={"CPC": "Avg CPC (AED)", "Brand": ""},
            template=TEMPLATE, text_auto=".2f",
        )
        fig_cpc.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, height=380,
                               xaxis_tickangle=-35, margin=dict(l=10, r=10, t=20, b=80))
        st.plotly_chart(fig_cpc, use_container_width=True)
    with cc2:
        fig_cpo = px.bar(
            cost_df, x="Brand", y="CPO", color_discrete_sequence=[SECONDARY],
            labels={"CPO": "Avg CPO (AED)", "Brand": ""},
            template=TEMPLATE, text_auto=".2f",
        )
        fig_cpo.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, height=380,
                               xaxis_tickangle=-35, margin=dict(l=10, r=10, t=20, b=80))
        st.plotly_chart(fig_cpo, use_container_width=True)
except Exception as e:
    st.info(f"CPC & CPO charts unavailable: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9 — User Acquisition Analysis
# ═══════════════════════════════════════════════════════════════════════════════
section("User Acquisition Analysis")

try:
    usr_cols = [c for c in ["newuser_orders", "repeatuser_orders", "lapseduser_orders"] if c in df.columns]
    if usr_cols:
        usr_df = (
            df.groupby("Brand")[usr_cols].sum().reset_index()
        )
        usr_df.columns = [c.replace("user_orders", "").replace("_orders", "").capitalize() if c != "Brand" else c for c in usr_df.columns]
        usr_melt = usr_df.melt(id_vars="Brand", var_name="User Type", value_name="Orders")

        ua1, ua2 = st.columns([3, 2])
        with ua1:
            fig_usr_bar = px.bar(
                usr_melt, x="Brand", y="Orders", color="User Type",
                color_discrete_map={
                    "New": ROAS_GREEN, "Repeat": SECONDARY, "Lapsed": ROAS_YELLOW,
                    "Newuser": ROAS_GREEN, "Repeatuser": SECONDARY, "Lapseduser": ROAS_YELLOW,
                },
                template=TEMPLATE,
                labels={"Orders": "Orders", "Brand": ""},
            )
            fig_usr_bar.update_layout(
                paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, height=380,
                xaxis_tickangle=-35, margin=dict(l=10, r=10, t=20, b=80),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig_usr_bar, use_container_width=True)

        with ua2:
            pie_vals = [usr_df[c].sum() for c in usr_df.columns if c != "Brand"]
            pie_labels = [c for c in usr_df.columns if c != "Brand"]
            fig_pie = go.Figure(
                go.Pie(
                    labels=pie_labels,
                    values=pie_vals,
                    hole=0.45,
                    marker_colors=[ROAS_GREEN, SECONDARY, ROAS_YELLOW],
                    textinfo="label+percent",
                )
            )
            fig_pie.update_layout(
                template=TEMPLATE, paper_bgcolor=PAPER_BG,
                height=380, margin=dict(l=10, r=10, t=20, b=20),
            )
            st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("User acquisition order columns not found in data.")
except Exception as e:
    st.info(f"User Acquisition Analysis unavailable: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 10 — User GMV Analysis
# ═══════════════════════════════════════════════════════════════════════════════
section("User GMV Analysis")

try:
    gmv_usr_cols = [c for c in ["newuser_gmv", "repeatuser_gmv", "lapseduser_gmv"] if c in df.columns]
    if gmv_usr_cols:
        gmv_usr = df.groupby("Brand")[gmv_usr_cols].sum().reset_index()
        gmv_usr_melt = gmv_usr.melt(id_vars="Brand", var_name="User Type", value_name="GMV")
        gmv_usr_melt["User Type"] = gmv_usr_melt["User Type"].str.replace("_gmv", "").str.replace("user", " User").str.title()

        fig_gmv_usr = px.bar(
            gmv_usr_melt, x="Brand", y="GMV", color="User Type",
            color_discrete_map={"New User": ROAS_GREEN, "Repeat User": SECONDARY, "Lapsed User": ROAS_YELLOW},
            template=TEMPLATE,
            labels={"GMV": "GMV (AED)", "Brand": ""},
        )
        fig_gmv_usr.update_layout(
            paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, height=380,
            xaxis_tickangle=-35, margin=dict(l=10, r=10, t=20, b=80),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_gmv_usr, use_container_width=True)
    else:
        st.info("User GMV columns not found in data.")
except Exception as e:
    st.info(f"User GMV Analysis unavailable: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 11 — Brand Efficiency Matrix
# ═══════════════════════════════════════════════════════════════════════════════
section("Brand Efficiency Matrix (CPC vs ROAS)")

try:
    eff_df = (
        df.groupby(["Brand", "Cuisine"])
        .agg(
            CPC=("CPC", "mean"),
            spend=("netbasket_amount", "sum"),
            revenue=("gmv_local", "sum"),
            orders=("orders", "sum"),
        )
        .reset_index()
    )
    eff_df["ROAS"] = eff_df.apply(lambda r: r["revenue"] / r["spend"] if r["spend"] > 0 else 0, axis=1)

    fig_matrix = px.scatter(
        eff_df, x="CPC", y="ROAS", size="orders", color="Cuisine",
        color_discrete_sequence=PALETTE,
        hover_name="Brand",
        hover_data={"orders": ":,", "CPC": ":.2f", "ROAS": ":.2f"},
        labels={"CPC": "Avg CPC (AED)", "ROAS": "ROAS"},
        template=TEMPLATE,
        size_max=60,
    )
    fig_matrix.add_hline(y=3, line_dash="dash", line_color=ROAS_GREEN, annotation_text="3x ROAS")
    fig_matrix.add_hline(y=1, line_dash="dot",  line_color=ROAS_RED,   annotation_text="break-even")
    fig_matrix.update_layout(
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, height=450,
        margin=dict(l=10, r=10, t=20, b=40),
    )
    st.plotly_chart(fig_matrix, use_container_width=True)
except Exception as e:
    st.info(f"Brand Efficiency Matrix unavailable: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 12 — Monthly ROAS Trend by Brand
# ═══════════════════════════════════════════════════════════════════════════════
section("Monthly ROAS Trend by Brand")

try:
    trend_df = (
        df.groupby(["Month", "Brand"])
        .agg(spend=("netbasket_amount", "sum"), revenue=("gmv_local", "sum"))
        .reset_index()
        .sort_values("Month")
    )
    trend_df["ROAS"] = trend_df.apply(lambda r: r["revenue"] / r["spend"] if r["spend"] > 0 else 0, axis=1)

    fig_trend = px.line(
        trend_df, x="Month", y="ROAS", color="Brand",
        color_discrete_sequence=PALETTE,
        markers=True, template=TEMPLATE,
        labels={"ROAS": "ROAS", "Month": "Month"},
    )
    fig_trend.add_hline(y=3, line_dash="dash", line_color=ROAS_GREEN, annotation_text="3x target")
    fig_trend.add_hline(y=1, line_dash="dot",  line_color=ROAS_RED,   annotation_text="break-even")
    fig_trend.update_layout(
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=40, b=40),
    )
    st.plotly_chart(fig_trend, use_container_width=True)
except Exception as e:
    st.info(f"Monthly ROAS Trend unavailable: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 13 — Top & Bottom Campaigns
# ═══════════════════════════════════════════════════════════════════════════════
section("Top 5 & Bottom 5 Campaigns by ROAS")

try:
    if "campaign_name" in df.columns:
        camp_roas = (
            df.groupby(["campaign_name", "campaign_type", "Brand"])
            .agg(
                spend=("netbasket_amount", "sum"),
                revenue=("gmv_local", "sum"),
                orders=("orders", "sum"),
                impressions=("impressions", "sum"),
            )
            .reset_index()
        )
        camp_roas["ROAS"] = camp_roas.apply(lambda r: r["revenue"] / r["spend"] if r["spend"] > 0 else 0, axis=1)
        top5    = camp_roas.nlargest(5, "ROAS")
        bottom5 = camp_roas.nsmallest(5, "ROAS")

        t_col, b_col = st.columns(2)
        with t_col:
            st.markdown("**Top 5 Campaigns**")
            for _, row in top5.iterrows():
                try:
                    camp_nm  = row.get("campaign_name", "N/A")
                    brand_nm = row.get("Brand", "")
                    roas_v   = row.get("ROAS", 0)
                    spend_v  = row.get("spend", 0)
                    orders_v = row.get("orders", 0)
                    st.markdown(
                        f"""<div class="campaign-card top-card">
                        <strong>{camp_nm}</strong> &nbsp; <span style="color:#666;font-size:0.82rem">{brand_nm}</span><br>
                        ROAS <strong style="color:{ROAS_GREEN}">{roas_v:.2f}x</strong> &nbsp;|&nbsp;
                        Spend <strong>AED {spend_v:,.0f}</strong> &nbsp;|&nbsp;
                        Orders <strong>{int(orders_v):,}</strong>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                except Exception:
                    pass

        with b_col:
            st.markdown("**Bottom 5 Campaigns**")
            for _, row in bottom5.iterrows():
                try:
                    camp_nm  = row.get("campaign_name", "N/A")
                    brand_nm = row.get("Brand", "")
                    roas_v   = row.get("ROAS", 0)
                    spend_v  = row.get("spend", 0)
                    orders_v = row.get("orders", 0)
                    st.markdown(
                        f"""<div class="campaign-card bottom-card">
                        <strong>{camp_nm}</strong> &nbsp; <span style="color:#666;font-size:0.82rem">{brand_nm}</span><br>
                        ROAS <strong style="color:{ROAS_RED}">{roas_v:.2f}x</strong> &nbsp;|&nbsp;
                        Spend <strong>AED {spend_v:,.0f}</strong> &nbsp;|&nbsp;
                        Orders <strong>{int(orders_v):,}</strong>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                except Exception:
                    pass
    else:
        st.info("Campaign name column not found in data.")
except Exception as e:
    st.info(f"Top & Bottom Campaigns unavailable: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 14 — Summary Recommendations
# ═══════════════════════════════════════════════════════════════════════════════
section("Summary Recommendations")

try:
    insights = []

    # Highest ROAS brand
    try:
        brand_roas = (
            df.groupby("Brand")
            .agg(spend=("netbasket_amount", "sum"), revenue=("gmv_local", "sum"))
            .assign(ROAS=lambda x: x["revenue"] / x["spend"].replace(0, np.nan))
            .dropna(subset=["ROAS"])
        )
        if not brand_roas.empty:
            best_roas_brand = brand_roas["ROAS"].idxmax()
            best_roas_val   = brand_roas.loc[best_roas_brand, "ROAS"]
            insights.append(
                f"<strong>Highest ROAS Brand:</strong> {best_roas_brand} is delivering the strongest return at "
                f"<strong>{best_roas_val:.2f}x ROAS</strong>. Consider increasing its ad budget to capture more orders."
            )
    except Exception:
        pass

    # Lowest CPC brand
    try:
        if "CPC" in df.columns:
            cpc_brand = df.groupby("Brand")["CPC"].mean().dropna()
            if not cpc_brand.empty:
                low_cpc_brand = cpc_brand.idxmin()
                low_cpc_val   = cpc_brand.min()
                insights.append(
                    f"<strong>Lowest CPC Brand:</strong> {low_cpc_brand} has the most cost-efficient clicks at "
                    f"<strong>AED {low_cpc_val:.2f} per click</strong>. Ideal candidate for scaling impressions."
                )
    except Exception:
        pass

    # Best new user acquisition
    try:
        if "newuser_orders" in df.columns:
            new_acq = df.groupby("Brand")["newuser_orders"].sum().dropna()
            if not new_acq.empty:
                best_new_brand = new_acq.idxmax()
                best_new_val   = new_acq.max()
                insights.append(
                    f"<strong>Best New User Acquisition:</strong> {best_new_brand} acquired the most new customers with "
                    f"<strong>{int(best_new_val):,} new-user orders</strong>. Strong top-of-funnel performance."
                )
    except Exception:
        pass

    # Overall efficiency note
    try:
        total_sp = df["netbasket_amount"].sum()
        total_gm = df["gmv_local"].sum()
        overall  = total_gm / total_sp if total_sp > 0 else 0
        tier     = "above target" if overall >= 3 else ("break-even" if overall >= 1 else "below break-even")
        insights.append(
            f"<strong>Portfolio ROAS:</strong> Overall portfolio ROAS is <strong>{overall:.2f}x</strong> — {tier}. "
            f"{'Maintain current spend allocation.' if overall >= 3 else 'Review underperforming campaigns and reallocate budget to high-ROAS brands.'}"
        )
    except Exception:
        pass

    # Campaigns with ROAS < 1 warning
    try:
        if "ROAS" in df.columns:
            low_roas_brands = (
                df.groupby("Brand")
                .apply(lambda g: (g["netbasket_amount"].sum() > 0) and
                       (g["gmv_local"].sum() / g["netbasket_amount"].sum() < 1))
                .loc[lambda x: x]
                .index.tolist()
            )
            if low_roas_brands:
                insights.append(
                    f"<strong>Underperforming Brands:</strong> {', '.join(low_roas_brands)} are running at below break-even ROAS. "
                    f"Pause or optimise these campaigns before further spend."
                )
    except Exception:
        pass

    if insights:
        for insight in insights:
            st.markdown(
                f'<div class="insight-box">💡 {insight}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("Insufficient data to generate recommendations.")

except Exception as e:
    st.info(f"Recommendations unavailable: {e}")
