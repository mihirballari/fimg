# engine/term.sh
term_read_key() {
  stty -echo -icanon time 0 min 1 2>/dev/null
  dd bs=1 count=1 2>/dev/null
  stty sane 2>/dev/null
}
