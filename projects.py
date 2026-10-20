"""Create and update company and well project records."""
import sqlite3
import streamlit as st
from project_store import companies, wells, create_company, create_well, update_well, export_json

st.title("Companies & Well Projects")
st.caption("Set up company and well information once, for reuse by the engineering tools.")

with st.expander("➕ Add a company", expanded=not bool(companies())):
    with st.form("create_company"):
        company_name = st.text_input("Company name")
        if st.form_submit_button("Create company"):
            try:
                create_company(company_name)
                st.success("Company created.")
                st.rerun()
            except (ValueError, sqlite3.IntegrityError) as error:
                st.error(str(error))

company_list = companies()
with st.expander("➕ Add a well project", expanded=bool(company_list) and not bool(wells())):
    if not company_list:
        st.info("Create a company first.")
    else:
        with st.form("create_well"):
            company_id = st.selectbox("Company", options=[c["id"] for c in company_list],
                format_func=lambda value: next(c["name"] for c in company_list if c["id"] == value))
            name = st.text_input("Well name *")
            left,right = st.columns(2)
            api_uwi = left.text_input("API / UWI")
            location = right.text_input("Location")
            status = st.selectbox("Status", ["Planning", "Active", "Completed", "Archived"])
            notes = st.text_area("Project notes")
            if st.form_submit_button("Create well"):
                try:
                    new_id = create_well(company_id, name, api_uwi, location, status, notes)
                    st.session_state.active_well_id = new_id
                    st.success("Well created and selected.")
                    st.rerun()
                except (ValueError, sqlite3.IntegrityError) as error:
                    st.error(str(error))

st.subheader("Existing well projects")
records = wells()
if not records:
    st.info("No wells have been created.")
for w in records:
    with st.expander(f'{w["company_name"]} / {w["name"]} — {w["status"]}'):
        with st.form(f'edit_well_{w["id"]}'):
            left,right = st.columns(2)
            api = left.text_input("API / UWI", value=w["api_uwi"])
            loc = right.text_input("Location", value=w["location"])
            statuses = ["Planning", "Active", "Completed", "Archived"]
            state = st.selectbox("Status", statuses, index=statuses.index(w["status"]))
            notes = st.text_area("Notes", value=w["notes"])
            if st.form_submit_button("Save project details"):
                update_well(w["id"], api, loc, state, notes)
                st.success("Project updated.")
                st.rerun()
        if st.button("Make this the active well", key=f'active_{w["id"]}'):
            st.session_state.active_well_id = w["id"]
            st.rerun()

st.divider()
st.subheader("Project data backup")
st.download_button("Download company & well backup (JSON)", data=export_json(),
                   file_name="toolbox_projects_backup.json", mime="application/json")
st.caption("Backup includes companies, wells, saved casing tallies and cementing worksheets. Import/restore is not yet implemented; keep this JSON file safe.")
