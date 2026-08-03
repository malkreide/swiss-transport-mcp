"""Gemeinsame Fixtures.

Der Zweck ist ein einziger: Die Retry-Schleife in ``retry`` wartet zwischen
Versuchen, und eine Testsuite, die diese Wartezeiten absitzt, wird langsam
genug, dass sie niemand mehr laufen lässt. Ein Test, der ein 503 mockt, kostet
sonst rund 14 Sekunden statt Millisekunden.
"""

from __future__ import annotations

import asyncio

import pytest

from swiss_transport_mcp import retry as retry_mod

# Die echte ``asyncio.sleep`` festhalten, bevor irgendeine Fixture läuft. Wer
# sie erst *innerhalb* eines Tests greift, greift die bereits gepatchte.
_REAL_SLEEP = asyncio.sleep


@pytest.fixture(autouse=True)
def _no_sleep(request, monkeypatch):
    """Retry-Wartezeiten überspringen — ausser in Live-Tests.

    Gepatcht wird das Modul-Attribut ``retry._sleep``, **nicht**
    ``asyncio.sleep``: Letzteres würde jeden Import im Prozess treffen. Ein
    Test, der ``asyncio.sleep(0)`` benutzt, um dem Event-Loop das Wort zu
    geben, prüft danach still nichts mehr — er läuft weiter und misst nichts.
    """
    if "live" in request.keywords:
        return

    async def _instant(_seconds):
        return None

    monkeypatch.setattr(retry_mod, "_sleep", _instant)


@pytest.fixture
def real_sleep():
    """Die ungepatchte ``asyncio.sleep`` für Tests über echte Zeit."""
    return _REAL_SLEEP
