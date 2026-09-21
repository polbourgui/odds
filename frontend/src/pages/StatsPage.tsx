import { useEffect, useState } from "react";
import { BankrollChart } from "../components/BankrollChart";
import { exportPaperBetsCsvUrl, fetchStats } from "../api/client";
import { formatPct, formatSignedPct, formatStake } from "../format";
import type { GroupStat, StatsSummary } from "../types";
import styles from "./StatsPage.module.css";

function ciLabel(ci: [number, number] | null, n: number, formatter: (v: number) => string): string {
  if (ci === null) return n === 0 ? "aucun pari" : `n=${n} (trop peu pour un IC)`;
  return `IC95 [${formatter(ci[0])}, ${formatter(ci[1])}] · n=${n}`;
}

function StatTile({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "positive" | "negative";
}) {
  return (
    <div className={styles.tile}>
      <div className={styles.tileLabel}>{label}</div>
      <div className={`${styles.tileValue} ${tone ?? ""}`}>{value}</div>
      {sub && <div className={styles.tileSub}>{sub}</div>}
    </div>
  );
}

function BreakdownTable({ title, groups }: { title: string; groups: GroupStat[] }) {
  return (
    <div className={styles.breakdown}>
      <h2>{title}</h2>
      {groups.length === 0 ? (
        <div className={styles.empty}>Aucune donnée.</div>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Nom</th>
              <th>Paris</th>
              <th>Profit</th>
              <th>ROI</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => (
              <tr key={g.key}>
                <td>{g.label}</td>
                <td className="num">{g.bets}</td>
                <td className={`num ${g.profit >= 0 ? "positive" : "negative"}`}>
                  {g.profit >= 0 ? "+" : ""}
                  {formatStake(g.profit)}
                </td>
                <td className="num">{g.roi !== null ? formatSignedPct(g.roi) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function StatsPage() {
  const [stats, setStats] = useState<StatsSummary | null>(null);

  useEffect(() => {
    fetchStats().then(setStats);
  }, []);

  if (!stats) {
    return <div className={styles.empty}>Chargement…</div>;
  }

  const initialBalance = stats.bankroll_curve[0]?.balance ?? 0;

  return (
    <>
      <header className={styles.header}>
        <span className={styles.title}>Statistiques</span>
        <a className={styles.exportLink} href={exportPaperBetsCsvUrl()}>
          Exporter en CSV
        </a>
      </header>

      {stats.monthly_loss_limit_reached && (
        <div className={styles.alert}>
          Plafond de perte mensuel virtuel atteint : {formatStake(stats.monthly_profit)} €
          ce mois-ci (limite : {formatStake(stats.monthly_loss_limit ?? 0)} €).
        </div>
      )}

      <div className={styles.tiles}>
        <StatTile
          label="Paris"
          value={String(stats.total_bets)}
          sub={`${stats.pending_bets} en attente · ${stats.graded_bets} gradés`}
        />
        <StatTile
          label="ROI / Yield"
          value={stats.roi !== null ? formatSignedPct(stats.roi) : "—"}
          sub={ciLabel(stats.roi_ci, stats.graded_bets + stats.pushes + stats.voids, formatSignedPct)}
          tone={stats.roi !== null ? (stats.roi >= 0 ? "positive" : "negative") : undefined}
        />
        <StatTile
          label="Taux de réussite"
          value={stats.win_rate !== null ? formatPct(stats.win_rate) : "—"}
          sub={ciLabel(stats.win_rate_ci, stats.graded_bets, formatPct)}
        />
        <StatTile
          label="CLV moyen"
          value={stats.average_clv !== null ? formatSignedPct(stats.average_clv) : "—"}
          sub={ciLabel(stats.average_clv_ci, stats.clv_sample_size, formatSignedPct)}
          tone={
            stats.average_clv !== null ? (stats.average_clv >= 0 ? "positive" : "negative") : undefined
          }
        />
        <StatTile
          label="Drawdown max"
          value={stats.max_drawdown_pct !== null ? formatPct(stats.max_drawdown_pct) : "—"}
        />
        <StatTile label="Profit" value={`${stats.profit >= 0 ? "+" : ""}${formatStake(stats.profit)}`} tone={stats.profit >= 0 ? "positive" : "negative"} />
      </div>

      <div className={styles.chartSection}>
        <h2>Courbe de bankroll</h2>
        <BankrollChart points={stats.bankroll_curve} initialBalance={initialBalance} />
      </div>

      <div className={styles.breakdowns}>
        <BreakdownTable title="Par book" groups={stats.by_bookmaker} />
        <BreakdownTable title="Par sport" groups={stats.by_sport} />
        <BreakdownTable title="Par marché" groups={stats.by_market} />
      </div>
    </>
  );
}
