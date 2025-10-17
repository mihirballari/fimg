#!/usr/bin/env sh
# ui/landing.sh — banner centered; vertical menu centered; 'q' to quit

. "$(dirname "$0")/../lib/term.sh"

measure_width() {
  python3 - <<'PY'
import sys
print(max((len(l.rstrip("\n")) for l in sys.stdin), default=0))
PY
}

draw() {
  term_clear
  cols=$(tput cols 2>/dev/null || echo 80)
  rows=$(tput lines 2>/dev/null || echo 24)

  # --- Banner ---
  B="$(cat "$(dirname "$0")/banner.txt")"
  BW=$(printf '%s\n' "$B" | measure_width)
  BH=$(printf '%s\n' "$B" | wc -l | tr -d ' ')
  GAP=3 # space between banner and menu

  top=$(((rows - (BH + GAP + 5)) / 2))
  [ "$top" -gt 0 ] || top=0 # 5 ≈ menu rows
  left=$(((cols - BW) / 2))
  [ "$left" -gt 0 ] || left=0

  # draw banner
  row=$((top + 5))
  printf '%s\n' "$B" | while IFS= read -r line; do
    printf '\033[%s;%sH%s' "$row" $((left + 1)) "$line"
    row=$((row + 1))
  done

  # --- Menu (vertical, centered) ---
  PLAIN="$("$(dirname "$0")/menu.sh" --plain)"
  MW=$(printf '%s\n' "$PLAIN" | measure_width)
  MH=$(printf '%s\n' "$PLAIN" | wc -l | tr -d ' ')

  OFFSET=15
  mleft=$(((cols - MW) / 2 + OFFSET))
  [ "$mleft" -gt 0 ] || mleft=0
  mtop=$((top + BH + GAP))

  r=$((mtop + 1))
  printf '%s\n' "$PLAIN" | while IFS= read -r line; do
    # draw each line at the same centered column; then re-render colored line over it
    printf '\033[%s;%sH%s' "$r" $((mleft + 1)) "$line"
    printf '\033[%s;%sH' "$r" $((mleft + 1))
    "$(dirname "$0")/menu.sh" | sed -n "$((r - mtop))p"
    r=$((r + 1))
  done
}

main() {
  term_save
  draw
  while :; do
    k="$(term_read_key)"
    [ "$k" = "q" ] && break
  done
  term_restore
}

main "$@"
