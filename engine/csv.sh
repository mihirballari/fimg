# engine/csv.sh
# Reads CSV rows (name,number,alias) and calls: cb name number alias
csv_each_row() {
  local file="$1" cb="$2"
  [ -f "$file" ] || return 0
  awk -F',' '
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*$/ { next }
    {
      name=$1; number=$2; alias=$3
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", name)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", number)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", alias)
      print name "," number "," alias
    }' "$file" | while IFS=',' read -r _n _p _a; do
    "$cb" "$_n" "$_p" "$_a"
  done
}
