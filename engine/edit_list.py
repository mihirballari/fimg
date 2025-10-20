#!/usr/bin/env python3
# engine/edit_list.py — roster editor used by: fimg -e r [list] | fimg -e a [list]
# CSV schema: name,number,alias

import sys, csv, re, os, unicodedata, readline
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# ---------- colors ----------
def _color_on() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
def C(code: str) -> str:
    return f"\033[{code}m" if _color_on() else ""

BOLD, DIM = C("1"), C("2")
HDR, META, OK, WARN, ERR = C("95"), C("90"), C("32"), C("33"), C("31")
NAME, NUM, RST = C("97"), C("36"), C("0")

# ---------- key helpers ----------
def _read_single_key(prompt: str) -> str:
    import termios, tty
    sys.stdout.write(prompt); sys.stdout.flush()
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    sys.stdout.write("\n"); sys.stdout.flush()
    return ch
def confirm_enter_else_cancel(prompt: str) -> bool:
    return _read_single_key(prompt) in ("\r", "\n")

# ---------- paths & list resolution ----------
def _pick_one_key(max_n: int, prompt: str) -> Optional[int]:
    """
    If max_n <= 9, read a single key (1..max_n) without Enter.
    Otherwise fall back to full-line input so you can type multi-digit.
    Returns 1-based index or None if canceled/invalid.
    """
    if max_n <= 9:
        ch = _read_single_key(prompt)
        if ch.isdigit():
            i = int(ch)
            return i if 1 <= i <= max_n else None
        if ch.lower() == 'q':
            return None
        return None
    else:
        try:
            s = input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            return None
        if s.lower() == 'q' or not s.isdigit():
            return None
        i = int(s)
        return i if 1 <= i <= max_n else None


ROOT  = Path(__file__).resolve().parents[1]
LISTS = ROOT / "lists"

def resolve_csv(arg: str) -> Path:
    key = (arg or "").lower()
    if key in {"pledges", "brothers", "actives", "all"}:
        file_key = "brothers" if key in {"brothers", "actives"} else key
        return (LISTS / f"{file_key}.csv").resolve()
    p = Path(arg).expanduser()
    if p.suffix == "": p = p.with_suffix(".csv")
    return p.resolve()

def list_choices() -> List[Path]:
    LISTS.mkdir(parents=True, exist_ok=True)
    return sorted(LISTS.glob("*.csv"))

def pick_from(paths: List[Path], title: str) -> Optional[Path]:
    if not paths:
        print(f"{WARN}No lists found.{RST}")
        return None

    print(f"{HDR}{title}{RST}")
    for i, p in enumerate(paths, 1):
        print(f" {DIM}{i:>2}{RST}) {p.stem}  {META}({p.name}){RST}")

    # Single-key when there are ≤9 choices; 'q' cancels
    max_n = len(paths)
    idx = _pick_one_key(max_n, f"{BOLD}Choose [1-{max_n}]:{RST} ")
    if idx is None:
        print("Canceled.")
        return None

    return paths[idx - 1]

# ---------- util & IO ----------
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[.,]", " ", s.lower())
    return " ".join(s.split())

def _initials(name_norm: str) -> str:
    parts = [p for p in name_norm.split() if p]
    return "".join(p[0] for p in parts)

def load_contacts(csv_path: Path) -> List[Dict]:
    if not csv_path.exists(): return []
    out = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("name") or row.get("Name") or "").strip()
            raw  = (row.get("number") or row.get("Number") or row.get("Phone") or "").strip()
            alias_raw = (row.get("alias") or row.get("Alias") or "").strip()
            if not name or not raw: continue
            number = re.sub(r"[^\d+]", "", raw)
            name_l = _norm(name)
            out.append({
                "name": name,
                "number": number,
                "alias": alias_raw,
                "name_l": name_l,
                "first_l": name_l.split()[0] if name_l else "",
                "last_l":  name_l.split()[-1] if name_l else "",
                "inits":   _initials(name_l),
                "aliases": [a.lower() for a in re.split(r"[,\s;/]+", alias_raw) if a.strip()] if alias_raw else [],
            })
    return out

def write_csv_no_backup(csv_path: Path, rows: List[Dict]):
    tmp = csv_path.with_suffix(csv_path.suffix + ".tmp")
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name","number","alias"])
        w.writeheader()
        for r in sorted(rows, key=lambda r: r["name"].lower()):
            w.writerow({"name": r["name"], "number": r["number"], "alias": r.get("alias","")})
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, csv_path)

# ---------- pretty print ----------
def print_header(title_left: str, csv_name: str):
    print(f"{HDR}List:{RST} {title_left}  {META}|{RST}  {HDR}CSV:{RST} {csv_name}")

def print_table(rows: List[Dict], caption: str):
    print(f"{META}{caption}{RST}")
    if not rows:
        print(f"{META}(none){RST}")
        return
    idx_w = len(str(len(rows)))
    name_w = max(len(r["name"]) for r in rows)
    num_w  = max(len(r["number"]) for r in rows)
    print(f"{META} {'#'.rjust(idx_w)}  {'Name'.ljust(name_w)}  {'Number'.rjust(num_w)} {RST}")
    for i, r in enumerate(rows, 1):
        idx  = str(i).rjust(idx_w)
        name = r["name"].ljust(name_w)
        num  = r["number"].rjust(num_w)
        print(f" {DIM}{idx}{RST}  {BOLD}{NAME}{name}{RST}  {NUM}{num}{RST}")

# ---------- matching ----------
def score_match(tok: str, c: Dict) -> Tuple[int,int]:
    t = _norm(tok)
    if not t: return (-1, 0)
    if t in c["aliases"]:                              return (100, len(c["name"]))
    if t == c["name_l"]:                               return (95, len(c["name"]))
    if t == c["first_l"] or t == c["last_l"]:          return (90, len(c["name"]))
    if len(t) <= 3 and t == c["inits"]:                return (85, len(c["name"]))
    if any(p.startswith(t) for p in c["name_l"].split()): return (70, len(c["name"]))
    if t in c["name_l"]:                               return (50, len(c["name"]))
    return (-1, 0)

def resolve_tokens(tokens: List[str], people: List[Dict]) -> Tuple[List[Dict], List[str]]:
    chosen, missing = [], []
    seen_numbers = set()
    for tok in tokens:
        best, best_sc = None, (-1, 0)
        for c in people:
            sc = score_match(tok, c)
            if sc > best_sc:
                best_sc, best = sc, c
        if best_sc[0] < 0:
            missing.append(tok)
        else:
            if best["number"] not in seen_numbers:
                seen_numbers.add(best["number"])
                chosen.append(best)
    return chosen, missing

# ---------- readline autocomplete ----------
def setup_readline(people: List[Dict]):
    try:
        cands = []
        for r in people:
            cands.append(r["name"]); cands.extend(r["aliases"])
        cands = sorted(set(cands), key=str.lower)
        class NameCompleter:
            def __init__(self, c): self.c=c
            def complete(self, text, state):
                buf = readline.get_line_buffer()
                parts = re.split(r"[,\s]+", buf.rstrip())
                pref = parts[-1] if parts else ""
                m = [x for x in self.c if x.lower().startswith(pref.lower())]
                try: return m[state]
                except IndexError: return None
        readline.set_completer_delims(" \t\n")
        readline.set_completer(NameCompleter(cands).complete)
        doc = getattr(readline, "__doc__", "") or ""
        if "libedit" in doc: readline.parse_and_bind("bind ^I rl_complete")
        else:                readline.parse_and_bind("tab: complete")
    except Exception:
        pass

# ---------- add/remove actions ----------
def action_remove(csv_path: Path):
    people = load_contacts(csv_path)
    print_header(csv_path.stem, csv_path.name)
    if not people:
        print(f"{ERR}List is empty; nothing to remove.{RST}"); return

    setup_readline(people)
    print(); print(f"{HDR}Removing{RST} Names\n")
    try:
        line = input(f"{BOLD}Name(s):{RST} ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nCanceled."); return
    tokens = [t for t in re.split(r"[,\s]+", line) if t]
    if not tokens: print("No names entered. Canceled."); return

    all_requested = any(_norm(t) == "all" for t in tokens)
    if all_requested:
        chosen, missing = people[:], [t for t in tokens if _norm(t) != "all"]
    else:
        chosen, missing = resolve_tokens(tokens, people)
    if missing: print(f"{WARN}Unmatched:{RST} " + ", ".join(missing))

    print(); print_table(chosen, caption=f"Recipients to remove ({len(chosen)}):"); print()
    if not confirm_enter_else_cancel(f"{WARN}Press Enter to remove{RST}, or any other key to cancel: "):
        print("Canceled."); return

    n = len(chosen)
    print(f"{WARN}removing {n} person..{RST}")
    for r in chosen: print(f"  -> {r['name']}")

    if all_requested:
        ch = _read_single_key(f"{WARN}Delete file {csv_path.name} too? (y/N): ")
        if ch in ("y","Y"):
            try: os.remove(csv_path)
            except FileNotFoundError: pass
            print(f"{OK}removed {n} | 0 left in {csv_path.name}{RST}")
            return
        write_csv_no_backup(csv_path, [])
        print(f"{OK}removed {n} | 0 left in {csv_path.name}{RST}")
        return

    nums = {c["number"] for c in chosen}
    remaining = [r for r in people if r["number"] not in nums]
    write_csv_no_backup(csv_path, remaining)
    print(f"{OK}removed {n} | {len(remaining)} left in {csv_path.name}{RST}")

def _prompt_one_person(i: int) -> Optional[Dict]:
    try:
        name = input(f"{BOLD}[{i}] Name:{RST} ").strip()
        if not name: return None
        number = input(f"{BOLD}[{i}] Number (+15551234567 or digits):{RST} ").strip()
        number = re.sub(r"[^\d+]", "", number)
        alias  = input(f"{BOLD}[{i}] Alias(es) [optional, comma-separated]:{RST} ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nCanceled."); return None
    if not number: print(f"{ERR}Number is required; entry skipped.{RST}"); return None
    return {"name": name, "number": number, "alias": alias}

def action_add(csv_path: Path):
    people = load_contacts(csv_path)
    print_header(csv_path.stem, csv_path.name)
    print(); print(f"{HDR}Add entry{RST}")

    # Ask how many to add; default 1 on blank
    try:
        cnt_raw = input(f"{BOLD}# people to add [default 1]:{RST} ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nCanceled."); return
    count = 1 if cnt_raw == "" else (int(cnt_raw) if cnt_raw.isdigit() and int(cnt_raw) > 0 else 1)

    staged: List[Dict] = []
    for i in range(1, count+1):
        ent = _prompt_one_person(i)
        if ent:
            # check duplicate number vs existing and staged
            if any(p["number"] == ent["number"] for p in people) or any(s["number"] == ent["number"] for s in staged):
                print(f"{WARN}That number already exists; skipped.{RST}")
            else:
                staged.append(ent)

    if not staged:
        print("No valid entries. Canceled."); return

    print()
    print_table(staged, caption=f"Entries to add ({len(staged)}):")
    if not confirm_enter_else_cancel(f"{OK}Press Enter to save{RST}, or any other key to cancel: "):
        print("Canceled."); return

    print(f"{OK}adding {len(staged)} person..{RST}")
    for s in staged: print(f"  -> {s['name']}")

    # commit
    for s in staged:
        people.append({
            "name": s["name"], "number": s["number"], "alias": s["alias"],
            "name_l": _norm(s["name"]),
            "first_l": _norm(s["name"]).split()[0] if s["name"] else "",
            "last_l":  _norm(s["name"]).split()[-1] if s["name"] else "",
            "inits":   "".join(w[0] for w in _norm(s["name"]).split() if w),
            "aliases": [a for a in re.split(r"[,\s;/]+", s["alias"]) if a],
        })
    write_csv_no_backup(csv_path, people)
    print(f"{OK}added {len(staged)} | {len(people)} left in {csv_path.name}{RST}")

# ---------- menus when list not provided ----------
def menu_add() -> Optional[Path]:
    print(f"{HDR}Add to{RST}")
    print(" 1) Existing list")
    print(" 2) Create new list")
    print(" q) Quit")
    ch = _read_single_key(f"{BOLD}Choose:{RST} ").lower()  # <-- single key
    if ch == "1":
        return pick_from(list_choices(), "Choose list")
    if ch == "2":
        name = input(f"{BOLD}New list name (no extension):{RST} ").strip()
        if not name:
            print("Canceled."); return None
        p = LISTS / f"{name}.csv"
        if not p.exists():
            write_csv_no_backup(p, [])
        else:
            print(f"{WARN}List already exists; using it.{RST}")
        return p
    print("Canceled."); return None

def menu_remove() -> Optional[Path]:
    print(f"{HDR}Remove from{RST}")
    print(" 1) Existing list")
    print(" 2) Delete existing list")
    print(" q) Quit")
    ch = _read_single_key(f"{BOLD}Choose:{RST} ").lower()  # <-- single key
    if ch == "1":
        return pick_from(list_choices(), "Choose list")
    if ch == "2":
        p = pick_from(list_choices(), "Delete which list")
        if not p:
            return None
        k = _read_single_key(f"{WARN}Delete file {p.name}? (y/N): ")
        if k in ("y", "Y"):
            try:
                os.remove(p)
            except FileNotFoundError:
                pass
            print(f"{OK}deleted {p.name}{RST}")
        else:
            print("Canceled delete.")
        return None
    print("Canceled."); return None

# ---------- CLI ----------
def main():
    argv = sys.argv[1:]
    if not argv or argv[0] not in ("r","a"):
        print("Usage: edit_list.py r|a [<list-or-path>]"); sys.exit(1)

    mode = argv[0]
    csv_path: Optional[Path] = None

    if len(argv) >= 2:
        csv_path = resolve_csv(argv[1])
    else:
        if mode == "a":
            csv_path = menu_add()
        elif mode == "r":
            csv_path = menu_remove()
        else:
            csv_path = None
        if csv_path is None:
            return

    if mode == "r":
        action_remove(csv_path)
    else:
        action_add(csv_path)

if __name__ == "__main__":
    main()

