"""
Centralized data loader for Grubtech Cloud Kitchen Dashboard.
Loads all 19 JSON data files and provides cleaned DataFrames.
Designed to also support Deliverect and Revly data sources in the future.
"""

import json
import os
import pandas as pd
import streamlit as st
from pathlib import Path

# Base path to JSON data
DATA_DIR = Path(__file__).parent.parent.parent / "JSON"


def _resolve_data_dir():
    """Resolve data directory - check multiple possible locations."""
    candidates = [
        DATA_DIR,
        Path("E:/Cloud Kitchen/Grubtech Data/2503/2603/JSON"),
        Path("C:/Users/harsh/Downloads/Grubtech Data/2503/2603/JSON"),
        Path(__file__).parent.parent / "data",
    ]
    for p in candidates:
        if p.exists():
            return p
    return DATA_DIR


def _load_json(filename: str) -> dict | list:
    """Load a JSON file and return its contents."""
    data_dir = _resolve_data_dir()
    filepath = data_dir / filename
    if not filepath.exists():
        st.warning(f"Data file not found: {filepath}")
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def _extract_df(data, expected_sheet=None) -> pd.DataFrame:
    """Extract DataFrame from JSON data (handles both sheet-wrapped and raw list formats)."""
    if isinstance(data, list):
        return pd.DataFrame(data)
    elif isinstance(data, dict):
        if expected_sheet and expected_sheet in data:
            return pd.DataFrame(data[expected_sheet])
        # Take the first (and usually only) sheet
        for key, value in data.items():
            if isinstance(value, list):
                return pd.DataFrame(value)
    return pd.DataFrame()


# ─── CACHED DATA LOADERS ───────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_sales_orders() -> pd.DataFrame:
    """Sales - Orders: 40,802 records, 32 columns. Core financial order data."""
    data = _load_json("2603 Sales - Orders.json")
    df = _extract_df(data, "OrderDetails")
    if not df.empty:
        df.columns = df.columns.str.strip()
        if "Received At" in df.columns:
            df["Received At"] = pd.to_datetime(df["Received At"], errors="coerce")
            df["Date"] = df["Received At"].dt.date
            df["Month"] = df["Received At"].dt.to_period("M").astype(str)
            df["Week"] = df["Received At"].dt.isocalendar().week.astype(int)
            df["Day"] = df["Received At"].dt.day_name()
            df["Hour"] = df["Received At"].dt.hour
        # Ensure numeric columns
        for col in ["Item Price", "Surcharge", "Delivery", "Net Sales", "Gross Price",
                     "Discount", "VAT", "Total(Receipt Total)", "Tips"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=3600)
def load_sales_brand() -> pd.DataFrame:
    """Sales - Brand: 31 records. Brand-level aggregated sales."""
    data = _load_json("2603 Sales - Brand.json")
    df = _extract_df(data, "BrandSales")
    if not df.empty:
        df.columns = df.columns.str.strip()
        for col in ["No. of Orders", "Avg. Order Value", "Gross Sales", "Discounts",
                     "Total Earnings", "Taxes", "Net Sales"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=3600)
def load_sales_channels() -> pd.DataFrame:
    """Sales - Channels: 6 records. Channel-level aggregated sales."""
    data = _load_json("2603 Sales - Channels.json")
    df = _extract_df(data, "ChannelSales")
    if not df.empty:
        df.columns = df.columns.str.strip()
        for col in ["No. of Orders", "Avg. Order Value", "Gross Sales", "Discounts",
                     "Total Earnings", "Taxes", "Net Sales"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=3600)
def load_sales_location() -> pd.DataFrame:
    """Sales - Location: 31 records. Location-level aggregated sales."""
    data = _load_json("2603 Sales - Location.json")
    df = _extract_df(data, "SalesByKitchen")
    if not df.empty:
        df.columns = df.columns.str.strip()
        for col in ["No. of Orders", "Avg. Order Value", "Gross Sales", "Discounts",
                     "Total Earnings", "Net Sales", "Delivery Charge", "Taxes"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=3600)
def load_operations_orders() -> pd.DataFrame:
    """Operations - Orders: 40,802 records. Operational timestamps per order."""
    data = _load_json("2603 Operations - Orders.json")
    df = _extract_df(data, "LocationPerformanceOrder")
    if not df.empty:
        df.columns = df.columns.str.strip()
        time_cols = ["Created At", "Received At", "Accepted At", "Started At",
                     "Prepared At", "Sent to Dispatcher At", "Dispatched At",
                     "Delivered At", "Driver Requested At", "Driver Assigned At",
                     "Driver ETA", "Driver Check-in", "Driver Check-Out", "Completed On"]
        for col in time_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        # Parse duration columns (HH:MM:SS strings to minutes)
        duration_cols = ["Order Accepted to Started", "Started To Prepared",
                         "Prepared to Sent to Dispatch", "Sent To Dispatch to Dispatched",
                         "Dispatched to Delivered", "Order Received to Delivered"]
        for col in duration_cols:
            if col in df.columns:
                df[f"{col} (min)"] = df[col].apply(_parse_duration_to_minutes)
        if "Received At" in df.columns:
            df["Date"] = df["Received At"].dt.date
            df["Month"] = df["Received At"].dt.to_period("M").astype(str)
    return df


@st.cache_data(ttl=3600)
def load_operations_locations() -> pd.DataFrame:
    """Operations - Locations: 32 records. Average operational times per location."""
    data = _load_json("2603 Operations - Locations.json")
    df = _extract_df(data, "LocationPerformanceAverage")
    if not df.empty:
        df.columns = df.columns.str.strip()
        duration_cols = ["Accepted to Started", "Started To Prepared",
                         "Prepared to Sent to Dispatch", "Sent To Dispatch to Dispatched",
                         "Dispatched to Delivered", "Received to Delivered"]
        for col in duration_cols:
            if col in df.columns:
                df[f"{col} (min)"] = df[col].apply(_parse_duration_to_minutes)
    return df


@st.cache_data(ttl=3600)
def load_operations_stations() -> pd.DataFrame:
    """Operations - Stations: 8,192 records. Station-level item prep data."""
    data = _load_json("2603 Operations - Stations.json")
    df = _extract_df(data, "StationPerformanceOrder")
    if not df.empty:
        df.columns = df.columns.str.strip()
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        if "Item Preparation Time" in df.columns:
            df["Prep Time (min)"] = df["Item Preparation Time"].apply(_parse_duration_to_minutes)
    return df


@st.cache_data(ttl=3600)
def load_cancelled_orders() -> pd.DataFrame:
    """Cancelled Orders: 525 records."""
    data = _load_json("2603 Cancelled orders.json")
    df = _extract_df(data, "CancelledOrder")
    if not df.empty:
        df.columns = df.columns.str.strip()
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        if "Cancellation Time" in df.columns:
            df["Cancellation Time"] = pd.to_datetime(df["Cancellation Time"], errors="coerce")
        for col in ["Sales Amount", "VAT", "Sales After Tax"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=3600)
def load_rejected_orders() -> pd.DataFrame:
    """Rejected Orders (Report): 14 records."""
    data = _load_json("2603 Report.json")
    df = _extract_df(data, "RejectedOrder")
    if not df.empty:
        df.columns = df.columns.str.strip()
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        for col in ["Sales Amount", "VAT", "Sales After Tax"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=3600)
def load_customers() -> pd.DataFrame:
    """Customers: 19,887 records."""
    data = _load_json("2603 Customers.json")
    df = _extract_df(data)  # Raw list, no sheet wrapper
    if not df.empty:
        df.columns = df.columns.str.strip()
    return df


@st.cache_data(ttl=3600)
def load_marketing() -> pd.DataFrame:
    """Marketing Campaign Performance: 372 records."""
    data = _load_json("2603 Marketing.json")
    df = _extract_df(data, "CampaignPerformanceByPartner")
    if not df.empty:
        df.columns = df.columns.str.strip()
        for col in ["No of Orders", "Original Amount", "Discount", "Sales Amount"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=3600)
def load_menu_details() -> pd.DataFrame:
    """Menu Performance - Details: 3,868 records. Item-level menu performance."""
    data = _load_json("2603 Menu Performance - Details.json")
    df = _extract_df(data, "MenuItemsDetails")
    if not df.empty:
        df.columns = df.columns.str.strip()
        for col in ["Item Quantity", "Gross Sales", "Discounts"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=3600)
def load_menu_orders() -> pd.DataFrame:
    """Menu Performance - Orders: 88,407 records. Order-item level data."""
    data = _load_json("2603 Menu Performance - Orders.json")
    df = _extract_df(data, "OrderItemsSales")
    if not df.empty:
        df.columns = df.columns.str.strip()
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        for col in ["Qty", "Item Price", "Item Total Sales Amount", "Item Discount",
                     "Order Price", "Delivery", "Net Sales", "Gross Price",
                     "Discount", "VAT", "Total(Receipt Total)"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=3600)
def load_menu_modifiers() -> pd.DataFrame:
    """Menu Performance - Modifiers: 3,018 records."""
    data = _load_json("2603 Menu Performance - Modifiers.json")
    df = _extract_df(data, "ModifierMenuItemsBreakdown")
    if not df.empty:
        df.columns = df.columns.str.strip()
        for col in ["Gross Sales", "Discount", "Total Quantity", "Average Quantity Per Day"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=3600)
def load_menu_tags() -> pd.DataFrame:
    """Menu Performance - Tags: 521 records."""
    data = _load_json("2603 Menu Performance - Tags.json")
    df = _extract_df(data, "SalesByMenuItemTags")
    if not df.empty:
        df.columns = df.columns.str.strip()
        for col in ["Item Qty", "Total Sales", "Total Discounts", "VAT"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=3600)
def load_item_availability_snapshot() -> pd.DataFrame:
    """Item Availability Snapshot: 55,478 records."""
    data = _load_json("2603 Item Availability snapshot.json")
    df = _extract_df(data, "ItemAvailabilitySnapshot")
    if not df.empty:
        df.columns = df.columns.str.strip()
        if "Last Updated" in df.columns:
            df["Last Updated"] = pd.to_datetime(df["Last Updated"], errors="coerce")
    return df


@st.cache_data(ttl=3600)
def load_item_availability_monitor() -> pd.DataFrame:
    """Monitor - Item Availability: 9,038 records."""
    data = _load_json("2603 Monitor - Item Availability.json")
    df = _extract_df(data, "ItemAvailability")
    if not df.empty:
        df.columns = df.columns.str.strip()
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        if "Duration" in df.columns:
            df["Duration (min)"] = df["Duration"].apply(_parse_duration_to_minutes)
    return df


@st.cache_data(ttl=3600)
def load_pos_sync() -> pd.DataFrame:
    """POS Sync Summary: 32 records."""
    data = _load_json("2603 POS Sync Summary.json")
    df = _extract_df(data, "PosSyncSummary")
    if not df.empty:
        df.columns = df.columns.str.strip()
        for col in ["Total No of Orders", "Sync Successful", "Error"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


# ─── HELPER FUNCTIONS ───────────────────────────────────────────────────

def _parse_duration_to_minutes(val) -> float:
    """Parse HH:MM:SS or similar duration string to total minutes."""
    if pd.isna(val) or val is None or val == "":
        return None
    try:
        if isinstance(val, (int, float)):
            return float(val)
        val = str(val).strip()
        parts = val.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 60 + int(m) + int(s) / 60
        elif len(parts) == 2:
            m, s = parts
            return int(m) + int(s) / 60
        return float(val)
    except (ValueError, TypeError):
        return None


def get_all_brands(df: pd.DataFrame = None) -> list:
    """Get unique brand names from sales orders."""
    if df is None:
        df = load_sales_orders()
    if "Brand" in df.columns:
        return sorted(df["Brand"].dropna().unique().tolist())
    return []


def get_all_locations(df: pd.DataFrame = None) -> list:
    """Get unique location names from sales orders."""
    if df is None:
        df = load_sales_orders()
    if "Location" in df.columns:
        return sorted(df["Location"].dropna().unique().tolist())
    return []


def get_all_channels(df: pd.DataFrame = None) -> list:
    """Get unique channel names from sales orders."""
    if df is None:
        df = load_sales_orders()
    if "Channel" in df.columns:
        return sorted(df["Channel"].dropna().unique().tolist())
    return []


def get_date_range(df: pd.DataFrame = None):
    """Get min and max dates from sales orders."""
    if df is None:
        df = load_sales_orders()
    if "Received At" in df.columns:
        valid = df["Received At"].dropna()
        if not valid.empty:
            return valid.min(), valid.max()
    return None, None


# ─── CUISINE-TO-BRAND MAPPING ──────────────────────────────────────────

CUISINE_BRAND_MAP = {
    "Big Dawg's Burgers": "American",
    "Bronx Burger House": "American",
    "Juicy Buns - Loaded Burgers & Fries": "American",
    "Smashville Burgers": "American",
    "The Patty Pit - Burgers & Fries": "American",
    "Slider Shack - Mini Beach Burgers": "American",
    "Winging It - Artisan Wings & Bites": "American",
    "Wings of Fury - Fiery Crispy Wings": "American",
    "Before Noon - Breakfast & Brunch": "Breakfast",
    "Toast & Co – Artisan Breakfast": "Breakfast",
    "Breakfast Counter – All Day Diner": "Breakfast",
    "Sunrise & Co – Acai & Power Bowls": "Breakfast",
    "Red Ginger - Chinese Wok House": "Chinese",
    "Shanghai Spice - Chinese Noodle House": "Chinese",
    "Wok Street - Chinese Street Noodles": "Chinese",
    "Patiala Plate - Indian Kitchen": "Indian",
    "Tandoori Tribe - Indian Grill": "Indian",
    "The Curry Club - Indian Kitchen": "Indian",
    "Smoky Tandoor - Indian Grill": "Indian",
    "Zaika Punjab - Indian Kitchen": "Indian",
    "Annyeong - Korean Cuisine": "Korean",
    "Hungry Oppa - Korean Street Food": "Korean",
    "Jinjja - Korean Kitchen": "Korean",
    "Noona": "Korean",
    "Seoul Food": "Korean",
    "Casa Del Queso": "Mexican",
    "Fiesta - Mexican food": "Mexican",
    "Loco Taco - Mexican Street Tacos": "Mexican",
    "Mexigo - Street Mexican": "Mexican",
    "Picante - Spicy Mexican Grill": "Mexican",
    "PokeMan - Poke Bowls": "Poke",
    "The Big Kahuna - Hawaiian Poke Bowls": "Poke",
    "Hikari - Sushi Bar": "Sushi",
    "Norii - Premium Sushi": "Sushi",
    "Oneesan - Sushi Bar": "Sushi",
}


def get_cuisine_for_brand(brand: str) -> str:
    """Return the cuisine category for a brand. Uses fuzzy matching as fallback."""
    if brand in CUISINE_BRAND_MAP:
        return CUISINE_BRAND_MAP[brand]
    # Fuzzy match: check if the brand name contains a known brand key
    brand_lower = brand.lower().strip()
    for key, cuisine in CUISINE_BRAND_MAP.items():
        if key.lower() in brand_lower or brand_lower in key.lower():
            return cuisine
    return "Other"


def add_cuisine_column(df: pd.DataFrame, brand_col: str = "Brand") -> pd.DataFrame:
    """Add a 'Cuisine' column to a DataFrame based on the Brand column."""
    if brand_col in df.columns:
        df = df.copy()
        df["Cuisine"] = df[brand_col].apply(get_cuisine_for_brand)
    return df


def get_all_cuisines() -> list:
    """Get sorted list of unique cuisine categories."""
    return sorted(set(CUISINE_BRAND_MAP.values()))


def get_cuisine_brand_df() -> pd.DataFrame:
    """Return the cuisine-brand mapping as a DataFrame."""
    records = [{"Brand": brand, "Cuisine": cuisine} for brand, cuisine in CUISINE_BRAND_MAP.items()]
    return pd.DataFrame(records).sort_values(["Cuisine", "Brand"]).reset_index(drop=True)


# ─── FUTURE: DELIVERECT & REVLY INTEGRATION STUBS ──────────────────────

def load_deliverect_orders() -> pd.DataFrame:
    """
    Placeholder for Deliverect API integration.
    Deliverect REST API: https://api.deliverect.com/
    Endpoints: /orders, /products, /channels, /reports
    Will require API key from Deliverect dashboard.
    """
    st.info("Deliverect integration coming soon. Configure API key in settings.")
    return pd.DataFrame()


def load_revly_data() -> pd.DataFrame:
    """
    Placeholder for Revly data integration.
    Revly provides revenue management & dynamic pricing data.
    Can be integrated via CSV export or API.
    """
    st.info("Revly integration coming soon. Upload CSV or configure API.")
    return pd.DataFrame()
