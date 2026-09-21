import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./index.css";
import App from "./App.tsx";
import { BetHistoryPage } from "./pages/BetHistoryPage.tsx";
import { EventComparisonPage } from "./pages/EventComparisonPage.tsx";
import { ValueBetsPage } from "./pages/ValueBetsPage.tsx";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<App />}>
          <Route index element={<ValueBetsPage />} />
          <Route path="events/:eventId" element={<EventComparisonPage />} />
          <Route path="bets" element={<BetHistoryPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
