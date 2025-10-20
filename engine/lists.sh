# engine/lists.sh
# Resolves comma-separated targets using ~/fimg/lists/*.csv
# Produces arrays: RESOLVED_NAMES[], RESOLVED_HANDLES[]

. "$(dirname "${BASH_SOURCE[0]}")/csv.sh"

RESOLVED_NAMES=()
RESOLVED_HANDLES=()

_lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
_trim() { printf '%s' "$1" | sed 's/^[[:space:]]\+//; s/[[:space:]]\+$//'; }

_is_handle() {
  case "$1" in
  *"@"* | *[0-9]*) return 0 ;;
  esac
  return 1
}

declare -gA __NAME_FOR_KEY
declare -gA __HANDLE_FOR_KEY

__collect_row() {
  local name="$1" number="$2" alias="$3"
  [ -n "$name" ] || return
  local lname="$(_lower "$name")"
  local lalias="$(_lower "$alias")"

  __NAME_FOR_KEY["$lname"]="$name"
  __HANDLE_FOR_KEY["$lname"]="$number"

  # also index first/last tokens
  local first="${lname%% *}"
  local last="${lname##* }"
  __NAME_FOR_KEY["$first"]="$name"
  __HANDLE_FOR_KEY["$first"]="$number"
  __NAME_FOR_KEY["$last"]="$name"
  __HANDLE_FOR_KEY["$last"]="$number"

  if [ -n "$lalias" ]; then
    __NAME_FOR_KEY["$lalias"]="$name"
    __HANDLE_FOR_KEY["$lalias"]="$number"
  fi
}

_build_maps() {
  __NAME_FOR_KEY=()
  __HANDLE_FOR_KEY=()
  local dir="${FIMG_LISTS_DIR:-$HOME/fimg/lists}"
  [ -d "$dir" ] || return 0
  for f in "$dir"/*.csv; do
    [ -e "$f" ] || continue
    csv_each_row "$f" __collect_row
  done
}

resolve_targets_from_lists() {
  local input="$1"
  RESOLVED_NAMES=()
  RESOLVED_HANDLES=()
  _build_maps

  IFS=',' read -r -a items <<<"$input"
  declare -A seen=()
  for raw in "${items[@]}"; do
    local item="$(_trim "$raw")"
    [ -n "$item" ] || continue

    local name handle key="$(_lower "$item")"

    if _is_handle "$item"; then
      name="$item"
      handle="$item"
    else
      if [ -n "${__NAME_FOR_KEY[$key]:-}" ]; then
        name="${__NAME_FOR_KEY[$key]}"
        handle="${__HANDLE_FOR_KEY[$key]}"
      else
        # substring fallback (matches parts of full name or alias already indexed)
        for k in "${!__NAME_FOR_KEY[@]}"; do
          if [[ "$k" == *"$key"* ]]; then
            name="${__NAME_FOR_KEY[$k]}"
            handle="${__HANDLE_FOR_KEY[$k]}"
            break
          fi
        done
      fi
      [ -n "$name" ] || name="$item"
      [ -n "$handle" ] || handle="$item"
    fi

    local hkey="$(_lower "$handle")"
    [ -n "${seen[$hkey]:-}" ] && continue
    seen[$hkey]=1
    RESOLVED_NAMES+=("$name")
    RESOLVED_HANDLES+=("$handle")
  done
}
