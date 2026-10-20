import { useEffect, useState } from "react";
import { api } from "./api";

export function Cumplimiento() {
  const [map, setMap] = useState<Record<string, unknown> | null>(null);
  const [leak, setLeak] = useState<Record<string, unknown> | null>(null);
  const [audit, setAudit] = useState<Record<string, unknown> | null>(null);
  const [tamper, setTamper] = useState<Record<string, unknown> | null>(null);
  const [models, setModels] = useState<Record<string, unknown> | null>(null);
  const [repro, setRepro] = useState<Record<string, unknown> | null>(null);
  const [rules, setRules] = useState<Array<Record<string, unknown>>>([]);
  const [finreg, setFinreg] = useState<Record<string, unknown> | null>(null);
  const [dora, setDora] = useState<Record<string, unknown> | null>(null);
  const [pack, setPack] = useState<Record<string, unknown> | null>(null);
  const [cases, setCases] = useState<Array<Record<string, unknown>>>([]);
  const [retId, setRetId] = useState("");
  const [ret, setRet] = useState<Record<string, unknown> | null>(null);
  const [years, setYears] = useState(10);

  useEffect(() => {
    api.dataMap().then(setMap);
    api.audit().then(setAudit);
    api.models().then(setModels);
    api.rules().then((r) => setRules(r as Array<Record<string, unknown>>));
    api.finreg().then(setFinreg);
    api.dora().then(setDora);
    api.queue().then((q) => {
      const items = (q.items as Array<Record<string, unknown>>) || [];
      setCases(items);
      if (items[0]) setRetId(String(items[0].id));
    });
  }, []);

  return (
    <main className="shell fade-in">
      <p className="meta" style={{ marginTop: 28 }}>Centro de cumplimiento · respuestas antes de que las pidan</p>
      <h1>Finreg no debería tener que preguntar.</h1>

      <section style={{ margin: "32px 0" }}>
        <h2>Mapa de datos</h2>
        <table className="table">
          <thead><tr><th>De</th><th>A</th><th>Cruza</th></tr></thead>
          <tbody>
            {((map?.flows as Array<Record<string, string>>) || []).map((f) => (
              <tr key={f.from + f.to}><td>{f.from}</td><td>{f.to}</td><td>{f.crosses}</td></tr>
            ))}
          </tbody>
        </table>
        <button className="btn" style={{ marginTop: 12 }} onClick={async () => setLeak(await api.leak())}>Probar fuga</button>
        {leak && (
          <table className="table" style={{ marginTop: 12 }}>
            <tbody>
              {((leak.results as Array<Record<string, string>>) || []).map((r) => (
                <tr key={r.label}><td>{r.label}</td><td>{r.target}</td><td>{r.outcome}</td></tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section style={{ margin: "32px 0" }}>
        <h2>Cadena de auditoría</h2>
        <p>Íntegra: {String((audit?.verify as { ok?: boolean })?.ok)} · {(audit?.verify as { count?: number })?.count} eventos · cabeza {(audit?.head as { hash?: string })?.hash?.slice(0, 16)}</p>
        <button className="btn alt" onClick={async () => setAudit(await api.audit())}>Verificar</button>
        {" "}
        <button className="btn alt" onClick={async () => setTamper(await api.tamper())}>Demostrar manipulación (copia)</button>
        {tamper && <pre style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>{JSON.stringify(tamper, null, 2)}</pre>}
      </section>

      <section style={{ margin: "32px 0" }}>
        <h2>Registro de modelos</h2>
        <p>{JSON.stringify(models?.status)}</p>
        <table className="table">
          <thead><tr><th>Id</th><th>Uso</th><th>Digest</th><th>Plantilla</th><th></th></tr></thead>
          <tbody>
            {((models?.calls as Array<Record<string, unknown>>) || []).slice(0, 8).map((c) => (
              <tr key={String(c.id)}>
                <td>{String(c.id)}</td><td>{String(c.purpose)}</td><td>{String(c.digest || "").slice(0, 12)}</td>
                <td>{c.fallback ? "sí" : "no"}</td>
                <td><button className="btn small alt" onClick={async () => setRepro(await api.reproduce(String(c.id)))}>Reproducir</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        {repro && <pre style={{ fontSize: 12 }}>{JSON.stringify(repro, null, 2)}</pre>}
      </section>

      <section style={{ margin: "32px 0" }}>
        <h2>Retención</h2>
        <label>Expediente
          <select value={retId} onChange={(e) => setRetId(e.target.value)}>
            {cases.map((c) => <option key={String(c.id)} value={String(c.id)}>{String(c.pseudonym)}</option>)}
          </select>
        </label>
        <label>Años desde el alta
          <input type="number" value={years} onChange={(e) => setYears(Number(e.target.value))} />
        </label>
        <button className="btn alt" onClick={async () => setRet(await api.retention(retId, years))}>Simular</button>
        {" "}
        <button className="btn alt" onClick={async () => setRet(await api.shred(retId, "pablo.ortiz"))}>Destruir la clave</button>
        {ret && <pre style={{ fontSize: 12 }}>{JSON.stringify(ret, null, 2)}</pre>}
      </section>

      <section style={{ margin: "32px 0" }}>
        <h2>Pack de reglas ES-PBC v2026.10</h2>
        {rules.map((pack) => (
          <div key={String(pack.pack)}>
            <h3>{String(pack.pack)} {String(pack.version)}</h3>
            {((pack.rules as Array<Record<string, unknown>>) || []).map((r) => (
              <div key={String(r.id)} className="q">
                <strong>{String(r.id)} · {String(r.title)}</strong>
                <div className="meta">{((r.cites as string[]) || []).join(" · ")}</div>
                <p>{String(r.reviewer || "")}</p>
              </div>
            ))}
          </div>
        ))}
      </section>

      <section style={{ margin: "32px 0" }}>
        <h2>Paquete de inspección</h2>
        <button className="btn" onClick={async () => setPack(await api.inspection())}>Exportar ZIP firmado</button>
        {pack && (
          <p>
            {String(pack.filename)} · sha256 {String(pack.sha256).slice(0, 16)}… · Ed25519
            {" "}<a href="/api/compliance/inspection/file">descargar</a>
          </p>
        )}
      </section>

      <section style={{ margin: "32px 0" }}>
        <h2>Cuestionario Finreg</h2>
        {((finreg?.questions as Array<{ q: string; a: string }>) || []).map((x) => (
          <div key={x.q} className="q"><strong>{x.q}</strong><p>{x.a}</p></div>
        ))}
      </section>

      <section style={{ margin: "32px 0" }}>
        <h2>Preguntas que cualquier proveedor de IA tiene que responder</h2>
        <p>{String(dora?.note || "")}</p>
        <table className="table">
          <thead><tr><th>Tema</th><th>Pregunta</th><th>Esta instalación</th><th>Otro proveedor</th></tr></thead>
          <tbody>
            {((dora?.rows as Array<Record<string, string>>) || []).map((r) => (
              <tr key={r.id}><td>{r.topic}<div className="meta">{r.art}</div></td><td>{r.question}</td><td>{r.us}</td><td>{r.other || "—"}</td></tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
