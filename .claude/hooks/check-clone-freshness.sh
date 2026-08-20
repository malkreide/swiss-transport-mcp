#!/usr/bin/env bash
#
# SessionStart-Hook: meldet, wie viele Commits der ausgecheckte Stand hinter
# origin/<default-branch> liegt.
#
# GRUND
#   Ein veralteter Klon hat am 3.8.2026 zweimal eine rote CI erzeugt, deren
#   Ursache nicht im Diff stand — die fehlenden Commits waren jeweils genau
#   die, die das Gate einfuehrten, an dem der Branch scheiterte. Die Pruefung
#   kostet eine Sekunde und ersetzt eine Fehlersuche in den falschen Dateien.
#
# OBERSTE REGEL: Dieser Hook blockiert die Session NIEMALS.
#   Kein Netz, kein Remote, detached HEAD, flatterndes DNS, kein git —
#   jeder dieser Faelle geht still durch (Exit 0, keine Ausgabe). Ein Hook,
#   der bei Netzproblemen die Arbeit anhaelt, wird nach dem zweiten Mal
#   abgeschaltet und schuetzt danach gar nichts.
#
# Ausgabe nur, wenn tatsaechlich Commits fehlen. Bei 0 schweigt er.
#
# Stellschrauben (Environment):
#   CLONE_FRESHNESS_REMOTE    Remote-Name          (Default: origin, sonst erster Remote)
#   CLONE_FRESHNESS_TIMEOUT   Sekunden pro Netzaufruf (Default: 5)
#   CLONE_FRESHNESS_SKIP=1    Pruefung ganz ueberspringen

# Absichtlich KEIN `set -e` und KEIN `set -o pipefail`: jeder Fehlschlag soll
# hier still enden, nicht die Session abbrechen. `trap` erzwingt Exit 0 auch
# bei einem Fehler, den wir nicht vorhergesehen haben.
set -u
trap 'exit 0' EXIT

[ "${CLONE_FRESHNESS_SKIP:-0}" = "1" ] && exit 0

TIMEOUT_SECS="${CLONE_FRESHNESS_TIMEOUT:-5}"
case "$TIMEOUT_SECS" in
  ''|*[!0-9]*) TIMEOUT_SECS=5 ;;
esac

# --- Netzaufrufe hart deckeln ------------------------------------------------
# `timeout` ist auf Linux da, auf macOS ohne coreutils nicht. Ohne ein hartes
# Limit darf kein Netzaufruf starten, sonst haengt genau das, was dieser Hook
# verhindern soll — deshalb der portable Fallback per Hintergrundprozess.
TIMEOUT_BIN="$(command -v timeout 2>/dev/null || command -v gtimeout 2>/dev/null || true)"

run_limited() {
  local secs="$1"; shift
  if [ -n "$TIMEOUT_BIN" ]; then
    "$TIMEOUT_BIN" -k 1 "$secs" "$@"
    return $?
  fi
  "$@" &
  local pid=$! waited=0
  while kill -0 "$pid" 2>/dev/null; do
    if [ "$waited" -ge "$secs" ]; then
      kill -TERM "$pid" 2>/dev/null
      sleep 1
      kill -KILL "$pid" 2>/dev/null
      wait "$pid" 2>/dev/null
      return 124
    fi
    sleep 1
    waited=$((waited + 1))
  done
  wait "$pid"
  return $?
}

# Nie interaktiv nachfragen: eine Passwort- oder Host-Key-Abfrage waere genau
# das Haengen, das hier ausgeschlossen ist. Konfigurierte Credential-Helper
# bleiben absichtlich aktiv — die sind nicht interaktiv, und ohne sie koennte
# der Hook bei privaten Remotes gar nichts pruefen.
git_net() {
  GIT_TERMINAL_PROMPT=0 \
  GIT_ASKPASS=true \
  SSH_ASKPASS=true \
  SSH_ASKPASS_REQUIRE=never \
  GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=${TIMEOUT_SECS} -o StrictHostKeyChecking=accept-new" \
  run_limited "$TIMEOUT_SECS" git "$@"
}

# --- Vorbedingungen, alle still ----------------------------------------------
command -v git >/dev/null 2>&1 || exit 0

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# Detached HEAD: ein bewusst ausgecheckter Tag oder ein bisect ist nicht
# "veraltet". Still durchlassen statt Rauschen erzeugen.
git symbolic-ref --quiet HEAD >/dev/null 2>&1 || exit 0

REMOTE="${CLONE_FRESHNESS_REMOTE:-}"
if [ -z "$REMOTE" ]; then
  if git config --get remote.origin.url >/dev/null 2>&1; then
    REMOTE="origin"
  else
    REMOTE="$(git remote 2>/dev/null | head -n 1)"
  fi
fi
[ -n "$REMOTE" ] || exit 0   # kein Remote -> nichts zu vergleichen

# --- Default-Branch ermitteln, NICHT "main" annehmen -------------------------
# Mindestens ein Repo im Portfolio nutzt "master"; genau diese Annahme hat
# schon einmal einen Branch 15 Commits alt werden lassen. Erst die Quelle
# fragen (autoritativ), dann das lokal beim Klonen gesetzte <remote>/HEAD.
DEFAULT_BRANCH="$(
  git_net ls-remote --symref "$REMOTE" HEAD 2>/dev/null \
    | sed -n 's|^ref: refs/heads/\([^[:space:]]*\).*|\1|p' | head -n 1
)"

if [ -z "$DEFAULT_BRANCH" ]; then
  DEFAULT_BRANCH="$(
    git symbolic-ref --quiet "refs/remotes/${REMOTE}/HEAD" 2>/dev/null \
      | sed -n -e "s|^refs/remotes/${REMOTE}/||p" -e "s|^refs/heads/||p"
  )"
fi

# Immer noch leer heisst: nicht ermittelbar. Dann wird nicht geraten — ein
# falsch geratener Branch meldet entweder Unsinn oder gar nichts.
[ -n "$DEFAULT_BRANCH" ] || exit 0

# --- Abstand messen ----------------------------------------------------------
git_net fetch --quiet --no-tags "$REMOTE" "$DEFAULT_BRANCH" >/dev/null 2>&1 || exit 0

BEHIND="$(git rev-list --count HEAD..FETCH_HEAD 2>/dev/null)"
case "${BEHIND:-}" in
  ''|*[!0-9]*) exit 0 ;;
  0)           exit 0 ;;   # aktuell -> schweigen
esac

BRANCH="$(git symbolic-ref --short --quiet HEAD 2>/dev/null || echo '?')"
COMMIT_WORD="Commits"; [ "$BEHIND" = "1" ] && COMMIT_WORD="Commit"

# In einem shallow Klon kann der Zaehler nur untertreiben, nie uebertreiben —
# ein Fehlalarm ist damit ausgeschlossen.
SHALLOW_NOTE=""
if [ "$(git rev-parse --is-shallow-repository 2>/dev/null)" = "true" ]; then
  SHALLOW_NOTE=" (shallow Klon: mindestens so viele)"
fi

cat <<MSG
Klon-Aktualitaet: '${BRANCH}' liegt ${BEHIND} ${COMMIT_WORD} hinter ${REMOTE}/${DEFAULT_BRANCH}${SHALLOW_NOTE}.

  Aktualisieren vor der Arbeit:
    git fetch ${REMOTE} ${DEFAULT_BRANCH} && git merge FETCH_HEAD

  Grund: Ein veralteter Klon erzeugt eine rote CI, deren Ursache nicht im Diff
  steht — am 3.8.2026 zweimal passiert, beide Male fehlten genau die Commits,
  die das Gate einfuehrten, an dem der Branch scheiterte.
MSG

exit 0
