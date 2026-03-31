"""
Operations Analytics Page
Cloud kitchen operational performance: timing, delays, kitchen throughput, POS sync.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.data_loader import *

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# ─── PAGE CONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Operations", page_icon="⚙️", layout="wide")

# ─── THEME ───────────────────────────────────────────────────────────────────
PRIMARY   = "#FF6B35"
SECONDARY = "#4ECDC4"
WARNING   = "#FFE66D"
DANGER    = "#FF6B6B"
TEMPLATE  = "plotly_dark"
DELAY_THRESHOLD   = 45   # minutes
TARGET_DELAY_RATE = 20   # percent

# ─── DATA LOAD ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def get_data():
    return (
        load_operations_orders(),
        load_operations_locations(),
        load_operations_stations(),
        load_pos_sync(),
    )

with st.spinner("Loading operations data…"):
    df_orders, df_locations, df_stations, df_pos = get_data()

# ─── SIDEBAR FILTERS ─────────────────────────────────────────────────────────
st.sidebar.header("⚙️ Operations Filters")

def _unique(df, col):
    return sorted(df[col].dropna().unique().tolist()) if col in df.columns else []

all_brands    = _unique(df_orders, "Brand")
all_locations = _unique(df_orders, "Location")
all_channels  = _unique(df_orders, "Channel")

sel_brands    = st.sidebar.multiselect("Brand",    all_brands,    default=all_brands)
sel_locations = st.sidebar.multiselect("Location", all_locations, default=all_locations)
sel_channels  = st.sidebar.multiselect("Channel",  all_channels,  default=all_channels)

def apply_filters(df):
    mask = pd.Series(True, index=df.index)
    if sel_brands    and "Brand"    in df.columns: mask &= df["Brand"].isin(sel_brands)
    if sel_locations and "Location" in df.columns: mask &= df["Location"].isin(sel_locations)
    if sel_channels  and "Channel"  in df.columns: mask &= df["Channel"].isin(sel_channels)
    return df[mask].copy()

fdf = apply_filters(df_orders)
fst = apply_filters(df_stations)

# ─── COLUMN ALIASES ──────────────────────────────────────────────────────────
COL_ACCEPT   = "Order Accepted to Started (min)"
COL_PREP     = "Started To Prepared (min)"
COL_PREDIS   = "Prepared to Sent to Dispatch (min)"
COL_DISPATCH = "Sent To Dispatch to Dispatched (min)"
COL_DELIVER  = "Dispatched to Delivered (min)"
COL_TOTAL    = "Order Received to Delivered (min)"

def safe_mean(s):
    v = s.dropna()
    return float(v.mean()) if not v.empty else 0.0

# ═════════════════════════════════════════════════════════════════════════════
# TITLE
# ═════════════════════════════════════════════════════════════════════════════
st.title("⚙️ Operations Analytics")
st.caption(
    f"Showing {len(fdf):,} orders after filters  ·  "
    f"Delay threshold: {DELAY_THRESHOLD} min end-to-end"
)

# ═════════════════════════════════════════════════════════════════════════════
# 1 – KPI ROW
# ═════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Key Performance Indicators")

avg_total    = safe_mean(fdf[COL_TOTAL])   if COL_TOTAL   in fdf.columns else 0.0
avg_prep     = safe_mean(fdf[COL_PREP])    if COL_PREP    in fdf.columns else 0.0
avg_dispatch = safe_mean(fdf[COL_DELIVER]) if COL_DELIVER in fdf.columns else 0.0

pos_sync_rate = 0.0
if (not df_pos.empty
        and "Sync Successful" in df_pos.columns
        and "Total No of Orders" in df_pos.columns):
    tot = df_pos["Total No of Orders"].sum()
    if tot > 0:
        pos_sync_rate = df_pos["Sync Successful"].sum() / tot * 100

delayed_orders = int((fdf[COL_TOTAL] > DELAY_THRESHOLD).sum()) if COL_TOTAL in fdf.columns else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric(
    "Avg Order-to-Delivery", f"{avg_total:.1f} min",
    delta=f"{avg_total - DELAY_THRESHOLD:.1f} vs {DELAY_THRESHOLD}min target",
    delta_color="inverse",
)
k2.metric("Avg Prep Time",     f"{avg_prep:.1f} min")
k3.metric("Avg Dispatch Time", f"{avg_dispatch:.1f} min")
k4.metric(
    "POS Sync Rate", f"{pos_sync_rate:.1f}%",
    delta=f"{pos_sync_rate - 100:.1f}pp" if pos_sync_rate < 100 else "100%",
    delta_color="inverse",
)
k5.metric(
    "Total Delayed Orders", f"{delayed_orders:,}",
    delta=f"{delayed_orders / len(fdf) * 100:.1f}% of total" if len(fdf) > 0 else "",
    delta_color="inverse",
)

# ═════════════════════════════════════════════════════════════════════════════
# 2 – DELAY ANALYSIS
# ═════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Delay Analysis")

d_col1, d_col2 = st.columns([2, 1])

# 2a – Daily delay rate trend (area chart + target line)
with d_col1:
    st.markdown("##### Daily Delay Rate (% orders > 45 min)")
    if COL_TOTAL in fdf.columns and "Date" in fdf.columns:
        daily = (
            fdf.groupby("Date")
               .apply(lambda g: pd.Series({
                   "total":   len(g),
                   "delayed": int((g[COL_TOTAL] > DELAY_THRESHOLD).sum()),
               }))
               .reset_index()
        )
        daily["delay_rate"] = daily["delayed"] / daily["total"] * 100
        daily["Date"] = pd.to_datetime(daily["Date"])
        daily = daily.sort_values("Date")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=daily["Date"], y=daily["delay_rate"],
            fill="tozeroy", fillcolor="rgba(255,107,107,0.20)",
            line=dict(color=DANGER, width=2),
            name="Delay Rate %",
            hovertemplate="%{x|%b %d}<br>Delay Rate: %{y:.1f}%<extra></extra>",
        ))
        fig.add_hline(
            y=TARGET_DELAY_RATE,
            line_dash="dash", line_color=WARNING, line_width=1.5,
            annotation_text=f"Target {TARGET_DELAY_RATE}%",
            annotation_font_color=WARNING,
        )
        fig.update_layout(
            template=TEMPLATE, height=320,
            margin=dict(t=10, b=10, l=0, r=0),
            yaxis_title="Delay Rate (%)", showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Date or total-time column not available.")

# 2b – Stacked bar: avg time per stage
with d_col2:
    st.markdown("##### Avg Time per Stage (min)")
    stage_map = {
        "Accept→Start":  COL_ACCEPT,
        "Start→Prep":    COL_PREP,
        "Prep→Dispatch": COL_PREDIS,
        "Dispatch":      COL_DISPATCH,
        "Delivery":      COL_DELIVER,
    }
    stage_vals = {
        label: safe_mean(fdf[col]) if col in fdf.columns else 0.0
        for label, col in stage_map.items()
    }
    stg_colors = [PRIMARY, SECONDARY, WARNING, DANGER, "#A29BFE"]
    fig2 = go.Figure()
    for i, (label, val) in enumerate(stage_vals.items()):
        fig2.add_trace(go.Bar(
            name=label, x=["All Orders"], y=[val],
            marker_color=stg_colors[i % len(stg_colors)],
            hovertemplate=f"{label}: %{{y:.1f}} min<extra></extra>",
        ))
    fig2.update_layout(
        template=TEMPLATE, barmode="stack", height=320,
        margin=dict(t=10, b=10, l=0, r=0),
        yaxis_title="Minutes",
        legend=dict(orientation="h", y=-0.30, font=dict(size=10)),
    )
    st.plotly_chart(fig2, use_container_width=True)

# 2c – Delay heatmap: Hour of Day vs Day of Week
st.markdown("##### Delay Rate Heatmap – Hour of Day vs Day of Week")
if COL_TOTAL in fdf.columns and "Received At" in fdf.columns:
    hmap_df = fdf.copy()
    hmap_df["Hour"]    = pd.to_datetime(hmap_df["Received At"], errors="coerce").dt.hour
    hmap_df["DayName"] = pd.to_datetime(hmap_df["Received At"], errors="coerce").dt.day_name()
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    pivot_raw = (
        hmap_df.groupby(["DayName", "Hour"])
               .apply(lambda g: (g[COL_TOTAL] > DELAY_THRESHOLD).mean() * 100)
               .reset_index(name="delay_rate")
    )
    pivot_raw["DayName"] = pd.Categorical(pivot_raw["DayName"], categories=day_order, ordered=True)
    pivot_raw = pivot_raw.sort_values("DayName")
    heat_pivot = pivot_raw.pivot(index="DayName", columns="Hour", values="delay_rate")

    fig3 = go.Figure(go.Heatmap(
        z=heat_pivot.values,
        x=[f"{h:02d}:00" for h in heat_pivot.columns],
        y=heat_pivot.index.tolist(),
        colorscale=[[0, "#1a1a2e"], [0.5, WARNING], [1, DANGER]],
        hovertemplate="Day: %{y}<br>Hour: %{x}<br>Delay Rate: %{z:.1f}%<extra></extra>",
        colorbar=dict(title="Delay %"),
    ))
    fig3.update_layout(
        template=TEMPLATE, height=300,
        margin=dict(t=10, b=10, l=0, r=0),
        xaxis_title="Hour of Day",
    )
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("Timestamp or total-time column not available for heatmap.")

# ═════════════════════════════════════════════════════════════════════════════
# 3 – KITCHEN PERFORMANCE
# ═════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Kitchen Performance")

kp1, kp2 = st.columns(2)

with kp1:
    st.markdown("##### Avg Prep Time by Location")
    if COL_PREP in fdf.columns and "Location" in fdf.columns:
        loc_prep = (
            fdf.groupby("Location")[COL_PREP].mean().dropna()
               .sort_values(ascending=True).reset_index()
        )
        loc_prep.columns = ["Location", "Avg Prep (min)"]
        fig4 = px.bar(
            loc_prep, x="Avg Prep (min)", y="Location", orientation="h",
            color="Avg Prep (min)",
            color_continuous_scale=[[0, SECONDARY], [1, DANGER]],
            template=TEMPLATE, height=max(300, len(loc_prep) * 22),
        )
        fig4.update_layout(margin=dict(t=10, b=10, l=0, r=0), coloraxis_showscale=False)
        fig4.update_traces(hovertemplate="%{y}: %{x:.1f} min<extra></extra>")
        st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info("Prep time or Location column not available.")

with kp2:
    st.markdown("##### Avg Prep Time by Brand")
    if COL_PREP in fdf.columns and "Brand" in fdf.columns:
        brand_prep = (
            fdf.groupby("Brand")[COL_PREP].mean().dropna()
               .sort_values(ascending=True).reset_index()
        )
        brand_prep.columns = ["Brand", "Avg Prep (min)"]
        fig5 = px.bar(
            brand_prep, x="Avg Prep (min)", y="Brand", orientation="h",
            color="Avg Prep (min)",
            color_continuous_scale=[[0, SECONDARY], [1, PRIMARY]],
            template=TEMPLATE, height=max(300, len(brand_prep) * 22),
        )
        fig5.update_layout(margin=dict(t=10, b=10, l=0, r=0), coloraxis_showscale=False)
        fig5.update_traces(hovertemplate="%{y}: %{x:.1f} min<extra></extra>")
        st.plotly_chart(fig5, use_container_width=True)
    else:
        st.info("Prep time or Brand column not available.")

kp3, kp4 = st.columns(2)

with kp3:
    st.markdown("##### Avg Prep Time by Station")
    if not fst.empty and "Station" in fst.columns and "Prep Time (min)" in fst.columns:
        station_perf = (
            fst.groupby("Station")["Prep Time (min)"].mean().dropna()
               .sort_values(ascending=True).reset_index()
        )
        station_perf.columns = ["Station", "Avg Prep (min)"]
        fig6 = px.bar(
            station_perf, x="Avg Prep (min)", y="Station", orientation="h",
            color="Avg Prep (min)",
            color_continuous_scale=[[0, SECONDARY], [1, WARNING]],
            template=TEMPLATE, height=max(300, len(station_perf) * 26),
        )
        fig6.update_layout(margin=dict(t=10, b=10, l=0, r=0), coloraxis_showscale=False)
        fig6.update_traces(hovertemplate="%{y}: %{x:.1f} min<extra></extra>")
        st.plotly_chart(fig6, use_container_width=True)
    else:
        st.info("Station data not available.")

with kp4:
    st.markdown("##### Prep Time Distribution")
    if COL_PREP in fdf.columns:
        prep_vals = fdf[COL_PREP].dropna()
        prep_vals = prep_vals[prep_vals <= prep_vals.quantile(0.99)]
        fig7 = px.histogram(
            prep_vals, nbins=50,
            color_discrete_sequence=[PRIMARY],
            template=TEMPLATE, height=320,
            labels={"value": "Prep Time (min)", "count": "Orders"},
        )
        fig7.update_layout(
            margin=dict(t=10, b=10, l=0, r=0),
            xaxis_title="Prep Time (min)", yaxis_title="# Orders", showlegend=False,
        )
        med = float(prep_vals.median())
        fig7.add_vline(
            x=med, line_dash="dash", line_color=SECONDARY,
            annotation_text=f"Median {med:.1f}m",
            annotation_font_color=SECONDARY,
        )
        st.plotly_chart(fig7, use_container_width=True)
    else:
        st.info("Prep time data not available.")

# ═════════════════════════════════════════════════════════════════════════════
# 4 – DELIVERY PERFORMANCE
# ═════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Delivery Performance")

dp1, dp2, dp3 = st.columns(3)

with dp1:
    st.markdown("##### Avg End-to-End Time by Channel")
    if COL_TOTAL in fdf.columns and "Channel" in fdf.columns:
        ch_time = (
            fdf.groupby("Channel")[COL_TOTAL].mean().dropna()
               .sort_values(ascending=False).reset_index()
        )
        ch_time.columns = ["Channel", "Avg Total (min)"]
        fig8 = px.bar(
            ch_time, x="Channel", y="Avg Total (min)",
            color="Avg Total (min)",
            color_continuous_scale=[[0, SECONDARY], [1, DANGER]],
            template=TEMPLATE, height=320,
        )
        fig8.add_hline(
            y=DELAY_THRESHOLD, line_dash="dash", line_color=WARNING,
            annotation_text=f"{DELAY_THRESHOLD}min target",
            annotation_font_color=WARNING,
        )
        fig8.update_layout(margin=dict(t=10, b=10, l=0, r=0), coloraxis_showscale=False)
        fig8.update_traces(hovertemplate="%{x}: %{y:.1f} min<extra></extra>")
        st.plotly_chart(fig8, use_container_width=True)
    else:
        st.info("Channel or total-time column not available.")

with dp2:
    st.markdown("##### Delivery Plan Breakdown")
    if "Delivery Plan" in fdf.columns:
        dp_counts = fdf["Delivery Plan"].value_counts().reset_index()
        dp_counts.columns = ["Delivery Plan", "Count"]
        fig9 = px.pie(
            dp_counts, names="Delivery Plan", values="Count", hole=0.45,
            color_discrete_sequence=[PRIMARY, SECONDARY, WARNING, DANGER, "#A29BFE"],
            template=TEMPLATE, height=320,
        )
        fig9.update_layout(margin=dict(t=10, b=10, l=0, r=0))
        fig9.update_traces(hovertemplate="%{label}: %{value:,} (%{percent})<extra></extra>")
        st.plotly_chart(fig9, use_container_width=True)
    else:
        st.info("Delivery Plan column not available.")

with dp3:
    st.markdown("##### Order Type Distribution")
    if "Order Type" in fdf.columns:
        ot_counts = fdf["Order Type"].value_counts().reset_index()
        ot_counts.columns = ["Order Type", "Count"]
        fig10 = px.pie(
            ot_counts, names="Order Type", values="Count", hole=0.45,
            color_discrete_sequence=[SECONDARY, PRIMARY, WARNING, DANGER, "#A29BFE"],
            template=TEMPLATE, height=320,
        )
        fig10.update_layout(margin=dict(t=10, b=10, l=0, r=0))
        fig10.update_traces(hovertemplate="%{label}: %{value:,} (%{percent})<extra></extra>")
        st.plotly_chart(fig10, use_container_width=True)
    else:
        st.info("Order Type column not available.")

# ═════════════════════════════════════════════════════════════════════════════
# 5 – OPERATIONAL FUNNEL (waterfall / stacked overlay)
# ═════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Operational Funnel – Avg Cumulative Time at Each Stage")

stage_labels = ["Accept→Start", "Start→Prep", "Prep→Dispatch", "Dispatch", "Delivery"]
stage_durations = [
    safe_mean(fdf[COL_ACCEPT])   if COL_ACCEPT   in fdf.columns else 0.0,
    safe_mean(fdf[COL_PREP])     if COL_PREP     in fdf.columns else 0.0,
    safe_mean(fdf[COL_PREDIS])   if COL_PREDIS   in fdf.columns else 0.0,
    safe_mean(fdf[COL_DISPATCH]) if COL_DISPATCH in fdf.columns else 0.0,
    safe_mean(fdf[COL_DELIVER])  if COL_DELIVER  in fdf.columns else 0.0,
]
cumulative      = list(np.cumsum([0.0] + stage_durations[:-1]))
total_pipeline  = sum(stage_durations)
funnel_colors   = [PRIMARY, SECONDARY, WARNING, DANGER, "#A29BFE"]

fig_funnel = go.Figure()
for i, (label, dur, base) in enumerate(zip(stage_labels, stage_durations, cumulative)):
    fig_funnel.add_trace(go.Bar(
        name=label, x=[label], y=[dur], base=[base],
        marker_color=funnel_colors[i],
        text=[f"{dur:.1f}m"], textposition="inside",
        hovertemplate=(
            f"<b>{label}</b><br>"
            f"Stage: {dur:.1f} min<br>"
            f"Cumulative: {base + dur:.1f} min<extra></extra>"
        ),
    ))
fig_funnel.add_hline(
    y=DELAY_THRESHOLD,
    line_dash="dash", line_color=WARNING, line_width=1.5,
    annotation_text=f"Delay Threshold {DELAY_THRESHOLD}min",
    annotation_font_color=WARNING,
)
fig_funnel.update_layout(
    template=TEMPLATE, barmode="overlay", height=380,
    margin=dict(t=40, b=10, l=0, r=0),
    yaxis_title="Cumulative Time (min)",
    showlegend=True,
    legend=dict(orientation="h", y=-0.15),
    title=dict(
        text=f"Total avg pipeline: <b>{total_pipeline:.1f} min</b>",
        x=0.5, font=dict(color=SECONDARY, size=14),
    ),
)
st.plotly_chart(fig_funnel, use_container_width=True)

# ═════════════════════════════════════════════════════════════════════════════
# 6 – POS SYNC HEALTH
# ═════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("POS Sync Health")

pos1, pos2 = st.columns([2, 1])

with pos1:
    st.markdown("##### Sync Success Rate by Location")
    needed = {"Location", "Sync Successful", "Total No of Orders", "Error"}
    if not df_pos.empty and needed.issubset(df_pos.columns):
        fig11 = go.Figure()
        fig11.add_trace(go.Bar(
            name="Sync Successful",
            x=df_pos["Location"], y=df_pos["Sync Successful"],
            marker_color=SECONDARY,
            hovertemplate="%{x}<br>Successful: %{y:,}<extra></extra>",
        ))
        fig11.add_trace(go.Bar(
            name="Errors",
            x=df_pos["Location"], y=df_pos["Error"],
            marker_color=DANGER,
            hovertemplate="%{x}<br>Errors: %{y:,}<extra></extra>",
        ))
        fig11.update_layout(
            template=TEMPLATE, barmode="stack", height=360,
            margin=dict(t=10, b=10, l=0, r=0),
            xaxis_tickangle=-45, yaxis_title="Orders",
            legend=dict(orientation="h", y=1.05),
        )
        st.plotly_chart(fig11, use_container_width=True)
    else:
        st.info("POS sync location data not available.")

with pos2:
    st.markdown("##### Total Errors by Brand")
    if not df_pos.empty and {"Brand", "Error"}.issubset(df_pos.columns):
        brand_err = (
            df_pos.groupby("Brand")["Error"].sum()
                  .sort_values(ascending=True).reset_index()
        )
        fig12 = px.bar(
            brand_err, x="Error", y="Brand", orientation="h",
            color="Error",
            color_continuous_scale=[[0, SECONDARY], [1, DANGER]],
            template=TEMPLATE, height=360,
            labels={"Error": "Total Errors"},
        )
        fig12.update_layout(margin=dict(t=10, b=10, l=0, r=0), coloraxis_showscale=False)
        fig12.update_traces(hovertemplate="%{y}: %{x:,} errors<extra></extra>")
        st.plotly_chart(fig12, use_container_width=True)
    else:
        st.info("POS Brand/Error data not available.")

# ═════════════════════════════════════════════════════════════════════════════
# 7 – TIME-BASED ANALYSIS
# ═════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Time-Based Analysis")

tb1, tb2 = st.columns(2)

# 7a – Order volume by hour of day (bar + delay rate overlay)
with tb1:
    st.markdown("##### Order Volume by Hour of Day")
    if "Received At" in fdf.columns:
        fdf_t = fdf.copy()
        fdf_t["Hour"] = pd.to_datetime(fdf_t["Received At"], errors="coerce").dt.hour
        hourly = fdf_t.groupby("Hour").size().reset_index(name="Orders")

        if COL_TOTAL in fdf_t.columns:
            hr_delay = (
                fdf_t.groupby("Hour")
                     .apply(lambda g: (g[COL_TOTAL] > DELAY_THRESHOLD).mean() * 100)
                     .reset_index(name="Delay Rate")
            )
            hourly = hourly.merge(hr_delay, on="Hour", how="left")
        else:
            hourly["Delay Rate"] = 0

        fig13 = go.Figure()
        fig13.add_trace(go.Bar(
            x=hourly["Hour"], y=hourly["Orders"],
            marker_color=PRIMARY, name="Orders",
            hovertemplate="Hour %{x}:00<br>Orders: %{y:,}<extra></extra>",
        ))
        fig13.add_trace(go.Scatter(
            x=hourly["Hour"], y=hourly["Delay Rate"],
            mode="lines+markers",
            line=dict(color=DANGER, width=2),
            yaxis="y2", name="Delay Rate %",
            hovertemplate="Hour %{x}:00<br>Delay Rate: %{y:.1f}%<extra></extra>",
        ))
        fig13.update_layout(
            template=TEMPLATE, height=350,
            margin=dict(t=10, b=10, l=0, r=0),
            xaxis=dict(title="Hour of Day", dtick=2),
            yaxis=dict(title="Orders"),
            yaxis2=dict(title="Delay Rate (%)", overlaying="y", side="right", showgrid=False),
            legend=dict(orientation="h", y=1.05),
        )
        st.plotly_chart(fig13, use_container_width=True)
    else:
        st.info("Received At timestamp not available.")

# 7b – Performance by day of week
with tb2:
    st.markdown("##### Performance by Day of Week")
    if "Received At" in fdf.columns:
        fdf_d = fdf.copy()
        fdf_d["DayName"] = pd.to_datetime(fdf_d["Received At"], errors="coerce").dt.day_name()
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        id_col = "Order ID" if "Order ID" in fdf_d.columns else fdf_d.columns[0]
        agg_dict = {"Orders": (id_col, "count")}
        if COL_TOTAL in fdf_d.columns: agg_dict["Avg Total (min)"] = (COL_TOTAL, "mean")
        if COL_PREP  in fdf_d.columns: agg_dict["Avg Prep (min)"]  = (COL_PREP,  "mean")

        day_grp = fdf_d.groupby("DayName").agg(**agg_dict).reset_index()
        day_grp["DayName"] = pd.Categorical(day_grp["DayName"], categories=day_order, ordered=True)
        day_grp = day_grp.sort_values("DayName")

        fig14 = go.Figure()
        fig14.add_trace(go.Bar(
            x=day_grp["DayName"], y=day_grp["Orders"],
            marker_color=PRIMARY, name="Orders",
            hovertemplate="%{x}<br>Orders: %{y:,}<extra></extra>",
        ))
        if "Avg Total (min)" in day_grp.columns:
            fig14.add_trace(go.Scatter(
                x=day_grp["DayName"], y=day_grp["Avg Total (min)"],
                mode="lines+markers", line=dict(color=SECONDARY, width=2),
                yaxis="y2", name="Avg Total (min)",
                hovertemplate="%{x}<br>Avg Total: %{y:.1f} min<extra></extra>",
            ))
        if "Avg Prep (min)" in day_grp.columns:
            fig14.add_trace(go.Scatter(
                x=day_grp["DayName"], y=day_grp["Avg Prep (min)"],
                mode="lines+markers", line=dict(color=WARNING, width=2, dash="dot"),
                yaxis="y2", name="Avg Prep (min)",
                hovertemplate="%{x}<br>Avg Prep: %{y:.1f} min<extra></extra>",
            ))
        fig14.update_layout(
            template=TEMPLATE, height=350,
            margin=dict(t=10, b=10, l=0, r=0),
            xaxis_title="Day of Week",
            yaxis=dict(title="Orders"),
            yaxis2=dict(title="Avg Time (min)", overlaying="y", side="right", showgrid=False),
            legend=dict(orientation="h", y=1.05),
        )
        st.plotly_chart(fig14, use_container_width=True)
    else:
        st.info("Received At timestamp not available.")

# ═════════════════════════════════════════════════════════════════════════════
# 8 – DETAILED OPERATIONS TABLE
# ═════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Detailed Operations Data")

display_cols = [c for c in [
    "Order ID", "Brand", "Location", "Channel", "Order Type", "Delivery Plan", "Date",
    COL_ACCEPT, COL_PREP, COL_PREDIS, COL_DISPATCH, COL_DELIVER, COL_TOTAL,
] if c in fdf.columns]

table_df = fdf[display_cols].copy()
if COL_TOTAL in table_df.columns:
    table_df["Delayed"] = table_df[COL_TOTAL] > DELAY_THRESHOLD

n_rows = st.slider(
    "Rows to display",
    min_value=50, max_value=min(5000, len(table_df)), value=200, step=50,
)

def highlight_delayed(row):
    color = "background-color: rgba(255,107,107,0.15)" if row.get("Delayed", False) else ""
    return [color] * len(row)

st.dataframe(
    table_df.head(n_rows).style.apply(highlight_delayed, axis=1),
    use_container_width=True, height=450,
)

n_total   = len(fdf)
n_delayed = int((fdf[COL_TOTAL] > DELAY_THRESHOLD).sum()) if COL_TOTAL in fdf.columns else 0
if n_total > 0:
    st.caption(
        f"Showing {min(n_rows, n_total):,} of {n_total:,} orders  ·  "
        f"{n_delayed:,} delayed ({n_delayed / n_total * 100:.1f}%)"
    )
