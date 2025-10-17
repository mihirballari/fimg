#!/usr/bin/env sh
# ui/menu.sh — vertical menu like LazyVim (narrow). --plain prints without ANSI for measuring.

# rows: "Label|Hotkey"
ROWS='Send|s
Draft|d
Schedule|S
Help|h
Quit|q'

if [ "${1-}" = "--plain" ]; then
  echo "$ROWS" | awk -F'|' '{ printf "%-10s %s\n", $1, $2 }'
  exit 0
fi

if tput colors >/dev/null 2>&1; then
  B=$(tput bold)
  R=$(tput sgr0)
  K=$(tput setaf 6) # hotkey color
  L=$(tput setaf 7) # label color
else
  B=''
  R=''
  K=''
  L=''
fi

echo "$ROWS" | awk -F'|' -v B="$B" -v R="$R" -v K="$K" -v L="$L" '
{
  # left label padded to 10; tight single space before key
  printf "%s%-10s%s %s%s%s\n", L, $1, R, B K, $2, R
}'
