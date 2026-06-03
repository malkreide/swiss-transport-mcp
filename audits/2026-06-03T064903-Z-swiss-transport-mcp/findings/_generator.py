#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, re, pathlib, sys

RUN = pathlib.Path(sys.argv[1])
CHECKS = pathlib.Path(sys.argv[2])
SERVER = "swiss-transport-mcp"
DATE = "2026-06-03"
AUDITOR = "mcp-audit Skill (automatisiert)"

vr = json.load(open(RUN / "verification-results.json"))
results = vr["results"]

def frontmatter(cid):
    t = (CHECKS / f"{cid}.md").read_text(encoding="utf-8")
    m = re.search(r"^---\n(.*?)\n---", t, re.S)
    d = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            d[k.strip()] = v.strip().strip('"\'')
    return d

# Per-check remediation + effort. Concrete, code-anchored.
REM = {
 "SEC-016": ("**S** — eine Zeile in `server.py`.",
   "```diff\n-        host = os.environ.get(\"MCP_HOST\", \"0.0.0.0\")\n+        # Lokal sicher per Default; 0.0.0.0 nur explizit fuer Container\n+        host = os.environ.get(\"MCP_HOST\", \"127.0.0.1\")\n```\n"
   "1. Default-Host auf `127.0.0.1` setzen.\n2. Im Deployment (Render/Railway) `MCP_HOST=0.0.0.0` explizit als Env-Var setzen.\n3. README-Deployment-Sektion entsprechend dokumentieren."),
 "SEC-004": ("**M** — Validierungs-Helper + SSL-Guard.",
   "1. `TRANSPORT_SSL_VERIFY=false` in Produktion verbieten (z.B. nur erlauben wenn `ENV=dev`).\n2. Falls je benutzergesteuerte URLs hinzukommen: `urlparse`-Schema-Check (nur `https`) + Blocklist fuer `169.254.169.254`, `127.0.0.0/8`, RFC-1918.\n3. `TRANSPORT_CKAN_URL`-Override gegen Allow-List der opentransportdata.swiss-Hosts validieren."),
 "SEC-009": ("**M** — abhaengig von Auth-Entscheidung.",
   "1. Solange `auth_model=none`: SSE-Deployment hinter Reverse-Proxy mit Auth oder nur intern erreichbar betreiben.\n2. SDK-Version pinnen und verifizieren, dass `Mcp-Session-Id` per `secrets.token_urlsafe(32)`/UUIDv4 generiert wird.\n3. Bei Einfuehrung von Auth: Session an validierte `user_id` binden (`<user_id>:<session_id>`)."),
 "OBS-004": ("**S** — Logging-Konfiguration ergaenzen.",
   "```diff\n+import sys\n+logging.basicConfig(stream=sys.stderr, level=logging.INFO,\n+    format=\"%(asctime)s %(name)s %(levelname)s: %(message)s\")\n```\n"
   "In `server.py` vor `mcp.run()` einfuegen, damit Logging garantiert auf stderr geht und stdout fuer das JSON-RPC-Protokoll reserviert bleibt."),
 "ARCH-009": ("**S** — Annotations an 5 Tools ergaenzen.",
   "Die fuenf Extension-Tools (`get_transport_disruptions`, `get_train_occupancy`, `get_ticket_price`, `get_train_composition`, `check_transport_api_status`) mit dem gleichen `annotations={...}`-Block wie die Core-Tools versehen (`readOnlyHint=True`, `destructiveHint=False`, `idempotentHint` je nach Echtzeit-Charakter, `openWorldHint=True`)."),
 "OBS-002": ("**S** — Upstream-Text nicht weiterreichen.",
   "`e.response.text[:200]`/`[:300]` aus den Fehlermeldungen in `api_client.py:163` und `api_infrastructure.py:257,317` entfernen oder durch generische Meldung + interne (stderr) Log-Zeile ersetzen. Dem LLM nur Status-Code + Klartext-Kategorie zurueckgeben."),
 "OPS-001": ("**M** — Tests auf echte Assertions umstellen.",
   "1. `print()`+Counter-Muster durch `assert` ersetzen, damit pytest tatsaechlich rot wird.\n2. `respx` (bereits Dev-Dep) fuer HTTP-Mocking nutzen → Unit-Tests ohne echten Key/Netz.\n3. Coverage auf die Kernmodule (ojp_client, siri_sx, occupancy, fare, formation) ausweiten."),
 "SCALE-001": ("**M** — Transport auf Streamable HTTP migrieren.",
   "`mcp.run(transport=\"sse\", ...)` auf den aktuellen Streamable-HTTP-Transport des MCP-SDK umstellen; SSE gilt als Legacy. Deployment-Doku in README aktualisieren."),
 "SCALE-002": ("**M** — Skalierungsstrategie dokumentieren.",
   "Falls Multi-Instance geplant: Sticky-Sessions / shared Session-Store (Redis) festlegen. Solange Single-Instance: explizit als Constraint im README dokumentieren."),
 "SCALE-003": ("**M** — Edge-Routing definieren (nur bei Scale-out).",
   "Bei horizontaler Skalierung `Mcp-Session-Id`-basiertes Routing am Edge-LB (HAProxy Stick-Tables o.ae.) einrichten. Aktuell als nicht-anwendbar (Single-Instance) dokumentieren."),
 "SDK-001": ("**M** — FastMCP Lifespan einfuehren.",
   "Einen `@asynccontextmanager`-Lifespan mit `AsyncExitStack` einrichten, der EINEN gepoolten `httpx.AsyncClient` erstellt und beim Shutdown sauber schliesst. `api_client.py` von Per-Request-Clients auf den geteilten Client umstellen; `TransportAPIClient.close()` im Lifespan-Teardown aufrufen."),
 "SDK-004": ("**S** — CORS explizit konfigurieren.",
   "Fuer den SSE/HTTP-Pfad CORS so konfigurieren, dass `Mcp-Session-Id` via `expose_headers` fuer Browser-Clients sichtbar ist; erlaubte Origins (z.B. claude.ai) explizit setzen."),
 "SEC-005": ("**M** — DNS-Pinning / SSL-Haertung.",
   "`TRANSPORT_SSL_VERIFY=false` in Produktion unterbinden. Optional DNS-Pinning der opentransportdata.swiss-Hosts oder fixe IP-Allow-List am Network-Layer."),
 "SEC-007": ("**M** — Dockerfile mit Haertung.",
   "Multi-Stage-Dockerfile hinzufuegen: non-root User, minimal base image (`python:3.12-slim`), nur noetige Dependencies, `--read-only`-faehig. Render/Railway auf das Image umstellen."),
 "SEC-013": ("**M** — Secret-Management haerten.",
   "1. `.gitignore` mit `.env` ergaenzen.\n2. Fuer Produktion Secret-Manager (Render/Railway Secrets bzw. Vault) statt Plain-Env empfehlen/dokumentieren.\n3. Optional `pydantic.SecretStr` fuer In-Memory-Repraesentation."),
 "SEC-021": ("**M** — Egress-Allow-List.",
   "Code-Layer: feste Allow-List der erlaubten Hosts (`api.opentransportdata.swiss`, `data.opentransportdata.swiss`) gegen die jede ausgehende Anfrage (inkl. `TRANSPORT_CKAN_URL`-Override) geprueft wird. Network-Layer: Egress-Policy im Deployment."),
 "SEC-022": ("**M** — Tool-Integritaet.",
   "Namespace-Praefix konsistent halten (alle Tools `transport_*`). Optional Tool-Hash-Manifest pflegen, das die registrierte Tool-Liste/Signaturen pinnt, um Rug-Pull-Redefinition zu erkennen."),
 "SEC-008": ("**S** — Consent-Hinweis dokumentieren.",
   "Im README einen kurzen Pre-Configuration-Consent-Hinweis ergaenzen (welche Daten der Server abruft, welche Keys er nutzt), bevor der User ihn in Claude Desktop registriert."),
 "ARCH-008": ("**S** — Prompts-Primitive ergaenzen.",
   "Mindestens einen `@mcp.prompt` hinzufuegen (z.B. 'Schulreise planen'-Prompt-Template), um alle drei MCP-Primitive (Tools/Resources/Prompts) zu nutzen."),
 "ARCH-012": ("**S** — Versionen pinnen.",
   "MCP-`protocolVersion` explizit pinnen/dokumentieren und `mcp[cli]` mit Obergrenze versehen (z.B. `>=1.0.0,<2.0.0`), um unkontrollierte SDK-Drift zu vermeiden."),
 "OBS-003": ("**M** — Structured Logging.",
   "Auf strukturierte Logs (JSON, z.B. `structlog`) mit RFC-5424-Severity umstellen und Handler explizit konfigurieren (zusammen mit OBS-004 stderr)."),
 "OBS-006": ("**L** — OpenTelemetry-Tracing.",
   "OpenTelemetry-Instrumentierung pro Tool-Call ergaenzen (Span je Tool, Attribute fuer API-Name/Dauer/Status). Optional, je nach Observability-Anforderung."),
 "SCALE-004": ("**M** — Containerization.",
   "Multi-Stage-Dockerfile + `.dockerignore` hinzufuegen (deckt sich mit SEC-007)."),
 "SCALE-006": ("**S** — Resource-Limits.",
   "Im Deployment (Render/Railway bzw. Container-Orchestrierung) Memory-/CPU-/FD-Limits setzen und im README dokumentieren."),
 "SDK-002": ("**M** — Typisierte Tool-Returns.",
   "Tool-Rueckgaben von handgebauten `json.dumps`-Strings auf Pydantic-v2-Modelle/`TypedDict` umstellen, damit das Output-Schema typisiert und stabil ist."),
 "SDK-003": ("**S** — Context-Injection.",
   "Bei laengeren OJP-Trip-Berechnungen `ctx: Context` injizieren und `ctx.info()/ctx.report_progress()` fuer Progress/Logging nutzen."),
}

written = []
for cid, r in results.items():
    if r["status"] not in ("fail", "partial"):
        continue
    fm = frontmatter(cid)
    title = fm.get("title", cid)
    pdf = fm.get("pdf_ref", "—")
    sev = r["severity"]
    effort, rem = REM.get(cid, ("**M**", "Siehe Best-Practice-Katalog-Check."))
    ev = "\n".join(f"- {e}" for e in r["evidence"]) or "- (kein Positiv-Beleg; Anforderung nicht erfuellt)"
    gaps = "\n".join(f"- {g}" for g in r["gaps"]) or "- —"
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]
    doc = f"""## Finding: {cid} — {title}

| Feld | Wert |
|---|---|
| **Severity** | {sev} |
| **Status** | open |
| **Server** | `{SERVER}` |
| **Check-Reference** | `{cid}` |
| **PDF-Reference** | {pdf} |
| **Audit-Datum** | {DATE} |
| **Auditor** | {AUDITOR} |
| **Verification-Status** | `{r['status']}` |

### Observed Behavior

{ev}

### Gaps (Abweichung vom Best-Practice-Katalog)

{gaps}

### Remediation

{rem}

### Effort Estimate

{effort}

### Verification After Fix

- Re-Audit dieses Checks ({cid}) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
"""
    (RUN / "findings").mkdir(exist_ok=True)
    (RUN / "findings" / f"{cid}-{slug}.md").write_text(doc, encoding="utf-8")
    written.append(cid)

print(f"Wrote {len(written)} findings: {sorted(written)}")
