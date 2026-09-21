# Odds — comparateur de cotes, value betting & paper betting

Outil d'analyse personnel pour le marché des bookmakers agréés ANJ : comparaison des
cotes à une référence sharp, calcul d'edge et de mise Kelly, suivi de paris fictifs
(paper betting). **Aucun pari réel n'est placé, aucun lien d'affiliation.**

> 18+. Jouer comporte des risques : dépendance, isolement, difficultés financières.
> Joueurs Info Service : 09 74 75 13 13 (appel non surtaxé). Cet outil est un outil
> d'analyse ; il ne garantit aucun gain.

## État du projet

Livraison en cours par étapes (voir le brief). Étape actuelle : **5/6 —
statistiques, réglages, export**.

- [x] 1. Schéma BDD, module de calcul et tests
- [x] 2. Adaptateur de cotes fonctionnel et stockage des snapshots
- [x] 3. API et tableau des value bets (+ comparateur par événement)
- [x] 4. Paper betting et capture de clôture (+ règlement automatique)
- [x] 5. Statistiques, réglages, export
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
    api/routes/     # endpoints FastAPI (value-bets, sports, bookmakers, events, paper-bets)
    core/           # configuration, module de calcul pur (devig, edge, Kelly, CLV)
    db/             # base SQLAlchemy déclarative, session
    models/         # schéma de données (sports, événements, cotes, paper bets, ...)
    providers/      # interface OddsProvider + adaptateur The Odds API
    schemas/        # DTOs Pydantic exposés par l'API
    services/       # normalisation, rapprochement, ingestion, value bets, paper betting, capture de clôture
    main.py         # app FastAPI
    scheduler.py    # process autonome (APScheduler) : capture de clôture périodique
  migrations/       # Alembic
  scripts/          # scripts dev (seed_dev_data.py)
  tests/            # pytest
frontend/
  src/
    api/            # client HTTP vers l'API FastAPI
    components/      # ComplianceBanner, Nav, BankrollBadge, Filters, ValueBetsTable, PlaceBetButton, BankrollChart
    hooks/           # useValueBets (fetch + polling)
    pages/           # ValueBetsPage ("/"), EventComparisonPage ("/events/:id"), BetHistoryPage ("/bets"),
                     # SettingsPage ("/settings"), StatsPage ("/stats")
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
4. Pour le règlement automatique, implémenter en plus `ResultsProvider.fetch_results`
   (contrat séparé, optionnel — `TheOddsApiProvider` implémente les deux).

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

## Paper betting et capture de clôture (`app/services/paper_bets.py`, `app/services/closing_capture.py`, `app/services/auto_settlement.py`)

- `place_paper_bet` : recalcule le pricing au moment du clic (jamais les valeurs
  affichées côté client, pour éviter toute manipulation) — cote, probabilité vraie,
  cote juste, edge et mise Kelly sont figés sur le pari. La mise Kelly est
  dimensionnée sur le solde **actuel** de la bankroll (pas une constante fixe), pour
  que le sizing s'adapte réellement à mesure que la bankroll varie. Rejette la
  création si le book n'est pas agréé ANJ, si la cote ou la référence sharp ne sont
  plus fraîches, ou si l'edge calculé est sous le seuil (mise Kelly nulle).
- `settle_paper_bet` : règlement manuel (gagné/perdu/push/annulé), toujours
  disponible pour rattraper ce que le règlement automatique ne sait pas résoudre.
- `run_auto_settlement` (`app/services/auto_settlement.py`) : règlement automatique
  via `ResultsProvider` (`app/providers/base.py`), un contrat séparé d'`OddsProvider`
  — implémenté par `TheOddsApiProvider.fetch_results` sur l'endpoint `/scores` de The
  Odds API (mêmes compte/clé que les cotes). Pour chaque événement dont le coup
  d'envoi est passé et qui a des paris en attente, récupère les scores groupés par
  `Competition.provider_sport_key` (retenu lors du rapprochement — plus précis que
  `Sport.slug` qui n'est que la catégorie générale), et détermine l'issue par
  sélection : 1X2 (domicile/nul/extérieur par comparaison des scores), vainqueur
  2 voies (tennis/NBA, par côté domicile/extérieur du participant), over/under
  (total vs ligne, push exact). Un cas indéterminable (égalité sur un marché à 2
  issues, type de marché hors scope) reste `pending` pour règlement manuel.
- `run_closing_capture` (`app/services/closing_capture.py`) : pour un événement dont
  le coup d'envoi est passé, retrouve le dernier prix de la référence sharp *avant*
  le coup d'envoi pour chaque sélection, le marque `is_closing`, le dévigue, et
  rétro-remplit `closing_odds`/`clv` sur les paris fictifs encore en attente de
  clôture. Idempotent, ignore les cotes capturées après le coup d'envoi.
- `app/scheduler.py` : process autonome (APScheduler) avec deux jobs périodiques
  (capture de clôture, règlement automatique), séparé du process web FastAPI exprès
  — un scheduler démarré dans le lifespan FastAPI tournerait aussi pendant les tests
  et taperait sur une vraie base non configurée. À lancer avec `python -m
  app.scheduler` ; sur Render, c'est le process d'un **Background Worker**, distinct
  du **Web Service** qui sert l'API.
- `GET/PATCH /api/bankroll`, `POST /api/bankroll/reset`, `GET/POST /api/paper-bets`,
  `POST /api/paper-bets/{id}/settle`.
- Frontend : bouton "Parier" sur chaque ligne du tableau des value bets, badge de
  bankroll dans la nav, page "Mes paris" (historique, règlement manuel, réglages de
  la bankroll de départ).

## Statistiques, réglages, export (`app/core/statistics.py`, `app/services/app_settings.py`, `app/services/stats.py`)

- `app/core/statistics.py` : module pur (sans I/O), testé indépendamment —
  `mean`/`stdev`, `confidence_interval_mean` (approximation normale, z-scores à
  90/95/99%), `wilson_score_interval` (intervalle de confiance pour une proportion
  binomiale, plus fiable que l'approximation normale sur petit échantillon comme un
  taux de réussite), `max_drawdown`. Toute statistique affichée est systématiquement
  accompagnée de son intervalle de confiance et de la taille d'échantillon `n`, pour
  éviter les conclusions hâtives sur peu de paris (exigence explicite du brief).
- `get_effective_settings` (`app/services/app_settings.py`) : les réglages (méthode
  de dévigage, fraction de Kelly, plafond de mise, seuil d'edge, fraîcheur des cotes,
  bankroll de référence, plafond de perte mensuel) sont stockés en base
  (`AppSettings`, ligne singleton) et fusionnés par-dessus les valeurs d'environnement
  via `Settings.model_copy(update=...)`. Modifiables depuis la page Réglages, ils
  s'appliquent immédiatement à tous les calculs (value bets, mise Kelly des paris
  fictifs) sans redémarrage. `GET/PATCH /api/settings`.
- `compute_stats` (`app/services/stats.py`) : nombre de paris (total/en attente/
  gradés), taux de réussite (+ IC Wilson), turnover, profit, ROI/yield (+ IC),
  CLV moyen (+ IC), drawdown max (rejoué sur la courbe d'équité de la bankroll à
  partir du solde initial), ventilation par book/sport/marché, et suivi du plafond
  de perte mensuel virtuel (calculé sur le mois calendaire en cours, jamais un
  blocage — juste une alerte informative, conforme à l'esprit "outil d'analyse").
  `GET /api/stats`.
- `export_paper_bets_csv` (`app/services/paper_bets.py`) : export CSV complet de
  l'historique des paris fictifs (une ligne par pari, du plus ancien au plus
  récent). `GET /api/paper-bets/export.csv`.
- Frontend : `StatsPage` (tuiles KPI avec libellé d'IC en clair, ex. "IC95 [9.5%,
  90.5%] · n=2", bannière d'alerte si le plafond de perte mensuel est atteint,
  `BankrollChart` — courbe d'équité en aire, Recharts, échelle Y calée sur la plage
  réelle des données plutôt qu'une échelle fixe — et tables de ventilation denses
  plutôt que des graphiques à barres, plus cohérent avec le reste de l'interface),
  `SettingsPage` (formulaire avec confirmation d'enregistrement, plafond de perte
  mensuel activable, bankroll de référence des value bets explicitement distinguée
  de la bankroll de départ du paper betting).

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

# Scheduler (autre terminal, optionnel en dev) : capture de clôture périodique
cd backend && python -m app.scheduler
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
