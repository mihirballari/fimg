#!/usr/bin/env python3
# engine/core.py — shared fimg logic (contacts, parsing, sending)

from __future__ import annotations

import csv
import os
import re
import shlex
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
LISTS_DIR = ROOT / "lists"
ENGINE_DIR = ROOT / "engine"

CSV_MAP = {
    "all": LISTS_DIR / "all.csv",
    "actives": LISTS_DIR / "brothers.csv",
    "brothers": LISTS_DIR / "brothers.csv",
    "pledges": LISTS_DIR / "pledges.csv",
}

AS_PATH = ENGINE_DIR / "send_imessage.applescript"


@dataclass(frozen=True)
class Contact:
    name: str
    first: str
    number: str
    name_l: str
    aliases: Tuple[str, ...]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[.,]", " ", s.lower())
    return " ".join(s.split())


def first_name(full: str) -> str:
    n = _norm(full)
    return n.split(" ")[0] if n else ""


def list_entries() -> List[Tuple[str, Path]]:
    entries: List[Tuple[str, Path]] = []
    seen = set()
    for key, path in CSV_MAP.items():
        if path.exists():
            entries.append((key, path))
            seen.add(path.resolve())
    if LISTS_DIR.exists():
        for path in sorted(LISTS_DIR.glob("*.csv")):
            if path.resolve() in seen:
                continue
            entries.append((path.stem, path))
    if not entries:
        entries.append(("all", LISTS_DIR / "all.csv"))
    return entries


def load_contacts(csv_path: Path) -> List[Contact]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Roster CSV missing: {csv_path}")
    contacts: List[Contact] = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("name") or row.get("Name") or "").strip()
            raw = (row.get("number") or row.get("Number") or row.get("Phone") or "").strip()
            alias_raw = (row.get("alias") or row.get("Alias") or "").strip()
            if not name or not raw:
                continue
            number = re.sub(r"[^\d+]", "", raw)
            aliases = (
                tuple(a.lower() for a in re.split(r"[,\s;/]+", alias_raw) if a.strip())
                if alias_raw
                else ()
            )
            contacts.append(
                Contact(
                    name=name,
                    first=first_name(name),
                    number=number,
                    name_l=_norm(name),
                    aliases=aliases,
                )
            )
    return contacts


def make_contact(name: str, number: str, alias_raw: str = "") -> Contact:
    aliases = (
        tuple(a.lower() for a in re.split(r"[,\s;/]+", alias_raw) if a.strip())
        if alias_raw
        else ()
    )
    name_norm = _norm(name)
    return Contact(
        name=name.strip(),
        first=first_name(name),
        number=number,
        name_l=name_norm,
        aliases=aliases,
    )


def write_contacts(csv_path: Path, contacts: List[Contact]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = csv_path.with_suffix(csv_path.suffix + ".tmp")
    with open(tmp, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "number", "alias"])
        writer.writeheader()
        for contact in sorted(contacts, key=lambda c: c.name.lower()):
            writer.writerow(
                {
                    "name": contact.name,
                    "number": contact.number,
                    "alias": ",".join(contact.aliases),
                }
            )
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, csv_path)


def dedup(people: Iterable[Contact]) -> List[Contact]:
    out: List[Contact] = []
    seen = set()
    for c in people:
        if c.number not in seen:
            out.append(c)
            seen.add(c.number)
    return out


def tokenize_names(names_raw: str) -> List[str]:
    parts: List[str] = []
    for chunk in re.split(r"\s*,\s*", names_raw):
        if chunk:
            parts.extend(shlex.split(chunk))
    return [t for t in parts if t]


def parse_targets_message(raw: str) -> Tuple[Optional[List[str]], Optional[str]]:
    raw = raw.strip()
    m = re.match(r"^(?:to\s+)?(.+?)\s*:\s*(.+)$", raw, flags=re.IGNORECASE)
    if not m:
        return None, None
    names_raw, message = m.group(1).strip(), m.group(2).strip()
    tokens = tokenize_names(names_raw)
    return tokens, message


def resolve_tokens(tokens: List[str], contacts: List[Contact]) -> Tuple[List[Contact], List[str]]:
    if any(t.lower() == "all" for t in tokens):
        return dedup(contacts), []
    chosen: List[Contact] = []
    missing: List[str] = []
    for tok in tokens:
        t = _norm(tok)
        alias_hits = [c for c in contacts if t in c.aliases]
        if alias_hits:
            chosen.append(alias_hits[0])
            continue
        hits = [
            c
            for c in contacts
            if t in c.name_l or any(p.startswith(t) for p in c.name_l.split())
        ]
        if not hits:
            missing.append(tok)
        else:
            starts = [c for c in hits if any(p.startswith(t) for p in c.name_l.split())]
            chosen.append((starts or hits)[0])
    return dedup(chosen), missing


def normalize_message(msg: str) -> str:
    msg = (
        msg.replace("########", "\n\n")
        .replace("####", "\n\n")
        .replace("##", "\n")
        .replace("||||", "\n\n")
        .replace("||", "\n")
        .replace("\\\\n", "\n")
        .replace("\\n", "\n")
    )
    msg = re.sub(r"\n[ \t]+", "\n", msg)
    return msg


def personalize(template: str, first_lower: str) -> str:
    first_title = first_lower.capitalize()
    msg = re.sub(r"(\[(?:names?)\]|\{(?:names?)\})", first_lower, template, flags=re.IGNORECASE)

    def _n(m: re.Match[str]) -> str:
        return first_title if m.group(0) == "-N" else first_lower

    msg = re.sub(r"(?<!\S)-[nN](?=$|\s|[.,;:!?])", _n, msg)
    return msg


def send_message(handle: str, message: str, applescript_path: Path = AS_PATH) -> Tuple[bool, str]:
    if not applescript_path.exists():
        raise FileNotFoundError(f"AppleScript missing: {applescript_path}")
    proc = subprocess.run(
        ["osascript", str(applescript_path), handle, message],
        text=True,
        capture_output=True,
    )
    detail = (proc.stdout or proc.stderr or "").strip()
    return proc.returncode == 0, detail
