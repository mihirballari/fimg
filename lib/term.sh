# lib/term.sh — tiny TTY helpers (POSIX sh)

term_save() {
  STTY_OLD=$(stty -g)
  tput smcup 2>/dev/null || printf '\033[?1049h'
  tput civis
  stty -echo -icanon time 0 min 1
}
term_restore() {
  stty "$STTY_OLD" 2>/dev/null || true
  tput cnorm
  tput rmcup 2>/dev/null || printf '\033[?1049l'
}

term_clear() { tput clear 2>/dev/null || printf '\033[2J\033[H'; }

term_size() {
  C=$(tput cols 2>/dev/null || echo 80)
  R=$(tput lines 2>/dev/null || echo 24)
}

# Move to row,col (1-based)
term_goto() { printf '\033[%s;%sH' "$1" "$2"; }

# Read one key from /dev/tty (works in sh)
term_read_key() { dd bs=1 count=1 2>/dev/null </dev/tty; }
