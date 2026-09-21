import { Outlet } from "react-router-dom";
import styles from "./App.module.css";
import { ComplianceBanner } from "./components/ComplianceBanner";
import { Nav } from "./components/Nav";

function App() {
  return (
    <div className={styles.app}>
      <ComplianceBanner />
      <Nav />
      <Outlet />
    </div>
  );
}

export default App;
