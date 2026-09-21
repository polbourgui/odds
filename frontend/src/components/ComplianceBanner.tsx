import styles from "./ComplianceBanner.module.css";

export function ComplianceBanner() {
  return (
    <div className={styles.banner}>
      <strong>18+</strong> — Jouer comporte des risques : dépendance, isolement,
      difficultés financières. Joueurs Info Service : <strong>09 74 75 13 13</strong> (appel
      non surtaxé). Outil d'analyse — aucun gain garanti.
    </div>
  );
}
