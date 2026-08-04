---
name: starburst-biac
description: >
  Gérer les habilitations Starburst (SEP Built-in Access Control / BIAC) via l'API REST :
  rôles, sécurité ligne (RLS / row filters), sécurité colonne (CLS / column masks),
  grants de privilèges, assignations utilisateur↔rôle, audit et vérification.
  Triggers : "mets en place la gouvernance", "configure RLS/CLS", "crée un rôle",
  "row filter", "column mask", "masque les colonnes", "restreins par pays",
  "donne accès à", "qui peut voir", "audit des habilitations", "gère les permissions BIAC",
  "setup access control", "grant select", "assigne le rôle".
---

# BIAC Governance — gestion des habilitations Starburst via API

Gère le **Built-in Access Control (BIAC)** de Starburst Enterprise via l'API REST :
rôles, row filters (RLS), column masks (CLS), grants, assignations, audit.

> ⚠️ **Sécurité.** Ce skill modifie le contrôle d'accès d'un cluster. Toute opération
> destructive ou élargissant les droits (`DELETE`, revoke, grant permissif, `allEntities`)
> doit être **résumée et confirmée** avant exécution. Least privilege par défaut.
> Ne jamais afficher de secret (password/token). Refuser les grants manifestement trop larges
> sans confirmation explicite.

---

## Step 0 — Résoudre la configuration serveur (INPUT OBLIGATOIRE)

**La config serveur est un input du skill, jamais en dur.**

1. Si l'utilisateur fournit un nom de cluster en argument (ex: `/biac-governance warpspeed2`),
   utiliser `dataproduct/servers/.env.<cluster>`.
2. Sinon, lister `dataproduct/servers/.env.*` et **demander lequel utiliser** (ne pas deviner).
3. L'utilisateur peut aussi fournir un chemin de fichier `.env` explicite, ou les paramètres
   directs. S'il colle un password en clair : l'accepter, **ne pas le réafficher**, et rappeler
   de le faire tourner ensuite.

**Parser le fichier `.env` en Python** (jamais `source`/`set -a` : les valeurs contiennent
des caractères spéciaux qui cassent le shell) :

```python
def load_env(path):
    env={}
    for l in open(path):
        l=l.strip()
        if "=" in l and not l.startswith("#"):
            k,v=l.split("=",1); env[k.strip()]=v.strip().strip('"').strip("'")
    return env
```

Clés attendues : `SB_HOST`, `SB_PORT` (def. 443), `SB_USER`, `SB_PASSWORD`.
Confirmer à l'utilisateur : `Host=… User=… Port=… (password masqué)`.

---

## Règles de connexion

- **Connexion directe au host Trino** (`https://<SB_HOST>:<SB_PORT>`), **pas** le proxy MCP
  (le proxy MCP est read-only et peut renvoyer des 502 sans impact sur l'API directe).
- Toute écriture exige l'en-tête **`X-Trino-Role: system=ROLE{sysadmin}`** (ou un rôle admin BIAC).
- Auth Basic (`-u user:password` / header `Authorization: Basic …`).
- Préférer `urllib`/`requests` en Python pour capturer les `id` renvoyés ; `curl` sinon.

## Règle d'or — partir de l'OpenAPI

**Toujours récupérer le contrat avant d'écrire** : `GET /api/v1/openApi`.
Ne jamais deviner les endpoints à l'aveugle. En extraire paths + schémas de payload.

---

## Carte des endpoints BIAC (`/api/v1/biac`)

| Opération | Méthode + path | Body |
|---|---|---|
| Lister / créer rôle | `GET`/`POST /roles` | `{"name": "<a-z0-9_>"}` |
| Détail / suppr. rôle | `GET`/`DELETE /roles/{id}` | — |
| Créer expression RLS | `POST /expressions/rowFilter` | `{name, expression, description}` → `{id}` |
| Créer expression CLS | `POST /expressions/columnMask` | `{name, expression, description}` → `{id}` |
| Attacher row filter | `POST /roles/{id}/rowFilters` | `{entity, expressionId, forceNone}` |
| Attacher column mask | `POST /roles/{id}/columnMasks` | `{entity, expressionId, forceNone}` |
| Grant privilège | `POST /roles/{id}/grants` | `{effect, action, entity}` |
| Assigner rôle→user | `POST /subjects/users/{user}/assignments` | `{roleId, roleAdmin}` |
| Assigner rôle→groupe | `POST /subjects/groups/{group}/assignments` | `{roleId, roleAdmin}` |
| Lister assignations | `GET /subjects/users/{user}/assignments` | — |

**`entity` (TableEntityData)** :
```json
{"category":"TABLES","catalog":"<cat>","schema":"<sch>","table":"<tbl>","columns":["<col>"]}
```
- `columns` uniquement pour les column masks.
- `allEntities:true` ⇒ **aucun autre attribut autorisé** (sinon 400). Pour cibler un schéma/table, lister explicitement.

**Enums utiles** — `Action`: `SELECT, INSERT, UPDATE, DELETE, SHOW, CREATE, ALTER, DROP, EXECUTE, …` ·
`Effect`: `ALLOW, DENY, ALLOW_WITH_GRANT_OPTION, APPLY_ROW_FILTER, APPLY_COLUMN_MASK, …`

---

## Workflow type — mettre en place RLS + CLS

Ordre **impératif** (l'expression existe avant le filtre/mask) :

1. **Créer le(s) rôle(s)** — noms en minuscules `a-z0-9_` uniquement.
2. **Créer les expressions** (`/expressions/rowFilter`, `/expressions/columnMask`) → récupérer les `id`.
   - RLS : ex. `pays = 'FRA'` ; `pays IN ('FRA','DEU','ITA')`.
   - CLS : l'expression référence la colonne masquée, ex. `substr(nom,1,1)` ou `substr(prenom,1,1) || '***'`. Le type de retour doit matcher la colonne.
3. **Attacher** row filters / column masks aux rôles, sur **chaque vue/table concernée**.
4. **Grants** : `SELECT` par table (pas `allEntities` avec attributs).
5. **Assigner** les utilisateurs/groupes réels aux rôles.
6. **Vérifier** (voir ci-dessous).

## Vérification — TOUJOURS double

1. **Relecture** : `GET` des `rowFilters` / `columnMasks` / `grants` / `assignments` pour confirmer la persistance.
2. **Test fonctionnel** : interroger une vue **en assumant le rôle** (le moteur applique alors la politique).
   ```python
   conn = trino.dbapi.connect(host=…, port=…, user=…,
       http_scheme="https",
       auth=trino.auth.BasicAuthentication(user, password),
       roles={"system": "<role>"})
   ```
   Comparer le résultat entre deux rôles (lignes filtrées, colonnes masquées).
   > sysadmin **bypass** les filtres : tester en forçant le rôle, jamais en sysadmin.

---

## Audit ("qui peut voir quoi")

Pour un rôle : `GET /roles/{id}/{rowFilters,columnMasks,grants}` + résoudre les `expressionId`
via `GET /expressions/{rowFilter|columnMask}/{id}`. Présenter en tableau lisible.

---

## Format de sortie

```
Cluster : <host>  (config: dataproduct/servers/.env.<cluster>)
Opération : <setup-rls | setup-cls | grant | assign | audit | verify | teardown>

Rôles      : <noms (id)>
Expressions: <name → expression>
Row filters: <rôle → table → expr>
Col masks  : <rôle → table.colonne → expr>
Grants     : <rôle → action → entité>
Assignations: <user/groupe → rôle>

Vérification :
  Relecture  : ✅ persisté
  Fonctionnel: <résultat par rôle (lignes/colonnes observées)>

⚠️ Restant manuel : <assignation des vrais utilisateurs, identité de connexion de l'app/AIDA…>
```

---

## Edge cases

| Situation | Comportement |
|---|---|
| Aucun cluster fourni | Lister `dataproduct/servers/.env.*` et demander — ne pas deviner |
| Fichier `.env` avec caractères spéciaux | Parser en Python, jamais `source` shell |
| Nom de rôle avec majuscules/tirets | Refuser/convertir en `a-z0-9_` (l'API renvoie 400 sinon) |
| Row filter / column mask sans expression | Créer l'expression d'abord, réutiliser son `id` |
| `Grant allEntities:true` + catalog/schema/table | 400 — passer en grants par table |
| Endpoint introuvable | Récupérer `GET /api/v1/openApi` et relire les paths — ne pas deviner |
| Test de sécurité en sysadmin | Inopérant (bypass) — assumer le rôle via `roles={"system":…}` |
| Connecteur cible sans `CREATE SCHEMA` (Oracle…) | Hors scope BIAC, mais signaler à l'utilisateur |
| Vue Data Product en `DEFINER` | Le rôle n'a besoin que de `SELECT` sur la vue ; les filtres/masks s'appliquent quand même au session user |
| Opération destructive (`DELETE`, revoke) | Résumer + confirmer avant d'exécuter |
| Password collé en clair | Ne pas réafficher ; rappeler de le faire tourner |

---

## Anti-pattern à éviter

Ne **pas** sonder les endpoints à l'aveugle par essais/erreurs (coûteux et risqué sur une API
de sécurité). La spec OpenAPI (`/api/v1/openApi`) est la source de vérité : la lire **d'abord**.
