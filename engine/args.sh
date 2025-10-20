# engine/args.sh
# Parses: fimg to <targets> : <message>
# Sets globals: TARGETS_STR, MESSAGE

parse_cli() {
  local raw="${*}"
  raw="${raw#to }" # optional leading "to "

  if printf '%s' "$raw" | grep -q ':'; then
    TARGETS_STR="$(printf '%s' "$raw" | sed 's/[[:space:]]*:[[:space:]]*/:/' | cut -d: -f1)"
    MESSAGE="$(printf '%s' "$raw" | sed 's/[[:space:]]*:[[:space:]]*/:/' | cut -d: -f2-)"
  else
    echo "[fimg] Usage: fimg to <targets> : <message>" >&2
    return 2
  fi

  # trim quotes around targets
  TARGETS_STR="${TARGETS_STR#\"}"
  TARGETS_STR="${TARGETS_STR%\"}"
  TARGETS_STR="${TARGETS_STR#\'}"
  TARGETS_STR="${TARGETS_STR%\'}"

  # decode literal \n into real newlines
  MESSAGE="$(printf '%b' "${MESSAGE//\\n/\\n}")"
}
