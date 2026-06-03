"""
Data Upload — drag-drop Deliverect JSON exports.

Merges with existing data using OrderID dedup, replaces the manual
file-drop-then-merge workflow.
"""

import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd

DATA_PATH = Path(__file__).parent.parent / "data" / "Deliverect_March_2026.json"

st.set_page_config(page_title="Data Upload", page_icon="⬆️", layout="wide")
st.title("⬆️ Upload Deliverect Data")

# ─── CURRENT DATA STATE ───────────────────────────────────────────────────────
def get_current_state():
    if not DATA_PATH.exists():
        return None, None, 0
    with open(DATA_PATH, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    records = data.get("DeliverectOrders", [])
    if not records:
        return None, None, 0
    # Parse timestamps
    times = []
    for r in records:
        t = r.get("PickupTime") or r.get("CreatedTime")
        if t:
            try:
                times.append(pd.to_datetime(t, utc=True).tz_convert("Asia/Dubai").tz_localize(None))
            except Exception:
                pass
    if not times:
        return None, None, len(records)
    return min(times), max(times), len(records)

min_t, max_t, cur_count = get_current_state()

st.markdown("### Current dataset")
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Records in file", f"{cur_count:,}")
with c2:
    st.metric("Earliest pickup", min_t.strftime("%Y-%m-%d %H:%M") if min_t else "—")
with c3:
    st.metric("Latest pickup", max_t.strftime("%Y-%m-%d %H:%M") if max_t else "—")

if max_t:
    age = pd.Timestamp.now() - max_t
    age_hours = age.total_seconds() / 3600
    if age_hours > 24:
        st.warning(f"⚠️ Data is **{age_hours:.0f} hours old**. Consider uploading a fresh export.")
    elif age_hours > 6:
        st.info(f"Data is {age_hours:.1f} hours old.")
    else:
        st.success(f"🟢 Data is current ({age_hours:.1f} hours old).")

st.markdown("---")

# ─── UPLOAD ────────────────────────────────────────────────────────────────────
st.markdown("### Upload new export")
st.caption(
    "Drag the JSON file from Deliverect (`order-*.json`). The merge uses OrderID for "
    "de-duplication — records with the same OrderID are replaced with the newer version. "
    "Existing records not in the new file are kept."
)

uploaded = st.file_uploader(
    "Choose Deliverect JSON file",
    type=["json"],
    help="Deliverect exports are JSONL (one JSON object per line). The merger handles this format.",
)

if uploaded is not None:
    # Parse the upload
    raw = uploaded.getvalue().decode("utf-8-sig")
    new_records = []
    parse_errors = 0
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            new_records.append(json.loads(line))
        except json.JSONDecodeError:
            parse_errors += 1

    if not new_records:
        # Try parsing as a single JSON object
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "DeliverectOrders" in data:
                new_records = data["DeliverectOrders"]
        except json.JSONDecodeError:
            pass

    if not new_records:
        st.error("Could not parse any records from this file. Ensure it's a valid Deliverect JSONL export.")
        st.stop()

    st.success(f"Parsed **{len(new_records)} records** from upload.")
    if parse_errors:
        st.warning(f"Skipped {parse_errors} malformed lines.")

    # Inspect new records
    new_dates = []
    for r in new_records:
        t = r.get("PickupTime") or r.get("CreatedTime")
        if t:
            try:
                new_dates.append(pd.to_datetime(t, utc=True).tz_convert("Asia/Dubai").tz_localize(None))
            except Exception:
                pass

    if new_dates:
        st.markdown(f"**New file date range:** {min(new_dates).strftime('%Y-%m-%d %H:%M')} → {max(new_dates).strftime('%Y-%m-%d %H:%M')}")

    new_ids = set(str(r.get("OrderID", "")) for r in new_records)
    unique_new = len(new_ids)
    st.markdown(f"**Unique OrderIDs in upload:** {unique_new}")

    # Confirm and merge
    if st.button("Merge into dataset", type="primary"):
        with st.spinner("Merging…"):
            # Load existing
            with open(DATA_PATH, "r", encoding="utf-8-sig") as f:
                ex_data = json.load(f)
            ex_records = ex_data.get("DeliverectOrders", [])

            # Keep records from old data that are NOT in new
            old_only = [r for r in ex_records if str(r.get("OrderID", "")) not in new_ids]
            combined = new_records + old_only
            net_new = len(combined) - len(ex_records)

            # Write
            output = {"DeliverectOrders": combined}
            with open(DATA_PATH, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False)

        st.success(f"✅ Merged. **+{net_new} net new orders.** Total records now: {len(combined):,}.")
        st.info(
            "**Next steps:**\n"
            "1. The dashboard will pick up the new data on next page load (or click 'Reload' in the app menu).\n"
            "2. To deploy to Streamlit Cloud, commit the file change and push. "
            "From the project folder:\n\n"
            "```bash\n"
            "git add data/Deliverect_March_2026.json\n"
            "git commit -m 'Update Deliverect data'\n"
            "git push origin main\n"
            "```"
        )

st.markdown("---")
st.caption(
    "**Merge rule:** new file records take precedence over existing records with the same OrderID. "
    "Existing records not in the new file are preserved. Both Deliverect JSONL format and "
    "the wrapped `{\"DeliverectOrders\": [...]}` format are accepted."
)
