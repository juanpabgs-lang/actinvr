export type Json = Record<string, unknown>;

async function req<T>(path: string, init: RequestInit = {}, staff?: string): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (staff) headers.set("X-Staff-Id", staff);
  const res = await fetch(path, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* keep */
    }
    throw new Error(detail);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json() as Promise<T>;
  return res as unknown as T;
}

export const api = {
  status: () => req<Json>("/api/status"),
  clock: () => req<Json>("/api/clock"),
  personas: () => req<Array<{ id: string; label: string }>>("/api/personas"),
  start: (persona: string) => req<Json>("/api/client/start", { method: "POST", body: JSON.stringify({ persona }) }),
  client: (id: string, token?: string) => req<Json>(`/api/client/${id}${token ? `?token=${token}` : ""}`),
  patch: (id: string, body: Json, token?: string) =>
    req<Json>(`/api/client/${id}${token ? `?token=${token}` : ""}`, { method: "PATCH", body: JSON.stringify(body) }),
  sample: (id: string, kind: string) => req<Json>(`/api/client/${id}/sample/${kind}`, { method: "POST" }),
  otp: (id: string) => req<Json>(`/api/client/${id}/otp`, { method: "POST" }),
  sign: (id: string, code: string, manuscript?: string) =>
    req<Json>(`/api/client/${id}/sign`, { method: "POST", body: JSON.stringify({ code, manuscript }) }),
  withdraw: (id: string) => req<Json>(`/api/client/${id}/withdraw`, { method: "POST" }),
  help: (id: string, question: string) =>
    req<Json>(`/api/client/${id}/help`, { method: "POST", body: JSON.stringify({ question }) }),
  staff: () => req<Json[]>("/api/desk/staff"),
  queue: () => req<Json>("/api/desk/queue"),
  file: (id: string, staff: string) => req<Json>(`/api/desk/${id}`, {}, staff),
  decide: (id: string, kind: string, comment: string, staff: string) =>
    req<Json>(`/api/desk/${id}/decide`, { method: "POST", body: JSON.stringify({ kind, comment }) }, staff),
  dataMap: () => req<Json>("/api/compliance/data-map"),
  leak: () => req<Json>("/api/compliance/leak-test", { method: "POST" }),
  audit: () => req<Json>("/api/compliance/audit"),
  verify: () => req<Json>("/api/compliance/audit/verify", { method: "POST" }),
  tamper: () => req<Json>("/api/compliance/audit/tamper", { method: "POST" }),
  models: () => req<Json>("/api/compliance/models"),
  reproduce: (callId: string) => req<Json>(`/api/compliance/models/${callId}/reproduce`, { method: "POST" }),
  rules: () => req<Json[]>("/api/compliance/rules"),
  retention: (id: string, years?: number) =>
    req<Json>(`/api/compliance/retention/${id}${years != null ? `?years=${years}` : ""}`),
  shred: (id: string, staff: string) =>
    req<Json>(`/api/compliance/retention/${id}/shred`, { method: "POST" }, staff),
  inspection: () => req<Json>("/api/compliance/inspection", { method: "POST" }),
  finreg: () => req<Json>("/api/compliance/finreg"),
  dora: () => req<Json>("/api/compliance/dora"),
  platform: () => req<Json>("/api/platform"),
};
