"""
Shared sidebar filter widget for all dashboard pages.

Uses stable widget keys so selections persist across pages via Streamlit's
session_state — pick a brand on Sales, click into Operations, brand stays picked.

Usage in any page:

    from utils.sidebar import render_filters, apply_filters

    df = load_sales_orders()
    filters = render_filters(df, time_filter=True)
    df = apply_filters(df, filters)
"""

from datetime import time as _time, datetime as _dt
import pandas as pd
import streamlit as st

from utils.data_loader import (
    add_cuisine_column, get_all_brands, get_all_channels,
    get_all_locations, get_all_cuisines,
)


def render_filters(df: pd.DataFrame, time_filter: bool = True, key_suffix: str = ""):
    """
    Render the standard sidebar filter UI and return the selected values.

    Stable widget keys (f_brands, f_locations, etc.) ensure filter values
    persist as users navigate between pages.

    Args:
        df: The primary order DataFrame (used to populate filter options
            and date range bounds).
        time_filter: If True, show the From/To time-of-day pickers.
        key_suffix: Optional suffix to append to widget keys. Use only if
            a page truly needs an isolated filter set; default empty
            value lets all pages share state.

    Returns:
        dict with keys: brands, locations, channels, cuisines, start, end,
        time_from, time_to.
    """
    if "Cuisine" not in df.columns:
        df = add_cuisine_column(df, "Brand")

    all_brands = get_all_brands(df)
    all_locations = get_all_locations(df)
    all_channels = get_all_channels(df)
    all_cuisines = get_all_cuisines()

    # Choose timestamp column for date range
    if "Pickup Time" in df.columns and df["Pickup Time"].notna().any():
        ts_col = "Pickup Time"
    elif "Received At" in df.columns:
        ts_col = "Received At"
    else:
        ts_col = None

    with st.sidebar:
        st.markdown("## 🎛️ Filters")
        st.caption("Filters persist across pages.")
        st.markdown("---")

        sel_brands = st.multiselect(
            "Brand", options=all_brands, default=[],
            placeholder="All brands", key=f"f_brands{key_suffix}",
        )
        sel_locations = st.multiselect(
            "Location", options=all_locations, default=[],
            placeholder="All locations", key=f"f_locations{key_suffix}",
        )
        sel_channels = st.multiselect(
            "Channel", options=all_channels, default=[],
            placeholder="All channels", key=f"f_channels{key_suffix}",
        )
        sel_cuisines = st.multiselect(
            "Cuisine", options=all_cuisines, default=[],
            placeholder="All cuisines", key=f"f_cuisines{key_suffix}",
        )

        st.markdown("---")
        st.markdown("**Date range**")
        sel_start, sel_end = None, None
        if ts_col:
            valid = df[ts_col].dropna()
            if not valid.empty:
                _min = valid.min().date()
                _max = valid.max().date()
                _dr = st.date_input(
                    "Period", value=(_min, _max),
                    min_value=_min, max_value=_max,
                    label_visibility="collapsed",
                    key=f"f_dates{key_suffix}",
                )
                if isinstance(_dr, (list, tuple)) and len(_dr) == 2:
                    sel_start, sel_end = _dr[0], _dr[1]
                else:
                    sel_start = sel_end = _min

        sel_time_from = _time(0, 0)
        sel_time_to = _time(23, 59)
        if time_filter:
            st.markdown("**Time range**")
            tc1, tc2 = st.columns(2)
            with tc1:
                sel_time_from = st.time_input(
                    "From", value=_time(0, 0), step=1800,
                    key=f"f_time_from{key_suffix}",
                )
            with tc2:
                sel_time_to = st.time_input(
                    "To", value=_time(23, 59), step=1800,
                    key=f"f_time_to{key_suffix}",
                )

        st.markdown("---")
        st.caption("Data: Grubtech (≤ Mar 23) + Deliverect (≥ Mar 24)")

    return {
        "brands": sel_brands,
        "locations": sel_locations,
        "channels": sel_channels,
        "cuisines": sel_cuisines,
        "start": sel_start,
        "end": sel_end,
        "time_from": sel_time_from,
        "time_to": sel_time_to,
        "ts_col": ts_col,
    }


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """
    Apply the filter dict returned by render_filters to a DataFrame.

    Silently skips columns that aren't present in df, so this works for
    sales orders, cancellations, and other shapes.
    """
    if df is None or df.empty:
        return df

    if filters.get("brands") and "Brand" in df.columns:
        df = df[df["Brand"].isin(filters["brands"])]
    if filters.get("locations") and "Location" in df.columns:
        df = df[df["Location"].isin(filters["locations"])]
    if filters.get("channels") and "Channel" in df.columns:
        df = df[df["Channel"].isin(filters["channels"])]
    if filters.get("cuisines") and "Cuisine" in df.columns:
        df = df[df["Cuisine"].isin(filters["cuisines"])]

    ts_col = filters.get("ts_col")
    if filters.get("start") and filters.get("end") and ts_col and ts_col in df.columns:
        start_dt = pd.Timestamp(_dt.combine(filters["start"], filters["time_from"]))
        end_dt = pd.Timestamp(_dt.combine(filters["end"], filters["time_to"]))
        df = df[(df[ts_col] >= start_dt) & (df[ts_col] <= end_dt)]

    return df
