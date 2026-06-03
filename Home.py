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
    delta_pct,
    fmt_aed,
    fmt_int,
    fmt_pct,
    latest_date,
    load_orders,
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
# THREE BLOCKS — Today / Week / Month
# ---------------------------------------------------------------------------
def render_block(label: str, icon: str, slice_df, full_slice_df,
                 ord_tiers, net_tiers, page_link: str):
    """Render one Today/Week/Month summary block."""
    k = total_kpis(slice_df)
    v_net = verdict_for(k["net"], net_tiers)
    v_ord = verdict_for(k["orders"], ord_tiers)
    st.markdown(f"#### {icon} {label}")
    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        st.metric("Net Sales", fmt_aed(k["net"]))
        st.markdown(f"**{v_net.emoji} {v_net.tier}**")
    with cc2:
        st.metric("Orders", fmt_int(k["orders"]))
        st.markdown(f"**{v_ord.emoji} {v_ord.tier}**")
    with cc3:
        st.metric("Discount", fmt_pct(k["discount_rate"]))
        st.markdown(f"AOV (net) **{fmt_aed(k['aov_net'])}**")
    st.page_link(page_link, label=f"Open {label} →", icon=icon)
    st.markdown("---")


# Today
today_slice = slice_range(df, latest, latest)
render_block(
    "Today",
    "📍",
    today_slice,
    today_slice,
    DAY_ORDERS_TIERS,
    DAY_NET_TIERS,
    "pages/00_Today.py",
)

# This Week (WTD)
monday = latest - timedelta(days=latest.weekday())
week_slice = slice_range(df, monday, latest)
render_block(
    f"This Week ({(latest - monday).days + 1} of 7 days)",
    "📆",
    week_slice,
    week_slice,
    WEEK_ORDERS_TIERS,
    WEEK_NET_TIERS,
    "pages/01_This_Week.py",
)

# This Month (MTD)
month_start = latest.replace(day=1)
days_in_month = calendar.monthrange(latest.year, latest.month)[1]
days_so_far = (latest - month_start).days + 1
month_slice = slice_range(df, month_start, latest)
render_block(
    f"This Month ({days_so_far} of {days_in_month} days)",
    "🗓️",
    month_slice,
    month_slice,
    MONTH_ORDERS_TIERS,
    MONTH_NET_TIERS,
    "pages/02_This_Month.py",
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
