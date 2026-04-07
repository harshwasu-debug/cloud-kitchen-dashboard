"""
AI Business Q&A — Cloud Kitchen Analytics Dashboard
Ask natural language questions about your business and get answers with
auto-generated visualisations. Powered by Claude (Anthropic API).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import json
import traceback

from utils.data_loader import (
    load_sales_orders,
    load_cancelled_orders,
    load_cpc_data,
    get_cuisine_for_brand,
    add_cuisine_column,
    get_all_cuisines,
    CUISINE_BRAND_MAP,
)

# ─── PAGE CONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="AI Business Q&A", page_icon="🤖", layout="wide")

# ─── THEME ───────────────────────────────────────────────────────────────────
PRIMARY   = "#FF6B35"
SECONDARY = "#4ECDC4"
ACCENT    = "#845EC2"
TEMPLATE  = "plotly_white"
PAPER_BG  = "white"
PLOT_BG   = "white"
PALETTE   = [PRIMARY, SECONDARY, ACCENT, "#F4A261", "#2A9D8F", "#457B9D",
             "#E63946", "#A8DADC", "#E9C46A", "#264653", "#6D6875", "#B5838D"]

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.qa-answer {
    background: #F8F9FA;
    border-radius: 10px;
    padding: 20px 24px;
    border-left: 4px solid #FF6B35;
    margin: 16px 0;
    color: #1A1A2E;
    font-size: 0.95rem;
    line-height: 1.6;
}
.qa-question {
    background: #EEF0F4;
    border-radius: 10px;
    padding: 14px 20px;
    margin: 8px 0;
    color: #333;
    font-weight: 600;
}
.example-chip {
    display: inline-block;
    background: #FFF3EE;
    border: 1px solid #FFD4BC;
    border-radius: 20px;
    padding: 6px 14px;
    margin: 4px;
    font-size: 0.82rem;
    color: #333;
    cursor: pointer;
}
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
</style>
""", unsafe_allow_html=True)


# ─── LOAD DATA ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def load_all_data():
    orders = load_sales_orders()
    cancelled = load_cancelled_orders()
    cpc = load_cpc_data()
    return orders, cancelled, cpc

orders_df, cancelled_df, cpc_df = load_all_data()

orders_df = add_cuisine_column(orders_df, "Brand")
cancelled_df = add_cuisine_column(cancelled_df, "Brand")
cpc_df = add_cuisine_column(cpc_df, "Brand")

# ─── SIDEBAR FILTERS ────────────────────────────────────────────────────────
st.sidebar.header("🤖 AI Q&A Filters")

df_work = orders_df.copy() if not orders_df.empty else pd.DataFrame()

all_brands = sorted(df_work["Brand"].dropna().unique().tolist()) if "Brand" in df_work.columns else []
sel_brands = st.sidebar.multiselect("Brand", all_brands, default=[], placeholder="All brands")

all_locations = sorted(df_work["Location"].dropna().unique().tolist()) if "Location" in df_work.columns else []
sel_locations = st.sidebar.multiselect("Location", all_locations, default=[], placeholder="All locations")

all_channels = sorted(df_work["Channel"].dropna().unique().tolist()) if "Channel" in df_work.columns else []
sel_channels = st.sidebar.multiselect("Channel", all_channels, default=[], placeholder="All channels")

all_cuisines = get_all_cuisines()
sel_cuisines = st.sidebar.multiselect("Cuisine", all_cuisines, default=[], placeholder="All cuisines")

st.sidebar.markdown("---")
st.sidebar.markdown("**Date Range**")
if "Received At" in df_work.columns and df_work["Received At"].notna().any():
    _min = df_work["Received At"].min().date()
    _max = df_work["Received At"].max().date()
    sel_dates = st.sidebar.date_input("Period", value=(_min, _max), min_value=_min, max_value=_max, label_visibility="collapsed")
    if isinstance(sel_dates, (list, tuple)) and len(sel_dates) == 2:
        start_date, end_date = sel_dates
    else:
        start_date, end_date = _min, _max
else:
    start_date = end_date = None

from datetime import time as _time
st.sidebar.markdown("**Time Range**")
_tc1, _tc2 = st.sidebar.columns(2)
with _tc1:
    sel_time_from = st.time_input("From", value=_time(0, 0), step=1800, key="tf_qa")
with _tc2:
    sel_time_to = st.time_input("To", value=_time(23, 59), step=1800, key="tt_qa")

# ─── APPLY FILTERS ──────────────────────────────────────────────────────────
def apply_filters(df):
    if df.empty:
        return df
    out = df.copy()
    if sel_brands and "Brand" in out.columns:
        out = out[out["Brand"].isin(sel_brands)]
    if sel_locations and "Location" in out.columns:
        out = out[out["Location"].isin(sel_locations)]
    if sel_channels and "Channel" in out.columns:
        out = out[out["Channel"].isin(sel_channels)]
    if sel_cuisines and "Cuisine" in out.columns:
        out = out[out["Cuisine"].isin(sel_cuisines)]
    if start_date and end_date and "Received At" in out.columns:
        from datetime import datetime as _dt
        _s = pd.Timestamp(_dt.combine(start_date, sel_time_from))
        _e = pd.Timestamp(_dt.combine(end_date, sel_time_to))
        out = out[(out["Received At"] >= _s) & (out["Received At"] <= _e)]
    return out

filtered_orders = apply_filters(orders_df)
filtered_cancelled = apply_filters(cancelled_df)
filtered_cpc = apply_filters(cpc_df)


# ─── DATA SUMMARY FOR CLAUDE ────────────────────────────────────────────────
def build_data_context(orders, cancelled, cpc):
    """Build a compact summary of the business data for Claude."""
    ctx = []

    if not orders.empty:
        revenue_col = "Gross Price" if "Gross Price" in orders.columns else "Total(Receipt Total)"
        total_revenue = orders[revenue_col].sum() if revenue_col in orders.columns else 0
        total_orders = len(orders)
        avg_aov = total_revenue / total_orders if total_orders > 0 else 0

        # Brand summary
        if "Brand" in orders.columns and revenue_col in orders.columns:
            brand_stats = orders.groupby("Brand").agg(
                revenue=(revenue_col, "sum"),
                orders=(revenue_col, "count"),
            ).reset_index()
            brand_stats["aov"] = brand_stats["revenue"] / brand_stats["orders"]
            brand_stats = brand_stats.sort_values("revenue", ascending=False)
            brand_summary = brand_stats.head(20).to_string(index=False, float_format="%.2f")
        else:
            brand_summary = "No brand data"

        # Channel summary
        if "Channel" in orders.columns and revenue_col in orders.columns:
            chan_stats = orders.groupby("Channel").agg(
                revenue=(revenue_col, "sum"),
                orders=(revenue_col, "count"),
            ).reset_index().sort_values("revenue", ascending=False)
            channel_summary = chan_stats.to_string(index=False, float_format="%.2f")
        else:
            channel_summary = "No channel data"

        # Cuisine summary
        if "Cuisine" in orders.columns and revenue_col in orders.columns:
            cuisine_stats = orders.groupby("Cuisine").agg(
                revenue=(revenue_col, "sum"),
                orders=(revenue_col, "count"),
            ).reset_index().sort_values("revenue", ascending=False)
            cuisine_summary = cuisine_stats.to_string(index=False, float_format="%.2f")
        else:
            cuisine_summary = "No cuisine data"

        # Location summary
        if "Location" in orders.columns:
            loc_stats = orders.groupby("Location").agg(
                orders=(revenue_col, "count"),
                revenue=(revenue_col, "sum"),
            ).reset_index().sort_values("revenue", ascending=False).head(10)
            location_summary = loc_stats.to_string(index=False, float_format="%.2f")
        else:
            location_summary = "No location data"

        # Date range
        if "Received At" in orders.columns:
            date_range = f"{orders['Received At'].min().strftime('%Y-%m-%d')} to {orders['Received At'].max().strftime('%Y-%m-%d')}"
        else:
            date_range = "Unknown"

        # Daily trends (last 14 days)
        if "Date" in orders.columns and revenue_col in orders.columns:
            daily = orders.groupby("Date").agg(
                revenue=(revenue_col, "sum"),
                orders=(revenue_col, "count"),
            ).reset_index().sort_values("Date").tail(14)
            daily_summary = daily.to_string(index=False, float_format="%.2f")
        else:
            daily_summary = "No daily data"

        ctx.append(f"""=== SALES ORDERS DATA ===
Date range: {date_range}
Total orders: {total_orders:,}
Total revenue: AED {total_revenue:,.2f}
Average order value: AED {avg_aov:,.2f}

Brand performance (top 20):
{brand_summary}

Channel performance:
{channel_summary}

Cuisine performance:
{cuisine_summary}

Top 10 locations:
{location_summary}

Daily trends (last 14 days):
{daily_summary}""")

    if not cancelled.empty:
        ctx.append(f"""=== CANCELLED ORDERS ===
Total cancelled: {len(cancelled):,}
""")

    if not cpc.empty:
        cpc_spend = cpc["netbasket_amount"].sum() if "netbasket_amount" in cpc.columns else 0
        cpc_gmv = cpc["gmv_local"].sum() if "gmv_local" in cpc.columns else 0
        cpc_roas = cpc_gmv / cpc_spend if cpc_spend > 0 else 0
        agg_summary = ""
        if "Aggregator" in cpc.columns:
            for agg in cpc["Aggregator"].unique():
                a = cpc[cpc["Aggregator"] == agg]
                sp = a["netbasket_amount"].sum()
                gm = a["gmv_local"].sum()
                r = gm/sp if sp > 0 else 0
                agg_summary += f"  {agg}: Spend AED {sp:,.0f}, GMV AED {gm:,.0f}, ROAS {r:.2f}x, {a['orders'].sum():,.0f} orders\n"

        ctx.append(f"""=== CPC ADVERTISING DATA ===
Total ad spend: AED {cpc_spend:,.2f}
Total ad GMV: AED {cpc_gmv:,.2f}
Overall ROAS: {cpc_roas:.2f}x
Platform breakdown:
{agg_summary}""")

    return "\n\n".join(ctx)


# ─── CHART BUILDER ──────────────────────────────────────────────────────────
def render_chart(chart_spec, orders, cpc):
    """Render a chart from Claude's JSON spec."""
    try:
        chart_type = chart_spec.get("type", "bar")
        title = chart_spec.get("title", "")
        x_col = chart_spec.get("x")
        y_col = chart_spec.get("y")
        color_col = chart_spec.get("color")
        data_source = chart_spec.get("data_source", "orders")
        agg_func = chart_spec.get("aggregation", "sum")
        orientation = chart_spec.get("orientation", "v")
        top_n = chart_spec.get("top_n")

        # Select data source
        if data_source == "cpc" and not cpc.empty:
            src = cpc
        else:
            src = orders

        if src.empty or not x_col or not y_col:
            return None

        # Check columns exist
        if x_col not in src.columns or y_col not in src.columns:
            return None

        # Aggregate
        if color_col and color_col in src.columns:
            plot_df = src.groupby([x_col, color_col])[y_col].agg(agg_func).reset_index()
        else:
            plot_df = src.groupby(x_col)[y_col].agg(agg_func).reset_index()

        if top_n:
            plot_df = plot_df.nlargest(top_n, y_col)

        # Sort
        plot_df = plot_df.sort_values(y_col, ascending=(orientation == "h"))

        # Build chart
        if chart_type == "bar":
            fig = px.bar(plot_df, x=x_col if orientation == "v" else y_col,
                         y=y_col if orientation == "v" else x_col,
                         color=color_col, orientation=orientation,
                         color_discrete_sequence=PALETTE, template=TEMPLATE,
                         title=title)
        elif chart_type == "line":
            fig = px.line(plot_df, x=x_col, y=y_col, color=color_col,
                          color_discrete_sequence=PALETTE, markers=True,
                          template=TEMPLATE, title=title)
        elif chart_type == "pie":
            fig = px.pie(plot_df, names=x_col, values=y_col,
                         color_discrete_sequence=PALETTE, template=TEMPLATE,
                         title=title, hole=0.4)
        elif chart_type == "scatter":
            size_col = chart_spec.get("size")
            fig = px.scatter(plot_df, x=x_col, y=y_col, color=color_col,
                             size=size_col if size_col and size_col in plot_df.columns else None,
                             color_discrete_sequence=PALETTE, template=TEMPLATE,
                             title=title, hover_name=x_col if x_col != y_col else None)
        elif chart_type == "treemap":
            fig = px.treemap(plot_df, path=[x_col], values=y_col,
                             color_discrete_sequence=PALETTE, template=TEMPLATE,
                             title=title)
        else:
            fig = px.bar(plot_df, x=x_col, y=y_col, template=TEMPLATE, title=title,
                         color_discrete_sequence=PALETTE)

        fig.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
                          height=420, margin=dict(l=10, r=10, t=50, b=40))
        return fig
    except Exception:
        return None


# ─── CALL CLAUDE ─────────────────────────────────────────────────────────────
def ask_claude(question: str, data_context: str) -> dict:
    """Send question + data context to Claude, get answer + optional chart spec."""
    try:
        import anthropic
    except ImportError:
        return {"answer": "The `anthropic` package is not installed. Please add it to requirements.txt and redeploy.", "chart": None}

    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {
            "answer": "No API key found. Please add `ANTHROPIC_API_KEY` to your Streamlit secrets (`.streamlit/secrets.toml` or Streamlit Cloud settings).",
            "chart": None,
        }

    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = f"""You are a cloud kitchen business analyst for ZwQ, a food & beverage holding company operating 35 brands across 9 cuisines in Dubai, UAE. All amounts are in AED (UAE Dirhams).

You answer business questions concisely based on the data provided. Always:
- Give specific numbers (revenue, orders, percentages)
- Compare and rank when relevant
- Highlight actionable insights
- Be concise (2-5 sentences for simple questions, more for complex analysis)

When a visual would help, include a JSON chart specification in your response inside <chart> tags. The chart spec should be valid JSON with these fields:
- type: "bar", "line", "pie", "scatter", or "treemap"
- title: chart title string
- x: column name for x-axis
- y: column name for y-axis (numeric column to aggregate)
- color: (optional) column to color by
- aggregation: "sum", "mean", "count", or "nunique"
- orientation: "v" (vertical) or "h" (horizontal)
- top_n: (optional) number of top items to show
- data_source: "orders" or "cpc"

Available columns in orders data: Brand, Location, Channel, Cuisine, Date, Month, Week, Day, Hour, Gross Price, Order ID, Received At
Available columns in CPC data: Aggregator, Ad Product, Brand, Cuisine, netbasket_amount, gmv_local, ROAS, clicks, orders, impressions, CPC, CPO

Here is the current business data (filtered by user's sidebar selections):

{data_context}"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": question}],
        )
        response_text = message.content[0].text

        # Extract chart spec if present
        chart_spec = None
        if "<chart>" in response_text and "</chart>" in response_text:
            chart_json = response_text.split("<chart>")[1].split("</chart>")[0].strip()
            try:
                chart_spec = json.loads(chart_json)
            except json.JSONDecodeError:
                pass
            # Remove chart tags from answer text
            answer = response_text.split("<chart>")[0].strip()
            remainder = response_text.split("</chart>")
            if len(remainder) > 1:
                answer += " " + remainder[1].strip()
        else:
            answer = response_text

        return {"answer": answer.strip(), "chart": chart_spec}
    except Exception as e:
        return {"answer": f"Error calling Claude API: {str(e)}", "chart": None}


# ─── PAGE CONTENT ────────────────────────────────────────────────────────────
st.title("🤖 AI Business Q&A")
st.caption("Ask questions about your cloud kitchen business. Powered by Claude.")

# Example questions
st.markdown("**Try asking:**")
examples = [
    "Which brand has the highest revenue?",
    "Compare Talabat vs Careem CPC performance",
    "What's our top cuisine by order volume?",
    "Show me revenue trend by month",
    "Which location has the most orders?",
    "What's the average order value by channel?",
    "Which brands have ROAS above 3x?",
    "Show cancellation rate by brand",
]
example_html = " ".join([f'<span class="example-chip">{ex}</span>' for ex in examples])
st.markdown(f'<div style="margin-bottom:16px">{example_html}</div>', unsafe_allow_html=True)

# Chat input
question = st.chat_input("Ask a question about your business...")

# Session state for history
if "qa_history" not in st.session_state:
    st.session_state.qa_history = []

if question:
    # Build data context from filtered data
    data_ctx = build_data_context(filtered_orders, filtered_cancelled, filtered_cpc)

    # Show user question
    st.session_state.qa_history.append({"role": "user", "content": question})

    # Get Claude's answer
    with st.spinner("Analysing your data..."):
        result = ask_claude(question, data_ctx)

    st.session_state.qa_history.append({
        "role": "assistant",
        "content": result["answer"],
        "chart": result.get("chart"),
    })

# Display chat history
for msg in st.session_state.qa_history:
    if msg["role"] == "user":
        st.markdown(f'<div class="qa-question">🧑 {msg["content"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="qa-answer">🤖 {msg["content"]}</div>', unsafe_allow_html=True)
        if msg.get("chart"):
            fig = render_chart(msg["chart"], filtered_orders, filtered_cpc)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

# Show data summary for transparency
with st.expander("📊 Data Context (what the AI sees)"):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Orders", f"{len(filtered_orders):,}")
    with c2:
        rev_col = "Gross Price" if "Gross Price" in filtered_orders.columns else "Total(Receipt Total)"
        total_rev = filtered_orders[rev_col].sum() if rev_col in filtered_orders.columns else 0
        st.metric("Revenue", f"AED {total_rev:,.0f}")
    with c3:
        st.metric("CPC Records", f"{len(filtered_cpc):,}")

    if not filtered_orders.empty:
        st.markdown("**Active Filters:**")
        active = []
        if sel_brands: active.append(f"Brands: {', '.join(sel_brands)}")
        if sel_locations: active.append(f"Locations: {', '.join(sel_locations)}")
        if sel_channels: active.append(f"Channels: {', '.join(sel_channels)}")
        if sel_cuisines: active.append(f"Cuisines: {', '.join(sel_cuisines)}")
        if start_date: active.append(f"Date: {start_date} to {end_date}")
        st.markdown(" | ".join(active) if active else "None (showing all data)")
