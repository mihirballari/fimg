# lib/layout.sh — center a multi-line block as a single object (unicode-aware width)

block_width() {
  # python counts codepoints; good for these block chars
  python3 - "$@" <<'PY'
import sys
lines=[l.rstrip("\n") for l in sys.stdin]
print(max((len(x) for x in lines), default=0))
PY
}

center_block_draw() {
  block="$1"
  gap="${2:-0}" # extra blank lines appended (already in block normally)
  cols=$(tput cols 2>/dev/null || echo 80)
  rows=$(tput lines 2>/dev/null || echo 24)

  # split into array, measure
  IFS='
' set -f
  set -- $block
  lines_list="$*"
  H=0
  for _ in $lines_list; do H=$((H + 1)); done
  W=$(printf '%s\n' "$block" | block_width)

  L=$(((cols - W) / 2))
  [ "$L" -gt 0 ] || L=0
  T=$(((rows - (H + gap)) / 2))
  [ "$T" -gt 0 ] || T=0

  r=$((T + 1))
  printf '%s\n' "$block" | while IFS= read -r line; do
    printf '\033[%s;%sH%s' "$r" $((L + 1)) "$line"
    r=$((r + 1))
  done
}
