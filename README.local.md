BlackTent 🏕️

An AI-safe firewall for your codebase

BlackTent lets you use AI on real projects without exposing secrets, keys, or environment variables.

It creates a safe boundary (“the tent”) between your repo and any AI assistant by:

Detecting sensitive data

Redacting it deterministically

Producing machine-readable reports

Bundling only what is safe to share

Why BlackTent exists

AI is powerful — but unsafe by default.

Common problems:

.env files block progress

Fear of leaking API keys

Copy/paste debugging is error-prone

Teams avoid AI because of risk

BlackTent solves this by design.

You can hand a repo to AI and say:

“Here’s everything you need. Nothing sensitive is inside.”

What BlackTent does

Core pipeline

scan → detect → redact → patch → bundle

Included tools

🔍 Scan

Detects secrets like:

API keys

Tokens

Passwords

Credential-like strings

✂️ Redact

Replaces sensitive values with stable placeholders:

[REDACTED:OPENAI_KEY:88c422f1]

🔁 Patch

Safely reapplies redactions to original files using a manifest

(no guessing, no re-scanning)

📦 Bundle

Creates an AI-safe snapshot of your repo:

Redacted files only

No .env values

Includes a manifest for traceability

🧪 Env-check (diagnostics)

Scans for environment configuration issues without reading secrets:

Detects .env* files

Parses .env.example

Reports missing vs present variables

Outputs safe JSON for AI handoff

Installation

git clone <this-repo>

cd blacktent

pip install -r requirements.txt


Python 3.9+ recommended.


Usage

Scan a file

python blacktent_scan.py scan-file path/to/file.txt


Scan a directory

python blacktent_scan.py scan-dir .


Patch (reapply redactions safely)

python blacktent_scan.py patch input.txt --out patched_input.txt


Bundle for AI

python blacktent_scan.py bundle .


Env diagnostics (safe)

python blacktent_scan.py env-check .



Reports are written to:

.blacktent/

├─ report.json

├─ manifest.json

├─ env_report.json


All outputs are safe to share with AI.

What BlackTent will NOT do

❌ Read actual secret values

❌ Upload anything

❌ Modify your repo silently

❌ Guess env values

❌ Phone home

BlackTent is local, explicit, and reversible.

Designed to be reusable

BlackTent is not tied to any one project.

It works with:

Node / Python / JS repos

Frontend or backend

Solo developers or teams

Any AI tool (ChatGPT, Claude, Cursor, etc.)

Use it once — or make it part of your workflow.

Status

MVP (tiny) — stable core

Next planned:

blacktent doctor (full repo health check)

Ignore rules (.blacktentignore)

CI-friendly mode

Pre-AI hooks

Philosophy

Use AI freely.

Share code confidently.

Never leak secrets.

That’s BlackTent.

