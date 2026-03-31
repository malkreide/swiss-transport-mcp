"""
Gemeinsame Infrastruktur für alle opentransportdata.swiss APIs.

Stell dir das vor wie die Wasserversorgung eines Hauses:
- Der RateLimiter ist der Druckminderer (verhindert, dass du den Hahn zu oft aufdrehst)
- Der Cache ist der Boiler (speichert heisses Wasser, damit nicht jedes Mal neu erhitzt wird)
- Der APIClient ist die Hauptleitung (eine einzige Verbindung für alle Wasserhähne)

Jede API bei opentransportdata.swiss braucht einen eigenen API-Key,
hat eigene Rate Limits und liefert unterschiedliche Formate (XML, JSON, Protobuf).
Diese Infrastruktur handhabt das alles zentral.
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger("swiss-transport-mcp")


# =============================================================================
# Rate Limiter – Der Druckminderer
# =============================================================================

@dataclass
class RateLimiter:
    """
    Sliding-Window Rate Limiter.

    Beispiel: GTFS-RT erlaubt 2 Abfragen pro Minute.
    Der Limiter merkt sich die Zeitpunkte der letzten Abfragen
    und blockiert neue, wenn das Limit erreicht ist.

    Metapher: Wie ein Türsteher, der zählt, wie viele Leute
    in der letzten Minute reingegangen sind.
    """
    max_requests: int
    window_seconds: float
    _timestamps: list = field(default_factory=list)

    def _clean_old(self):
        """Entfernt Zeitstempel, die ausserhalb des Fensters liegen."""
        cutoff = time.monotonic() - self.window_seconds
        self._timestamps = [t for t in self._timestamps if t > cutoff]

    def can_proceed(self) -> bool:
        """Prüft, ob eine Abfrage erlaubt ist."""
        self._clean_old()
        return len(self._timestamps) < self.max_requests

    def record(self):
        """Registriert eine durchgeführte Abfrage."""
        self._timestamps.append(time.monotonic())

    def wait_time(self) -> float:
        """Berechnet die Wartezeit bis zur nächsten erlaubten Abfrage."""
        self._clean_old()
        if self.can_proceed():
            return 0.0
        oldest = self._timestamps[0]
        return (oldest + self.window_seconds) - time.monotonic()


# =============================================================================
# Cache – Der Boiler
# =============================================================================

@dataclass
class CacheEntry:
    data: Any
    created_at: float
    ttl: float

    @property
    def is_expired(self) -> bool:
        return (time.monotonic() - self.created_at) > self.ttl


class SimpleCache:
    """
    In-Memory Cache mit TTL (Time-to-Live).

    Warum? Störungsmeldungen ändern sich nicht jede Sekunde.
    Wenn 5 User gleichzeitig fragen "Gibt es Störungen auf der Strecke
    Zürich-Bern?", schicken wir nur EINE Anfrage an die API
    und liefern das gecachte Ergebnis für die nächsten X Sekunden.

    Metapher: Wie eine Wandtafel im Lehrerzimmer –
    einmal geschrieben, für alle lesbar, bis jemand wischt.
    """

    def __init__(self, max_entries: int = 500):
        self._store: dict[str, CacheEntry] = {}
        self._max_entries = max_entries

    def _make_key(self, prefix: str, params: dict) -> str:
        """Erstellt einen einheitlichen Cache-Schlüssel."""
        raw = f"{prefix}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, prefix: str, params: dict) -> Any | None:
        """Holt einen Wert aus dem Cache, falls noch gültig."""
        key = self._make_key(prefix, params)
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.is_expired:
            del self._store[key]
            return None
        logger.debug(f"Cache HIT für {prefix}")
        return entry.data

    def set(self, prefix: str, params: dict, data: Any, ttl: float):
        """Speichert einen Wert im Cache."""
        # Aufräumen, wenn Cache zu voll
        if len(self._store) >= self._max_entries:
            self._evict_expired()
        key = self._make_key(prefix, params)
        self._store[key] = CacheEntry(data=data, created_at=time.monotonic(), ttl=ttl)
        logger.debug(f"Cache SET für {prefix} (TTL: {ttl}s)")

    def _evict_expired(self):
        """Entfernt alle abgelaufenen Einträge."""
        expired = [k for k, v in self._store.items() if v.is_expired]
        for k in expired:
            del self._store[k]

    def clear(self):
        """Leert den gesamten Cache."""
        self._store.clear()


# =============================================================================
# API Client – Die Hauptleitung
# =============================================================================

@dataclass
class APIConfig:
    """
    Konfiguration für eine einzelne API.

    Jede API bei opentransportdata.swiss hat:
    - Einen eigenen API-Key (vom API-Manager)
    - Ein eigenes Rate Limit
    - Eine eigene Cache-Dauer (Störungen: kurz, Formationen: länger)
    """
    name: str
    base_url: str
    api_key: str
    rate_limit: RateLimiter
    cache_ttl: float  # Sekunden
    content_type: str = "application/json"  # oder "application/xml"


class TransportAPIClient:
    """
    Zentraler HTTP-Client für alle opentransportdata.swiss APIs.

    Bündelt:
    - Authentifizierung (Bearer Token im Header)
    - Rate Limiting (pro API getrennt)
    - Caching (gemeinsamer Cache, aber pro API getrennte Schlüssel)
    - Fehlerbehandlung (Retries, Timeouts, HTTP-Fehler)
    - Redirect-Handling (GTFS-RT nutzt Redirects für Caching)

    Metapher: Wie eine Telefonzentrale – ein Eingang,
    aber jeder Anruf wird an die richtige Abteilung weitergeleitet.
    """

    def __init__(self):
        self._configs: dict[str, APIConfig] = {}
        self._cache = SimpleCache()
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,  # Wichtig für GTFS-RT!
            headers={"User-Agent": "swiss-transport-mcp/1.0"}
        )

    def register_api(self, config: APIConfig):
        """Registriert eine neue API-Konfiguration."""
        self._configs[config.name] = config
        logger.info(f"API registriert: {config.name} → {config.base_url}")

    async def get(
        self,
        api_name: str,
        path: str = "",
        params: dict | None = None,
        use_cache: bool = True,
        cache_ttl_override: float | None = None,
    ) -> dict | str:
        """
        Führt einen GET-Request gegen eine registrierte API aus.

        Ablauf (wie eine Pipeline):
        1. Cache prüfen → Treffer? Sofort zurückgeben.
        2. Rate Limit prüfen → Zu viele Anfragen? Warten oder Fehler.
        3. Request senden → Mit Auth-Header und Redirect-Handling.
        4. Antwort verarbeiten → JSON parsen oder XML als Text.
        5. Cache befüllen → Für die nächsten Anfragen.
        """
        config = self._configs.get(api_name)
        if not config:
            raise ValueError(f"API '{api_name}' nicht registriert. Hast du den API-Key konfiguriert?")

        params = params or {}
        url = f"{config.base_url}{path}"

        # 1. Cache prüfen
        if use_cache:
            cached = self._cache.get(api_name, {"url": url, **params})
            if cached is not None:
                return cached

        # 2. Rate Limit prüfen
        if not config.rate_limit.can_proceed():
            wait = config.rate_limit.wait_time()
            if wait > 10:  # Mehr als 10s warten? Lieber Cache nutzen oder Fehler.
                raise RateLimitError(
                    f"API '{api_name}': Rate Limit erreicht. "
                    f"Nächste Abfrage möglich in {wait:.0f}s. "
                    f"Tipp: Erhöhe die Cache-TTL oder reduziere die Abfragehäufigkeit."
                )
            logger.info(f"Rate Limit für {api_name}: Warte {wait:.1f}s...")
            import asyncio
            await asyncio.sleep(wait)

        # 3. Request senden
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Accept": config.content_type,
        }

        try:
            config.rate_limit.record()
            response = await self._client.get(url, params=params, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitError(
                    f"API '{api_name}': Server meldet Rate Limit (HTTP 429). "
                    f"Warte und versuche es erneut."
                )
            elif e.response.status_code == 401:
                raise AuthenticationError(
                    f"API '{api_name}': Ungültiger API-Key (HTTP 401). "
                    f"Prüfe deinen Key im API-Manager: https://api-manager.opentransportdata.swiss/"
                )
            elif e.response.status_code == 404:
                raise NotFoundError(f"API '{api_name}': Ressource nicht gefunden (HTTP 404) für {url}")
            else:
                raise APIError(f"API '{api_name}': HTTP {e.response.status_code} – {e.response.text[:200]}")
        except httpx.TimeoutException:
            raise APIError(f"API '{api_name}': Timeout nach 30s. Der Server antwortet nicht.")
        except httpx.ConnectError:
            raise APIError(f"API '{api_name}': Verbindung fehlgeschlagen. Prüfe deine Netzwerkverbindung.")

        # 4. Antwort verarbeiten
        if "json" in config.content_type or "json" in response.headers.get("content-type", ""):
            result = response.json()
        else:
            result = response.text

        # 5. Cache befüllen
        ttl = cache_ttl_override or config.cache_ttl
        self._cache.set(api_name, {"url": url, **params}, result, ttl)

        return result

    async def post_xml(
        self,
        api_name: str,
        xml_body: str,
        use_cache: bool = True,
        cache_key_params: dict | None = None,
    ) -> str:
        """
        Führt einen POST-Request mit XML-Body aus (für OJP).

        OJP ist eine SOAP-ähnliche Schnittstelle:
        Man schickt XML rein, bekommt XML zurück.
        """
        config = self._configs.get(api_name)
        if not config:
            raise ValueError(f"API '{api_name}' nicht registriert.")

        # Cache prüfen
        cache_params = cache_key_params or {"body_hash": hashlib.md5(xml_body.encode()).hexdigest()}
        if use_cache:
            cached = self._cache.get(api_name, cache_params)
            if cached is not None:
                return cached

        # Rate Limit
        if not config.rate_limit.can_proceed():
            wait = config.rate_limit.wait_time()
            if wait > 10:
                raise RateLimitError(f"API '{api_name}': Rate Limit erreicht. Warte {wait:.0f}s.")
            import asyncio
            await asyncio.sleep(wait)

        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/xml",
        }

        try:
            config.rate_limit.record()
            response = await self._client.post(config.base_url, content=xml_body, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise APIError(f"API '{api_name}': HTTP {e.response.status_code} – {e.response.text[:300]}")

        result = response.text
        self._cache.set(api_name, cache_params, result, config.cache_ttl)
        return result

    async def close(self):
        """Schliesst den HTTP-Client."""
        await self._client.aclose()


# =============================================================================
# Fehlerklassen – Klare Diagnose statt kryptische Meldungen
# =============================================================================

class APIError(Exception):
    """Allgemeiner API-Fehler."""
    pass

class RateLimitError(APIError):
    """Rate Limit überschritten."""
    pass

class AuthenticationError(APIError):
    """API-Key ungültig oder fehlend."""
    pass

class NotFoundError(APIError):
    """Ressource nicht gefunden."""
    pass


# =============================================================================
# Factory – Erstellt den konfigurierten Client
# =============================================================================

def create_transport_client(
    siri_sx_key: str | None = None,
    occupancy_key: str | None = None,
    formation_key: str | None = None,
    ojp_fare_key: str | None = None,
) -> TransportAPIClient:
    """
    Erstellt einen fertig konfigurierten TransportAPIClient.

    Jede API, für die ein Key angegeben wird, wird registriert.
    Fehlende Keys = API nicht verfügbar (statt Crash).

    Rate Limits und Cache-TTLs sind auf die API-Dokumentation abgestimmt:
    - SIRI-SX: 2 req/min, Cache 120s (Störungen ändern sich nicht sekündlich)
    - Occupancy: 2 req/min, Cache 300s (Prognosen sind tagesbasiert)
    - Formation: 5 req/min, Cache 600s (Zugzusammensetzung ist stabil)
    - OJP Fare: 5 req/min, Cache 1800s (Preise ändern selten untertags)
    """
    client = TransportAPIClient()

    if siri_sx_key:
        client.register_api(APIConfig(
            name="siri_sx",
            base_url="https://api.opentransportdata.swiss/la/siri-sx",
            api_key=siri_sx_key,
            rate_limit=RateLimiter(max_requests=2, window_seconds=60),
            cache_ttl=120,
            content_type="application/xml",
        ))

    if occupancy_key:
        client.register_api(APIConfig(
            name="occupancy",
            base_url="https://api.opentransportdata.swiss/ckan-api",
            api_key=occupancy_key,
            rate_limit=RateLimiter(max_requests=2, window_seconds=60),
            cache_ttl=300,
            content_type="application/json",
        ))

    if formation_key:
        client.register_api(APIConfig(
            name="formation",
            base_url="https://api.opentransportdata.swiss/formation/v2",
            api_key=formation_key,
            rate_limit=RateLimiter(max_requests=5, window_seconds=60),
            cache_ttl=600,
            content_type="application/json",
        ))

    if ojp_fare_key:
        client.register_api(APIConfig(
            name="ojp_fare",
            base_url="https://api.opentransportdata.swiss/ojp20",
            api_key=ojp_fare_key,
            rate_limit=RateLimiter(max_requests=5, window_seconds=60),
            cache_ttl=1800,
            content_type="application/xml",
        ))

    return client
