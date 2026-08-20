# SessionStart-Hook: Klon-Aktualität

`check-clone-freshness.sh` meldet beim Sessionstart, wie viele Commits der
ausgecheckte Stand hinter `<remote>/<default-branch>` liegt. Registriert in
[`../settings.json`](../settings.json).

## Grund

Ein veralteter Klon hat am 3.8.2026 **zweimal** eine rote CI erzeugt, deren
Ursache nicht im Diff stand — die fehlenden Commits waren jeweils genau die,
die das Gate einführten, an dem der Branch scheiterte. Man sucht den Fehler
dann in den geänderten Dateien, wo er nicht ist. Die Prüfung kostet eine
Sekunde und ersetzt eine Fehlersuche in den falschen Dateien.

Sie ist die ausführbare Fassung des Abschnitts «Vor der Arbeit» in
[`CLAUDE.md`](../../CLAUDE.md).

## Verhalten

| Situation | Verhalten |
|---|---|
| Stand ist aktuell (0 Commits fehlen) | **schweigt** |
| Commits fehlen | eine Meldung mit Anzahl und `git`-Befehl zum Nachziehen |
| Kein Netz, DNS flattert, Remote nicht erreichbar | still durch, Exit 0 |
| Kein Remote konfiguriert | still durch, Exit 0 |
| Detached HEAD | still durch, Exit 0 |
| Default-Branch nicht ermittelbar | still durch, Exit 0 |
| Kein Git-Repo / kein `git` im `PATH` | still durch, Exit 0 |

**Der Hook blockiert die Session unter keinen Umständen.** Ein Hook, der bei
Netzproblemen die Arbeit anhält, wird nach dem zweiten Mal abgeschaltet und
schützt danach gar nichts. Deshalb:

- kein `set -e`, dafür `trap 'exit 0' EXIT` — auch ein unvorhergesehener
  Fehler endet mit Exit 0;
- jeder Netzaufruf hart gedeckelt (Default 5 s, `timeout` bzw. portabler
  Fallback per Hintergrundprozess, falls `timeout` fehlt — auf macOS ohne
  coreutils ist es nicht da);
- `GIT_TERMINAL_PROMPT=0` und No-op-Askpass: eine Passwort- oder
  Host-Key-Abfrage wäre genau das Hängen, das ausgeschlossen sein soll.
  Konfigurierte Credential-Helper bleiben aktiv (nicht interaktiv), sonst
  könnte bei privaten Remotes gar nichts geprüft werden;
- zusätzlich `"timeout": 20` in `settings.json` als Netz darunter.

## Default-Branch wird ermittelt, nicht angenommen

Drei Server im Portfolio (`openlex-mcp`, `swiss-courts-mcp`, `swisstopo-mcp`)
nennen ihren Default-Branch `master`. Fest verdrahtetes `main` scheitert dort
mit «couldn't find remote ref main» — und genau diese Annahme hat schon einmal
einen Branch 15 Commits alt werden lassen.

Ermittlung in dieser Reihenfolge:

1. `git ls-remote --symref <remote> HEAD` — autoritativ, fragt die Quelle;
2. `refs/remotes/<remote>/HEAD` — lokal beim Klonen gesetzt, kein Netz nötig;
3. sonst **abbrechen ohne Ausgabe**. Es wird nicht geraten: ein falsch
   geratener Branch meldet entweder Unsinn oder gar nichts.

## Shallow Clones

Claude Code auf dem Web klont flach. `git rev-list --count HEAD..FETCH_HEAD`
kann dann nur **unter**zählen, nie übertreiben — ein Fehlalarm ist damit
ausgeschlossen. Ist der Klon flach, sagt die Meldung «mindestens so viele».

## Stellschrauben

| Variable | Default | Wirkung |
|---|---|---|
| `CLONE_FRESHNESS_SKIP=1` | – | Prüfung ganz überspringen |
| `CLONE_FRESHNESS_TIMEOUT` | `5` | Sekunden pro Netzaufruf |
| `CLONE_FRESHNESS_REMOTE` | `origin`, sonst erster Remote | Remote-Name |

Der Hook läuft in lokalen wie in Web-Sessions — ein veralteter Klon kostet
überall dieselbe Fehlersuche. Auf `$CLAUDE_CODE_REMOTE` wird deshalb bewusst
nicht eingeschränkt.

## Von Hand testen

```bash
./.claude/hooks/check-clone-freshness.sh; echo "exit=$?"   # aktuell -> keine Ausgabe, exit=0

# Meldepfad erzwingen (Wegwerf-Klon, Original bleibt unberührt):
git clone . /tmp/stale && git -C /tmp/stale reset --hard HEAD~3
CLAUDE_PROJECT_DIR=/tmp/stale CLONE_FRESHNESS_REMOTE=origin \
  ./.claude/hooks/check-clone-freshness.sh
```
