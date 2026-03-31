"""
Forecasting utilities using Facebook Prophet.
Provides 30/60/90-day projections for revenue, orders, and AOV.
"""

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def prepare_prophet_df(df: pd.DataFrame, date_col: str, value_col: str, agg_func: str = "sum") -> pd.DataFrame:
    """Prepare a DataFrame for Prophet: requires 'ds' and 'y' columns."""
    if df.empty or date_col not in df.columns or value_col not in df.columns:
        return pd.DataFrame()

    ts = df.copy()
    ts[date_col] = pd.to_datetime(ts[date_col], errors="coerce")
    ts = ts.dropna(subset=[date_col])
    ts[value_col] = pd.to_numeric(ts[value_col], errors="coerce").fillna(0)

    if agg_func == "sum":
        daily = ts.groupby(ts[date_col].dt.date)[value_col].sum().reset_index()
    elif agg_func == "mean":
        daily = ts.groupby(ts[date_col].dt.date)[value_col].mean().reset_index()
    elif agg_func == "count":
        daily = ts.groupby(ts[date_col].dt.date)[value_col].count().reset_index()
    else:
        daily = ts.groupby(ts[date_col].dt.date)[value_col].sum().reset_index()

    daily.columns = ["ds", "y"]
    daily["ds"] = pd.to_datetime(daily["ds"])
    daily = daily.sort_values("ds").reset_index(drop=True)
    return daily


@st.cache_data(ttl=3600)
def run_prophet_forecast(prophet_df: pd.DataFrame, periods: int = 90,
                         yearly_seasonality: bool = False,
                         weekly_seasonality: bool = True,
                         daily_seasonality: bool = False) -> tuple:
    """
    Run Prophet forecast and return (forecast_df, model).
    Returns tuple of (forecast DataFrame, fig).
    """
    if prophet_df.empty or len(prophet_df) < 7:
        return pd.DataFrame(), None

    try:
        from prophet import Prophet

        model = Prophet(
            yearly_seasonality=yearly_seasonality,
            weekly_seasonality=weekly_seasonality,
            daily_seasonality=daily_seasonality,
            changepoint_prior_scale=0.05,
            interval_width=0.80,
        )
        model.fit(prophet_df)

        future = model.make_future_dataframe(periods=periods)
        forecast = model.predict(future)

        return forecast, model
    except ImportError:
        st.warning("Prophet not installed. Install with: pip install prophet")
        return pd.DataFrame(), None
    except Exception as e:
        st.warning(f"Forecasting error: {str(e)}")
        return pd.DataFrame(), None


def create_forecast_chart(historical_df: pd.DataFrame, forecast_df: pd.DataFrame,
                          title: str = "Forecast", y_label: str = "Value",
                          color_actual: str = "#FF6B35",
                          color_forecast: str = "#4ECDC4") -> go.Figure:
    """Create a Plotly chart showing historical data + forecast with confidence interval."""
    fig = go.Figure()

    if not historical_df.empty:
        fig.add_trace(go.Scatter(
            x=historical_df["ds"], y=historical_df["y"],
            mode="lines+markers", name="Actual",
            line=dict(color=color_actual, width=2),
            marker=dict(size=4),
        ))

    if not forecast_df.empty:
        # Split into historical fit and future forecast
        if not historical_df.empty:
            last_date = historical_df["ds"].max()
            future_forecast = forecast_df[forecast_df["ds"] > last_date]
        else:
            future_forecast = forecast_df

        # Confidence interval
        fig.add_trace(go.Scatter(
            x=pd.concat([future_forecast["ds"], future_forecast["ds"][::-1]]),
            y=pd.concat([future_forecast["yhat_upper"], future_forecast["yhat_lower"][::-1]]),
            fill="toself", fillcolor=f"rgba(78, 205, 196, 0.15)",
            line=dict(color="rgba(255,255,255,0)"),
            name="80% Confidence",
            showlegend=True,
        ))

        # Forecast line
        fig.add_trace(go.Scatter(
            x=future_forecast["ds"], y=future_forecast["yhat"],
            mode="lines", name="Forecast",
            line=dict(color=color_forecast, width=2, dash="dash"),
        ))

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title=y_label,
        template="plotly_dark",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=60, b=40),
    )

    return fig


def calculate_growth_rates(df: pd.DataFrame, date_col: str = "ds",
                           value_col: str = "y") -> pd.DataFrame:
    """Calculate WoW, MoM growth rates from a time series."""
    if df.empty:
        return pd.DataFrame()

    ts = df.copy()
    ts[date_col] = pd.to_datetime(ts[date_col])

    # Weekly aggregation
    weekly = ts.set_index(date_col).resample("W")[value_col].sum().reset_index()
    weekly.columns = ["Week", "Value"]
    weekly["WoW_Growth_%"] = weekly["Value"].pct_change() * 100

    # Monthly aggregation
    monthly = ts.set_index(date_col).resample("ME")[value_col].sum().reset_index()
    monthly.columns = ["Month", "Value"]
    monthly["MoM_Growth_%"] = monthly["Value"].pct_change() * 100

    return weekly, monthly
