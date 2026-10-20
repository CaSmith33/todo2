"""Main entry point for the Drilling Engineering Toolbox."""
import streamlit as st
from project_store import initialize, wells

st.set_page_config(page_title="Drilling Engineering Toolbox", page_icon="🛢️", layout="wide")
initialize()

st.session_state.setdefault("active_well_id", None)
all_wells = wells()
well_lookup = {w["id"]: w for w in all_wells}
selected = st.session_state.active_well_id
if selected not in well_lookup:
    st.session_state.active_well_id = None

with st.sidebar:
    st.markdown("### 🛢️ Engineering Toolbox")
    st.caption("Development preview · no login")
    ids = [None] + list(well_lookup)
    current_idx = ids.index(st.session_state.active_well_id)
    active = st.selectbox(
        "Current well project",
        options=ids,
        index=current_idx,
        format_func=lambda value: "No well selected" if value is None else
        f'{well_lookup[value]["company_name"]} · {well_lookup[value]["name"]}',
    )
    st.session_state.active_well_id = active
    if active is not None:
        st.caption(f'Status: {well_lookup[active]["status"]}')
    st.divider()

navigation = st.navigation({
    "Workspace": [
        st.Page("dashboard.py", title="Dashboard", icon="🏠", default=True),
        st.Page("projects.py", title="Companies & Wells", icon="📁"),
    ],
    "Engineering Tools": [
        st.Page("Tally.py", title="Casing Tally", icon="📏"),
        st.Page("FIT.py", title="FIT Analysis", icon="📈"),
    ],
})
navigation.run()
