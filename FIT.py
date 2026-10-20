# # Pressure Testing App V3.1 – Streamlit (index-based only)
# -------------------------------------------------
# Updates:
# - Leak-off detection window is now the last **N points before the peak** (default N=30).
# - N is user-adjustable in the sidebar and replaces prior window/guard params.
# - All analysis remains index-based; time is display-only.
# -------------------------------------------------

import io
import json
from datetime import date
from xml.sax.saxutils import escape
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st

try:
    from scipy.signal import savgol_filter
    SCIPY_AVAILABLE = True
except Exception:
    SCIPY_AVAILABLE = False

import plotly.graph_objects as go

# -----------------------------
# Helpers
# -----------------------------

def _moving_average(x: np.ndarray, window: int) -> np.ndarray:
    window = max(int(window), 1)
    if window <= 1:
        return x.copy()
    kernel = np.ones(window) / window
    return np.convolve(x, kernel, mode='same')


def smooth_series(values: np.ndarray, window: int, poly: int) -> np.ndarray:
    if len(values) < 5:
        return values.copy()
    window = max(3, int(window) | 1)
    poly = max(1, min(int(poly), window - 1))
    if SCIPY_AVAILABLE:
        try:
            return savgol_filter(values, window_length=window, polyorder=poly, mode='interp')
        except Exception:
            pass
    return _moving_average(values, window)


def compute_derivatives_index(y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Compute first and second derivatives with respect to **index** (Δi = 1)."""
    if len(y) < 3:
        return np.zeros_like(y), np.zeros_like(y)
    d1 = np.gradient(y)
    d2 = np.gradient(d1)
    return d1, d2


def detect_leakoff_lastN(df: pd.DataFrame, pre_n: int = 30, d2_neg_quantile: float = 0.2) -> Optional[int]:
    """Detect leak-off using only the last N points *before* the global pressure peak.

    Args:
        df: DataFrame with 'pressure' column (smoothed already if desired).
        pre_n: Number of points directly preceding the peak to analyze (>=5 recommended).
        d2_neg_quantile: Quantile threshold among negative curvature values to flag leak-off.

    Returns:
        Index (iloc) of detected leak-off within df, or None.
    """
    if df is None or df.empty or len(df) < 10:
        return None

    p = df['pressure'].values
    # Light smoothing for curvature decision
    p_s = smooth_series(p, window=7, poly=2)
    d1, d2 = compute_derivatives_index(p_s)

    i_peak = int(np.argmax(p))
    if i_peak <= 0:
        return None

    pre_n = max(5, int(pre_n))
    start = max(0, i_peak - pre_n)
    end = i_peak  # exclude the peak itself
    if end - start < 5:
        return None

    w_d2 = d2[start:end]
    neg_vals = w_d2[w_d2 < 0]
    if len(neg_vals) == 0:
        # Fallback: most negative curvature inside the window
        return start + int(np.argmin(w_d2))

    thr = np.quantile(neg_vals, d2_neg_quantile)

    # Scan inside the window for first strong concavity drop while slope is positive but falling
    for k in range(start + 2, end):
        if d2[k] < thr and d1[k] > 0 and d1[k] < (0.9 * np.max(d1[start:k])):
            return k

    # Fallback: most negative curvature point
    return start + int(np.argmin(w_d2))


def make_fit_report(df, options, details, metrics):
    """One-page landscape PDF showing the plotted data and engineering summary."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.utils import ImageReader
    from reportlab.lib import colors

    # Independent static rendering of the same series shown by Plotly.
    fig, ax = plt.subplots(figsize=(12.2, 6.1), dpi=135)
    fig.patch.set_facecolor("white")
    ax.plot(df["idx"], df["pressure_raw"], label="Pressure (raw)", linewidth=1.25, color="#17699A")
    if options["smooth"]:
        ax.plot(df["idx"], df["pressure"], label="Pressure (smoothed)",
                linewidth=1.45, color="#E09029")
    chosen = options["selected_index"]
    if chosen is not None:
        ax.scatter([df.loc[chosen, "idx"]], [df.loc[chosen, "pressure"]],
                   s=58, zorder=5, label="Selected leak-off", color="#C64748")
    if options["d1"] or options["d2"]:
        ax2 = ax.twinx()
        if options["d1"]:
            ax2.plot(df["idx"], df["dP_di"], label="dP/di",
                     linewidth=1, alpha=0.65, color="#31A17D")
        if options["d2"]:
            ax2.plot(df["idx"], df["d2P_di2"], label="d²P/di²",
                     linewidth=1, alpha=0.65, color="#8A5CC9")
        ax2.set_ylabel("Derivatives", fontsize=9)
        lines, labels = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines + lines2, labels + labels2,
                  loc="upper center", bbox_to_anchor=(0.5, 1.13),
                  ncol=3, fontsize=8, frameon=False)
    else:
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.13),
                  ncol=3, fontsize=8, frameon=False)
    ax.set_xlabel("Index (i)", fontsize=10)
    ax.set_ylabel("Pressure (psi)", fontsize=10)
    ax.grid(True, alpha=0.18)
    ax.tick_params(labelsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    image = io.BytesIO()
    fig.savefig(image, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    image.seek(0)

    buffer = io.BytesIO()
    page_w, page_h = landscape(letter)
    pdf = canvas.Canvas(buffer, pagesize=(page_w, page_h))
    pdf.setTitle("Pressure Test Report - " + details["Well"])
    pdf.setAuthor(details["Prepared By"])
    navy = colors.HexColor("#18324E")
    pdf.setFillColor(navy)
    pdf.rect(0, page_h - 9, page_w, 9, stroke=0, fill=1)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(30, page_h - 34, "PRESSURE TEST REPORT")

    def field(label, value, x, y, max_width):
        pdf.setFont("Helvetica-Bold", 8)
        pdf.setFillColor(navy)
        pdf.drawString(x, y, label + ":")
        label_width = pdf.stringWidth(label + ": ", "Helvetica-Bold", 8)
        pdf.setFont("Helvetica", 8)
        pdf.setFillColor(colors.HexColor("#42546A"))
        text = str(value or "—")
        allowed = max_width - label_width
        while text and pdf.stringWidth(text, "Helvetica", 8) > allowed:
            text = text[:-1]
        pdf.drawString(x + label_width, y, text)

    field("Company", details["Company"], 30, page_h - 55, 230)
    field("Well", details["Well"], 288, page_h - 55, 230)
    field("Section", details["Section"], 555, page_h - 55, 220)
    field("Date", details["Date"], 30, page_h - 71, 160)
    field("Version", details["Version"], 220, page_h - 71, 130)
    field("Prepared by", details["Prepared By"], 390, page_h - 71, 350)
    pdf.setStrokeColor(colors.HexColor("#C6D4DF"))
    pdf.line(30, page_h - 80, page_w - 30, page_h - 80)

    # Chart occupies the main report area while retaining its aspect ratio.
    img = ImageReader(image)
    iw, ih = img.getSize()
    box_w, box_h = page_w - 60, 390
    ratio = min(box_w / iw, box_h / ih)
    w, h = iw * ratio, ih * ratio
    pdf.drawImage(img, (page_w - w) / 2, 125 + (box_h - h) / 2,
                  width=w, height=h, preserveAspectRatio=True, mask="auto")

    pdf.setFillColor(colors.HexColor("#F1F5F8"))
    pdf.roundRect(30, 57, page_w - 60, 64, 7, stroke=0, fill=1)
    summary_fields = [
        ("Rows", str(metrics["rows"])),
        ("Max pressure", f'{metrics["max_pressure_psi"]:,.1f} psi'),
        ("Selected pressure", "—" if metrics["pressure_psi"] is None
         else f'{metrics["pressure_psi"]:,.1f} psi'),
        ("Gradient", "—" if metrics["gradient"] is None
         else f'{metrics["gradient"]:.4f} psi/ft'),
        ("EMW", "—" if metrics["emw"] is None
         else f'{metrics["emw"]:.2f} ppg'),
    ]
    slot = (page_w - 64) / len(summary_fields)
    for i, (label, value) in enumerate(summary_fields):
        x = 38 + i * slot
        pdf.setFont("Helvetica", 8)
        pdf.setFillColor(colors.HexColor("#617487"))
        pdf.drawString(x, 98, label)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.setFillColor(navy)
        pdf.drawString(x, 79, value)
    pdf.setFont("Helvetica", 7.5)
    pdf.setFillColor(colors.HexColor("#637284"))
    pdf.drawString(30, 37,
        f'TVD: {metrics["tvd_ft"]:,.1f} ft  |  Mud weight: {metrics["mud_weight_ppg"]:.2f} ppg  |  '
        f'Leak-off index: {metrics["index"] if metrics["index"] is not None else "N/A"}')
    pdf.drawRightString(page_w - 30, 24, "Page 1 of 1")
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


def project_report_defaults():
    """Prefill values from the selected well without changing the analysis."""
    active_id = st.session_state.get("active_well_id")
    if active_id is None:
        return "", ""
    try:
        from project_store import wells
        well = next((w for w in wells() if w["id"] == active_id), None)
        return (well["company_name"], well["name"]) if well else ("", "")
    except Exception:
        return "", ""

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Pressure Testing App V3.1", layout="wide")
st.title("Pressure Testing App V3.1 (Index-based)")

with st.sidebar:
    st.header("1) Load Data")
    src = st.radio("Input method", ["Upload CSV", "Paste text"], horizontal=True)

    uploaded = None
    pasted = None
    if src == "Upload CSV":
        uploaded = st.file_uploader("Upload a CSV with Time, Pressure, Strokes", type=["csv"])
    else:
        pasted = st.text_area("Paste CSV text (headers: Time,Pressure,Strokes)", height=150)

    st.markdown("---")
    st.header("2) Parameters")
    tvd_ft = st.number_input("TVD / Depth (ft)", min_value=0.0, value=0.0, step=50.0)
    mud_weight_ppg = st.number_input("Mud Weight (ppg)", min_value=0.0, value=9.0, step=0.1)

    sg_enabled = st.checkbox("Enable smoothing", value=True)
    sg_window = st.slider("Smoothing window (odd)", min_value=3, max_value=51, value=9, step=2)
    sg_poly = st.slider("Smoothing polyorder", min_value=1, max_value=5, value=2)

    st.markdown("**Detection Window (pre-peak)**")
    pre_n = st.slider("Points to analyze before the peak (N)", min_value=5, max_value=300, value=30, step=1,
                      help="Leak-off is searched only within the last N points right before the global pressure peak.")
    d2_q = st.slider("Curvature negativity quantile", 0.0, 0.9, 0.2, step=0.05,
                     help="Sensitivity threshold: lower = stricter (more negative) curvature required.")

    st.markdown("---")
    st.header("3) Manual Override")
    override_value = st.text_input("Override by index (leave blank to use auto)", value="")

    st.markdown("---")
    st.header("4) Display")
    show_d1 = st.checkbox("Overlay dP/di (1st derivative)", value=True)
    show_d2 = st.checkbox("Overlay d²P/di² (2nd derivative)", value=False)

# Load data
if uploaded is not None:
    try:
        raw_df = pd.read_csv(uploaded)
    except Exception as e:
        st.error(f"Failed to read CSV: {e}")
elif pasted:
    try:
        raw_df = pd.read_csv(io.StringIO(pasted))
    except Exception as e:
        st.error(f"Failed to parse pasted CSV: {e}")
else:
    raw_df = None

if raw_df is not None and not raw_df.empty:
    # Map columns (case-insensitive)
    cols_lower = {c.lower(): c for c in raw_df.columns}
    def pick(*names):
        for n in names:
            if n in cols_lower:
                return cols_lower[n]
        return None

    c_time = pick('time')  # for display only
    c_press = pick('pressure', 'p', 'psi')
    c_stk = pick('strokes', 'stk', 'stroke')

    if c_press is None:
        st.warning("Missing required column: pressure.")
    else:
        # Build working frame in ORIGINAL FILE ORDER
        df = pd.DataFrame()
        if c_time:
            df['Time'] = raw_df[c_time]
        df['pressure'] = pd.to_numeric(raw_df[c_press], errors='coerce')
        if c_stk:
            df['strokes'] = pd.to_numeric(raw_df[c_stk], errors='coerce')

        # Drop rows with missing pressure (keep row order)
        keep_mask = df['pressure'].notna()
        df = df[keep_mask].reset_index(drop=True)

        # Index for plotting/derivatives
        df['idx'] = np.arange(len(df))

        # Preserve raw pressure; optionally smooth for analysis/plot
        df['pressure_raw'] = df['pressure']
        if sg_enabled:
            df['pressure'] = smooth_series(df['pressure'].values, window=sg_window, poly=sg_poly)

        # Derivatives with respect to index
        d1, d2 = compute_derivatives_index(df['pressure'].values)
        df['dP_di'] = d1
        df['d2P_di2'] = d2

        # --- Leakoff detection using last N points pre-peak ---
        idx_auto = detect_leakoff_lastN(df, pre_n=pre_n, d2_neg_quantile=d2_q)
        idx_pick = idx_auto

        # Manual override by index (if provided)
        if override_value.strip():
            try:
                idx = int(float(override_value))
                if 0 <= idx < len(df):
                    idx_pick = idx
                    st.info(f"Manual override → index {idx_pick}")
                else:
                    st.warning("Override index out of range; using auto-detected value.")
            except Exception as e:
                st.warning(f"Failed to apply override: {e}. Using auto-detected value.")

        # Summary values and gradient
        lop_index = lop_pressure = lop_strokes = gradient = emw_ppg = None
        if idx_pick is not None:
            lop_index = int(idx_pick)
            # Leakoff Pressure from the chosen index
            lop_pressure = float(df.loc[idx_pick, 'pressure'])
            lop_strokes = float(df.loc[idx_pick, 'strokes']) if 'strokes' in df else None
            gradient = (lop_pressure / tvd_ft) if tvd_ft and tvd_ft > 0 else None
            # EMW (FIT/LOT) using formula: EMW = Mud Weight + Pressure / (0.052 * TVD)
            if tvd_ft and tvd_ft > 0:
                emw_ppg = float(mud_weight_ppg + (lop_pressure / (0.052 * tvd_ft)))

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.metric("Rows", len(df))
        with c2:
            st.metric("Max Pressure (psi)", f"{df['pressure_raw'].max():.1f}")
        with c3:
            st.metric("Leak-Off Pressure (psi)", f"{lop_pressure:.1f}" if lop_pressure is not None else "—")
        with c4:
            st.metric("Gradient (psi/ft)", f"{gradient:.4f}" if gradient is not None else "—")
        with c5:
            st.metric("FIT/LOT EMW (ppg)", f"{emw_ppg:.2f}" if emw_ppg is not None else "—")

        # Chart: Pressure + optional derivatives
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['idx'], y=df['pressure_raw'], name='Pressure (raw)', mode='lines'))
        if sg_enabled:
            fig.add_trace(go.Scatter(x=df['idx'], y=df['pressure'], name='Pressure (smoothed)', mode='lines'))
        if idx_pick is not None:
            fig.add_trace(go.Scatter(x=[df.loc[idx_pick, 'idx']], y=[df.loc[idx_pick, 'pressure']],
                                     mode='markers', name='Leak-Off', marker=dict(size=10)))
        if show_d1:
            fig.add_trace(go.Scatter(x=df['idx'], y=df['dP_di'], name='dP/di', mode='lines', yaxis='y2'))
        if show_d2:
            fig.add_trace(go.Scatter(x=df['idx'], y=df['d2P_di2'], name='d²P/di²', mode='lines', yaxis='y2'))

        fig.update_layout(
            title='Pressure (and derivatives) vs Index',
            xaxis_title='Index (i)',
            yaxis=dict(title='Pressure (psi)'),
            yaxis2=dict(title='Derivatives', overlaying='y', side='right', showgrid=False),
            height=520,
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0)
        )
        st.plotly_chart(fig, use_container_width=True)


        # Static print report uses the same processed data and selected analysis point.
        st.subheader("Print-ready pressure test report")
        st.caption("Generate a landscape PDF containing the plotted pressure curves, selected leak-off point, and key results.")
        project_company, project_well = project_report_defaults()
        project_key = st.session_state.get("active_well_id")
        if st.session_state.get("_fit_report_project") != project_key:
            st.session_state["_fit_report_project"] = project_key
            st.session_state["fit_report_company"] = project_company
            st.session_state["fit_report_well"] = project_well
        report_a, report_b, report_c = st.columns(3)
        with report_a:
            company = st.text_input("Company Name", key="fit_report_company")
            well = st.text_input("Well Name", key="fit_report_well")
        with report_b:
            section = st.text_input("Section", key="fit_report_section")
            report_date = st.date_input("Report Date", value=date.today(), key="fit_report_date")
        with report_c:
            version = st.text_input("Version", value="1.0", key="fit_report_version")
            prepared_by = st.text_input("Prepared By", key="fit_report_prepared_by")
        if st.button("Prepare PDF report", key="fit_create_pdf"):
            try:
                report_details = {
                    "Company": company, "Well": well, "Section": section,
                    "Date": report_date.strftime("%Y-%m-%d"),
                    "Version": version, "Prepared By": prepared_by,
                }
                report_metrics = {
                    "rows": int(len(df)),
                    "max_pressure_psi": float(df["pressure_raw"].max()),
                    "pressure_psi": lop_pressure,
                    "gradient": gradient,
                    "emw": emw_ppg,
                    "tvd_ft": float(tvd_ft),
                    "mud_weight_ppg": float(mud_weight_ppg),
                    "index": lop_index,
                }
                st.session_state["fit_report_pdf"] = make_fit_report(
                    df,
                    {"smooth": sg_enabled, "d1": show_d1, "d2": show_d2, "selected_index": idx_pick},
                    report_details, report_metrics,
                )
            except Exception as exc:
                st.error(f"Failed to generate PDF: {exc}")
        if st.session_state.get("fit_report_pdf"):
            st.download_button(
                "Download Print-Ready PDF",
                data=st.session_state["fit_report_pdf"],
                file_name="FIT_pressure_test_report.pdf",
                mime="application/pdf",
                key="fit_download_pdf",
            )

        # Data table — include Time for context (display only)
        st.subheader("Processed Data")
        display_cols = []
        if 'Time' in df.columns:
            display_cols.append('Time')
        display_cols += ['idx', 'pressure_raw']
        if sg_enabled:
            display_cols.append('pressure')
        if 'strokes' in df:
            display_cols.append('strokes')
        display_cols += ['dP_di', 'd2P_di2']
        st.dataframe(df[display_cols], use_container_width=True, height=340)

        # Exports
        st.subheader("Export")
        csv_buf = io.StringIO()
        df.to_csv(csv_buf, index=False)
        st.download_button("Download processed CSV", data=csv_buf.getvalue(), file_name="processed_v3_1.csv")

        summary = {
            "leakoff": {
                "index": int(lop_index) if lop_index is not None else None,
                "pressure_psi": float(lop_pressure) if lop_pressure is not None else None,
                "strokes": float(lop_strokes) if lop_strokes is not None else None,
            },
            "depth_ft": float(tvd_ft) if tvd_ft else None,
            "mud_weight_ppg": float(mud_weight_ppg) if mud_weight_ppg is not None else None,
            "gradient_psi_per_ft": float(gradient) if gradient is not None else None,
            "emw_ppg": float(emw_ppg) if emw_ppg is not None else None,
            "max_pressure_psi": float(df['pressure_raw'].max()),
            "rows": int(len(df)),
            "smoothing": {
                "enabled": bool(sg_enabled),
                "window": int(sg_window),
                "polyorder": int(sg_poly)
            },
            "detection_params": {
                "pre_n": int(pre_n),
                "d2_neg_quantile": float(d2_q)
            }
        }
        json_buf = io.StringIO()
        json.dump(summary, json_buf, indent=2)
        st.download_button("Download summary JSON", data=json_buf.getvalue(), file_name="summary_v3_1.json")
else:
    st.info("Upload or paste your CSV to begin. Required: Pressure. Optional: Time, Strokes.")
