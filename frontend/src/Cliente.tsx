import { useEffect, useState } from "react";
import { api } from "./api";

const STEPS = ["bienvenida", "datos", "documentos", "fondos", "idoneidad", "contrato", "hecho"] as const;
type Step = (typeof STEPS)[number];

const QUESTIONS = [
  { id: "horizon", text: "¿En cuántos años piensas usar este dinero?",
    options: [["0-2", "Menos de 2 años"], ["3-5", "De 3 a 5 años"], ["6-10", "De 6 a 10 años"], ["10+", "Más de 10 años"]] },
  { id: "capacity", text: "Si la cuenta bajara un 20 por ciento en un año, ¿qué harías?",
    options: [["sell", "La cerraría"], ["wait", "Esperaría a recuperar"], ["buy", "Añadiría dinero"]] },
  { id: "experience", text: "¿Qué has usado antes?",
    options: [["none", "Nada, o solo una cuenta de ahorro"], ["funds", "Fondos o acciones"], ["complex", "Derivados u otros productos complejos"]] },
  { id: "knowledge", text: "¿Qué estudiaste o a qué te dedicas?",
    options: [["other", "Otra cosa"], ["related", "Algo cercano a finanzas o empresa"], ["finance", "Finanzas, economía o inversión"]] },
  { id: "income", text: "¿De dónde sale el dinero que vas a invertir?",
    options: [["salary", "Nómina o honorarios"], ["sale", "Venta de un bien o de un negocio"], ["inheritance", "Herencia o donación"]] },
  { id: "share", text: "¿Qué parte de lo que tienes va a esta cuenta?",
    options: [["low", "Menos de un cuarto"], ["mid", "Entre un cuarto y la mitad"], ["high", "Más de la mitad"]] },
  { id: "sustainability", text: "¿Quieres que la sostenibilidad cuente en las recomendaciones?",
    options: [["yes", "Sí"], ["no", "No tengo preferencia"]] },
];

export function Cliente() {
  const [personas, setPersonas] = useState<Array<{ id: string; label: string }>>([]);
  const [persona, setPersona] = useState("live");
  const [caseId, setCaseId] = useState<string | null>(localStorage.getItem("caseId"));
  const [token, setToken] = useState<string | null>(localStorage.getItem("resume"));
  const [rec, setRec] = useState<Record<string, unknown> | null>(null);
  const [step, setStep] = useState<Step>("bienvenida");
  const [err, setErr] = useState<string | null>(null);
  const [docs, setDocs] = useState<Array<Record<string, unknown>>>([]);
  const [otp, setOtp] = useState<string>("");
  const [shownCode, setShownCode] = useState<string>("");
  const [manuscript, setManuscript] = useState("");
  const [helpQ, setHelpQ] = useState("");
  const [helpA, setHelpA] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const data = (rec?.data as Record<string, unknown>) || {};
  const person = (data.person as Record<string, string>) || {};

  useEffect(() => { api.personas().then(setPersonas); }, []);
  useEffect(() => {
    if (!caseId) return;
    api.client(caseId, token || undefined).then((out) => {
      setRec(out.case as Record<string, unknown>);
      setDocs((out.documents as Array<Record<string, unknown>>) || []);
      const st = (out.case as { stage?: Step }).stage;
      if (st && STEPS.includes(st)) setStep(st);
    }).catch(() => { setCaseId(null); localStorage.removeItem("caseId"); });
  }, [caseId, token]);

  async function start() {
    setBusy(true); setErr(null);
    try {
      const out = await api.start(persona);
      setCaseId(out.id as string);
      setToken(out.resume_token as string);
      localStorage.setItem("caseId", out.id as string);
      localStorage.setItem("resume", out.resume_token as string);
      setRec(out.case as Record<string, unknown>);
      setStep("datos");
      await api.patch(out.id as string, { gdpr_ack: true, ai_ack: true, stage: "datos" }, out.resume_token as string);
    } catch (e) { setErr((e as Error).message); }
    setBusy(false);
  }

  async function save(patch: Record<string, unknown>, next?: Step) {
    if (!caseId) return;
    const out = await api.patch(caseId, { ...patch, ...(next ? { stage: next } : {}) }, token || undefined);
    setRec(out.case as Record<string, unknown>);
    if (next) setStep(next);
  }

  async function sample(kind: string) {
    if (!caseId) return;
    setBusy(true);
    const out = await api.sample(caseId, kind);
    setDocs((d) => [...d.filter((x) => x.kind !== kind), { kind, analysis: out.analysis, id: out.id }]);
    setBusy(false);
  }

  return (
    <div className="phone-wrap">
      <div className="phone fade-in">
        <p className="meta">Alterna · alta a distancia</p>
        <div className="stepbar">{STEPS.map((s) => <i key={s} className={STEPS.indexOf(s) <= STEPS.indexOf(step) ? "on" : ""} />)}</div>

        {step === "bienvenida" && (
          <>
            <h2>Abre tu cuenta desde el celular</h2>
            <p>Esto es una demostración. Los clientes son inventados. No uses datos de nadie.</p>
            <p>Usamos tus datos para cumplir la ley de prevención de blanqueo. Eso no depende de que nos des permiso. En esta pantalla te ayuda un sistema de inteligencia artificial. No decide si te aceptamos: eso lo hace una persona.</p>
            <label>Con quién entras
              <select value={persona} onChange={(e) => setPersona(e.target.value)}>
                {personas.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
            </label>
            <button className="btn accent" disabled={busy} onClick={start}>Empezar</button>
          </>
        )}

        {step === "datos" && (
          <>
            <h2>Tus datos</h2>
            <p>{person.nombres} {person.apellido1} {person.apellido2}. Naciste el {person.dob}. CURP {person.curp}.</p>
            <label>¿Actúas por tu cuenta?
              <select defaultValue="si" onChange={(e) => save({ own_account: e.target.value === "si" })}>
                <option value="si">Sí</option>
                <option value="no">No</option>
              </select>
            </label>
            <label>¿Tú o tu pareja, padres o hijos tienen o tuvieron un cargo público importante?
              <select defaultValue="no" onChange={(e) => save({ is_pep: e.target.value === "si", pep_declared: e.target.value === "si" })}>
                <option value="no">No</option>
                <option value="si">Sí</option>
              </select>
            </label>
            <p>Si dices que sí, no se cierra la cuenta: cambia quién tiene que firmar en Madrid.</p>
            <label>¿Eres persona estadounidense (FATCA)?
              <select defaultValue="no" onChange={(e) => save({ fatca: { us_person: e.target.value === "si" } })}>
                <option value="no">No</option>
                <option value="si">Sí</option>
              </select>
            </label>
            <button className="btn" onClick={() => save({ crs: { residence: "MX", only_mx_es: true } }, "documentos")}>Seguir</button>
          </>
        )}

        {step === "documentos" && (
          <>
            <h2>Tus documentos</h2>
            <p>El que nos sirve es el pasaporte vigente. La INE la guardamos como complemento. El comprobante de domicilio, de los últimos tres meses —eso es política interna, no un artículo de la ley.</p>
            {(["pasaporte", "ine", "domicilio"] as const).map((kind) => {
              const doc = docs.find((d) => d.kind === kind);
              const analysis = (doc?.analysis as Record<string, unknown>) || {};
              const messages = (analysis.messages as string[]) || [];
              return (
                <div key={kind} style={{ marginBottom: 16 }}>
                  <button className="btn alt" disabled={busy} onClick={() => sample(kind)}>Usar documento de muestra · {kind}</button>
                  {messages.map((m) => <div key={m} className={`msg ${analysis.status === "ok" ? "ok" : ""}`}>{m}</div>)}
                  {doc && !messages.length && <div className="msg ok">Documento recibido.</div>}
                </div>
              );
            })}
            <button className="btn" onClick={() => save({}, "fondos")}>Seguir</button>
          </>
        )}

        {step === "fondos" && (
          <>
            <h2>Para qué y de dónde</h2>
            <label>¿A qué te dedicas?
              <input defaultValue={String(data.occupation || "")} onBlur={(e) => save({ occupation: e.target.value })} />
            </label>
            <label>¿Para qué quieres la cuenta?
              <input defaultValue={String(data.purpose || "")} onBlur={(e) => save({ purpose: e.target.value })} />
            </label>
            <label>Importe inicial aproximado (EUR)
              <input type="number" defaultValue={String(data.initial_amount || 40000)} onBlur={(e) => save({ initial_amount: Number(e.target.value) })} />
            </label>
            <p>El primer ingreso tiene que salir de una cuenta a tu nombre en un banco de México, de la UE o de España. En esta demo lo damos por simulado.</p>
            <button className="btn alt" disabled={busy} onClick={() => sample("origen_fondos")}>Añadir constancia de ingresos (muestra)</button>
            <div style={{ height: 12 }} />
            <button className="btn" onClick={() => save({ first_transfer: { same_holder: true, equivalent_country: true, arrived: true, country: "MX", simulated: true } }, "idoneidad")}>Seguir</button>
          </>
        )}

        {step === "idoneidad" && (
          <>
            <h2>Cómo quieres invertir</h2>
            {QUESTIONS.map((q) => (
              <label key={q.id}>{q.text}
                <select defaultValue={((data.answers as Record<string, string>) || {})[q.id] || ""}
                  onChange={(e) => save({ answers: { ...((data.answers as object) || {}), [q.id]: e.target.value } })}>
                  <option value="">Elige</option>
                  {q.options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </label>
            ))}
            <label>Servicio
              <select defaultValue={String(data.service || "asesoramiento")} onChange={(e) => save({ service: e.target.value })}>
                <option value="asesoramiento">Que me aconsejen</option>
                <option value="gdc">Que gestionen ellos la cartera</option>
                <option value="rto">Solo que envíen mis órdenes</option>
              </select>
            </label>
            <button className="btn" onClick={() => save({ precontract_ack: true }, "contrato")}>Ver el contrato</button>
          </>
        )}

        {step === "contrato" && (
          <>
            <h2>Lee y firma</h2>
            <p>Contrato con Alterna Inversiones y Valores, S.G.I.I.C., S.A. No produce efectos hasta que una persona en Madrid lo acepte. [Importes de costes: tarifario de Alterna.]</p>
            {caseId && <p><a href={`/api/client/${caseId}/contract`} target="_blank" rel="noreferrer">Abrir el PDF</a> — se genera al firmar.</p>}
            <button className="btn alt" onClick={async () => { const o = await api.otp(caseId!); setShownCode(String(o.code)); }}>Pedir código (simulado)</button>
            {shownCode && <p>Código de esta demo: <strong>{shownCode}</strong>. [Proveedor SMS: no hay.]</p>}
            <label>Código
              <input value={otp} onChange={(e) => setOtp(e.target.value)} inputMode="numeric" />
            </label>
            {data.service === "rto" && (
              <label>Si el producto es complejo y no te conviene, escribe: «este producto es complejo y se considera no conveniente para mí»
                <input value={manuscript} onChange={(e) => setManuscript(e.target.value)} />
              </label>
            )}
            <button className="btn accent" disabled={busy || !otp} onClick={async () => {
              setBusy(true);
              try {
                await api.sign(caseId!, otp, manuscript || undefined);
                setStep("hecho");
              } catch (e) { setErr((e as Error).message); }
              setBusy(false);
            }}>Firmar</button>
          </>
        )}

        {step === "hecho" && (
          <>
            <h2>Listo. Madrid lo ve a las nueve.</h2>
            <p>Cada comprobación ya está hecha. Una persona acepta. Te escribiremos cuando eso ocurra —el aviso no lleva tus datos.</p>
            {caseId && <p><a href={`/api/client/${caseId}/contract`} target="_blank" rel="noreferrer">Tu contrato (aún sin aceptación)</a></p>}
            <button className="btn alt" onClick={async () => { await api.withdraw(caseId!); setStep("hecho"); setErr("Has desistido del contrato."); }}>Desistir del contrato</button>
            <p style={{ marginTop: 16, fontSize: 12 }}>[España no ha publicado la transposición de la Directiva 2023/2673 a 20 oct 2026. El botón está porque la Directiva ya aplica.]</p>
          </>
        )}

        {err && <div className="msg">{err}</div>}

        {caseId && (
          <div className="help">
            <p>Te responde un sistema de inteligencia artificial. Una persona decide.</p>
            <label>Pregunta
              <input value={helpQ} onChange={(e) => setHelpQ(e.target.value)} placeholder="¿Me sirve la INE?" />
            </label>
            <button className="btn small alt" onClick={async () => {
              const a = await api.help(caseId, helpQ);
              setHelpA(String(a.text));
            }}>Preguntar</button>
            {helpA && <p style={{ marginTop: 8 }}>{helpA}</p>}
          </div>
        )}
      </div>
    </div>
  );
}
