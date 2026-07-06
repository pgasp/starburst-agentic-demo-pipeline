# Starburst Agentic Demo Pipeline

A multi-agent [Claude Code](https://claude.ai/code) pipeline that auto-generates complete Starburst demo environments — dataset, Data Product YAML, and coherence validation — from a plain-language business request.

## Overview

```
User request (vertical, use case, audience)
     ↓
Step 1 — Agent 1: Demo Consultant   →  <dp-name>-spec.json     (Schema Spec + BIAC fields)
     ↓
     ├── Step 2: Agent 2 — Data Modeler  →  <dp-name>-data.py   (Python loader)  ┐ parallel
     └── Step 3: Agent 3 — DP Builder    →  <dp-name>-dp.yaml   (Data Product)   ┘
     ↓
Step 4 — Agent 4: Coherence Checker →  validation report + auto-corrections
     ↓
Step 5 — Review (HITL)
     ↓
Step 6 — Cluster deployment (data load + Data Product import)
     ↓
Step 7 — BIAC auto-setup (3 roles: superuser / user / data_ing)
     ↓
Step 8 — (optional) Lineage HTML  →  <dp-name>-lineage.html
```

The pipeline produces four deployment-ready artifacts in `dataproduct/<Client>/<Entity>/`:
- **Spec JSON** — single contract shared by all agents, includes `rls_column` + `sensitive_columns`
- **Python script** — DDL + synthetic data generation + parallel upload via SQLAlchemy/Trino
- **Data Product YAML** — deployable directly to a Starburst cluster via the REST API
- **Lineage HTML** — self-contained 2-panel diagram (data lineage + BIAC roles, no external dependencies)

## Skills

| File | Agent / Tool | Role |
|---|---|---|
| `starburst-demo.md` | Orchestrator | Coordinates the full 8-step pipeline end-to-end |
| `starburst-demo-consultant.md` | Agent 1 | Business context → Schema Spec JSON (incl. BIAC fields) |
| `starburst-demo-data-modeler.md` | Agent 2 | Spec → Python data loader (DDL + synthetic data) |
| `starburst-demo-dp-builder.md` | Agent 3 | Spec → Starburst Data Product YAML |
| `starburst-demo-coherence-checker.md` | Agent 4 | Cross-validates all 3 artifacts, auto-corrects |
| `starburst-demo-lineage-gen.py` | Standalone script | Generates data lineage HTML (sources → views + BIAC roles) |

## Prerequisites

- [Claude Code](https://claude.ai/code) CLI installed
- A Starburst Enterprise cluster (for data loading and Data Product deployment)
- Python dependencies for the generated loader script:
  ```
  pip install pandas faker trino sqlalchemy numpy
  ```

## Setup

1. Copy the `.claude/commands/` folder into your project (or Obsidian vault):
   ```bash
   cp -r .claude/commands/ /your/project/.claude/commands/
   ```

2. Open the project in Claude Code.

## Usage

### Full pipeline (recommended)

Trigger the orchestrator with any of:

```
/starburst-demo prépare un demo pour le secteur santé — pilotage PMSI, audience DSI CHU Toulouse
/starburst-demo génère un demo complet pour la détection de fraude, banque retail
```

Claude will ask for any missing context (vertical, use case, business questions, audience), then run the 4-agent pipeline.

### Individual agents

You can invoke agents independently if you already have a spec:

```
/starburst-demo-consultant      # Generate spec from business context
/starburst-demo-data-modeler    # Generate Python loader from spec
/starburst-demo-dp-builder      # Generate Data Product YAML from spec
/starburst-demo-coherence-checker  # Validate and auto-correct artifacts
```

## Pipeline details

### Agent 1 — Demo Consultant

Takes a business request and produces a **Schema Spec JSON** — the single contract for downstream agents. Applies strict rules:
- 2–4 tables (1 fact + dims/refs)
- Volumes: fact 2,000–5,000 rows, ref 20–200 rows
- Exact Trino types only (`VARCHAR`, `INTEGER`, `DOUBLE`, `BOOLEAN`, `DATE`, `DECIMAL(p,s)`, ...)
- 5–6 AIDA questions covering aggregation, ranking, KPI, trend, anomaly detection
- `dp_name` in kebab-case with no client name (reusable)

### Agent 2 — Data Modeler

Reads the spec and generates a standalone Python script with:
- DDL dict using exact Trino types from spec
- Synthetic data generation (Faker + numpy, `random.seed(42)`)
- Static hardcoded ref tables (realistic domain codes)
- FK integrity enforced via parent ID lists
- Anomaly flags at specified rates
- Parallel upload via `ProcessPoolExecutor` (4 workers)
- `--teardown` flag for cleanup

### Agent 3 — DP Builder

Reads the spec and generates a deployment-ready Starburst Data Product YAML:
- One direct view per raw table
- One denormalized JOIN view per fact→dim relationship
- Sample queries (4–5) covering aggregation, trend, ranking, anomaly
- Column docs from spec descriptions
- AIDA questions embedded in `metadata.description`
- YAML formatting rules enforced (no blank lines between fields, no inline comments, `|` for description blocks)

### Step 7 — BIAC Auto-Setup

Automatically runs after cluster deployment. Derives a 3-role BIAC structure from the spec:

| Role | Assignee | Grants |
|---|---|---|
| `{prefix}_superuser` | `starburst_service` | SELECT on all views, no filter |
| `{prefix}_user` | demo user | SELECT on all views + RLS on `rls_column` + CLS on `sensitive_columns` |
| `{prefix}_data_ing` | demo user | Cross-DP SELECT + raw iceberg allEntities |

The `prefix` is derived from the first 3 `_`-separated segments of `dp_name`. Generates and executes a Python BIAC script using the cluster credentials from `dataproduct/servers/.env.<cluster>`.

### Step 8 — Lineage HTML (optional)

Triggered by: `"génère le lineage pour {dp-name}"`

Calls `starburst-demo-lineage-gen.py` — a standalone portable Python script that generates a self-contained HTML file with:
- **Left panel:** data lineage diagram (raw Iceberg tables → Data Product views, SVG bézier arrows)
- **Right panel:** 3 BIAC role cards with grants, RLS/CLS indicators, stats bar

The script embeds the Starburst logo as a base64 data URI — no external files or network dependencies.

```bash
python .claude/commands/starburst-demo-lineage-gen.py \
  --spec  dataproduct/<Client>/<Entity>/<dp-name>-spec.json \
  --yaml  dataproduct/<Client>/<Entity>/<dp-name>-dp.yaml \
  --output account/<Client>/<dp-name>-lineage.html
```

### Agent 4 — Coherence Checker

Runs 10 checks across all 3 artifacts and auto-corrects where possible:

| Check | What it validates |
|---|---|
| 1 | DDL completeness vs spec |
| 2 | Type consistency DDL vs spec |
| 3 | YAML view columns vs DDL |
| 4 | YAML column types (lowercase) vs DDL |
| 5 | `definitionQuery` SELECT columns vs DDL |
| 6 | Sample queries reference existing views only |
| 7 | `dataDomainName` is a valid safe value |
| 8 | `catalogName` matches cluster catalog |
| 9 | FK relationships present in both artifacts |
| 10 | AIDA questions covered by sample queries |

## Supported verticals

The consultant agent has built-in domain knowledge for:
- **Santé / PMSI** — GHM codes, CIM-10, T2A tariffs, readmission flags
- **Finance / Banque Retail** — transactions, fraud detection, client segments
- **Assurance** — sinistres, contrats, délais expertise
- **Logistique** — commandes, expéditions, transporteurs, retards
- **Secteur Public** — dossiers, prestations, délais de traitement

## Output structure

```
dataproduct/
  <Client>/
    <Entity>/
      <dp-name>-spec.json      # Schema Spec (Agent 1 output)
      <dp-name>-data.py        # Python loader (Agent 2 output)
      <dp-name>-dp.yaml        # Data Product YAML (Agent 3 output)
```

## Deploying the Data Product

Once the pipeline completes:

```bash
# 1. Load raw data
python dataproduct/<Client>/<Entity>/<dp-name>-data.py \
  --host <cluster-host> \
  --user <user> \
  --password <password> \
  --catalog iceberg \
  --schema <dp_name>_raw \
  --location s3://<bucket>/path/

# 2. Import Data Product via REST API
curl -X POST https://<cluster-host>/api/v1/dataProduct/products/import \
  -H "Content-Type: application/yaml" \
  -u <user>:<password> \
  --data-binary @dataproduct/<Client>/<Entity>/<dp-name>-dp.yaml

# 3. Teardown (cleanup raw schema)
python dataproduct/<Client>/<Entity>/<dp-name>-data.py \
  --host <cluster-host> --user <user> --password <password> \
  --catalog iceberg --schema <dp_name>_raw --teardown
```
