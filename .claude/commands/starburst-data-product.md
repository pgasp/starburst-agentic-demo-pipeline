---
name: starburst-data-product
description: >
  Generate production-ready Starburst Data Product YAML files from a list of tables.
  Use this skill whenever a user provides table names, column lists, DDL, or schema details
  and wants to create a Starburst Data Product definition — including views, column
  documentation, and AIDA sample queries. Also triggers for requests like
  "create a data product", "build a data product YAML", "generate a data product for
  these tables", or any mention of AIDA questions in a Starburst context.
  Always use this skill when the user pastes a table list or schema and mentions
  Starburst, SEP, Galaxy, or Data Products.
---

# Starburst Data Product Generator

You are a Starburst Data Product expert. When this skill is invoked, the user will
provide a list of tables (with or without column details). Generate a complete,
production-ready Starburst Data Product YAML file.

---

## Step 1 — Ask for the domain name FIRST (hard blocker)

**Before doing anything else**, send this message and wait for the answer:

> **What is the exact name of the data domain on the target Starburst cluster?**
> (e.g. `BALE 4`, `Credit Risk`, `Supply Chain`)
>
> This name must exactly match an existing domain on the cluster — an incorrect
> name causes a `DATA_DOMAIN_NOT_FOUND` error at import. If the domain does not
> exist yet, it must be created in Starburst before continuing.

**Do NOT proceed to Step 2 until the user has provided this value.** Do NOT invent a domain name. Do NOT infer it from the table names or business context.

---

## Step 1b — Ask remaining required fields

Once the domain name is confirmed, send a **single follow-up message** asking for any
of the following that cannot be inferred from the user's input:

1. **Owner** — full name and email address.
2. **Data product catalog and schema** — the catalog and schema where the **data product will be published** in Starburst (these become `metadata.catalogName` and `metadata.schemaName`). This is NOT the source tables' location — it is the target namespace where the product's views will be created. Ask as: "In which catalog and schema should the data product be published?" Default: `data_product` catalog (singular — never `data_products`).
   - If the source tables' catalog/schema are not present in the DDL, ask for those separately as: "What is the catalog and schema of the source tables used in the views?"
3. **Platform** — SEP/on-prem or Galaxy?
4. **Client and entity** — for the save path `dataproduct/<Client>/<Entity>/`.
   Ask as: "Under which client and entity should I save this? (e.g. `Acme Corp / Finance`)"

Do NOT invent any of these values.
If the user's input already provides some answers, ask only for the missing ones.
If all four are clear from context, proceed directly to Step 2.

---

## Step 2 — Generate the YAML

Follow this structure exactly. This schema is validated against the Starburst REST API.

```yaml
apiVersion: v1
kind: DataProduct
metadata:
  name: "<domain-name>-data-product"
  catalogName: "<catalog>"
  schemaName: "<schema>"
  dataDomainName: "<Exact Domain Name from Starburst>"
  summary: "<one-line summary>"
  description: |-
    ## Overview
    <1-2 sentences — what this data product is and what it exposes. Who owns it.>

    ## Business context
    <2-3 sentences — regulatory or operational purpose, data lineage, source systems.>

    ## Business use cases
    - <use case 1>
    - <use case 2>
    - <use case 3>

    ## Sample questions for AIDA
    - <Q1>?
    - <Q2>?
    - <Q3>?
    - <Q4>?
    - <Q5>?
owners:
  - name: "<Owner Full Name>"
    email: "<owner@company.com>"
relevantLinks:
  - label: "<Link label>"
    url: "<https://...>"
tags:
  - "<domain>"
  - "<regulation or subject>"
sampleQueries:
  - name: "<Short label — Aggregation>"
    description: "<One-line business description of what this query answers>"
    query: |
      SELECT ...
      FROM <catalogName>.<schemaName>.<view_name>
      WHERE ...
  - name: "<Short label — Trend>"
    description: "<One-line description>"
    query: "SELECT ..."
  - name: "<Short label — Comparison>"
    description: "<One-line description>"
    query: "SELECT ..."
  - name: "<Short label — Compliance/risk>"
    description: "<One-line description>"
    query: "SELECT ..."
  - name: "<Short label — Outlier/anomaly>"
    description: "<One-line description>"
    query: "SELECT ..."
views:
  - name: "<snake_case_name>"
    description: "<Business description of what this view represents>"
    viewSecurityMode: DEFINER
    definitionQuery: |
      SELECT
        <col1>,
        <col2>
      FROM <catalog>.<schema>.<table>
    columns:
      - name: <col1>
        type: <varchar|bigint|date|decimal(p,s)|double|boolean|timestamp>
        description: "<business meaning of this column>"
materializedViews: []
exportMetadata: {}
```

### YAML formatting rules — critical for Starburst parser compatibility

- **No blank lines between YAML fields** at any level (top-level, views, columns) — SnakeYAML fails with BLANK_LINE error. Blank lines *inside* a `|-` scalar value are fine.
- **No inline YAML comments** (`# ...` after a value) — embed notes inside the description string instead
- **`metadata.description:` MUST use `|-`** (literal scalar, strip trailing newline) — this preserves newlines so Markdown headers and lists render in the portal. Never use `>-` (folded) for this field — it collapses all content into one unreadable paragraph.
- **All other `description:` fields** (views, columns) must be plain quoted strings on one line
- **`name:` fields — ASCII only** (`metadata.name`, `views[].name`, `sampleQueries[].name`, tags). This is a Starburst identifier constraint, not a Markdown/YAML constraint — accented characters in `name:` fields cause matching and storage issues in the engine. All `description:` fields (metadata, views, columns) fully support UTF-8 and should keep proper accents and punctuation.

### Name length rules — HARD LIMIT: 40 characters

Every `name:` field in the YAML is subject to a 40-character maximum enforced by Starburst:

- `metadata.name` (product name) — count characters, truncate or abbreviate if over 40
- `sampleQueries[].name` — keep short; abbreviate words if needed (e.g. "without" → "no", "by entity and portfolio" → "by entity/portfolio")
- `views[].name` — use snake_case abbreviations

Always count characters before finalising any name field. When in doubt, shorten.

### Tag format rules

Tags are **plain strings**, not objects:

```yaml
tags:
  - "risk"
  - "basel4"
```

NOT `- value: "risk"` — that format causes a parse error.

### Naming rules

- **Product name**: lowercase, hyphenated, domain-prefixed → `credit-risk-data-product`
- **View name**: snake_case, meaningful business label, not the raw table name → `counterparty_exposure_summary` not `tbl_cp_exp_03`
- **Tags**: include domain + regulation/subject if applicable (e.g. `basel4`, `finance`, `gdpr`)

### metadata.description — Markdown format with 4 sections

The `metadata.description` field uses `|-` (literal block) and **must render as Markdown** in the Starburst portal. Always follow this four-section structure, in order:

1. `## Overview` — what this data product is and what it exposes. Who owns it. 1–2 sentences.
2. `## Business context` — regulatory or operational purpose, data lineage, source systems. 2–3 sentences.
3. `## Business use cases` — bullet list, 3 concrete use cases.
4. `## Sample questions for AIDA` — bullet list of 5 natural language questions.

Rules for sample questions:
- Phrase each as a complete question ending with `?`
- Write in English (including for French customers)
- Questions must be answerable using the views defined in this product — not the source tables
- Keep each question under 80 characters

Example:
```
  description: |-
    ## Overview
    Basel IV corporate exposures data product - EAD, prudential calculations and counterparty profiles. Owner: Mohamed Biane (CA-GIP).

    ## Business context
    Data from the Iceberg lake (`iceberg.bale_iv_raw`), partitioned by legal entity (`ent_id`) and agreement reference (`baapid`), over 4 quarterly 2024 closings.

    ## Business use cases
    - Solvency ratio and RWA calculation by legal entity
    - Analysis of defaulted counterparties with their internal BdF rating
    - Quarterly EAD monitoring and identification of the most critical exposures

    ## Sample questions for AIDA
    - What is the total EAD by risk type at the latest closing?
    - Which counterparties are in default and what is their BdF rating?
    - What is the average PD by IRB calculation mode?
    - What are the 10 largest exposures by EAD in euros?
    - How does quarterly EAD evolve by legal entity?
```

---

### definitionQuery rules

- Always qualify table references as `catalog.schema.table`
- List columns explicitly when DDL is provided; use `SELECT *` only when no columns are known
- If tables share a key column (JOIN is warranted), add a second view entry with a JOIN query and a clear `description` explaining what the join represents

### Column documentation rules

- Every column needs a `type:` field — infer from DDL types or domain knowledge
- Write every `description:` in plain business language — no SQL jargon
- For cryptic column names (e.g. `amt_03`, `col_cd_1`, `flg_y`): infer meaning from domain context and append `(inferred — please verify)` inside the description string — never as a YAML comment
- Never leave a description empty or as a placeholder like "TBD"
- **Enum/categorical columns — always list possible values explicitly.** For any column whose values are a fixed set (type codes, status flags, rating scales, roles, modes), append the exhaustive value list to the description using this pattern:
  `"<business meaning> - values: val1 (meaning), val2 (meaning), val3"`
  This is the single highest-impact signal for AIDA — it allows the assistant to filter, compare, and explain values without guessing.
  Examples:
  - `risk_type_cd`: `"Risk type - values: bilan (on-balance-sheet credits), hors_bilan_confirme (irrevocable commitments, CCF applied), repo, derive"`
  - `calculation_mode`: `"Calculation mode - values: IRB_AVANCE (PD+LGD estimated internally), IRB_FONDATION (regulatory LGD 45%), STANDARD (flat-rate weighting)"`
  - `cpy_role`: `"Role - values: emprunteur (main debtor), garant (provides a Basel IV eligible guarantee)"`
  Data values (e.g. `bilan`, `IRB_AVANCE`, `emprunteur`) are kept exactly as they appear in the data; only the explanatory text is in English.

### Sample query rules

- Write **at least 8 queries** — 5 single-view + 3 multi-view JOIN queries (see below)
- Cover these angles across the 5 single-view queries: Aggregation, Trend, Comparison, Compliance/risk, Outlier/anomaly
- `name:` must be ≤ 40 characters, ASCII only (no accents)
- Use `description:` (not `question:`) — there is no `question:` field in the schema
- Queries must be specific to the domain and views in this product — never generic
- **Always query the data product views, not the source tables.** Use `<catalogName>.<schemaName>.<view_name>` — where `catalogName` and `schemaName` are the data product's published namespace from `metadata`, and `view_name` is one of the `views[].name` entries defined in this same YAML. Never reference source table paths (e.g. `iceberg.bale_iv_raw.*`) in sample queries.
- **Multi-view JOIN queries — write at least 3.** These JOIN two or more data product views together and are the highest-value queries for AIDA: they show how views combine, expose cross-domain insights, and train AIDA on the join keys between views. Pattern:
  ```sql
  SELECT e.col1, c.col2, s.col3
  FROM <catalog>.<schema>.<view_a> e
  JOIN <catalog>.<schema>.<view_b> c
    ON e.key = c.fk AND e.closing_date = c.closing_date AND e.partition_key = c.partition_key
  JOIN <catalog>.<schema>.<view_c> s
    ON e.key = s.fk AND e.closing_date = s.closing_date
  WHERE e.closing_date = DATE 'YYYY-MM-DD'
  ```
  Always join on all partition columns (e.g. `ent_id`, `baapid`, `closing_date`) to avoid cross-joins.

---

## Step 3 — Save the YAML file

After generating the YAML:

1. Use the client and entity confirmed in Step 1.
2. Save path: `dataproduct/<Client>/<Entity>/<product-name>.yaml`
   - Omit `<Entity>` subfolder if no entity was specified.
3. Create the directory if it does not exist (`mkdir -p`).
4. Write the file using the `metadata.name` value as the filename.
5. Confirm the full saved path to the user.

If a file with the same name already exists at that path, warn the user and ask for confirmation before overwriting.

---

## Step 4 — Deployment

Ask the user in a **single message**:
> "To generate the deployment command, I need three things: the Starburst server URL, your username, and your password."

Once provided, show **Option A** by default (REST API). Include Option B only if the user asks.

**Option A — REST API (recommended)**
```bash
curl --location \
  -X POST 'https://<server>/api/v1/dataProduct/products/import?onDuplicate=fail' \
  -u '<username>:<password>' \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/yaml' \
  -H 'X-Trino-Role: system=ROLE{sysadmin}' \
  --data-binary @<product-name>.yaml
```

- Replace `onDuplicate=fail` with `onDuplicate=overwrite` to overwrite an existing product.
- Requires `sysadmin` role or data product admin privileges.

**Option B — SEP CLI**
```bash
sep data-product create --file <product-name>.yaml
```

---

## Edge cases

| Situation | How to handle |
|---|---|
| No catalog/schema provided | Ask in Step 1 — do NOT invent or placeholder-fill |
| No columns known | Use `SELECT *` in definitionQuery; note column descriptions as `(inferred — please verify)` |
| Cryptic column names | Infer + append `(inferred — please verify)` in the description string |
| Multiple related tables with shared keys | Add a second view entry with a JOIN query |
| Domain name unknown | Always ask in Step 1 — wrong value causes `DATA_DOMAIN_NOT_FOUND` at deploy time |
| `name:` field exceeds 40 chars | Shorten — abbreviate, remove filler words, use acronyms. Count characters explicitly |
| Client/entity cannot be inferred | Ask before saving — never invent a path |
| File already exists at save path | Warn and ask before overwriting |
| `DATA_DOMAIN_NOT_FOUND` error at deploy | The domain name in `dataDomainName` doesn't match any configured domain — ask user for the exact string |
| User provides `onDuplicate=fail` error | Suggest rerunning with `onDuplicate=update` to overwrite |
