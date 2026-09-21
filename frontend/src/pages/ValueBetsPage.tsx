import { useState } from "react";
import styles from "../App.module.css";
import { Filters, type FiltersState } from "../components/Filters";
import { ValueBetsTable } from "../components/ValueBetsTable";
import { useValueBets } from "../hooks/useValueBets";

const DEFAULT_FILTERS: FiltersState = {
  sport: "",
  market: "",
  bookmaker: "",
  edgeMin: 0.03,
};

export function ValueBetsPage() {
  const [filters, setFilters] = useState<FiltersState>(DEFAULT_FILTERS);

  const { valueBets, error, lastUpdated, refresh } = useValueBets({
    sport: filters.sport || undefined,
    market: filters.market || undefined,
    bookmaker: filters.bookmaker || undefined,
    edgeMin: filters.edgeMin,
  });

  return (
    <>
      <header className={styles.header}>
        <h1>Value bets</h1>
        <span className={styles.subtitle}>
          Cotes ANJ comparées à la référence sharp — outil d'analyse, aucun pari réel
        </span>
      </header>
      <Filters value={filters} onChange={setFilters} lastUpdated={lastUpdated} onRefresh={refresh} />
      {error && <div className={styles.error}>{error}</div>}
      <main className={styles.main}>
        <ValueBetsTable data={valueBets} />
      </main>
    </>
  );
}
