import { useEffect, useState } from "react";
import { fetchBookmakers, fetchSports } from "../api/client";
import type { Bookmaker, MarketType, Sport } from "../types";
import styles from "./Filters.module.css";

export interface FiltersState {
  sport: string;
  market: MarketType | "";
  bookmaker: string;
  edgeMin: number;
}

interface FiltersProps {
  value: FiltersState;
  onChange: (next: FiltersState) => void;
  lastUpdated: Date | null;
  onRefresh: () => void;
}

const MARKET_OPTIONS: { value: MarketType; label: string }[] = [
  { value: "1x2", label: "1X2" },
  { value: "moneyline", label: "Vainqueur" },
  { value: "over_under", label: "Over/Under" },
];

export function Filters({ value, onChange, lastUpdated, onRefresh }: FiltersProps) {
  const [sports, setSports] = useState<Sport[]>([]);
  const [bookmakers, setBookmakers] = useState<Bookmaker[]>([]);

  useEffect(() => {
    fetchSports().then(setSports).catch(() => setSports([]));
    fetchBookmakers().then(setBookmakers).catch(() => setBookmakers([]));
  }, []);

  return (
    <div className={styles.filters}>
      <div className={styles.field}>
        <label htmlFor="filter-sport">Sport</label>
        <select
          id="filter-sport"
          value={value.sport}
          onChange={(e) => onChange({ ...value, sport: e.target.value })}
        >
          <option value="">Tous</option>
          {sports.map((s) => (
            <option key={s.slug} value={s.slug}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.field}>
        <label htmlFor="filter-market">Marché</label>
        <select
          id="filter-market"
          value={value.market}
          onChange={(e) => onChange({ ...value, market: e.target.value as MarketType | "" })}
        >
          <option value="">Tous</option>
          {MARKET_OPTIONS.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.field}>
        <label htmlFor="filter-book">Book</label>
        <select
          id="filter-book"
          value={value.bookmaker}
          onChange={(e) => onChange({ ...value, bookmaker: e.target.value })}
        >
          <option value="">Tous</option>
          {bookmakers.map((b) => (
            <option key={b.slug} value={b.slug}>
              {b.name}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.field}>
        <label htmlFor="filter-edge-min">Edge min (%)</label>
        <input
          id="filter-edge-min"
          type="number"
          step="0.5"
          min="-100"
          max="100"
          value={value.edgeMin * 100}
          onChange={(e) =>
            onChange({ ...value, edgeMin: (Number(e.target.value) || 0) / 100 })
          }
        />
      </div>

      <button type="button" className={styles.refreshButton} onClick={onRefresh}>
        Rafraîchir
      </button>

      <div className={styles.status}>
        {lastUpdated
          ? `Mis à jour à ${lastUpdated.toLocaleTimeString("fr-FR")}`
          : "Chargement…"}
      </div>
    </div>
  );
}
