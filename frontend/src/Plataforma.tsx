import { useEffect, useState } from "react";
import { api } from "./api";

export function Plataforma() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  useEffect(() => { api.platform().then(setData); }, []);
  const modules = (data?.modules as Array<Record<string, string>>) || [];
  const foundation = (data?.foundation as string[]) || [];
  return (
    <main className="shell fade-in">
      <p className="meta" style={{ marginTop: 28 }}>Capa de inteligencia de la entidad</p>
      <h1>El alta es el primer módulo. El resto se apoya en lo mismo.</h1>
      <p className="lede">Cadena de auditoría, bóveda por cliente, guardia de salida, reglas versionadas, modelo local. Lo que no está en esta demo se marca como siguiente. No inventamos un producto.</p>
      <div className="grid-12" style={{ marginTop: 28 }}>
        {modules.map((m) => (
          <div key={m.id} className="card span-4">
            <p className="meta">{m.status}</p>
            <h2>{m.name}</h2>
            <p>{m.note}</p>
          </div>
        ))}
      </div>
      <hr className="hair" style={{ margin: "36px 0" }} />
      <h2>Base compartida</h2>
      <ul>{foundation.map((f) => <li key={f}>{f}</li>)}</ul>
    </main>
  );
}
