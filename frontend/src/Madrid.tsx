import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "./api";

export function Madrid() {
  const { id } = useParams();
  const nav = useNavigate();
  const [staff, setStaff] = useState<Array<Record<string, string>>>([]);
  const [who, setWho] = useState("ana.reyes");
  const [queue, setQueue] = useState<Record<string, unknown> | null>(null);
  const [file, setFile] = useState<Record<string, unknown> | null>(null);
  const [comment, setComment] = useState("");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { api.staff().then((s) => setStaff(s as Array<Record<string, string>>)); }, []);
  useEffect(() => {
    const load = () => api.queue().then(setQueue);
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    if (!id) { setFile(null); return; }
    api.file(id, who).then(setFile).catch((e) => setErr((e as Error).message));
  }, [id, who]);

  const items = ((queue?.items as Array<Record<string, unknown>>) || []);
  const rec = file?.case as Record<string, unknown> | undefined;
  const result = (rec?.result as Record<string, unknown>) || {};
  const data = (rec?.data as Record<string, unknown>) || {};
  const person = (data.person as Record<string, string>) || {};

  return (
    <div className="split fade-in">
      <aside>
        <p className="meta">Mesa · Madrid</p>
        <label>Quién eres
          <select value={who} onChange={(e) => setWho(e.target.value)}>
            {staff.map((s) => <option key={s.id} value={s.id}>{s.name} · {s.role}</option>)}
          </select>
        </label>
        <p style={{ fontSize: 12 }}>Control de demostración. No hay inicio de sesión.</p>
        <table className="table">
          <thead><tr><th>Expediente</th><th></th></tr></thead>
          <tbody>
            {items.map((it) => (
              <tr key={String(it.id)} onClick={() => nav(`/madrid/${it.id}`)}>
                <td>
                  <div>{String(it.pseudonym)}</div>
                  <div className="meta">{String(it.id)}</div>
                </td>
                <td><span className={`pill ${it.readiness}`}>{String(it.readiness || it.status)}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </aside>

      <article className="evidence">
        {!rec && <p>Elige un expediente. A las nueve, estos ya estaban hechos.</p>}
        {rec && (
          <>
            <p className="meta">{String(rec.id)} · {String(rec.route)} · {String(rec.service)}</p>
            <h2>{String(rec.pseudonym)}</h2>
            <p>{person.nombres} {person.apellido1} {person.apellido2} · {person.dob} · {person.curp}</p>
            <section>
              <h3>Resumen (borrador, no decide)</h3>
              <p>{String((result.summary as { text?: string } | undefined)?.text || "Sin resumen")}</p>
              {(result.summary as { fallback?: boolean } | undefined)?.fallback && <p className="meta">Plantilla: el modelo no contestó o está desactivado.</p>}
            </section>
            <section>
              <h3>Identidad</h3>
              <p>Pasaporte fehaciente: {String((result.identity as { fehaciente?: boolean } | undefined)?.fehaciente)}</p>
              <p>Vía: {String(rec.route)}. Primer ingreso simulado desde cuenta propia en México (país equivalente, Acuerdo 17/07/2012).</p>
            </section>
            <section>
              <h3>Listas</h3>
              <pre style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>
                {JSON.stringify((result.screening as { discarded?: unknown; candidates?: unknown; confirmed_hit?: boolean } | undefined) && {
                  confirmado: (result.screening as { confirmed_hit?: boolean }).confirmed_hit,
                  candidatos: (result.screening as { candidates?: unknown[] }).candidates?.length ?? (result.screening as { candidates?: number }).candidates,
                  descartados: (result.screening as { discarded?: unknown[] }).discarded,
                }, null, 2)}
              </pre>
            </section>
            <section>
              <h3>Riesgo</h3>
              <p>Nivel {String((result.risk as { level?: string })?.level)} · {String((result.risk as { score?: number })?.score)} puntos · diligencia {String((result.risk as { regime?: string })?.regime)} · autoriza {String(rec.approval_level)}</p>
              <ul>
                {((result.risk as { factors?: Array<{ label: string; points: number }> })?.factors || []).map((f) => (
                  <li key={f.label}>{f.label} ({f.points > 0 ? "+" : ""}{f.points})</li>
                ))}
              </ul>
              <p className="meta">[Pesos de ejemplo. Calibración: Alterna / Finreg.]</p>
            </section>
            <section>
              <h3>MiFID</h3>
              <p>Minorista. Perfil {String(((result.mifid as { suitability?: { profile?: string } })?.suitability || {}).profile || "—")}.</p>
            </section>
            <section>
              <h3>Reglas</h3>
              {((result.findings as Array<{ id: string; status: string; title: string; cites: string[] }>) || []).map((f) => (
                <div key={f.id} style={{ marginBottom: 8 }}>
                  <span className={`pill ${f.status}`}>{f.status}</span> {f.id} {f.title}
                  <div className="meta">{(f.cites || []).join(" · ")}</div>
                </div>
              ))}
            </section>
            <section>
              <h3>Contrato</h3>
              <p><a href={`/api/client/${rec.id}/contract`} target="_blank" rel="noreferrer">PDF · {String(rec.contract_sha256 || "").slice(0, 16)}</a></p>
            </section>
            <section>
              <h3>Auditoría de este expediente</h3>
              <ul>
                {((file?.audit as Array<{ seq: number; action: string; ts: string }>) || []).slice(0, 12).map((e) => (
                  <li key={e.seq}>{e.ts} · {e.action}</li>
                ))}
              </ul>
            </section>
          </>
        )}
      </article>

      <aside>
        <p className="meta">Decisión</p>
        {!rec && <p>Cuatro ojos. PEP y riesgo alto: dirección.</p>}
        {rec && (
          <>
            <p>Estado {String(rec.status)}. Autorización {String(rec.approval_level)}.</p>
            <label>Nota
              <textarea rows={4} value={comment} onChange={(e) => setComment(e.target.value)} />
            </label>
            <div className="row">
              {["recomendar", "pedir_mas", "aceptar", "rechazar"].map((k) => (
                <button key={k} className={`btn small ${k === "aceptar" ? "accent" : "alt"}`} onClick={async () => {
                  setErr(null);
                  try { await api.decide(String(rec.id), k, comment, who); setFile(await api.file(String(rec.id), who)); }
                  catch (e) { setErr((e as Error).message); }
                }}>{k.replace("_", " ")}</button>
              ))}
            </div>
            {err && <div className="msg">{err}</div>}
            <p className="meta" style={{ marginTop: 16 }}>Aceptar pide una recomendación previa de otra persona.</p>
            <Link to="/cumplimiento">Centro de cumplimiento</Link>
          </>
        )}
      </aside>
    </div>
  );
}
