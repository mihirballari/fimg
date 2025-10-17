#!/usr/bin/env sh
# ui/compose_overlay.sh — centered floating overlay window (no alt-screen)
# Esc closes; :q closes; :w accepts (exit 0). Cleans up (erases box) on exit.

set -eu

# --- tiny tty helpers (no alternate screen) ---
save() {
  STTY_OLD=$(stty -g)
  tput civis
  stty -echo -icanon time 0 min 1
}
rest() {
  stty "$STTY_OLD" 2>/dev/null || true
  tput cnorm
}
goto() { printf '\033[%s;%sH' "$1" "$2"; }
read1() { dd bs=1 count=1 2>/dev/null </dev/tty || true; }

# globals for geometry
W=0 H=0 L=0 T=0

compute_geom() {
  cols=$(tput cols 2>/dev/null || echo 80)
  rows=$(tput lines 2>/dev/null || echo 24)
  W=$((cols * 3 / 5))
  [ "$W" -lt 60 ] && W=60
  [ "$W" -gt $((cols - 4)) ] && W=$((cols - 4))
  H=$((rows * 2 / 5))
  [ "$H" -lt 12 ] && H=12
  [ "$H" -gt $((rows - 4)) ] && H=$((rows - 4))
  L=$(((cols - W) / 2))
  T=$(((rows - H) / 2))
}

erase_box() {
  compute_geom
  # erase border area and shadow by painting spaces
  r=$T
  while [ $r -le $((T + H)) ]; do
    goto "$r" "$L"
    printf "%*s" "$((W + 1))" "" # +1 covers right border
    r=$((r + 1))
  done
  # erase bottom shadow line
  goto $((T + H)) $((L + 1))
  printf "%*s" "$W" ""
}

draw_box() {
  compute_geom

  # subtle shadow (gray)
  if tput setaf 8 >/dev/null 2>&1; then
    SH="$(tput setaf 8)"
    NC="$(tput sgr0)"
    r=$((T + 1))
    while [ $r -le $((T + H)) ]; do
      goto "$r" $((L + W))
      printf "%s " "$SH"
      r=$((r + 1))
    done
    goto $((T + H)) $((L + 1))
    printf "%s%*s%s" "$SH" "$W" "" "$NC"
  fi

  # border (box-drawing)
  tl="┌"
  tr="┐"
  bl="└"
  br="┘"
  hz="─"
  vt="│"
  goto "$T" "$L"
  printf "%s%s%s" "$tl" "$(printf "%*s" $((W - 2)) "" | tr ' ' "$hz")" "$tr"
  r=$((T + 1))
  while [ $r -lt $((T + H - 1)) ]; do
    goto "$r" "$L"
    printf "%s%*s%s" "$vt" $((W - 2)) "" "$vt"
    r=$((r + 1))
  done
  goto "$r" "$L"
  printf "%s%s%s" "$bl" "$(printf "%*s" $((W - 2)) "" | tr ' ' "$hz")" "$br"

  # title
  title=" Compose  —  :w accept   :q cancel   (Esc closes) "
  goto "$T" $((L + (W - ${#title}) / 2))
  printf "%s" "$title"

  # footer hint
  goto $((T + H - 1)) $((L + 2))
  printf "Type here…"
}

main() {
  save
  # ensure cleanup always erases the window and restores tty
  trap 'erase_box; rest' EXIT

  draw_box
  MODE="INSERT"
  CMD=""

  while :; do
    k="$(read1)"
    case "$k" in
    "$(printf '\e')") exit 1 ;; # Esc closes overlay
    :)
      MODE="CMD"
      CMD=""
      ;;                     # enter command mode
    "$(printf '\r')") : ;;   # ignore Enter (window-only preview)
    "$(printf '\x7f')") : ;; # ignore Backspace here
    *) [ "$MODE" = "CMD" ] && CMD="$CMD$k" ;;
    esac

    # handle :w / :q on Enter
    if [ "$MODE" = "CMD" ] && [ "$k" = "$(printf '\r')" ]; then
      [ "$CMD" = "q" ] && exit 1
      [ "$CMD" = "w" ] && exit 0
      MODE="INSERT"
    fi
  done
}
main "$@"
