"""In-process egress guard.

Every outbound socket connection, UDP send and DNS lookup made by this process is
checked against an allowlist (loopback and the local model server). Anything else
is refused before a packet leaves, and the attempt is written to the audit log.

This complements, and does not replace, a host or network firewall: see
deploy/nftables-egress.conf for the production rule set.
"""
from __future__ import annotations

import collections
import errno
import ipaddress
import socket
import threading
import time

from . import settings
from .timeutil import iso

_ORIG_CONNECT = socket.socket.connect
_ORIG_CONNECT_EX = socket.socket.connect_ex
_ORIG_SENDTO = socket.socket.sendto
_ORIG_GETADDRINFO = socket.getaddrinfo

_lock = threading.Lock()
_recent: collections.deque = collections.deque(maxlen=200)
_counts = {"blocked": 0, "allowed": 0}
_installed = False
_persist = None


class EgressBlocked(ConnectionRefusedError):
    pass


def allowlist() -> list[dict]:
    return [
        {"host": "127.0.0.1 / ::1 / localhost", "purpose": "Servicios de esta misma máquina"},
        {"host": f"{settings.MODEL_HOST}:{settings.MODEL_PORT}", "purpose": "Servidor del modelo local (Ollama)"},
    ]


def _host_allowed(host: str | None) -> bool:
    if not host:
        return False
    h = str(host).strip("[]").lower()
    if h in {"localhost", "testserver", settings.MODEL_HOST.lower()}:
        return True
    try:
        return ipaddress.ip_address(h.split("%")[0]).is_loopback
    except ValueError:
        return False


def _note(kind: str, host, port, allowed: bool) -> None:
    entry = {"ts": iso(), "kind": kind, "host": str(host) if host is not None else None,
             "port": port, "allowed": allowed}
    with _lock:
        _counts["allowed" if allowed else "blocked"] += 1
        if not allowed:
            _recent.appendleft(entry)
    if not allowed and _persist is not None:
        try:
            _persist(entry)
        except Exception:
            pass


def _split(address):
    if isinstance(address, tuple) and len(address) >= 2:
        return address[0], address[1]
    return None, None


def _guarded_connect(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        host, port = _split(address)
        if not _host_allowed(host):
            _note("tcp", host, port, False)
            raise EgressBlocked(errno.ECONNREFUSED, f"Salida bloqueada por la guardia de red: {host}:{port}")
        _note("tcp", host, port, True)
    return _ORIG_CONNECT(self, address)


def _guarded_connect_ex(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        host, port = _split(address)
        if not _host_allowed(host):
            _note("tcp", host, port, False)
            return errno.ECONNREFUSED
        _note("tcp", host, port, True)
    return _ORIG_CONNECT_EX(self, address)


def _guarded_sendto(self, data, *args):
    address = args[-1] if args else None
    if self.family in (socket.AF_INET, socket.AF_INET6):
        host, port = _split(address)
        if not _host_allowed(host):
            _note("udp", host, port, False)
            raise EgressBlocked(errno.ECONNREFUSED, f"Envío UDP bloqueado: {host}:{port}")
    return _ORIG_SENDTO(self, data, *args)


def _guarded_getaddrinfo(host, *args, **kwargs):
    if host is not None:
        h = host.decode() if isinstance(host, bytes) else str(host)
        is_literal = True
        try:
            ipaddress.ip_address(h.strip("[]").split("%")[0])
        except ValueError:
            is_literal = False
        if not is_literal and not _host_allowed(h):
            port = args[0] if args else kwargs.get("port")
            _note("dns", h, port, False)
            raise socket.gaierror(socket.EAI_NONAME, f"Resolución DNS bloqueada por la guardia de red: {h}")
    return _ORIG_GETADDRINFO(host, *args, **kwargs)


def install(persist=None) -> None:
    global _installed, _persist
    _persist = persist
    if _installed:
        return
    socket.socket.connect = _guarded_connect
    socket.socket.connect_ex = _guarded_connect_ex
    socket.socket.sendto = _guarded_sendto
    socket.getaddrinfo = _guarded_getaddrinfo
    _installed = True


def uninstall() -> None:
    global _installed
    socket.socket.connect = _ORIG_CONNECT
    socket.socket.connect_ex = _ORIG_CONNECT_EX
    socket.socket.sendto = _ORIG_SENDTO
    socket.getaddrinfo = _ORIG_GETADDRINFO
    _installed = False


def status() -> dict:
    with _lock:
        return {
            "installed": _installed,
            "blocked": _counts["blocked"],
            "allowed": _counts["allowed"],
            "recent_blocked": list(_recent)[:50],
            "allowlist": allowlist(),
        }


def leak_test() -> list[dict]:
    """Try the usual ways data leaves a server. Every one of them must fail."""
    import smtplib

    import httpx

    attempts = [
        ("Llamada HTTPS a un proveedor de IA en la nube", "api.openai.com:443",
         lambda: httpx.get("https://api.openai.com/v1/models", timeout=3)),
        ("Resolución DNS de un dominio externo", "example.com",
         lambda: socket.getaddrinfo("example.com", 443)),
        ("Conexión directa por IP, sin DNS", "8.8.8.8:53",
         lambda: socket.create_connection(("8.8.8.8", 53), timeout=3)),
        ("Envío UDP a un servidor externo", "1.1.1.1:53",
         lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b"x", ("1.1.1.1", 53))),
        ("Correo saliente (SMTP)", "smtp.gmail.com:587",
         lambda: smtplib.SMTP("smtp.gmail.com", 587, timeout=3)),
        ("Webhook de telemetría", "telemetry.example.net:443",
         lambda: httpx.post("https://telemetry.example.net/collect", json={"probe": True}, timeout=3)),
    ]
    results = []
    for label, target, fn in attempts:
        started = time.perf_counter()
        try:
            fn()
            outcome, error = "salió", None
        except Exception as exc:
            outcome, error = "bloqueado", f"{type(exc).__name__}: {exc}"
        results.append({
            "label": label,
            "target": target,
            "outcome": outcome,
            "error": error,
            "ms": round((time.perf_counter() - started) * 1000, 1),
        })
    return results
