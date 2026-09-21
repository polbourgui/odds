import { useEffect, useState } from "react";
import { ApiError, fetchAppSettings, updateAppSettings } from "../api/client";
import type { AppSettings, DevigMethod } from "../types";
import styles from "./SettingsPage.module.css";

const DEVIG_LABELS: Record<DevigMethod, string> = {
  multiplicative: "Multiplicatif",
  power: "Power",
  shin: "Shin",
};

interface FormState {
  devig_method: DevigMethod;
  kelly_fraction_pct: string;
  kelly_cap_pct_pct: string;
  edge_threshold_pct: string;
  stale_odds_minutes: string;
  default_bankroll: string;
  monthly_loss_limit_enabled: boolean;
  monthly_loss_limit: string;
}

function toFormState(settings: AppSettings): FormState {
  return {
    devig_method: settings.devig_method,
    kelly_fraction_pct: String(settings.kelly_fraction * 100),
    kelly_cap_pct_pct: String(settings.kelly_cap_pct * 100),
    edge_threshold_pct: String(settings.edge_threshold * 100),
    stale_odds_minutes: String(settings.stale_odds_minutes),
    default_bankroll: String(settings.default_bankroll),
    monthly_loss_limit_enabled: settings.monthly_loss_limit !== null,
    monthly_loss_limit: settings.monthly_loss_limit !== null ? String(settings.monthly_loss_limit) : "500",
  };
}

export function SettingsPage() {
  const [form, setForm] = useState<FormState | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<Date | null>(null);

  useEffect(() => {
    fetchAppSettings().then((s) => setForm(toFormState(s)));
  }, []);

  if (!form) {
    return <div className={styles.main}>Chargement…</div>;
  }

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm({ ...form, [key]: value });

  const handleSave = () => {
    setSaving(true);
    setError(null);
    updateAppSettings({
      devig_method: form.devig_method,
      kelly_fraction: Number(form.kelly_fraction_pct) / 100,
      kelly_cap_pct: Number(form.kelly_cap_pct_pct) / 100,
      edge_threshold: Number(form.edge_threshold_pct) / 100,
      stale_odds_minutes: Number(form.stale_odds_minutes),
      default_bankroll: Number(form.default_bankroll),
      monthly_loss_limit: form.monthly_loss_limit_enabled ? Number(form.monthly_loss_limit) : null,
    })
      .then((updated) => {
        setForm(toFormState(updated));
        setSavedAt(new Date());
      })
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Erreur inconnue"))
      .finally(() => setSaving(false));
  };

  return (
    <>
      <header className={styles.header}>
        <span className={styles.title}>Réglages</span>
        <div className={styles.subtitle}>
          Ces paramètres pilotent le calcul d'edge et de mise Kelly pour l'ensemble de
          l'application — modifiés ici, ils s'appliquent immédiatement, sans redémarrage.
        </div>
      </header>
      <main className={styles.main}>
        <section className={styles.section}>
          <h2>Dévigage &amp; edge</h2>
          <div className={styles.field}>
            <label htmlFor="devig-method">
              Méthode de dévigage
              <span className={styles.hint}>Utilisée pour calculer la probabilité vraie à partir de la référence sharp</span>
            </label>
            <select
              id="devig-method"
              value={form.devig_method}
              onChange={(e) => update("devig_method", e.target.value as DevigMethod)}
            >
              {Object.entries(DEVIG_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div className={styles.field}>
            <label htmlFor="edge-threshold">
              Seuil d'edge minimum (%)
              <span className={styles.hint}>Mise Kelly nulle en dessous de ce seuil</span>
            </label>
            <input
              id="edge-threshold"
              type="number"
              step="0.1"
              value={form.edge_threshold_pct}
              onChange={(e) => update("edge_threshold_pct", e.target.value)}
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="stale-minutes">
              Fraîcheur max des cotes (min)
              <span className={styles.hint}>Une cote plus vieille n'est jamais affichée comme valide</span>
            </label>
            <input
              id="stale-minutes"
              type="number"
              min="1"
              step="1"
              value={form.stale_odds_minutes}
              onChange={(e) => update("stale_odds_minutes", e.target.value)}
            />
          </div>
        </section>

        <section className={styles.section}>
          <h2>Mise Kelly</h2>
          <div className={styles.field}>
            <label htmlFor="kelly-fraction">
              Fraction de Kelly (%)
              <span className={styles.hint}>25% = quart de Kelly, plus conservateur que le Kelly complet</span>
            </label>
            <input
              id="kelly-fraction"
              type="number"
              step="1"
              min="1"
              max="100"
              value={form.kelly_fraction_pct}
              onChange={(e) => update("kelly_fraction_pct", e.target.value)}
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="kelly-cap">
              Plafond de mise (% de la bankroll)
              <span className={styles.hint}>Mise jamais supérieure à ce pourcentage, même si Kelly le suggère</span>
            </label>
            <input
              id="kelly-cap"
              type="number"
              step="0.5"
              min="0.5"
              max="100"
              value={form.kelly_cap_pct_pct}
              onChange={(e) => update("kelly_cap_pct_pct", e.target.value)}
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="default-bankroll">
              Bankroll de référence (€)
              <span className={styles.hint}>
                Utilisée pour la mise suggérée dans le tableau des value bets — distincte de la
                bankroll de départ des paris fictifs, réglable dans « Mes paris »
              </span>
            </label>
            <input
              id="default-bankroll"
              type="number"
              min="0"
              step="10"
              value={form.default_bankroll}
              onChange={(e) => update("default_bankroll", e.target.value)}
            />
          </div>
        </section>

        <section className={styles.section}>
          <h2>Conformité</h2>
          <div className={styles.field}>
            <label htmlFor="loss-limit-enabled">Plafond de perte mensuel virtuel</label>
            <input
              id="loss-limit-enabled"
              type="checkbox"
              checked={form.monthly_loss_limit_enabled}
              onChange={(e) => update("monthly_loss_limit_enabled", e.target.checked)}
              style={{ justifySelf: "end" }}
            />
          </div>
          {form.monthly_loss_limit_enabled && (
            <div className={styles.field}>
              <label htmlFor="loss-limit">
                Plafond (€)
                <span className={styles.hint}>Alerte sur la page Statistiques une fois atteint ce mois-ci</span>
              </label>
              <input
                id="loss-limit"
                type="number"
                min="0"
                step="10"
                value={form.monthly_loss_limit}
                onChange={(e) => update("monthly_loss_limit", e.target.value)}
              />
            </div>
          )}
        </section>

        <div className={styles.actions}>
          <button type="button" className={styles.button} onClick={handleSave} disabled={saving}>
            Enregistrer
          </button>
          {error && <span className={`${styles.status} negative`}>{error}</span>}
          {!error && savedAt && (
            <span className={styles.status}>Enregistré à {savedAt.toLocaleTimeString("fr-FR")}</span>
          )}
        </div>
      </main>
    </>
  );
}
