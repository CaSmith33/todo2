"""Interactive casing tally: Excel import, drag reorder, include/exclude and forward/reverse lengths."""
import io
import pandas as pd
from datetime import date
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase.pdfmetrics import stringWidth
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


def create_print_pdf(result, details):
    """Build a landscape, multi-page, print-ready PDF; repeat table headings."""
    buffer = io.BytesIO()
    page_w, page_h = landscape(letter)
    margin = 28
    doc = SimpleDocTemplate(
        buffer, pagesize=(page_w, page_h),
        leftMargin=margin, rightMargin=margin,
        topMargin=98, bottomMargin=43,
        title="Casing Tally - " + str(details["Well"]),
        author=str(details["Prepared By"]),
    )
    font = ParagraphStyle(
        "Cell", fontName="Helvetica", fontSize=7.1, leading=9,
        alignment=TA_LEFT, wordWrap="CJK",
    )
    bold = ParagraphStyle(
        "Head", parent=font, fontName="Helvetica-Bold", fontSize=7,
        textColor=colors.white,
    )
    columns = [
        ("Run", "Run Order", 31), ("Used", "Used", 31),
        ("No.", "Number", 43), ("Length", "Length", 49),
        ("Grade", "grade", 40), ("Wt", "weight", 32),
        ("ID", "ID", 38), ("OD", "OD", 38),
        ("Description", "Description", 104),
        ("Description 2", "Description 2", 94),
        ("Forward", "Forward (ft)", 57),
        ("Backward", "Backward (ft)", 57),
    ]
    usable = page_w - 2 * margin
    widths = [c[2] for c in columns]
    widths[8] += (usable - sum(widths)) * 0.55
    widths[9] += (usable - sum(widths)) * 0.45

    def cell(v):
        if pd.isna(v):
            return ""
        if isinstance(v, float):
            return f"{v:,.3f}".rstrip("0").rstrip(".")
        return str(v)

    rows = [[Paragraph(escape(head), bold) for head, _, _ in columns]]
    inactive = []
    for i, (_, record) in enumerate(result.iterrows(), start=1):
        rows.append([
            Paragraph(escape("Yes" if record["Used"] else "No") if key == "Used" else escape(cell(record[key])), font)
            for _, key, _ in columns
        ])
        if not bool(record["Used"]):
            inactive.append(i)

    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#18324E")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#10243B")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#DCE4EA")),
    ]
    for i in range(2, len(rows), 2):
        style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F3F7FA")))
    for i in inactive:
        style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#ECECEC")))
        style.append(("TEXTCOLOR", (0, i), (-1, i), colors.HexColor("#777777")))
    table.setStyle(TableStyle(style))
    total_length = result.loc[result["Used"], "Length"].sum()
    summary = (
        f'Included joints: {int(result["Used"].sum())}  |  '
        f'Excluded joints: {int((~result["Used"]).sum())}  |  '
        f'Total included length: {total_length:,.2f} ft'
    )

    def draw_page(canvas, document):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#18324E"))
        canvas.rect(0, page_h - 9, page_w, 9, stroke=0, fill=1)
        canvas.setFont("Helvetica-Bold", 14)
        canvas.setFillColor(colors.HexColor("#18324E"))
        canvas.drawString(margin, page_h - 31, "CASING TALLY")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#46586D"))
        # Keep long user-entered values within their allotted header slots.
        def fitted(value, limit):
            s = str(value or "-")
            while s and stringWidth(s, "Helvetica", 8) > limit:
                s = s[:-1]
            return s
        canvas.drawString(margin, page_h - 47, "Company: " + fitted(details["Company"], 195))
        canvas.drawString(270, page_h - 47, "Well: " + fitted(details["Well"], 190))
        canvas.drawString(530, page_h - 47, "Section: " + fitted(details["Section"], 180))
        canvas.drawString(margin, page_h - 62, "Date: " + fitted(details["Date"], 130))
        canvas.drawString(195, page_h - 62, "Version: " + fitted(details["Version"], 95))
        canvas.drawString(350, page_h - 62, "Prepared by: " + fitted(details["Prepared By"], 260))
        canvas.setStrokeColor(colors.HexColor("#BCCAD5"))
        canvas.line(margin, page_h - 72, page_w - margin, page_h - 72)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(margin, 25, summary)
        canvas.drawRightString(page_w - margin, 25, f"Page {document.page}")
        canvas.restoreState()

    doc.build([table], onFirstPage=draw_page, onLaterPages=draw_page)
    buffer.seek(0)
    return buffer.getvalue()

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
# Return the actual visible row order to Python before the user presses Run Tally.
grid = AgGrid(
    st.session_state.tally_rows_v2,
    gridOptions=options,
    # Dragging a row does not emit a cell-value-change event. Return the
    # newly displayed order on rowDragEnd, and checkbox edits on value change.
    update_mode=GridUpdateMode.NO_UPDATE,
    update_on=["rowDragEnd", "cellValueChanged"],
    data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
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

if result is not None:
    st.divider()

    active_well_id = st.session_state.get("active_well_id")
    if active_well_id is not None:
        st.subheader("Save tally to well project")
        with st.form("save_tally_snapshot"):
            tally_name = st.text_input("Tally name", value="Casing tally")
            section_name = st.text_input("Casing section")
            save_clicked = st.form_submit_button("Save tally snapshot")
        if save_clicked:
            try:
                import json
                from project_store import save_casing_tally
                snapshot = json.loads(result.to_json(orient="records"))
                tally_id = save_casing_tally(active_well_id, tally_name, section_name, snapshot)
                st.success(f"Saved tally #{tally_id} to the selected well for Cementing.")
            except Exception as exc:
                st.error(f"Unable to save tally: {exc}")
    else:
        st.info("Select an active well in the sidebar to save this tally for Cementing.")

    st.subheader("Print-ready tally report")
    st.caption("Enter report details, then download the landscape PDF. Headers repeat on every page.")
    col1, col2, col3 = st.columns(3)
    with col1:
        company = st.text_input("Company Name", key="tally_company")
        well = st.text_input("Well", key="tally_well")
    with col2:
        section = st.text_input("Section", key="tally_section")
        report_date = st.date_input("Date", value=date.today(), key="tally_report_date")
    with col3:
        version = st.text_input("Version", value="1.0", key="tally_version")
        prepared_by = st.text_input("Prepared By", key="tally_prepared_by")
    details = {
        "Company": company, "Well": well, "Section": section,
        "Date": report_date.strftime("%Y-%m-%d"),
        "Version": version, "Prepared By": prepared_by,
    }
    pdf = create_print_pdf(result, details)
    st.download_button(
        "Download Print-Ready PDF", data=pdf,
        file_name="casing_tally_print.pdf",
        mime="application/pdf", type="primary",
    )
