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
              │   Agent 1: Consultant     │
              │                           │
              │  Business need            │
              │       ↓                   │
              │  Schema Spec JSON         │
              └───────────┬───────────────┘
                          │  Shared contract
               ┌──────────┴──────────┐
               ↓                     ↓   (parallel)
  ┌────────────────────┐  ┌──────────────────────┐
  │  Agent 2           │  │  Agent 3              │
  │  Data Modeler      │  │  DP Builder           │
  │                    │  │                       │
  │  DDL + Python      │  │  Starburst Data       │
  │  data script       │  │  Product YAML         │
  └──────────┬─────────┘  └──────────┬────────────┘
             └──────────┬────────────┘
                        ↓
          ┌─────────────────────────────┐
          │  Agent 4: Coherence Checker │
          │                             │
          │  DDL ↔ YAML validation      │
          │  Auto-fix + report          │
          └─────────────────────────────┘
                        ↓
         dataproduct/<Client>/<Entity>/
         ├── *-spec.json
         ├── *-data.py
         └── *-dp.yaml
```

---

## ## The Architecture detailled

Multi-agent pipeline that transforms a business request into a complete Starburst demo (dataset + Data Product YAML) deployable on a cluster.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    /starburst-demo (orchestrator)                   │
│                    .claude/commands/starburst-demo.md               │
│                                                                     │
│  1. Collects business context (vertical, use case, client)         │
│  2. Spawns agents in sequence                                      │
│  3. Displays results + final summary                               │
│  4. Offers cluster deployment                                      │
└──────────────┬──────────────────────────────────────────────────────┘
               │ foreground (blocking)
               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Agent 1 — starburst-demo-consultant                                │
│  starburst-demo-consultant.md  (235 lines)                         │
│                                                                     │
│  INPUT  : business context (vertical, use case, audience)          │
│  OUTPUT : <dp-name>-spec.json                                      │
│                                                                     │
│  Role : Senior SE — translates a business request into a Schema    │
│         Spec JSON (tables, columns, types, volumes, AIDA           │
│         questions, RLS policies, seed data)                        │
└──────────────┬──────────────────────────────────────────────────────┘
               │ spec.json → two parallel agents
               ├─────────────────────────┐
               ▼                         ▼
┌──────────────────────────┐  ┌──────────────────────────────────────┐
│  Agent 2                 │  │  Agent 3                             │
│  starburst-demo-         │  │  starburst-demo-dp-builder           │
│  data-modeler            │  │  starburst-demo-dp-builder.md        │
│  (502 lines)             │  │  (378 lines)                         │
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
│  Agent 4 — starburst-demo-coherence-checker                         │
│  starburst-demo-coherence-checker.md  (184 lines)                  │
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
│  Deployment (in /starburst-demo Step 6)                            │
│                                                                     │
│  python data.py --host --user --password --catalog --schema        │
│  GET  /api/v1/dataProduct/domains   → check/create domain          │
│  POST /api/v1/dataProduct/products/import  → deploy dp.yaml        │
└─────────────────────────────────────────────────────────────────────┘
```

---


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
        { "name": "duree_sejour",    "trino_type": "INTEGER", "description": "Length of stay in days" },
        { "name": "readmission_30j", "trino_type": "BOOLEAN", "description": "Unplanned 30-day readmission flag" }
      ],
      "anomalies": ["readmission_30j = true at 5% rate"]
    }
  ],
  "relationships": ["sejour_hospitalier.code_ghm → ghm_valorisation.code_ghm"],
  "aida_questions": [
    "Which GHMs generate the most T2A revenue?",
    "What is the 30-day readmission rate per medical pole?"
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

**Role:** Single entry point. Takes a business request, sequences the four agents, surfaces results.

**Sequencing strategy:**
- Agent 1 is **blocking** — the spec must exist before anything else can start
- Agents 2 and 3 are **parallel** — both read the same spec, no dependency between them
- Agent 4 **waits for both** — needs all three artifacts to exist

This gives the minimum critical path: `Agent1 → (Agent2 ‖ Agent3) → Agent4`.

**What the user sees:**

```
✅ Agent 1 — Spec: dataproduct/Demo/pmsi-activite-hospitaliere-spec.json
✅ Agent 2 — Script: dataproduct/Demo/pmsi-activite-hospitaliere-data.py
✅ Agent 3 — YAML: dataproduct/Demo/pmsi-activite-hospitaliere-dp.yaml

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

Prochaines étapes :
  1. Charger les données → python *-data.py --host ...
  2. Déployer le Data Product → POST /api/v1/dataProduct/products/import
  3. Tester AIDA avec les 6 questions de la spec
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

---

*Built with Claude Code using the Agent tool for parallel subagent orchestration. Skills implemented as Markdown slash commands in `.claude/commands/`.*
