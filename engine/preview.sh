# engine/preview.sh
. "$(dirname "${BASH_SOURCE[0]}")/term.sh"

BOLD="\033[1m"
DIM="\033[2m"
RST="\033[0m"

preview_and_confirm() {
  local message="$1"
  shift
  local recipients=("$@")

  local title="Message preview:"
  local maxw=${#title}
  while IFS= read -r line; do
    [ ${#line} -gt $maxw ] && maxw=${#line}
  done < <(printf '%s\n' "$message")
  maxw=$((maxw + 2))

  local rule
  rule="$(printf '%*s' "$maxw" | tr ' ' '─')"
  printf '\n' # top spacing
  printf '┌%s┐\n' "$rule"
  printf '│ %s%*s│\n' "$title" $((maxw - ${#title} - 1)) ""
  while IFS= read -r line; do
    printf '│ %s%*s│\n' "$line" $((maxw - ${#line} - 1)) ""
  done < <(printf '%s\n' "$message")
  printf '└%s┘\n' "$rule"

  printf '\n'
  printf '%b%s%b\n' "$BOLD" "send to:" "$RST"
  printf '%s\n\n' "$(printf '%s ' "${recipients[@]}")"
  printf '%b%s%b' "$DIM" "Press Enter to send; any other key to cancel..." "$RST"
  local k
  k="$(term_read_key)"
  printf '\n'
  [ "$k" = $'\n' ] || [ "$k" = $'\r' ]
}
