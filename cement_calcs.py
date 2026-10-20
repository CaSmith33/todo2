"""Preliminary cementing capacity math. All dimensions in inches and lengths in feet."""
from math import pi, isfinite

BBL_PER_CUFT = 1 / 5.614583333333333
GALLONS_PER_BBL = 42.0

def annular_bbl(length_ft, outer_id_in, inner_od_in):
    """Capacity of concentric annular space in barrels."""
    values = (length_ft, outer_id_in, inner_od_in)
    if any(not isfinite(float(v)) for v in values):
        raise ValueError("Geometry values must be finite.")
    if length_ft < 0 or inner_od_in < 0 or outer_id_in <= inner_od_in:
        raise ValueError("Annular outer diameter must exceed inner OD; length cannot be negative.")
    return (outer_id_in**2 - inner_od_in**2) * length_ft / 1029.4

def pipe_bbl(length_ft, inner_id_in):
    if length_ft < 0 or inner_id_in <= 0:
        raise ValueError("Pipe length and ID must be positive (length may be zero).")
    return inner_id_in**2 * length_ft / 1029.4

def split_casing_capacity(rows, shoe_length_ft, bottom_last=True):
    """Use EACH included joint's ID to partition capacity from casing shoe upward."""
    used = [r for r in rows if bool(r.get("Used", True))]
    if not used:
        raise ValueError("No included joints in saved tally.")
    total_length = sum(float(r["Length"]) for r in used)
    if shoe_length_ft < 0 or shoe_length_ft > total_length:
        raise ValueError("Shoe track length must fall within included tally length.")
    remaining_shoe = shoe_length_ft
    shoe_bbl = upper_bbl = 0.0
    walk = list(reversed(used)) if bottom_last else used
    for row in walk:
        length = float(row["Length"])
        inner = float(row["ID"])
        if length <= 0 or inner <= 0:
            raise ValueError("Included joint lengths and IDs must be positive.")
        assign_shoe = min(length, remaining_shoe)
        shoe_bbl += pipe_bbl(assign_shoe, inner)
        upper_bbl += pipe_bbl(length - assign_shoe, inner)
        remaining_shoe -= assign_shoe
    return {"length_ft": total_length, "shoe_length_ft": shoe_length_ft,
            "above_length_ft": total_length - shoe_length_ft,
            "shoe_bbl": shoe_bbl, "above_bbl": upper_bbl,
            "internal_bbl": shoe_bbl + upper_bbl}

def triplex_gal_per_stroke(liner_in, stroke_in, efficiency):
    if liner_in <= 0 or stroke_in <= 0 or not (0 < efficiency <= 1):
        raise ValueError("Pump dimensions must be positive and efficiency 0–100%.")
    # 3 single-acting plungers. Efficiency is a fraction.
    return (3 * pi / 4 * liner_in**2 * stroke_in / 231) * efficiency

def segment_volumes(segments):
    result = []
    for section in segments:
        length = float(section["Length (ft)"])
        bore = float(section["Outer ID (in)"])
        casing = float(section["Casing OD (in)"])
        excess = float(section["Excess (%)"]) if section["Type"] == "Open hole" else 0.0
        if excess < 0:
            raise ValueError("Excess percent must not be negative.")
        nominal = annular_bbl(length, bore, casing)
        result.append({**section, "Nominal (bbl)": nominal,
                       "Adjusted (bbl)": nominal * (1 + excess / 100)})
    return result
