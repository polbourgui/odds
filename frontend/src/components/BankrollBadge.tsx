import { useEffect, useState } from "react";
import { fetchBankroll } from "../api/client";
import { formatStake } from "../format";
import type { Bankroll } from "../types";
import styles from "./BankrollBadge.module.css";

const REFRESH_INTERVAL_MS = 30_000;

export function BankrollBadge() {
  const [bankroll, setBankroll] = useState<Bankroll | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      fetchBankroll()
        .then((data) => {
          if (!cancelled) setBankroll(data);
        })
        .catch(() => {
          // Silently skip a failed refresh; the badge just keeps its last value.
        });
    };
    load();
    const id = window.setInterval(load, REFRESH_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  if (!bankroll) return null;

  const pl = bankroll.current_balance - bankroll.initial_balance;
  const plClass = pl >= 0 ? "positive" : "negative";

  return (
    <span className={styles.badge}>
      Bankroll :{" "}
      <span className={styles.value}>
        {formatStake(bankroll.current_balance)} {bankroll.currency}
      </span>{" "}
      <span className={`num ${plClass}`} style={{ display: "inline" }}>
        ({pl >= 0 ? "+" : ""}
        {formatStake(pl)})
      </span>
    </span>
  );
}
