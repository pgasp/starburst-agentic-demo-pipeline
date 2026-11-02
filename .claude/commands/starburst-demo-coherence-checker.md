---
name: starburst-demo-coherence-checker
description: >
  Agent 4 of the Starburst demo pipeline. Reads spec.json + data.py + dp.yaml and validates
  their consistency: DDL columns vs YAML views, types, sample queries, dataDomainName.
  Automatically fixes discrepancies and produces a report.
  Invoked by /starburst-demo or directly.
  Triggers on: "check consistency", "coherence check", "agent 4 demo",
  "validate the demo artifacts", "check the artifacts".
---

# Agent 4 — Starburst Demo Coherence Checker

You are Agent 4 of the Starburst demo pipeline. You read the three artifacts produced by the previous agents and validate their consistency. You automatically fix the discrepancies detected.

---

## Step 1 — Locate the artifacts

Search in `dataproduct/<Client>/<Entity>/`. If several customer folders exist, ask which one to target.

The three files share the same `<dp-name>` prefix:
- `<dp-name>-spec.json`
- `<dp-name>-data.py`
- `<dp-name>-dp.yaml`

If `data.py` or `dp.yaml` is missing → block and report. If `spec.json` is missing → attempt the DDL↔YAML checks only, report the absence.

---

## Step 2 — Extract the schemas

### From `*-data.py` — DDL (source of truth)

Parse the `DDL = { ... }` dict. For each table, extract:
- Table name
- List of columns with their Trino type (normalize to UPPERCASE)

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
- Tables referenced in the FROM/JOIN of `definitionQuery`

### From `*-spec.json` — reference contract

- Expected tables with columns and types (`trino_type`)
- FK relationships (`relationships`)
- `data_domain_name`
- `aida_questions`

---

## Step 3 — Run the 10 checks

### Check 1 — DDL completeness vs Spec
Each table in `spec.tables` has a DDL entry in the Python script.
Each column of the spec is present in the DDL of the corresponding table.

### Check 2 — DDL vs Spec type consistency
For each column: `spec.trino_type` (normalized to uppercase) == type in the DDL.
Normalization: `varchar`→`VARCHAR`, `integer`→`INTEGER`, `boolean`→`BOOLEAN`, etc.

### Check 3 — YAML view columns vs DDL
For each view in the YAML, each column listed in `columns:` must exist in the DDL of the corresponding raw table (or in one of the JOINed tables).

### Check 4 — Types in YAML views vs DDL
`view.columns[].type` (lowercase in the YAML) must match the DDL type, ignoring case.
Example: DDL `INTEGER` → YAML must have `integer`.

### Check 5 — SELECT columns in definitionQuery vs DDL
Parse the SELECT of each `definitionQuery`. For **direct views**: each selected column must exist in the DDL table. For **JOIN views** with aliases (`a.col1`, `b.col2`): strip the table prefix (`a.`, `b.`) before checking existence in the DDL of the corresponding table (left = fact, right = dim). If `SELECT *` is detected → warning, cannot be verified statically.

### Check 6 — Sample queries vs existing views
Each `sampleQuery.query` in the YAML references only views defined in that same YAML. No direct reference to raw tables.

### Check 7 — dataDomainName
`metadata.dataDomainName` in the YAML must be in the allowed list:
`Healthcare`, `Finance`, `Logistics`, `HR`, `Sales`, `Operations`, `Public Sector`.

### Check 8 — catalogName
`metadata.catalogName` must match the Data Product catalog of the target cluster.

If the connection parameters (host, user, password) are available → check via `SHOW CATALOGS`:
```python
from sqlalchemy import create_engine, text
engine = create_engine(f"trino://{user}:{password}@{host}:443/system",
                       connect_args={"http_scheme": "https"})
with engine.begin() as conn:
    rows = conn.execute(text("SHOW CATALOGS")).fetchall()
    catalogs = [r[0] for r in rows if "data" in r[0].lower()]
```
Compare the result with `metadata.catalogName` in the YAML. If there is a discrepancy → fix the YAML.

If the connection parameters are not available → report: "⚠️ catalogName not verified — make sure `<value>` exists on the cluster before deploying."

### Check 9 — FK relationships in both artifacts
Each relationship in `spec.relationships` (`table_a.col → table_b.col`) is:
- Represented in the DDL (FK column present in `table_a`)
- Represented in the YAML (a JOIN view or a view that exposes both tables)

### Check 10 — spec ↔ YAML consistency: AIDA questions
The `spec.aida_questions` are covered by the YAML `sampleQueries` (semantic match, not necessarily textual). Each question must have an associated query that answers it.

### Check 11 — Length of `name:` fields ≤ 40 characters
Check in the YAML: `metadata.name`, each `views[].name`, each `sampleQueries[].name`. Any value > 40 characters → truncate or abbreviate in the YAML and report.

---

## Step 4 — Fix automatically

**Absolute rule: the Python script DDL is the source of truth for types. The YAML aligns with the DDL, never the other way around.**

Apply directly in the file concerned:

| Discrepancy | Fix |
|---|---|
| Column missing in DDL | Add it to the Python script DDL, with the type from the spec |
| DDL vs YAML type mismatch | Fix the YAML to align with the DDL |
| Extra column in YAML view `columns:` | Remove it from `columns:` in the YAML |
| Sample query references a non-existent view | Fix the view name in the query |
| Incorrect `dataDomainName` | Fix in the YAML |
| Incorrect `catalogName` | Fix in the YAML |
| `name:` > 40 characters | Truncate/abbreviate in the YAML + report |

If a fix risks creating a regression (e.g. removing a column used elsewhere in the same YAML) → do not apply it, report it for manual action with file + line.

---

## Step 5 — Produce the report

Fixed format to follow:

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
  ✅ Check 2 — DDL types vs Spec
  ⚠️  Check 3 — YAML view columns vs DDL
     → sejour_hospitalier.readmission_30j : type 'boolean' vs DDL 'BOOLEAN' — fixed
  ✅ Check 4 — YAML view types vs DDL
  ✅ Check 5 — definitionQuery SELECT vs DDL
  ✅ Check 6 — Sample queries vs views
  ✅ Check 7 — dataDomainName: Healthcare ✓
  ✅ Check 8 — catalogName: data_product ✓
  ✅ Check 9 — FK relationships
  ✅ Check 10 — AIDA questions covered
  ✅ Check 11 — name: length ≤ 40 chars

Result: <N> issue(s) detected, <N> fixed automatically.

Artifacts ready for deployment.
```

If 0 issues: `✅ All checks pass — artifacts consistent and ready.`

If some fixes cannot be automated: list them clearly with the file and line concerned, and state the manual action required.

---

## Edge cases

| Situation | Behavior |
|---|---|
| `spec.json` missing | Attempt DDL↔YAML checks only, report the missing spec |
| `data.py` missing | Block — the DDL is the source of truth, cannot continue |
| `dp.yaml` missing | Block — nothing to check |
| Fix creates a regression | Do not apply, report for manual action with file + line |
| `SELECT *` in `definitionQuery` | Warning — cannot be verified statically without execution |
| `DECIMAL(10,2)` vs `DECIMAL` | Treat as consistent if the precision is compatible |
| Several candidate `dataproduct/` folders | Ask which one to target before starting |
