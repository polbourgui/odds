import { useState } from "react";
import { ApiError, placePaperBet } from "../api/client";
import styles from "./PlaceBetButton.module.css";

interface PlaceBetButtonProps {
  selectionId: number;
  bookmakerSlug: string;
}

type Status = "idle" | "loading" | "placed" | "error";

export function PlaceBetButton({ selectionId, bookmakerSlug }: PlaceBetButtonProps) {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);

  const handleClick = () => {
    setStatus("loading");
    setError(null);
    placePaperBet(selectionId, bookmakerSlug)
      .then(() => setStatus("placed"))
      .catch((err: unknown) => {
        setStatus("error");
        setError(err instanceof ApiError ? err.message : "Erreur inconnue");
      });
  };

  if (status === "placed") {
    return <span className={styles.placed}>Placé ✓</span>;
  }

  return (
    <div className={styles.wrapper}>
      <button
        type="button"
        className={styles.button}
        onClick={handleClick}
        disabled={status === "loading"}
      >
        {status === "loading" ? "…" : "Parier"}
      </button>
      {status === "error" && <span className={styles.error}>{error}</span>}
    </div>
  );
}
