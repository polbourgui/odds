# Odds — frontend

React + TypeScript + Vite. Tableau des value bets comparant les cotes des bookmakers
ANJ à une référence sharp dévigée.

## Développement

```bash
npm install
cp .env.example .env.local   # VITE_API_BASE_URL vers le backend local (défaut: http://localhost:8000)
npm run dev
```

- `npm run build` — vérifie les types (`tsc -b`) puis build de production
- `npm run lint` — oxlint

## Structure

```
src/
  api/client.ts        # appels à l'API FastAPI (/api/value-bets, /api/sports, /api/bookmakers)
  components/           # ComplianceBanner, Filters, ValueBetsTable
  hooks/useValueBets.ts # fetch + polling (rafraîchissement auto toutes les 30s)
  format.ts             # formatage cotes/edge/marché/fraîcheur
  types.ts              # types alignés sur les schémas Pydantic du backend
```

Thème sombre, chiffres en police monospace alignés à droite, vert/rouge réservés à
l'edge positif/négatif, tableau dense sans animation.
