import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { api } from "./api";
import { Cliente } from "./Cliente";
import { Cumplimiento } from "./Cumplimiento";
import { Hub } from "./Hub";
import { Madrid } from "./Madrid";
import { Plataforma } from "./Plataforma";

export function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "light");
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    api.status().then(setStatus).catch(() => setStatus(null));
  }, []);

  const tenant = (status?.tenant as { brand_short?: string } | undefined)?.brand_short || "Alterna";

  return (
    <div className="app">
      <header className="top">
        <div className="top-inner">
          <div className="brand">
            {tenant}
            <small>Alta a distancia · SINTÉTICO</small>
          </div>
          <nav className="nav">
            <NavLink to="/" end>Inicio</NavLink>
            <NavLink to="/cliente">Cliente</NavLink>
            <NavLink to="/madrid">Madrid</NavLink>
            <NavLink to="/cumplimiento">Cumplimiento</NavLink>
            <NavLink to="/plataforma">Plataforma</NavLink>
          </nav>
          <div className="top-tools">
            <span className="mark">Sintético</span>
            <button className="ghost" type="button" onClick={() => setTheme(theme === "light" ? "dark" : "light")}>
              {theme === "light" ? "Oscuro" : "Claro"}
            </button>
          </div>
        </div>
      </header>
      <Routes>
        <Route path="/" element={<Hub status={status} />} />
        <Route path="/cliente" element={<Cliente />} />
        <Route path="/madrid" element={<Madrid />} />
        <Route path="/madrid/:id" element={<Madrid />} />
        <Route path="/cumplimiento" element={<Cumplimiento />} />
        <Route path="/plataforma" element={<Plataforma />} />
      </Routes>
    </div>
  );
}
