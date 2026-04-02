"""
Cancellations & Issues Page — Cloud Kitchen Analytics Dashboard
Covers: cancellation trends, rejection analysis, item availability issues,
item snapshot, POS sync health, post-cancellation patterns, and location health scores.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.data_loader import (
    load_cancelled_orders,
    load_rejected_orders,
    load_sales_orders,
    load_item_availability_monitor,
    load_item_availability_snapshot,
    load_pos_sync,
    get_all_brands,
    get_all_locations,
    get_all_channels,
)

# ─── THEME CONSTANTS ────────────────────────────────────────────────────────
DANGER   = "#FF6B6B"
WARNING  = "#FFE66D"
SUCCESS  = "#4ECDC4"
PRIMARY  = "#FF6B35"
MUTED    = "#9E9E9E"
BG_CARD  = "#1E1E2E"
BG_PLOT  = "#16161F"
TEMPLATE = "plotly_dark"
BG       = "rgba(0,0,0,0)"

# ─── PAGE CONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Cancellations & Issues",
    page_icon="🚨",
    layout="wide",
)

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
    .kpi-card.danger  { border-left-color: #FF6B6B; }
    .kpi-card.warning { border-left-color: #FFE66D; }
    .kpi-card.success { border-left-color: #4ECDC4; }
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

def kpi_card(label: str, value: str, sub: str = "", variant: str = ""):
    cls = f"kpi-card {variant}".strip()
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    st.markdown(
        f'<div class="{cls}">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'{sub_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def section(title: str):
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)


def fmt_currency(val: float) -> str:
    if abs(val) >= 1_000_000:
        return f"AED {val/1_000_000:.2f}M"
    if abs(val) >= 1_000:
        return f"AED {val/1_000:.1f}K"
    return f"AED {val:,.0f}"


def apply_filters(df: pd.DataFrame, brands, locations, channels) -> pd.DataFrame:
    if brands and "Brand" in df.columns:
        df = df[df["Brand"].isin(brands)]
    if locations and "Location" in df.columns:
        df = df[df["Location"].isin(locations)]
    if channels and "Channel" in df.columns:
        df = df[df["Channel"].isin(channels)]
    return df


def bar_fig(df_plot, x, y, title, color=PRIMARY, orientation="v", height=320):
    if orientation == "h":
        fig = go.Figure(go.Bar(
            x=df_plot[y], y=df_plot[x],
            orientation="h",
            marker_color=color,
            text=df_plot[y],
            textposition="outside",
        ))
        fig.update_layout(
            template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
            title=title, height=height,
            yaxis=dict(autorange="reversed"),
            margin=dict(l=10, r=10, t=40, b=10),
        )
    else:
        fig = go.Figure(go.Bar(
            x=df_plot[x], y=df_plot[y],
            marker_color=color,
        ))
        fig.update_layout(
            template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
            title=title, height=height,
            margin=dict(l=10, r=10, t=40, b=10),
        )
    return fig


def pie_fig(labels, values, title, height=320):
    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        marker_colors=[PRIMARY, DANGER, SUCCESS, WARNING, "#A29BFE", "#74B9FF", "#FD79A8", "#00CEC9"],
        textinfo="label+percent",
    ))
    fig.update_layout(
        template=TEMPLATE, paper_bgcolor=BG,
        title=title, height=height,
        showlegend=True,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


# ─── LOAD DATA ───────────────────────────────────────────────────────────────

with st.spinner("Loading data…"):
    df_cancel_raw   = load_cancelled_orders()
    df_reject_raw   = load_rejected_orders()
    df_sales_raw    = load_sales_orders()
    df_avail_mon    = load_item_availability_monitor()
    df_avail_snap   = load_item_availability_snapshot()
    df_pos          = load_pos_sync()
    all_brands      = get_all_brands()
    all_locations   = get_all_locations()
    all_channels    = get_all_channels()

# ─── SIDEBAR FILTERS ─────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## Filters")
    sel_brands    = st.multiselect("Brand",    all_brands,    placeholder="All brands")
    sel_locations = st.multiselect("Location", all_locations, placeholder="All locations")
    sel_channels  = st.multiselect("Channel",  all_channels,  placeholder="All channels")
    st.markdown("---")
    st.markdown("**Date Range**")
    _all_dates_ci = pd.to_datetime(df_cancel_raw["Date"], errors="coerce").dropna() if "Date" in df_cancel_raw.columns else pd.Series(dtype="datetime64[ns]")
    _min_ci6 = _all_dates_ci.min().date() if not _all_dates_ci.empty else None
    _max_ci6 = _all_dates_ci.max().date() if not _all_dates_ci.empty else None
    sel_start_ci6 = sel_end_ci6 = None
    if _min_ci6 and _max_ci6:
        _dr_ci6 = st.date_input("Period", value=(_min_ci6, _max_ci6), min_value=_min_ci6, max_value=_max_ci6, label_visibility="collapsed")
        sel_start_ci6, sel_end_ci6 = (_dr_ci6[0], _dr_ci6[1]) if isinstance(_dr_ci6, (list, tuple)) and len(_dr_ci6) == 2 else (_min_ci6, _max_ci6)
    st.markdown("**Time Range**")
    from datetime import time as _time
    _tc1_c6, _tc2_c6 = st.columns(2)
    with _tc1_c6:
        sel_time_from_c6 = st.time_input("From", value=_time(0, 0), step=1800, key="tf_c6")
    with _tc2_c6:
        sel_time_to_c6 = st.time_input("To", value=_time(23, 59), step=1800, key="tt_c6")
    st.markdown("---")
    st.caption("Data: Grubtech + Deliverect")

# ─── APPLY FILTERS ───────────────────────────────────────────────────────────

df_cancel = apply_filters(df_cancel_raw.copy(), sel_brands, sel_locations, sel_channels)
df_reject = apply_filters(df_reject_raw.copy(), sel_brands, sel_locations, sel_channels)
df_sales  = apply_filters(df_sales_raw.copy(),  sel_brands, sel_locations, sel_channels)

# Apply date + time range filter
def _apply_date_filter(dframe):
    if sel_start_ci6 and sel_end_ci6 and "Date" in dframe.columns:
        dframe["Date"] = pd.to_datetime(dframe["Date"], errors="coerce")
        dframe = dframe[dframe["Date"].dt.date >= sel_start_ci6]
        dframe = dframe[dframe["Date"].dt.date <= sel_end_ci6]
        if sel_time_from_c6 != _time(0, 0) or sel_time_to_c6 != _time(23, 59):
            _t = dframe["Date"].dt.time
            _valid = _t.notna()
            dframe = dframe[~_valid | ((_t >= sel_time_from_c6) & (_t <= sel_time_to_c6))]
    return dframe
df_cancel = _apply_date_filter(df_cancel)
df_reject = _apply_date_filter(df_reject)
df_sales  = _apply_date_filter(df_sales)

# Ensure date columns are datetime
for _df, _col in [(df_cancel, "Date"), (df_reject, "Date"), (df_sales, "Date")]:
    if _col in _df.columns:
        _df[_col] = pd.to_datetime(_df[_col], errors="coerce")

# Numeric amounts
for _df in [df_cancel, df_reject]:
    for c in ["Sales Amount", "VAT", "Sales After Tax"]:
        if c in _df.columns:
            _df[c] = pd.to_numeric(_df[c], errors="coerce").fillna(0)

# ─── PAGE HEADER ─────────────────────────────────────────────────────────────

st.title("🚨 Cancellations & Issues")
st.caption("Operational risk dashboard — cancellations, rejections, item availability, and POS sync health.")

# ─── KPI ROW ─────────────────────────────────────────────────────────────────

total_cancel   = len(df_cancel)
total_orders   = max(len(df_sales), 1)
cancel_rate    = total_cancel / (total_orders + total_cancel) * 100
total_reject   = len(df_reject)
rev_lost_cancel = df_cancel["Sales Amount"].sum() if "Sales Amount" in df_cancel.columns else 0
rev_lost_reject = df_reject["Sales Amount"].sum() if "Sales Amount" in df_reject.columns else 0
total_rev_lost  = rev_lost_cancel + rev_lost_reject

# POS error rate
if not df_pos.empty and "Sync Successful" in df_pos.columns and "Total No of Orders" in df_pos.columns:
    pos_total   = pd.to_numeric(df_pos["Total No of Orders"], errors="coerce").sum()
    pos_success = pd.to_numeric(df_pos["Sync Successful"],    errors="coerce").sum()
    pos_err_rate = (1 - pos_success / max(pos_total, 1)) * 100
else:
    pos_err_rate = 0.0

# Avg item unavailability duration
if not df_avail_mon.empty and "Duration (min)" in df_avail_mon.columns:
    df_avail_mon["Duration (min)"] = pd.to_numeric(df_avail_mon["Duration (min)"], errors="coerce")
    avg_unavail_dur = df_avail_mon["Duration (min)"].mean()
else:
    avg_unavail_dur = 0.0

col1, col2, col3, col4, col5, col6 = st.columns(6)
with col1:
    kpi_card("Total Cancellations", f"{total_cancel:,}", "filtered orders", "danger")
with col2:
    kpi_card("Cancellation Rate", f"{cancel_rate:.1f}%", f"{total_cancel} / {total_cancel+total_orders:,}", "warning")
with col3:
    kpi_card("Total Rejections", f"{total_reject:,}", "by operators", "danger")
with col4:
    kpi_card("Revenue Lost", fmt_currency(total_rev_lost), "cancel + reject", "danger")
with col5:
    kpi_card("POS Error Rate", f"{pos_err_rate:.1f}%", "sync failures", "warning" if pos_err_rate < 10 else "danger")
with col6:
    kpi_card("Avg Unavailability", f"{avg_unavail_dur:.0f} min", "per item event", "warning")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — CANCELLATION ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

section("1 · Cancellation Analysis")

# ── Daily cancellation trend ──────────────────────────────────────────────────
if not df_cancel.empty and "Date" in df_cancel.columns:
    daily_cancel = df_cancel.groupby(df_cancel["Date"].dt.date).size().reset_index(name="Cancellations")
    daily_cancel.columns = ["Date", "Cancellations"]

    # Total orders per day (for rate)
    if not df_sales.empty and "Date" in df_sales.columns:
        df_sales["_date"] = pd.to_datetime(df_sales["Date"], errors="coerce").dt.date
        daily_sales = df_sales.groupby("_date").size().reset_index(name="Total")
        daily_sales.columns = ["Date", "Total"]
        daily_merged = daily_cancel.merge(daily_sales, on="Date", how="left").fillna(0)
        daily_merged["Rate"] = daily_merged["Cancellations"] / (
            daily_merged["Cancellations"] + daily_merged["Total"].clip(lower=1)
        ) * 100
    else:
        daily_merged = daily_cancel.copy()
        daily_merged["Rate"] = np.nan

    col_a, col_b = st.columns(2)

    with col_a:
        fig_daily = go.Figure(go.Bar(
            x=daily_cancel["Date"].astype(str),
            y=daily_cancel["Cancellations"],
            marker_color=DANGER,
            name="Cancellations",
        ))
        fig_daily.update_layout(
            template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
            title="Daily Cancellation Volume",
            xaxis_title="Date", yaxis_title="Count",
            height=320, margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig_daily, use_container_width=True)

    with col_b:
        if "Rate" in daily_merged.columns and daily_merged["Rate"].notna().any():
            fig_rate = go.Figure(go.Scatter(
                x=daily_merged["Date"].astype(str),
                y=daily_merged["Rate"],
                mode="lines+markers",
                line=dict(color=WARNING, width=2),
                marker=dict(size=6, color=WARNING),
                name="Cancel Rate %",
                fill="tozeroy",
                fillcolor="rgba(255,230,109,0.12)",
            ))
            fig_rate.add_hline(
                y=cancel_rate,
                line_dash="dash",
                line_color=DANGER,
                annotation_text=f"Avg {cancel_rate:.1f}%",
                annotation_position="top right",
            )
            fig_rate.update_layout(
                template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
                title="Daily Cancellation Rate (%)",
                xaxis_title="Date", yaxis_title="Rate %",
                height=320, margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig_rate, use_container_width=True)
        else:
            st.info("Insufficient data to compute cancellation rate trend.")

    # ── Cancellation reasons ──────────────────────────────────────────────────
    col_c, col_d = st.columns(2)

    with col_c:
        if "Reason" in df_cancel.columns:
            reasons = (
                df_cancel["Reason"]
                .fillna("Unknown")
                .value_counts()
                .reset_index()
            )
            reasons.columns = ["Reason", "Count"]
            reasons = reasons.sort_values("Count")
            fig_reasons = go.Figure(go.Bar(
                x=reasons["Count"],
                y=reasons["Reason"],
                orientation="h",
                marker_color=DANGER,
                text=reasons["Count"],
                textposition="outside",
            ))
            fig_reasons.update_layout(
                template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
                title="Cancellation Reasons",
                height=max(300, len(reasons) * 30),
                yaxis=dict(autorange="reversed"),
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig_reasons, use_container_width=True)

    with col_d:
        if "Source" in df_cancel.columns:
            source_counts = df_cancel["Source"].fillna("Unknown").value_counts()
            fig_src = pie_fig(
                source_counts.index.tolist(),
                source_counts.values.tolist(),
                "Cancellation by Source",
            )
            st.plotly_chart(fig_src, use_container_width=True)

    # ── By Brand / Location / Channel / Delivery ──────────────────────────────
    col_e, col_f = st.columns(2)

    with col_e:
        if "Brand" in df_cancel.columns:
            brand_c = df_cancel["Brand"].value_counts().reset_index()
            brand_c.columns = ["Brand", "Count"]
            st.plotly_chart(
                bar_fig(brand_c, "Brand", "Count", "Cancellations by Brand", PRIMARY, height=300),
                use_container_width=True,
            )

    with col_f:
        if "Location" in df_cancel.columns:
            loc_c = df_cancel["Location"].value_counts().reset_index()
            loc_c.columns = ["Location", "Count"]
            st.plotly_chart(
                bar_fig(loc_c, "Location", "Count", "Cancellations by Location", WARNING, height=300),
                use_container_width=True,
            )

    col_g, col_h = st.columns(2)

    with col_g:
        if "Channel" in df_cancel.columns:
            ch_c = df_cancel["Channel"].value_counts().reset_index()
            ch_c.columns = ["Channel", "Count"]
            st.plotly_chart(
                bar_fig(ch_c, "Channel", "Count", "Cancellations by Channel", SUCCESS, height=300),
                use_container_width=True,
            )

    with col_h:
        if "Delivery Type" in df_cancel.columns:
            dt_c = df_cancel["Delivery Type"].fillna("Unknown").value_counts()
            st.plotly_chart(
                pie_fig(dt_c.index.tolist(), dt_c.values.tolist(), "Cancellations by Delivery Type"),
                use_container_width=True,
            )

    # ── Revenue lost trend ────────────────────────────────────────────────────
    if "Sales Amount" in df_cancel.columns:
        rev_trend = df_cancel.groupby(df_cancel["Date"].dt.date)["Sales Amount"].sum().reset_index()
        rev_trend.columns = ["Date", "Revenue Lost"]
        fig_rev = go.Figure(go.Scatter(
            x=rev_trend["Date"].astype(str),
            y=rev_trend["Revenue Lost"],
            mode="lines+markers",
            line=dict(color=DANGER, width=2),
            fill="tozeroy",
            fillcolor="rgba(255,107,107,0.15)",
            name="Revenue Lost",
        ))
        fig_rev.update_layout(
            template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
            title="Daily Revenue Lost from Cancellations (AED)",
            height=280, margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig_rev, use_container_width=True)

else:
    st.info("No cancellation data available for the selected filters.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — REJECTION ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

section("2 · Rejection Analysis")

if not df_reject.empty:
    col1r, col2r, col3r = st.columns(3)

    with col1r:
        if "Reason" in df_reject.columns:
            rej_reasons = df_reject["Reason"].fillna("Unknown").value_counts().reset_index()
            rej_reasons.columns = ["Reason", "Count"]
            rej_reasons = rej_reasons.sort_values("Count")
            fig_rr = go.Figure(go.Bar(
                x=rej_reasons["Count"],
                y=rej_reasons["Reason"],
                orientation="h",
                marker_color=DANGER,
                text=rej_reasons["Count"],
                textposition="outside",
            ))
            fig_rr.update_layout(
                template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
                title="Rejection Reasons",
                height=320,
                yaxis=dict(autorange="reversed"),
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig_rr, use_container_width=True)

    with col2r:
        sub_cols = [c for c in ["Brand", "Location"] if c in df_reject.columns]
        if sub_cols:
            grp_col = sub_cols[0]
            rej_grp = df_reject[grp_col].value_counts().reset_index()
            rej_grp.columns = [grp_col, "Count"]
            st.plotly_chart(
                bar_fig(rej_grp, grp_col, "Count", f"Rejections by {grp_col}", WARNING, height=320),
                use_container_width=True,
            )

    with col3r:
        if "Sales Amount" in df_reject.columns:
            rej_rev_col = "Brand" if "Brand" in df_reject.columns else (
                "Location" if "Location" in df_reject.columns else None
            )
            if rej_rev_col:
                rej_rev = df_reject.groupby(rej_rev_col)["Sales Amount"].sum().reset_index()
                rej_rev.columns = [rej_rev_col, "Revenue Lost"]
                rej_rev = rej_rev.sort_values("Revenue Lost", ascending=False)
                fig_rrev = go.Figure(go.Bar(
                    x=rej_rev[rej_rev_col],
                    y=rej_rev["Revenue Lost"],
                    marker_color=DANGER,
                ))
                fig_rrev.update_layout(
                    template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
                    title=f"Rejection Revenue Impact by {rej_rev_col} (AED)",
                    height=320,
                    margin=dict(l=10, r=10, t=40, b=10),
                )
                st.plotly_chart(fig_rrev, use_container_width=True)
            else:
                total_r = df_reject["Sales Amount"].sum()
                kpi_card("Total Rejection Revenue Lost", fmt_currency(total_r), "", "danger")
else:
    st.info("No rejection records for the selected filters.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — ITEM AVAILABILITY ISSUES (MONITOR)
# ═══════════════════════════════════════════════════════════════════════════════

section("3 · Item Availability Issues")

df_mon = df_avail_mon.copy()
if not df_mon.empty:
    if "Date" in df_mon.columns:
        df_mon["Date"] = pd.to_datetime(df_mon["Date"], errors="coerce")
    if "Duration (min)" in df_mon.columns:
        df_mon["Duration (min)"] = pd.to_numeric(df_mon["Duration (min)"], errors="coerce")

    # Apply brand/location filters
    if sel_brands and "Brand" in df_mon.columns:
        df_mon = df_mon[df_mon["Brand"].isin(sel_brands)]
    if sel_locations and "Location" in df_mon.columns:
        df_mon = df_mon[df_mon["Location"].isin(sel_locations)]

    # ── Trend over time ───────────────────────────────────────────────────────
    col_m1, col_m2 = st.columns(2)

    with col_m1:
        if "Date" in df_mon.columns:
            unavail_trend = df_mon.groupby(df_mon["Date"].dt.date).size().reset_index(name="Events")
            unavail_trend.columns = ["Date", "Events"]
            fig_ut = go.Figure(go.Bar(
                x=unavail_trend["Date"].astype(str),
                y=unavail_trend["Events"],
                marker_color=WARNING,
            ))
            fig_ut.update_layout(
                template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
                title="Item Unavailability Events Over Time",
                xaxis_title="Date", yaxis_title="Events",
                height=300, margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig_ut, use_container_width=True)

    with col_m2:
        if "Action Type" in df_mon.columns:
            action_counts = df_mon["Action Type"].fillna("Unknown").value_counts()
            fig_at = pie_fig(
                action_counts.index.tolist(),
                action_counts.values.tolist(),
                "Action Type Breakdown",
            )
            st.plotly_chart(fig_at, use_container_width=True)

    # ── Top unavailable items ─────────────────────────────────────────────────
    col_m3, col_m4 = st.columns(2)

    with col_m3:
        if "Item" in df_mon.columns:
            top_items = df_mon["Item"].value_counts().head(20).reset_index()
            top_items.columns = ["Item", "Count"]
            top_items = top_items.sort_values("Count")
            fig_ti = go.Figure(go.Bar(
                x=top_items["Count"],
                y=top_items["Item"],
                orientation="h",
                marker_color=WARNING,
                text=top_items["Count"],
                textposition="outside",
            ))
            fig_ti.update_layout(
                template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
                title="Top 20 Most Frequently Unavailable Items",
                height=500,
                yaxis=dict(autorange="reversed"),
                margin=dict(l=10, r=10, t=40, b=60),
            )
            st.plotly_chart(fig_ti, use_container_width=True)

    with col_m4:
        if "Item" in df_mon.columns and "Duration (min)" in df_mon.columns:
            avg_dur = (
                df_mon.groupby("Item")["Duration (min)"]
                .mean()
                .dropna()
                .sort_values(ascending=False)
                .head(20)
                .reset_index()
            )
            avg_dur.columns = ["Item", "Avg Duration (min)"]
            avg_dur = avg_dur.sort_values("Avg Duration (min)")
            fig_ad = go.Figure(go.Bar(
                x=avg_dur["Avg Duration (min)"],
                y=avg_dur["Item"],
                orientation="h",
                marker_color=DANGER,
                text=avg_dur["Avg Duration (min)"].round(1),
                textposition="outside",
            ))
            fig_ad.update_layout(
                template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
                title="Avg Unavailability Duration by Item (min)",
                height=500,
                yaxis=dict(autorange="reversed"),
                margin=dict(l=10, r=10, t=40, b=60),
            )
            st.plotly_chart(fig_ad, use_container_width=True)

    # ── By location ───────────────────────────────────────────────────────────
    if "Location" in df_mon.columns:
        loc_unavail = df_mon["Location"].value_counts().reset_index()
        loc_unavail.columns = ["Location", "Events"]
        fig_lu = go.Figure(go.Bar(
            x=loc_unavail["Location"],
            y=loc_unavail["Events"],
            marker_color=WARNING,
        ))
        fig_lu.update_layout(
            template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
            title="Item Unavailability Events by Location",
            height=300, margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig_lu, use_container_width=True)

else:
    st.info("No item availability monitor data available.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — ITEM AVAILABILITY SNAPSHOT
# ═══════════════════════════════════════════════════════════════════════════════

section("4 · Item Availability Snapshot (Current Status)")

df_snap = df_avail_snap.copy()
if not df_snap.empty:
    if sel_brands and "Brand" in df_snap.columns:
        df_snap = df_snap[df_snap["Brand"].isin(sel_brands)]
    if sel_locations and "Location" in df_snap.columns:
        df_snap = df_snap[df_snap["Location"].isin(sel_locations)]

    col_s1, col_s2, col_s3 = st.columns(3)

    with col_s1:
        if "Status" in df_snap.columns:
            status_counts = df_snap["Status"].fillna("Unknown").value_counts()
            colors_snap = [SUCCESS if str(s).lower() in ("available", "active", "enabled")
                           else DANGER for s in status_counts.index]
            fig_status = go.Figure(go.Pie(
                labels=status_counts.index.tolist(),
                values=status_counts.values.tolist(),
                hole=0.4,
                marker_colors=colors_snap,
                textinfo="label+percent",
            ))
            fig_status.update_layout(
                template=TEMPLATE, paper_bgcolor=BG,
                title="Current Status Distribution",
                height=320, margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig_status, use_container_width=True)

    with col_s2:
        if "Brand" in df_snap.columns and "Status" in df_snap.columns:
            unavail_mask = ~df_snap["Status"].fillna("").str.lower().isin(
                ["available", "active", "enabled"]
            )
            snap_brand = (
                df_snap[unavail_mask]["Brand"]
                .value_counts()
                .reset_index()
            )
            snap_brand.columns = ["Brand", "Unavailable Items"]
            st.plotly_chart(
                bar_fig(snap_brand, "Brand", "Unavailable Items",
                        "Unavailable Items by Brand", DANGER, height=320),
                use_container_width=True,
            )

    with col_s3:
        if "Location" in df_snap.columns and "Status" in df_snap.columns:
            unavail_mask2 = ~df_snap["Status"].fillna("").str.lower().isin(
                ["available", "active", "enabled"]
            )
            snap_loc = (
                df_snap[unavail_mask2]["Location"]
                .value_counts()
                .reset_index()
            )
            snap_loc.columns = ["Location", "Unavailable Items"]
            st.plotly_chart(
                bar_fig(snap_loc, "Location", "Unavailable Items",
                        "Unavailable Items by Location", WARNING, height=320),
                use_container_width=True,
            )

else:
    st.info("No item availability snapshot data available.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — POS SYNC HEALTH
# ═══════════════════════════════════════════════════════════════════════════════

section("5 · POS Sync Health")

df_pos_f = df_pos.copy()
if not df_pos_f.empty:
    for c in ["Total No of Orders", "Sync Successful", "Error"]:
        if c in df_pos_f.columns:
            df_pos_f[c] = pd.to_numeric(df_pos_f[c], errors="coerce").fillna(0)

    df_pos_f["Sync Rate %"] = np.where(
        df_pos_f["Total No of Orders"] > 0,
        df_pos_f["Sync Successful"] / df_pos_f["Total No of Orders"] * 100,
        0,
    )
    df_pos_f["Error Rate %"] = 100 - df_pos_f["Sync Rate %"]

    col_p1, col_p2 = st.columns(2)

    with col_p1:
        if "Location" in df_pos_f.columns:
            pos_loc = df_pos_f.sort_values("Sync Rate %")
            bar_colors = [SUCCESS if r >= 95 else WARNING if r >= 80 else DANGER
                          for r in pos_loc["Sync Rate %"]]
            fig_sync = go.Figure()
            fig_sync.add_trace(go.Bar(
                x=pos_loc["Sync Rate %"],
                y=pos_loc["Location"],
                orientation="h",
                marker_color=bar_colors,
                text=[f"{r:.1f}%" for r in pos_loc["Sync Rate %"]],
                textposition="outside",
                name="Sync Rate",
            ))
            fig_sync.add_vline(
                x=95, line_dash="dash", line_color=SUCCESS,
                annotation_text="95% target",
                annotation_position="top",
            )
            fig_sync.update_layout(
                template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
                title="POS Sync Success Rate by Location (%)",
                xaxis=dict(range=[0, 110]),
                height=max(300, len(pos_loc) * 35 + 60),
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig_sync, use_container_width=True)

    with col_p2:
        if "Brand" in df_pos_f.columns:
            brand_err = df_pos_f.groupby("Brand").agg(
                Total=("Total No of Orders", "sum"),
                Errors=("Error", "sum"),
            ).reset_index()
            brand_err["Error Rate %"] = np.where(
                brand_err["Total"] > 0,
                brand_err["Errors"] / brand_err["Total"] * 100,
                0,
            )
            fig_berr = go.Figure(go.Bar(
                x=brand_err["Brand"],
                y=brand_err["Error Rate %"],
                marker_color=[DANGER if r > 5 else WARNING if r > 1 else SUCCESS
                               for r in brand_err["Error Rate %"]],
                text=[f"{r:.1f}%" for r in brand_err["Error Rate %"]],
                textposition="outside",
            ))
            fig_berr.update_layout(
                template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
                title="POS Error Rate by Brand (%)",
                height=320,
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig_berr, use_container_width=True)

    # ── Scatter: total orders vs sync errors ──────────────────────────────────
    scatter_col = "Location" if "Location" in df_pos_f.columns else (
        "Brand" if "Brand" in df_pos_f.columns else None
    )
    if scatter_col and "Error" in df_pos_f.columns:
        fig_sc = go.Figure(go.Scatter(
            x=df_pos_f["Total No of Orders"],
            y=df_pos_f["Error"],
            mode="markers+text",
            text=df_pos_f[scatter_col],
            textposition="top center",
            marker=dict(
                size=12,
                color=df_pos_f["Error Rate %"],
                colorscale=[[0, SUCCESS], [0.5, WARNING], [1, DANGER]],
                showscale=True,
                colorbar=dict(title="Error Rate %"),
            ),
        ))
        fig_sc.update_layout(
            template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
            title="Total Orders vs POS Sync Errors",
            xaxis_title="Total Orders",
            yaxis_title="Sync Errors",
            height=360,
            margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig_sc, use_container_width=True)

else:
    st.info("No POS sync data available.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — POST-CANCELLATION ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

section("6 · Post-Cancellation Analysis")

if not df_cancel.empty:
    col_pc1, col_pc2 = st.columns(2)

    with col_pc1:
        if "Post Cancelled" in df_cancel.columns:
            pc_counts = df_cancel["Post Cancelled"].fillna("Unknown").value_counts()
            pc_total = pc_counts.sum()
            fig_pc = go.Figure(go.Pie(
                labels=pc_counts.index.tolist(),
                values=pc_counts.values.tolist(),
                hole=0.4,
                marker_colors=[DANGER, SUCCESS, WARNING, MUTED],
                textinfo="label+percent+value",
            ))
            fig_pc.update_layout(
                template=TEMPLATE, paper_bgcolor=BG,
                title=f"Post-Cancelled Flag Distribution (n={pc_total:,})",
                height=320, margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig_pc, use_container_width=True)
        else:
            st.info("No 'Post Cancelled' column found in cancellations data.")

    with col_pc2:
        if "Credit Memo Sequence" in df_cancel.columns:
            has_memo = df_cancel["Credit Memo Sequence"].notna() & (
                df_cancel["Credit Memo Sequence"].astype(str).str.strip() != ""
            )
            memo_counts = pd.Series({
                "Has Credit Memo": has_memo.sum(),
                "No Credit Memo": (~has_memo).sum(),
            })
            fig_cm = go.Figure(go.Pie(
                labels=memo_counts.index.tolist(),
                values=memo_counts.values.tolist(),
                hole=0.4,
                marker_colors=[SUCCESS, WARNING],
                textinfo="label+percent+value",
            ))
            fig_cm.update_layout(
                template=TEMPLATE, paper_bgcolor=BG,
                title="Credit Memo Coverage",
                height=320, margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig_cm, use_container_width=True)

            # Credit memo by brand
            if "Brand" in df_cancel.columns:
                memo_brand = (
                    df_cancel[has_memo]["Brand"]
                    .value_counts()
                    .reset_index()
                )
                memo_brand.columns = ["Brand", "Credit Memos"]
                if not memo_brand.empty:
                    fig_cmb = go.Figure(go.Bar(
                        x=memo_brand["Brand"],
                        y=memo_brand["Credit Memos"],
                        marker_color=SUCCESS,
                    ))
                    fig_cmb.update_layout(
                        template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
                        title="Credit Memos Issued by Brand",
                        height=280, margin=dict(l=10, r=10, t=40, b=10),
                    )
                    st.plotly_chart(fig_cmb, use_container_width=True)
        else:
            st.info("No 'Credit Memo Sequence' column found in cancellations data.")
else:
    st.info("No cancellation data available for post-cancellation analysis.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — COMBINED LOCATION HEALTH SCORE
# ═══════════════════════════════════════════════════════════════════════════════

section("7 · Location Health Score")

st.caption(
    "Composite score (0–100, higher = healthier) combining cancellation rate, "
    "POS sync errors, and item unavailability. "
    "Weights: cancellation 40% · POS errors 30% · item unavailability 30%."
)

health_records = {}

# 1) Cancellation rate per location
if not df_cancel_raw.empty and "Location" in df_cancel_raw.columns:
    cancel_by_loc = df_cancel_raw["Location"].value_counts().to_dict()
else:
    cancel_by_loc = {}

if not df_sales_raw.empty and "Location" in df_sales_raw.columns:
    sales_by_loc = df_sales_raw["Location"].value_counts().to_dict()
else:
    sales_by_loc = {}

all_locs_health = set(list(cancel_by_loc.keys()) + list(sales_by_loc.keys()))

for loc in all_locs_health:
    c = cancel_by_loc.get(loc, 0)
    s = sales_by_loc.get(loc, 0)
    rate = c / (c + s) * 100 if (c + s) > 0 else 0
    health_records.setdefault(loc, {})["cancel_rate"] = rate

# 2) POS error rate per location
if not df_pos.empty and "Location" in df_pos.columns:
    for _, row in df_pos.iterrows():
        loc = row.get("Location", "Unknown")
        total = pd.to_numeric(row.get("Total No of Orders", 0), errors="coerce") or 0
        err   = pd.to_numeric(row.get("Error", 0),              errors="coerce") or 0
        err_rate = (err / total * 100) if total > 0 else 0
        health_records.setdefault(loc, {})["pos_err_rate"] = err_rate

# 3) Avg unavailability events per location
if not df_avail_mon.empty and "Location" in df_avail_mon.columns:
    unavail_by_loc = df_avail_mon["Location"].value_counts().to_dict()
    max_unavail = max(unavail_by_loc.values()) if unavail_by_loc else 1
    for loc, cnt in unavail_by_loc.items():
        health_records.setdefault(loc, {})["unavail_score"] = cnt / max_unavail * 100
else:
    unavail_by_loc = {}

# Build score
health_rows = []
for loc, metrics in health_records.items():
    c_rate   = metrics.get("cancel_rate",   0)
    p_rate   = metrics.get("pos_err_rate",  0)
    u_score  = metrics.get("unavail_score", 0)

    # Penalty scores (0 = perfect, 100 = worst)
    c_penalty = min(c_rate * 5, 100)      # 20% cancel rate → 100 penalty
    p_penalty = min(p_rate * 2, 100)      # 50% error rate → 100 penalty
    u_penalty = u_score                    # already 0–100

    composite_penalty = 0.40 * c_penalty + 0.30 * p_penalty + 0.30 * u_penalty
    health_score = max(0, 100 - composite_penalty)

    health_rows.append({
        "Location": loc,
        "Cancel Rate %": round(c_rate, 2),
        "POS Error Rate %": round(p_rate, 2),
        "Unavailability Score": round(u_score, 1),
        "Health Score": round(health_score, 1),
    })

if health_rows:
    df_health = pd.DataFrame(health_rows).sort_values("Health Score", ascending=False)

    # Bar chart
    bar_colors_h = [
        SUCCESS if s >= 80 else WARNING if s >= 60 else DANGER
        for s in df_health["Health Score"]
    ]
    fig_health = go.Figure(go.Bar(
        x=df_health["Location"],
        y=df_health["Health Score"],
        marker_color=bar_colors_h,
        text=[f"{s:.0f}" for s in df_health["Health Score"]],
        textposition="outside",
    ))
    fig_health.add_hline(y=80, line_dash="dash", line_color=SUCCESS,
                          annotation_text="Good (80)", annotation_position="top right")
    fig_health.add_hline(y=60, line_dash="dash", line_color=WARNING,
                          annotation_text="Warning (60)", annotation_position="top right")
    fig_health.update_layout(
        template=TEMPLATE, paper_bgcolor=BG, plot_bgcolor=BG,
        title="Location Health Score (100 = Perfect)",
        yaxis=dict(range=[0, 115]),
        height=360,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(fig_health, use_container_width=True)

    # Detail table
    st.markdown("##### Health Score Breakdown by Location")
    df_display = df_health.copy()
    df_display["Rank"] = range(1, len(df_display) + 1)
    df_display = df_display[["Rank", "Location", "Health Score",
                               "Cancel Rate %", "POS Error Rate %", "Unavailability Score"]]
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Health Score": st.column_config.ProgressColumn(
                "Health Score",
                min_value=0,
                max_value=100,
                format="%d",
            ),
        },
    )
else:
    st.info("Insufficient location-level data to compute health scores.")

st.divider()
st.caption("Cancellations & Issues · Cloud Kitchen Analytics Dashboard · Data: March 2026")
