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
(optionnel) Charger les données sur le cluster
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
  1. Charger les données → python <dp-name>-data.py --host ... --teardown pour nettoyer
  2. Déployer le Data Product → POST /api/v1/dataProduct/products/import
  3. Tester AIDA avec les questions de la spec
```

Puis demander :
> "Tu veux que je charge les données sur un cluster maintenant ? (j'aurai besoin du host, user et password)"

Si oui → collecter les paramètres manquants et lancer `<dp-name>-data.py` avec les bons args.

---

## Step 6 — Déploiement du Data Product (si demandé)

### 6a — Collecter les paramètres cluster

Demander en un seul message si manquants : host, user, password, et domaine cible.

### 6b — Valider le catalogName avant de déployer

**Avant tout import YAML, interroger le cluster pour trouver le nom exact du catalog Data Product.**

Exécuter via SQLAlchemy/Trino :
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

- Si **un seul** catalog contient "data" → l'utiliser automatiquement
- Si **plusieurs** → afficher la liste et demander lequel est le catalog Data Product
- Si **aucun** → demander à l'user de préciser le nom du catalog

Mettre à jour `catalogName` dans le YAML avant d'envoyer la requête d'import.

### 6c — Valider / créer le domaine

Vérifier que le domaine cible existe via `GET /api/v1/dataProduct/domains`.
Si absent → créer via `POST /api/v1/dataProduct/domains` avec `name`, `description`, `schemaLocation`.

### 6d — Déployer

```
POST /api/v1/dataProduct/products/import
Content-Type: application/yaml
Body: <dp-name>-dp.yaml (avec catalogName mis à jour)
```

Si 409 (produit déjà existant) → `catalogName` est immutable, supprimer depuis l'UI puis relancer.

---

## Règles d'orchestration

- **Agent 1 est toujours foreground** — sa spec est le contrat pour la suite.
- **Agents 2 & 3 sont toujours parallèles** — les spawner dans le même appel.
- **Agent 4 attend la fin des deux** avant de démarrer.
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
