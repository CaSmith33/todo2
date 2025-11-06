# # Pressure Testing App V3.1 – Streamlit (index-based only)
# -------------------------------------------------
# Updates:
# - Leak-off detection window is now the last **N points before the peak** (default N=30).
# - N is user-adjustable in the sidebar and replaces prior window/guard params.
# - All analysis remains index-based; time is display-only.
# -------------------------------------------------

import io
import json
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
