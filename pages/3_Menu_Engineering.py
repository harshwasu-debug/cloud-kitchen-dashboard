"""
Menu Engineering Analytics - BCG Matrix & Deep Menu Insights
Cloud Kitchen Dashboard | Grubtech Data
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

# ─── PAGE CONFIG ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Menu Engineering",
    page_icon="🍽️",
    layout="wide",
)

TEMPLATE = "plotly_white"
COLORS = {
    "Stars":       "#4ECDC4",
    "Puzzles":     "#FFE66D",
    "Plowhorses":  "#FF6B35",
    "Dogs":        "#FF6B6B",
}
ACCENT = "#4ECDC4"

# ─── CSS ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.6rem !important; }
section[data-testid="stSidebar"] { background: #F8F9FA; }
</style>
""", unsafe_allow_html=True)

# ─── LOAD DATA ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def get_menu_data():
    details   = load_menu_details()
    orders    = load_menu_orders()
    modifiers = load_menu_modifiers()
    tags      = load_menu_tags()
    return details, orders, modifiers, tags

with st.spinner("Loading menu data…"):
    df_details, df_orders, df_modifiers, df_tags = get_menu_data()

# ─── SIDEBAR FILTERS ────────────────────────────────────────────────────────
st.sidebar.title("🍽️ Menu Engineering")
st.sidebar.markdown("---")

all_brands = sorted(df_details["Brand"].dropna().unique().tolist()) if "Brand" in df_details.columns else []
sel_brands = st.sidebar.multiselect(
    "Brand",
    options=all_brands,
    default=all_brands,
    help="Filter by brand",
)

all_locs = sorted(df_details["Location"].dropna().unique().tolist()) if "Location" in df_details.columns else []
sel_locs = st.sidebar.multiselect(
    "Location",
    options=all_locs,
    default=all_locs,
    help="Filter by kitchen location",
)

all_channels_me = sorted(df_orders["Channel"].dropna().unique().tolist()) if "Channel" in df_orders.columns else []
sel_channels_me = st.sidebar.multiselect(
    "Channel",
    options=all_channels_me,
    default=all_channels_me,
    help="Filter by sales channel",
)

all_cuisines_me = sorted(df_orders["Cuisine"].dropna().unique().tolist()) if "Cuisine" in df_orders.columns else []
sel_cuisines_me = st.sidebar.multiselect(
    "Cuisine",
    options=all_cuisines_me,
    default=all_cuisines_me,
    help="Filter by cuisine type",
)

st.sidebar.markdown("---")
st.sidebar.markdown("**BCG Matrix Settings**")
bcg_metric = st.sidebar.radio(
    "Profitability Axis",
    ["Gross Sales", "Gross Sales per Unit"],
    index=0,
    help="Y-axis metric for the BCG matrix",
)
top_n_annotations = st.sidebar.slider("Top items to annotate per quadrant", 1, 5, 2)

st.sidebar.markdown("---")
st.sidebar.markdown("**Date Range**")
_dates_me = df_orders["Date"].dropna() if "Date" in df_orders.columns else pd.Series(dtype="datetime64[ns]")
_dates_me = pd.to_datetime(_dates_me, errors="coerce").dropna()
_min_me = _dates_me.min().date() if not _dates_me.empty else None
_max_me = _dates_me.max().date() if not _dates_me.empty else None
sel_start_me = sel_end_me = None
if _min_me and _max_me:
    _dr_me = st.sidebar.date_input("Period", value=(_min_me, _max_me), min_value=_min_me, max_value=_max_me, label_visibility="collapsed")
    sel_start_me, sel_end_me = (_dr_me[0], _dr_me[1]) if isinstance(_dr_me, (list, tuple)) and len(_dr_me) == 2 else (_min_me, _max_me)
st.sidebar.markdown("**Time Range**")
from datetime import time as _time
_tc1_me, _tc2_me = st.sidebar.columns(2)
with _tc1_me:
    sel_time_from_me = st.time_input("From", value=_time(0, 0), step=1800, key="tf_me")
with _tc2_me:
    sel_time_to_me = st.time_input("To", value=_time(23, 59), step=1800, key="tt_me")
st.sidebar.markdown("---")
st.sidebar.caption("Data: Grubtech + Deliverect")

# ─── APPLY FILTERS ──────────────────────────────────────────────────────────
def apply_filters(df, brand_col="Brand", loc_col="Location"):
    mask = pd.Series([True] * len(df), index=df.index)
    if sel_brands and brand_col in df.columns:
        mask &= df[brand_col].isin(sel_brands)
    if sel_locs and loc_col in df.columns:
        mask &= df[loc_col].isin(sel_locs)
    if sel_channels_me and "Channel" in df.columns:
        mask &= df["Channel"].isin(sel_channels_me)
    if sel_cuisines_me and "Cuisine" in df.columns:
        mask &= df["Cuisine"].isin(sel_cuisines_me)
    out = df[mask].copy()
    if sel_start_me and sel_end_me:
        from datetime import datetime as _dt
        _s = pd.Timestamp(_dt.combine(sel_start_me, sel_time_from_me))
        _e = pd.Timestamp(_dt.combine(sel_end_me, sel_time_to_me))
        if "Received At" in out.columns:
            out = out[(out["Received At"] >= _s) & (out["Received At"] <= _e)]
        elif "Date" in out.columns:
            out["_date"] = pd.to_datetime(out["Date"], errors="coerce").dt.date
            out = out[(out["_date"] >= sel_start_me) & (out["_date"] <= sel_end_me)]
            out = out.drop(columns=["_date"])
    return out

det  = apply_filters(df_details)
ord_ = apply_filters(df_orders)
mod  = apply_filters(df_modifiers)

# ─── AGGREGATE TO ITEM LEVEL ─────────────────────────────────────────────────
item_agg = (
    det.groupby("Menu Item", as_index=False)
    .agg(
        Item_Quantity=("Item Quantity", "sum"),
        Gross_Sales=("Gross Sales", "sum"),
        Discounts=("Discounts", "sum"),
    )
)
item_agg = item_agg[item_agg["Item_Quantity"] > 0].copy()
item_agg["Gross_Sales_Per_Unit"] = (
    item_agg["Gross_Sales"] / item_agg["Item_Quantity"].replace(0, np.nan)
)

total_qty = item_agg["Item_Quantity"].sum()
total_rev = item_agg["Gross_Sales"].sum()

item_agg["Popularity_Pct"] = item_agg["Item_Quantity"] / total_qty * 100
item_agg["Revenue_Pct"]    = item_agg["Gross_Sales"]   / total_rev * 100
item_agg["Discount_Rate"]  = (
    item_agg["Discounts"] / item_agg["Gross_Sales"].replace(0, np.nan) * 100
)

# ─── BCG CLASSIFICATION ──────────────────────────────────────────────────────
pop_median    = item_agg["Popularity_Pct"].median()
profit_col    = "Gross_Sales" if bcg_metric == "Gross Sales" else "Gross_Sales_Per_Unit"
profit_median = item_agg[profit_col].median()

def classify_bcg(row):
    hi_pop    = row["Popularity_Pct"] >= pop_median
    hi_profit = row[profit_col]       >= profit_median
    if hi_pop and hi_profit:
        return "Stars"
    elif not hi_pop and hi_profit:
        return "Puzzles"
    elif hi_pop and not hi_profit:
        return "Plowhorses"
    else:
        return "Dogs"

item_agg["Quadrant"] = item_agg.apply(classify_bcg, axis=1)

# ─── PAGE HEADER ─────────────────────────────────────────────────────────────
st.title("🍽️ Menu Engineering Analytics")
st.markdown(
    "BCG Matrix · Top/Bottom Analysis · Category & Modifier Intelligence · "
    "Price & Discount Insights"
)
st.markdown("---")

# ─── KPI ROW ─────────────────────────────────────────────────────────────────
if not item_agg.empty:
    top_qty_item = item_agg.loc[item_agg["Item_Quantity"].idxmax(), "Menu Item"]
    top_rev_item = item_agg.loc[item_agg["Gross_Sales"].idxmax(), "Menu Item"]
    avg_price_val = (
        item_agg["Gross_Sales"].sum() / item_agg["Item_Quantity"].sum()
        if item_agg["Item_Quantity"].sum() > 0 else 0
    )
else:
    top_qty_item = top_rev_item = "N/A"
    avg_price_val = 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Menu Items",     f"{len(item_agg):,}")
k2.metric("Total Items Sold",     f"{int(item_agg['Item_Quantity'].sum()):,}")
k3.metric("Avg Item Price",       f"AED {avg_price_val:,.2f}")
k4.metric("Top Selling Item",     (top_qty_item[:28] + "…") if len(top_qty_item) > 28 else top_qty_item)
k5.metric("Most Profitable Item", (top_rev_item[:28] + "…") if len(top_rev_item) > 28 else top_rev_item)

st.markdown("---")

# ════════════════════════════════════════════════════════════════════════════
# SECTION 1 – BCG MATRIX
# ════════════════════════════════════════════════════════════════════════════
st.header("📊 BCG Matrix – Menu Portfolio")

quad_counts = item_agg["Quadrant"].value_counts()
leg1, leg2, leg3, leg4, leg5 = st.columns(5)
for col, label, desc in [
    (leg1, "⭐ Stars",      "High pop · High profit"),
    (leg2, "🧩 Puzzles",    "Low pop · High profit"),
    (leg3, "🐴 Plowhorses", "High pop · Low profit"),
    (leg4, "🐶 Dogs",       "Low pop · Low profit"),
    (leg5, "Total Items",   ""),
]:
    q = label.split(" ", 1)[1] if label != "Total Items" else None
    col.metric(label, f"{quad_counts.get(q, 0):,}" if q else f"{len(item_agg):,}", desc)

st.markdown("")

if not item_agg.empty:
    plot_df = item_agg.copy()
    plot_df["Menu Item Short"] = plot_df["Menu Item"].str[:30]

    fig_bcg = go.Figure()

    for quad, color in COLORS.items():
        sub = plot_df[plot_df["Quadrant"] == quad]
        if sub.empty:
            continue
        max_sales = plot_df["Gross_Sales"].max()
        sizes = np.clip(
            np.sqrt(sub["Gross_Sales"] / (max_sales + 1e-9)) * 40, 5, 45
        )
        fig_bcg.add_trace(go.Scatter(
            x=sub["Popularity_Pct"],
            y=sub[profit_col],
            mode="markers",
            name=quad,
            marker=dict(
                color=color,
                size=sizes,
                opacity=0.82,
                line=dict(width=0.6, color="#111"),
            ),
            customdata=np.stack([
                sub["Menu Item"],
                sub["Item_Quantity"],
                sub["Gross_Sales"],
                sub["Gross_Sales_Per_Unit"].fillna(0),
                sub["Discounts"],
            ], axis=-1),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Popularity: %{x:.2f}% of sales mix<br>"
                "Gross Sales: AED %{customdata[2]:,.0f}<br>"
                "Per Unit: AED %{customdata[3]:,.2f}<br>"
                "Qty Sold: %{customdata[1]:,.0f}<br>"
                "Discounts: AED %{customdata[4]:,.0f}"
                "<extra></extra>"
            ),
        ))

    # Quadrant divider lines
    x_max = plot_df["Popularity_Pct"].quantile(0.98) * 1.15
    y_max = plot_df[profit_col].quantile(0.98) * 1.15
    line_style = dict(color="rgba(255,255,255,0.25)", width=1.5, dash="dash")

    fig_bcg.add_shape(type="line", x0=pop_median,    x1=pop_median,    y0=0, y1=y_max, line=line_style)
    fig_bcg.add_shape(type="line", x0=0,             x1=x_max,         y0=profit_median, y1=profit_median, line=line_style)

    # Quadrant background labels
    for qx, qy, qlabel, qcolor, qdesc in [
        (x_max * 0.75, y_max * 0.85, "⭐ STARS",      COLORS["Stars"],      "high pop · high profit"),
        (x_max * 0.05, y_max * 0.85, "🧩 PUZZLES",    COLORS["Puzzles"],    "low pop · high profit"),
        (x_max * 0.75, y_max * 0.10, "🐴 PLOWHORSES", COLORS["Plowhorses"], "high pop · low profit"),
        (x_max * 0.05, y_max * 0.10, "🐶 DOGS",       COLORS["Dogs"],       "low pop · low profit"),
    ]:
        fig_bcg.add_annotation(
            x=qx, y=qy,
            text=f"<b>{qlabel}</b><br><span style='font-size:10px'>{qdesc}</span>",
            showarrow=False,
            font=dict(size=12, color=qcolor),
            bgcolor="rgba(0,0,0,0.05)",
            bordercolor=qcolor,
            borderwidth=1,
            borderpad=5,
            opacity=0.9,
        )

    # Annotate top items per quadrant
    for quad, color in COLORS.items():
        sub = plot_df[plot_df["Quadrant"] == quad].nlargest(top_n_annotations, "Gross_Sales")
        for _, row in sub.iterrows():
            fig_bcg.add_annotation(
                x=row["Popularity_Pct"],
                y=row[profit_col],
                text=row["Menu Item Short"],
                showarrow=True,
                arrowhead=2,
                arrowsize=0.8,
                arrowcolor=color,
                arrowwidth=1,
                font=dict(size=9, color=color),
                bgcolor="rgba(0,0,0,0.05)",
                borderpad=3,
                ax=25, ay=-25,
            )

    y_axis_title = "Gross Sales (AED)" if bcg_metric == "Gross Sales" else "Gross Sales per Unit (AED)"
    fig_bcg.update_layout(
        template=TEMPLATE,
        height=640,
        title=dict(text="BCG Matrix — Menu Item Portfolio", font=dict(size=16)),
        xaxis=dict(
            title="Popularity (% of Sales Mix)",
            range=[0, x_max],
            gridcolor="rgba(255,255,255,0.06)",
        ),
        yaxis=dict(
            title=y_axis_title,
            range=[0, y_max],
            gridcolor="rgba(255,255,255,0.06)",
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
        margin=dict(l=60, r=20, t=70, b=60),
    )
    st.plotly_chart(fig_bcg, use_container_width=True)

    # Quadrant detail tables
    st.markdown("#### Quadrant Breakdown")
    q_tabs = st.tabs(["⭐ Stars", "🧩 Puzzles", "🐴 Plowhorses", "🐶 Dogs"])
    for tab, quad in zip(q_tabs, ["Stars", "Puzzles", "Plowhorses", "Dogs"]):
        with tab:
            qdf = (
                item_agg[item_agg["Quadrant"] == quad]
                .sort_values("Gross_Sales", ascending=False)
            )
            if qdf.empty:
                st.info("No items in this quadrant with current filters.")
            else:
                disp = qdf[[
                    "Menu Item", "Item_Quantity", "Gross_Sales",
                    "Gross_Sales_Per_Unit", "Popularity_Pct", "Revenue_Pct", "Discount_Rate"
                ]].copy().reset_index(drop=True)
                disp.columns = [
                    "Menu Item", "Qty Sold", "Gross Sales (AED)",
                    "Per Unit (AED)", "Popularity %", "Revenue %", "Discount Rate %"
                ]
                st.dataframe(
                    disp.style.format({
                        "Qty Sold": "{:,.0f}",
                        "Gross Sales (AED)": "{:,.2f}",
                        "Per Unit (AED)": "{:,.2f}",
                        "Popularity %": "{:.2f}%",
                        "Revenue %": "{:.2f}%",
                        "Discount Rate %": "{:.1f}%",
                    }),
                    use_container_width=True,
                    hide_index=True,
                    height=min(400, 55 + len(disp) * 35),
                )
else:
    st.warning("No item data available with current filters.")

st.markdown("---")

# ════════════════════════════════════════════════════════════════════════════
# SECTION 2 – TOP / BOTTOM ANALYSIS
# ════════════════════════════════════════════════════════════════════════════
st.header("📈 Top / Bottom Item Analysis")

tab_tq, tab_tr, tab_bot, tab_scat = st.tabs([
    "Top 20 by Quantity", "Top 20 by Revenue", "Bottom 20 (Removal Candidates)", "Revenue vs Qty"
])

with tab_tq:
    top_qty = item_agg.nlargest(20, "Item_Quantity").sort_values("Item_Quantity")
    fig = px.bar(
        top_qty, x="Item_Quantity", y="Menu Item",
        orientation="h",
        color="Item_Quantity", color_continuous_scale="Teal",
        title="Top 20 Items by Quantity Sold",
        labels={"Item_Quantity": "Units Sold", "Menu Item": ""},
        template=TEMPLATE,
    )
    fig.update_layout(height=600, coloraxis_showscale=False, margin=dict(l=10, r=20, t=50, b=40))
    st.plotly_chart(fig, use_container_width=True)

with tab_tr:
    top_rev = item_agg.nlargest(20, "Gross_Sales").sort_values("Gross_Sales")
    fig = px.bar(
        top_rev, x="Gross_Sales", y="Menu Item",
        orientation="h",
        color="Gross_Sales", color_continuous_scale="Teal",
        title="Top 20 Items by Gross Revenue (AED)",
        labels={"Gross_Sales": "Gross Sales (AED)", "Menu Item": ""},
        template=TEMPLATE,
    )
    fig.update_layout(height=600, coloraxis_showscale=False, margin=dict(l=10, r=20, t=50, b=40))
    st.plotly_chart(fig, use_container_width=True)

with tab_bot:
    bot_qty = item_agg.nsmallest(20, "Item_Quantity").sort_values("Item_Quantity", ascending=False)
    fig = px.bar(
        bot_qty, x="Item_Quantity", y="Menu Item",
        orientation="h",
        color="Item_Quantity", color_continuous_scale="Reds",
        title="Bottom 20 Items by Quantity — Removal Candidates",
        labels={"Item_Quantity": "Units Sold", "Menu Item": ""},
        template=TEMPLATE,
    )
    fig.update_layout(height=600, coloraxis_showscale=False, margin=dict(l=10, r=20, t=50, b=40))
    st.plotly_chart(fig, use_container_width=True)
    st.info(
        f"These {len(bot_qty)} items account for "
        f"{bot_qty['Item_Quantity'].sum():,.0f} units "
        f"({bot_qty['Item_Quantity'].sum() / total_qty * 100:.2f}% of total volume). "
        "Consider removing or repositioning them."
    )

with tab_scat:
    if not item_agg.empty:
        fig = px.scatter(
            item_agg,
            x="Item_Quantity",
            y="Gross_Sales",
            color="Quadrant",
            color_discrete_map=COLORS,
            size="Gross_Sales",
            size_max=35,
            hover_name="Menu Item",
            hover_data={
                "Item_Quantity": True,
                "Gross_Sales": ":.2f",
                "Gross_Sales_Per_Unit": ":.2f",
                "Quadrant": True,
            },
            title="Revenue vs Quantity — All Items",
            labels={"Item_Quantity": "Units Sold", "Gross_Sales": "Gross Sales (AED)"},
            template=TEMPLATE,
        )
        fig.update_layout(height=500, margin=dict(l=40, r=20, t=50, b=40))
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ════════════════════════════════════════════════════════════════════════════
# SECTION 3 – CATEGORY ANALYSIS
# ════════════════════════════════════════════════════════════════════════════
st.header("🏷️ Category Analysis")

cat_col = next((c for c in ["Category", "Tags"] if c in det.columns), None)

if cat_col:
    cat_agg = (
        det.groupby(cat_col, as_index=False)
        .agg(
            Total_Quantity=("Item Quantity", "sum"),
            Total_Sales=("Gross Sales", "sum"),
            Total_Discounts=("Discounts", "sum"),
            Item_Count=("Menu Item", "nunique"),
        )
        .sort_values("Total_Sales", ascending=False)
    )
    cat_agg = cat_agg[cat_agg["Total_Quantity"] > 0]

    if not cat_agg.empty:
        c1, c2 = st.columns(2)
        bar_height = max(400, len(cat_agg) * 28)

        with c1:
            fig = px.bar(
                cat_agg.sort_values("Total_Sales"),
                x="Total_Sales", y=cat_col,
                orientation="h",
                color="Total_Sales", color_continuous_scale="Teal",
                title=f"Sales by {cat_col} (AED)",
                labels={"Total_Sales": "Gross Sales (AED)", cat_col: ""},
                template=TEMPLATE,
            )
            fig.update_layout(height=bar_height, coloraxis_showscale=False,
                               margin=dict(l=10, r=20, t=50, b=40))
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            fig2 = px.bar(
                cat_agg.sort_values("Total_Quantity"),
                x="Total_Quantity", y=cat_col,
                orientation="h",
                color="Total_Quantity", color_continuous_scale="Tealgrn",
                title=f"Volume by {cat_col}",
                labels={"Total_Quantity": "Units Sold", cat_col: ""},
                template=TEMPLATE,
            )
            fig2.update_layout(height=bar_height, coloraxis_showscale=False,
                                margin=dict(l=10, r=20, t=50, b=40))
            st.plotly_chart(fig2, use_container_width=True)

        cat_agg["Avg Price (AED)"]   = cat_agg["Total_Sales"] / cat_agg["Total_Quantity"].replace(0, np.nan)
        cat_agg["Discount Rate %"]   = cat_agg["Total_Discounts"] / cat_agg["Total_Sales"].replace(0, np.nan) * 100
        st.dataframe(
            cat_agg.rename(columns={
                cat_col: "Category",
                "Total_Quantity": "Units Sold",
                "Total_Sales": "Gross Sales (AED)",
                "Total_Discounts": "Discounts (AED)",
                "Item_Count": "Unique Items",
            }).style.format({
                "Units Sold": "{:,.0f}",
                "Gross Sales (AED)": "{:,.2f}",
                "Discounts (AED)": "{:,.2f}",
                "Unique Items": "{:,.0f}",
                "Avg Price (AED)": "{:,.2f}",
                "Discount Rate %": "{:.1f}%",
            }),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No category data available after applying filters.")
else:
    st.info("Category column not found in menu details data.")

st.markdown("---")

# ════════════════════════════════════════════════════════════════════════════
# SECTION 4 – MODIFIER ANALYSIS
# ════════════════════════════════════════════════════════════════════════════
st.header("🔧 Modifier Analysis")

if not mod.empty and "Modifier" in mod.columns:
    mod_agg = (
        mod.groupby("Modifier", as_index=False)
        .agg(
            Total_Qty=("Total Quantity", "sum"),
            Gross_Sales=("Gross Sales", "sum"),
            Discount=("Discount", "sum"),
        )
        .sort_values("Total_Qty", ascending=False)
    )

    # Attach rate
    attach_top = pd.DataFrame()
    if "Menu Item" in mod.columns:
        parent_qty = mod.groupby("Menu Item")["Total Quantity"].sum().rename("Parent_Qty")
        mod_attach = mod.join(parent_qty, on="Menu Item")
        mod_attach["Attach_Rate"] = (
            mod_attach["Total Quantity"] / mod_attach["Parent_Qty"].replace(0, np.nan) * 100
        )
        attach_top = (
            mod_attach.groupby("Modifier", as_index=False)
            .agg(Avg_Attach_Rate=("Attach_Rate", "mean"))
            .sort_values("Avg_Attach_Rate", ascending=False)
        )

    tab_mq, tab_mr, tab_attach = st.tabs(["Top by Quantity", "Top by Revenue", "Attach Rate"])

    with tab_mq:
        top_mod_qty = mod_agg.nlargest(25, "Total_Qty").sort_values("Total_Qty")
        fig = px.bar(
            top_mod_qty, x="Total_Qty", y="Modifier",
            orientation="h",
            color="Total_Qty", color_continuous_scale="Teal",
            title="Top 25 Modifiers by Quantity",
            labels={"Total_Qty": "Total Quantity", "Modifier": ""},
            template=TEMPLATE,
        )
        fig.update_layout(height=650, coloraxis_showscale=False, margin=dict(l=10, r=20, t=50, b=40))
        st.plotly_chart(fig, use_container_width=True)

    with tab_mr:
        top_mod_rev = mod_agg.nlargest(25, "Gross_Sales").sort_values("Gross_Sales")
        fig = px.bar(
            top_mod_rev, x="Gross_Sales", y="Modifier",
            orientation="h",
            color="Gross_Sales", color_continuous_scale="Teal",
            title="Top 25 Modifiers by Revenue (AED)",
            labels={"Gross_Sales": "Gross Sales (AED)", "Modifier": ""},
            template=TEMPLATE,
        )
        fig.update_layout(height=650, coloraxis_showscale=False, margin=dict(l=10, r=20, t=50, b=40))
        st.plotly_chart(fig, use_container_width=True)

    with tab_attach:
        if not attach_top.empty:
            top_att = attach_top.nlargest(25, "Avg_Attach_Rate").sort_values("Avg_Attach_Rate")
            fig = px.bar(
                top_att, x="Avg_Attach_Rate", y="Modifier",
                orientation="h",
                color="Avg_Attach_Rate", color_continuous_scale="Oranges",
                title="Top 25 Modifiers by Attach Rate (Modifier Qty / Parent Item Qty %)",
                labels={"Avg_Attach_Rate": "Avg Attach Rate (%)", "Modifier": ""},
                template=TEMPLATE,
            )
            fig.update_layout(height=650, coloraxis_showscale=False, margin=dict(l=10, r=20, t=50, b=40))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Attach rate requires 'Menu Item' column in modifier data.")

    st.markdown(
        f"**Total Modifiers:** {len(mod_agg):,} &nbsp;|&nbsp; "
        f"**Total Modifier Revenue:** AED {mod_agg['Gross_Sales'].sum():,.2f} &nbsp;|&nbsp; "
        f"**Total Modifier Qty:** {int(mod_agg['Total_Qty'].sum()):,}"
    )
else:
    st.info("No modifier data available with current filters.")

st.markdown("---")

# ════════════════════════════════════════════════════════════════════════════
# SECTION 5 – PRICE ANALYSIS
# ════════════════════════════════════════════════════════════════════════════
st.header("💰 Price Analysis")

price_df = item_agg[item_agg["Gross_Sales_Per_Unit"] > 0].copy()

if not price_df.empty:
    tab_hist, tab_elast, tab_bp = st.tabs([
        "Price Distribution", "Price vs Volume (Elasticity)", "Avg Price by Brand"
    ])

    with tab_hist:
        p99 = price_df["Gross_Sales_Per_Unit"].quantile(0.99)
        hist_df = price_df[price_df["Gross_Sales_Per_Unit"] <= p99]
        fig = px.histogram(
            hist_df,
            x="Gross_Sales_Per_Unit",
            nbins=50,
            color_discrete_sequence=[ACCENT],
            title="Price Distribution — Gross Sales per Unit (AED)",
            labels={"Gross_Sales_Per_Unit": "Price (AED)"},
            template=TEMPLATE,
        )
        med_price = hist_df["Gross_Sales_Per_Unit"].median()
        fig.add_vline(
            x=med_price, line_dash="dash", line_color="#FFE66D",
            annotation_text=f"Median: AED {med_price:.2f}",
            annotation_position="top right",
        )
        fig.update_layout(height=420, margin=dict(l=40, r=20, t=50, b=40), bargap=0.05)
        st.plotly_chart(fig, use_container_width=True)

    with tab_elast:
        p99_qty = price_df["Item_Quantity"].quantile(0.99)
        elast_df = price_df[price_df["Item_Quantity"] <= p99_qty]
        fig = px.scatter(
            elast_df,
            x="Gross_Sales_Per_Unit",
            y="Item_Quantity",
            color="Quadrant",
            color_discrete_map=COLORS,
            size="Gross_Sales",
            size_max=30,
            hover_name="Menu Item",
            hover_data={"Gross_Sales_Per_Unit": ":.2f", "Item_Quantity": True},
                trendline="ols",
            trendline_color_override="#FFE66D",
            title="Price vs Volume — Elasticity Indicator",
            labels={"Gross_Sales_Per_Unit": "Unit Price (AED)", "Item_Quantity": "Units Sold"},
            template=TEMPLATE,
        )
        fig.update_layout(height=480, margin=dict(l=40, r=20, t=50, b=40))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "LOWESS trend line indicates the general price-volume relationship. "
            "A downward slope suggests price sensitivity."
        )

    with tab_bp:
        if "Brand" in det.columns:
            brand_price_rows = []
            for brand, grp in det.groupby("Brand"):
                total_s = grp["Gross Sales"].sum()
                total_q = grp["Item Quantity"].sum()
                brand_price_rows.append({
                    "Brand": brand,
                    "Avg_Price": total_s / total_q if total_q > 0 else 0,
                    "Total_Revenue": total_s,
                    "Total_Qty": total_q,
                    "Unique_Items": grp["Menu Item"].nunique(),
                })
            brand_price = pd.DataFrame(brand_price_rows).sort_values("Avg_Price", ascending=False)
            if sel_brands:
                brand_price = brand_price[brand_price["Brand"].isin(sel_brands)]

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=brand_price["Brand"],
                y=brand_price["Avg_Price"],
                name="Avg Price",
                marker_color=ACCENT,
                text=brand_price["Avg_Price"].map(lambda v: f"AED {v:.2f}"),
                textposition="outside",
            ))
            fig.update_layout(
                template=TEMPLATE, height=420,
                title="Average Item Price by Brand (AED)",
                xaxis_title="Brand", yaxis_title="Avg Price (AED)",
                margin=dict(l=40, r=20, t=50, b=100),
                xaxis_tickangle=-35,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Brand column not available for price-by-brand analysis.")
else:
    st.info("Insufficient price data for analysis.")

st.markdown("---")

# ════════════════════════════════════════════════════════════════════════════
# SECTION 6 – MENU TAG PERFORMANCE
# ════════════════════════════════════════════════════════════════════════════
st.header("🔖 Menu Tag Performance")

tag_df = df_tags.copy() if not df_tags.empty else pd.DataFrame()

if not tag_df.empty:
    tag_col = "Menu Item Tag" if "Menu Item Tag" in tag_df.columns else tag_df.columns[0]

    tag_agg = (
        tag_df.groupby(tag_col, as_index=False)
        .agg(**{k: (k, "sum") for k in ["Item Qty", "Total Sales", "Total Discounts", "VAT"]
                if k in tag_df.columns})
    )
    # Normalise column names if they came through
    rename_map = {
        "Item Qty": "Item_Qty",
        "Total Sales": "Total_Sales",
        "Total Discounts": "Total_Discounts",
        "VAT": "VAT",
    }
    tag_agg = tag_agg.rename(columns={k: v for k, v in rename_map.items() if k in tag_agg.columns})

    # Ensure required columns exist with defaults
    for col in ["Item_Qty", "Total_Sales", "Total_Discounts", "VAT"]:
        if col not in tag_agg.columns:
            tag_agg[col] = 0

    tag_agg = tag_agg[tag_agg["Item_Qty"] > 0].sort_values("Total_Sales", ascending=False)
    tag_agg["Discount_Rate_Pct"] = (
        tag_agg["Total_Discounts"] / tag_agg["Total_Sales"].replace(0, np.nan) * 100
    )
    tag_agg["Avg_Price"] = tag_agg["Total_Sales"] / tag_agg["Item_Qty"].replace(0, np.nan)

    t1, t2 = st.columns(2)
    with t1:
        top_tags = tag_agg.nlargest(20, "Total_Sales").sort_values("Total_Sales")
        fig = px.bar(
            top_tags, x="Total_Sales", y=tag_col,
            orientation="h",
            color="Total_Sales", color_continuous_scale="Teal",
            title="Top 20 Tags by Revenue (AED)",
            labels={"Total_Sales": "Total Sales (AED)", tag_col: ""},
            template=TEMPLATE,
        )
        fig.update_layout(height=560, coloraxis_showscale=False, margin=dict(l=10, r=20, t=50, b=40))
        st.plotly_chart(fig, use_container_width=True)

    with t2:
        top_disc_tags = (
            tag_agg[tag_agg["Discount_Rate_Pct"].notna()]
            .nlargest(20, "Discount_Rate_Pct")
            .sort_values("Discount_Rate_Pct")
        )
        fig2 = px.bar(
            top_disc_tags, x="Discount_Rate_Pct", y=tag_col,
            orientation="h",
            color="Discount_Rate_Pct", color_continuous_scale="Reds",
            title="Top 20 Tags by Discount Rate (%)",
            labels={"Discount_Rate_Pct": "Discount Rate (%)", tag_col: ""},
            template=TEMPLATE,
        )
        fig2.update_layout(height=560, coloraxis_showscale=False, margin=dict(l=10, r=20, t=50, b=40))
        st.plotly_chart(fig2, use_container_width=True)

    with st.expander("Full Tag Performance Table"):
        st.dataframe(
            tag_agg.rename(columns={
                tag_col: "Tag",
                "Item_Qty": "Units Sold",
                "Total_Sales": "Total Sales (AED)",
                "Total_Discounts": "Discounts (AED)",
                "VAT": "VAT (AED)",
                "Discount_Rate_Pct": "Discount Rate %",
                "Avg_Price": "Avg Price (AED)",
            }).style.format({
                "Units Sold": "{:,.0f}",
                "Total Sales (AED)": "{:,.2f}",
                "Discounts (AED)": "{:,.2f}",
                "VAT (AED)": "{:,.2f}",
                "Discount Rate %": "{:.1f}%",
                "Avg Price (AED)": "{:,.2f}",
            }),
            use_container_width=True,
            hide_index=True,
        )
else:
    st.info("Menu tag data not loaded.")

st.markdown("---")

# ════════════════════════════════════════════════════════════════════════════
# SECTION 7 – DISCOUNT IMPACT
# ════════════════════════════════════════════════════════════════════════════
st.header("🏷️ Discount Impact Analysis")

disc_df = item_agg[item_agg["Discounts"] > 0].copy().sort_values("Discounts", ascending=False)

if not disc_df.empty:
    tab_d1, tab_d2, tab_d3 = st.tabs([
        "Most Discounted Items", "Discount Rate by Item", "Discount Dependency"
    ])

    with tab_d1:
        top_disc = disc_df.nlargest(25, "Discounts").sort_values("Discounts")
        fig = px.bar(
            top_disc, x="Discounts", y="Menu Item",
            orientation="h",
            color="Discounts", color_continuous_scale="Reds",
            title="Top 25 Items by Total Discount Value (AED)",
            labels={"Discounts": "Total Discounts (AED)", "Menu Item": ""},
            template=TEMPLATE,
        )
        fig.update_layout(height=650, coloraxis_showscale=False, margin=dict(l=10, r=20, t=50, b=40))
        st.plotly_chart(fig, use_container_width=True)

    with tab_d2:
        rate_df = (
            disc_df[disc_df["Discount_Rate"].notna()]
            .nlargest(25, "Discount_Rate")
            .sort_values("Discount_Rate")
        )
        fig = px.bar(
            rate_df, x="Discount_Rate", y="Menu Item",
            orientation="h",
            color="Discount_Rate", color_continuous_scale="Oranges",
            title="Top 25 Items by Discount Rate (Discount / Gross Sales %)",
            labels={"Discount_Rate": "Discount Rate (%)", "Menu Item": ""},
            template=TEMPLATE,
        )
        med_rate = disc_df["Discount_Rate"].dropna().median()
        fig.add_vline(
            x=med_rate, line_dash="dash", line_color="#FFE66D",
            annotation_text=f"Median: {med_rate:.1f}%",
        )
        fig.update_layout(height=650, coloraxis_showscale=False, margin=dict(l=10, r=20, t=50, b=40))
        st.plotly_chart(fig, use_container_width=True)

    with tab_d3:
        fig = px.scatter(
            disc_df,
            x="Gross_Sales",
            y="Discounts",
            color="Discount_Rate",
            size="Item_Quantity",
            size_max=30,
            hover_name="Menu Item",
            hover_data={
                "Gross_Sales": ":.2f",
                "Discounts": ":.2f",
                "Discount_Rate": ":.1f",
                "Item_Quantity": True,
            },
            color_continuous_scale="Reds",
            title="Discount Dependency — Gross Sales vs Discount Amount",
            labels={
                "Gross_Sales": "Gross Sales (AED)",
                "Discounts": "Total Discounts (AED)",
                "Discount_Rate": "Discount Rate %",
            },
            template=TEMPLATE,
        )
        # 10% threshold reference line
        max_sales = disc_df["Gross_Sales"].max()
        fig.add_shape(
            type="line", x0=0, x1=max_sales, y0=0, y1=max_sales * 0.10,
            line=dict(color="#FFE66D", dash="dot", width=1.5),
        )
        fig.add_annotation(
            x=max_sales * 0.78, y=max_sales * 0.08,
            text="10% discount threshold",
            font=dict(color="#FFE66D", size=10),
            showarrow=False,
        )
        fig.update_layout(height=480, margin=dict(l=40, r=20, t=50, b=40))
        st.plotly_chart(fig, use_container_width=True)

        high_dep = disc_df[disc_df["Discount_Rate"] >= 20].sort_values("Discount_Rate", ascending=False)
        if not high_dep.empty:
            st.warning(
                f"**{len(high_dep)} items** have a discount rate ≥ 20% — "
                "these may be over-reliant on discounts to drive volume."
            )
            st.dataframe(
                high_dep[[
                    "Menu Item", "Item_Quantity", "Gross_Sales", "Discounts", "Discount_Rate"
                ]].rename(columns={
                    "Item_Quantity": "Qty Sold",
                    "Gross_Sales": "Gross Sales (AED)",
                    "Discounts": "Discounts (AED)",
                    "Discount_Rate": "Discount Rate %",
                }).style.format({
                    "Qty Sold": "{:,.0f}",
                    "Gross Sales (AED)": "{:,.2f}",
                    "Discounts (AED)": "{:,.2f}",
                    "Discount Rate %": "{:.1f}%",
                }),
                use_container_width=True,
                hide_index=True,
            )
else:
    st.info("No discount data found with current filters.")

st.markdown("---")

# ─── FOOTER ──────────────────────────────────────────────────────────────────
st.caption(
    "Menu Engineering Dashboard · Grubtech Cloud Kitchen · "
    "Data: March 2026 · "
    "BCG Matrix median thresholds are auto-calculated from the filtered dataset"
)
