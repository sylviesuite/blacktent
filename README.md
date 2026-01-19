# BlackTent

**BlackTent** is a local-first safety environment for diagnosing development problems without exposing secrets, source code, or private system state.

It is designed for moments when something is *wrong* but copying files, logs, or environment variables into an external tool would be unsafe or irresponsible.

BlackTent prioritizes **clarity over automation** and **containment over convenience**.

---

## What BlackTent Is

BlackTent is a **CLI-based diagnostic tool** that operates inside a secure, local boundary.

It helps developers answer questions like:

* Is my environment configured the way I think it is?
* Are required variables present without revealing their values?
* Is this issue caused by drift, mismatch, or missing state?
* What assumptions are failing right now?

BlackTent analyzes **structure, presence, and coherence**, not secret content.

---

## What BlackTent Is Not

BlackTent does **not**:

* Read or transmit secret values
* Upload files, logs, or environment data
* Auto-fix systems or mutate configuration
* Scan entire repositories
* Replace debugging judgment with automation
* Provide a UI or dashboard (by design)

BlackTent is intentionally conservative.

---

## Core Principles

### 1. Local First

All diagnostics run on the user’s machine.
Nothing is sent to external services.

### 2. Structure Over Secrets

BlackTent evaluates *whether* something exists and *whether it aligns*, never *what it contains*.

### 3. No Silent Actions

BlackTent does not modify systems automatically.
It explains what it sees and why it matters.

### 4. Human-in-the-Loop

The goal is understanding, not blind repair.

---

## Current Scope (v1)

BlackTent v1 is feature-locked around:

* **Boot Doctor**
  Diagnose whether services are running, where, and why confusion exists.

* **Security Tent**
  Environment and redaction-safe diagnostics for sensitive contexts.

* **Mechanic Mode**
  Suggests likely causes and next steps without auto-fixing.

Future versions will expand **clarity**, not automation.

---

## Interface

BlackTent is a **CLI tool**.

This is intentional.

A CLI allows:

* auditability
* composability
* safe use in sensitive environments
* predictable behavior

A UI may exist in the future, but it is not required for BlackTent to do its job well.

---

## Status

BlackTent is under active development.

This repository contains the **canonical, minimal implementation** intended for public use.

Experimental work, prototypes, and research live elsewhere.

---

## License

MIT License.

---

## Security

If you believe you’ve found a security issue, please see `SECURITY.md`.

BlackTent treats security as a first-class constraint, not a feature.
