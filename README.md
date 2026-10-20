# Drilling Engineering Toolbox

A Streamlit-based drilling engineering workspace. Early development preview — **not suitable for confidential project information or public multi-user use yet**.

## Run locally or in GitHub Codespaces

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8502
```

Use **app.py** for the main dashboard. Existing **Tally.py** and **FIT.py** remain individually runnable.

## What works

- Toolbox dashboard and navigation
- Create and select companies and well projects
- Edit project status, location and notes
- Local SQLite persistence in `data/toolbox.sqlite3`
- Download company/well metadata backup as JSON
- Existing Casing Tally and FIT tools remain available

## Not yet implemented

- Saving FIT/Tally calculation runs to projects
- Shared cloud database and project permissions
- User accounts, invitation emails or authentication
- Restoring downloaded JSON backups

**Important:** Codespace/local SQLite files may disappear when the environment is deleted or rebuilt. Export backup JSON often. Do not store real confidential well data in publicly accessible deployments. Keep the forwarded port private during development.

## Planned architecture

- `app.py`: navigation and current project selection
- `dashboard.py`: workspace overview
- `projects.py`: company and well management
- `project_store.py`: replaceable persistence layer
- `Tally.py`: casing tally tool
- `FIT.py`: formation integrity test tool

The next development step is project-linked saves and revisions for each engineering tool.
