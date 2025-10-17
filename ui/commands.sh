#!/usr/bin/env sh
# ui/commands.sh — prints commands; --plain outputs no ANSI for width calc

if [ "${1-}" = "--plain" ]; then
  printf 's (send)   d (draft)   S (schedule)   h (help)   q(uit)'
  exit 0
fi

if tput colors >/dev/null 2>&1; then
  B=$(tput bold)
  R=$(tput sgr0)
  K=$(tput setaf 6)
  L=$(tput setaf 7)
else
  B=''
  R=''
  K=''
  L=''
fi

printf "%s%s%s %s(send)%s   %s%s%s %s(draft)%s   %s%s%s %s(schedule)%s   %s%s%s %s(help)%s   %s%s%s%s(uit)%s" \
  "$B" "$K" s "$L" "$R" \
  "$B" "$K" d "$L" "$R" \
  "$B" "$K" S "$L" "$R" \
  "$B" "$K" h "$L" "$R" \
  "$B" "$K" q "$L" "$R"
