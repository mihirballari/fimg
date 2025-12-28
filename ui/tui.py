#!/usr/bin/env python3
# ui/tui.py — terminal UI for fimg

from __future__ import annotations

import curses
import curses.textpad
import re
import textwrap
import time
import signal
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import core

BANNER_PATH = Path(__file__).with_name("banner.txt")


class TuiApp:
    def __init__(self, stdscr: "curses._CursesWindow") -> None:
        self.stdscr = stdscr
        self.menu_idx = 0
        self.menu_items = [
            ("Send", "s", self.send_flow),
            ("Drafts", "d", self.not_implemented),
            ("Schedule", "S", self.not_implemented),
            ("Lists", "l", self.list_flow),
            ("Help", "h", self.show_help),
            ("Quit", "q", self.quit_app),
        ]
        self.banner_lines = self._load_banner()
        self.running = True
        self.needs_redraw = False

    def _load_banner(self) -> list[str]:
        if not BANNER_PATH.exists():
            return ["fimg"]
        return BANNER_PATH.read_text().splitlines()

    def init_screen(self) -> None:
        curses.curs_set(0)
        curses.noecho()
        curses.cbreak()
        self.stdscr.keypad(True)
        self.stdscr.nodelay(True)
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
        signal.signal(signal.SIGWINCH, self._on_resize)

    def _on_resize(self, _signum: int, _frame: object) -> None:
        self.needs_redraw = True

    def safe_addstr(
        self,
        win: "curses._CursesWindow",
        y: int,
        x: int,
        text: str,
        attr: int = 0,
    ) -> None:
        try:
            if attr:
                win.addstr(y, x, text, attr)
            else:
                win.addstr(y, x, text)
        except curses.error:
            pass

    def set_cursor(self, visible: bool) -> None:
        try:
            curses.curs_set(1 if visible else 0)
        except curses.error:
            pass

    def draw_scrim(self) -> None:
        rows, cols = self.stdscr.getmaxyx()
        fill = " " * max(0, cols - 1)
        for y in range(rows):
            self.safe_addstr(self.stdscr, y, 0, fill, curses.A_DIM)
        self.stdscr.refresh()

    def handle_resize(self) -> None:
        try:
            curses.resize_term(0, 0)
        except curses.error:
            pass
        self.stdscr.clear()
        self.stdscr.refresh()
        curses.flushinp()
        self.draw_landing()

    def run(self) -> None:
        self.init_screen()
        self.draw_landing()
        try:
            while self.running:
                if self.needs_redraw:
                    self.needs_redraw = False
                    self.handle_resize()
                ch = self.stdscr.getch()
                if ch == -1:
                    time.sleep(0.05)
                    continue
                if ch == curses.KEY_RESIZE:
                    self.handle_resize()
                    continue
                if ch in (curses.KEY_UP, ord("k")):
                    self.menu_idx = max(0, self.menu_idx - 1)
                    self.draw_landing()
                    continue
                if ch in (curses.KEY_DOWN, ord("j")):
                    self.menu_idx = min(len(self.menu_items) - 1, self.menu_idx + 1)
                    self.draw_landing()
                    continue

                if ch in (10, 13):
                    _, _, action = self.menu_items[self.menu_idx]
                    action()
                    self.draw_landing()
                    continue

                key = chr(ch).lower() if 0 <= ch < 256 else ""
                for _label, hotkey, action in self.menu_items:
                    if key == hotkey.lower():
                        action()
                        self.draw_landing()
                        break
        except KeyboardInterrupt:
            self.running = False

    def draw_landing(self) -> None:
        self.stdscr.clear()
        rows, cols = self.stdscr.getmaxyx()
        if rows < 24 or cols < 80:
            msg = "Resize terminal to at least 80x24."
            self.safe_addstr(self.stdscr, rows // 2, max(0, (cols - len(msg)) // 2), msg)
            self.stdscr.refresh()
            return

        banner_w = max((len(line) for line in self.banner_lines), default=0)
        banner_h = len(self.banner_lines)
        menu_h = len(self.menu_items)
        menu_w = max((len(f"{label:<10} {hotkey}") for label, hotkey, _ in self.menu_items), default=0)
        gap = 2
        total_h = banner_h + gap + menu_h
        top = max(0, (rows - total_h) // 2)
        menu_left = max(0, (cols - menu_w) // 2)
        left = max(0, menu_left + (menu_w - banner_w) // 2)
        for i, line in enumerate(self.banner_lines):
            self.safe_addstr(self.stdscr, top + i, left, line)

        menu_top = top + banner_h + gap
        for i, (label, hotkey, _) in enumerate(self.menu_items):
            line = f"{label:<10} {hotkey}"
            if i == self.menu_idx:
                self.safe_addstr(self.stdscr, menu_top + i, menu_left, line, curses.A_REVERSE)
            else:
                self.safe_addstr(self.stdscr, menu_top + i, menu_left, line)

        hint = "s send  l lists  h help  q quit"
        self.safe_addstr(
            self.stdscr,
            rows - 2,
            max(0, (cols - len(hint)) // 2),
            hint,
            curses.A_DIM,
        )
        self.stdscr.refresh()

    def draw_shadow(self, top: int, left: int, height: int, width: int) -> None:
        rows, cols = self.stdscr.getmaxyx()
        shadow_attr = curses.A_DIM
        if left + width < cols:
            for r in range(top + 1, min(top + height + 1, rows)):
                self.safe_addstr(self.stdscr, r, left + width, " ", shadow_attr)
        if top + height < rows:
            shadow_w = min(width - 1, cols - left - 1)
            if shadow_w > 0:
                self.safe_addstr(self.stdscr, top + height, left + 1, " " * shadow_w, shadow_attr)

    def make_overlay(self, height: int, width: int, title: str) -> "curses._CursesWindow":
        rows, cols = self.stdscr.getmaxyx()
        height = min(height, rows - 2)
        width = min(width, cols - 2)
        top = max(0, (rows - height) // 2)
        left = max(0, (cols - width) // 2)
        self.draw_scrim()
        self.draw_shadow(top, left, height, width)
        win = curses.newwin(height, width, top, left)
        win.box()
        if title:
            self.safe_addstr(win, 0, 2, f" {title} ")
        win.keypad(True)
        win.refresh()
        return win

    def input_line(self, win: "curses._CursesWindow", y: int, x: int, max_len: int, initial: str = "") -> str | None:
        self.set_cursor(True)
        try:
            buf = list(initial[:max_len])
            pos = len(buf)
            self.safe_addstr(win, y, x, "".join(buf))
            while True:
                win.move(y, x + pos)
                win.refresh()
                ch = win.getch()
                if ch == curses.KEY_RESIZE:
                    self.handle_resize()
                    return None
                if ch in (10, 13):
                    return "".join(buf).strip()
                if ch == 27:
                    return None
                if ch in (curses.KEY_BACKSPACE, 127, 8):
                    if pos > 0:
                        pos -= 1
                        buf.pop()
                        self.safe_addstr(win, y, x + pos, " ")
                    continue
                if 32 <= ch < 127 and pos < max_len:
                    buf.append(chr(ch))
                    self.safe_addstr(win, y, x + pos, chr(ch))
                    pos += 1
        finally:
            self.set_cursor(False)

    def input_multiline(self, title: str, initial: str = "") -> str | None:
        rows, cols = self.stdscr.getmaxyx()
        height = min(16, rows - 4)
        width = min(72, cols - 6)
        win = self.make_overlay(height, width, title)
        self.safe_addstr(win, 1, 2, "Ctrl+D finish | Esc cancel", curses.A_DIM)
        edit_h = height - 4
        edit_w = width - 4
        edit_win = win.derwin(edit_h, edit_w, 2, 2)
        if initial:
            for i, line in enumerate(initial.splitlines()[:edit_h]):
                self.safe_addstr(edit_win, i, 0, line[:edit_w - 1])

        canceled = {"flag": False}

        def validator(ch: int) -> int:
            if ch == 27:
                canceled["flag"] = True
                return 7
            if ch == curses.KEY_RESIZE:
                canceled["flag"] = True
                self.handle_resize()
                return 7
            if ch == 4:
                return 7
            return ch

        box = curses.textpad.Textbox(edit_win)
        self.set_cursor(True)
        try:
            text = box.edit(validator)
        finally:
            self.set_cursor(False)
        if canceled["flag"]:
            return None
        return text.strip()

    def contact_matches(self, contact: core.Contact, query: str) -> bool:
        if not query:
            return True
        hay = " ".join([contact.name, contact.number, " ".join(contact.aliases)]).lower()
        return all(part in hay for part in query.lower().split())

    def draw_contact_row(
        self,
        win: "curses._CursesWindow",
        y: int,
        x: int,
        width: int,
        contact: core.Contact,
        active: bool,
        selected: bool,
        show_marker: bool,
    ) -> None:
        marker = ""
        if show_marker:
            marker = "[x] " if selected else "[ ] "
        inner = max(0, width - len(marker))
        name_w = min(max(8, min(26, inner // 2)), inner)
        meta_w = max(0, inner - name_w - 1)
        name_part = contact.name[:name_w].ljust(name_w)
        meta_parts = [contact.number]
        if contact.aliases:
            meta_parts.append(",".join(contact.aliases))
        meta = " | ".join([p for p in meta_parts if p])
        meta_part = meta[:meta_w]
        row_attr = curses.A_REVERSE if active else curses.A_NORMAL
        meta_attr = row_attr | curses.A_DIM
        self.safe_addstr(win, y, x, f"{marker}{name_part}", row_attr)
        if meta_part:
            self.safe_addstr(win, y, x + len(marker) + name_w + 1, meta_part, meta_attr)

    def contact_browser(
        self,
        title: str,
        contacts: list[core.Contact],
        selectable: bool,
    ) -> list[core.Contact] | None:
        query = ""
        idx = 0
        offset = 0
        selected_numbers: set[str] = set()
        sorted_contacts = sorted(contacts, key=lambda c: c.name.lower())
        while True:
            rows, cols = self.stdscr.getmaxyx()
            height = min(20, rows - 4)
            width = min(78, cols - 6)
            win = self.make_overlay(height, width, title)
            inner_w = width - 4
            filtered = [c for c in sorted_contacts if self.contact_matches(c, query)]
            if idx >= len(filtered):
                idx = max(0, len(filtered) - 1)
            max_rows = height - 4
            max_offset = max(0, len(filtered) - max_rows)
            if offset > max_offset:
                offset = max_offset
            if idx < offset:
                offset = idx
            if idx >= offset + max_rows:
                offset = idx - max_rows + 1

            filter_label = f"Filter: {query}" if query else "Filter: (type to search)"
            self.safe_addstr(win, 1, 2, filter_label[:inner_w])
            right = f"{len(filtered)}/{len(sorted_contacts)}"
            if selectable:
                right = f"Selected {len(selected_numbers)} | {right}"
            if len(right) + 1 < inner_w:
                self.safe_addstr(win, 1, width - 2 - len(right), right, curses.A_DIM)

            if not filtered:
                self.safe_addstr(win, 3, 2, "No matches.", curses.A_DIM)
            else:
                view = filtered[offset : offset + max_rows]
                for i, contact in enumerate(view):
                    active = (offset + i) == idx
                    selected = contact.number in selected_numbers
                    self.draw_contact_row(
                        win,
                        2 + i,
                        2,
                        inner_w,
                        contact,
                        active,
                        selected,
                        selectable,
                    )
                if offset > 0:
                    self.safe_addstr(win, 2, width - 3, "^", curses.A_DIM)
                if offset + max_rows < len(filtered):
                    self.safe_addstr(win, 2 + max_rows - 1, width - 3, "v", curses.A_DIM)

            footer = "Esc back"
            if selectable:
                footer = "Space toggle | Enter confirm | Esc back"
            self.safe_addstr(win, height - 2, 2, footer[:inner_w], curses.A_DIM)
            win.refresh()
            ch = win.getch()
            if ch == curses.KEY_RESIZE:
                self.handle_resize()
                continue
            if ch in (curses.KEY_UP, ord("k")):
                idx = max(0, idx - 1)
                continue
            if ch in (curses.KEY_DOWN, ord("j")):
                idx = min(max(0, len(filtered) - 1), idx + 1)
                continue
            if ch in (10, 13):
                if not selectable:
                    return None
                if not selected_numbers:
                    self.show_message("No selection", "Select at least one contact to remove.")
                    continue
                return [c for c in sorted_contacts if c.number in selected_numbers]
            if ch == 27:
                return None
            if ch in (curses.KEY_BACKSPACE, 127, 8):
                query = query[:-1]
                idx = 0
                offset = 0
                continue
            if ch == ord(" ") and selectable and filtered:
                contact = filtered[idx]
                if contact.number in selected_numbers:
                    selected_numbers.remove(contact.number)
                else:
                    selected_numbers.add(contact.number)
                continue
            if 32 <= ch < 127 and ch != ord(" "):
                query += chr(ch)
                idx = 0
                offset = 0
                continue

    def select_list(self, entries: list[tuple[str, Path]]) -> tuple[str, Path] | None:
        height = min(12, len(entries) + 4)
        width = 40
        idx = 0
        offset = 0
        while True:
            win = self.make_overlay(height, width, "Select list")
            while True:
                max_rows = height - 4
                if idx < offset:
                    offset = idx
                if idx >= offset + max_rows:
                    offset = idx - max_rows + 1
                view = entries[offset : offset + max_rows]
                for i, (label, _path) in enumerate(view):
                    attr = curses.A_REVERSE if (offset + i) == idx else curses.A_NORMAL
                    self.safe_addstr(win, 2 + i, 2, f"{label:<20}", attr)
                if offset > 0:
                    self.safe_addstr(win, 1, width - 3, "^", curses.A_DIM)
                if offset + max_rows < len(entries):
                    self.safe_addstr(win, height - 3, width - 3, "v", curses.A_DIM)
                self.safe_addstr(win, height - 2, 2, "Enter select | Esc back", curses.A_DIM)
                win.refresh()
                ch = win.getch()
                if ch in (curses.KEY_UP, ord("k")):
                    idx = max(0, idx - 1)
                elif ch in (curses.KEY_DOWN, ord("j")):
                    idx = min(len(entries) - 1, idx + 1)
                elif ch in (10, 13):
                    return entries[idx]
                elif ch == 27:
                    return None
                elif ch == curses.KEY_RESIZE:
                    self.handle_resize()
                    break

    def preview_send(
        self,
        list_label: str,
        resolved: list[core.Contact],
        missing: list[str],
        message: str,
    ) -> bool:
        while True:
            rows, cols = self.stdscr.getmaxyx()
            height = min(20, rows - 4)
            width = min(78, cols - 6)
            win = self.make_overlay(height, width, "Preview")
            y = 2
            self.safe_addstr(win, y, 2, f"List: {list_label}")
            y += 1
            names = ", ".join(c.name for c in resolved)
            for line in textwrap.wrap(f"Recipients ({len(resolved)}): {names}", width - 4):
                if y >= height - 4:
                    break
                self.safe_addstr(win, y, 2, line)
                y += 1
            if missing and y < height - 4:
                self.safe_addstr(win, y, 2, "Unmatched (ignored): " + ", ".join(missing), curses.A_DIM)
                y += 1

            y += 1
            if y < height - 3:
                self.safe_addstr(win, y, 2, "Message:", curses.A_BOLD)
                y += 1
            for line in message.splitlines() or ["(empty)"]:
                for wrapped in textwrap.wrap(line, width - 4) or [""]:
                    if y >= height - 3:
                        break
                    self.safe_addstr(win, y, 2, wrapped)
                    y += 1
                if y >= height - 3:
                    break

            self.safe_addstr(win, height - 2, 2, "Enter send | Esc cancel", curses.A_DIM)
            win.refresh()
            ch = win.getch()
            if ch == curses.KEY_RESIZE:
                self.handle_resize()
                continue
            return ch in (10, 13)

    def send_messages(self, resolved: list[core.Contact], message: str) -> None:
        rows, cols = self.stdscr.getmaxyx()
        height = min(rows - 4, max(10, len(resolved) + 6))
        width = min(70, cols - 6)
        win = self.make_overlay(height, width, "Sending")
        win.scrollok(True)
        y = 2
        self.safe_addstr(win, y, 2, f"Sending {len(resolved)} message(s)...")
        y += 2
        for contact in resolved:
            per = core.personalize(message, contact.first)
            self.safe_addstr(win, y, 2, f"-> {contact.name} ...")
            win.refresh()
            ok, detail = core.send_message(contact.number, per)
            status = "OK" if ok else "FAIL"
            info = f"{status} {contact.name}"
            if detail:
                info = f"{info} ({detail})"
            self.safe_addstr(win, y, 2, info[: width - 4])
            y += 1
            if y >= height - 2:
                win.scroll(1)
                y = height - 3
            time.sleep(0.1)
        self.safe_addstr(win, height - 2, 2, "Done. Press any key.", curses.A_DIM)
        win.refresh()
        while True:
            ch = win.getch()
            if ch == curses.KEY_RESIZE:
                self.handle_resize()
                return
            if ch != -1:
                return

    def send_flow(self) -> None:
        entries = core.list_entries()
        selected = self.select_list(entries)
        if not selected:
            return
        list_label, list_path = selected
        win = self.make_overlay(8, 72, "Recipients")
        self.safe_addstr(win, 2, 2, "To (comma or space separated):")
        recipients = self.input_line(win, 3, 2, 66)
        if recipients is None or not recipients.strip():
            return
        message = self.input_multiline("Compose message")
        if message is None or not message.strip():
            return

        try:
            contacts = core.load_contacts(list_path)
        except FileNotFoundError as exc:
            self.show_message("Error", str(exc))
            return

        tokens = core.tokenize_names(recipients)
        resolved, missing = core.resolve_tokens(tokens, contacts)
        if not resolved:
            self.show_message("No recipients", "No recipients matched your input.")
            return

        normalized = core.normalize_message(message)
        if not self.preview_send(list_label, resolved, missing, normalized):
            return
        self.send_messages(resolved, normalized)

    def list_flow(self) -> None:
        while True:
            action = self.overlay_menu(
                "Lists",
                [("Preview", "preview"), ("Add", "add"), ("Remove", "remove"), ("Back", None)],
            )
            if action is None:
                return
            if action == "preview":
                self.list_preview_flow()
            elif action == "add":
                self.list_add_flow()
            elif action == "remove":
                self.list_remove_flow()

    def overlay_menu(
        self,
        title: str,
        options: list[tuple[str, str | None]],
    ) -> str | None:
        height = min(12, len(options) + 4)
        width = 32
        idx = 0
        offset = 0
        while True:
            win = self.make_overlay(height, width, title)
            while True:
                max_rows = height - 4
                if idx < offset:
                    offset = idx
                if idx >= offset + max_rows:
                    offset = idx - max_rows + 1
                view = options[offset : offset + max_rows]
                for i, (label, _value) in enumerate(view):
                    attr = curses.A_REVERSE if (offset + i) == idx else curses.A_NORMAL
                    self.safe_addstr(win, 2 + i, 2, f"{label:<20}", attr)
                if offset > 0:
                    self.safe_addstr(win, 1, width - 3, "^", curses.A_DIM)
                if offset + max_rows < len(options):
                    self.safe_addstr(win, height - 3, width - 3, "v", curses.A_DIM)
                self.safe_addstr(win, height - 2, 2, "Enter select | Esc back", curses.A_DIM)
                win.refresh()
                ch = win.getch()
                if ch in (curses.KEY_UP, ord("k")):
                    idx = max(0, idx - 1)
                elif ch in (curses.KEY_DOWN, ord("j")):
                    idx = min(len(options) - 1, idx + 1)
                elif ch in (10, 13):
                    return options[idx][1]
                elif ch == 27:
                    return None
                elif ch == curses.KEY_RESIZE:
                    self.handle_resize()
                    break

    def prompt_field(self, title: str, label: str) -> str | None:
        rows, cols = self.stdscr.getmaxyx()
        width = min(70, cols - 6)
        win = self.make_overlay(7, width, title)
        self.safe_addstr(win, 2, 2, label)
        return self.input_line(win, 3, 2, width - 4)

    def list_add_flow(self) -> None:
        entries = core.list_entries()
        options = [(label, label) for label, _path in entries]
        options.append(("Create new list", "__new__"))
        selection = self.overlay_menu("Add to list", options)
        if selection is None:
            return
        if selection == "__new__":
            name = self.prompt_field("New list", "List name:")
            if not name:
                return
            list_label = name.strip()
            list_path = core.LISTS_DIR / f"{list_label}.csv"
            if not list_path.exists():
                core.write_contacts(list_path, [])
        else:
            list_label = selection
            list_path = next((p for l, p in entries if l == list_label), None)
            if list_path is None:
                return

        try:
            contacts = core.load_contacts(list_path)
        except FileNotFoundError:
            contacts = []

        name = self.prompt_field("Add contact", "Name:")
        if not name:
            return
        raw_number = self.prompt_field("Add contact", "Number:")
        if raw_number is None:
            return
        number = re.sub(r"[^\d+]", "", raw_number)
        if not number:
            self.show_message("Invalid number", "A phone number or handle is required.")
            return
        alias = self.prompt_field("Add contact", "Alias (optional):") or ""

        if any(c.number == number for c in contacts):
            self.show_message("Duplicate", "That number already exists in the list.")
            return

        contacts.append(core.make_contact(name, number, alias))
        core.write_contacts(list_path, contacts)
        self.show_message("Added", f"Added {name} to {list_label}.")

    def list_remove_flow(self) -> None:
        entries = core.list_entries()
        selection = self.overlay_menu("Remove from list", [(label, label) for label, _ in entries])
        if selection is None:
            return
        list_label = selection
        list_path = next((p for l, p in entries if l == list_label), None)
        if list_path is None:
            return

        try:
            contacts = core.load_contacts(list_path)
        except FileNotFoundError as exc:
            self.show_message("Missing list", str(exc))
            return

        if not contacts:
            self.show_message("Empty list", f"{list_label} has no entries.")
            return

        chosen = self.contact_browser(f"Remove from {list_label}", contacts, selectable=True)
        if not chosen:
            return

        confirm = self.overlay_menu("Confirm remove", [("Remove", "yes"), ("Cancel", None)])
        if confirm != "yes":
            return

        remaining = [c for c in contacts if c.number not in {c.number for c in chosen}]
        core.write_contacts(list_path, remaining)
        self.show_message("Removed", f"Removed {len(chosen)} from {list_label}.")

    def list_preview_flow(self) -> None:
        entries = core.list_entries()
        selected = self.select_list(entries)
        if not selected:
            return
        list_label, list_path = selected
        try:
            contacts = core.load_contacts(list_path)
        except FileNotFoundError as exc:
            self.show_message("Missing list", str(exc))
            return
        if not contacts:
            self.show_message("Empty list", f"{list_label} has no entries.")
            return
        self.contact_browser(f"Preview {list_label}", contacts, selectable=False)

    def show_message(self, title: str, body: str) -> None:
        while True:
            width = min(70, max(40, len(title) + 10))
            win = self.make_overlay(7, width, title)
            for i, line in enumerate(textwrap.wrap(body, width - 4)[:3]):
                self.safe_addstr(win, 2 + i, 2, line)
            self.safe_addstr(win, 5, 2, "Press any key.", curses.A_DIM)
            win.refresh()
            ch = win.getch()
            if ch == curses.KEY_RESIZE:
                self.handle_resize()
                continue
            return

    def show_help(self) -> None:
        lines = [
            "Send: select list, type recipients, write message, preview, send.",
            "Lists: preview, add, or remove names and numbers.",
            "Recipients: comma or space separated; use aliases if set.",
            "Message: Ctrl+D to finish, Esc to cancel.",
            "List browser: type to filter; Space toggles selection in remove.",
            "Keys: arrows or j/k to move, Enter to select, Esc to go back.",
        ]
        while True:
            width = 78
            height = min(12, len(lines) + 4)
            win = self.make_overlay(height, width, "Help")
            for i, line in enumerate(lines):
                self.safe_addstr(win, 2 + i, 2, line)
            self.safe_addstr(win, height - 2, 2, "Press any key.", curses.A_DIM)
            win.refresh()
            ch = win.getch()
            if ch == curses.KEY_RESIZE:
                self.handle_resize()
                continue
            return

    def not_implemented(self) -> None:
        self.show_message("Coming soon", "This section is not implemented yet.")

    def quit_app(self) -> None:
        self.running = False


def main(stdscr: "curses._CursesWindow") -> None:
    app = TuiApp(stdscr)
    try:
        app.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    curses.wrapper(main)
