# lib/center.sh — normalize and measure

# Strip common leading spaces from a multi-line block.
center_normalize() {
  awk '
    {buf[NR]=$0; if($0 ~ /[^[:space:]]/){ match($0,/^[[:space:]]*/); l=RLENGTH; if(min==0 || l<min) min=l; }}
    END{ if(min=="") min=0; for(i=1;i<=NR;i++){ s=buf[i]; if(length(s)>min) print substr(s,min+1); else print "" } }
  '
}

# Max char width of stdin (unicode safe via python3; falls back to awk)
center_width() {
  if command -v python3 >/dev/null 2>&1; then
    python3 - <<'PY'
import sys
lines=[l.rstrip("\n") for l in sys.stdin]
print(max((len(x) for x in lines), default=0))
PY
  else
    awk 'length>m{m=length}END{print m+0}'
  fi
}
