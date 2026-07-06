---
name: starburst-demo
description: >
  Orchestrateur du pipeline demo Starburst. Prend une demande business (vertical,
  use case, client) et orchestre 4 agents pour produire dataset + data product
  cohérents : consultant → [data modeler ‖ dp builder] → coherence checker.
  Triggers on: "prépare un demo pour", "génère un demo complet", "demo pipeline",
  "crée un demo starburst pour", "pipeline demo", "full demo pour", "demo pour".
---

## Vue d'ensemble du pipeline

```
User request
     ↓
Agent 1 : starburst-demo-consultant   → <dp-name>-spec.json
     ↓
     ├── Agent 2 : starburst-demo-data-modeler   → <dp-name>-data.py   ┐ (parallèle)
     └── Agent 3 : starburst-demo-dp-builder     → <dp-name>-dp.yaml   ┘
     ↓
Agent 4 : starburst-demo-coherence-checker → rapport + corrections
     ↓
HITL Review → confirmation déploiement
     ↓
     ├── 6b: SHOW CATALOGS (catalogName)   ┐
     ├── 6c: GET/POST domain               ┘ (parallèle) → 6d: POST dp.yaml import
     └── data.py (chargement iceberg raw)  ┘
     ↓
Step 7 : BIAC — auto après Step 6 (superuser / user / data_ing)
     ↓
(optionnel) Step 8 : Lineage — trigger: "génère le lineage pour <dp-name>"
```

---

## Step 1 — Collecter le contexte business

Si des arguments sont fournis, les utiliser directement.
Sinon, demander en **un seul message** :

> "Pour générer ce demo, dis-moi :
> - **Vertical / secteur** (ex : Santé, Banque, Logistique)
> - **Cas d'usage principal** (ex : pilotage PMSI, détection fraude)
> - **2–3 questions business** que le client doit pouvoir poser
> - **Client ou événement** (ex : Santexpo, BNP Paribas)
> - **Audience** : DSI, Métier, C-level ?"

---

## Step 2 — Agent 1 : Demo Consultant (foreground)

Utiliser le tool **Agent** pour spawner un sous-agent avec ces instructions :

> "Tu es l'Agent 1 du pipeline demo Starburst. Utilise le Skill tool pour invoquer `starburst-demo-consultant` : `Skill(skill='starburst-demo-consultant', args='[contexte business complet]')`. Tu es en mode orchestrateur — skip la validation utilisateur (Step 4 du skill) et sauvegarde directement la spec dans `dataproduct/<Client>/<Entity>/<dp-name>-spec.json`. Retourne le chemin complet du fichier sauvegardé et le contenu JSON de la spec."

Attendre la complétion — la spec est nécessaire avant de continuer.

Afficher : `✅ Agent 1 — Spec produite : <chemin>`

---

## Step 3 — Agents 2 & 3 en parallèle (foreground)

Spawner **deux agents simultanément** dans le même message (deux appels Agent dans la même réponse) :

**Agent 2 — Data Modeler :**
> "Tu es l'Agent 2 du pipeline demo Starburst. Utilise le Skill tool pour invoquer `starburst-demo-data-modeler` : `Skill(skill='starburst-demo-data-modeler', args='<chemin-spec.json>')`. La spec se trouve ici : `<chemin-spec.json>`. Génère et sauvegarde `<dp-name>-data.py` dans le même dossier. Retourne le chemin du fichier et un résumé des tables générées."

**Agent 3 — DP Builder :**
> "Tu es l'Agent 3 du pipeline demo Starburst. Utilise le Skill tool pour invoquer `starburst-demo-dp-builder` : `Skill(skill='starburst-demo-dp-builder', args='<chemin-spec.json>')`. La spec se trouve ici : `<chemin-spec.json>`. Génère et sauvegarde `<dp-name>-dp.yaml` dans le même dossier. Retourne le chemin du fichier et un résumé des vues générées."

Attendre les deux completions.

Afficher :
```
✅ Agent 2 — Script data : <chemin>
✅ Agent 3 — Data Product YAML : <chemin>
```

---

## Step 4 — Agent 4 : Coherence Checker (foreground)

Spawner un agent avec :

> "Tu es l'Agent 4 du pipeline demo Starburst. Utilise le Skill tool pour invoquer `starburst-demo-coherence-checker` : `Skill(skill='starburst-demo-coherence-checker', args='<dossier>')`. Les artifacts se trouvent dans : `<dossier>`. Analyse les trois fichiers (<dp-name>-spec.json, <dp-name>-data.py, <dp-name>-dp.yaml), applique les corrections nécessaires, et retourne le rapport complet."

Afficher le rapport de cohérence tel quel.

---

## Step 5 — Résumé et prochaines étapes

Afficher un résumé final :

```
══════════════════════════════════════════
  Demo pipeline terminé — <dp-name>
══════════════════════════════════════════

Artifacts générés dans dataproduct/<Client>/<Entity>/ :
  📋 <dp-name>-spec.json     — Schema Spec (contrat)
  🐍 <dp-name>-data.py       — Script de données (<N> tables, <N> rows)
  📦 <dp-name>-dp.yaml       — Data Product YAML (<N> vues)

Cohérence : <✅ OK | ⚠️ N corrections appliquées>

Prochaines étapes :
  1. Déployer → données (iceberg raw) + Data Product + BIAC en une seule commande
  2. Tester AIDA avec les questions de la spec
  3. Générer le lineage → "génère le lineage pour <dp-name>"
```

Puis demander :
> "Tu veux que je déploie maintenant sur un cluster ? (chargement des données + import Data Product + BIAC setup — j'aurai besoin du host, user et password)"

Si oui → aller au Step 6.

---

## Step 6 — Déploiement (parallélisé)

### 6a — Collecter les paramètres cluster

Demander en un seul message si manquants : host, user, password, domaine cible.

### 6b + 6c + data.py — Phase parallèle (lancer simultanément)

Les trois opérations sont indépendantes — les démarrer dans le même appel :

**6b — Valider le catalogName** (interroge `system`, pas besoin du domaine) :
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
- Un seul résultat → l'utiliser ; plusieurs → demander ; aucun → demander à l'user.

**6c — Valider / créer le domaine** (appel REST indépendant) :
`GET /api/v1/dataProduct/domains` — si absent → `POST /api/v1/dataProduct/domains`.

**data.py — Charger les données dans Iceberg raw** (indépendant du catalog DP et du domaine) :
```bash
python <dp-name>-data.py \
  --host <host> --user <user> --password <password> \
  --catalog iceberg --schema <schema_raw> \
  --location s3://<bucket>/<path>/
```

Attendre la fin des trois avant de continuer.

Afficher :
```
✅ 6b — catalogName : <catalog>
✅ 6c — Domaine : <domain> (créé | existant)
✅ data.py — <N> lignes chargées dans iceberg.<schema_raw>
```

### 6d — Importer le Data Product YAML

Mettre à jour `catalogName` dans le YAML avec la valeur trouvée en 6b, puis :

```
POST /api/v1/dataProduct/products/import
Content-Type: application/yaml
Body: <dp-name>-dp.yaml (avec catalogName mis à jour)
```

Si 409 (produit déjà existant) → `catalogName` est immutable, supprimer depuis l'UI puis relancer.

---

## Step 7 — BIAC Setup (automatique après déploiement)

Lancer immédiatement après confirmation du Step 6. Pas d'attente de confirmation utilisateur.

### 7a — Dériver les identifiants depuis la spec

```python
dp_name   = spec["dp_name"]
segments  = dp_name.replace("-", "_").split("_")[:3]
prefix    = "_".join(segments)
# ex: "bnpp-cib-fraude-corporate" → "bnpp_cib_fraude"

rls_col    = spec.get("rls_column")           # None si absent
sensitive   = spec.get("sensitive_columns", [])
catalog     = dp_yaml["metadata"]["catalogName"]  # ex: data_products
schema      = dp_yaml["metadata"]["schemaName"]   # ex: cib_fraude_transactions_corporate
views       = [v["name"] for v in dp_yaml.get("views", [])]

# Valeurs pour substitution dans le template script :
views_list    = repr(views)        # ex: ['vue_a', 'vue_b']
rls_col_repr  = repr(rls_col)      # "None" ou '"nom_colonne"'
sensitive_repr = repr(sensitive)   # liste Python littérale des sensitive_columns
# env_path : chemin vers le fichier .env du cluster (ex: "dataproduct/servers/.env.warpspeed2")
#             → récupéré depuis les paramètres collectés au Step 6a
```

Si `demo_user` inconnu (pas dans la spec, pas de session en cours) : demander une fois à l'utilisateur.

### 7b — Générer et exécuter le script BIAC

Générer un script Python dans le scratchpad, instancié avec les valeurs ci-dessus depuis ce template, puis l'exécuter avec `python` :

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
HW   = {"Content-Type":"application/json","Accept":"application/json","X-Trino-Role":"system=ROLE{sysadmin}"}  # {sysadmin} = syntaxe Starburst BIAC, pas un placeholder
HR   = {"Accept":"application/json","X-Trino-Role":"system=ROLE{sysadmin}"}  # idem

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

### 7c — Afficher la Next Steps card

```
══ Demo pipeline complet — {dp-name} ══════════════════════════════════
✅ Data Product déployé
✅ 3 rôles BIAC créés :
   • {prefix}_superuser → starburst_service  (vision globale)
   • {prefix}_user      → {demo_user}        ({rls_col si non null: "RLS: {rls_col} + "}CLS colonnes sensibles)
   • {prefix}_data_ing  → {demo_user}        (vues DP + cross-DP + raw Iceberg)

── Checklist validation ────────────────────────────────────────────────
  □ AIDA superuser  → toutes lignes, toutes colonnes
  □ AIDA user       → lignes filtrées (RLS) + colonnes masquées (CLS)
  □ AIDA data_ing   → vues DP + accès Iceberg raw
  □ Questions J-30  → au moins 1 résultat sur chaque vue temporelle

── Quand tu as validé ──────────────────────────────────────────────────
  → "génère le lineage pour {dp-name}"
════════════════════════════════════════════════════════════════════════
```

---

## Step 8 — Lineage (trigger utilisateur)

**Trigger** : l'utilisateur dit "génère le lineage pour {dp-name}" ou formule similaire.

Ne pas générer automatiquement — attendre ce trigger explicite après validation de la démo.

### 8a — Lire les artifacts

```
dataproduct/<Client>/<Entity>/<dp-name>-spec.json
dataproduct/<Client>/<Entity>/<dp-name>-dp.yaml
```

Extraire : `dp_name`, `domain`, `client`, tables raw (spec), vues DP (yaml), `rls_column`, `sensitive_columns`, prefix BIAC (dérivé du dp_name).

### 8b — Générer le HTML de lineage

Tenter d'abord via le script générique :
```bash
python .claude/commands/starburst-demo-lineage-gen.py \
  --spec "dataproduct/<Client>/<Entity>/<dp-name>-spec.json" \
  --yaml  "dataproduct/<Client>/<Entity>/<dp-name>-dp.yaml" \
  --output "account/<Client>/<dp-name>-lineage.html"
```

Si le script est absent ou échoue : générer le HTML directement, en s'inspirant du design de `account/BNPP/CIB/cib-data-lineage.html` — 2-panel (lineage gauche, BIAC droite), arrows SVG bézier, logo Starburst base64 inline, palette teal/navy.

### 8c — Confirmer

```
✅ Lineage généré : account/<Client>/<dp-name>-lineage.html
   Ouvrir dans le navigateur pour validation avant la démo.
```

---

## Règles d'orchestration

- **Agent 1 est toujours foreground** — sa spec est le contrat pour la suite.
- **Agents 2 & 3 sont toujours parallèles** — les spawner dans le même appel.
- **Agent 4 attend la fin des deux** avant de démarrer.
- **Step 6 — phase parallèle** : 6b (catalog) + 6c (domain) + data.py sont indépendants — les lancer simultanément. 6d (import YAML) attend seulement 6b + 6c.
- **Step 7 BIAC** : toujours lancer après Step 6 complet (6d réussi), sans demander confirmation.
- **Step 8 Lineage** : uniquement sur trigger utilisateur — jamais automatique.
- Si un agent échoue : signaler l'erreur, proposer de relancer cet agent seul.
- Ne jamais skip l'Agent 4 — la cohérence est non-négociable.
- Les sous-agents ont accès aux skills via le Skill tool — leur dire d'invoquer le skill par son nom.

---

## Edge cases

| Situation | Comportement |
|---|---|
| Spec déjà existante dans le dossier | Demander : "Utiliser la spec existante ou en générer une nouvelle ?" |
| Agent 2 ou 3 échoue | Relancer l'agent en échec seul, ne pas re-exécuter les autres |
| Agent 4 trouve des erreurs non corrigeables | Lister et demander à l'user comment procéder |
| User veut sauter l'Agent 1 (spec fournie) | Lire la spec existante et démarrer à l'étape 3 |
| Cluster indisponible au Step 5 | Afficher la commande, ne pas bloquer |
| `rls_column` est null dans la spec | Skip Step 7 RLS — créer quand même les 3 rôles avec grants SELECT |
| `sensitive_columns` est vide | Skip Step 7 CLS — pas de masquage pour `_user` |
| `demo_user` inconnu | Demander une fois avant de lancer le script BIAC |
| BIAC : rôle déjà existant | L'API renvoie l'id existant — continuer sans erreur |
| BIAC : allEntities grant échoue | Signaler, continuer avec les autres grants — documenter le gap |
| Lineage trigger avant déploiement | Afficher : "Déploie d'abord le DP et valide la démo, puis relance le trigger" |
