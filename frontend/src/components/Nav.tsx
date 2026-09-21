import { NavLink } from "react-router-dom";
import { BankrollBadge } from "./BankrollBadge";
import styles from "./Nav.module.css";

export function Nav() {
  return (
    <nav className={styles.nav}>
      <div className={styles.links}>
        <NavLink
          to="/"
          end
          className={({ isActive }) => `${styles.link} ${isActive ? styles.activeLink : ""}`}
        >
          Value bets
        </NavLink>
        <NavLink
          to="/bets"
          className={({ isActive }) => `${styles.link} ${isActive ? styles.activeLink : ""}`}
        >
          Mes paris
        </NavLink>
        <NavLink
          to="/stats"
          className={({ isActive }) => `${styles.link} ${isActive ? styles.activeLink : ""}`}
        >
          Statistiques
        </NavLink>
        <NavLink
          to="/settings"
          className={({ isActive }) => `${styles.link} ${isActive ? styles.activeLink : ""}`}
        >
          Réglages
        </NavLink>
      </div>
      <div className={styles.spacer} />
      <BankrollBadge />
    </nav>
  );
}
