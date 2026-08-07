---
name: starburst-biac
description: >
  Manage Starburst (SEP Built-in Access Control / BIAC) entitlements via REST API:
  roles, row-level security (RLS / row filters), column-level security (CLS / column masks),
  privilege grants, user↔role assignments, audit and verification.
  Triggers: "set up governance", "configure RLS/CLS", "create a role",
  "row filter", "column mask", "mask columns", "restrict by country",
  "grant access to", "who can see", "entitlement audit", "manage BIAC permissions",
  "setup access control", "grant select", "assign the role".
---

# BIAC Governance — managing Starburst entitlements via API

Manages Starburst Enterprise **Built-in Access Control (BIAC)** via REST API:
roles, row filters (RLS), column masks (CLS), grants, assignments, audit.

> ⚠️ **Security.** This skill modifies cluster access control. Any destructive operation
> or one that broadens permissions (`DELETE`, revoke, permissive grant, `allEntities`)
> must be **summarised and confirmed** before execution. Least privilege by default.
> Never display secrets (password/token). Refuse manifestly over-permissive grants
> without explicit confirmation.

---

## Step 0 — Resolve server configuration (MANDATORY INPUT)

**Server config is an input to the skill, never hardcoded.**

1. If the user provides a cluster name as argument (e.g. `/starburst-biac warpspeed2`),
   use `dataproduct/servers/.env.<cluster>`.
2. Otherwise, list `dataproduct/servers/.env.*` and **ask which one to use** (do not guess).
3. The user may also provide an explicit `.env` file path, or direct parameters.
   If they paste a password in plaintext: accept it, **do not display it back**, and remind them to rotate it.

**Parse the `.env` file in Python** (never `source`/`set -a`: values may contain
special characters that break the shell):

```python
def load_env(path):
    env={}
    for l in open(path):
        l=l.strip()
        if "=" in l and not l.startswith("#"):
            k,v=l.split("=",1); env[k.strip()]=v.strip().strip('"').strip("'")
    return env
```

Expected keys: `SB_HOST`, `SB_PORT` (default 443), `SB_USER`, `SB_PASSWORD`.
Confirm to the user: `Host=… User=… Port=… (password masked)`.

---

## Connection rules

- **Connect directly to the Trino host** (`https://<SB_HOST>:<SB_PORT>`), **not** the MCP proxy
  (the MCP proxy is read-only and may return 502s with no impact on the direct API).
- All write operations require the header **`X-Trino-Role: system=ROLE{sysadmin}`** (or a BIAC admin role).
- Basic auth (`-u user:password` / `Authorization: Basic …` header).
- Prefer `urllib`/`requests` in Python to capture returned `id` values; `curl` otherwise.

## Golden rule — start from the OpenAPI spec

**Always fetch the contract before writing**: `GET /api/v1/openApi`.
Never blindly guess endpoints. Extract paths + payload schemas from it.

---

## BIAC endpoint map (`/api/v1/biac`)

| Operation | Method + path | Body |
|---|---|---|
| List / create role | `GET`/`POST /roles` | `{"name": "<a-z0-9_>"}` |
| Get / delete role | `GET`/`DELETE /roles/{id}` | — |
| Create RLS expression | `POST /expressions/rowFilter` | `{name, expression, description}` → `{id}` |
| Create CLS expression | `POST /expressions/columnMask` | `{name, expression, description}` → `{id}` |
| Attach row filter | `POST /roles/{id}/rowFilters` | `{entity, expressionId, forceNone}` |
| Attach column mask | `POST /roles/{id}/columnMasks` | `{entity, expressionId, forceNone}` |
| Grant privilege | `POST /roles/{id}/grants` | `{effect, action, entity}` |
| Assign role→user | `POST /subjects/users/{user}/assignments` | `{roleId, roleAdmin}` |
| Assign role→group | `POST /subjects/groups/{group}/assignments` | `{roleId, roleAdmin}` |
| List assignments | `GET /subjects/users/{user}/assignments` | — |

**`entity` (TableEntityData)**:
```json
{"category":"TABLES","catalog":"<cat>","schema":"<sch>","table":"<tbl>","columns":["<col>"]}
```
- `columns` only for column masks.
- `allEntities:true` ⇒ **no other attribute allowed** (else 400). To target a schema/table, list explicitly.

**Useful enums** — `Action`: `SELECT, INSERT, UPDATE, DELETE, SHOW, CREATE, ALTER, DROP, EXECUTE, …` ·
`Effect`: `ALLOW, DENY, ALLOW_WITH_GRANT_OPTION, APPLY_ROW_FILTER, APPLY_COLUMN_MASK, …`

---

## Standard workflow — setting up RLS + CLS

**Mandatory order** (expression must exist before filter/mask):

1. **Create role(s)** — names in lowercase `a-z0-9_` only.
2. **Create expressions** (`/expressions/rowFilter`, `/expressions/columnMask`) → capture the returned `id`.
   - RLS: e.g. `country = 'FRA'`; `country IN ('FRA','DEU','ITA')`.
   - CLS: expression references the masked column, e.g. `substr(name,1,1)` or `substr(firstname,1,1) || '***'`. Return type must match the column type.
3. **Attach** row filters / column masks to roles, on **each affected view/table**.
4. **Grants**: `SELECT` per table (not `allEntities` with attributes).
5. **Assign** real users/groups to roles.
6. **Verify** (see below).

## Verification — ALWAYS double-check

1. **Read-back**: `GET` the `rowFilters` / `columnMasks` / `grants` / `assignments` to confirm persistence.
2. **Functional test**: query a view **assuming the role** (the engine then enforces the policy).
   ```python
   conn = trino.dbapi.connect(host=…, port=…, user=…,
       http_scheme="https",
       auth=trino.auth.BasicAuthentication(user, password),
       roles={"system": "<role>"})
   ```
   Compare results between two roles (filtered rows, masked columns).
   > sysadmin **bypasses** filters: always test by forcing a role, never as sysadmin.

---

## Audit ("who can see what")

For a role: `GET /roles/{id}/{rowFilters,columnMasks,grants}` + resolve `expressionId`
via `GET /expressions/{rowFilter|columnMask}/{id}`. Present as a readable table.

---

## Output format

```
Cluster   : <host>  (config: dataproduct/servers/.env.<cluster>)
Operation : <setup-rls | setup-cls | grant | assign | audit | verify | teardown>

Roles       : <names (id)>
Expressions : <name → expression>
Row filters : <role → table → expr>
Col masks   : <role → table.column → expr>
Grants      : <role → action → entity>
Assignments : <user/group → role>

Verification:
  Read-back  : ✅ persisted
  Functional : <result per role (rows/columns observed)>

⚠️ Remaining manual steps: <assignment of real users, app/AIDA connection identity…>
```

---

## Edge cases

| Situation | Behaviour |
|---|---|
| No cluster provided | List `dataproduct/servers/.env.*` and ask — do not guess |
| `.env` file with special characters | Parse in Python, never `source` shell |
| Role name with uppercase/hyphens | Reject/convert to `a-z0-9_` (API returns 400 otherwise) |
| Row filter / column mask without expression | Create the expression first, reuse its `id` |
| `Grant allEntities:true` + catalog/schema/table | 400 — switch to per-table grants |
| Endpoint not found | Fetch `GET /api/v1/openApi` and re-read paths — do not guess |
| Security test as sysadmin | Ineffective (bypasses filters) — assume the role via `roles={"system":…}` |
| Target connector without `CREATE SCHEMA` (Oracle…) | Out of BIAC scope, but flag to the user |
| Data Product view in `DEFINER` mode | Role only needs `SELECT` on the view; filters/masks still apply to the session user |
| Destructive operation (`DELETE`, revoke) | Summarise + confirm before executing |
| Password pasted in plaintext | Do not display it back; remind user to rotate it |

---

## Anti-patterns to avoid

Do **not** probe endpoints blindly by trial and error (expensive and risky on a security API).
The OpenAPI spec (`/api/v1/openApi`) is the source of truth: read it **first**.
