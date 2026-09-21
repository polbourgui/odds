import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchEventComparison } from "../api/client";
import {
  formatFreshness,
  formatKickoff,
  formatMarket,
  formatOdds,
  formatSelection,
  formatSignedPct,
} from "../format";
import type { ComparisonMarket, ComparisonQuote, EventComparison } from "../types";
import styles from "./EventComparisonPage.module.css";

function cellClassName(quote: ComparisonQuote): string {
  const classes: string[] = [];
  if (quote.is_best) classes.push(styles.best);
  if (quote.is_stale) classes.push(styles.stale);
  return classes.join(" ");
}

function MarketTable({ market }: { market: ComparisonMarket }) {
  const bookmakers = new Map<string, { name: string; isSharp: boolean }>();
  for (const selection of market.selections) {
    for (const quote of selection.quotes) {
      bookmakers.set(quote.bookmaker_slug, {
        name: quote.bookmaker_name,
        isSharp: quote.is_sharp_reference,
      });
    }
  }
  const orderedBookmakers = [...bookmakers.entries()].sort(([, a], [, b]) => {
    if (a.isSharp !== b.isSharp) return a.isSharp ? -1 : 1;
    return a.name.localeCompare(b.name);
  });

  return (
    <div className={styles.marketSection}>
      <h2>{formatMarket(market.market_type, market.line)}</h2>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Sélection</th>
            {orderedBookmakers.map(([slug, info]) => (
              <th key={slug} className={info.isSharp ? styles.sharpHeader : undefined}>
                {info.name}
                {info.isSharp ? " (réf.)" : ""}
              </th>
            ))}
            <th>Cote juste</th>
          </tr>
        </thead>
        <tbody>
          {market.selections.map((selection) => {
            const quoteBySlug = new Map(selection.quotes.map((q) => [q.bookmaker_slug, q]));
            return (
              <tr key={`${selection.selection_code}-${selection.participant_name ?? ""}`}>
                <td>{formatSelection(selection.selection_code, selection.participant_name)}</td>
                {orderedBookmakers.map(([slug]) => {
                  const quote = quoteBySlug.get(slug);
                  if (!quote) {
                    return (
                      <td key={slug} className="num">
                        —
                      </td>
                    );
                  }
                  return (
                    <td key={slug} className={`num ${cellClassName(quote)}`}>
                      {formatOdds(quote.odds)}
                      <span className={styles.deviation}>
                        {quote.deviation_vs_reference !== null
                          ? formatSignedPct(quote.deviation_vs_reference)
                          : " "}
                        {" · "}
                        {formatFreshness(quote.captured_at)}
                      </span>
                    </td>
                  );
                })}
                <td className="num">
                  {selection.fair_odds !== null ? formatOdds(selection.fair_odds) : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function EventComparisonPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const [comparison, setComparison] = useState<EventComparison | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!eventId) return;
    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    fetchEventComparison(Number(eventId))
      .then((data) => {
        if (cancelled) return;
        if (data === null) {
          setNotFound(true);
        } else {
          setComparison(data);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Erreur inconnue");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [eventId]);

  return (
    <>
      <header className={styles.header}>
        <Link className={styles.backLink} to="/">
          ← Retour aux value bets
        </Link>
        {comparison && (
          <>
            <span className={styles.title}>
              {comparison.home_name} – {comparison.away_name}
            </span>
            <span className={styles.subtitle}>
              {comparison.competition_name} · {formatKickoff(comparison.start_time)}
            </span>
          </>
        )}
      </header>
      <main className={styles.main}>
        {error && <div className={styles.empty}>{error}</div>}
        {notFound && <div className={styles.empty}>Événement introuvable.</div>}
        {loading && !comparison && !error && !notFound && (
          <div className={styles.empty}>Chargement…</div>
        )}
        {comparison?.markets.map((market) => (
          <MarketTable key={`${market.market_type}-${market.line ?? ""}`} market={market} />
        ))}
        {comparison && comparison.markets.length === 0 && (
          <div className={styles.empty}>Aucune cote disponible pour cet événement.</div>
        )}
      </main>
    </>
  );
}
