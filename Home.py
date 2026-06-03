"""
Cloud Kitchen Command Center — Home.

Lean executive overview. Three Performance pages live in the sidebar:
Today / This Week / This Month. This Home page shows headline numbers
across all three time scales and points at where to drill in.
"""
import calendar
import sys
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from utils.performance_data import (
    DAY_INFLECTION_NET,
    DAY_INFLECTION_ORDERS,
    DAY_NET_TIERS,
    DAY_ORDERS_TIERS,
    MONTH_NET_TIERS,
    MONTH_ORDERS_TIERS,
    WEEK_NET_TIERS,
    WEEK_ORDERS_TIERS,
    data_freshness,
    day_fraction,
    delta_pct,
    fmt_aed,
    fmt_int,
    fmt_pct,
    latest_date,
    latest_order_time_today,
    load_orders,
    now_dubai,
    project_eod_additive,
    project_period_end,
    same_weekday_history,
    should_project,
    signed_pct,
    slice_range,
    total_kpis,
    verdict_for,
)


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Cloud Kitchen Command Center",
    page_icon="🍕",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Keep the orange / pizza identity for now (per owner: defer aesthetics)
PRIMARY = "#FF6B35"

st.markdown("""
<style>
.stApp { background-color: #FFFFFF; }
[data-testid="metric-container"] {
    background: linear-gradient(135deg, #F8F9FA 0%, #EEF0F4 100%);
    border: 1px solid #DEE2E6; border-radius: 12px; padding: 16px 20px;
}
[data-testid="metric-container"] label {
    color: #6C757D !important; font-size: 0.78rem !important;
    font-weight: 600 !important; text-transform: uppercase;
    letter-spacing: 0.06em;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #1A1A2E !important; font-size: 1.65rem !important; font-weight: 700 !important;
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(f"# 🍕 Cloud Kitchen Command Center")
st.caption("Performance overview. Drill into Today / This Week / This Month for the detail.")


# ---------------------------------------------------------------------------
# Data load + freshness
# ---------------------------------------------------------------------------
df = load_orders()
if df.empty:
    st.error(
        "No order data available. The `Combined_Orders_clean.jsonl` master "
        "wasn't found at any expected path."
    )
    st.stop()

fresh = data_freshness()
latest = latest_date(df)
days_stale = (date.today() - latest).days
if days_stale > 0:
    st.info(
        f"📅 Latest data is from **{latest.strftime('%a, %d %b %Y')}** "
        f"({days_stale} day{'s' if days_stale != 1 else ''} ago). "
        f"Re-run the data builder to refresh."
    )


# ---------------------------------------------------------------------------
# Three blocks — Today / Week / Month. Tier = projected end-of-period.
# ---------------------------------------------------------------------------
today_dubai = now_dubai().date()
in_progress = (latest == today_dubai)  # Are we looking at a live partial day?


def render_block(label: str, icon: str, actual_kpis: dict, projected_kpis: dict,
                 ord_tiers, net_tiers, page_link: str, sub_caption: str = "",
                 show_projection: bool = False):
    """Render one summary block. Tier badge based on projection if applicable."""
    v_net = verdict_for(projected_kpis["net"], net_tiers)
    v_ord = verdict_for(projected_kpis["orders"], ord_tiers)
    st.markdown(f"#### {icon} {label}")
    if sub_caption:
        st.caption(sub_caption)

    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        if show_projection:
            st.metric("Projected Net Sales", fmt_aed(projected_kpis["net"]),
                      delta=f"actual so far: {fmt_aed(actual_kpis['net'])}",
                      delta_color="off")
        else:
            st.metric("Net Sales", fmt_aed(actual_kpis["net"]))
        st.markdown(f"**{v_net.emoji} {v_net.tier}**")
    with cc2:
        if show_projection:
            st.metric("Projected Orders", fmt_int(projected_kpis["orders"]),
                      delta=f"actual so far: {fmt_int(actual_kpis['orders'])}",
                      delta_color="off")
        else:
            st.metric("Orders", fmt_int(actual_kpis["orders"]))
        st.markdown(f"**{v_ord.emoji} {v_ord.tier}**")
    with cc3:
        st.metric("Discount", fmt_pct(actual_kpis["discount_rate"]))
        st.markdown(f"AOV (net) **{fmt_aed(actual_kpis['aov_net'])}**")

    st.page_link(page_link, label=f"Open {label} →", icon=icon)
    st.markdown("---")


# ---------------------------------------------------------------------------
# Today
# ---------------------------------------------------------------------------
today_slice = slice_range(df, latest, latest)
today_k = total_kpis(today_slice)

# Compute projection if today is live partial day
if in_progress:
    # Get last 4 same-weekday history for typical full-day
    hist_dates = same_weekday_history(df, latest, n=4)
    if hist_dates:
        hist_slice = df[df["biz_date"].isin(hist_dates)]
        hist_total = total_kpis(hist_slice)
        n = len(hist_dates)
        typical_day = {
            "orders": hist_total["orders"] / n,
            "net": hist_total["net"] / n,
            "gross": hist_total["gross"] / n,
            "discount": hist_total["discount"] / n,
        }
        latest_t = latest_order_time_today(df, latest)
        frac = day_fraction(latest_t) if latest_t else day_fraction(now_dubai())
        today_projected = project_eod_additive(today_k, typical_day, frac)
        today_sub = (
            f"⏱️ At ~{frac * 100:.0f}% of the business day "
            f"(03:00 → 03:00). Projected to end-of-day, then tiered."
        )
        today_show_proj = frac < 0.95
    else:
        today_projected = today_k
        today_sub = "No same-weekday history yet — showing actual."
        today_show_proj = False
else:
    today_projected = today_k
    today_sub = f"Full day actuals from {latest.strftime('%a %d %b')}."
    today_show_proj = False

render_block(
    f"Today — {latest.strftime('%a %d %b')}",
    "📍",
    today_k,
    today_projected,
    DAY_ORDERS_TIERS,
    DAY_NET_TIERS,
    "pages/00_Today.py",
    today_sub,
    today_show_proj,
)


# ---------------------------------------------------------------------------
# This Week — WTD + projection
# ---------------------------------------------------------------------------
monday = latest - timedelta(days=latest.weekday())
days_into_week = (latest - monday).days + 1
week_slice = slice_range(df, monday, latest)
week_k = total_kpis(week_slice)

# Average daily from prior 4 full weeks
prior_full_weeks = []
for i in range(1, 5):
    s = monday - timedelta(days=7 * i)
    e = s + timedelta(days=6)
    if s >= df["biz_date"].min():
        prior_full_weeks.append(total_kpis(slice_range(df, s, e)))
if prior_full_weeks:
    typical_day_week = {
        k: sum(w[k] for w in prior_full_weeks) / (len(prior_full_weeks) * 7)
        for k in ("orders", "net", "gross", "discount")
    }
else:
    typical_day_week = {"orders": 0, "net": 0, "gross": 0, "discount": 0}

if in_progress:
    latest_t = latest_order_time_today(df, latest)
    frac = day_fraction(latest_t) if latest_t else day_fraction(now_dubai())
    eff_days = (days_into_week - 1) + frac
else:
    eff_days = float(days_into_week)
week_projected = project_period_end(week_k, eff_days, 7, typical_day_week)

week_sub = (
    f"Mon **{monday.strftime('%d %b')}** → Sun "
    f"**{(monday + timedelta(days=6)).strftime('%d %b')}** "
    f"(through {latest.strftime('%a %d %b')})"
)
render_block(
    f"This Week — {days_into_week} of 7 days",
    "📆",
    week_k,
    week_projected,
    WEEK_ORDERS_TIERS,
    WEEK_NET_TIERS,
    "pages/01_This_Week.py",
    week_sub,
    show_projection=(days_into_week < 7),
)


# ---------------------------------------------------------------------------
# This Month — MTD + projection
# ---------------------------------------------------------------------------
month_start = latest.replace(day=1)
days_in_month = calendar.monthrange(latest.year, latest.month)[1]
days_so_far = (latest - month_start).days + 1
month_slice = slice_range(df, month_start, latest)
month_k = total_kpis(month_slice)

# Typical daily from last month
prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
prev_days = calendar.monthrange(prev_month_start.year, prev_month_start.month)[1]
prev_month_end = prev_month_start.replace(day=prev_days)
prev_month_full = total_kpis(slice_range(df, prev_month_start, prev_month_end))
typical_day_month = {
    k: prev_month_full[k] / prev_days if prev_days else 0
    for k in ("orders", "net", "gross", "discount")
}

if in_progress:
    latest_t = latest_order_time_today(df, latest)
    frac = day_fraction(latest_t) if latest_t else day_fraction(now_dubai())
    eff_days_m = (days_so_far - 1) + frac
else:
    eff_days_m = float(days_so_far)
month_projected = project_period_end(month_k, eff_days_m, days_in_month, typical_day_month)

month_sub = (
    f"{month_start.strftime('%d %b')} → {month_start.replace(day=days_in_month).strftime('%d %b %Y')} "
    f"(through {latest.strftime('%a %d %b')})"
)
render_block(
    f"This Month — {days_so_far} of {days_in_month} days",
    "🗓️",
    month_k,
    month_projected,
    MONTH_ORDERS_TIERS,
    MONTH_NET_TIERS,
    "pages/02_This_Month.py",
    month_sub,
    show_projection=(days_so_far < days_in_month),
)


# ---------------------------------------------------------------------------
# Footer — data range + tier legend
# ---------------------------------------------------------------------------
with st.expander("How tiers are scored"):
    st.markdown(f"""
**Day tiers** — based on owner-set calibration (the profitability inflection
is roughly 185 orders / AED 10,000 net):

| Tier | Orders | Net Sales |
|---|---|---|
| 🟢🟢 Exceptional | 215+ | AED 11,800+ |
| 🟢 Good | 200–215 | AED 11,000–11,800 |
| 🟡 On-trend | 180–200 | AED 9,900–11,000 |
| 🟠 Soft | 160–180 | AED 8,800–9,900 |
| 🔴 Bad | <160 | <AED 8,800 |

**Week tiers** — On-trend 1,300 orders / AED 68k · Good 1,400 / AED 74k · Exceptional 1,500+ / AED 80k+

**Month tiers** — Day × 30
""")

if fresh:
    st.caption(
        f"Data range: {fresh['min_date']} to {fresh['max_date']} · "
        f"{fresh['total_orders']:,} fulfilled orders · "
        f"AED {fresh['total_net']:,.0f} net sales total"
    )
