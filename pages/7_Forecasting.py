"""
Forecasting Analytics Page
Cloud Kitchen Analytics Dashboard
Powered by Facebook Prophet for 30/60/90-day projections.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.data_loader import load_sales_orders, get_all_brands, get_all_locations, get_all_channels
from utils.forecasting import (
    prepare_prophet_df,
    run_prophet_forecast,
    create_forecast_chart,
    calculate_growth_rates,
)

# ─── CONSTANTS ────────────────────────────────────────────────────────────────
COLOR_ACTUAL     = "#FF6B35"
COLOR_FORECAST   = "#4ECDC4"
COLOR_CONFIDENCE = "#FFE66D"
COLOR_POS        = "#00C851"
COLOR_NEG        = "#FF4444"
TEMPLATE         = "plotly_white"
BG               = "rgba(255,255,255,0)"

# ─── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Forecasting", page_icon="🔮", layout="wide")

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def fmt_currency(val: float, decimals: int = 0) -> str:
    if pd.isna(val):
        return "N/A"
    if abs(val) >= 1_000_000:
        return f"AED {val/1_000_000:.2f}M"
    if abs(val) >= 1_000:
        return f"AED {val/1_000:.1f}K"
    return f"AED {val:,.{decimals}f}"


def fmt_pct(val: float) -> str:
    if pd.isna(val):
        return "N/A"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.1f}%"


def color_pct(val: float) -> str:
    if pd.isna(val):
        return ""
    return COLOR_POS if val >= 0 else COLOR_NEG


def apply_filters(df: pd.DataFrame, brands, locations, channels=None, cuisines=None) -> pd.DataFrame:
    if brands:
        df = df[df["Brand"].isin(brands)]
    if locations and "Location" in df.columns:
        df = df[df["Location"].isin(locations)]
    if channels and "Channel" in df.columns:
        df = df[df["Channel"].isin(channels)]
    if cuisines and "Cuisine" in df.columns:
        df = df[df["Cuisine"].isin(cuisines)]
    return df


def safe_pct_change(new_val: float, old_val: float) -> float:
    if old_val and old_val != 0:
        return (new_val - old_val) / abs(old_val) * 100
    return float("nan")


def forecast_summary_metric(df_hist: pd.DataFrame, forecast_df: pd.DataFrame,
                             periods: int, label: str, fmt_fn=None) -> dict:
    """Compute current-period vs forecast-period totals and % change."""
    if df_hist.empty or forecast_df.empty:
        return {}
    last_date = df_hist["ds"].max()
    recent = df_hist[df_hist["ds"] >= last_date - pd.Timedelta(days=periods)]
    current_total = recent["y"].sum() if not recent.empty else 0.0

    future_fc = forecast_df[forecast_df["ds"] > last_date].head(periods)
    forecast_total = future_fc["yhat"].clip(lower=0).sum() if not future_fc.empty else 0.0

    pct = safe_pct_change(forecast_total, current_total)
    return {
        "label": label,
        "current": current_total,
        "forecast": forecast_total,
        "pct_change": pct,
        "fmt_fn": fmt_fn or (lambda x: f"{x:,.1f}"),
    }


def growth_table_html(df: pd.DataFrame, value_col: str, growth_col: str,
                      date_col: str, date_fmt: str = "%Y-%m-%d") -> str:
    """Render a styled HTML table for growth rates."""
    if df.empty:
        return "<p>No data available.</p>"
    rows = ""
    for _, row in df.tail(12).iterrows():
        val = row[value_col]
        gr = row[growth_col]
        date_str = pd.Timestamp(row[date_col]).strftime(date_fmt)
        gr_str = fmt_pct(gr) if not pd.isna(gr) else "—"
        gr_color = COLOR_POS if (not pd.isna(gr) and gr >= 0) else COLOR_NEG
        rows += (
            f"<tr>"
            f"<td style='padding:6px 12px;color:#333;'>{date_str}</td>"
            f"<td style='padding:6px 12px;text-align:right;'>{val:,.0f}</td>"
            f"<td style='padding:6px 12px;text-align:right;color:{gr_color};font-weight:600;'>{gr_str}</td>"
            f"</tr>"
        )
    return (
        "<table style='width:100%;border-collapse:collapse;background:#F8F9FA;border-radius:8px;overflow:hidden;'>"
        "<thead><tr style='background:#F8F9FA;'>"
        "<th style='padding:8px 12px;text-align:left;color:#555;font-weight:600;'>Period</th>"
        "<th style='padding:8px 12px;text-align:right;color:#555;font-weight:600;'>Value</th>"
        "<th style='padding:8px 12px;text-align:right;color:#555;font-weight:600;'>Growth %</th>"
        "</tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def weekly_seasonality_chart(model) -> go.Figure:
    """Extract and visualise Prophet's weekly seasonality component."""
    try:
        future = model.make_future_dataframe(periods=0)
        forecast = model.predict(future)
        if "weekly" not in forecast.columns:
            return None

        df_comp = pd.DataFrame({
            "day": pd.to_datetime(forecast["ds"]).dt.day_name(),
            "weekly": forecast["weekly"],
        })
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        avg_by_day = df_comp.groupby("day")["weekly"].mean().reindex(day_order).reset_index()
        avg_by_day.columns = ["Day", "Effect"]

        colors = [COLOR_POS if v >= 0 else COLOR_NEG for v in avg_by_day["Effect"]]
        fig = go.Figure(go.Bar(
            x=avg_by_day["Day"],
            y=avg_by_day["Effect"],
            marker_color=colors,
            text=[f"{v:+.1f}" for v in avg_by_day["Effect"]],
            textposition="outside",
        ))
        fig.update_layout(
            title="Weekly Seasonality Effect",
            xaxis_title="Day of Week",
            yaxis_title="Additive Effect on Revenue",
            template=TEMPLATE,
            paper_bgcolor=BG,
            plot_bgcolor=BG,
            margin=dict(l=40, r=20, t=60, b=40),
        )
        return fig
    except Exception:
        return None


def trend_component_chart(model, forecast_df: pd.DataFrame, title: str = "Trend Component") -> go.Figure:
    """Show the trend component from Prophet."""
    if forecast_df.empty or "trend" not in forecast_df.columns:
        return None
    fig = go.Figure(go.Scatter(
        x=forecast_df["ds"],
        y=forecast_df["trend"],
        mode="lines",
        line=dict(color=COLOR_FORECAST, width=2),
        name="Trend",
    ))
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Trend Value",
        template=TEMPLATE,
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        margin=dict(l=40, r=20, t=60, b=40),
    )
    return fig


# ─── CHECK PROPHET AVAILABILITY ───────────────────────────────────────────────
prophet_available = False
try:
    from prophet import Prophet  # noqa: F401
    prophet_available = True
except ImportError:
    pass

# ─── PAGE HEADER ──────────────────────────────────────────────────────────────
st.markdown(
    "<h1 style='margin-bottom:4px;'>🔮 Forecasting Analytics</h1>"
    "<p style='color:#666;margin-top:0;'>Prophet-powered 30 / 60 / 90-day revenue, order and AOV projections</p>",
    unsafe_allow_html=True,
)
st.divider()

if not prophet_available:
    st.error(
        "**Prophet is not installed.** "
        "Install it with:\n\n"
        "```bash\npip install prophet\n```\n\n"
        "Then restart the Streamlit app."
    )
    st.stop()

# ─── LOAD DATA ────────────────────────────────────────────────────────────────
with st.spinner("Loading sales data…"):
    df_raw = load_sales_orders()

if df_raw.empty:
    st.warning("No sales data available. Please check the data source.")
    st.stop()

df_raw["Received At"] = pd.to_datetime(df_raw["Received At"], errors="coerce")
df_raw["Total(Receipt Total)"] = pd.to_numeric(df_raw["Total(Receipt Total)"], errors="coerce").fillna(0)
df_raw["Net Sales"] = pd.to_numeric(df_raw.get("Net Sales", 0), errors="coerce").fillna(0)

all_brands    = sorted(get_all_brands())
all_locations = sorted(get_all_locations())

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔮 Forecast Controls")

    forecast_horizon = st.select_slider(
        "Forecast Horizon (days)",
        options=[30, 60, 90],
        value=30,
        help="Number of days to forecast into the future",
    )

    st.markdown("---")
    st.subheader("Filters")

    sel_brands = st.multiselect(
        "Brand (optional)",
        options=all_brands,
        default=[],
        help="Leave blank to forecast across all brands",
    )

    sel_locations = st.multiselect(
        "Location (optional)",
        options=all_locations,
        default=[],
        help="Leave blank to include all locations",
    )

    all_channels_fc = sorted(df_raw["Channel"].dropna().unique().tolist()) if "Channel" in df_raw.columns else []
    sel_channels_fc = st.multiselect("Channel (optional)", options=all_channels_fc, default=[], help="Leave blank to include all channels")

    all_cuisines_fc = sorted(df_raw["Cuisine"].dropna().unique().tolist()) if "Cuisine" in df_raw.columns else []
    sel_cuisines_fc = st.multiselect("Cuisine (optional)", options=all_cuisines_fc, default=[], help="Leave blank to include all cuisines")

    st.markdown("---")
    confidence_pct = st.selectbox(
        "Confidence Interval",
        options=["80%", "90%", "95%"],
        index=0,
        help="Width of the forecast confidence band",
    )
    confidence_map = {"80%": 0.80, "90%": 0.90, "95%": 0.95}
    interval_width = confidence_map[confidence_pct]

    st.markdown("---")
    st.markdown("**Date Range**")
    _dates_fc = df_raw["Received At"].dropna() if "Received At" in df_raw.columns else pd.Series(dtype="datetime64[ns]")
    _min_fc = _dates_fc.min().date() if not _dates_fc.empty else None
    _max_fc = _dates_fc.max().date() if not _dates_fc.empty else None
    sel_start_fc = sel_end_fc = None
    if _min_fc and _max_fc:
        _dr_fc = st.date_input("Period", value=(_min_fc, _max_fc), min_value=_min_fc, max_value=_max_fc, label_visibility="collapsed")
        sel_start_fc, sel_end_fc = (_dr_fc[0], _dr_fc[1]) if isinstance(_dr_fc, (list, tuple)) and len(_dr_fc) == 2 else (_min_fc, _max_fc)
    st.markdown("**Time Range**")
    from datetime import time as _time
    _tc1_fc, _tc2_fc = st.columns(2)
    with _tc1_fc:
        sel_time_from_fc = st.time_input("From", value=_time(0, 0), step=1800, key="tf_fc")
    with _tc2_fc:
        sel_time_to_fc = st.time_input("To", value=_time(23, 59), step=1800, key="tt_fc")
    st.markdown("---")
    st.caption(f"Dataset: {len(df_raw):,} orders loaded")

# ─── APPLY FILTERS ────────────────────────────────────────────────────────────
df = apply_filters(df_raw.copy(), sel_brands, sel_locations, sel_channels_fc, sel_cuisines_fc)
if sel_start_fc and sel_end_fc:
    from datetime import datetime as _dt
    _s = pd.Timestamp(_dt.combine(sel_start_fc, sel_time_from_fc))
    _e = pd.Timestamp(_dt.combine(sel_end_fc, sel_time_to_fc))
    if "Received At" in df.columns:
        df = df[(df["Received At"] >= _s) & (df["Received At"] <= _e)]
    elif "Date" in df.columns:
        df["_date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
        df = df[(df["_date"] >= sel_start_fc) & (df["_date"] <= sel_end_fc)]
        df = df.drop(columns=["_date"])

if df.empty:
    st.warning("No data matches the selected filters. Please adjust the sidebar controls.")
    st.stop()

filter_label = ""
if sel_brands:
    filter_label += f" | Brands: {', '.join(sel_brands)}"
if sel_locations:
    filter_label += f" | Locations: {', '.join(sel_locations)}"
if filter_label:
    st.info(f"Active filters{filter_label}")

# ─── RUN CORE FORECASTS ───────────────────────────────────────────────────────
with st.spinner("Running Prophet forecasts… this may take a moment."):
    # --- Revenue ---
    rev_prophet_df = prepare_prophet_df(df, "Received At", "Total(Receipt Total)", "sum")
    rev_forecast_df, rev_model = run_prophet_forecast(
        rev_prophet_df, periods=forecast_horizon,
        yearly_seasonality=False, weekly_seasonality=True, daily_seasonality=False,
    )

    # --- Orders ---
    order_prophet_df = prepare_prophet_df(df, "Received At", "Total(Receipt Total)", "count")
    ord_forecast_df, ord_model = run_prophet_forecast(
        order_prophet_df, periods=forecast_horizon,
        yearly_seasonality=False, weekly_seasonality=True, daily_seasonality=False,
    )

    # --- AOV (daily revenue / daily orders) ---
    if not rev_prophet_df.empty and not order_prophet_df.empty:
        aov_df = rev_prophet_df.copy()
        ord_for_aov = order_prophet_df.set_index("ds")["y"].rename("orders")
        aov_df = aov_df.join(ord_for_aov, on="ds")
        aov_df["y"] = np.where(
            aov_df["orders"] > 0,
            aov_df["y"] / aov_df["orders"],
            np.nan,
        )
        aov_df = aov_df[["ds", "y"]].dropna()
        aov_forecast_df, aov_model = run_prophet_forecast(
            aov_df, periods=forecast_horizon,
            yearly_seasonality=False, weekly_seasonality=True, daily_seasonality=False,
        )
    else:
        aov_df = pd.DataFrame()
        aov_forecast_df = pd.DataFrame()
        aov_model = None

# ─── 1. REVENUE FORECAST ──────────────────────────────────────────────────────
st.markdown("## 📈 Revenue Forecast")

if not rev_prophet_df.empty and not rev_forecast_df.empty:
    last_date = rev_prophet_df["ds"].max()
    future_rev = rev_forecast_df[rev_forecast_df["ds"] > last_date].head(forecast_horizon)
    total_forecast_rev = future_rev["yhat"].clip(lower=0).sum()
    daily_avg_rev = total_forecast_rev / forecast_horizon if forecast_horizon > 0 else 0

    recent_rev_df = rev_prophet_df[
        rev_prophet_df["ds"] >= last_date - pd.Timedelta(days=forecast_horizon)
    ]
    current_rev = recent_rev_df["y"].sum()
    rev_growth = safe_pct_change(total_forecast_rev, current_rev)

    last_30_df_m = rev_prophet_df.copy()
    last_30_df_m["ds"] = pd.to_datetime(last_30_df_m["ds"])
    monthly_rev = last_30_df_m.set_index("ds").resample("ME")["y"].sum()
    if len(monthly_rev) >= 2:
        mom_growth = safe_pct_change(monthly_rev.iloc[-1], monthly_rev.iloc[-2])
    else:
        mom_growth = float("nan")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            f"Forecast Revenue (next {forecast_horizon}d)",
            fmt_currency(total_forecast_rev),
            delta=fmt_pct(rev_growth) if not pd.isna(rev_growth) else None,
        )
    with col2:
        st.metric("Daily Avg Revenue (Forecast)", fmt_currency(daily_avg_rev))
    with col3:
        st.metric(
            f"Current Period ({forecast_horizon}d)",
            fmt_currency(current_rev),
        )
    with col4:
        st.metric(
            "Projected MoM Growth",
            fmt_pct(mom_growth) if not pd.isna(mom_growth) else "N/A",
        )

    rev_fig = create_forecast_chart(
        rev_prophet_df, rev_forecast_df,
        title=f"Revenue Forecast — Next {forecast_horizon} Days",
        y_label="Daily Revenue (AED)",
        color_actual=COLOR_ACTUAL,
        color_forecast=COLOR_FORECAST,
    )
    rev_fig.update_layout(paper_bgcolor=BG, plot_bgcolor=BG)
    st.plotly_chart(rev_fig, use_container_width=True)
else:
    st.warning("Insufficient data to generate a revenue forecast.")

st.divider()

# ─── 2. ORDER VOLUME FORECAST ─────────────────────────────────────────────────
st.markdown("## 📦 Order Volume Forecast")

if not order_prophet_df.empty and not ord_forecast_df.empty:
    last_date_o = order_prophet_df["ds"].max()
    future_ord = ord_forecast_df[ord_forecast_df["ds"] > last_date_o].head(forecast_horizon)
    total_forecast_ord = future_ord["yhat"].clip(lower=0).sum()
    daily_avg_ord = total_forecast_ord / forecast_horizon if forecast_horizon > 0 else 0

    recent_ord_df = order_prophet_df[
        order_prophet_df["ds"] >= last_date_o - pd.Timedelta(days=forecast_horizon)
    ]
    current_ord = recent_ord_df["y"].sum()
    ord_growth = safe_pct_change(total_forecast_ord, current_ord)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            f"Forecast Orders (next {forecast_horizon}d)",
            f"{total_forecast_ord:,.0f}",
            delta=fmt_pct(ord_growth) if not pd.isna(ord_growth) else None,
        )
    with col2:
        st.metric("Projected Daily Avg Orders", f"{daily_avg_ord:,.1f}")
    with col3:
        st.metric(f"Current Period ({forecast_horizon}d)", f"{current_ord:,.0f}")

    ord_fig = create_forecast_chart(
        order_prophet_df, ord_forecast_df,
        title=f"Order Volume Forecast — Next {forecast_horizon} Days",
        y_label="Daily Order Count",
        color_actual=COLOR_ACTUAL,
        color_forecast=COLOR_FORECAST,
    )
    ord_fig.update_layout(paper_bgcolor=BG, plot_bgcolor=BG)
    st.plotly_chart(ord_fig, use_container_width=True)
else:
    st.warning("Insufficient data to generate an order volume forecast.")

st.divider()

# ─── 3. AOV FORECAST ──────────────────────────────────────────────────────────
st.markdown("## 💳 Average Order Value (AOV) Forecast")

if not aov_df.empty and not aov_forecast_df.empty:
    last_date_a = aov_df["ds"].max()
    future_aov = aov_forecast_df[aov_forecast_df["ds"] > last_date_a].head(forecast_horizon)
    avg_forecast_aov = future_aov["yhat"].clip(lower=0).mean()

    recent_aov_df = aov_df[aov_df["ds"] >= last_date_a - pd.Timedelta(days=forecast_horizon)]
    current_aov = recent_aov_df["y"].mean()
    aov_growth = safe_pct_change(avg_forecast_aov, current_aov)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "Projected Avg AOV (Forecast)",
            fmt_currency(avg_forecast_aov, decimals=2),
            delta=fmt_pct(aov_growth) if not pd.isna(aov_growth) else None,
        )
    with col2:
        st.metric("Current AOV (last period)", fmt_currency(current_aov, decimals=2))
    with col3:
        aov_min = future_aov["yhat_lower"].clip(lower=0).mean() if "yhat_lower" in future_aov else float("nan")
        aov_max = future_aov["yhat_upper"].clip(lower=0).mean() if "yhat_upper" in future_aov else float("nan")
        st.metric(
            f"{confidence_pct} Range",
            f"{fmt_currency(aov_min, 2)} – {fmt_currency(aov_max, 2)}"
            if not pd.isna(aov_min) else "N/A",
        )

    aov_fig = create_forecast_chart(
        aov_df, aov_forecast_df,
        title=f"AOV Forecast — Next {forecast_horizon} Days",
        y_label="Average Order Value (AED)",
        color_actual=COLOR_ACTUAL,
        color_forecast=COLOR_FORECAST,
    )
    aov_fig.update_layout(paper_bgcolor=BG, plot_bgcolor=BG)
    st.plotly_chart(aov_fig, use_container_width=True)
else:
    st.warning("Insufficient data to generate an AOV forecast.")

st.divider()

# ─── 4. GROWTH RATE DASHBOARD ─────────────────────────────────────────────────
st.markdown("## 📊 Growth Rate Dashboard")

gr_col1, gr_col2 = st.columns(2)

def render_growth_section(prophet_df, label, value_suffix="", is_currency=False):
    if prophet_df.empty or len(prophet_df) < 7:
        st.warning(f"Not enough data to calculate {label} growth rates.")
        return

    try:
        weekly_gr, monthly_gr = calculate_growth_rates(prophet_df, date_col="ds", value_col="y")
    except Exception as e:
        st.warning(f"Could not calculate {label} growth rates: {e}")
        return

    st.markdown(f"#### {label}")

    tab_w, tab_m = st.tabs(["Weekly (WoW)", "Monthly (MoM)"])

    with tab_w:
        if not weekly_gr.empty:
            st.markdown(
                growth_table_html(weekly_gr, "Value", "WoW_Growth_%", "Week", "%b %d, %Y"),
                unsafe_allow_html=True,
            )
            # Trend chart
            fig_w = go.Figure()
            fig_w.add_trace(go.Scatter(
                x=weekly_gr["Week"], y=weekly_gr["WoW_Growth_%"],
                mode="lines+markers",
                line=dict(color=COLOR_FORECAST, width=2),
                marker=dict(
                    color=[COLOR_POS if (not pd.isna(v) and v >= 0) else COLOR_NEG
                           for v in weekly_gr["WoW_Growth_%"]],
                    size=8,
                ),
                name="WoW Growth %",
            ))
            fig_w.add_hline(y=0, line_dash="dash", line_color="#666")
            fig_w.update_layout(
                title=f"{label} — Weekly Growth Rate",
                yaxis_title="WoW Growth %",
                template=TEMPLATE,
                paper_bgcolor=BG,
                plot_bgcolor=BG,
                height=280,
                margin=dict(l=40, r=20, t=50, b=40),
            )
            st.plotly_chart(fig_w, use_container_width=True)

    with tab_m:
        if not monthly_gr.empty:
            st.markdown(
                growth_table_html(monthly_gr, "Value", "MoM_Growth_%", "Month", "%b %Y"),
                unsafe_allow_html=True,
            )
            fig_m = go.Figure()
            fig_m.add_trace(go.Bar(
                x=monthly_gr["Month"], y=monthly_gr["MoM_Growth_%"],
                marker_color=[COLOR_POS if (not pd.isna(v) and v >= 0) else COLOR_NEG
                              for v in monthly_gr["MoM_Growth_%"]],
                name="MoM Growth %",
            ))
            fig_m.add_hline(y=0, line_dash="dash", line_color="#666")
            fig_m.update_layout(
                title=f"{label} — Monthly Growth Rate",
                yaxis_title="MoM Growth %",
                template=TEMPLATE,
                paper_bgcolor=BG,
                plot_bgcolor=BG,
                height=280,
                margin=dict(l=40, r=20, t=50, b=40),
            )
            st.plotly_chart(fig_m, use_container_width=True)


with gr_col1:
    render_growth_section(rev_prophet_df, "Revenue", is_currency=True)

with gr_col2:
    render_growth_section(order_prophet_df, "Order Volume")

if not aov_df.empty:
    aov_gr_col, _ = st.columns([1, 1])
    with aov_gr_col:
        render_growth_section(aov_df, "AOV", is_currency=True)

st.divider()

# ─── 5. BRAND-LEVEL FORECASTS ─────────────────────────────────────────────────
st.markdown("## 🏷️ Brand-Level Forecasts")

brand_rev = (
    df.groupby("Brand")["Total(Receipt Total)"]
    .sum()
    .sort_values(ascending=False)
)
top_brands = brand_rev.head(5).index.tolist()

if len(top_brands) < 2:
    st.info("Fewer than two brands found — brand comparison skipped.")
else:
    brand_tabs = st.tabs(top_brands)
    brand_summary = []

    for i, brand in enumerate(top_brands):
        with brand_tabs[i]:
            df_brand = df[df["Brand"] == brand]
            with st.spinner(f"Forecasting {brand}…"):
                try:
                    b_prophet = prepare_prophet_df(df_brand, "Received At", "Total(Receipt Total)", "sum")
                    b_forecast, b_model = run_prophet_forecast(
                        b_prophet, periods=forecast_horizon,
                        yearly_seasonality=False, weekly_seasonality=True, daily_seasonality=False,
                    )
                except Exception as e:
                    st.warning(f"Could not run forecast for {brand}: {e}")
                    b_prophet, b_forecast, b_model = pd.DataFrame(), pd.DataFrame(), None

            if not b_prophet.empty and not b_forecast.empty:
                last_d = b_prophet["ds"].max()
                future_b = b_forecast[b_forecast["ds"] > last_d].head(forecast_horizon)
                total_b_fc = future_b["yhat"].clip(lower=0).sum()
                recent_b = b_prophet[b_prophet["ds"] >= last_d - pd.Timedelta(days=forecast_horizon)]
                current_b = recent_b["y"].sum()
                b_growth = safe_pct_change(total_b_fc, current_b)

                b_col1, b_col2, b_col3 = st.columns(3)
                b_col1.metric(
                    f"Forecast Revenue ({forecast_horizon}d)",
                    fmt_currency(total_b_fc),
                    delta=fmt_pct(b_growth) if not pd.isna(b_growth) else None,
                )
                b_col2.metric(f"Current ({forecast_horizon}d)", fmt_currency(current_b))
                b_col3.metric("Daily Avg (Forecast)", fmt_currency(total_b_fc / forecast_horizon))

                b_fig = create_forecast_chart(
                    b_prophet, b_forecast,
                    title=f"{brand} — Revenue Forecast",
                    y_label="Daily Revenue (AED)",
                    color_actual=COLOR_ACTUAL,
                    color_forecast=COLOR_FORECAST,
                )
                b_fig.update_layout(paper_bgcolor=BG, plot_bgcolor=BG)
                st.plotly_chart(b_fig, use_container_width=True)

                brand_summary.append({
                    "Brand": brand,
                    "Current Revenue": current_b,
                    "Forecast Revenue": total_b_fc,
                    "Projected Growth %": b_growth,
                })
            else:
                st.info(f"Not enough data to forecast {brand} ({len(df_brand)} records).")
                brand_summary.append({
                    "Brand": brand,
                    "Current Revenue": brand_rev.get(brand, 0),
                    "Forecast Revenue": float("nan"),
                    "Projected Growth %": float("nan"),
                })

    # Brand comparison chart
    if brand_summary:
        st.markdown("### Brand Growth Comparison")
        bs_df = pd.DataFrame(brand_summary).dropna(subset=["Projected Growth %"])
        if not bs_df.empty:
            fig_brand_cmp = go.Figure(go.Bar(
                x=bs_df["Brand"],
                y=bs_df["Projected Growth %"],
                marker_color=[COLOR_POS if v >= 0 else COLOR_NEG for v in bs_df["Projected Growth %"]],
                text=[fmt_pct(v) for v in bs_df["Projected Growth %"]],
                textposition="outside",
            ))
            fig_brand_cmp.add_hline(y=0, line_dash="dash", line_color="#555")
            fig_brand_cmp.update_layout(
                title=f"Projected Revenue Growth — Next {forecast_horizon} Days",
                yaxis_title="Projected Growth %",
                xaxis_title="Brand",
                template=TEMPLATE,
                paper_bgcolor=BG,
                plot_bgcolor=BG,
                height=380,
                margin=dict(l=40, r=20, t=60, b=40),
            )
            st.plotly_chart(fig_brand_cmp, use_container_width=True)

st.divider()

# ─── 6. FORECAST SUMMARY TABLE ────────────────────────────────────────────────
st.markdown("## 🗂️ Forecast Summary")

summary_rows = []

if not rev_prophet_df.empty and not rev_forecast_df.empty:
    summary_rows.append(forecast_summary_metric(
        rev_prophet_df, rev_forecast_df, forecast_horizon,
        "Revenue (AED)", fmt_fn=fmt_currency,
    ))

if not order_prophet_df.empty and not ord_forecast_df.empty:
    summary_rows.append(forecast_summary_metric(
        order_prophet_df, ord_forecast_df, forecast_horizon,
        "Order Volume", fmt_fn=lambda x: f"{x:,.0f}",
    ))

if not aov_df.empty and not aov_forecast_df.empty:
    last_d_a = aov_df["ds"].max()
    recent_aov2 = aov_df[aov_df["ds"] >= last_d_a - pd.Timedelta(days=forecast_horizon)]
    future_aov2 = aov_forecast_df[aov_forecast_df["ds"] > last_d_a].head(forecast_horizon)
    current_aov2 = recent_aov2["y"].mean() if not recent_aov2.empty else float("nan")
    forecast_aov2 = future_aov2["yhat"].clip(lower=0).mean() if not future_aov2.empty else float("nan")
    aov_pct2 = safe_pct_change(forecast_aov2, current_aov2)
    summary_rows.append({
        "label": "Avg Order Value (AED)",
        "current": current_aov2,
        "forecast": forecast_aov2,
        "pct_change": aov_pct2,
        "fmt_fn": lambda x: fmt_currency(x, 2),
    })

if summary_rows:
    tbl_cols = st.columns([3, 2, 2, 2])
    tbl_cols[0].markdown("**Metric**")
    tbl_cols[1].markdown(f"**Current (last {forecast_horizon}d)**")
    tbl_cols[2].markdown(f"**Forecast (next {forecast_horizon}d)**")
    tbl_cols[3].markdown("**Projected Growth**")
    st.markdown("<hr style='margin:4px 0 12px 0;border-color:#333;'>", unsafe_allow_html=True)

    for row in summary_rows:
        fn = row.get("fmt_fn", lambda x: f"{x:,.1f}")
        pct = row["pct_change"]
        pct_color = COLOR_POS if (not pd.isna(pct) and pct >= 0) else COLOR_NEG
        c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
        c1.markdown(f"**{row['label']}**")
        c2.markdown(fn(row["current"]) if not pd.isna(row["current"]) else "—")
        c3.markdown(fn(row["forecast"]) if not pd.isna(row["forecast"]) else "—")
        c4.markdown(
            f"<span style='color:{pct_color};font-weight:600;'>{fmt_pct(pct)}</span>"
            if not pd.isna(pct) else "—",
            unsafe_allow_html=True,
        )

    # Key insights
    st.markdown("#### Key Insights")
    insights = []
    if summary_rows:
        best = max(summary_rows, key=lambda r: r["pct_change"] if not pd.isna(r["pct_change"]) else -999)
        worst = min(summary_rows, key=lambda r: r["pct_change"] if not pd.isna(r["pct_change"]) else 999)
        if not pd.isna(best["pct_change"]):
            arrow = "↑" if best["pct_change"] >= 0 else "↓"
            insights.append(
                f"**{best['label']}** shows the strongest outlook with a projected "
                f"{arrow} {abs(best['pct_change']):.1f}% change over the next {forecast_horizon} days."
            )
        if len(summary_rows) > 1 and not pd.isna(worst["pct_change"]) and worst["label"] != best["label"]:
            insights.append(
                f"**{worst['label']}** requires monitoring — projected change of "
                f"{fmt_pct(worst['pct_change'])}."
            )
    for ins in insights:
        st.markdown(f"- {ins}")

st.divider()

# ─── 7. SEASONALITY PATTERNS ──────────────────────────────────────────────────
st.markdown("## 🌀 Seasonality Patterns")

seas_col1, seas_col2 = st.columns(2)

with seas_col1:
    if rev_model is not None:
        weekly_fig = weekly_seasonality_chart(rev_model)
        if weekly_fig:
            weekly_fig.update_layout(paper_bgcolor=BG, plot_bgcolor=BG, height=350)
            st.plotly_chart(weekly_fig, use_container_width=True)
        else:
            st.info("Weekly seasonality pattern not available.")
    else:
        st.info("Revenue model not available for seasonality analysis.")

with seas_col2:
    if rev_model is not None and not rev_forecast_df.empty:
        trend_fig = trend_component_chart(
            rev_model, rev_forecast_df,
            title="Revenue Trend Component",
        )
        if trend_fig:
            trend_fig.update_layout(paper_bgcolor=BG, plot_bgcolor=BG, height=350)
            st.plotly_chart(trend_fig, use_container_width=True)
        else:
            st.info("Trend component not available.")
    else:
        st.info("Revenue model not available for trend analysis.")

st.divider()

# ─── 8. FORECAST ACCURACY DISCLAIMER ─────────────────────────────────────────
st.markdown("## ⚠️ Forecast Accuracy Note")

st.warning(
    """
**Forecast Limitations**

These projections are generated by Facebook Prophet using your current historical dataset (~40,800 orders).
Please consider the following caveats before acting on forecast numbers:

- **Short history window:** Prophet benefits from 1–2+ years of daily data to detect yearly seasonality.
  With less history, yearly seasonality is disabled and estimates will carry wider uncertainty bands.
- **External shocks:** Promotions, new brand launches, Ramadan/holiday demand spikes, or operational
  changes are not modelled and will cause actual results to deviate from forecasts.
- **Data gaps:** Missing days in the historical series reduce forecast accuracy. Ensure orders are
  recorded consistently across all channels and locations.
- **Confidence intervals** represent statistical uncertainty in the model, not guaranteed bounds.
  Actual outcomes may fall outside the shaded region.

**Recommendation:** Treat forecasts as directional guidance (trend, seasonality, growth rate) rather
than precise predictions. Re-run forecasts monthly as new data accumulates.

*More historical data collected via Deliverect going forward will materially improve forecast accuracy.*
    """
)

st.divider()

# ─── 9. DELIVERECT / REVLY INTEGRATION PLACEHOLDER ───────────────────────────
st.markdown("## 🔌 Deliverect & Revly Integration (Coming Soon)")

st.info(
    """
**Future live-data integration will unlock:**

- **Real-time revenue forecasting** — Deliverect order webhooks will feed live data into Prophet,
  enabling rolling daily forecasts that update automatically without manual exports.

- **Dynamic pricing signals from Revly** — Revly's pricing intelligence will add promotional
  discount schedules and price-elasticity coefficients as regressors in the Prophet model,
  improving forecast accuracy during sale periods.

- **Multi-source data fusion** — Combining Deliverect (order management), Revly (pricing),
  and supply-chain data will allow demand sensing: detecting inventory shortfalls or
  menu-mix shifts before they materialise in revenue.

- **Automated anomaly alerts** — When actual daily revenue deviates more than ±15% from
  the Prophet forecast, an automated Slack/email alert will notify the operations team.

- **Channel-level granularity** — Separate forecasts per delivery platform (Talabat, Noon Food,
  Careem, etc.) to optimise platform-specific promotions.

*Contact the tech team to prioritise Deliverect API integration.*
    """
)

# ─── FOOTER ───────────────────────────────────────────────────────────────────
st.markdown(
    "<p style='text-align:center;color:#555;font-size:12px;margin-top:32px;'>"
    "Powered by Facebook Prophet &nbsp;|&nbsp; Cloud Kitchen Analytics Dashboard &nbsp;|&nbsp; "
    f"Data as of {df_raw['Received At'].max().strftime('%d %b %Y') if not df_raw.empty else 'N/A'}"
    "</p>",
    unsafe_allow_html=True,
)
