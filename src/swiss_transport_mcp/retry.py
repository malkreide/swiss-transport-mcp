"""Retry-Politik gegenüber opentransportdata.swiss (ARCH-014).

Drei Fragen muss ein Retry beantworten: *was* wird wiederholt, *wie schnell*
und *wie lange*. Die erste klärt :func:`call_with_retry` (4xx ausser 429
scheitert sofort); die Konstanten hier klären die anderen beiden.

Der Kern ist über einen Callback generisch, weil die vier Aufrufstellen dieses
Servers unterschiedlich viel selbst tun: ``ckan_request`` prüft ein 403 vor
``raise_for_status``, ``TransportAPIClient`` bildet Fehler auf eigene
Exceptions ab und muss zusätzlich seinen Rate-Limiter pro Versuch bedienen.
Ein Kern, der den Request selbst absetzt, könnte das alles nicht.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import TypeVar

import httpx

logger = logging.getLogger("swiss-transport-mcp")

T = TypeVar("T")

ATTEMPTS = 4

# Deckel über den *ganzen* Aufruf — alle Versuche und Wartezeiten zusammen.
#
# Eine Versuchszahl ist keine Grenze: Vier Versuche à 30 s Timeout plus Backoff
# sind über zwei Minuten, und die Zahl 4 sagt das nirgends. Entscheidender ist,
# dass die massgebliche Grenze gar nicht uns gehört — der Aufrufer hat sein
# eigenes Timeout, und jenseits davon hört niemand mehr zu: Die Arbeit läuft
# weiter, die Last landet bei der Quelle, das Ergebnis geht ins Leere.
#
# Der Anker ist gemessen, nicht geschätzt: Das Python-MCP-SDK setzt
# ``MCP_DEFAULT_TIMEOUT = 30.0`` (``mcp/shared/_httpx_utils.py``).
TOTAL_BUDGET = 25.0

# OJP bekommt mehr, und zwar bewusst über dem Client-Default. Der Grund steht
# schon seit je an ``OJP_TIMEOUT``: Trip-Berechnungen dauern länger. Ein Budget
# von 25 s würde legitime Verbindungsabfragen abwürgen, die heute durchgehen —
# der Retry soll Ausfälle überbrücken und nicht funktionierende Anfragen
# kürzen. Damit ist die 45 s eine Abweichung mit Grund, keine aus Versehen.
OJP_BUDGET = 45.0

# Deckel für eine einzelne Wartezeit. Sichert zweierlei zugleich: eine
# Exponentialleiter, die sonst unbegrenzt wächst, und ein ``Retry-After``, das
# die Quelle senden darf, das man aber nicht absitzen muss.
MAX_DELAY = 20.0

BACKOFF_BASE = 2.0

# Streuung. Ohne sie retryen alle Clients, die denselben Ausfall getroffen
# haben, im Gleichtakt, und die Last kommt als Welle zurück — genau wenn die
# Quelle sich erholt. Der Retry-Sturm verlängert den Ausfall, den er
# überbrücken soll.
JITTER_SPREAD = 0.5  # exponentielle Wartezeiten landen in [0.5x, 1.5x]

# Auf einem ``Retry-After`` einseitig: Die Quelle hat gesagt, wann wir
# wiederkommen sollen — später ist höflich, früher wäre die Missachtung
# derselben Angabe, die man gerade liest.
AFTER_JITTER = 0.25  # landet in [1.0x, 1.25x]

# Status, die ein sinnvolles ``Retry-After`` tragen (RFC 9110 §10.2.3).
AFTER_STATUSES = frozenset({429, 503})

# Backoff-Wartezeiten laufen über diesen Alias, damit ein Test sie durch
# Patchen *dieses Modul-Attributs* überspringen kann. ``asyncio.sleep`` selbst
# zu patchen würde jeden Import im Prozess treffen — und ein Test, der
# ``asyncio.sleep(0)`` benutzt, um dem Event-Loop das Wort zu geben, prüft
# danach still nichts mehr.
_sleep = asyncio.sleep


def parse_retry_after(resp: httpx.Response | None) -> float | None:
    """Sekunden laut ``Retry-After`` der Antwort, oder ``None``.

    RFC 9110 §10.2.3 erlaubt zwei Formen: eine Sekundenzahl (``120``) und ein
    HTTP-Datum (``Wed, 21 Oct 2026 07:28:00 GMT``). Beide kommen vor, beide
    werden gelesen. Alles Unlesbare ergibt ``None`` und der Aufrufer fällt auf
    die eigene Kurve zurück — eine kaputte Kopfzeile darf auf dem Fehlerpfad
    nicht zum Absturz werden.
    """
    if resp is None or resp.status_code not in AFTER_STATUSES:
        return None
    raw = (resp.headers.get("Retry-After") or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return float(raw)
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:  # RFC-9110-Daten sind GMT; naiv heisst UTC
        when = when.replace(tzinfo=UTC)
    # Nie negativ: ein Datum in der Vergangenheit heisst «jetzt».
    return max(0.0, (when - datetime.now(UTC)).total_seconds())


def retry_delay(attempt: int, last_error: Exception | None) -> float:
    """Sekunden Wartezeit vor ``attempt`` (ARCH-014).

    Die Antwort der Quelle schlägt unsere Schätzung: Hat sie auf einem 429 oder
    503 ein ``Retry-After`` gesendet, gewinnt dieser Wert über die
    Exponentialkurve.
    """
    hinted = parse_retry_after(getattr(last_error, "response", None))
    if hinted is not None:
        jittered = hinted * (1.0 + random.random() * AFTER_JITTER)
    else:
        jittered = BACKOFF_BASE**attempt * (
            1.0 - JITTER_SPREAD + random.random() * 2 * JITTER_SPREAD
        )
    # Deckel *nach* dem Jittern. Die andere Reihenfolge machte MAX_DELAY zu gar
    # keiner Schranke: ein auf 20 s gedeckelter Wert wurde anschliessend mit bis
    # zu 1.5 multipliziert und landete bei 30 s.
    return min(jittered, MAX_DELAY)


def is_retryable(exc: Exception) -> bool:
    """Ob ``exc`` einen weiteren Versuch rechtfertigt.

    Netzwerkfehler und Timeouts ja. Beim Status gilt: 5xx und 429 ja, jedes
    andere 4xx nein — das ist eine Aussage über die Anfrage und keine über den
    Moment, und sie fällt beim vierten Mal genauso aus.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return isinstance(exc, httpx.RequestError)


async def call_with_retry(
    attempt_fn: Callable[[float], Awaitable[T]],
    *,
    budget: float | None = None,
    label: str = "request",
    before_attempt: Callable[[], None] | None = None,
) -> T:
    """Führt ``attempt_fn`` aus und wiederholt, was zu wiederholen sich lohnt.

    ``attempt_fn`` bekommt die Restlaufzeit in Sekunden und macht *einen*
    vollständigen Versuch. Alles, was es wirft und nicht :func:`is_retryable`
    erfüllt, geht unverändert an den Aufrufer — insbesondere ``ValueError``
    aus den Egress-Prüfungen, das sich nicht dadurch ändert, dass man es
    wiederholt.

    ``before_attempt`` wird vor jedem Versuch gerufen; die Aufrufstellen mit
    Rate-Limiter registrieren dort ihre Abfrage, damit ein Retry nicht am
    Limiter vorbei geht.
    """
    # Erst hier auflösen, nicht als Default-Argument: Ein Default bindet den
    # Wert beim Import, und damit wäre ``TOTAL_BUDGET`` zur Laufzeit nicht mehr
    # die Quelle der Wahrheit — wer die Konstante ändert, änderte nichts.
    if budget is None:
        budget = TOTAL_BUDGET
    deadline = time.monotonic() + budget
    last_exc: Exception | None = None

    for attempt in range(ATTEMPTS):
        if attempt > 0:
            delay = retry_delay(attempt, last_exc)
            # Eine Wartezeit, die das Budget überdauert, ist eine Wartezeit für
            # niemanden: Der Aufrufer hat aufgegeben, bevor sie endet.
            if delay >= deadline - time.monotonic():
                break
            logger.info(
                "Retry %s (%d/%d) in %.2fs nach %s",
                label,
                attempt + 1,
                ATTEMPTS,
                delay,
                type(last_exc).__name__,
            )
            await _sleep(delay)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            # httpx wendet sein Timeout pro Operation an (connect/read/write/
            # pool), und das Read-Timeout beginnt mit jedem Chunk von vorn — das
            # begrenzt jeden Schritt, nicht den Aufruf. Eine langsam tröpfelnde
            # Antwort könnte das Budget also überdauern, ohne dass ein einzelner
            # Read abliefe. ``asyncio.timeout`` ist die Wanduhr-Deadline, die
            # das Budget tatsächlich verspricht.
            async with asyncio.timeout(remaining):
                if before_attempt is not None:
                    before_attempt()
                return await attempt_fn(remaining)
        except TimeoutError as exc:  # Budget weg, nicht bloss dieser Versuch
            last_exc = exc
            break
        except Exception as exc:
            if not is_retryable(exc):
                raise
            last_exc = exc

    if last_exc is None:  # Budget weg, bevor ein Versuch rausging
        raise httpx.ConnectTimeout(f"Kein Versuch möglich: {budget:g}s Budget aufgebraucht")
    raise last_exc
