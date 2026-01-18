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
