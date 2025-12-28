#!/usr/bin/env python3
# engine/blast.py — CLI sender with pretty, colored, aligned recipient table

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import core

USAGE = (
    "Usage:\n"
    "  fimg -c [-skip] [all|actives|brothers|pledges] to NAME1 NAME2 : MESSAGE\n"
    "  fimg -c [-skip] [all|actives|brothers|pledges] NAME1 NAME2 : MESSAGE\n"
    "  fimg -c [-skip] to NAME1 NAME2 : MESSAGE   # defaults to list = 'all'\n"
)

# -------------------- utils --------------------

def color_enabled() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

def c(code: str) -> str:
    return f"\033[{code}m" if color_enabled() else ""

# palette
BOLD = c("1")
DIM = c("2")
FG_NAME = c("97")      # bright white
FG_NUM = c("36")       # cyan
FG_HEAD = c("95")      # magenta
FG_META = c("90")      # bright black (gray)
RESET = c("0")

def strip_skip_flag(argv):
    skip = False
    cleaned = []
    in_message = False
    for tok in argv:
        if not in_message and tok == "-skip":
            skip = True
            continue
        if not in_message and ":" in tok:
            in_message = True
        cleaned.append(tok)
    return skip, cleaned

# ---------------- pretty printing -------------

def print_header(list_key: str, csv_name: str, n: int):
    h = f"{BOLD}{FG_HEAD}List:{RESET} {BOLD}{list_key}{RESET}  {FG_META}|{RESET}  {FG_HEAD}CSV:{RESET} {csv_name}"
    print(h)
    print(f"{FG_META}Recipients ({n}):{RESET}")

def print_recipients(resolved):
    # compute column widths
    idx_w = len(str(len(resolved)))
    name_w = max(len(c.name) for c in resolved) if resolved else 4
    num_w = max(len(c.number) for c in resolved) if resolved else 10

    # header line
    hdr = f" {'#'.rjust(idx_w)}  {'Name'.ljust(name_w)}  {'Number'.rjust(num_w)} "
    print(f"{FG_META}{hdr}{RESET}")

    # rows
    for i, ctd in enumerate(resolved, 1):
        idx = str(i).rjust(idx_w)
        name = ctd.name.ljust(name_w)
        num = ctd.number.rjust(num_w)
        line = f" {DIM}{idx}{RESET}  {BOLD}{FG_NAME}{name}{RESET}  {FG_NUM}{num}{RESET}"
        print(line)

# -------------------- main --------------------

def confirm():
    try:
        import termios, tty
        sys.stdout.write("\nPress Enter to send; any other key to cancel... ")
        sys.stdout.flush()
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd); ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        print()
        return ch in ("\r", "\n")
    except Exception:
        try: ans = input("\nPress Enter to send; any other key to cancel... ")
        except KeyboardInterrupt: print(); return False
        return ans == ""

def main():
    argv = sys.argv[1:]
    skip_confirm, argv = strip_skip_flag(argv)
    list_key = "all"
    rest = argv
    if argv and argv[0].lower() in core.CSV_MAP:
        list_key = argv[0].lower()
        rest = argv[1:]

    tokens, message = core.parse_targets_message(" ".join(rest))
    if tokens is None or not message:
        print(USAGE); sys.exit(1)

    contacts = core.load_contacts(core.CSV_MAP[list_key])
    message = core.normalize_message(message)
    resolved, missing = core.resolve_tokens(tokens, contacts)

    if not resolved:
        print("No recipients matched.")
        if missing: print("Unmatched:", ", ".join(missing))
        sys.exit(1)

    print_header(list_key, core.CSV_MAP[list_key].name, len(resolved))
    print_recipients(resolved)

    if missing:
        print(f"\n{FG_META}Unmatched (ignored): {', '.join(missing)}{RESET}")

    print(f"\n{FG_HEAD}Message:{RESET}\n")
    print(message)
    print()

    if not skip_confirm and not confirm():
        print("Canceled."); return

    print(f"\nSending {len(resolved)} message(s)...")

    sent = failed = 0
    failures = []
    for c in resolved:
        per = core.personalize(message, c.first)
        print(f"  -> {c.name} ... ", end="", flush=True)
        ok, _detail = core.send_message(c.number, per)
        if ok:
            print("OK"); sent += 1
        else:
            print("FAIL"); failed += 1; failures.append(c.name)
        time.sleep(0.6)

    print(f"\n✅ Done. Sent: {sent}  |  Failed: {failed}")
    if failures:
        print("Failed:", ", ".join(failures))

if __name__ == "__main__":
    main()
