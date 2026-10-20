"""Workspace dashboard."""
import streamlit as st
from project_store import companies, wells

st.title("Drilling Engineering Toolbox")
st.caption("Your workspace for well projects, engineering calculations and reports.")

all_companies = companies()
all_wells = wells()
a,b,c = st.columns(3)
a.metric("Companies", len(all_companies))
b.metric("Well Projects", len(all_wells))
c.metric("Available Tools", 3)

st.subheader("Engineering tools")
one,two = st.columns(2)
with one:
    with st.container(border=True):
        st.markdown("#### 📏 Casing Tally")
        st.write("Import joint data, organize the load buffer, calculate forward/reverse tallies and print reports.")
        if st.button("Open Casing Tally", use_container_width=True):
            st.switch_page("Tally.py")
with two:
    with st.container(border=True):
        st.markdown("#### 📈 FIT Analysis")
        st.write("Analyze pressure tests with your existing FIT application.")
        if st.button("Open FIT Analysis", use_container_width=True):
            st.switch_page("FIT.py")

with st.container(border=True):
    st.markdown("#### 🧪 Cementing Volumes")
    st.write("Load a saved Casing Tally, calculate shoe track and annular capacities, open-hole excess and pump strokes.")
    if st.button("Open Cementing Volumes", use_container_width=True):
        st.switch_page("Cementing.py")

st.subheader("Well projects")
if not all_wells:
    st.info("No projects yet. Create a company, then create your first well.")
else:
    for w in all_wells:
        with st.container(border=True):
            st.markdown(f'**{w["name"]}**')
            st.caption(f'{w["company_name"]} · {w["location"] or "Location not set"} · {w["status"]}')
            if st.button("Set as active project", key=f'activate_{w["id"]}'):
                st.session_state.active_well_id = w["id"]
                st.rerun()
if st.button("Manage companies and wells"):
    st.switch_page("projects.py")
st.divider()
st.warning("Development mode: project records are stored locally in SQLite. No login or multi-user isolation is configured. Use test/nonconfidential data only; back up your projects before rebuilding a Codespace.")
