import { useEffect, useState } from "react";
import {
  ApiError,
  fetchBankroll,
  fetchPaperBets,
  resetBankroll,
  settlePaperBet,
  updateBankroll,
} from "../api/client";
import {
  formatKickoff,
  formatMarket,
  formatOdds,
  formatPct,
  formatSelection,
  formatSignedPct,
  formatStake,
} from "../format";
import type { Bankroll, BetStatus, PaperBet } from "../types";
import styles from "./BetHistoryPage.module.css";

const STATUS_LABELS: Record<BetStatus, string> = {
  pending: "En attente",
  won: "Gagné",
  lost: "Perdu",
  push: "Push",
  void: "Annulé",
};

const STATUS_CLASS: Record<BetStatus, string> = {
  pending: styles.statusPending,
  won: styles.statusWon,
  lost: styles.statusLost,
  push: styles.statusPending,
  void: styles.statusPending,
};

function BankrollPanel({
  bankroll,
  onChanged,
}: {
  bankroll: Bankroll;
  onChanged: (b: Bankroll) => void;
}) {
  const [initialBalanceInput, setInitialBalanceInput] = useState(String(bankroll.initial_balance));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = () => {
    const value = Number(initialBalanceInput);
    if (!Number.isFinite(value) || value < 0) {
      setError("Montant invalide");
      return;
    }
    setSaving(true);
    setError(null);
    updateBankroll({ initial_balance: value })
      .then(onChanged)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Erreur"))
      .finally(() => setSaving(false));
  };

  const handleReset = () => {
    setSaving(true);
    resetBankroll()
      .then((b) => {
        onChanged(b);
        setInitialBalanceInput(String(b.initial_balance));
      })
      .finally(() => setSaving(false));
  };

  const pl = bankroll.current_balance - bankroll.initial_balance;

  return (
    <div className={styles.bankrollSection}>
      <div className={styles.stat}>
        Solde actuel
        <span className={`${styles.value} num`}>
          {formatStake(bankroll.current_balance)} {bankroll.currency}
        </span>
      </div>
      <div className={styles.stat}>
        P&amp;L
        <span className={`${styles.value} num ${pl >= 0 ? "positive" : "negative"}`}>
          {pl >= 0 ? "+" : ""}
          {formatStake(pl)}
        </span>
      </div>
      <div className={styles.field}>
        <label htmlFor="initial-balance">Bankroll de départ</label>
        <input
          id="initial-balance"
          type="number"
          min="0"
          step="10"
          value={initialBalanceInput}
          onChange={(e) => setInitialBalanceInput(e.target.value)}
        />
      </div>
      <button type="button" className={styles.button} onClick={handleSave} disabled={saving}>
        Enregistrer
      </button>
      <button type="button" className={styles.button} onClick={handleReset} disabled={saving}>
        Réinitialiser le solde
      </button>
      {error && <span className="negative">{error}</span>}
    </div>
  );
}

export function BetHistoryPage() {
  const [bankroll, setBankroll] = useState<Bankroll | null>(null);
  const [bets, setBets] = useState<PaperBet[]>([]);
  const [statusFilter, setStatusFilter] = useState<BetStatus | "">("");
  const [settlingId, setSettlingId] = useState<number | null>(null);

  const loadBets = () => {
    fetchPaperBets(statusFilter || undefined).then(setBets).catch(() => setBets([]));
  };

  useEffect(() => {
    fetchBankroll().then(setBankroll);
  }, []);

  useEffect(() => {
    loadBets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  const handleSettle = (betId: number, status: BetStatus) => {
    setSettlingId(betId);
    settlePaperBet(betId, status)
      .then(() => {
        loadBets();
        fetchBankroll().then(setBankroll);
      })
      .finally(() => setSettlingId(null));
  };

  return (
    <>
      <header className={styles.header}>
        <span className={styles.title}>Mes paris fictifs</span>
      </header>

      {bankroll && <BankrollPanel bankroll={bankroll} onChanged={setBankroll} />}

      <div className={styles.filterBar}>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as BetStatus | "")}>
          <option value="">Tous les statuts</option>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      <main className={styles.main}>
        {bets.length === 0 ? (
          <div className={styles.empty}>Aucun pari fictif pour le moment.</div>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Coup d'envoi</th>
                <th>Événement</th>
                <th>Marché</th>
                <th>Sélection</th>
                <th>Book</th>
                <th>Cote</th>
                <th>Mise</th>
                <th>Edge</th>
                <th>Statut</th>
                <th>CLV</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {bets.map((bet) => (
                <tr key={bet.id}>
                  <td>{formatKickoff(bet.event_start_time)}</td>
                  <td>
                    {bet.home_name} – {bet.away_name}
                  </td>
                  <td>{formatMarket(bet.market_type, bet.line)}</td>
                  <td>{formatSelection(bet.selection_code, bet.participant_name)}</td>
                  <td>{bet.bookmaker_name}</td>
                  <td className="num">{formatOdds(bet.odds_taken)}</td>
                  <td className="num">{formatStake(bet.stake)}</td>
                  <td className={`num ${bet.edge_at_placement >= 0 ? "positive" : "negative"}`}>
                    {formatPct(bet.edge_at_placement)}
                  </td>
                  <td className={STATUS_CLASS[bet.status]}>{STATUS_LABELS[bet.status]}</td>
                  <td className={`num ${bet.clv !== null ? (bet.clv >= 0 ? "positive" : "negative") : ""}`}>
                    {bet.clv !== null ? formatSignedPct(bet.clv) : "—"}
                  </td>
                  <td>
                    {bet.status === "pending" && (
                      <div className={styles.settleActions}>
                        <button
                          type="button"
                          className={styles.settleButton}
                          disabled={settlingId === bet.id}
                          onClick={() => handleSettle(bet.id, "won")}
                        >
                          Gagné
                        </button>
                        <button
                          type="button"
                          className={styles.settleButton}
                          disabled={settlingId === bet.id}
                          onClick={() => handleSettle(bet.id, "lost")}
                        >
                          Perdu
                        </button>
                        <button
                          type="button"
                          className={styles.settleButton}
                          disabled={settlingId === bet.id}
                          onClick={() => handleSettle(bet.id, "push")}
                        >
                          Push
                        </button>
                        <button
                          type="button"
                          className={styles.settleButton}
                          disabled={settlingId === bet.id}
                          onClick={() => handleSettle(bet.id, "void")}
                        >
                          Annulé
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </main>
    </>
  );
}
