"""Interactive casing tally: Excel import, drag reorder, include/exclude and forward/reverse lengths."""
import io
import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode

st.set_page_config(page_title="Casing Tally", layout="wide")
st.title("Casing Tally")

COLUMNS = ["Number", "Length", "grade", "weight", "ID", "OD", "Description", "Description 2"]
NUMERIC = ["Length", "weight", "ID", "OD"]

def prepare(df):
    # Accept case/space variations in spreadsheet headers.
    normalized = {str(c).strip().casefold(): c for c in df.columns}
    missing = [c for c in COLUMNS if c.casefold() not in normalized]
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    out = df[[normalized[c.casefold()] for c in COLUMNS]].copy()
    out.columns = COLUMNS
    for c in NUMERIC:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    if out["Length"].isna().any() or (out["Length"] < 0).any():
        raise ValueError("Every joint must have a valid nonnegative Length.")
    out["Used"] = True
    return out.reset_index(drop=True)

def calculate(df):
    result = df.copy().reset_index(drop=True)
    result.insert(0, "Run Order", range(1, len(result) + 1))
    included = result["Used"].fillna(False).astype(bool)
    effective = result["Length"].where(included, 0).fillna(0)
    result["Forward (ft)"] = effective.cumsum().round(3)
    result["Backward (ft)"] = effective.iloc[::-1].cumsum().iloc[::-1].round(3)
    return result

if "tally_rows_v2" not in st.session_state:
    st.session_state.tally_rows_v2 = prepare(pd.DataFrame([
        [1, 40.0, "P110", 23, 4.67, 5, "Casing", "Example"],
        [2, 42.0, "P110", 23, 4.67, 5, "Casing", "Example"],
        [3, 38.0, "P110", 23, 4.67, 5, "Casing", "Example"],
    ], columns=COLUMNS))
if "tally_result_v2" not in st.session_state:
    st.session_state.tally_result_v2 = None

st.caption("Upload an Excel file, drag rows by the handle to set running order, and uncheck Used to exclude joints. Then click Run Tally.")
uploaded = st.file_uploader("Upload casing tally (.xlsx)", type=["xlsx"], key="tally_upload_v2")
if st.button("Load Excel", disabled=uploaded is None):
    try:
        st.session_state.tally_rows_v2 = prepare(pd.read_excel(uploaded, engine="openpyxl"))
        st.session_state.tally_result_v2 = None
        st.rerun()
    except Exception as exc:
        st.error(f"Could not import tally: {exc}")

gb = GridOptionsBuilder.from_dataframe(st.session_state.tally_rows_v2)
gb.configure_default_column(editable=False, resizable=True, sortable=False, filter=False)
gb.configure_column("Used", editable=True, cellRenderer="agCheckboxCellRenderer", cellEditor="agCheckboxCellEditor", width=95)
gb.configure_column("Number", rowDrag=True, width=115)
gb.configure_column("Length", type=["numericColumn"], width=125)
options = gb.build()
options.update({
    "rowDragManaged": True,
    "animateRows": True,
    "suppressMoveWhenRowDragging": False,
    "suppressRowClickSelection": True,
    "domLayout": "normal",
})
# Grid's displayed order is returned after drag; use that exact order for calculations.
grid = AgGrid(
    st.session_state.tally_rows_v2,
    gridOptions=options,
    update_mode=GridUpdateMode.MODEL_CHANGED | GridUpdateMode.VALUE_CHANGED,
    data_return_mode=DataReturnMode.AS_INPUT,
    allow_unsafe_jscode=False,
    fit_columns_on_grid_load=False,
    height=400,
    key="tally_grid_v2",
)
current = pd.DataFrame(grid["data"])
if not current.empty:
    current = current[[*COLUMNS, "Used"]].copy()
    current["Used"] = current["Used"].fillna(False).astype(bool)
    st.session_state.tally_rows_v2 = current.reset_index(drop=True)

if st.button("Run Tally", type="primary"):
    st.session_state.tally_result_v2 = calculate(st.session_state.tally_rows_v2)

result = st.session_state.tally_result_v2
if result is not None:
    selected = result[result["Used"]]
    a, b, c = st.columns(3)
    a.metric("Included joints", len(selected))
    b.metric("Excluded joints", len(result) - len(selected))
    c.metric("Total length (ft)", f'{selected["Length"].sum():,.2f}')
    st.subheader("Forward / Backward Tally")
    st.dataframe(result, hide_index=True, use_container_width=True)
    st.download_button("Download tally CSV", result.to_csv(index=False).encode("utf-8"),
                       file_name="casing_tally.csv", mime="text/csv")
