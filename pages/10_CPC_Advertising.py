"""
CPC & Advertising Page — Cloud Kitchen Analytics Dashboard
Analyzes CPC paid advertising campaign performance across ALL aggregators
(Talabat, Careem, Noon): spend, impressions, clicks, orders, ROAS, CPC, CPO,
CTR, conversion rates, and user acquisition split (new / repeat / lapsed).

Three-tab layout: Overall | Platform View | Brand View
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

AGG_COLORS = {"Talabat": "#FF5A00", "Careem": "#00B140", "Noon": "#FEEE00"}
AGG_TEXT   = {"Talabat": "#FF5A00", "Careem": "#00B140", "Noon": "#C4A800"}

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
    .kpi-card.talabat { border-left-color: #FF5A00; }
    .kpi-card.careem  { border-left-color: #00B140; }
    .kpi-card.noon    { border-left-color: #C4A800; }
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
    .agg-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 6px;
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

def kpi_card(label, value, sub="", css_class=""):
    st.markdown(
        f"""
        <div class="kpi-card {css_class}">
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

def safe_roas(revenue, spend):
    """Calculate ROAS safely."""
    return revenue / spend if spend > 0 else 0

def chart_layout(**kwargs):
    """Common chart layout."""
    base = dict(template=TEMPLATE, paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG)
    base.update(kwargs)
    return base

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

# Aggregator filter
all_aggs = sorted(df_work["Aggregator"].dropna().unique().tolist()) if "Aggregator" in df_work.columns else []
sel_aggs = st.sidebar.multiselect("Aggregator / Platform", all_aggs, default=all_aggs)

# Ad Product filter
all_prods = sorted(df_work["Ad Product"].dropna().unique().tolist()) if "Ad Product" in df_work.columns else []
sel_prods = st.sidebar.multiselect("Ad Product", all_prods, default=all_prods)

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

if sel_aggs:
    df = df[df["Aggregator"].isin(sel_aggs)]
if sel_prods:
    df = df[df["Ad Product"].isin(sel_prods)]
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

agg_counts = df["Aggregator"].value_counts()
agg_summary = " | ".join([f"**{a}**: {c:,} records" for a, c in agg_counts.items()])
st.caption(f"Multi-platform ad performance — {agg_summary}")

# ═════════════════════════════════════════════════════════════════════════════
# TABS
# ═════════════════════════════════════════════════════════════════════════════
tab_overall, tab_platform, tab_brand = st.tabs(["📊 Overall View", "🏢 Platform View", "🏷️ Brand View"])

# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — OVERALL VIEW
# ═════════════════════════════════════════════════════════════════════════════
with tab_overall:

    # ── KPIs ──
    section("Key Performance Indicators")
    try:
        total_spend       = df["netbasket_amount"].sum()
        total_impressions = df["impressions"].sum()
        total_clicks      = df["clicks"].sum()
        total_orders      = df["orders"].sum()
        overall_roas      = safe_roas(df["gmv_local"].sum(), total_spend)
        avg_cpc           = df["CPC"].mean() if "CPC" in df.columns else 0
    except Exception:
        total_spend = total_impressions = total_clicks = total_orders = overall_roas = avg_cpc = 0

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1: kpi_card("Total Spend", fmt_currency(total_spend), f"across {len(agg_counts)} platforms")
    with k2: kpi_card("Total Impressions", fmt_number(total_impressions), "ad views")
    with k3: kpi_card("Total Clicks", fmt_number(total_clicks), "link clicks")
    with k4: kpi_card("Total Orders", fmt_number(total_orders), "conversions")
    with k5: kpi_card("Overall ROAS", fmt_x(overall_roas), "return on ad spend")
    with k6: kpi_card("Avg CPC", fmt_currency(avg_cpc, 2), "cost per click")

    # ── Campaign Performance Table ──
    section("Campaign Performance Table")
    try:
        camp_group_cols = [c for c in ["Aggregator", "Ad Product", "campaign_name", "campaign_type", "Brand", "Cuisine"] if c in df.columns]
        camp_metric_sum = [c for c in ["impressions", "clicks", "orders", "netbasket_amount", "gmv_local"] if c in df.columns]
        camp_metric_avg = [c for c in ["ROAS", "CPC", "CPO", "CTR", "Conversion Rate"] if c in df.columns]
        camp_df = (
            df[camp_group_cols + camp_metric_sum + camp_metric_avg]
            .groupby(camp_group_cols)
            .agg({**{c: "sum" for c in camp_metric_sum}, **{c: "mean" for c in camp_metric_avg}})
            .reset_index()
            .sort_values("ROAS" if "ROAS" in camp_metric_avg else camp_group_cols[0], ascending=False)
        )
        sort_by = st.selectbox("Sort campaigns by", options=[c for c in ["ROAS", "netbasket_amount", "orders", "impressions"] if c in camp_df.columns], index=0)
        camp_df = camp_df.sort_values(sort_by, ascending=False)
        fmt_map = {}
        for c in ["netbasket_amount", "gmv_local", "CPC", "CPO"]:
            if c in camp_df.columns: fmt_map[c] = "AED {:,.2f}"
        for c in ["ROAS"]:
            if c in camp_df.columns: fmt_map[c] = "{:.2f}x"
        for c in ["CTR", "Conversion Rate"]:
            if c in camp_df.columns: fmt_map[c] = "{:.2f}%"
        st.dataframe(camp_df.style.format(fmt_map), use_container_width=True, height=400)
    except Exception as e:
        st.info(f"Campaign table unavailable: {e}")

    # ── Monthly Trends ──
    section("Monthly Trends — Spend, GMV & ROAS")
    try:
        monthly_df = (
            df.groupby("Month")
            .agg(spend=("netbasket_amount", "sum"), gmv=("gmv_local", "sum"), orders=("orders", "sum"))
            .reset_index().sort_values("Month")
        )
        monthly_df["ROAS"] = monthly_df.apply(lambda r: safe_roas(r["gmv"], r["spend"]), axis=1)
        fig_monthly = make_subplots(specs=[[{"secondary_y": True}]])
        fig_monthly.add_trace(go.Bar(x=monthly_df["Month"], y=monthly_df["spend"], name="Spend (AED)", marker_color=PRIMARY, opacity=0.75), secondary_y=False)
        fig_monthly.add_trace(go.Scatter(x=monthly_df["Month"], y=monthly_df["gmv"], name="GMV (AED)", mode="lines+markers", line=dict(color=SECONDARY, width=2)), secondary_y=False)
        fig_monthly.add_trace(go.Scatter(x=monthly_df["Month"], y=monthly_df["ROAS"], name="ROAS", mode="lines+markers", line=dict(color=ACCENT, width=2, dash="dot")), secondary_y=True)
        fig_monthly.update_layout(**chart_layout(height=400, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), margin=dict(l=10, r=60, t=40, b=40)))
        fig_monthly.update_yaxes(title_text="Amount (AED)", secondary_y=False)
        fig_monthly.update_yaxes(title_text="ROAS", secondary_y=True)
        st.plotly_chart(fig_monthly, use_container_width=True)
    except Exception as e:
        st.info(f"Monthly Trends chart unavailable: {e}")

    # ── Funnel ──
    section("Impressions Funnel: Impressions → Clicks → Orders")
    try:
        total_imp = df["impressions"].sum()
        total_clk = df["clicks"].sum()
        total_ord = df["orders"].sum()
        ctr_pct  = (total_clk / total_imp * 100) if total_imp > 0 else 0
        conv_pct = (total_ord / total_clk * 100) if total_clk > 0 else 0
        fig_funnel = go.Figure(go.Funnel(
            y=["Impressions", "Clicks", "Orders"],
            x=[total_imp, total_clk, total_ord],
            textinfo="value+percent initial",
            marker=dict(color=[PRIMARY, SECONDARY, ACCENT]),
            connector=dict(line=dict(color="#ccc", width=1)),
        ))
        fig_funnel.update_layout(**chart_layout(height=350, margin=dict(l=10, r=10, t=20, b=20)))
        fc1, fc2, fc3 = st.columns([2, 1, 1])
        with fc1: st.plotly_chart(fig_funnel, use_container_width=True)
        with fc2: kpi_card("Click-Through Rate", fmt_pct(ctr_pct), f"{fmt_number(total_clk)} of {fmt_number(total_imp)}")
        with fc3: kpi_card("Conversion Rate", fmt_pct(conv_pct), f"{fmt_number(total_ord)} of {fmt_number(total_clk)}")
    except Exception as e:
        st.info(f"Impressions Funnel unavailable: {e}")

    # ── Top & Bottom 5 Campaigns ──
    section("Top 5 & Bottom 5 Campaigns by ROAS")
    try:
        if "campaign_name" in df.columns:
            camp_roas = (
                df.groupby(["Aggregator", "campaign_name", "campaign_type", "Brand"])
                .agg(spend=("netbasket_amount", "sum"), revenue=("gmv_local", "sum"), orders=("orders", "sum"), impressions=("impressions", "sum"))
                .reset_index()
            )
            camp_roas["ROAS"] = camp_roas.apply(lambda r: safe_roas(r["revenue"], r["spend"]), axis=1)
            # Filter out zero-spend
            camp_roas_valid = camp_roas[camp_roas["spend"] > 0]
            top5 = camp_roas_valid.nlargest(5, "ROAS")
            bottom5 = camp_roas_valid.nsmallest(5, "ROAS")
            t_col, b_col = st.columns(2)
            with t_col:
                st.markdown("**Top 5 Campaigns**")
                for _, row in top5.iterrows():
                    try:
                        st.markdown(f"""<div class="campaign-card top-card">
                        <strong>{row.get("campaign_name","N/A")}</strong>
                        &nbsp;<span style="color:#666;font-size:0.82rem">{row.get("Brand","")} — {row.get("Aggregator","")}</span><br>
                        ROAS <strong style="color:{ROAS_GREEN}">{row.get("ROAS",0):.2f}x</strong> &nbsp;|&nbsp;
                        Spend <strong>AED {row.get("spend",0):,.0f}</strong> &nbsp;|&nbsp;
                        Orders <strong>{int(row.get("orders",0)):,}</strong>
                        </div>""", unsafe_allow_html=True)
                    except Exception:
                        pass
            with b_col:
                st.markdown("**Bottom 5 Campaigns**")
                for _, row in bottom5.iterrows():
                    try:
                        st.markdown(f"""<div class="campaign-card bottom-card">
                        <strong>{row.get("campaign_name","N/A")}</strong>
                        &nbsp;<span style="color:#666;font-size:0.82rem">{row.get("Brand","")} — {row.get("Aggregator","")}</span><br>
                        ROAS <strong style="color:{ROAS_RED}">{row.get("ROAS",0):.2f}x</strong> &nbsp;|&nbsp;
                        Spend <strong>AED {row.get("spend",0):,.0f}</strong> &nbsp;|&nbsp;
                        Orders <strong>{int(row.get("orders",0)):,}</strong>
                        </div>""", unsafe_allow_html=True)
                    except Exception:
                        pass
    except Exception as e:
        st.info(f"Top & Bottom Campaigns unavailable: {e}")

    # ── Summary Recommendations ──
    section("Summary Recommendations")
    try:
        insights = []
        brand_roas = (
            df.groupby("Brand")
            .agg(spend=("netbasket_amount", "sum"), revenue=("gmv_local", "sum"))
            .assign(ROAS=lambda x: x["revenue"] / x["spend"].replace(0, np.nan))
            .dropna(subset=["ROAS"])
        )
        if not brand_roas.empty:
            best = brand_roas["ROAS"].idxmax()
            insights.append(f"<strong>Highest ROAS Brand:</strong> {best} at <strong>{brand_roas.loc[best, 'ROAS']:.2f}x ROAS</strong>. Consider increasing its ad budget.")

        if "CPC" in df.columns:
            cpc_brand = df.groupby("Brand")["CPC"].mean().dropna()
            if not cpc_brand.empty:
                low = cpc_brand.idxmin()
                insights.append(f"<strong>Lowest CPC Brand:</strong> {low} at <strong>AED {cpc_brand.min():.2f}/click</strong>. Ideal for scaling impressions.")

        total_sp = df["netbasket_amount"].sum()
        total_gm = df["gmv_local"].sum()
        overall = safe_roas(total_gm, total_sp)
        tier = "above target" if overall >= 3 else ("break-even" if overall >= 1 else "below break-even")
        insights.append(f"<strong>Portfolio ROAS:</strong> Overall <strong>{overall:.2f}x</strong> — {tier}.")

        # Per-platform insight
        for agg in df["Aggregator"].unique():
            agg_df = df[df["Aggregator"] == agg]
            sp = agg_df["netbasket_amount"].sum()
            gm = agg_df["gmv_local"].sum()
            r = safe_roas(gm, sp)
            if r > 0:
                insights.append(f"<strong>{agg}:</strong> ROAS <strong>{r:.2f}x</strong> on AED {sp:,.0f} spend → AED {gm:,.0f} GMV.")

        for insight in insights:
            st.markdown(f'<div class="insight-box">💡 {insight}</div>', unsafe_allow_html=True)
    except Exception as e:
        st.info(f"Recommendations unavailable: {e}")

# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — PLATFORM VIEW
# ═════════════════════════════════════════════════════════════════════════════
with tab_platform:

    # ── Platform KPIs side-by-side ──
    section("Platform Comparison — KPIs")
    platforms = sorted(df["Aggregator"].dropna().unique())
    cols = st.columns(len(platforms)) if platforms else []
    for col, agg in zip(cols, platforms):
        a = df[df["Aggregator"] == agg]
        sp = a["netbasket_amount"].sum()
        gm = a["gmv_local"].sum()
        r  = safe_roas(gm, sp)
        with col:
            kpi_card(f"{agg} — Spend", fmt_currency(sp), f"{len(a):,} records", css_class=agg.lower())
            kpi_card(f"{agg} — GMV", fmt_currency(gm), f"ROAS: {r:.2f}x", css_class=agg.lower())
            kpi_card(f"{agg} — Orders", fmt_number(a["orders"].sum()), f"Clicks: {fmt_number(a['clicks'].sum())}", css_class=agg.lower())

    # ── Spend / Revenue / ROAS by Platform ──
    section("Spend, Revenue & ROAS by Platform")
    try:
        plat_df = (
            df.groupby("Aggregator")
            .agg(spend=("netbasket_amount", "sum"), revenue=("gmv_local", "sum"),
                 orders=("orders", "sum"), clicks=("clicks", "sum"))
            .reset_index()
        )
        plat_df["ROAS"] = plat_df.apply(lambda r: safe_roas(r["revenue"], r["spend"]), axis=1)
        plat_df["color"] = plat_df["Aggregator"].map(AGG_COLORS)

        p1, p2 = st.columns(2)
        with p1:
            fig_plat_bar = go.Figure()
            fig_plat_bar.add_trace(go.Bar(
                name="Spend", x=plat_df["Aggregator"], y=plat_df["spend"],
                marker_color=PRIMARY, text=plat_df["spend"].apply(lambda v: f"AED {v:,.0f}"), textposition="outside",
            ))
            fig_plat_bar.add_trace(go.Bar(
                name="Revenue", x=plat_df["Aggregator"], y=plat_df["revenue"],
                marker_color=SECONDARY, text=plat_df["revenue"].apply(lambda v: f"AED {v:,.0f}"), textposition="outside",
            ))
            fig_plat_bar.update_layout(**chart_layout(
                barmode="group", height=400,
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                margin=dict(l=10, r=10, t=40, b=40),
                yaxis_title="Amount (AED)",
            ))
            st.plotly_chart(fig_plat_bar, use_container_width=True)
        with p2:
            fig_plat_roas = go.Figure(go.Bar(
                x=plat_df["Aggregator"], y=plat_df["ROAS"],
                marker_color=[AGG_COLORS.get(a, PRIMARY) for a in plat_df["Aggregator"]],
                text=plat_df["ROAS"].apply(lambda v: f"{v:.2f}x"), textposition="outside",
            ))
            fig_plat_roas.add_hline(y=3, line_dash="dash", line_color=ROAS_GREEN, annotation_text="3x target")
            fig_plat_roas.add_hline(y=1, line_dash="dot", line_color=ROAS_RED, annotation_text="break-even")
            fig_plat_roas.update_layout(**chart_layout(
                height=400, yaxis_title="ROAS",
                margin=dict(l=10, r=10, t=40, b=40),
            ))
            st.plotly_chart(fig_plat_roas, use_container_width=True)
    except Exception as e:
        st.info(f"Platform comparison unavailable: {e}")

    # ── CPC & CPO by Platform ──
    section("CPC & CPO by Platform")
    try:
        plat_cost = (
            df.groupby("Aggregator")
            .agg(spend=("netbasket_amount", "sum"), clicks=("clicks", "sum"), orders=("orders", "sum"))
            .reset_index()
        )
        plat_cost["CPC"] = plat_cost.apply(lambda r: r["spend"] / r["clicks"] if r["clicks"] > 0 else 0, axis=1)
        plat_cost["CPO"] = plat_cost.apply(lambda r: r["spend"] / r["orders"] if r["orders"] > 0 else 0, axis=1)

        pc1, pc2 = st.columns(2)
        with pc1:
            fig_pcpc = px.bar(plat_cost, x="Aggregator", y="CPC", color="Aggregator",
                              color_discrete_map=AGG_COLORS, template=TEMPLATE, text_auto=".2f",
                              labels={"CPC": "Avg CPC (AED)"})
            fig_pcpc.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, height=350, showlegend=False, margin=dict(l=10,r=10,t=20,b=40))
            st.plotly_chart(fig_pcpc, use_container_width=True)
        with pc2:
            fig_pcpo = px.bar(plat_cost, x="Aggregator", y="CPO", color="Aggregator",
                              color_discrete_map=AGG_COLORS, template=TEMPLATE, text_auto=".2f",
                              labels={"CPO": "Avg CPO (AED)"})
            fig_pcpo.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, height=350, showlegend=False, margin=dict(l=10,r=10,t=20,b=40))
            st.plotly_chart(fig_pcpo, use_container_width=True)
    except Exception as e:
        st.info(f"Platform CPC/CPO unavailable: {e}")

    # ── Platform Efficiency Scatter ──
    section("Platform Efficiency Matrix (CPC vs ROAS)")
    try:
        plat_eff = (
            df.groupby("Aggregator")
            .agg(spend=("netbasket_amount", "sum"), revenue=("gmv_local", "sum"),
                 clicks=("clicks", "sum"), orders=("orders", "sum"))
            .reset_index()
        )
        plat_eff["CPC"] = plat_eff.apply(lambda r: r["spend"]/r["clicks"] if r["clicks"]>0 else 0, axis=1)
        plat_eff["ROAS"] = plat_eff.apply(lambda r: safe_roas(r["revenue"], r["spend"]), axis=1)
        fig_peff = px.scatter(plat_eff, x="CPC", y="ROAS", size="orders", color="Aggregator",
                              color_discrete_map=AGG_COLORS, hover_data={"orders": ":,", "spend": ":,.0f"},
                              labels={"CPC": "CPC (AED)", "ROAS": "ROAS"}, template=TEMPLATE, size_max=80)
        fig_peff.add_hline(y=3, line_dash="dash", line_color=ROAS_GREEN, annotation_text="3x")
        fig_peff.add_hline(y=1, line_dash="dot", line_color=ROAS_RED, annotation_text="break-even")
        fig_peff.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, height=420, margin=dict(l=10,r=10,t=20,b=40))
        st.plotly_chart(fig_peff, use_container_width=True)
    except Exception as e:
        st.info(f"Platform Efficiency Matrix unavailable: {e}")

    # ── Monthly ROAS Trend by Platform ──
    section("Monthly ROAS Trend by Platform")
    try:
        plat_trend = (
            df.groupby(["Month", "Aggregator"])
            .agg(spend=("netbasket_amount", "sum"), revenue=("gmv_local", "sum"))
            .reset_index().sort_values("Month")
        )
        plat_trend["ROAS"] = plat_trend.apply(lambda r: safe_roas(r["revenue"], r["spend"]), axis=1)
        fig_pt = px.line(plat_trend, x="Month", y="ROAS", color="Aggregator",
                         color_discrete_map=AGG_COLORS, markers=True, template=TEMPLATE,
                         labels={"ROAS": "ROAS", "Month": "Month"})
        fig_pt.add_hline(y=3, line_dash="dash", line_color=ROAS_GREEN, annotation_text="3x target")
        fig_pt.add_hline(y=1, line_dash="dot", line_color=ROAS_RED, annotation_text="break-even")
        fig_pt.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, height=420,
                             legend=dict(orientation="h", yanchor="bottom", y=1.02), margin=dict(l=10,r=10,t=40,b=40))
        st.plotly_chart(fig_pt, use_container_width=True)
    except Exception as e:
        st.info(f"Monthly Platform ROAS Trend unavailable: {e}")

    # ── User Acquisition by Platform ──
    section("User Acquisition by Platform")
    try:
        usr_cols = [c for c in ["newuser_orders", "repeatuser_orders", "lapseduser_orders"] if c in df.columns]
        if usr_cols:
            usr_plat = df.groupby("Aggregator")[usr_cols].sum().reset_index()
            usr_plat_melt = usr_plat.melt(id_vars="Aggregator", var_name="User Type", value_name="Orders")
            usr_plat_melt["User Type"] = usr_plat_melt["User Type"].str.replace("user_orders", "").str.replace("_orders", "").str.capitalize()
            fig_usr_plat = px.bar(usr_plat_melt, x="Aggregator", y="Orders", color="User Type",
                                  color_discrete_map={"New": ROAS_GREEN, "Repeat": SECONDARY, "Lapsed": ROAS_YELLOW,
                                                      "Newuser": ROAS_GREEN, "Repeatuser": SECONDARY, "Lapseduser": ROAS_YELLOW},
                                  template=TEMPLATE, barmode="stack")
            fig_usr_plat.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, height=380,
                                       margin=dict(l=10,r=10,t=20,b=40),
                                       legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig_usr_plat, use_container_width=True)
        else:
            st.info("User acquisition data not available for platform comparison.")
    except Exception as e:
        st.info(f"User Acquisition by Platform unavailable: {e}")

    # ── Ad Product Breakdown ──
    section("Ad Product Performance")
    try:
        prod_df = (
            df.groupby(["Aggregator", "Ad Product"])
            .agg(spend=("netbasket_amount", "sum"), revenue=("gmv_local", "sum"),
                 orders=("orders", "sum"), clicks=("clicks", "sum"))
            .reset_index()
        )
        prod_df["ROAS"] = prod_df.apply(lambda r: safe_roas(r["revenue"], r["spend"]), axis=1)
        prod_df["CPC"]  = prod_df.apply(lambda r: r["spend"]/r["clicks"] if r["clicks"]>0 else 0, axis=1)

        st.dataframe(
            prod_df.style.format({
                "spend": "AED {:,.2f}", "revenue": "AED {:,.2f}",
                "ROAS": "{:.2f}x", "CPC": "AED {:,.2f}",
                "orders": "{:,.0f}", "clicks": "{:,.0f}",
            }),
            use_container_width=True, height=300,
        )
    except Exception as e:
        st.info(f"Ad Product breakdown unavailable: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — BRAND VIEW
# ═════════════════════════════════════════════════════════════════════════════
with tab_brand:

    # ── ROAS by Brand (colored by aggregator) ──
    section("ROAS by Brand")
    try:
        roas_brand = (
            df.groupby(["Brand", "Aggregator"])
            .agg(spend=("netbasket_amount", "sum"), revenue=("gmv_local", "sum"))
            .reset_index()
        )
        roas_brand["ROAS"] = roas_brand.apply(lambda r: safe_roas(r["revenue"], r["spend"]), axis=1)
        roas_brand = roas_brand.sort_values("ROAS", ascending=True)

        fig_roas = px.bar(
            roas_brand, x="ROAS", y="Brand", orientation="h", color="Aggregator",
            color_discrete_map=AGG_COLORS, template=TEMPLATE,
            labels={"ROAS": "ROAS", "Brand": ""},
            text=roas_brand["ROAS"].apply(lambda v: f"{v:.2f}x"),
        )
        fig_roas.add_vline(x=3, line_dash="dash", line_color=ROAS_GREEN, annotation_text="3x target")
        fig_roas.add_vline(x=1, line_dash="dot", line_color=ROAS_RED, annotation_text="break-even")
        fig_roas.update_layout(**chart_layout(
            height=max(400, len(roas_brand["Brand"].unique()) * 30),
            margin=dict(l=10, r=60, t=20, b=40),
            barmode="group",
        ))
        st.plotly_chart(fig_roas, use_container_width=True)
    except Exception as e:
        st.info(f"ROAS by Brand chart unavailable: {e}")

    # ── Brand × Aggregator Heatmap ──
    section("Brand × Aggregator Heatmap (ROAS)")
    try:
        heat_df = (
            df.groupby(["Brand", "Aggregator"])
            .agg(spend=("netbasket_amount", "sum"), revenue=("gmv_local", "sum"))
            .reset_index()
        )
        heat_df["ROAS"] = heat_df.apply(lambda r: safe_roas(r["revenue"], r["spend"]), axis=1)
        heat_pivot = heat_df.pivot_table(index="Brand", columns="Aggregator", values="ROAS", fill_value=0)

        fig_heat = px.imshow(
            heat_pivot, text_auto=".2f",
            color_continuous_scale=["#F8F9FA", ROAS_GREEN],
            labels=dict(color="ROAS"),
            template=TEMPLATE,
        )
        fig_heat.update_layout(paper_bgcolor=PAPER_BG, height=max(400, len(heat_pivot) * 28),
                               margin=dict(l=10, r=10, t=20, b=40))
        st.plotly_chart(fig_heat, use_container_width=True)
    except Exception as e:
        st.info(f"Brand × Aggregator Heatmap unavailable: {e}")

    # ── Spend vs Revenue Scatter ──
    section("Spend vs Revenue by Brand")
    try:
        scatter_df = (
            df.groupby(["Brand", "Aggregator"])
            .agg(spend=("netbasket_amount", "sum"), revenue=("gmv_local", "sum"), orders=("orders", "sum"))
            .reset_index()
        )
        fig_scatter = px.scatter(
            scatter_df, x="spend", y="revenue", size="orders", color="Aggregator",
            color_discrete_map=AGG_COLORS, hover_name="Brand",
            labels={"spend": "Ad Spend (AED)", "revenue": "GMV Revenue (AED)"},
            template=TEMPLATE, size_max=60,
        )
        max_val = max(scatter_df["spend"].max(), scatter_df["revenue"].max()) * 1.1
        fig_scatter.add_trace(go.Scatter(x=[0, max_val], y=[0, max_val], mode="lines",
                                          line=dict(dash="dash", color="#888", width=1), name="Break-even", hoverinfo="skip"))
        fig_scatter.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, height=420, margin=dict(l=10,r=10,t=20,b=40))
        st.plotly_chart(fig_scatter, use_container_width=True)
    except Exception as e:
        st.info(f"Spend vs Revenue chart unavailable: {e}")

    # ── CTR & Conversion Rate by Brand ──
    section("CTR & Conversion Rate by Brand")
    try:
        rate_df = (
            df.groupby("Brand")
            .agg(impressions=("impressions", "sum"), clicks=("clicks", "sum"), orders=("orders", "sum"))
            .reset_index()
        )
        rate_df["CTR"] = rate_df.apply(lambda r: r["clicks"]/r["impressions"]*100 if r["impressions"]>0 else 0, axis=1)
        rate_df["Conv"] = rate_df.apply(lambda r: r["orders"]/r["clicks"]*100 if r["clicks"]>0 else 0, axis=1)
        rate_df = rate_df.sort_values("CTR", ascending=True)
        fig_rates = make_subplots(rows=1, cols=2, subplot_titles=["CTR (%)", "Conversion Rate (%)"])
        fig_rates.add_trace(go.Bar(y=rate_df["Brand"], x=rate_df["CTR"], orientation="h", marker_color=PRIMARY, name="CTR",
                                   text=rate_df["CTR"].apply(lambda v: f"{v:.2f}%"), textposition="outside"), row=1, col=1)
        fig_rates.add_trace(go.Bar(y=rate_df["Brand"], x=rate_df["Conv"], orientation="h", marker_color=SECONDARY, name="Conv Rate",
                                   text=rate_df["Conv"].apply(lambda v: f"{v:.2f}%"), textposition="outside"), row=1, col=2)
        fig_rates.update_layout(**chart_layout(showlegend=False, height=max(350, len(rate_df)*30), margin=dict(l=10,r=60,t=40,b=20)))
        st.plotly_chart(fig_rates, use_container_width=True)
    except Exception as e:
        st.info(f"CTR & Conversion Rate chart unavailable: {e}")

    # ── CPC & CPO by Brand ──
    section("CPC & CPO by Brand")
    try:
        cost_df = (
            df.groupby("Brand")
            .agg(spend=("netbasket_amount", "sum"), clicks=("clicks", "sum"), orders=("orders", "sum"))
            .reset_index()
        )
        cost_df["CPC"] = cost_df.apply(lambda r: r["spend"]/r["clicks"] if r["clicks"]>0 else 0, axis=1)
        cost_df["CPO"] = cost_df.apply(lambda r: r["spend"]/r["orders"] if r["orders"]>0 else 0, axis=1)
        cost_df = cost_df.sort_values("CPC", ascending=False)
        cc1, cc2 = st.columns(2)
        with cc1:
            fig_cpc = px.bar(cost_df, x="Brand", y="CPC", color_discrete_sequence=[PRIMARY],
                             labels={"CPC": "Avg CPC (AED)"}, template=TEMPLATE, text_auto=".2f")
            fig_cpc.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, height=380, xaxis_tickangle=-35, margin=dict(l=10,r=10,t=20,b=80))
            st.plotly_chart(fig_cpc, use_container_width=True)
        with cc2:
            fig_cpo = px.bar(cost_df, x="Brand", y="CPO", color_discrete_sequence=[SECONDARY],
                             labels={"CPO": "Avg CPO (AED)"}, template=TEMPLATE, text_auto=".2f")
            fig_cpo.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, height=380, xaxis_tickangle=-35, margin=dict(l=10,r=10,t=20,b=80))
            st.plotly_chart(fig_cpo, use_container_width=True)
    except Exception as e:
        st.info(f"CPC & CPO charts unavailable: {e}")

    # ── Brand Efficiency Matrix ──
    section("Brand Efficiency Matrix (CPC vs ROAS)")
    try:
        eff_df = (
            df.groupby(["Brand", "Cuisine"])
            .agg(spend=("netbasket_amount", "sum"), revenue=("gmv_local", "sum"),
                 clicks=("clicks", "sum"), orders=("orders", "sum"))
            .reset_index()
        )
        eff_df["CPC"] = eff_df.apply(lambda r: r["spend"]/r["clicks"] if r["clicks"]>0 else 0, axis=1)
        eff_df["ROAS"] = eff_df.apply(lambda r: safe_roas(r["revenue"], r["spend"]), axis=1)
        fig_matrix = px.scatter(
            eff_df, x="CPC", y="ROAS", size="orders", color="Cuisine",
            color_discrete_sequence=PALETTE, hover_name="Brand",
            hover_data={"orders": ":,", "CPC": ":.2f", "ROAS": ":.2f"},
            labels={"CPC": "Avg CPC (AED)", "ROAS": "ROAS"}, template=TEMPLATE, size_max=60,
        )
        fig_matrix.add_hline(y=3, line_dash="dash", line_color=ROAS_GREEN, annotation_text="3x ROAS")
        fig_matrix.add_hline(y=1, line_dash="dot", line_color=ROAS_RED, annotation_text="break-even")
        fig_matrix.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, height=450, margin=dict(l=10,r=10,t=20,b=40))
        st.plotly_chart(fig_matrix, use_container_width=True)
    except Exception as e:
        st.info(f"Brand Efficiency Matrix unavailable: {e}")

    # ── Monthly ROAS Trend by Brand ──
    section("Monthly ROAS Trend by Brand")
    try:
        trend_df = (
            df.groupby(["Month", "Brand"])
            .agg(spend=("netbasket_amount", "sum"), revenue=("gmv_local", "sum"))
            .reset_index().sort_values("Month")
        )
        trend_df["ROAS"] = trend_df.apply(lambda r: safe_roas(r["revenue"], r["spend"]), axis=1)
        fig_trend = px.line(trend_df, x="Month", y="ROAS", color="Brand",
                            color_discrete_sequence=PALETTE, markers=True, template=TEMPLATE)
        fig_trend.add_hline(y=3, line_dash="dash", line_color=ROAS_GREEN, annotation_text="3x target")
        fig_trend.add_hline(y=1, line_dash="dot", line_color=ROAS_RED, annotation_text="break-even")
        fig_trend.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, height=420,
                                legend=dict(orientation="h", yanchor="bottom", y=1.02), margin=dict(l=10,r=10,t=40,b=40))
        st.plotly_chart(fig_trend, use_container_width=True)
    except Exception as e:
        st.info(f"Monthly ROAS Trend unavailable: {e}")

    # ── User Acquisition by Brand ──
    section("User Acquisition Analysis")
    try:
        usr_cols = [c for c in ["newuser_orders", "repeatuser_orders", "lapseduser_orders"] if c in df.columns]
        if usr_cols:
            usr_df = df.groupby("Brand")[usr_cols].sum().reset_index()
            usr_df.columns = [c.replace("user_orders", "").replace("_orders", "").capitalize() if c != "Brand" else c for c in usr_df.columns]
            usr_melt = usr_df.melt(id_vars="Brand", var_name="User Type", value_name="Orders")
            ua1, ua2 = st.columns([3, 2])
            with ua1:
                fig_usr_bar = px.bar(usr_melt, x="Brand", y="Orders", color="User Type",
                                     color_discrete_map={"New": ROAS_GREEN, "Repeat": SECONDARY, "Lapsed": ROAS_YELLOW,
                                                         "Newuser": ROAS_GREEN, "Repeatuser": SECONDARY, "Lapseduser": ROAS_YELLOW},
                                     template=TEMPLATE)
                fig_usr_bar.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, height=380,
                                          xaxis_tickangle=-35, margin=dict(l=10,r=10,t=20,b=80),
                                          legend=dict(orientation="h", yanchor="bottom", y=1.02))
                st.plotly_chart(fig_usr_bar, use_container_width=True)
            with ua2:
                pie_vals = [usr_df[c].sum() for c in usr_df.columns if c != "Brand"]
                pie_labels = [c for c in usr_df.columns if c != "Brand"]
                fig_pie = go.Figure(go.Pie(labels=pie_labels, values=pie_vals, hole=0.45,
                                           marker_colors=[ROAS_GREEN, SECONDARY, ROAS_YELLOW], textinfo="label+percent"))
                fig_pie.update_layout(template=TEMPLATE, paper_bgcolor=PAPER_BG, height=380, margin=dict(l=10,r=10,t=20,b=20))
                st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("User acquisition order columns not found.")
    except Exception as e:
        st.info(f"User Acquisition Analysis unavailable: {e}")

    # ── User GMV Analysis ──
    section("User GMV Analysis")
    try:
        gmv_usr_cols = [c for c in ["newuser_gmv", "repeatuser_gmv", "lapseduser_gmv"] if c in df.columns]
        if gmv_usr_cols:
            gmv_usr = df.groupby("Brand")[gmv_usr_cols].sum().reset_index()
            gmv_usr_melt = gmv_usr.melt(id_vars="Brand", var_name="User Type", value_name="GMV")
            gmv_usr_melt["User Type"] = gmv_usr_melt["User Type"].str.replace("_gmv", "").str.replace("user", " User").str.title()
            fig_gmv_usr = px.bar(gmv_usr_melt, x="Brand", y="GMV", color="User Type",
                                 color_discrete_map={"New User": ROAS_GREEN, "Repeat User": SECONDARY, "Lapsed User": ROAS_YELLOW},
                                 template=TEMPLATE, labels={"GMV": "GMV (AED)"})
            fig_gmv_usr.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, height=380,
                                      xaxis_tickangle=-35, margin=dict(l=10,r=10,t=20,b=80),
                                      legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig_gmv_usr, use_container_width=True)
        else:
            st.info("User GMV columns not found.")
    except Exception as e:
        st.info(f"User GMV Analysis unavailable: {e}")
