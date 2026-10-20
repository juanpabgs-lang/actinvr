import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "./api";

function useClock(zone: string) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  const time = new Intl.DateTimeFormat("es-MX", { timeZone: zone, hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(now);
  const date = new Intl.DateTimeFormat("es-MX", { timeZone: zone, weekday: "long", day: "numeric", month: "long" }).format(now);
  return { time, date };
}

export function Hub({ status }: { status: Record<string, unknown> | null }) {
  const cdmx = useClock("America/Mexico_City");
  const madrid = useClock("Europe/Madrid");
  const [clock, setClock] = useState<Record<string, unknown> | null>(null);
  const [resources, setResources] = useState<string>("comprobando…");

  useEffect(() => {
    api.clock().then(setClock).catch(() => null);
    const origins = new Set<string>();
    const push = (url: string) => {
      try { origins.add(new URL(url, location.href).origin); } catch { /* */ }
    };
    performance.getEntriesByType("resource").forEach((e) => push((e as PerformanceResourceTiming).name));
    const obs = new PerformanceObserver((list) => list.getEntries().forEach((e) => push(e.name)));
    obs.observe({ type: "resource", buffered: true });
    const t = setTimeout(() => {
      const foreign = [...origins].filter((o) => o !== location.origin);
      setResources(foreign.length ? `origen ajeno: ${foreign.join(", ")}` : "todo sale de este origen");
      obs.disconnect();
    }, 800);
    return () => { clearTimeout(t); obs.disconnect(); };
  }, []);

  const model = (status?.model as { available?: boolean; short_digest?: string; name?: string; digest_matches_pin?: boolean }) || {};
  const audit = (status?.audit as { ok?: boolean; count?: number }) || {};
  const egress = (status?.egress as { installed?: boolean; blocked?: number }) || {};
  const gap = clock?.gap_hours as number | undefined;

  return (
    <main className="shell fade-in">
      <p className="meta" style={{ margin: "28px 0 12px" }}>Demostración · datos inventados · 20 octubre 2026</p>
      <h1>De medianoche en México a las nueve en Madrid, el expediente ya está hecho.</h1>
      <p className="lede">
        El cliente envía lo que tenga, cuando quiera. Se le dice al momento qué falta.
        A las nueve, en Marqués de la Ensenada, una persona solo decide.
      </p>

      <div className="clocks" style={{ margin: "36px 0" }}>
        <div className="clock card">
          <div className="city">Ciudad de México</div>
          <div className="time">{cdmx.time}</div>
          <p>{cdmx.date}</p>
        </div>
        <div className="clock card">
          <div className="city">Madrid</div>
          <div className="time">{madrid.time}</div>
          <p>{madrid.date}{gap != null ? ` · ${gap} horas por delante` : ""}</p>
        </div>
      </div>

      <div className="status-dots" style={{ marginBottom: 28 }}>
        <span><i className={`dot ${model.available ? "" : "off"}`} />Modelo {model.name || "ministral-3:3b"} {model.short_digest || "f04aa1c738f6"}{model.digest_matches_pin ? " · anclado" : ""}</span>
        <span><i className={`dot ${egress.installed ? "" : "off"}`} />Salida bloqueada{egress.blocked ? ` · ${egress.blocked} intentos` : ""}</span>
        <span><i className={`dot ${audit.ok ? "" : "off"}`} />Cadena de auditoría {audit.ok ? `íntegra · ${audit.count} eventos` : "sin verificar"}</span>
        <span><i className="dot" />{resources}</span>
      </div>

      <div className="grid-12">
        <Link className="card span-4" to="/cliente" style={{ textDecoration: "none" }}>
          <p className="meta">01</p>
          <h2>Cliente en México</h2>
          <p>Alta en el teléfono, en español de México. Aviso inmediato si un documento no sirve.</p>
        </Link>
        <Link className="card span-4" to="/madrid" style={{ textDecoration: "none" }}>
          <p className="meta">02</p>
          <h2>Mesa de Madrid</h2>
          <p>Cola de la mañana. Cada comprobación hecha, cada evidencia unida, una persona firma.</p>
        </Link>
        <Link className="card span-4" to="/cumplimiento" style={{ textDecoration: "none" }}>
          <p className="meta">03</p>
          <h2>Cumplimiento</h2>
          <p>Dónde están los datos, qué modelo, cómo se borra, qué respondería Finreg.</p>
        </Link>
      </div>

      <hr className="hair" style={{ margin: "36px 0" }} />
      <p style={{ maxWidth: "40rem" }}>
        La entidad contratante es Alterna Inversiones y Valores, S.G.I.I.C., S.A., CNMV nº 282.
        Antes Actinver Inversiones y Valores. Norfront es una empresa de Delaware con su equipo en Madrid.
      </p>
    </main>
  );
}
