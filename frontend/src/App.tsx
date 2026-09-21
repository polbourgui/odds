import { Outlet } from "react-router-dom";
import styles from "./App.module.css";
import { ComplianceBanner } from "./components/ComplianceBanner";

function App() {
  return (
    <div className={styles.app}>
      <ComplianceBanner />
      <Outlet />
    </div>
  );
}

export default App;
