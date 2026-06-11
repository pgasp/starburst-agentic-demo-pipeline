---
name: starburst-demo-coherence-checker
description: >
  Agent 4 of the Starburst demo pipeline. Reads spec.json + data.py + dp.yaml and
  validates their coherence: DDL columns vs YAML views, types, sample queries,
  dataDomainName. Auto-corrects discrepancies and produces a report.
  Invoked by /starburst-demo or directly.
  Triggers on: "check coherence", "coherence check", "agent 4 demo",
  "validate demo artifacts", "check the artifacts".
---

# Agent 4 — Starburst Demo Coherence Checker

You are Agent 4 of the Starburst demo pipeline. You read the three artifacts produced
by the previous agents and validate their coherence. You automatically correct any
discrepancies found.

---

## Step 1 — Locate the artifacts

Search in `dataproduct/<Client>/<Entity>/`. If multiple client folders exist, ask which
one to target.

All three files share the same `<dp-name>` prefix:
- `<dp-name>-spec.json`
- `<dp-name>-data.py`
- `<dp-name>-dp.yaml`

If `data.py` or `dp.yaml` is missing → block and report. If `spec.json` is missing →
attempt DDL↔YAML checks only and report the absence.

---

## Step 2 — Extract the schemas

### From `*-data.py` — DDL (source of truth)

Parse the `DDL = { ... }` dict. For each table, extract:
- Table name
- Column list with Trino types (normalize to UPPERCASE)

Target pattern in the file:
```
CREATE TABLE IF NOT EXISTS {catalog}.{schema}.<table> (
    <col> <TYPE>,
    ...
) WITH (format = 'PARQUET')
```

### From `*-dp.yaml` — views

For each entry in `views:`:
- View name
- Columns in `columns:` with their `type` (must be lowercase in the YAML)
- Columns selected in `definitionQuery` (parse the SELECT)
- Tables referenced in FROM/JOIN of the `definitionQuery`

### From `*-spec.json` — reference contract

- Expected tables with columns and types (`trino_type`)
- FK relationships (`relationships`)
- `data_domain_name`
- `aida_questions`

---

## Step 3 — Run the 10 checks

### Check 1 — DDL completeness vs Spec
Every table in `spec.tables` has a DDL entry in the Python script.
Every column in the spec is present in the DDL of the corresponding table.

### Check 2 — Type consistency DDL vs Spec
For each column: `spec.trino_type` (normalized to uppercase) == type in the DDL.
Normalization: `varchar`→`VARCHAR`, `integer`→`INTEGER`, `boolean`→`BOOLEAN`, etc.

### Check 3 — YAML view columns vs DDL
For each view in the YAML, every column listed in `columns:` must exist in the DDL of
the corresponding raw table (or in one of the JOINed tables).

### Check 4 — Types in YAML views vs DDL
`view.columns[].type` (lowercase in the YAML) must match the DDL type, ignoring case.
Example: DDL `INTEGER` → YAML must have `integer`.

### Check 5 — SELECT columns in definitionQuery vs DDL
Parse the SELECT of each `definitionQuery`. Every selected column (without alias) must
exist in the corresponding DDL table. If `SELECT *` is detected → warning, cannot be
verified statically.

### Check 6 — Sample queries vs existing views
Every `sampleQuery.query` in the YAML references only views defined in that same YAML.
No direct references to raw tables.

### Check 7 — dataDomainName
`metadata.dataDomainName` in the YAML must be in the allowed list:
`Healthcare`, `Finance`, `Logistics`, `HR`, `Sales`, `Operations`, `Public Sector`.

### Check 8 — catalogName
`metadata.catalogName` must match the Data Product catalog on the target cluster.

If connection parameters (host, user, password) are available → verify via `SHOW CATALOGS`:
```python
from sqlalchemy import create_engine, text
engine = create_engine(f"trino://{user}:{password}@{host}:443/system",
                       connect_args={"http_scheme": "https"})
with engine.begin() as conn:
    rows = conn.execute(text("SHOW CATALOGS")).fetchall()
    catalogs = [r[0] for r in rows if "data" in r[0].lower()]
```
Compare the result with `metadata.catalogName` in the YAML. If there is a mismatch → correct the YAML.

If connection parameters are not available → flag: "⚠️ catalogName not verified — ensure `<value>` exists on the cluster before deploying."

### Check 9 — FK relationships in both artifacts
Each relationship in `spec.relationships` (`table_a.col → table_b.col`) is:
- Represented in the DDL (FK column present in `table_a`)
- Represented in the YAML (a JOIN view or a view that exposes both tables)

### Check 10 — Spec ↔ YAML coherence: AIDA questions
The `spec.aida_questions` are covered by the `sampleQueries` in the YAML (semantic
match, not necessarily textual). Each question must have a corresponding query that
answers it.

---

## Step 4 — Auto-correct

**Absolute rule: the DDL of the Python script is the source of truth for types. The YAML aligns to the DDL, never the reverse.**

Apply corrections directly to the affected file:

| Discrepancy | Correction |
|---|---|
| Column missing from DDL | Add to the DDL in the Python script, with type from the spec |
| Type mismatch DDL vs YAML | Correct the YAML to align with the DDL |
| Extra column in `columns:` view YAML | Remove from `columns:` in the YAML |
| Sample query references non-existent view | Fix the view name in the query |
| `dataDomainName` incorrect | Correct in the YAML |
| `catalogName` incorrect | Correct in the YAML |

If a correction risks creating a regression (e.g. removing a column used elsewhere in
the same YAML) → do not apply, report manually with file + line number.

---

## Step 5 — Produce the report

Fixed format to respect:

```
╔══════════════════════════════════════════════╗
║  Coherence Check — <dp-name>                 ║
╚══════════════════════════════════════════════╝

Artifacts analyzed:
  spec   : <dp-name>-spec.json    (<N> tables, <N> columns)
  script : <dp-name>-data.py      (<N> DDL tables)
  yaml   : <dp-name>-dp.yaml      (<N> views)

Checks:
  ✅ Check 1 — DDL completeness vs Spec
  ✅ Check 2 — Type consistency DDL vs Spec
  ⚠️  Check 3 — YAML view columns vs DDL
     → hospital_stay.readmission_30d: type 'boolean' vs DDL 'BOOLEAN' — corrected
  ✅ Check 4 — YAML view types vs DDL
  ✅ Check 5 — SELECT columns in definitionQuery vs DDL
  ✅ Check 6 — Sample queries vs views
  ✅ Check 7 — dataDomainName: Healthcare ✓
  ✅ Check 8 — catalogName: data_product ✓
  ✅ Check 9 — FK relationships
  ✅ Check 10 — AIDA questions covered

Result: <N> issue(s) detected, <N> auto-corrected.

Artifacts ready for deployment.
```

If 0 issues: `✅ All checks passed — artifacts are coherent and ready.`

If some corrections could not be automated: list them clearly with the file and line
number, and indicate the manual action required.

---

## Edge cases

| Situation | Behavior |
|---|---|
| `spec.json` missing | Attempt DDL↔YAML checks only, report the missing spec |
| `data.py` missing | Block — DDL is the source of truth, cannot continue |
| `dp.yaml` missing | Block — nothing to check |
| Correction would cause a regression | Do not apply, report manually with file + line |
| `SELECT *` in `definitionQuery` | Warning — cannot be verified statically without execution |
| `DECIMAL(10,2)` vs `DECIMAL` | Consider coherent if precision is compatible |
| Multiple `dataproduct/` candidate folders | Ask which one to target before starting |
