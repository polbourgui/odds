# Odds — comparateur de cotes, value betting & paper betting

Outil d'analyse personnel pour le marché des bookmakers agréés ANJ : comparaison des
cotes à une référence sharp, calcul d'edge et de mise Kelly, suivi de paris fictifs
(paper betting). **Aucun pari réel n'est placé, aucun lien d'affiliation.**

> 18+. Jouer comporte des risques : dépendance, isolement, difficultés financières.
> Joueurs Info Service : 09 74 75 13 13 (appel non surtaxé). Cet outil est un outil
> d'analyse ; il ne garantit aucun gain.

## État du projet

Livraison en cours par étapes (voir le brief). Étape actuelle : **3/6 — API et
tableau des value bets**.

- [x] 1. Schéma BDD, module de calcul et tests
- [x] 2. Adaptateur de cotes fonctionnel et stockage des snapshots
- [x] 3. API et tableau des value bets
- [ ] 4. Paper betting et capture de clôture
- [ ] 5. Statistiques, réglages, export
- [ ] 6. Déploiement (Vercel + Render), durcissement

## Déploiement (décision prise, mise en œuvre à l'étape 6)

Pas de Docker : le frontend React/Vite est déployé sur **Vercel** (détection
automatique, aucune config particulière). Le backend FastAPI a besoin d'un process
persistant pour le scheduler de rafraîchissement des cotes (APScheduler) — ce que
Vercel (serverless) ne permet pas nativement — donc il est déployé séparément sur
**Render** (web service Python natif + PostgreSQL managé sur la même plateforme,
déploiement par push Git, sans Dockerfile). Ce choix ne change rien au code déjà
écrit (étapes 1-2) : SQLAlchemy/FastAPI/APScheduler restent agnostiques de l'hébergeur.

## Structure

```
backend/
  app/
    api/routes/     # endpoints FastAPI (value-bets, sports, bookmakers)
    core/           # configuration, module de calcul pur (devig, edge, Kelly, CLV)
    db/             # base SQLAlchemy déclarative, session
    models/         # schéma de données (sports, événements, cotes, paper bets, ...)
    providers/      # interface OddsProvider + adaptateur The Odds API
    schemas/        # DTOs Pydantic exposés par l'API
    services/       # normalisation, rapprochement, ingestion, calcul des value bets
    main.py         # app FastAPI
  migrations/       # Alembic
  scripts/          # scripts dev (seed_dev_data.py)
  tests/            # pytest
frontend/
  src/
    api/            # client HTTP vers l'API FastAPI
    components/      # ComplianceBanner, Filters, ValueBetsTable
    hooks/           # useValueBets (fetch + polling)
    pages/           # ValueBetsPage ("/"), EventComparisonPage ("/events/:id")
```

## Module de calcul (`app/core/calculations.py`)

Fonctions pures, sans dépendance DB/réseau :

- `implied_probability`, `fair_odds`
- `devig_multiplicative`, `devig_power`, `devig_shin` (dévigage de la référence sharp)
- `edge`, `kelly_fraction_full`, `kelly_stake` (Kelly fractionné, plafonné, seuil d'edge)
- `clv` (closing line value)

## Adaptateur de cotes et rapprochement (`app/providers/`, `app/services/`)

- `OddsProvider` (`app/providers/base.py`) : interface abstraite (`fetch_events`,
  `fetch_odds`) que tout adaptateur implémente. Le reste de l'application ne dépend
  jamais du format JSON brut d'une source — uniquement des schémas Pydantic exposés
  ici (`ProviderEvent`, `ProviderEventOdds`, ...).
- `TheOddsApiProvider` (`app/providers/the_odds_api.py`) : premier adaptateur, basé sur
  [The Odds API](https://the-odds-api.com). Marchés V1 mappés : `h2h` → 1X2 (3 issues)
  ou vainqueur (2 issues, tennis/NBA), `totals` → over/under. Gestion des erreurs
  (401/403, 429 avec quota restant, timeout) via des exceptions typées et des logs
  clairs (`app/providers/exceptions.py`).
- `EventReconciler` (`app/services/reconciliation.py`) : rapproche les événements et
  participants entre sources par normalisation du nom (`app/services/normalization.py`
  — accents, casse, suffixes de club), puis repli sur une correspondance approximative
  (ratio `difflib`), avec une table d'alias éditable (`participant_aliases`,
  `competition_aliases`) qui prend toujours la priorité et peut être corrigée à la main.
- `OddsIngestionService` (`app/services/odds_ingestion.py`) : récupère les cotes via un
  provider, rapproche l'événement/la sélection, et insère un `OddsSnapshot` horodaté
  par (sélection, bookmaker) — jamais d'écrasement, historique complet pour le CLV.

### Ajouter un nouvel adaptateur

1. Créer une classe héritant de `OddsProvider` sous `app/providers/`, implémentant
   `fetch_events` et `fetch_odds` et renvoyant les schémas `ProviderEvent` /
   `ProviderEventOdds` définis dans `app/providers/base.py`.
2. Lever les exceptions de `app/providers/exceptions.py` (`ProviderAuthError`,
   `ProviderQuotaExceededError`, `ProviderTimeoutError`, ...) plutôt que de laisser
   fuiter des erreurs de transport.
3. `OddsIngestionService` et `EventReconciler` fonctionnent avec n'importe quel
   `OddsProvider` sans modification — seul `provider.name` sert à scoper les alias.

## API et tableau des value bets (`app/api/`, `app/services/value_bets.py`, `frontend/`)

- `compute_value_bets` (`app/services/value_bets.py`) : prend la cote la plus récente
  par (sélection, bookmaker), dévigue le marché complet du bookmaker sharp (référence)
  pour obtenir les probabilités vraies, puis calcule edge et mise Kelly pour chaque book
  ANJ. Une cote — sharp ou ANJ — plus vieille que `stale_odds_minutes` est exclue avant
  tout calcul (jamais affichée comme valide), et un marché où le sharp ne couvre pas
  toutes les issues est exclu en bloc plutôt que dévigué partiellement.
- `GET /api/value-bets` (filtres `sport`, `market`, `bookmaker`, `edge_min`), `GET
  /api/sports`, `GET /api/bookmakers` (liste uniquement les books ANJ actifs).
- `get_event_comparison` (`app/services/event_comparison.py`) : pour un événement,
  toutes les cotes de chaque sélection côte à côte (y compris la référence sharp, pour
  contexte), meilleure cote ANJ surlignée, écart vs référence (cote juste dévigée si le
  sharp couvre tout le marché, sinon sa cote brute). Contrairement au tableau des value
  bets, une cote périmée n'est pas masquée ici mais montrée grisée (`is_stale`) — jamais
  éligible à "meilleure cote". `GET /api/events/{id}/comparison`.
- Frontend : `ValueBetsTable` (TanStack Table) — tri par colonne, filtres, chiffres en
  police monospace alignés à droite, edge coloré vert/rouge, rafraîchissement
  automatique toutes les 30s. Chaque ligne renvoie vers `EventComparisonPage`
  (`/events/:id`, react-router) : une table par marché, cotes de tous les books côte à
  côte, meilleure cote surlignée en vert, écart vs référence affiché sous chaque cote.

## Lancer le projet en local

```bash
# Backend
cd backend
source .venv/bin/activate
export DATABASE_URL=postgresql+psycopg://odds:odds@localhost:5432/odds
alembic upgrade head
python scripts/seed_dev_data.py   # données de démo via le pipeline d'ingestion réel
uvicorn app.main:app --reload

# Frontend (autre terminal)
cd frontend
cp .env.example .env.local
npm run dev
```

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
