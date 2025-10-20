#!/usr/bin/env python3
import csv, os, sys, subprocess, termios, tty, time, threading

LISTS_DIR = os.environ.get("FIMG_LISTS_DIR", os.path.expanduser("~/fimg/lists"))
AS_PATH   = os.path.expanduser("~/fimg/engine/send_imessage.applescript")

# --- ANSI styles ---
RST   = "\033[0m"
BOLD  = "\033[1m"
DIM   = "\033[2m"
GREEN = "\033[32m"
RED   = "\033[31m"
BLUE  = "\033[34m"

CHECK = "✔"
CROSS = "✖"
SPIN  = list("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")

def read_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch

def parse_cli(argv):
    if len(argv) < 2:
        raise SystemExit("Usage: test_send.py to <targets> : <message>")
    raw = " ".join(argv[1:])
    # accept "to bay : yo" or "to bay: yo"
    if raw.startswith("to "):
        raw = raw[3:]
    if ":" not in raw:
        raise SystemExit("Usage: test_send.py to <targets> : <message>")
    # normalize single colon split (with or without spaces around)
    parts = raw.split(":", 1)
    targets = parts[0].strip().strip('"').strip("'")
    message = parts[1].strip().replace("\\n", "\n")
    return targets, message

def load_entries():
    entries = []
    if not os.path.isdir(LISTS_DIR):
        return entries
    for fn in os.listdir(LISTS_DIR):
        if not fn.lower().endswith(".csv"): continue
        path = os.path.join(LISTS_DIR, fn)
        with open(path, newline='') as f:
            r = csv.DictReader(f)
            for row in r:
                name = (row.get("name") or "").strip()
                number = (row.get("number") or "").strip()
                alias = (row.get("alias") or "").strip()
                if not name: continue
                tokens = [t for t in name.lower().split() if t]
                entries.append({
                    "name": name,
                    "number": number,
                    "alias": alias.lower(),
                    "tokens": tokens,
                    "name_l": name.lower()
                })
    return entries

def is_handle(s):
    s2 = s.replace(" ", "")
    return any(ch.isdigit() for ch in s2) or ("@" in s2)

def resolve_targets(targets_str, entries):
    want = [x.strip() for x in targets_str.split(",") if x.strip()]
    out = []
    seen = set()
    for w in want:
        if is_handle(w):
            key = w.lower()
            if key in seen: continue
            out.append((w, w)); seen.add(key); continue
        wl = w.lower()
        hit = next((e for e in entries if e["alias"] == wl and e["alias"]), None)
        if not hit:
            hit = next((e for e in entries if e["name_l"] == wl), None)
        if not hit:
            hit = next((e for e in entries if wl in e["tokens"]), None)
        if not hit:
            hit = next((e for e in entries if wl in e["name_l"]), None)
        if hit:
            handle = hit["number"] or hit["name"]
            key = handle.lower()
            if key not in seen:
                out.append((hit["name"], handle)); seen.add(key)
        else:
            key = wl
            if key not in seen:
                out.append((w, w)); seen.add(key)
    return out

def box_preview(message, names):
    # Plain, no box — just show the message and recipients, then confirm.
    print()  # top spacing
    print("Message:")
    print(message if message.strip() else "(empty)")
    print()
    print("send to:")
    print(" ".join(names))
    print()
    print(DIM + "Press Enter to send; any other key to cancel..." + RST, end="", flush=True)
    ch = read_key()
    print()
    return ch in ("\n", "\r")

def run_osascript(handle, message):
    # Use Popen so we can animate while it runs
    return subprocess.Popen(
        ["osascript", AS_PATH, handle, message],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

def send_with_spinner(name, handle, message):
    """Run AppleScript with a spinner; return (ok, detail)."""
    proc = run_osascript(handle, message)
    spinning = True
    out = {"done": False, "stdout": "", "stderr": ""}

    def reader():
        so, se = proc.communicate()
        out["stdout"] = (so or "").strip()
        out["stderr"] = (se or "").strip()
        out["done"] = True

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    i = 0
    prefix = f"{DIM}{SPIN[i % len(SPIN)]}{RST} {DIM}sending to{RST} {BOLD}{name}{RST}"
    sys.stdout.write(prefix); sys.stdout.flush()

    while not out["done"]:
        time.sleep(0.08)
        i += 1
        prefix = f"\r{DIM}{SPIN[i % len(SPIN)]}{RST} {DIM}sending to{RST} {BOLD}{name}{RST}"
        sys.stdout.write(prefix); sys.stdout.flush()

    # Clear spinner line
    sys.stdout.write("\r"); sys.stdout.flush()

    status = out["stdout"] or out["stderr"]
    status = status.strip()
    if proc.returncode == 0 and status and not status.startswith("ERROR"):
        # iMessage or SMS
        sys.stdout.write(f"{GREEN}{CHECK}{RST} {BOLD}{name}{RST} {DIM}[{status}]{RST}\n")
        return True, status
    else:
        sys.stdout.write(f"{RED}{CROSS}{RST} {BOLD}{name}{RST} {DIM}[{status or 'failed'}]{RST}\n")
        return False, status

def main():
    targets_str, msg = parse_cli(sys.argv)
    entries = load_entries()
    resolved = resolve_targets(targets_str, entries)
    if not resolved:
        print("[fimg] no recipients resolved"); sys.exit(3)

    names = [r[0] for r in resolved]
    if not box_preview(msg, names):
        print("[fimg] cancelled"); sys.exit(0)

    print(BLUE + BOLD + "Sending…" + RST)
    failures = 0
    for name, handle in resolved:
        ok, status = send_with_spinner(name, handle, msg)
        if not ok:
            failures += 1

    if failures:
        print(RED + BOLD + f"Done with {failures} error(s)." + RST)
        sys.exit(1)
    else:
        print(GREEN + BOLD + "All sent." + RST)

if __name__ == "__main__":
    main()

