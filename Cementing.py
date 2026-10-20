"""Cementing worksheet: saved tallies, depth-based annular capacities, pump strokes and schematic."""
import math
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from cement_calcs import (
    split_casing_capacity, segment_volumes, check_intervals, triplex_gal_per_stroke
)
from project_store import (
    wells, list_casing_tallies, load_casing_tally,
    save_cement_scenario, load_cement_scenario,
)

st.set_page_config(page_title="Cementing Volumes", layout="wide")
st.title("Cementing Volumes")
st.caption("A preliminary, depth-based casing and annular capacity worksheet linked to your saved Casing Tally.")

well_id = st.session_state.get("active_well_id")
if well_id is None:
    st.warning("Select a well in the toolbox sidebar first.")
    st.stop()
well = next((x for x in wells() if x["id"] == well_id), None)
if well is None:
    st.error("The selected well cannot be found.")
    st.stop()
st.info(f'**{well["company_name"]}** / **{well["name"]}**')
tallies = list_casing_tallies(well_id)
if not tallies:
    st.warning("No saved tally for this well. Run Casing Tally, then save the tally snapshot.")
    st.stop()
lookup = {x["id"]: x for x in tallies}
tally_id = st.selectbox(
    "Saved Casing Tally", list(lookup),
    format_func=lambda n: f'{lookup[n]["name"]} · {lookup[n]["section"] or "No section"} · {lookup[n]["created_at"]} (#{n})',
)
tally = load_casing_tally(tally_id, well_id)
included = [r for r in tally["rows"] if bool(r.get("Used", False))]
if not included:
    st.error("The selected tally contains no included joints.")
    st.stop()
try:
    casing_length = sum(float(r["Length"]) for r in included)
    unique_od = sorted({round(float(r["OD"]), 4) for r in included})
    if casing_length <= 0 or any(float(r["ID"]) <= 0 or float(r["OD"]) <= 0 for r in included):
        raise ValueError("Each included joint needs valid length, ID, and OD.")
except (TypeError, ValueError, KeyError) as error:
    st.error(f"Cannot use this saved tally: {error}")
    st.stop()
st.caption(f'Included joints: {len(included)}  |  Casing length: {casing_length:,.2f} ft')
if len(unique_od) > 1:
    st.warning("Multiple OD values exist in the tally. The simplified schematic uses an illustrative OD; set the correct OD within each annular interval.")

scenario_key = f"cement_worksheet_{well_id}_{tally_id}"
if scenario_key not in st.session_state:
    saved = load_cement_scenario(well_id, tally_id)
    st.session_state[scenario_key] = saved or {
        "shoe_md": float(round(casing_length, 2)),
        "shoe_length": min(80.0, casing_length),
        "bottom_last": True,
        "method": "Manual gal/stroke",
        "gal_stroke": 0.0, "liner": 6.0, "stroke": 12.0,
        "efficiency": 95.0,
        "segments": [{
            "Section": "Open hole", "Type": "Open hole",
            "Start MD (ft)": 0.0, "End MD (ft)": float(round(casing_length, 2)),
            "Outer ID (in)": 0.0, "Casing OD (in)": float(unique_od[0]),
            "Excess (%)": 0.0,
        }],
    }
initial = st.session_state[scenario_key]

st.subheader("1. Casing geometry and shoe track")
st.caption("All depths are measured depth (MD) in feet. Shoe MD is the bottom of the new casing string. The top MD is derived from saved tally length.")
st.subheader("2. Annular sections — depth intervals")
st.caption("Add each previous casing / open-hole interval by its start and end MD. Set Outer ID to the previous casing ID or open-hole diameter. Open-hole excess applies only to Open hole rows.")
st.subheader("3. Pump specifications")
st.caption("The pump can be entered directly in gal/stroke or calculated from a single-acting triplex pump. All edits are applied together when you click Save & Run.")

with st.form(f"cement_form_{well_id}_{tally_id}", clear_on_submit=False):
    c1, c2, c3 = st.columns(3)
    with c1:
        shoe_md = st.number_input(
            "New casing shoe MD (ft)", min_value=0.0, value=float(initial["shoe_md"]),
            step=50.0, format="%.2f")
    with c2:
        shoe_track_ft = st.number_input(
            "Shoe track length (ft)", min_value=0.0, max_value=float(casing_length),
            value=min(float(initial["shoe_length"]), float(casing_length)), step=5.0, format="%.2f")
    with c3:
        orientation = st.selectbox(
            "Shoe / bottom position in tally", ["Last row", "First row"],
            index=0 if initial["bottom_last"] else 1,
        )
    st.caption(f"Casing top MD = shoe MD − {casing_length:,.2f} ft (included joint lengths).")

    editor = st.data_editor(
        pd.DataFrame(initial["segments"]),
        num_rows="dynamic", hide_index=True, use_container_width=True,
        key=f"cement_editor_{well_id}_{tally_id}",
        column_config={
            "Section": st.column_config.TextColumn("Section / Description", required=True),
            "Type": st.column_config.SelectboxColumn(
                "Type", options=["Open hole", "Cased hole"], required=True),
            "Start MD (ft)": st.column_config.NumberColumn(
                "Start MD (ft)", min_value=0.0, format="%.2f", required=True),
            "End MD (ft)": st.column_config.NumberColumn(
                "End MD (ft)", min_value=0.0, format="%.2f", required=True),
            "Outer ID (in)": st.column_config.NumberColumn(
                "Hole diameter / previous casing ID (in)", min_value=0.0, format="%.3f", required=True),
            "Casing OD (in)": st.column_config.NumberColumn(
                "New casing OD (in)", min_value=0.0, format="%.3f", required=True),
            "Excess (%)": st.column_config.NumberColumn(
                "OH excess (%)", min_value=0.0, format="%.1f", required=True),
        },
    )
    method = st.selectbox(
        "Pump input method", ["Manual gal/stroke", "Single-acting triplex"],
        index=0 if initial["method"] == "Manual gal/stroke" else 1)
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        direct = st.number_input("Pump output (gal/stroke)", min_value=0.0,
                                 value=float(initial["gal_stroke"]), format="%.3f", step=0.01)
    with p2:
        liner = st.number_input("Triplex liner diameter (in)", min_value=0.0,
                                value=float(initial["liner"]), step=0.25)
    with p3:
        stroke = st.number_input("Triplex stroke length (in)", min_value=0.0,
                                 value=float(initial["stroke"]), step=0.5)
    with p4:
        efficiency = st.number_input("Volumetric efficiency (%)", min_value=0.1,
                                     max_value=100.0, value=float(initial["efficiency"]), step=1.0)
    submit = st.form_submit_button("Save & Run Cementing Volumes", type="primary", use_container_width=True)

if submit:
    try:
        if not math.isfinite(shoe_md) or shoe_md < casing_length - 0.001:
            raise ValueError("Shoe MD cannot be shallower than the total casing string length.")
        casing_top = shoe_md - casing_length
        if editor.empty:
            raise ValueError("Add at least one annular section.")
        if editor.isna().any().any():
            raise ValueError("Fill all cells in every annular section.")
        records = editor.to_dict("records")
        calculated = segment_volumes(records)
        gaps = check_intervals(calculated, casing_top, shoe_md)
        inside = split_casing_capacity(included, shoe_track_ft,
                                       bottom_last=orientation == "Last row")
        pump_gal = (float(direct) if method == "Manual gal/stroke"
                    else triplex_gal_per_stroke(float(liner), float(stroke), float(efficiency) / 100))
        if not math.isfinite(pump_gal) or pump_gal <= 0:
            raise ValueError("Provide a pump displacement greater than zero.")
        payload = {
            "shoe_md": shoe_md, "shoe_length": shoe_track_ft,
            "bottom_last": orientation == "Last row", "method": method,
            "gal_stroke": direct, "liner": liner, "stroke": stroke,
            "efficiency": efficiency, "segments": records,
        }
        # Save project worksheet only after validation succeeds.
        save_cement_scenario(well_id, tally_id, payload)
        st.session_state[scenario_key] = payload
        st.session_state[f"cement_result_{well_id}_{tally_id}"] = {
            "inside": inside, "segments": calculated, "gaps": gaps,
            "shoe_md": shoe_md, "casing_top": casing_top, "pump_gal": pump_gal,
            "shoe_track_ft": shoe_track_ft,
        }
        st.success("Worksheet saved to this well and volumes calculated.")
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        st.error(f"Please review your inputs: {error}")

result = st.session_state.get(f"cement_result_{well_id}_{tally_id}")
if result:
    segments = result["segments"]
    inside = result["inside"]
    annular = sum(float(x["Adjusted (bbl)"]) for x in segments)
    st.divider()
    st.subheader("Calculated volumes")
    a, b, c, d = st.columns(4)
    a.metric("Shoe track", f'{inside["shoe_bbl"]:,.2f} bbl')
    b.metric("Inside casing above shoe", f'{inside["above_bbl"]:,.2f} bbl')
    c.metric("Annulus incl. excess", f'{annular:,.2f} bbl')
    d.metric("Pump displacement", f'{result["pump_gal"]:,.3f} gal/stroke')
    st.subheader("Annular volumes by casing / hole section")
    st.caption("Nominal capacity (bbl/ft) is calculated from the hole or previous casing ID and the new casing OD. It excludes all open-hole excess.")
    section_df = pd.DataFrame(segments).copy()
    section_df["Excess added (bbl)"] = section_df["Adjusted (bbl)"] - section_df["Nominal (bbl)"]
    section_df["Strokes (theoretical)"] = (
        section_df["Adjusted (bbl)"] * 42 / result["pump_gal"]
    )
    display_cols = [
        "Section", "Type", "Start MD (ft)", "End MD (ft)", "Length (ft)",
        "Outer ID (in)", "Casing OD (in)", "Nominal capacity (bbl/ft)", "Excess (%)",
        "Nominal (bbl)", "Excess added (bbl)", "Adjusted (bbl)",
        "Strokes (theoretical)",
    ]
    st.dataframe(
        section_df[display_cols].style.format({
            "Start MD (ft)": "{:,.2f}", "End MD (ft)": "{:,.2f}",
            "Length (ft)": "{:,.2f}", "Outer ID (in)": "{:.3f}",
            "Casing OD (in)": "{:.3f}", "Nominal capacity (bbl/ft)": "{:.5f}",
            "Excess (%)": "{:.1f}",
            "Nominal (bbl)": "{:,.2f}", "Excess added (bbl)": "{:,.2f}",
            "Adjusted (bbl)": "{:,.2f}", "Strokes (theoretical)": "{:,.1f}",
        }),
        hide_index=True, use_container_width=True,
    )

    # Preserve previous casing identity: user-entered Section labels identify each
    # previous casing string. Sum repeated intervals without combining unrelated IDs.
    by_casing = (
        section_df.groupby(
            ["Type", "Section", "Outer ID (in)", "Casing OD (in)"],
            as_index=False, sort=False,
        )[["Length (ft)", "Nominal (bbl)", "Excess added (bbl)",
           "Adjusted (bbl)", "Strokes (theoretical)"]].sum()
    )
    # For grouped intervals, compute nominal capacity from total nominal
    # volume / total footage (weighted if the grouped inputs ever vary).
    by_casing["Nominal capacity (bbl/ft)"] = (
        by_casing["Nominal (bbl)"] / by_casing["Length (ft)"]
    )
    st.markdown("**Subtotal by previous casing / open-hole section**")
    st.dataframe(
        by_casing.style.format({
            "Outer ID (in)": "{:.3f}", "Casing OD (in)": "{:.3f}",
            "Length (ft)": "{:,.2f}", "Nominal capacity (bbl/ft)": "{:.5f}",
            "Nominal (bbl)": "{:,.2f}",
            "Excess added (bbl)": "{:,.2f}", "Adjusted (bbl)": "{:,.2f}",
            "Strokes (theoretical)": "{:,.1f}",
        }), hide_index=True, use_container_width=True,
    )
    open_hole_bbl = float(
        section_df.loc[section_df["Type"] == "Open hole", "Adjusted (bbl)"].sum()
    )
    cased_hole_bbl = float(
        section_df.loc[section_df["Type"] == "Cased hole", "Adjusted (bbl)"].sum()
    )
    oh_col, ch_col, total_col = st.columns(3)
    oh_col.metric("Open-hole annulus (incl. excess)", f"{open_hole_bbl:,.2f} bbl")
    ch_col.metric("Cased-hole annulus", f"{cased_hole_bbl:,.2f} bbl")
    total_col.metric("Total annulus", f"{annular:,.2f} bbl")

    summary = pd.DataFrame([
        {"Volume": "Shoe track", "Barrels": inside["shoe_bbl"]},
        {"Volume": "Casing ID above shoe track", "Barrels": inside["above_bbl"]},
        {"Volume": "Total casing internal", "Barrels": inside["internal_bbl"]},
        {"Volume": "Open-hole annulus, including excess", "Barrels": open_hole_bbl},
        {"Volume": "Cased-hole annulus", "Barrels": cased_hole_bbl},
        {"Volume": "Total annulus, including OH excess", "Barrels": annular},
        {"Volume": "Sum of casing interior and annulus (not pumping schedule)",
         "Barrels": inside["internal_bbl"] + annular},
    ])
    summary["Gallons"] = summary["Barrels"] * 42
    summary["Strokes (theoretical)"] = summary["Gallons"] / result["pump_gal"]
    st.dataframe(summary.style.format({
        "Barrels": "{:,.3f}", "Gallons": "{:,.1f}",
        "Strokes (theoretical)": "{:,.1f}"}), use_container_width=True, hide_index=True)
    if result["gaps"]:
        gaps_text = ", ".join(f'{a:,.2f}–{b:,.2f} ft' for a,b in result["gaps"])
        st.warning(f"Unmodeled annular interval(s): {gaps_text}. These depths are omitted from annular volume totals.")

    st.subheader("Wellbore schematic")
    st.caption("Schematic based on submitted depths and diameters, not to engineering scale. Depth increases downward; previous casing and open hole are distinguished by color.")
    fig = go.Figure()
    max_diam = max(float(x["Outer ID (in)"]) for x in segments)
    new_od = float(unique_od[0])
    new_id = float(included[0]["ID"])
    # Sections provide surrounding bore geometry, colored by open/cased hole.
    for section in segments:
        top = float(section["Start MD (ft)"])
        bottom = float(section["End MD (ft)"])
        radius = float(section["Outer ID (in)"]) / 2
        kind = section["Type"]
        color = "#C7D6E7" if kind == "Cased hole" else "#EAD7BC"
        fig.add_shape(type="rect", x0=-radius, x1=radius,
                      y0=top, y1=bottom, line=dict(color="#7B8A99", width=1.2),
                      fillcolor=color, layer="below")
        fig.add_annotation(x=radius + max_diam*.10, y=(top+bottom)/2,
                           text=f'{section["Section"]} · {kind}<br>{top:,.0f}–{bottom:,.0f} ft',
                           showarrow=False, xanchor="left", align="left", font=dict(size=10))
        fig.add_annotation(x=-radius-max_diam*.08, y=(top+bottom)/2,
                           text=f'{float(section["Outer ID (in)"]):g}"',
                           showarrow=False, xanchor="right", font=dict(size=10))
    # New casing walls and interior. Uniform diameter for illustration only.
    top = result["casing_top"]
    bottom = result["shoe_md"]
    for lo,hi in [(-new_od/2,-new_id/2),(new_id/2,new_od/2)]:
        fig.add_shape(type="rect",x0=lo,x1=hi,y0=top,y1=bottom,
                      fillcolor="#244C70",line=dict(width=0))
    fig.add_shape(type="rect", x0=-new_id/2, x1=new_id/2, y0=top,
                  y1=bottom, fillcolor="#FFFFFF", line=dict(width=0),layer="below")
    shoe_top = bottom - result["shoe_track_ft"]
    fig.add_shape(type="rect", x0=-new_id/2, x1=new_id/2,
                  y0=shoe_top, y1=bottom, fillcolor="#9AD1C2",
                  opacity=0.8,line=dict(width=0))
    fig.add_shape(type="line",x0=-new_od/2,x1=new_od/2,y0=bottom,y1=bottom,
                  line=dict(color="#12334F",width=4))
    fig.add_annotation(x=0,y=bottom,text="Shoe",showarrow=True,ay=28,font=dict(size=10))
    # Fix the horizontal bounds and prevent zoom interactions from distorting
    # the diameter scale. Only depth is zoomable. Plotly range is specified
    # descending to guarantee 0/shallow MD at the TOP.
    diagram_top = min(
        result["casing_top"], min(float(x["Start MD (ft)"]) for x in segments)
    )
    diagram_bottom = max(
        result["shoe_md"], max(float(x["End MD (ft)"]) for x in segments)
    )
    depth_padding = max((diagram_bottom - diagram_top) * 0.03, 1.0)
    fig.update_layout(
        height=700, autosize=True,
        margin=dict(t=18, b=22, l=72, r=190),
        dragmode="zoom",
        xaxis=dict(
            title=None, range=[-max_diam * 0.95, max_diam * 1.45],
            fixedrange=True, zeroline=False, showgrid=False,
            showticklabels=False, ticks="", showline=False,
        ),
        yaxis=dict(
            title="Measured depth (ft MD)",
            range=[diagram_bottom + depth_padding, max(0, diagram_top - depth_padding)],
            autorange=False, showgrid=True, tickformat=",.0f",
        ),
        plot_bgcolor="white", paper_bgcolor="white", showlegend=False,
        uirevision=f"cement-schematic-{well_id}-{tally_id}",
    )
    st.caption("The horizontal diameter scale is locked; scroll or drag to zoom depth. Use the plot toolbar's Reset axes button to restore the full well view.")
    st.plotly_chart(fig, use_container_width=True)
    csv_export = pd.concat([
        section_df.assign(Report_Table="Detailed annular sections"),
        by_casing.assign(Report_Table="Annulus subtotal by casing"),
    ], ignore_index=True, sort=False)
    st.download_button(
        "Download annular breakdown CSV",
        data=csv_export.to_csv(index=False).encode("utf-8"),
        file_name="cementing_annular_breakdown.csv", mime="text/csv",
    )
    st.download_button("Download calculations CSV",
        data=summary.to_csv(index=False).encode("utf-8"),
        file_name="cementing_volumes.csv", mime="text/csv")
    st.warning("Preliminary theoretical capacities and strokes only. This is not a verified cement-job pumping schedule. Check volumes, depth references, pipe dimensions, excess factors, slurry yields, plug/spacer displacement, float equipment, pump calibration and operational constraints before field use.")
