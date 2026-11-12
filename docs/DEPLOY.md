# Deploying, usage limits, Docker and CI

## Deploying to Streamlit Community Cloud

Checked against Streamlit's documentation on 2026-11-11. Community Cloud installs
`requirements.txt` from the repo root (`streamlit` is preinstalled there; the file pins it to
1.67.0), runs on Debian 11, and redeploys on every push to the deployed branch.
The app reads only committed files: `data/demo/`, `assets/`, `.streamlit/config.toml` and `src/`.

1. Go to [share.streamlit.io](https://share.streamlit.io), click **Continue to sign-in**, then
   **Continue with GitHub**. While this repo is private, Streamlit asks for access to private
   repositories; for a public repo the default access is enough.
2. Click **Create app** (upper right), then **Yup, I have an app**.
3. Fill in:
   - Repository: `sumeyye-agac/ask-your-wearable`
   - Branch: `main`
   - Main file path: `streamlit_app.py`
   - App URL (optional): pick the subdomain, for example `ask-your-wearable`.
4. Click **Advanced settings**.
   - Python version: **3.11**. The default is 3.12; the app is developed on 3.11, and CI tests
     both. The version cannot be changed later without deleting and redeploying the app.
   - Secrets: paste this, with the real key between the quotes (TOML needs the quotes):

     ```toml
     ANTHROPIC_API_KEY = "sk-ant-..."
     ```

     Optional second line, only to use another model: `WEARABLE_MODEL = "claude-haiku-5-5"`.
   - Click **Save**.
5. Click **Deploy** and wait for the build.
6. After the first deploy:
   - Ask one question. If the page says no API key is set, open the app's settings in your
     workspace and check the line above in its secrets.
   - Open the app's logs (**Manage app**, lower right of the app). The line
     `Visitor identified by: forwarded`, `ip` or `session` says how visitors are told apart.
     Addresses are never logged.
   - Check the per-visitor limit: open the app on a laptop and on a phone using mobile data,
     ask one question on each. Each should then show "Questions left today: 9 of 10". If the
     second device shows 8, visitors share one address and the limit is shared too; tell me
     and the rule in `wearable.presentation.visitor_key` gets changed.
   - Put the link at the top of `README.md`.
   - Set a low monthly spend limit in the Claude Console. The limits in the app are estimates
     kept in memory.

An app with no visits for 12 hours goes to sleep and wakes on the next visit. The key lives only
in the Secrets box (and in `.env` locally); `.env` and `.streamlit/secrets.toml` are git-ignored.

## Usage limits and visitor identification

Limits, both kept in memory and reset when the app restarts: 10 questions per visitor per UTC
day, and an estimated $1.00 of API spend per UTC day for the whole app. A failed question does
not count. API failures (no credit, rate limits, outages, a missing key) are shown as a short
message, not an error page. The app's tests run it headless with the API call replaced, so they
cost nothing.

Who counts as one visitor is decided in this order: the last public address in the
`X-Forwarded-For` header, then `st.context.ip_address` if it is a public address, then the
browser session. The reason for the order: in Streamlit 1.67.0 `st.context.ip_address` is the
address of the connection that reached the app (read in the installed source), so behind a
hosting proxy it is the proxy. Streamlit's documentation does not say what either value holds on
Community Cloud, so this is **not verified** there; step 6 of the deploy guide above has the
check. If neither gives a public address, the fallback is the browser session, which a reload
resets. The per-visitor count is therefore a courtesy limit. What protects the API budget in
every case is the app-wide $1.00 per day, and behind it the spend limit set in the Claude
Console.

## Docker and CI

`.github/workflows/ci.yml` runs on every push and pull request: the tests on Python 3.11 and
3.12, and a build of the `Dockerfile`. The image holds only `requirements.txt` and the files the
app reads, like Community Cloud, so CI also renders the page inside it once and checks the
server's health endpoint. The Dockerfile is an optional way to run the app, not the deployment:

```bash
docker build -t ask-your-wearable .
docker run --rm -p 8501:8501 -e ANTHROPIC_API_KEY=... ask-your-wearable   # http://localhost:8501
```
