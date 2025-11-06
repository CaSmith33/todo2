# Casing Tally Tool — with Commit button
# --------------------------------------
# Workflow:
#   • Top table: fully editable (staging area)
#   • Row actions: Import Excel / Select all / Delete / Duplicate / Move Up / Move Down
#   • Table has its own "+" to add rows
#   • Press "✅ Commit edits to tally" to update the read-only summary + totals
#
# Columns (editable table):
#   Selected, Used, JointNumber, Description, Length_ft, OD_in, ID_in, Grade, Comments
#
# Summary table (read-only):
#   Same columns + CumTop_ft, CumBottom_ft (rightmost)
# --------------------------------------

import io
import json

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Casing Tally Tool", layout="wide")
st.title("Casing Tally Tool")


# --------------------------------------
# Helpers
# --------------------------------------

def init_tally_base() -> pd.DataFrame:
    """Initial committed tally table."""
    base = [
        {
            "Selected": False,
            "Used": True,
            "JointNumber": 1,
            "Description": "Shoe Track",
            "Length_ft": 100.0,
            "OD_in": 9.625,
            "ID_in": 8.535,
            "Grade": "L80",
            "Comments": "",
        },
        {
            "Selected": False,
            "Used": True,
            "JointNumber": 2,
            "Description": "Casing Joint",
            "Length_ft": 40.0,
            "OD_in": 9.625,
            "ID_in": 8.535,
            "Grade": "L80",
            "Comments": "R3",
        },
        {
            "Selected": False,
            "Used": False,
            "JointNumber": 3,
            "Description": "Spare Joint",
            "Length_ft": 45.0,
            "OD_in": 9.625,
            "ID_in": 8.535,
            "Grade": "L80",
            "Comments": "Spare",
        },
    ]
    return sanitize_base(pd.DataFrame(base))


def sanitize_base(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure committed/base table has the correct columns and dtypes."""
    df = df.copy()
    n = len(df)

    cols_all = [
        "Selected",
        "Used",
        "JointNumber",
        "Description",
        "Length_ft",
        "OD_in",
        "ID_in",
        "Grade",
        "Comments",
    ]

    # Ensure all columns exist
    for col in cols_all:
        if col not in df.columns:
            if col in ("Selected", "Used"):
                df[col] = False
            elif col == "JointNumber":
                df[col] = np.arange(1, n + 1)
            elif col in ("Length_ft", "OD_in", "ID_in"):
                df[col] = np.nan
            else:
                df[col] = ""

    # Types and cleaning
    df["Selected"] = pd.Series(df["Selected"]).fillna(False).astype(bool)
    df["Used"] = pd.Series(df["Used"]).fillna(True).astype(bool)

    # JointNumber as int, auto-fill if missing/NaN
    df["JointNumber"] = pd.to_numeric(df["JointNumber"], errors="coerce")
    if df["JointNumber"].isna().all():
        df["JointNumber"] = np.arange(1, n + 1)
    else:
        fill_series = pd.Series(np.arange(1, n + 1), index=df.index)
        df["JointNumber"] = df["JointNumber"].fillna(fill_series)
    df["JointNumber"] = df["JointNumber"].astype(int)

    # Numeric columns, rounded
    for col in ["Length_ft", "OD_in", "ID_in"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").round(3)

    # Enforce column order
    df = df[cols_all]

    return df


def add_cumulative_cols(base_df: pd.DataFrame) -> pd.DataFrame:
    """Add CumTop_ft and CumBottom_ft from a committed/base table."""
    df = base_df.copy()
    eff_len = df["Length_ft"].fillna(0.0) * df["Used"].astype(int)
    df["CumTop_ft"] = eff_len.cumsum()
    df["CumBottom_ft"] = eff_len[::-1].cumsum()[::-1]
    return df


def get_selected_indices(df: pd.DataFrame):
    """Return list of row indices where Selected == True, safely."""
    if "Selected" not in df.columns:
        return []
    sel = pd.Series(df["Selected"]).fillna(False).astype(bool)
    return list(df.index[sel])


def move_row(df: pd.DataFrame, idx: int, direction: str) -> pd.DataFrame:
    """Move a single row up or down in the DataFrame."""
    if direction not in ("up", "down"):
        return df

    df = df.copy().reset_index(drop=True)
    n = len(df)
    if n <= 1 or idx < 0 or idx >= n:
        return df

    if direction == "up" and idx == 0:
        return df
    if direction == "down" and idx == n - 1:
        return df

    j = idx - 1 if direction == "up" else idx + 1

    order = list(range(n))
    order[idx], order[j] = order[j], order[idx]
    df = df.iloc[order].reset_index(drop=True)
    return df


# --------------------------------------
# Session state init
# --------------------------------------

# Committed tally (used for summary/export)
if "tally_base" not in st.session_state:
    st.session_state.tally_base = init_tally_base()

# Editor staging data (where you type)
if "tally_editor_data" not in st.session_state:
    # start editor from the committed tally
    st.session_state.tally_editor_data = st.session_state.tally_base.copy()

# --------------------------------------
# Workflow text (left) + Import Excel (right)
# --------------------------------------

col_explain, col_import = st.columns([3, 2])

with col_explain:
    st.markdown(
        """
**Workflow**

1. Edit the table below (staging area). Use the **+** icon in the table to add rows.
2. Use **Selected** to pick rows for toolbar actions.
3. Use **💾 Apply edits to staging** to save cell changes into the staging table.
4. Use the toolbar buttons to **Import Excel / Select all / Delete / Duplicate / Move Up / Move Down**.
5. When you're happy with the staging table, click **✅ Commit edits to tally** to update the read-only summary and totals.
"""
    )

with col_import:
    st.markdown("### Import Excel")
    uploaded_file = st.file_uploader(
        "Select Excel file",
        type=["xlsx", "xls"],
        key="tally_excel",
        label_visibility="visible",
    )
    if st.button("📥 Load Excel to staging", disabled=uploaded_file is None):
        try:
            imported_df = pd.read_excel(uploaded_file)

            # Explicitly map any TRUE/FALSE-ish values to bools
            for col in ["Selected", "Used"]:
                if col in imported_df.columns:
                    imported_df[col] = imported_df[col].apply(
                        lambda x: str(x).strip().upper() in ("1", "TRUE", "YES", "Y", "T")
                        if pd.notna(x) else False
                    )

            imported_df = sanitize_base(imported_df)
            st.session_state.tally_editor_data = imported_df
            st.success("Excel imported into staging table.")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to read Excel file: {e}")

# --------------------------------------
# Main editable table (staging) in a form
# --------------------------------------

with st.form("tally_editor_form"):
    edited = st.data_editor(
        st.session_state.tally_editor_data,
        num_rows="dynamic",          # allow adding rows with the "+" icon
        use_container_width=True,
        hide_index=True,
        key="tally_editor",
        column_config={
            "Selected": st.column_config.CheckboxColumn(
                "Selected",
                help="Mark rows to act on",
            ),
            "Used": st.column_config.CheckboxColumn(
                "Used",
                help="Include in cumulative length",
            ),
            "JointNumber": st.column_config.NumberColumn(
                "Joint #",
                help="Joint number / sequence",
                step=1,
                format="%d",
            ),
            "Length_ft": st.column_config.NumberColumn(
                "Length (ft)",
                step=0.1,      # decimal, not integers only
                format="%.2f",
            ),
            "OD_in": st.column_config.NumberColumn(
                "OD (in)",
                step=0.01,
                format="%.3f",
            ),
            "ID_in": st.column_config.NumberColumn(
                "ID (in)",
                step=0.01,
                format="%.3f",
            ),
        },
    )

    apply_edits = st.form_submit_button("💾 Apply edits to staging")

# If user hits "Apply edits", push cell changes into session_state (with rounding)
if apply_edits and isinstance(edited, pd.DataFrame):
    df = edited.copy()
    for col in ["Length_ft", "OD_in", "ID_in"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").round(3)
    # JointNumber: keep as int where possible
    if "JointNumber" in df.columns:
        df["JointNumber"] = pd.to_numeric(df["JointNumber"], errors="coerce")
        n = len(df)
        fill_series = pd.Series(np.arange(1, n + 1), index=df.index)
        df["JointNumber"] = df["JointNumber"].fillna(fill_series).astype(int)
    st.session_state.tally_editor_data = df
    st.rerun()

# Use the latest visible table (from editor) for actions & selection
if isinstance(edited, pd.DataFrame):
    editor_df = edited.copy()
else:
    editor_df = st.session_state.tally_editor_data.copy()

# --------------------------------------
# Row Actions (staging)
# --------------------------------------

st.markdown("### Row Actions (staging)")

col_sel_all, col_used_all, col_del, col_dup, col_up, col_down = st.columns(6)

selected_indices = get_selected_indices(editor_df)

# Select all Selected
with col_sel_all:
    if st.button("Select all 'Selected'"):
        df = editor_df.copy()
        df["Selected"] = True
        st.session_state.tally_editor_data = df
        st.rerun()

# Select all Used
with col_used_all:
    if st.button("Select all 'Used'"):
        df = editor_df.copy()
        df["Used"] = True
        st.session_state.tally_editor_data = df
        st.rerun()

# Delete Selected
with col_del:
    if st.button("🗑️ Delete Selected", disabled=len(selected_indices) == 0):
        df = editor_df.copy()
        df = df.drop(index=selected_indices).reset_index(drop=True)
        for col in ["Length_ft", "OD_in", "ID_in"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").round(3)
        st.session_state.tally_editor_data = df
        st.rerun()

# Duplicate Selected
with col_dup:
    if st.button("📑 Duplicate Selected", disabled=len(selected_indices) == 0):
        df = editor_df.copy()
        rows_to_add = df.loc[selected_indices].copy()
        rows_to_add["Selected"] = False
        df = pd.concat([df, rows_to_add], ignore_index=True)
        for col in ["Length_ft", "OD_in", "ID_in"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").round(3)
        st.session_state.tally_editor_data = df
        st.rerun()

# Move Up
with col_up:
    if st.button("⬆️ Move Up", disabled=len(selected_indices) != 1):
        idx = selected_indices[0] if selected_indices else None
        if idx is not None:
            df = move_row(editor_df, idx, "up")
            for col in ["Length_ft", "OD_in", "ID_in"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").round(3)
            st.session_state.tally_editor_data = df
            st.rerun()

# Move Down
with col_down:
    if st.button("⬇️ Move Down", disabled=len(selected_indices) != 1):
        idx = selected_indices[0] if selected_indices else None
        if idx is not None:
            df = move_row(editor_df, idx, "down")
            for col in ["Length_ft", "OD_in", "ID_in"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").round(3)
            st.session_state.tally_editor_data = df
            st.rerun()

st.markdown("---")

# --------------------------------------
# Commit button
# --------------------------------------

if st.button("✅ Commit edits to tally"):
    # Sanitize and store as committed/base
    committed = sanitize_base(st.session_state.tally_editor_data)
    st.session_state.tally_base = committed
    # Also reset editor to reflect the committed version (optional)
    st.session_state.tally_editor_data = committed.copy()
    st.success("Edits committed to tally.")
    st.rerun()

# --------------------------------------
# Read-only summary with cumulative columns
# --------------------------------------

st.markdown("### Committed Casing Tally (read-only)")

committed_df = st.session_state.tally_base.copy()
calc_df = add_cumulative_cols(committed_df)

summary_cols = [
    "Selected",
    "Used",
    "JointNumber",
    "Description",
    "Length_ft",
    "OD_in",
    "ID_in",
    "Grade",
    "Comments",
    "CumTop_ft",
    "CumBottom_ft",
]
summary_df = calc_df[summary_cols]

st.dataframe(summary_df, use_container_width=True, height=380)

# --------------------------------------
# Metrics + Export
# --------------------------------------

st.markdown("### Summary Metrics")

total_used = float(
    (calc_df["Length_ft"].fillna(0) * calc_df["Used"].astype(int)).sum()
)
st.metric("Total Used Length (ft)", f"{total_used:,.2f}")

st.subheader("Export")

csv_buf = io.StringIO()
summary_df.to_csv(csv_buf, index=False)
st.download_button("Download CSV", data=csv_buf.getvalue(), file_name="casing_tally.csv")

json_buf = io.StringIO()
json.dump(
    {
        "tally": summary_df.to_dict(orient="records"),
        "total_used_length_ft": total_used,
    },
    json_buf,
    indent=2,
)
st.download_button("Download JSON", data=json_buf.getvalue(), file_name="casing_tally.json")
