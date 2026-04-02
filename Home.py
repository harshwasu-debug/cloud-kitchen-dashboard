"""
Cloud Kitchen Command Center — Executive Summary Dashboard (Home Page)
Main entry point for the Streamlit multi-page dashboard.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from utils.data_loader import (
    load_sales_orders,
    load_sales_brand,
    load_sales_channels,
    load_sales_location,
    load_cancelled_orders,
    get_all_brands,
    get_all_locations,
    get_all_channels,
    get_date_range,
)

# ─── CONSTANTS ──────────────────────────────────────────────────────────────

PRIMARY   = "#FF6B35"
SECONDARY = "#4ECDC4"
ACCENT    = "#FFE66D"
DARK      = "#2C3E50"
TEMPLATE  = "plotly_dark"

PALETTE = [
    PRIMARY, SECONDARY, ACCENT, "#A8E6CF", "#FF8B94",
    "#B5EAD7", "#C7CEEA", "#FFDAC1", "#E2F0CB", "#F0E6FF",
]

# ─── PAGE CONFIG ────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Cloud Kitchen Command Center",
    page_icon="🍕",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── GLOBAL STYLES ──────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
        /* Main background */
        .stApp { background-color: #1a1f2e; }

        /* Metric card styling */
        [data-testid="metric-container"] {
            background: linear-gradient(135deg, #1e2535 0%, #252d40 100%);
            border: 1px solid #2e3a50;
            border-radius: 12px;
            padding: 16px 20px;
        }
        [data-testid="metric-container"] label {
            color: #8b9ab5 !important;
            font-size: 0.78rem !important;
            font-weight: 600 !important;
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }
        [data-testid="metric-container"] [data-testid="stMetricValue"] {
            color: #e8eaf0 !important;
            font-size: 1.65rem !important;
            font-weight: 700 !important;
        }
        [data-testid="metric-container"] [data-testid="stMetricDelta"] {
            font-size: 0.82rem !important;
        }

        /* Section headers */
        .section-header {
            color: #e8eaf0;
            font-size: 1.1rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            margin: 0.25rem 0 0.75rem 0;
            padding-bottom: 6px;
            border-bottom: 2px solid #FF6B35;
            display: inline-block;
        }

        /* Sidebar styling */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #1a1f2e 0%, #0f1318 100%);
            border-right: 1px solid #2e3a50;
        }
        [data-testid="stSidebar"] .stMarkdown p {
            color: #8b9ab5;
        }

        /* Dividers */
        hr { border-color: #2e3a50 !important; }

        /* Data source badge */
        .ds-badge {
            background: #1e2535;
            border: 1px solid #4ECDC4;
            border-radius: 8px;
            padding: 8px 12px;
            color: #4ECDC4;
            font-size: 0.8rem;
            font-weight: 600;
        }
        .ds-soon {
            background: #1e2535;
            border: 1px dashed #3a4555;
            border-radius: 8px;
            padding: 6px 12px;
            color: #3a4555;
            font-size: 0.75rem;
            margin-top: 4px;
        }

        /* KPI row label */
        .kpi-row-label {
            color: #5a6a80;
            font-size: 0.7rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-bottom: 0.4rem;
        }

        /* Table styling */
        .stDataFrame { border-radius: 10px; overflow: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── LOAD DATA ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _load_all():
    orders    = load_sales_orders()
    brand_df  = load_sales_brand()
    chan_df   = load_sales_channels()
    loc_df    = load_sales_location()
    cancel_df = load_cancelled_orders()
    return orders, brand_df, chan_df, loc_df, cancel_df


with st.spinner("Loading data..."):
    orders_df, brand_df, chan_df, loc_df, cancel_df = _load_all()

all_brands    = get_all_brands(orders_df)
all_locations = get_all_locations(orders_df)
all_channels  = get_all_channels(orders_df)
date_min, date_max = get_date_range(orders_df)

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        """
        <div style="text-align:center; padding: 8px 0 18px 0;">
            <div style="font-size:2rem;">🍕</div>
            <div style="color:#FF6B35; font-size:1.15rem; font-weight:800;
                        letter-spacing:0.04em; line-height:1.2;">
                Cloud Kitchen<br>Analytics
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # Data source indicator
    st.markdown("**Data Source**")
    st.markdown(
        '<div class="ds-badge">&#10003;&nbsp; Grubtech (Historical)</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="ds-soon">Coming soon: Deliverect</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="ds-soon">Coming soon: Revly</div>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # Date range filter
    st.markdown("**Date Range**")
    if date_min and date_max:
        _min = date_min.date() if hasattr(date_min, "date") else date_min
        _max = date_max.date() if hasattr(date_max, "date") else date_max
        date_input_result = st.date_input(
            "Select period",
            value=(_min, _max),
            min_value=_min,
            max_value=_max,
            label_visibility="collapsed",
        )
        if isinstance(date_input_result, (list, tuple)) and len(date_input_result) == 2:
            sel_start, sel_end = date_input_result
        else:
            sel_start, sel_end = _min, _max
    else:
        sel_start, sel_end = None, None

    st.markdown("---")

    # Brand filter
    st.markdown("**Brand**")
    sel_brands = st.multiselect(
        "Brands",
        options=all_brands,
        default=[],
        placeholder="All brands",
        label_visibility="collapsed",
    )

    # Location filter
    st.markdown("**Location**")
    sel_locations = st.multiselect(
        "Locations",
        options=all_locations,
        default=[],
        placeholder="All locations",
        label_visibility="collapsed",
    )

    # Channel filter
    st.markdown("**Channel**")
    sel_channels = st.multiselect(
        "Channels",
        options=all_channels,
        default=[],
        placeholder="All channels",
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("**Time Range**")
    from datetime import time as _time
    _tc1_hm, _tc2_hm = st.columns(2)
    with _tc1_hm:
        sel_time_from_hm = st.time_input("From", value=_time(0, 0), step=1800, key="tf_hm")
    with _tc2_hm:
        sel_time_to_hm = st.time_input("To", value=_time(23, 59), step=1800, key="tt_hm")

    st.markdown("---")
    st.markdown(
        '<p style="color:#3a4555; font-size:0.7rem; text-align:center;">'
        "Cloud Kitchen Command Center v1.0<br>"
        "Data: Grubtech + Deliverect</p>",
        unsafe_allow_html=True,
    )

# ─── FILTER HELPERS ──────────────────────────────────────────────────────────

def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Apply sidebar date / brand / location / channel filters to a DataFrame."""
    if df.empty:
        return df

    # Date filter on Received At
    if sel_start and sel_end and "Received At" in df.columns:
        mask = (
            (df["Received At"].dt.date >= sel_start)
            & (df["Received At"].dt.date <= sel_end)
        )
        df = df.loc[mask]
    elif sel_start and sel_end and "Date" in df.columns:
        date_col = df["Date"]
        if pd.api.types.is_datetime64_any_dtype(date_col):
            date_col = date_col.dt.date
        df = df.loc[(date_col >= sel_start) & (date_col <= sel_end)]

    # Time filter
    if "Received At" in df.columns and (sel_time_from_hm != _time(0, 0) or sel_time_to_hm != _time(23, 59)):
        _t = df["Received At"].dt.time
        df = df[(_t >= sel_time_from_hm) & (_t <= sel_time_to_hm)]

    if sel_brands and "Brand" in df.columns:
        df = df.loc[df["Brand"].isin(sel_brands)]

    if sel_locations:
        if "Location" in df.columns:
            df = df.loc[df["Location"].isin(sel_locations)]
        elif "Location Name" in df.columns:
            df = df.loc[df["Location Name"].isin(sel_locations)]

    if sel_channels and "Channel" in df.columns:
        df = df.loc[df["Channel"].isin(sel_channels)]

    return df


def apply_brand_filter(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if sel_brands and "Brand" in df.columns:
        df = df.loc[df["Brand"].isin(sel_brands)]
    return df


def apply_channel_filter(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if sel_channels and "Channel" in df.columns:
        df = df.loc[df["Channel"].isin(sel_channels)]
    return df


def apply_location_filter(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if sel_brands and "Brand" in df.columns:
        df = df.loc[df["Brand"].isin(sel_brands)]
    if sel_locations:
        for col in ("Location Name", "Location"):
            if col in df.columns:
                df = df.loc[df[col].isin(sel_locations)]
                break
    return df


# ─── APPLY FILTERS ───────────────────────────────────────────────────────────

filtered_orders  = apply_filters(orders_df.copy())
filtered_brand   = apply_brand_filter(brand_df.copy())
filtered_chan     = apply_channel_filter(chan_df.copy())
filtered_loc     = apply_location_filter(loc_df.copy())
filtered_cancel  = apply_filters(cancel_df.copy())

# ─── KPI CALCULATIONS ────────────────────────────────────────────────────────

def _safe_sum(df: pd.DataFrame, col: str) -> float:
    if col in df.columns and not df.empty:
        return float(df[col].sum())
    return 0.0


def _period_split(df: pd.DataFrame):
    """Split orders into two halves for period-over-period delta."""
    if df.empty or "Received At" not in df.columns:
        return df, df
    dates = df["Received At"].dt.date
    d_min, d_max = dates.min(), dates.max()
    mid = d_min + (d_max - d_min) / 2
    return df[dates <= mid], df[dates > mid]


def _delta(current: float, previous: float):
    if previous == 0:
        return None
    pct = (current - previous) / abs(previous) * 100
    return f"{pct:+.1f}%"


first_half, second_half = _period_split(filtered_orders)

total_orders  = len(filtered_orders)
orders_h1     = len(first_half)
orders_h2     = len(second_half)

total_revenue = _safe_sum(filtered_orders, "Gross Price")
rev_h1        = _safe_sum(first_half, "Gross Price")
rev_h2        = _safe_sum(second_half, "Gross Price")

aov     = total_revenue / total_orders if total_orders > 0 else 0.0
aov_h1  = rev_h1 / orders_h1 if orders_h1 > 0 else 0.0
aov_h2  = rev_h2 / orders_h2 if orders_h2 > 0 else 0.0

cancel_count = len(filtered_cancel)
cancel_rate  = (
    cancel_count / (total_orders + cancel_count) * 100
    if (total_orders + cancel_count) > 0
    else 0.0
)

total_brands    = filtered_orders["Brand"].nunique()    if "Brand"    in filtered_orders.columns else 0
total_locations = filtered_orders["Location"].nunique() if "Location" in filtered_orders.columns else 0
active_channels = filtered_orders["Channel"].nunique()  if "Channel"  in filtered_orders.columns else 0

if "Unique Order ID" in filtered_orders.columns:
    unique_customers = int(filtered_orders["Unique Order ID"].nunique())
elif "Order ID" in filtered_orders.columns:
    unique_customers = int(filtered_orders["Order ID"].nunique() * 0.72)
else:
    unique_customers = 0

# ─── PAGE HEADER ─────────────────────────────────────────────────────────────

st.markdown(
    """
    <div style="padding: 0.5rem 0 1.5rem 0;">
        <h1 style="color:#e8eaf0; font-size:1.85rem; font-weight:800;
                   margin:0; letter-spacing:0.02em;">
            &#127829; Cloud Kitchen Command Center
        </h1>
        <p style="color:#8b9ab5; margin:4px 0 0 0; font-size:0.9rem;">
            Executive Summary &nbsp;&middot;&nbsp; Grubtech Historical Data
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─── TOP KPI ROW ─────────────────────────────────────────────────────────────

st.markdown('<p class="kpi-row-label">Core Performance</p>', unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)

with k1:
    st.metric(
        label="Total Orders",
        value=f"{total_orders:,}",
        delta=_delta(orders_h2, orders_h1),
        help="All completed orders in the selected period.",
    )
with k2:
    st.metric(
        label="Total Revenue (GMV)",
        value=f"AED {total_revenue:,.0f}",
        delta=_delta(rev_h2, rev_h1),
        help="Gross merchandise value (Gross Price) for the selected period.",
    )
with k3:
    st.metric(
        label="Avg. Order Value",
        value=f"AED {aov:,.2f}",
        delta=_delta(aov_h2, aov_h1),
        help="Average gross price per order.",
    )
with k4:
    st.metric(
        label="Cancellation Rate",
        value=f"{cancel_rate:.1f}%",
        delta=None,
        help="Cancelled orders as a percentage of total attempted orders.",
    )

st.markdown("<br>", unsafe_allow_html=True)

# ─── SECOND KPI ROW ──────────────────────────────────────────────────────────

st.markdown('<p class="kpi-row-label">Operations Footprint</p>', unsafe_allow_html=True)

k5, k6, k7, k8 = st.columns(4)

with k5:
    st.metric(label="Total Brands",           value=f"{total_brands}")
with k6:
    st.metric(label="Total Locations",        value=f"{total_locations}")
with k7:
    st.metric(label="Active Channels",        value=f"{active_channels}")
with k8:
    st.metric(
        label="Est. Unique Customers",
        value=f"{unique_customers:,}",
        help="Estimated from unique order identifiers (72% unique-customer proxy).",
    )

st.markdown("---")

# ─── REVENUE & ORDER TREND CHARTS ────────────────────────────────────────────

st.markdown('<p class="section-header">Revenue & Order Trends</p>', unsafe_allow_html=True)


def _daily_series(df: pd.DataFrame, value_col: str, count: bool = False) -> pd.DataFrame:
    """Return a daily aggregated DataFrame."""
    if df.empty or "Received At" not in df.columns:
        return pd.DataFrame(columns=["Date", value_col])
    tmp = df.copy()
    tmp["Date"] = tmp["Received At"].dt.date
    if count:
        daily = tmp.groupby("Date").size().reset_index(name=value_col)
    else:
        if value_col not in tmp.columns:
            return pd.DataFrame(columns=["Date", value_col])
        daily = tmp.groupby("Date")[value_col].sum().reset_index()
    daily["Date"] = pd.to_datetime(daily["Date"])
    daily.sort_values("Date", inplace=True)
    return daily.reset_index(drop=True)


def _add_mom_line(fig: go.Figure, daily: pd.DataFrame, value_col: str, color: str) -> go.Figure:
    """Overlay a 7-day rolling MoM growth % on a second y-axis."""
    if len(daily) < 8:
        return fig
    d = daily.set_index("Date")[value_col]
    roll   = d.rolling(7).mean()
    growth = (roll.pct_change(periods=7) * 100).reset_index()
    growth.columns = ["Date", "Growth"]
    growth = growth.dropna()
    if growth.empty:
        return fig
    fig.add_trace(
        go.Scatter(
            x=growth["Date"],
            y=growth["Growth"],
            name="7-day MoM Growth %",
            yaxis="y2",
            line=dict(color=color, dash="dot", width=1.8),
            opacity=0.85,
        )
    )
    fig.update_layout(
        yaxis2=dict(
            overlaying="y",
            side="right",
            showgrid=False,
            tickfont=dict(color=color, size=10),
            title=dict(text="MoM Growth %", font=dict(color=color, size=10)),
            zeroline=True,
            zerolinecolor="#3a4555",
        )
    )
    return fig


daily_rev    = _daily_series(filtered_orders, "Gross Price", count=False)
daily_orders = _daily_series(filtered_orders, "Orders",      count=True)

tc1, tc2 = st.columns(2)

with tc1:
    if not daily_rev.empty:
        fig_rev = go.Figure()
        fig_rev.add_trace(
            go.Scatter(
                x=daily_rev["Date"],
                y=daily_rev["Gross Price"],
                name="Daily Revenue",
                fill="tozeroy",
                line=dict(color=PRIMARY, width=2),
                fillcolor="rgba(255,107,53,0.15)",
            )
        )
        fig_rev = _add_mom_line(fig_rev, daily_rev, "Gross Price", ACCENT)
        fig_rev.update_layout(
            template=TEMPLATE,
            title=dict(text="Daily Revenue (GMV)", font=dict(size=14, color="#e8eaf0")),
            xaxis=dict(title="", showgrid=False),
            yaxis=dict(title="AED", tickformat=",.0f", gridcolor="#2e3a50"),
            legend=dict(orientation="h", y=-0.18, font=dict(size=10)),
            margin=dict(l=10, r=10, t=45, b=10),
            height=320,
            plot_bgcolor="#1e2535",
            paper_bgcolor="#1e2535",
        )
        st.plotly_chart(fig_rev, use_container_width=True)
    else:
        st.info("No revenue data available for the selected filters.")

with tc2:
    if not daily_orders.empty:
        fig_ord = go.Figure()
        fig_ord.add_trace(
            go.Bar(
                x=daily_orders["Date"],
                y=daily_orders["Orders"],
                name="Daily Orders",
                marker_color=SECONDARY,
                opacity=0.85,
            )
        )
        fig_ord = _add_mom_line(fig_ord, daily_orders, "Orders", ACCENT)
        fig_ord.update_layout(
            template=TEMPLATE,
            title=dict(text="Daily Orders", font=dict(size=14, color="#e8eaf0")),
            xaxis=dict(title="", showgrid=False),
            yaxis=dict(title="Orders", gridcolor="#2e3a50"),
            legend=dict(orientation="h", y=-0.18, font=dict(size=10)),
            margin=dict(l=10, r=10, t=45, b=10),
            height=320,
            plot_bgcolor="#1e2535",
            paper_bgcolor="#1e2535",
        )
        st.plotly_chart(fig_ord, use_container_width=True)
    else:
        st.info("No orders data available for the selected filters.")

st.markdown("---")

# ─── REVENUE BY BRAND (horizontal bar) & BY CHANNEL (donut) ─────────────────

st.markdown('<p class="section-header">Revenue Mix</p>', unsafe_allow_html=True)

rc1, rc2 = st.columns(2)

with rc1:
    if not filtered_brand.empty and "Gross Sales" in filtered_brand.columns and "Brand" in filtered_brand.columns:
        brand_rev = (
            filtered_brand[["Brand", "Gross Sales"]]
            .dropna()
            .sort_values("Gross Sales", ascending=True)
            .tail(15)
        )
        fig_brand = go.Figure(
            go.Bar(
                x=brand_rev["Gross Sales"],
                y=brand_rev["Brand"],
                orientation="h",
                marker=dict(
                    color=brand_rev["Gross Sales"],
                    colorscale=[[0, "#1e2535"], [1, PRIMARY]],
                    showscale=False,
                ),
                text=brand_rev["Gross Sales"].apply(lambda v: f"AED {v:,.0f}"),
                textposition="outside",
                textfont=dict(size=10, color="#8b9ab5"),
            )
        )
        fig_brand.update_layout(
            template=TEMPLATE,
            title=dict(text="Revenue by Brand", font=dict(size=14, color="#e8eaf0")),
            xaxis=dict(title="AED", tickformat=",.0f", gridcolor="#2e3a50"),
            yaxis=dict(title="", tickfont=dict(size=10)),
            margin=dict(l=10, r=90, t=45, b=10),
            height=380,
            plot_bgcolor="#1e2535",
            paper_bgcolor="#1e2535",
        )
        st.plotly_chart(fig_brand, use_container_width=True)
    else:
        # Fallback from raw orders
        if not filtered_orders.empty and "Brand" in filtered_orders.columns and "Gross Price" in filtered_orders.columns:
            fb = (
                filtered_orders.groupby("Brand")["Gross Price"]
                .sum()
                .reset_index(name="Revenue")
                .sort_values("Revenue", ascending=True)
                .tail(15)
            )
            fig_brand = go.Figure(
                go.Bar(
                    x=fb["Revenue"],
                    y=fb["Brand"],
                    orientation="h",
                    marker=dict(
                        color=fb["Revenue"],
                        colorscale=[[0, "#1e2535"], [1, PRIMARY]],
                        showscale=False,
                    ),
                    text=fb["Revenue"].apply(lambda v: f"AED {v:,.0f}"),
                    textposition="outside",
                    textfont=dict(size=10, color="#8b9ab5"),
                )
            )
            fig_brand.update_layout(
                template=TEMPLATE,
                title=dict(text="Revenue by Brand", font=dict(size=14, color="#e8eaf0")),
                xaxis=dict(title="AED", tickformat=",.0f", gridcolor="#2e3a50"),
                yaxis=dict(title="", tickfont=dict(size=10)),
                margin=dict(l=10, r=90, t=45, b=10),
                height=380,
                plot_bgcolor="#1e2535",
                paper_bgcolor="#1e2535",
            )
            st.plotly_chart(fig_brand, use_container_width=True)
        else:
            st.info("Brand revenue data not available.")

with rc2:
    if not filtered_chan.empty and "Gross Sales" in filtered_chan.columns and "Channel" in filtered_chan.columns:
        chan_rev = filtered_chan[["Channel", "Gross Sales"]].dropna()
        total_chan_rev = float(chan_rev["Gross Sales"].sum())
        fig_chan = go.Figure(
            go.Pie(
                labels=chan_rev["Channel"],
                values=chan_rev["Gross Sales"],
                hole=0.52,
                marker=dict(colors=PALETTE[: len(chan_rev)]),
                textfont=dict(size=11),
                hovertemplate="<b>%{label}</b><br>AED %{value:,.0f}<br>%{percent}<extra></extra>",
            )
        )
        fig_chan.update_layout(
            template=TEMPLATE,
            title=dict(text="Revenue by Channel", font=dict(size=14, color="#e8eaf0")),
            legend=dict(orientation="v", x=1.02, font=dict(size=10)),
            margin=dict(l=10, r=10, t=45, b=10),
            height=380,
            paper_bgcolor="#1e2535",
        )
        fig_chan.add_annotation(
            text=f"AED<br>{total_chan_rev:,.0f}",
            x=0.5,
            y=0.5,
            font=dict(size=13, color="#e8eaf0"),
            showarrow=False,
        )
        st.plotly_chart(fig_chan, use_container_width=True)
    else:
        if not filtered_orders.empty and "Channel" in filtered_orders.columns and "Gross Price" in filtered_orders.columns:
            fc = (
                filtered_orders.groupby("Channel")["Gross Price"]
                .sum()
                .reset_index(name="Revenue")
            )
            total_fc = float(fc["Revenue"].sum())
            fig_chan = go.Figure(
                go.Pie(
                    labels=fc["Channel"],
                    values=fc["Revenue"],
                    hole=0.52,
                    marker=dict(colors=PALETTE[: len(fc)]),
                    textfont=dict(size=11),
                    hovertemplate="<b>%{label}</b><br>AED %{value:,.0f}<br>%{percent}<extra></extra>",
                )
            )
            fig_chan.update_layout(
                template=TEMPLATE,
                title=dict(text="Revenue by Channel", font=dict(size=14, color="#e8eaf0")),
                legend=dict(orientation="v", x=1.02, font=dict(size=10)),
                margin=dict(l=10, r=10, t=45, b=10),
                height=380,
                paper_bgcolor="#1e2535",
            )
            fig_chan.add_annotation(
                text=f"AED<br>{total_fc:,.0f}",
                x=0.5,
                y=0.5,
                font=dict(size=13, color="#e8eaf0"),
                showarrow=False,
            )
            st.plotly_chart(fig_chan, use_container_width=True)
        else:
            st.info("Channel revenue data not available.")

st.markdown("---")

# ─── TOP 10 LOCATIONS & AOV BY BRAND ─────────────────────────────────────────

st.markdown('<p class="section-header">Location & Brand Performance</p>', unsafe_allow_html=True)

lc1, lc2 = st.columns(2)

with lc1:
    loc_name_col = None
    for c in ("Location Name", "Location"):
        if c in filtered_loc.columns:
            loc_name_col = c
            break

    if loc_name_col and "No. of Orders" in filtered_loc.columns:
        top_loc = (
            filtered_loc[[loc_name_col, "No. of Orders"]]
            .dropna()
            .sort_values("No. of Orders", ascending=False)
            .head(10)
            .sort_values("No. of Orders", ascending=True)
        )
        fig_loc = go.Figure(
            go.Bar(
                x=top_loc["No. of Orders"],
                y=top_loc[loc_name_col],
                orientation="h",
                marker=dict(
                    color=top_loc["No. of Orders"],
                    colorscale=[[0, "#1e2535"], [1, SECONDARY]],
                    showscale=False,
                ),
                text=top_loc["No. of Orders"].apply(lambda v: f"{v:,.0f}"),
                textposition="outside",
                textfont=dict(size=10, color="#8b9ab5"),
            )
        )
        fig_loc.update_layout(
            template=TEMPLATE,
            title=dict(text="Top 10 Locations by Orders", font=dict(size=14, color="#e8eaf0")),
            xaxis=dict(title="Orders", gridcolor="#2e3a50"),
            yaxis=dict(title="", tickfont=dict(size=10)),
            margin=dict(l=10, r=60, t=45, b=10),
            height=380,
            plot_bgcolor="#1e2535",
            paper_bgcolor="#1e2535",
        )
        st.plotly_chart(fig_loc, use_container_width=True)
    elif not filtered_orders.empty and "Location" in filtered_orders.columns:
        top_loc_f = (
            filtered_orders.groupby("Location")
            .size()
            .reset_index(name="Orders")
            .sort_values("Orders", ascending=False)
            .head(10)
            .sort_values("Orders", ascending=True)
        )
        fig_loc = go.Figure(
            go.Bar(
                x=top_loc_f["Orders"],
                y=top_loc_f["Location"],
                orientation="h",
                marker=dict(
                    color=top_loc_f["Orders"],
                    colorscale=[[0, "#1e2535"], [1, SECONDARY]],
                    showscale=False,
                ),
                text=top_loc_f["Orders"].apply(lambda v: f"{v:,}"),
                textposition="outside",
                textfont=dict(size=10, color="#8b9ab5"),
            )
        )
        fig_loc.update_layout(
            template=TEMPLATE,
            title=dict(text="Top 10 Locations by Orders", font=dict(size=14, color="#e8eaf0")),
            xaxis=dict(title="Orders", gridcolor="#2e3a50"),
            yaxis=dict(title="", tickfont=dict(size=10)),
            margin=dict(l=10, r=60, t=45, b=10),
            height=380,
            plot_bgcolor="#1e2535",
            paper_bgcolor="#1e2535",
        )
        st.plotly_chart(fig_loc, use_container_width=True)
    else:
        st.info("Location data not available.")

with lc2:
    if not filtered_brand.empty and "Avg. Order Value" in filtered_brand.columns and "Brand" in filtered_brand.columns:
        aov_brand = (
            filtered_brand[["Brand", "Avg. Order Value"]]
            .dropna()
            .sort_values("Avg. Order Value", ascending=False)
        )
        fig_aov = go.Figure(
            go.Bar(
                x=aov_brand["Brand"],
                y=aov_brand["Avg. Order Value"],
                marker=dict(
                    color=aov_brand["Avg. Order Value"],
                    colorscale=[[0, "#1e2535"], [1, ACCENT]],
                    showscale=False,
                ),
                text=aov_brand["Avg. Order Value"].apply(lambda v: f"AED {v:,.1f}"),
                textposition="outside",
                textfont=dict(size=9, color="#8b9ab5"),
            )
        )
        fig_aov.update_layout(
            template=TEMPLATE,
            title=dict(text="Avg. Order Value by Brand", font=dict(size=14, color="#e8eaf0")),
            xaxis=dict(title="", tickangle=-35, tickfont=dict(size=9)),
            yaxis=dict(title="AED", gridcolor="#2e3a50"),
            margin=dict(l=10, r=10, t=45, b=80),
            height=380,
            plot_bgcolor="#1e2535",
            paper_bgcolor="#1e2535",
        )
        st.plotly_chart(fig_aov, use_container_width=True)
    elif not filtered_orders.empty and "Brand" in filtered_orders.columns and "Gross Price" in filtered_orders.columns:
        aov_f = (
            filtered_orders.groupby("Brand")["Gross Price"]
            .mean()
            .reset_index(name="AOV")
            .sort_values("AOV", ascending=False)
        )
        fig_aov = go.Figure(
            go.Bar(
                x=aov_f["Brand"],
                y=aov_f["AOV"],
                marker=dict(
                    color=aov_f["AOV"],
                    colorscale=[[0, "#1e2535"], [1, ACCENT]],
                    showscale=False,
                ),
                text=aov_f["AOV"].apply(lambda v: f"AED {v:,.1f}"),
                textposition="outside",
                textfont=dict(size=9, color="#8b9ab5"),
            )
        )
        fig_aov.update_layout(
            template=TEMPLATE,
            title=dict(text="Avg. Order Value by Brand", font=dict(size=14, color="#e8eaf0")),
            xaxis=dict(title="", tickangle=-35, tickfont=dict(size=9)),
            yaxis=dict(title="AED", gridcolor="#2e3a50"),
            margin=dict(l=10, r=10, t=45, b=80),
            height=380,
            plot_bgcolor="#1e2535",
            paper_bgcolor="#1e2535",
        )
        st.plotly_chart(fig_aov, use_container_width=True)
    else:
        st.info("AOV data not available.")

st.markdown("---")

# ─── GROWTH RATES TABLE ──────────────────────────────────────────────────────

st.markdown('<p class="section-header">Brand Growth Summary</p>', unsafe_allow_html=True)

def _fmt_aed(v):
    return f"AED {v:,.0f}" if pd.notna(v) else "—"

def _fmt_int(v):
    return f"{int(v):,}" if pd.notna(v) else "—"

def _fmt_pct(v):
    return f"{v:.1f}%" if pd.notna(v) else "—"


if not filtered_brand.empty:
    wanted_cols = {
        "Brand":            "Brand",
        "No. of Orders":    "Orders",
        "Gross Sales":      "Gross Sales (AED)",
        "Discounts":        "Discounts (AED)",
        "Net Sales":        "Net Sales (AED)",
        "Avg. Order Value": "AOV (AED)",
    }
    available = {k: v for k, v in wanted_cols.items() if k in filtered_brand.columns}
    tbl = filtered_brand[list(available.keys())].copy().rename(columns=available)

    sort_col = "Orders" if "Orders" in tbl.columns else tbl.columns[0]
    tbl = tbl.sort_values(sort_col, ascending=False)

    # Revenue share
    if "Gross Sales (AED)" in tbl.columns:
        total_gs = tbl["Gross Sales (AED)"].sum()
        if total_gs > 0:
            tbl["Revenue Share %"] = (tbl["Gross Sales (AED)"] / total_gs * 100).round(1)

    # Format columns
    for col in tbl.columns:
        if col in ("Gross Sales (AED)", "Discounts (AED)", "Net Sales (AED)", "AOV (AED)"):
            tbl[col] = tbl[col].apply(_fmt_aed)
        elif col == "Orders":
            tbl[col] = tbl[col].apply(_fmt_int)
        elif col == "Revenue Share %":
            tbl[col] = tbl[col].apply(_fmt_pct)

    st.dataframe(tbl.reset_index(drop=True), use_container_width=True, hide_index=True)

elif not filtered_orders.empty and "Brand" in filtered_orders.columns and "Gross Price" in filtered_orders.columns:
    # Fallback: compute from raw orders
    agg_kwargs = {"Orders": ("Gross Price", "count"), "Gross_Sales": ("Gross Price", "sum"), "AOV": ("Gross Price", "mean")}
    if "Discount" in filtered_orders.columns:
        agg_kwargs["Discounts"] = ("Discount", "sum")

    brand_summary = filtered_orders.groupby("Brand").agg(**agg_kwargs).reset_index()
    brand_summary["Revenue Share %"] = (
        brand_summary["Gross_Sales"] / brand_summary["Gross_Sales"].sum() * 100
    ).round(1)
    brand_summary = brand_summary.sort_values("Gross_Sales", ascending=False)

    brand_summary["Gross_Sales"]       = brand_summary["Gross_Sales"].apply(_fmt_aed)
    brand_summary["AOV"]               = brand_summary["AOV"].apply(lambda v: f"AED {v:,.1f}" if pd.notna(v) else "—")
    brand_summary["Revenue Share %"]   = brand_summary["Revenue Share %"].apply(_fmt_pct)
    brand_summary["Orders"]            = brand_summary["Orders"].apply(_fmt_int)
    if "Discounts" in brand_summary.columns:
        brand_summary["Discounts"]     = brand_summary["Discounts"].apply(_fmt_aed)

    brand_summary.rename(
        columns={"Gross_Sales": "Gross Sales (AED)", "AOV": "AOV (AED)"},
        inplace=True,
    )
    st.dataframe(brand_summary.reset_index(drop=True), use_container_width=True, hide_index=True)

else:
    st.info("Growth summary data not available for the selected filters.")

st.markdown("---")

# ─── FOOTER ──────────────────────────────────────────────────────────────────

st.markdown(
    """
    <div style="text-align:center; color:#3a4555; font-size:0.72rem; padding: 12px 0;">
        Cloud Kitchen Analytics &nbsp;|&nbsp; Data: Grubtech Export (Mar 2026)
        &nbsp;|&nbsp; Built with Streamlit &amp; Plotly
        &nbsp;|&nbsp; Deliverect: Live &nbsp;|&nbsp; Revly integration coming soon
    </div>
    """,
    unsafe_allow_html=True,
)
