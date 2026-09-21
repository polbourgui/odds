# Odds — comparateur de cotes, value betting & paper betting

Outil d'analyse personnel pour le marché des bookmakers agréés ANJ : comparaison des
cotes à une référence sharp, calcul d'edge et de mise Kelly, suivi de paris fictifs
(paper betting). **Aucun pari réel n'est placé, aucun lien d'affiliation.**

> 18+. Jouer comporte des risques : dépendance, isolement, difficultés financières.
> Joueurs Info Service : 09 74 75 13 13 (appel non surtaxé). Cet outil est un outil
> d'analyse ; il ne garantit aucun gain.

## État du projet

Livraison en cours par étapes (voir le brief). Étape actuelle : **1/6 — schéma de
base de données et module de calcul**.

- [x] 1. Schéma BDD, module de calcul et tests
- [ ] 2. Adaptateur de cotes fonctionnel et stockage des snapshots
- [ ] 3. API et tableau des value bets
- [ ] 4. Paper betting et capture de clôture
- [ ] 5. Statistiques, réglages, export
- [ ] 6. Docker Compose, durcissement

## Structure

```
backend/
  app/
    core/          # configuration, module de calcul pur (devig, edge, Kelly, CLV)
    db/             # base SQLAlchemy déclarative, session
    models/         # schéma de données (sports, événements, cotes, paper bets, ...)
  migrations/       # Alembic
  tests/            # pytest
frontend/           # React + TypeScript + Vite (à venir)
```

## Module de calcul (`app/core/calculations.py`)

Fonctions pures, sans dépendance DB/réseau :

- `implied_probability`, `fair_odds`
- `devig_multiplicative`, `devig_power`, `devig_shin` (dévigage de la référence sharp)
- `edge`, `kelly_fraction_full`, `kelly_stake` (Kelly fractionné, plafonné, seuil d'edge)
- `clv` (closing line value)

## Développement backend

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# Tests unitaires (module de calcul)
pytest -v

# Lint
ruff check app tests
```

### Base de données

Le schéma est défini par les modèles SQLAlchemy sous `app/models/` et versionné avec
Alembic (`migrations/`). Pour appliquer les migrations sur une base PostgreSQL locale :

```bash
export DATABASE_URL=postgresql+psycopg://odds:odds@localhost:5432/odds
alembic upgrade head
```

## Licence / avertissement

Projet à usage personnel. Aucune connexion aux comptes bookmakers, aucun placement
automatique de paris réels.
