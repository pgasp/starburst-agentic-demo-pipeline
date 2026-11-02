---
name: starburst-demo
description: >
  Orchestrator of the Starburst demo pipeline. Takes a business request (vertical,
  use case, customer) and orchestrates 4 agents to produce a consistent dataset +
  data product: consultant → [data modeler ‖ dp builder] → coherence checker.
  Triggers on: "prepare a demo for", "generate a full demo", "demo pipeline",
  "create a starburst demo for", "pipeline demo", "full demo for", "demo for".
---

## Pipeline overview

```
User request
     ↓
Agent 1: starburst-demo-consultant   → <dp-name>-spec.json
     ↓
     ├── Agent 2: starburst-demo-data-modeler    → <dp-name>-data.py   ┐ (parallel)
     └── Agent 3: starburst-demo-dp-builder      → <dp-name>-dp.yaml   ┘
     ↓
Agent 4: starburst-demo-coherence-checker → report + fixes
     ↓
HITL Review → deployment confirmation
     ↓
     ├── 6b: SHOW CATALOGS (catalogName)   ┐
     ├── 6c: GET/POST domain               ┘ (parallel) → 6d: POST dp.yaml import
     └── data.py (iceberg raw load)        ┘
     ↓
Step 7: BIAC — auto after Step 6 (superuser / user / data_ing)
     ↓
(optional) Step 8: Lineage — trigger: "generate the lineage for <dp-name>"
```

---

## Step 1 — Collect the business context

If arguments are provided, use them directly.
Otherwise, ask in **a single message**:

> "To generate this demo, tell me:
> - **Vertical / industry** (e.g. Healthcare, Banking, Logistics)
> - **Main use case** (e.g. PMSI monitoring, fraud detection)
> - **2–3 business questions** the customer must be able to ask
> - **Customer or event** (e.g. Santexpo, BNP Paribas)
> - **Audience**: IT leadership, Business, C-level?"

---

## Step 2 — Agent 1: Demo Consultant (foreground)

Use the **Agent** tool to spawn a sub-agent with these instructions:

> "You are Agent 1 of the Starburst demo pipeline. Use the Skill tool to invoke `starburst-demo-consultant`: `Skill(skill='starburst-demo-consultant', args='[full business context]')`. You are in orchestrator mode — skip the user validation (Step 4 of the skill) and save the spec directly to `dataproduct/<Client>/<Entity>/<dp-name>-spec.json`. Return the full path of the saved file and the JSON content of the spec."

Wait for completion — the spec is required before continuing.

Display: `✅ Agent 1 — Spec produced: <path>`

---

## Step 3 — Agents 2 & 3 in parallel (foreground)

Spawn **two agents simultaneously** in the same message (two Agent calls in the same response):

**Agent 2 — Data Modeler:**
> "You are Agent 2 of the Starburst demo pipeline. Use the Skill tool to invoke `starburst-demo-data-modeler`: `Skill(skill='starburst-demo-data-modeler', args='<spec.json-path>')`. The spec is here: `<spec.json-path>`. Generate and save `<dp-name>-data.py` in the same folder. Return the file path and a summary of the generated tables."

**Agent 3 — DP Builder:**
> "You are Agent 3 of the Starburst demo pipeline. Use the Skill tool to invoke `starburst-demo-dp-builder`: `Skill(skill='starburst-demo-dp-builder', args='<spec.json-path>')`. The spec is here: `<spec.json-path>`. Generate and save `<dp-name>-dp.yaml` in the same folder. Return the file path and a summary of the generated views."

Wait for both to complete.

Display:
```
✅ Agent 2 — Data script: <path>
✅ Agent 3 — Data Product YAML: <path>
```

---

## Step 4 — Agent 4: Coherence Checker (foreground)

Spawn an agent with:

> "You are Agent 4 of the Starburst demo pipeline. Use the Skill tool to invoke `starburst-demo-coherence-checker`: `Skill(skill='starburst-demo-coherence-checker', args='<folder>')`. The artifacts are in: `<folder>`. Analyze the three files (<dp-name>-spec.json, <dp-name>-data.py, <dp-name>-dp.yaml), apply the necessary fixes, and return the full report."

Display the coherence report as is.

---

## Step 5 — Summary and next steps

Display a final summary:

```
══════════════════════════════════════════
  Demo pipeline complete — <dp-name>
══════════════════════════════════════════

Artifacts generated in dataproduct/<Client>/<Entity>/:
  📋 <dp-name>-spec.json     — Schema Spec (contract)
  🐍 <dp-name>-data.py       — Data script (<N> tables, <N> rows)
  📦 <dp-name>-dp.yaml       — Data Product YAML (<N> views)

Consistency: <✅ OK | ⚠️ N fixes applied>

Next steps:
  1. Deploy → data (iceberg raw) + Data Product + BIAC in a single command
  2. Test AIDA with the spec questions
  3. Generate the lineage → "generate the lineage for <dp-name>"
```

Then ask:
> "Do you want me to deploy to a cluster now? (data load + Data Product import + BIAC setup — I'll need the host, user and password)"

If yes → go to Step 6.

---

## Step 6 — Deployment (parallelized)

### 6a — Collect the cluster parameters

Ask in a single message if missing: host, user, password, target domain.

### 6b + 6c + data.py — Parallel phase (launch simultaneously)

The three operations are independent — start them in the same call:

**6b — Validate the catalogName** (queries `system`, no domain needed):
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
- A single result → use it; several → ask; none → ask the user.

**6c — Validate / create the domain** (independent REST call):
`GET /api/v1/dataProduct/domains` — if missing → `POST /api/v1/dataProduct/domains`.

**data.py — Load the data into Iceberg raw** (independent of the DP catalog and the domain):
```bash
python <dp-name>-data.py \
  --host <host> --user <user> --password <password> \
  --catalog iceberg --schema <schema_raw> \
  --location s3://<bucket>/<path>/
```

Wait for all three to finish before continuing.

Display:
```
✅ 6b — catalogName: <catalog>
✅ 6c — Domain: <domain> (created | existing)
✅ data.py — <N> rows loaded into iceberg.<schema_raw>
```

### 6d — Import the Data Product YAML

Update `catalogName` in the YAML with the value found in 6b, then:

```
POST /api/v1/dataProduct/products/import
Content-Type: application/yaml
Body: <dp-name>-dp.yaml (with updated catalogName)
```

If 409 (product already exists) → `catalogName` is immutable, delete it from the UI then re-run.

---

## Step 7 — BIAC Setup (automatic after deployment)

Launch immediately after Step 6 is confirmed. Do not wait for user confirmation.

### 7a — Derive the identifiers from the spec

```python
dp_name   = spec["dp_name"]
segments  = dp_name.replace("-", "_").split("_")[:3]
prefix    = "_".join(segments)
# e.g. "bnpp-cib-fraude-corporate" → "bnpp_cib_fraude"

rls_col    = spec.get("rls_column")           # None if missing
sensitive   = spec.get("sensitive_columns", [])
catalog     = dp_yaml["metadata"]["catalogName"]  # e.g. data_products
schema      = dp_yaml["metadata"]["schemaName"]   # e.g. cib_fraude_transactions_corporate
views       = [v["name"] for v in dp_yaml.get("views", [])]

# Values for substitution in the script template:
views_list    = repr(views)        # e.g. ['vue_a', 'vue_b']
rls_col_repr  = repr(rls_col)      # "None" or '"column_name"'
sensitive_repr = repr(sensitive)   # Python literal list of the sensitive_columns
# env_path : path to the cluster's .env file (e.g. "dataproduct/servers/.env.warpspeed2")
#             → taken from the parameters collected in Step 6a
```

If `demo_user` is unknown (not in the spec, no current session): ask the user once.

### 7b — Generate and run the BIAC script

Generate a Python script in the scratchpad, instantiated with the values above from this template, then run it with `python`:

```python
"""BIAC Setup — {dp_name}"""
import requests, sys

def load_env(path):
    env={}
    for l in open(path):
        l=l.strip()
        if "=" in l and not l.startswith("#"):
            k,v=l.split("=",1); env[k.strip()]=v.strip().strip('"').strip("'")
    return env

env  = load_env("{env_path}")
HOST = env["SB_HOST"]; PORT = env.get("SB_PORT","443")
USER = env["SB_USER"]; PWD  = env["SB_PASSWORD"]
BASE = f"https://{HOST}:{PORT}"; AUTH = (USER, PWD)
HW   = {"Content-Type":"application/json","Accept":"application/json","X-Trino-Role":"system=ROLE{sysadmin}"}  # {sysadmin} = Starburst BIAC syntax, not a placeholder
HR   = {"Accept":"application/json","X-Trino-Role":"system=ROLE{sysadmin}"}  # same

CATALOG="{catalog}"; SCHEMA="{schema}"; VIEWS={views_list}
RLS_COL={rls_col_repr}  # None or "column_name"
DEMO_USER="{demo_user}"; PREFIX="{prefix}"

def post(p,b):
    r=requests.post(f"{BASE}{p}",auth=AUTH,headers=HW,json=b,verify=True)
    if r.status_code not in(200,201): print(f"  ERR POST {p} -> {r.status_code}: {r.text[:200]}"); sys.exit(1)
    return r.json()
def get(p):
    r=requests.get(f"{BASE}{p}",auth=AUTH,headers=HR,verify=True); r.raise_for_status()
    d=r.json(); return d.get("result",d) if isinstance(d,dict) and "result" in d else d

print("-- 1. Roles --")
existing={r["name"]:r["id"] for r in get("/api/v1/biac/roles")}
ids={}
for rname in [f"{PREFIX}_superuser",f"{PREFIX}_user",f"{PREFIX}_data_ing"]:
    if rname in existing: ids[rname]=existing[rname]; print(f"  exists: {rname}")
    else: res=post("/api/v1/biac/roles",{"name":rname}); ids[rname]=res["id"]; print(f"  created: {rname} id={res['id']}")
sup_id=ids[f"{PREFIX}_superuser"]; usr_id=ids[f"{PREFIX}_user"]; ing_id=ids[f"{PREFIX}_data_ing"]

print("-- 2. RLS --")
if RLS_COL:
    rls=post("/api/v1/biac/expressions/rowFilter",{"name":f"{PREFIX}_rls_{RLS_COL}","expression":f"{RLS_COL} = current_user","description":f"RLS {RLS_COL}"})
    rls_id=rls["id"]; print(f"  RLS expr id={rls_id}")
    for v in VIEWS:
        post(f"/api/v1/biac/roles/{usr_id}/rowFilters",{"entity":{"category":"TABLES","catalog":CATALOG,"schema":SCHEMA,"table":v},"expressionId":rls_id,"forceNone":False})
    print(f"  RLS attached ({len(VIEWS)} views)")

print("-- 3. CLS --")
SENSITIVE={sensitive_repr}  # list of {"name","mask","trino_type"}
for col in SENSITIVE:
    if col["mask"]=="range":   expr=f"CAST(ROUND(CAST({col['name']} AS DOUBLE)/100000)*100000 AS {col['trino_type']})"
    elif col["mask"]=="prefix": expr=f"CONCAT(SUBSTR({col['name']},1,4),'****')"
    else:                       expr=f"CAST(ROUND(CAST({col['name']} AS DOUBLE)/10)*10 AS INTEGER)"
    res=post("/api/v1/biac/expressions/columnMask",{"name":f"{PREFIX}_cls_{col['name']}","expression":expr,"description":f"CLS {col['name']}"})
    cls_id=res["id"]; print(f"  CLS {col['name']} id={cls_id}")
    for v in VIEWS:
        post(f"/api/v1/biac/roles/{usr_id}/columnMasks",{"entity":{"category":"TABLES","catalog":CATALOG,"schema":SCHEMA,"table":v,"columns":[col["name"]]},"expressionId":cls_id,"forceNone":False})

print("-- 4. SELECT grants (superuser + user) --")
for rid,label in [(sup_id,"superuser"),(usr_id,"user")]:
    for v in VIEWS:
        post(f"/api/v1/biac/roles/{rid}/grants",{"effect":"ALLOW","action":"SELECT","entity":{"category":"TABLES","catalog":CATALOG,"schema":SCHEMA,"table":v}})
    print(f"  SELECT -> {label} ({len(VIEWS)} views)")

print("-- 5. data_ing grants (DP views + allEntities) --")
for v in VIEWS:
    post(f"/api/v1/biac/roles/{ing_id}/grants",{"effect":"ALLOW","action":"SELECT","entity":{"category":"TABLES","catalog":CATALOG,"schema":SCHEMA,"table":v}})
post(f"/api/v1/biac/roles/{ing_id}/grants",{"effect":"ALLOW","action":"SELECT","entity":{"allEntities":True}})
print(f"  SELECT -> data_ing ({len(VIEWS)} DP views + allEntities system-wide)")

print("-- 6. Assign roles --")
post(f"/api/v1/biac/subjects/users/starburst_service/assignments",{"roleId":sup_id,"roleAdmin":False})
print(f"  starburst_service -> {PREFIX}_superuser")
for rid,suf in [(usr_id,"_user"),(ing_id,"_data_ing")]:
    post(f"/api/v1/biac/subjects/users/{DEMO_USER}/assignments",{"roleId":rid,"roleAdmin":False})
    print(f"  {DEMO_USER} -> {PREFIX}{suf}")

print("-- Verify --")
for rid,label in [(sup_id,"superuser"),(usr_id,"user"),(ing_id,"data_ing")]:
    g=get(f"/api/v1/biac/roles/{rid}/grants"); print(f"  {label}: {len(g)} grant(s)")
print("== BIAC complete ==")
```

### 7c — Display the Next Steps card

```
══ Demo pipeline complete — {dp-name} ═════════════════════════════════
✅ Data Product deployed
✅ 3 BIAC roles created:
   • {prefix}_superuser → starburst_service  (global view)
   • {prefix}_user      → {demo_user}        ({rls_col if not null: "RLS: {rls_col} + "}CLS sensitive columns)
   • {prefix}_data_ing  → {demo_user}        (DP views + cross-DP + raw Iceberg)

── Validation checklist ────────────────────────────────────────────────
  □ AIDA superuser  → all rows, all columns
  □ AIDA user       → filtered rows (RLS) + masked columns (CLS)
  □ AIDA data_ing   → DP views + raw Iceberg access
  □ D-30 questions  → at least 1 result on each time-based view

── Once you have validated ─────────────────────────────────────────────
  → "generate the lineage for {dp-name}"
════════════════════════════════════════════════════════════════════════
```

---

## Step 8 — Lineage (user trigger)

**Trigger**: the user says "generate the lineage for {dp-name}" or a similar phrasing.

Do not generate automatically — wait for this explicit trigger after the demo has been validated.

### 8a — Read the artifacts

```
dataproduct/<Client>/<Entity>/<dp-name>-spec.json
dataproduct/<Client>/<Entity>/<dp-name>-dp.yaml
```

Extract: `dp_name`, `domain`, `client`, raw tables (spec), DP views (yaml), `rls_column`, `sensitive_columns`, BIAC prefix (derived from dp_name).

### 8b — Generate the lineage HTML

Try the generic script first:
```bash
python .claude/commands/starburst-demo-lineage-gen.py \
  --spec "dataproduct/<Client>/<Entity>/<dp-name>-spec.json" \
  --yaml  "dataproduct/<Client>/<Entity>/<dp-name>-dp.yaml" \
  --output "account/<Client>/<dp-name>-lineage.html"
```

If the script is missing or fails: generate the HTML directly, following the design of `account/BNPP/CIB/cib-data-lineage.html` — 2-panel (lineage left, BIAC right), SVG bézier arrows, inline base64 Starburst logo, teal/navy palette.

### 8c — Confirm

```
✅ Lineage generated: account/<Client>/<dp-name>-lineage.html
   Open in the browser for validation before the demo.
```

---

## Orchestration rules

- **Agent 1 is always foreground** — its spec is the contract for what follows.
- **Agents 2 & 3 are always parallel** — spawn them in the same call.
- **Agent 4 waits for both to finish** before starting.
- **Step 6 — parallel phase**: 6b (catalog) + 6c (domain) + data.py are independent — launch them simultaneously. 6d (YAML import) waits only for 6b + 6c.
- **Step 7 BIAC**: always launch after Step 6 is complete (6d succeeded), without asking for confirmation.
- **Step 8 Lineage**: only on user trigger — never automatic.
- If an agent fails: report the error, offer to re-run that agent alone.
- Never skip Agent 4 — consistency is non-negotiable.
- Sub-agents have access to skills via the Skill tool — tell them to invoke the skill by name.

---

## Edge cases

| Situation | Behavior |
|---|---|
| Spec already exists in the folder | Ask: "Use the existing spec or generate a new one?" |
| Agent 2 or 3 fails | Re-run the failed agent alone, do not re-run the others |
| Agent 4 finds unfixable errors | List them and ask the user how to proceed |
| User wants to skip Agent 1 (spec provided) | Read the existing spec and start at step 3 |
| Cluster unavailable at Step 5 | Display the command, do not block |
| `rls_column` is null in the spec | Skip Step 7 RLS — still create the 3 roles with SELECT grants |
| `sensitive_columns` is empty | Skip Step 7 CLS — no masking for `_user` |
| `demo_user` unknown | Ask once before launching the BIAC script |
| BIAC: role already exists | The API returns the existing id — continue without error |
| BIAC: allEntities grant fails | Report, continue with the other grants — document the gap |
| Lineage trigger before deployment | Display: "Deploy the DP and validate the demo first, then re-run the trigger" |
