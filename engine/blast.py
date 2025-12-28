#!/usr/bin/env python3
# engine/blast.py — CLI sender with pretty, colored, aligned recipient table

import csv, sys, re, subprocess, time, os, shlex, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LISTS = ROOT / "lists"
ENGINE = ROOT / "engine"

CSV_MAP = {
    "all":       LISTS / "all.csv",
    "actives":   LISTS / "brothers.csv",
    "brothers":  LISTS / "brothers.csv",
    "pledges":   LISTS / "pledges.csv",
}
AS_PATH = ENGINE / "send_imessage.applescript"

USAGE = (
    "Usage:\n"
    "  fimg -c [-skip] [all|actives|brothers|pledges] to NAME1 NAME2 : MESSAGE\n"
    "  fimg -c [-skip] [all|actives|brothers|pledges] NAME1 NAME2 : MESSAGE\n"
    "  fimg -c [-skip] to NAME1 NAME2 : MESSAGE   # defaults to list = 'all'\n"
)

# -------------------- utils --------------------

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[.,]", " ", s.lower())
    return " ".join(s.split())

def first_name(full: str) -> str:
    n = _norm(full)
    return n.split(" ")[0] if n else ""

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

# -------------------- data ---------------------

def load_contacts(csv_path: Path):
    if not csv_path.exists():
        sys.exit(f"Roster CSV missing: {csv_path}")
    contacts = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("name") or row.get("Name") or "").strip()
            raw  = (row.get("number") or row.get("Number") or row.get("Phone") or "").strip()
            alias_raw = (row.get("alias") or row.get("Alias") or "").strip()
            if not name or not raw:
                continue
            number = re.sub(r"[^\d+]", "", raw)  # keep digits and '+'
            aliases = [a.lower() for a in re.split(r"[,\s;/]+", alias_raw) if a.strip()] if alias_raw else []
            contacts.append({
                "name": name,
                "first": first_name(name),
                "number": number,
                "name_l": _norm(name),
                "aliases": aliases,
            })
    return contacts

def dedup(people):
    out, seen = [], set()
    for c in people:
        if c["number"] not in seen:
            out.append(c); seen.add(c["number"])
    return out

def parse(rest):
    raw = " ".join(rest).strip()
    m = re.match(r'^(?:to\s+)?(.+?)\s*:\s*(.+)$', raw, flags=re.IGNORECASE)
    if not m: return None, None
    names_raw, message = m.group(1).strip(), m.group(2).strip()
    parts = []
    for chunk in re.split(r'\s*,\s*', names_raw):
        if chunk:
            parts.extend(shlex.split(chunk))
    tokens = [t for t in parts if t]
    return tokens, message

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

def resolve(tokens, contacts):
    if any(t.lower() == "all" for t in tokens):
        return dedup(contacts), []
    chosen, missing = [], []
    for tok in tokens:
        t = _norm(tok)
        alias_hits = [c for c in contacts if t in c.get("aliases", [])]
        if alias_hits:
            chosen.append(alias_hits[0]); continue
        hits = [c for c in contacts
                if t in c["name_l"] or any(p.startswith(t) for p in c["name_l"].split())]
        if not hits:
            missing.append(tok)
        else:
            starts = [c for c in hits if any(p.startswith(t) for p in c["name_l"].split())]
            chosen.append((starts or hits)[0])
    return dedup(chosen), missing

def normalize_message(msg: str) -> str:
    msg = (msg.replace('########', '\n\n')
              .replace('####', '\n\n')
              .replace('##', '\n')
              .replace('||||', '\n\n')
              .replace('||', '\n')
              .replace('\\\\n', '\n')
              .replace('\\n', '\n'))
    msg = re.sub(r'\n[ \t]+', '\n', msg)
    return msg

def personalize(template: str, first_lower: str) -> str:
    first_title = first_lower.capitalize()
    msg = re.sub(r'(\[(?:names?)\]|\{(?:names?)\})', first_lower, template, flags=re.IGNORECASE)
    def _n(m): return first_title if m.group(0) == '-N' else first_lower
    msg = re.sub(r'(?<!\S)-[nN](?=$|\s|[.,;:!?])', _n, msg)
    return msg

# ---------------- pretty printing -------------

def print_header(list_key: str, csv_name: str, n: int):
    h = f"{BOLD}{FG_HEAD}List:{RESET} {BOLD}{list_key}{RESET}  {FG_META}|{RESET}  {FG_HEAD}CSV:{RESET} {csv_name}"
    print(h)
    print(f"{FG_META}Recipients ({n}):{RESET}")

def print_recipients(resolved):
    # compute column widths
    idx_w = len(str(len(resolved)))
    name_w = max(len(c["name"]) for c in resolved) if resolved else 4
    num_w = max(len(c["number"]) for c in resolved) if resolved else 10

    # header line
    hdr = f" {'#'.rjust(idx_w)}  {'Name'.ljust(name_w)}  {'Number'.rjust(num_w)} "
    print(f"{FG_META}{hdr}{RESET}")

    # rows
    for i, ctd in enumerate(resolved, 1):
        idx = str(i).rjust(idx_w)
        name = ctd["name"].ljust(name_w)
        num = ctd["number"].rjust(num_w)
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
    if argv and argv[0].lower() in CSV_MAP:
        list_key = argv[0].lower()
        rest = argv[1:]

    tokens, message = parse(rest)
    if tokens is None or not message:
        print(USAGE); sys.exit(1)

    contacts = load_contacts(CSV_MAP[list_key])
    message = normalize_message(message)
    resolved, missing = resolve(tokens, contacts)

    if not resolved:
        print("No recipients matched.")
        if missing: print("Unmatched:", ", ".join(missing))
        sys.exit(1)

    print_header(list_key, CSV_MAP[list_key].name, len(resolved))
    print_recipients(resolved)

    if missing:
        print(f"\n{FG_META}Unmatched (ignored): {', '.join(missing)}{RESET}")

    print(f"\n{FG_HEAD}Message:{RESET}\n")
    print(message)
    print()

    if not skip_confirm and not confirm():
        print("Canceled."); return

    if not AS_PATH.exists():
        sys.exit(f"AppleScript missing: {AS_PATH}")
    print(f"\nSending {len(resolved)} message(s)...")

    sent = failed = 0
    failures = []
    for c in resolved:
        per = personalize(message, c["first"])
        print(f"  -> {c['name']} … ", end="", flush=True)
        proc = subprocess.run(["osascript", str(AS_PATH), c["number"], per],
                              text=True, capture_output=True)
        if proc.returncode == 0:
            print("✔"); sent += 1
        else:
            print("✖"); failed += 1; failures.append(c["name"])
        time.sleep(0.6)

    print(f"\n✅ Done. Sent: {sent}  |  Failed: {failed}")
    if failures:
        print("Failed:", ", ".join(failures))

if __name__ == "__main__":
    main()
