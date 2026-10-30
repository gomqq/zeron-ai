# ZERON AI — starter

This is the first UI/backend scaffold for the ZERON AI cloud coding-agent project.

## What works now
- BLUE FUTURE landing page
- Task submission form
- Basic job list saved in SQLite
- Health endpoint

## Important
This starter **does not yet call an AI model or execute code**. It records tasks so we can verify the website first. The next step is to connect an AI provider and a separate, sandboxed cloud worker. Do not run arbitrary generated code directly on the public web server.

## Run locally (Windows)
1. Install Python 3.11+ from https://www.python.org/downloads/
2. Extract this ZIP.
3. Open the extracted folder.
4. In the folder address bar, type `cmd` and press Enter.
5. Run:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python app.py
   ```
6. Open http://127.0.0.1:5000

## Deploy
`render.yaml` is a starting point for deployment on Render. Note that free web instances may sleep and local SQLite data may not persist across redeploys/restarts. For durable cloud jobs, use persistent storage/database and a worker/queue service. Always add AI API keys as environment variables, never commit them to GitHub.
