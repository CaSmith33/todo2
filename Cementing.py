"""Cementing preliminary volumetrics based on a saved Casing Tally."""
import math
import pandas as pd
import streamlit as st
from cement_calcs import (split_casing_capacity, segment_volumes,
                          triplex_gal_per_stroke)
from project_store import wells, list_casing_tallies, load_casing_tally

st.set_page_config(page_title="Cementing Volumes", layout="wide")
st.title("Cementing Volumes")
st.caption("Load a saved casing tally, enter annular sections and open-hole excess, then calculate capacities and pump strokes.")

well_id = st.session_state.get("active_well_id")
if well_id is None:
    st.warning("Select a well project in the toolbox sidebar, then save a Casing Tally under that well.")
    st.stop()
well = next((w for w in wells() if w["id"] == well_id), None)
if well is None:
    st.error("The selected project no longer exists.")
    st.stop()
st.info(f'Project: **{well["company_name"]}** / **{well["name"]}**')

saved = list_casing_tallies(well_id)
if not saved:
    st.warning("No saved casing tallies for this well. Open Casing Tally, run the calculation, then select Save tally snapshot.")
    st.stop()
lookup = {t["id"]: t for t in saved}
selected_tally_id = st.selectbox("Saved casing tally", list(lookup),
    format_func=lambda i: f'{lookup[i]["name"]} · {lookup[i]["section"] or "Unspecified section"} · {lookup[i]["created_at"]} (#{i})')
tally = load_casing_tally(selected_tally_id, well_id)
if tally is None:
    st.error("Could not load the selected tally.")
    st.stop()
included = [r for r in tally["rows"] if bool(r.get("Used", False))]
if not included:
    st.error("The saved tally has no included joints.")
    st.stop()

try:
    string_length = sum(float(r["Length"]) for r in included)
    casing_ods = sorted({round(float(r["OD"]), 4) for r in included})
    if any(float(r["ID"]) <= 0 or float(r["OD"]) <= 0 for r in included):
        raise ValueError("All included joints need valid positive ID and OD.")
except (ValueError, TypeError, KeyError) as err:
    st.error(f"Invalid saved joint dimensions: {err}")
    st.stop()
st.write(f"**Included joints:** {len(included)}  ·  **String length:** {string_length:,.2f} ft")
if len(casing_ods) > 1:
    st.warning("The tally contains multiple casing ODs. Set the correct casing OD for each annular section below.")

st.subheader("1. Shoe track & internal casing volumes")
left, right = st.columns(2)
with left:
    bottom_last = st.radio("Saved tally orientation", ["Shoe / bottom is last row", "Shoe / bottom is first row"],
                           horizontal=False, help="Choose which end of the saved running order is at the casing shoe.")
    shoe_length = st.number_input("Shoe track length (ft)", min_value=0.0,
                                  max_value=float(string_length), value=min(80.0, float(string_length)),
                                  step=5.0)
with right:
    st.caption("Shoe track is measured UP from the casing shoe. Capacities use the ID of each included joint, and the final joint is split if necessary.")
    st.caption("Exclude joints in Casing Tally before saving. Accessories, float equipment and plug volumes are not independently modeled.")

st.subheader("2. Annular sections & open-hole excess")
st.caption("Enter each non-overlapping section along the cemented interval. Outer ID is hole diameter in open hole or the containing casing's drift/ID in cased hole. Only open-hole sections receive excess.")
segment_key = f"cement_segments_{well_id}_{selected_tally_id}"
default_od = float(casing_ods[0])
if segment_key not in st.session_state:
    st.session_state[segment_key] = pd.DataFrame([{
        "Section": "Open hole", "Type": "Open hole",
        "Length (ft)": float(string_length), "Outer ID (in)": 0.0,
        "Casing OD (in)": default_od, "Excess (%)": 0.0,
    }])
segments_input = st.data_editor(
    st.session_state[segment_key], num_rows="dynamic", hide_index=True,
    use_container_width=True, key=f"cement_grid_{well_id}_{selected_tally_id}",
    column_config={
        "Type": st.column_config.SelectboxColumn("Type", options=["Open hole", "Cased hole"], required=True),
        "Length (ft)": st.column_config.NumberColumn("Length (ft)", min_value=0.0, format="%.2f"),
        "Outer ID (in)": st.column_config.NumberColumn("Hole / host casing ID (in)", min_value=0.0, format="%.3f"),
        "Casing OD (in)": st.column_config.NumberColumn("String OD (in)", min_value=0.0, format="%.3f"),
        "Excess (%)": st.column_config.NumberColumn("OH excess (%)", min_value=0.0, format="%.1f"),
    }
)
st.session_state[segment_key] = segments_input.copy()

st.subheader("3. Pump specifications")
method = st.radio("Displacement input", ["Enter gal/stroke", "Calculate triplex pump output"],
                  horizontal=True)
if method == "Enter gal/stroke":
    gal_stroke = st.number_input("Pump output (gal/stroke)", min_value=0.0, value=0.0, step=0.01, format="%.3f")
else:
    p1, p2, p3 = st.columns(3)
    liner = p1.number_input("Liner diameter (in)", min_value=0.0, value=6.0, step=0.25)
    stroke = p2.number_input("Stroke length (in)", min_value=0.0, value=12.0, step=0.5)
    efficiency_pct = p3.number_input("Volumetric efficiency (%)", min_value=0.1, max_value=100.0, value=95.0, step=1.0)
    gal_stroke = triplex_gal_per_stroke(liner, stroke, efficiency_pct / 100)
    st.caption(f"Calculated single-acting triplex displacement: {gal_stroke:.3f} gal/stroke")

if st.button("Calculate cementing volumes", type="primary"):
    try:
        inside = split_casing_capacity(included, shoe_length,
            bottom_last=bottom_last == "Shoe / bottom is last row")
        if segments_input.empty:
            raise ValueError("Add at least one annular section.")
        if segments_input.isna().any().any():
            raise ValueError("Fill in all annular section cells, including excess percentage.")
        if not math.isfinite(float(gal_stroke)) or gal_stroke <= 0:
            raise ValueError("Pump displacement must be greater than zero.")
        calculated = segment_volumes(segments_input.to_dict("records"))
        if sum(v["Length (ft)"] for v in calculated) > string_length + 0.01:
            raise ValueError("Total annular section lengths exceed the included casing string length.")
        st.session_state["cement_result"] = {
            "well_id": well_id, "tally_id": selected_tally_id,
            "inside": inside, "segments": calculated, "gal_stroke": gal_stroke,
        }
    except (ValueError, TypeError, KeyError) as err:
        st.session_state.pop("cement_result", None)
        st.error(f"Please correct the input: {err}")

report = st.session_state.get("cement_result")
if report and report["well_id"] == well_id and report["tally_id"] == selected_tally_id:
    internal = report["inside"]
    sections = pd.DataFrame(report["segments"])
    annular = sections["Adjusted (bbl)"].sum()
    shoe = internal["shoe_bbl"]
    above = internal["above_bbl"]
    gal_per_stroke = report["gal_stroke"]
    st.subheader("Calculated capacity summary")
    a, b, c, d = st.columns(4)
    a.metric("Shoe track", f"{shoe:,.2f} bbl")
    b.metric("Casing ID above shoe", f"{above:,.2f} bbl")
    c.metric("Annulus incl. OH excess", f"{annular:,.2f} bbl")
    d.metric("Total internal", f"{internal['internal_bbl']:,.2f} bbl")
    st.dataframe(sections, hide_index=True, use_container_width=True)
    summary = pd.DataFrame([
        {"Volume": "Shoe track", "Barrels": shoe},
        {"Volume": "Inner casing above shoe track", "Barrels": above},
        {"Volume": "Total casing internal", "Barrels": internal["internal_bbl"]},
        {"Volume": "Annulus, adjusted for open-hole excess", "Barrels": annular},
        {"Volume": "Internal + annulus (geometric sum)", "Barrels": internal["internal_bbl"] + annular},
    ])
    summary["Gallons"] = summary["Barrels"] * 42
    summary["Pump strokes"] = summary["Gallons"] / gal_per_stroke
    st.dataframe(summary.style.format({"Barrels":"{:,.3f}", "Gallons":"{:,.1f}", "Pump strokes":"{:,.1f}"}),
                 hide_index=True, use_container_width=True)
    st.download_button("Download cementing calculations CSV",
        summary.to_csv(index=False).encode("utf-8"), file_name="cementing_volumes.csv", mime="text/csv")
    st.warning("Engineering check: these are theoretical capacities and corresponding pump strokes, NOT a verified cement job design or pumping sequence. Cement slurry yields, slurry mix volumes, displacement targets, spacers, float equipment, losses, washouts, compressibility, and actual pump calibration require separate review.")
