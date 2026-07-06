# Building a Multi-Agent Pipeline to Generate Starburst Demos on Demand

> **Context:** This document describes an AI-powered pipeline built with Claude Code that generates production-ready Starburst demo environments — synthetic dataset + Data Product YAML — from a plain-language business request. The system uses four specialized agents coordinated by an orchestrator.

---

## The Problem

Preparing a Starburst demo for a prospect is repetitive and error-prone. The typical workflow looks like this:

1. Write a data model (tables, columns, types) adapted to the client's vertical
2. Write a Python script to generate synthetic data and load it into a cluster
3. Write a Data Product YAML with views, column documentation, and AIDA sample questions
4. Manually verify that the YAML views reference columns that actually exist in the dataset
5. Discover a type mismatch the day of the demo

Steps 2, 3, and 4 are largely mechanical once the data model is defined. Step 4 (coherence) is what fails silently — the YAML is written separately from the script, with no enforcement that they describe the same schema.

**The core issue:** two artifacts (Python script + YAML) are generated independently by a human who may introduce subtle mismatches that only surface at runtime.

---

## The Architecture: Four Specialized Agents + One Orchestrator

The pipeline takes a business request as input and produces three files as output:

```
User: "Demo for a hospital — PMSI activity, T2A revenue, readmission rates"
                              ↓
              ┌───────────────────────────┐
              │  Step 1: Agent 1          │
              │  Consultant               │
              │                           │
              │  Business need            │
              │       ↓                   │
              │  Schema Spec JSON         │
              │  (+ rls_column, CLS)      │
              └───────────┬───────────────┘
                          │  Shared contract
               ┌──────────┴──────────┐
               ↓                     ↓   (parallel)
  ┌────────────────────┐  ┌──────────────────────┐
  │  Step 2: Agent 2   │  │  Step 3: Agent 3      │
  │  Data Modeler      │  │  DP Builder           │
  │                    │  │                       │
  │  DDL + Python      │  │  Starburst Data       │
  │  data script       │  │  Product YAML         │
  └──────────┬─────────┘  └──────────┬────────────┘
             └──────────┬────────────┘
                        ↓
          ┌─────────────────────────────┐
          │  Step 4: Agent 4            │
          │  Coherence Checker          │
          │                             │
          │  DDL ↔ YAML validation      │
          │  Auto-fix + report          │
          └─────────────────────────────┘
                        ↓
          ┌─────────────────────────────┐
          │  Step 5: HITL Review        │
          └─────────────────────────────┘
                        ↓
          ┌─────────────────────────────────────────────────────┐
          │  Step 6: Cluster Deploy (parallel phase)            │
          │                                                     │
          │  ┌─────────────────┐  ┌──────────────┐            │
          │  │ 6b SHOW CATALOGS│  │ 6c GET domain│  ┐ parallel│
          │  └────────┬────────┘  └──────┬───────┘  │         │
          │           │                  │           │         │
          │  ┌─────────────────────────────────┐    │         │
          │  │  data.py  (iceberg raw load)     │ ───┘         │
          │  └─────────────────────────────────┘              │
          │           ↓ (after 6b + 6c)                       │
          │  6d: POST dp.yaml import                           │
          └─────────────────────────────────────────────────────┘
                        ↓
          ┌─────────────────────────────┐
          │  Step 7: BIAC Auto-Setup    │
          │  3 roles via REST API       │
          │  (always, auto)             │
          └─────────────────────────────┘
                        ↓ (on user trigger)
          ┌─────────────────────────────┐
          │  Step 8: Lineage HTML       │
          │  lineage-gen.py             │
          │  (optional)                 │
          └─────────────────────────────┘
                        ↓
         dataproduct/<Client>/<Entity>/
         ├── *-spec.json
         ├── *-data.py
         └── *-dp.yaml
         account/<Client>/
         └── *-lineage.html
```

---

## ## The Architecture detailled

Multi-agent pipeline that transforms a business request into a complete Starburst demo (dataset + Data Product YAML) deployable on a cluster.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    /starburst-demo (orchestrator)                   │
│                    .claude/commands/starburst-demo.md               │
│                                                                     │
│  Steps 1–8: business context → spec → data+yaml → coherence →      │
│             HITL review → deploy → BIAC → (lineage)                │
└──────────────┬──────────────────────────────────────────────────────┘
               │ foreground (blocking)
               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 1 — Agent 1: starburst-demo-consultant                        │
│  starburst-demo-consultant.md                                       │
│                                                                     │
│  INPUT  : business context (vertical, use case, audience)          │
│  OUTPUT : <dp-name>-spec.json                                      │
│                                                                     │
│  Role : Senior SE — translates a business request into a Schema    │
│         Spec JSON (tables, columns, types, volumes, AIDA           │
│         questions, rls_column, sensitive_columns)                  │
└──────────────┬──────────────────────────────────────────────────────┘
               │ spec.json → two parallel agents
               ├─────────────────────────┐
               ▼                         ▼
┌──────────────────────────┐  ┌──────────────────────────────────────┐
│  Step 2 — Agent 2        │  │  Step 3 — Agent 3                    │
│  starburst-demo-         │  │  starburst-demo-dp-builder           │
│  data-modeler            │  │  starburst-demo-dp-builder.md        │
│                          │  │                                      │
│  INPUT  : spec.json      │  │  INPUT  : spec.json                  │
│  OUTPUT : data.py        │  │  OUTPUT : dp.yaml                    │
│                          │  │                                      │
│  DDL + realistic         │  │  Views, column docs,                 │
│  synthetic data          │  │  sample SQL queries,                 │
│  SQLAlchemy/Trino upload │  │  AIDA business context,              │
│  --teardown flag         │  │  catalogName placeholder             │
└──────────────┬───────────┘  └──────────────────┬───────────────────┘
               └──────────────┬──────────────────┘
                              │ data.py + dp.yaml
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 4 — Agent 4: starburst-demo-coherence-checker                 │
│  starburst-demo-coherence-checker.md                                │
│                                                                     │
│  INPUT  : spec.json + data.py + dp.yaml                            │
│  OUTPUT : report + in-place corrections                            │
│                                                                     │
│  10 checks : DDL↔spec, types, view columns↔DDL,                   │
│              sample queries↔views, dataDomainName,                 │
│              catalogName, FK relations, AIDA coverage              │
└──────────────┬──────────────────────────────────────────────────────┘
               │ validated artifacts
               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 5 — HITL Review                                              │
│                                                                     │
│  User reviews generated artifacts; can request corrections before  │
│  moving to deployment. Pipeline waits for explicit confirmation.    │
└──────────────┬──────────────────────────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 6 — Cluster Deployment                                       │
│                                                                     │
│  python data.py --host --user --password --catalog --schema        │
│  GET  /api/v1/dataProduct/domains   → check/create domain          │
│  POST /api/v1/dataProduct/products/import  → deploy dp.yaml        │
│                                                                     │
│  Credentials from: dataproduct/servers/.env.<cluster>              │
└──────────────┬──────────────────────────────────────────────────────┘
               │ (auto, always runs after Step 6)
               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 7 — BIAC Auto-Setup                                          │
│                                                                     │
│  INPUT  : spec.json (rls_column, sensitive_columns) + .env cluster │
│  OUTPUT : 3 BIAC roles created via REST API                        │
│                                                                     │
│  {prefix}_superuser  → starburst_service, all views, no filter     │
│  {prefix}_user       → demo user, RLS on rls_column, CLS masks     │
│  {prefix}_data_ing   → demo user, cross-DP + raw iceberg           │
│                                                                     │
│  prefix = first 3 segments of dp_name (hyphens → underscores)     │
└──────────────┬──────────────────────────────────────────────────────┘
               │ (optional — triggered by user)
               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 8 — Lineage HTML                                             │
│                                                                     │
│  Trigger: "génère le lineage pour {dp-name}"                       │
│                                                                     │
│  INPUT  : spec.json + dp.yaml                                      │
│  OUTPUT : <dp-name>-lineage.html  (fully self-contained)           │
│                                                                     │
│  Script : starburst-demo-lineage-gen.py                            │
│           - Left panel: raw tables → views (SVG bézier arrows)     │
│           - Right panel: 3 BIAC role cards + stats                 │
│           - Logo embedded as base64 — no external dependencies     │
└─────────────────────────────────────────────────────────────────────┘
```

---


---

## Steps 7–8: BIAC and Lineage

### Step 7 — BIAC Auto-Setup

Runs automatically after successful cluster deployment (Step 6). No user action required.

Derives a 3-role permission structure from the spec:

| Role | Assignee | Grants |
|---|---|---|
| `{prefix}_superuser` | `starburst_service` | SELECT on all views — no filter |
| `{prefix}_user` | demo user | SELECT + RLS (`rls_column = current_user`) + CLS masks |
| `{prefix}_data_ing` | demo user | Cross-DP SELECT + raw iceberg `allEntities` |

**`rls_column`** — auto-detected by the consultant agent from patterns: `_owner`, `_responsable`, `_assignee`, `region`, `department`, `entity`, `desk_*`, `agence_*`. Set to `null` if no candidate.

**`sensitive_columns`** — auto-detected column masks:
- `amount` → `ROUND(col / 100000) * 100000` (financial ranges)
- `id` → `CONCAT(SUBSTR(col, 1, 4), '****')` (identifier prefix masking)
- `score` → `CAST(ROUND(CAST(col AS DOUBLE) / 10) * 10 AS INTEGER)` (risk score bucketing)

The step generates and executes a Python BIAC script using the cluster REST API. Credentials are read from `dataproduct/servers/.env.<cluster>` — never passed on the command line.

### Step 8 — Lineage HTML (optional)

Trigger phrase: `"génère le lineage pour {dp-name}"`

`starburst-demo-lineage-gen.py` is a **fully portable** standalone Python script — no workspace dependencies, no external files, no network requests. The Starburst logo is embedded as a base64 data URI constant.

```
starburst-demo-lineage-gen.py
  --spec  <dp-name>-spec.json
  --yaml  <dp-name>-dp.yaml
  --output account/<Client>/<dp-name>-lineage.html
```

Outputs a single self-contained HTML file:
- **Left panel:** raw Iceberg tables → Data Product views, connected by SVG bézier arrows (color-coded per view)
- **Right panel:** 3 BIAC role cards (grants, RLS tag, CLS count) + stats bar + embedded logo

View→table mapping uses a substring heuristic: a view is connected to tables that share a word segment >3 chars with the view name.

---

## The Shared Contract: Schema Spec JSON

The key architectural decision is the **Schema Spec** — a structured JSON file produced by Agent 1 and consumed simultaneously by Agents 2 and 3. It is the single source of truth that makes coherence possible.

```json
{
  "dp_name": "pmsi-activite-hospitaliere",
  "vertical": "Healthcare",
  "data_domain_name": "Healthcare",
  "tables": [
    {
      "name": "sejour_hospitalier",
      "type": "fact",
      "volume": 3000,
      "columns": [
        { "name": "code_ghm",        "trino_type": "VARCHAR", "description": "GHM code from ATIH grouping" },
        { "name": "pole_responsable","trino_type": "VARCHAR", "description": "Medical pole owning the stay" },
        { "name": "tarif_ghs",       "trino_type": "DECIMAL(10,2)", "description": "T2A tariff in euros" },
        { "name": "readmission_30j", "trino_type": "BOOLEAN", "description": "Unplanned 30-day readmission flag" }
      ],
      "anomalies": ["readmission_30j = true at 5% rate"]
    }
  ],
  "relationships": ["sejour_hospitalier.code_ghm → ghm_valorisation.code_ghm"],
  "aida_questions": [
    "Which GHMs generate the most T2A revenue?",
    "What is the 30-day readmission rate per medical pole?"
  ],
  "rls_column": "pole_responsable",
  "sensitive_columns": [
    { "name": "tarif_ghs", "type": "amount", "mask": "range", "trino_type": "DECIMAL(10,2)" }
  ]
}
```

Because both the data script DDL and the YAML views are generated from the same spec, type mismatches become structurally impossible — as long as the agents respect the contract.

---

## Agent 1: The Demo Consultant

**Role:** Translate a business request into a precise, complete Schema Spec JSON.

**Why a dedicated agent?** Schema design requires domain expertise — knowing that a healthcare demo needs a `ghm_valorisation` reference table, that T2A tariffs range from €800 to €12,000, that a `readmission_30j` boolean flag at 5% makes the anomaly detection story compelling. This is consultant-level knowledge, not boilerplate generation.

**Key constraints enforced:**
- 2–4 tables maximum — "one demo, one story"
- `data_domain_name` validated against a fixed list of values that exist on the target cluster (never invented)
- AIDA questions must be answerable by the schema — validated before output
- `dp_name` is client-agnostic (reusable across demos)

**Self-check before saving:** the agent verifies 6 invariants before writing the spec file — FK type consistency, AIDA question coverage, domain name validity, etc.

---

## Agent 2: The Data Modeler

**Role:** Read the Schema Spec and generate a fully standalone Python script that creates the schema, generates synthetic data, and loads it into a Starburst cluster.

**Key design decisions:**

**No external dependencies beyond pip packages.** The generated script requires only `pandas`, `faker`, `trino`, `sqlalchemy`. No shared utility libraries, no `.env` files, no project structure. It runs anywhere Python is installed.

**DDL is derived directly from the spec.** Column names and Trino types come from `spec.tables[].columns[].trino_type` — no interpretation, no inference. If the spec says `BOOLEAN`, the DDL says `BOOLEAN`.

**Upload via SQLAlchemy INSERT, not pystarburst.** `pystarburst` causes segfaults on macOS Python 3.11. The script uses batched `INSERT INTO ... VALUES (...)` statements via the trino SQLAlchemy dialect instead. A custom `_val()` function handles Python→SQL literal conversion with correct `isinstance` ordering (bool before int, datetime before date).

**`--teardown` flag built in.** Every generated script supports `--teardown` to drop the schema cleanly after a demo. No separate cleanup script needed.

```bash
# Load data
python pmsi-activite-hospitaliere-data.py \
  --host cluster.example.com --user demo_user --password *** \
  --catalog iceberg --schema pmsi_raw \
  --location s3://bucket/path/

# Clean up after demo
python pmsi-activite-hospitaliere-data.py \
  --host cluster.example.com --user demo_user --password *** \
  --schema pmsi_raw --teardown
```

---

## Agent 3: The DP Builder

**Role:** Read the same Schema Spec and generate a Starburst Data Product YAML with views, column documentation, sample SQL queries, and AIDA questions.

**Key design decisions:**

**One view per table, plus denormalized JOIN views.** For each `fact → ref` relationship in the spec, the agent creates an additional view that pre-joins the tables — making AIDA queries simpler and more impressive (no manual joins needed in natural language queries).

**Column descriptions come from the spec.** Every column in every view inherits its `description` from `spec.tables[].columns[].description`. This is what appears in the Starburst UI — it needs to be business-meaningful, not technical.

**Sample queries are real SQL, not pseudocode.** Each sample query targets a named view (not the raw tables) and is valid Trino SQL that AIDA can use as a reference.

**15-point self-check before saving.** Includes: no `SELECT *` in `definitionQuery`, `catalogName` always `data_product`, `dataDomainName` in the safe list, all view columns exist in the spec.

---

## Agent 4: The Coherence Checker

**Role:** Read all three artifacts simultaneously and enforce consistency between them. Fix automatically where possible.

**Why this agent exists:** Even when Agents 2 and 3 both read the same spec, subtle drift can occur — a column added to the DDL after an edit, a type normalized differently (`INTEGER` vs `integer`), a view name changed in the YAML that a sample query still references by the old name. The coherence checker is the safety net.

**Ten checks, one rule:** DDL is the source of truth. The YAML aligns to the DDL, never the reverse.

| Check | What it validates |
|---|---|
| DDL completeness | Every spec column is present in the DDL |
| Type consistency | `spec.trino_type` matches DDL type (case-insensitive) |
| View columns vs DDL | Every YAML view column exists in the corresponding DDL table |
| Type alignment | YAML column types (lowercase) match DDL types |
| SELECT coverage | Every column selected in `definitionQuery` exists in DDL |
| Sample query targets | Queries reference views defined in this YAML, not raw tables |
| `dataDomainName` | Must be one of 7 validated values |
| `catalogName` | Must be `data_product` |
| FK representation | Relationships from spec appear in both DDL and YAML views |
| AIDA coverage | Spec AIDA questions are semantically covered by sample queries |

**Output:** a structured report with ✅/⚠️ per check, plus auto-applied fixes logged inline.

---

## The Orchestrator: `/starburst-demo`

**Role:** Single entry point. Takes a business request, sequences the 8-step pipeline, surfaces results.

**Sequencing strategy:**
- Step 1 (Agent 1) is **blocking** — the spec must exist before anything else can start
- Steps 2 and 3 (Agents 2 and 3) are **parallel** — both read the same spec, no dependency between them
- Step 4 (Agent 4) **waits for both** — needs all three artifacts to exist
- Step 5 is a **HITL gate** — pipeline waits for explicit user confirmation before deploying
- Step 6 has an **internal parallel phase**: catalog check (6b) + domain check (6c) + data.py load run simultaneously; only the YAML import (6d) waits for 6b + 6c to complete
- Step 7 (BIAC) runs automatically after 6d succeeds
- Step 8 (lineage) is **on-demand only** — triggered by the phrase `"génère le lineage pour {dp-name}"`

Critical path: `Step1 → (Step2 ‖ Step3) → Step4 → Step5 → (6b ‖ 6c ‖ data.py) → 6d → Step7 → [Step8]`.

**What the user sees:**

```
✅ Step 1 — Spec: dataproduct/Demo/pmsi-activite-hospitaliere-spec.json
✅ Step 2 — Script: dataproduct/Demo/pmsi-activite-hospitaliere-data.py
✅ Step 3 — YAML: dataproduct/Demo/pmsi-activite-hospitaliere-dp.yaml

══════════════════════════════════════════
  Coherence Check — pmsi-activite-hospitaliere
══════════════════════════════════════════
  ✅ DDL completeness (16 columns)
  ✅ Type consistency
  ✅ View columns vs DDL
  ✅ Sample queries vs views
  ✅ dataDomainName: Healthcare
  ✅ catalogName: data_product
  ✅ FK relationships

Résultat : 0 issue — artifacts cohérents et prêts.

[Step 5 — HITL] Review artifacts above. Confirme pour déployer.

✅ Step 6 — Data chargée (3 000 lignes), Data Product importé
✅ Step 7 — BIAC
  pmsi_activite_hospitaliere_superuser  → starburst_service
  pmsi_activite_hospitaliere_user       → RLS: pole_responsable, CLS: tarif_ghs
  pmsi_activite_hospitaliere_data_ing   → cross-DP + iceberg raw

Prochaines étapes :
  • Tester AIDA avec les 6 questions de la spec
  • Générer le lineage → "génère le lineage pour pmsi-activite-hospitaliere"
```

---

## File Naming Convention

All artifacts share the same base name, derived from the `dp_name` in the spec:

```
pmsi-activite-hospitaliere-spec.json   ← Agent 1 output
pmsi-activite-hospitaliere-data.py     ← Agent 2 output
pmsi-activite-hospitaliere-dp.yaml     ← Agent 3 output
```

This makes it immediately obvious which files belong together, and allows the coherence checker to locate all three by prefix without configuration.

---

## What This Replaces

| Before | After |
|---|---|
| 2–3 hours of manual schema design | 2–3 minutes of Agent 1 output + one validation |
| Separate, uncoordinated script and YAML authoring | Single shared spec, parallel generation |
| Type mismatches discovered at demo time | Agent 4 catches and fixes before any file is finalized |
| No cleanup path → cluster accumulates stale schemas | `--teardown` flag on every generated script |
| Domain knowledge in engineer's head | Encoded in agent prompts, reusable across verticals |

---

## Design Patterns Worth Noting

**Shared contract over direct agent communication.** Agents 2 and 3 don't communicate with each other — they both read the spec. This makes them independently testable and replaceable.

**DDL as source of truth.** The coherence checker's single most important rule: if DDL and YAML disagree, fix the YAML. This prevents the common failure mode where documentation diverges from implementation.

**Fail-closed naming.** `dp_name` contains no client name (reusable), `data_domain_name` is validated against a fixed allowlist (no invented values that would fail at deploy time), `catalogName` is hardcoded to `data_product` (the only valid value in production).

**Standalone scripts, no framework dependency.** The generated `*-data.py` file runs with `pip install pandas faker trino sqlalchemy` — nothing else. This is a deliberate constraint: demo scripts must be shareable with customers and colleagues without requiring internal tooling.

---

## Limitations and Known Issues

- **pystarburst segfaults on macOS Python 3.11** — worked around by using SQLAlchemy INSERT batches instead. The trade-off is slower upload (batches of 200 rows vs streaming), acceptable for demo volumes of 2,000–5,000 rows.
- **`SELECT *` in `definitionQuery` is unverifiable** — the coherence checker flags it as a warning but cannot resolve column-level checks without executing the query.
- **Agent 4 cannot auto-fix all discrepancies** — structural issues (missing table in YAML with no corresponding DDL) are reported but require human resolution.
- **Cluster-specific values require human confirmation** — `data_domain_name` must exist on the target cluster; the agent uses a validated allowlist but cannot query the cluster to verify.
- **BIAC view→table mapping is heuristic** — the lineage script uses shared word segments to connect views to source tables; this works well for sensibly named schemas but may produce incorrect arrows for very short or ambiguous names.
- **`allEntities: true` in BIAC grants cannot coexist with entity-level attributes** — if catalog/schema are specified alongside `allEntities`, the REST API returns an error. The BIAC step always uses one or the other, never both.

---

*Built with Claude Code using the Agent tool for parallel subagent orchestration. Skills implemented as Markdown slash commands in `.claude/commands/`.*
