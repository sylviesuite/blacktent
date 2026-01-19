# blacktent
Local-first AI development sandbox that protects secrets, sanitizes project files, and allows safe AI-assisted coding. MVP includes secret scanning, redaction mapping, sanitized filesystem, patch engine, and AI gateway.

## Why BlackTent Exists

Modern AI tools are powerful, but unsafe by default.

They:

- encourage copying secrets into chat windows  
- execute commands too eagerly  
- refactor large surfaces without context  
- blur the line between thinking and acting  

BlackTent exists to restore control, safety, and intent to AI-assisted development.

---

## What BlackTent Is

BlackTent is a security-first development tent for working through fragile or high-risk problems without exposing secrets, damaging state, or spiraling into unintended changes.

It is designed for moments when:

- your environment is unstable  
- configuration feels haunted  
- secrets are involved (.env, credentials, tokens)  
- you need diagnosis, not automation  

BlackTent favors clarity over speed and containment over cleverness.

---

## Core Principles

### No Silent Execution

BlackTent never:

- runs commands without explicit consent  
- kills processes automatically  
- mutates files invisibly  

All actions are explain-first, opt-in, and reversible.

---

### Security by Design

BlackTent treats secrets as opaque:

- values are never read or logged
- structure and presence are analyzed instead
- .env files can be reasoned about without exposure

This allows safe debugging of authentication, config drift, and deployment issues.

---

### Think Before Fix

BlackTent separates:

- Diagnosis from Repair
- Suggestion from Execution

Mechanic Mode can suggest fixes, but will not auto-apply them unless explicitly requested.

---

## What BlackTent Protects

- Environment variables and credentials  
- Fragile dev server state  
- Configuration assumptions vs reality  
- Developers under stress or fatigue  

BlackTent is designed to reduce panic-driven damage.

---

## What BlackTent Does Not Do

- It does not act as a full autonomous agent  
- It does not refactor entire repositories  
- It does not replace developer judgment  

BlackTent is a stability tool, not an automation engine.

---

## Intended Use

BlackTent shines in:

- environment drift debugging  
- dev server confusion (Boot Doctor)  
- security-sensitive work  
- pre-release hardening (core lock)  

It is intentionally conservative by design.

---

## Philosophy

> "Fast tools break things. Safe tools help you stop."

BlackTent is built for moments when stopping is the most valuable action.

---

## Status

BlackTent v1.0 is feature-locked around:

- Boot Doctor  
- Security Tent (env + redaction safety)  
- Mechanic Mode (suggest, don’t auto-fix)

Future work will expand clarity, not automation.

---

## Stateless Incident Response

BlackTent is built around a **Stateless Incident Response** security model.

When something breaks, the most common risks are not attackers, but panic, overreach, and accidental disclosure. BlackTent is designed to reduce those risks by controlling how investigation happens, not by storing more data.

### What “stateless” means

BlackTent does **not**:

* remember repository contents, environment state, or system history

* retain logs, snapshots, or diagnostic context between runs

* upload or persist any data internally

* build long-term memory of incidents or projects

Each run is **local, ephemeral, and self-contained**.

When BlackTent exits, it forgets everything it observed.

This is intentional.

### How incident response works without memory

During an incident, BlackTent focuses on **preservation through non-action**:

* **Read-only diagnostics**

  BlackTent observes without fixing, rewriting, or normalizing system state.

* **Intentional evidence capture**

  When explicitly requested, BlackTent can generate sanitized reports, redacted bundles, and safe summaries for escalation. These artifacts never include secret values and are created only through user intent.

* **Safe external escalation**

  Sanitized output can be shared with AI tools, consultants, or teammates without exposing sensitive data.

* **Forensic preservation**

  Because BlackTent does not modify the system or retain hidden state, the original context remains intact for internal investigation, postmortems, and audits.

The artifact persists.

The human decides.

The tool forgets.

### Why this matters

Most debugging and AI-assisted tools optimize for speed and automation. In high-stress situations, that often leads to evidence destruction, uncontrolled changes, accidental leaks, and unclear postmortems.

BlackTent optimizes for **trust under pressure**.

By remaining stateless, it minimizes attack surface, simplifies security review, and makes it safe to use during the moments when mistakes are most likely.

Stateless Incident Response is not about doing more.

It is about **not making things worse**, while still enabling help.

---

## CLI (v1)

BlackTent exposes a calm, read-only CLI surface for the scoped v1 release. The commands below are placeholder-first and intentionally avoid secrets, automation, or repo-wide mutations.

Example commands:

- `python -m blacktent doctor --scope minimal --category boot`  
- `python -m blacktent env check --strict --print-keys`  
- `python -m blacktent scan --include "*.env*" --report blacktent-scan.json`  
- `python -m blacktent redact bundle --dry-run --policy default`

Use `--json` for machine-friendly output and add `--report` or `--out` when you explicitly want sanitized artifacts written to disk.
