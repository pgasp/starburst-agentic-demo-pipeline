---
name: starburst-demo
description: >
  Starburst demo pipeline orchestrator. Takes a business request (vertical,
  use case, client) and orchestrates 4 agents to produce a coherent dataset +
  data product: consultant → [data modeler ‖ dp builder] → coherence checker.
  Triggers on: "prepare a demo for", "generate a full demo", "demo pipeline",
  "create a starburst demo for", "pipeline demo", "full demo for", "demo for".
---

## Pipeline overview

```
User request
     ↓
Agent 1 : starburst-demo-consultant   → <dp-name>-spec.json
     ↓
     ├── Agent 2 : starburst-demo-data-modeler   → <dp-name>-data.py   ┐ (parallel)
     └── Agent 3 : starburst-demo-dp-builder     → <dp-name>-dp.yaml   ┘
     ↓
Agent 4 : starburst-demo-coherence-checker → report + corrections
     ↓
(optional) Load data onto the cluster
```

---

## Step 1 — Collect business context

If arguments are provided, use them directly.
Otherwise, ask in a **single message**:

> "To generate this demo, tell me:
> - **Vertical / industry** (e.g. Healthcare, Banking, Logistics)
> - **Main use case** (e.g. PMSI activity tracking, fraud detection)
> - **2–3 business questions** the client should be able to answer
> - **Client or event** (e.g. Santexpo, BNP Paribas)
> - **Audience**: IT/DSI, Business users, C-level?"

---

## Step 2 — Agent 1: Demo Consultant (foreground)

Use the **Agent** tool to spawn a subagent with these instructions:

> "You are Agent 1 of the Starburst demo pipeline. Invoke the `starburst-demo-consultant` skill with these arguments: [full business context]. Produce and save the Schema Spec JSON to `dataproduct/<Client>/<Entity>/<dp-name>-spec.json`. Return the full file path and the JSON content of the spec."

Wait for completion — the spec is required before continuing.

Display: `✅ Agent 1 — Spec produced: <path>`

---

## Step 3 — Agents 2 & 3 in parallel (foreground)

Spawn **two agents simultaneously** in the same message (two Agent calls in the same response):

**Agent 2 — Data Modeler:**
> "You are Agent 2 of the Starburst demo pipeline. Invoke the `starburst-demo-data-modeler` skill. The spec is located at: `<spec-path>`. Generate and save `<dp-name>-data.py` in the same folder. Return the file path and a summary of the generated tables."

**Agent 3 — DP Builder:**
> "You are Agent 3 of the Starburst demo pipeline. Invoke the `starburst-demo-dp-builder` skill. The spec is located at: `<spec-path>`. Generate and save `<dp-name>-dp.yaml` in the same folder. Return the file path and a summary of the generated views."

Wait for both completions.

Display:
```
✅ Agent 2 — Data script: <path>
✅ Agent 3 — Data Product YAML: <path>
```

---

## Step 4 — Agent 4: Coherence Checker (foreground)

Spawn an agent with:

> "You are Agent 4 of the Starburst demo pipeline. Invoke the `starburst-demo-coherence-checker` skill. The artifacts are located in: `<folder>`. Analyze all three files (<dp-name>-spec.json, <dp-name>-data.py, <dp-name>-dp.yaml), apply necessary corrections, and return the full report."

Display the coherence report as-is.

---

## Step 5 — Summary and next steps

Display a final summary:

```
══════════════════════════════════════════
  Demo pipeline complete — <dp-name>
══════════════════════════════════════════

Artifacts generated in dataproduct/<Client>/<Entity>/ :
  📋 <dp-name>-spec.json     — Schema Spec (contract)
  🐍 <dp-name>-data.py       — Data script (<N> tables, <N> rows)
  📦 <dp-name>-dp.yaml       — Data Product YAML (<N> views)

Coherence: <✅ OK | ⚠️ N corrections applied>

Next steps:
  1. Load data    → python <dp-name>-data.py --host ... --catalog ... --schema ... --location ...
  2. Clean up     → python <dp-name>-data.py --host ... --schema ... --teardown
  3. Deploy DP    → POST /api/v1/dataProduct/products/import
  4. Test AIDA with the questions from the spec
```

Then ask:
> "Do you want me to load the data onto a cluster now? (I will need the host, user and password)"

If yes → collect the missing parameters and run `<dp-name>-data.py` with the correct args.

---

## Step 6 — Data Product deployment (if requested)

### 6a — Collect cluster parameters

Ask in a single message if missing: host, user, password, and target domain.

### 6b — Validate the catalogName before deploying

**Before any YAML import, query the cluster to find the exact Data Product catalog name.**

Run via SQLAlchemy/Trino:
```python
from sqlalchemy import create_engine, text
engine = create_engine(
    f"trino://{user}:{password}@{host}:443/system",
    connect_args={"http_scheme": "https"}
)
with engine.begin() as conn:
    rows = conn.execute(text("SHOW CATALOGS")).fetchall()
    catalogs = [r[0] for r in rows if "data" in r[0].lower()]
```

- If **exactly one** catalog contains "data" → use it automatically
- If **multiple** → display the list and ask which one is the Data Product catalog
- If **none** → ask the user to specify the catalog name

Update `catalogName` in the YAML before sending the import request.

### 6c — Validate / create the domain

Check that the target domain exists via `GET /api/v1/dataProduct/domains`.
If absent → create via `POST /api/v1/dataProduct/domains` with `name`, `description`, `schemaLocation`.

### 6d — Deploy

```
POST /api/v1/dataProduct/products/import
Content-Type: application/yaml
Body: <dp-name>-dp.yaml (with updated catalogName)
```

If 409 (product already exists) → `catalogName` is immutable, delete from the UI then retry.

---

## Orchestration rules

- **Agent 1 is always foreground** — its spec is the contract for everything downstream.
- **Agents 2 & 3 are always parallel** — spawn them in the same tool call.
- **Agent 4 waits for both** before starting.
- If an agent fails: report the error, offer to re-run that agent alone.
- Never skip Agent 4 — coherence is non-negotiable.
- Subagents invoke skills via the Skill tool — tell them to invoke the skill by name.

---

## Edge cases

| Situation | Behavior |
|---|---|
| Spec already exists in the folder | Ask: "Use the existing spec or generate a new one?" |
| Agent 2 or 3 fails | Re-run the failing agent alone, do not re-run the others |
| Agent 4 finds non-auto-fixable errors | List them and ask the user how to proceed |
| User wants to skip Agent 1 (spec already provided) | Read the existing spec and start at Step 3 |
| Cluster unavailable at Step 5 | Display the command, do not block |
