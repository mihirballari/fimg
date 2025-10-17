#!/usr/bin/env sh
# ui/landing.sh — centered banner; fast menu highlight; j/k + Enter; s opens overlay; q quits

. "$(dirname "$0")/../lib/term.sh"

measure_width() {
  python3 - <<'PY'
import sys
print(max((len(l.rstrip("\n")) for l in sys.stdin), default=0))
PY
}

# --- incremental highlight state (0..4 = Send..Quit) ---
HOVER=0
_mleft=0 _mtop=0 _mw=0

# Re-highlight a single menu row without redrawing the page
# $1 = row idx (0..4), $2 = 1 to highlight, 0 to restore colored line
hilite_line() {
  idx="$1"
  on="${2:-0}"
  r=$((_mtop + 1 + idx))
  printf '\033[%s;%sH' "$r" $((_mleft + 1))
  if [ "$on" -eq 1 ]; then
    plain="$("$(dirname "$0")/menu.sh" --plain | sed -n "$((idx + 1))p")"
    printf '\033[7m%-*s\033[0m' "$_mw" "$plain"
  else
    "$(dirname "$0")/menu.sh" | sed -n "$((idx + 1))p"
  fi
}

draw() {
  term_clear
  cols=$(tput cols 2>/dev/null || echo 80)
  rows=$(tput lines 2>/dev/null || echo 24)

  # --- Banner geometry ---
  B="$(cat "$(dirname "$0")/banner.txt")"
  BW=$(printf '%s\n' "$B" | measure_width)
  BH=$(printf '%s\n' "$B" | wc -l | tr -d ' ')
  GAP=3
  top=$(((rows - (BH + GAP + 5)) / 2))
  [ "$top" -gt 0 ] || top=0
  left=$(((cols - BW) / 2))
  [ "$left" -gt 0 ] || left=0

  # draw banner once
  row=$((top + 5))
  printf '%s\n' "$B" | while IFS= read -r line; do
    printf '\033[%s;%sH%s' "$row" $((left + 1)) "$line"
    row=$((row + 1))
  done

  # --- Menu block (remember geometry) ---
  plain="$("$(dirname "$0")/menu.sh" --plain)"
  _mw=$(printf '%s\n' "$plain" | measure_width)
  MH=$(printf '%s\n' "$plain" | wc -l | tr -d ' ')
  OFFSET=15
  _mleft=$(((cols - _mw) / 2 + OFFSET))
  [ "$_mleft" -gt 0 ] || _mleft=0
  _mtop=$((top + BH + GAP))

  # draw colored menu once
  r=$((_mtop + 1))
  "$(dirname "$0")/menu.sh" | while IFS= read -r line; do
    printf '\033[%s;%sH%s' "$r" $((_mleft + 1)) "$line"
    r=$((r + 1))
  done

  # initial highlight
  hilite_line "$HOVER" 1

  # park cursor off-screen
  printf '\033[%s;%sH' "$rows" 1
}

main() {
  term_save
  tput civis 2>/dev/null || true
  trap 'tput cnorm 2>/dev/null || true; term_restore' EXIT

  HOVER=0
  draw

  while :; do
    k="$(term_read_key)"
    case "$k" in
    q)
      printf '\033[2J\033[H'
      break
      ;;

    # vim navigation (incremental highlight only)
    j)
      if [ "$HOVER" -lt 4 ]; then
        hilite_line "$HOVER" 0
        HOVER=$((HOVER + 1))
        hilite_line "$HOVER" 1
      fi
      ;;
    k)
      if [ "$HOVER" -gt 0 ]; then
        hilite_line "$HOVER" 0
        HOVER=$((HOVER - 1))
        hilite_line "$HOVER" 1
      fi
      ;;

    # direct hotkeys
    s)
      hilite_line "$HOVER" 0
      HOVER=0
      hilite_line "$HOVER" 1
      /Users/mihir/fimg/ui/compose_overlay.sh </dev/tty >/dev/tty 2>/dev/null
      draw
      ;;
    d)
      hilite_line "$HOVER" 0
      HOVER=1
      hilite_line "$HOVER" 1
      ;;
    S)
      hilite_line "$HOVER" 0
      HOVER=2
      hilite_line "$HOVER" 1
      ;;
    h)
      hilite_line "$HOVER" 0
      HOVER=3
      hilite_line "$HOVER" 1
      ;;

    # Enter selects the highlighted row
    "$(printf '\r')")
      case "$HOVER" in
      0)
        /Users/mihir/fimg/ui/compose_overlay.sh </dev/tty >/dev/tty 2>/dev/null
        draw
        ;;
      1) : ;; 2) : ;; 3) : ;;
      4)
        printf '\033[2J\033[H'
        break
        ;;
      esac
      ;;
    *) : ;;
    esac
  done
}

main "$@"
