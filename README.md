# BlackTent — A strictly local CLI for generating policy-constrained bundles intended for external sharing with LLMs or vendors

BlackTent is a local, non-networked CLI that prepares sanitized incident context for sharing. It never reaches outside the host, it does not execute an LLM, and its only purpose is to capture, sanitize, and package data for safe external review.

BlackTent applies an explicit, reviewable policy (paths, file types, and redaction rules) defined in config, so organizations can agree in advance on what is allowed to leave during incidents.

## What BlackTent is

- A strictly local command-line program with no network connectivity or hidden services.
- A toolkit for capturing incident data, redacting high-risk fields, and producing exportable bundles.
- A preparer of context intended for human reviewers, LLMs, or vendors once the outputs are explicitly exported.

## What BlackTent is not

- Not an AI model, inference engine, or agent.
- Not a sandboxed runtime or container orchestrator.
- Not a replacement for a full incident response pipeline or managed service.
- Not automated remediation; it does not decide on actions for you.

## Problem statement

Incidents happen under stress. Teams often respond by dumping sensitive files into chats or tools without understanding what leaks to the outside. Accidentally exposing credentials or internal state to LLMs or vendors is a real harm. BlackTent exists to reduce that harm by making evidence curation intentional, auditable, and repeatable, not by pretending to eliminate risk entirely.

## Threat model (v0)

- Reduces risk of leaking secrets, credentials, or broken defaults when sharing incident context externally.
- Reduces risk of undocumented transformations by requiring deterministic sanitization steps.
- Does not prevent attackers from accessing the machine directly.
- Does not replace hardened infrastructure or ongoing detection tooling.
- Does not handle insider threats, lateral movement, or persistence that occurs outside the bundle generation window.
- Does not make exports safe against malicious downstream recipients; downstream vendors and LLM providers must still be vetted.

## Statelessness contract

- No network access at any point during bundle creation.
- No telemetry, no phoning home, no hidden endpoints.
- One-shot execution: run once, produce a bundle, exit.
- No hidden persistence: temporary artifacts live only in the working directory unless explicitly exported.
- Explicit export only: data leaves the machine only when the user runs `blacktent bundle --export ...`.
- Deterministic output target so repeated runs with the same inputs and flags yield the same bundle tree.

## How it works

1. The operator points BlackTent at the incident scope (directories, files, logs).
2. BlackTent scans the specified inputs, records metadata, and applies sanitization policies.
3. Sanitized files and indicators are written into a dedicated bundle directory.
4. The manifest describes every file, what was redacted, and what policies were applied.
5. The bundle is exported only when the operator explicitly copies or ships it to reviewers.

## Bundle format (v0)

- A top-level directory such as `bundle-<timestamp>/`.
- A `manifest.json` file that lists every included artifact, its source path, sanitization status, and a hash for integrity checks.
- Subdirectories for logs, configuration, and diagnostics, each documenting redaction status in accompanying metadata files.
- No default modification outside the bundle directory.

## Redaction approach (v0)

- Bias toward over-redaction: better to omit than to guess accuracy of sensitive values.
- Logs and high-risk files are opt-in; nothing is redacted unless the operator names it explicitly.
- Redactions are marked in manifests and within files with consistent placeholders so reviewers know what was removed.
- When a value cannot be safely retained, a descriptive comment explains why it was omitted.

## Minimal CLI surface (v0)

- `blacktent bundle [path] --export <destination>` – create and export a sanitized incident bundle.
- `blacktent inspect manifest.json` – review the manifest before sharing.
- `blacktent verify <bundle>` – confirm hashes and consistently applied redactions.
- CLI flags control policy strictness, log inclusion, and what sources to capture; nothing runs without explicit options.

## Why not tar/grep/Docker?

Traditional tools like `tar` or `grep` are powerful but not repeatable under stress, and they offer no audit trail for what gets exposed. Docker adds complexity and hidden layers. BlackTent enforces deterministic sanitization, generates a manifest for every export, and keeps the UI simple so that under pressure the operator knows exactly what is being captured and why.

## Status & feedback

Status: planning v0.2.  
Feedback: open issues and README comments welcome; flag anything that feels unclear or too permissive.

