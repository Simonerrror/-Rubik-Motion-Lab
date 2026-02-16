#!/usr/bin/env python3
from __future__ import annotations

import sys
import threading
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, ttk

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cubeanim.models import RenderGroup
from cubeanim.render_service import RenderRequest, plan_formula_render, render_formula

QUALITY_OPTIONS = [
    ("Draft (fast)", "draft"),
    ("Standard", "standard"),
    ("High", "high"),
    ("Final", "final"),
]
QUALITY_LABEL_TO_VALUE = dict(QUALITY_OPTIONS)


class RenderUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Cube Formula Renderer")
        self.root.geometry("820x560")

        self._build_form()
        self._setup_clipboard_shortcuts()

    def _build_form(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Formula (moves)").grid(row=0, column=0, sticky="w")
        self.formula_input = tk.Text(frame, height=5, width=90)
        self.formula_input.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(4, 12))

        ttk.Label(frame, text="Name").grid(row=2, column=0, sticky="w")
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(frame, textvariable=self.name_var, width=28)
        self.name_entry.grid(row=3, column=0, sticky="ew", padx=(0, 12))

        ttk.Label(frame, text="Group").grid(row=2, column=1, sticky="w")
        self.group_var = tk.StringVar(value=RenderGroup.NO_GROUP.value)
        ttk.Combobox(
            frame,
            textvariable=self.group_var,
            values=[group.value for group in RenderGroup],
            width=14,
            state="readonly",
        ).grid(row=3, column=1, sticky="ew", padx=(0, 12))

        ttk.Label(frame, text="Quality").grid(row=2, column=2, sticky="w")
        self.quality_var = tk.StringVar(value=QUALITY_OPTIONS[0][0])
        ttk.Combobox(
            frame,
            textvariable=self.quality_var,
            values=[label for label, _ in QUALITY_OPTIONS],
            width=14,
            state="readonly",
        ).grid(row=3, column=2, sticky="ew", padx=(0, 12))

        ttk.Label(frame, text="Repeat").grid(row=2, column=3, sticky="w")
        self.repeat_var = tk.StringVar(value="1")
        ttk.Spinbox(frame, from_=1, to=999, textvariable=self.repeat_var, width=8).grid(
            row=3,
            column=3,
            sticky="w",
        )

        self.play_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Play after render", variable=self.play_var).grid(
            row=4,
            column=0,
            sticky="w",
            pady=(12, 8),
        )

        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=4, sticky="w", pady=(8, 8))

        self.render_button = ttk.Button(buttons, text="Render", command=self.on_render)
        self.render_button.grid(row=0, column=0, padx=(0, 10))

        ttk.Button(buttons, text="Clear", command=self.on_clear).grid(row=0, column=1)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(frame, textvariable=self.status_var, foreground="#444").grid(
            row=6,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(4, 8),
        )

        ttk.Label(frame, text="Render log").grid(row=7, column=0, sticky="w")
        self.log_output = tk.Text(frame, height=14, width=90, state=tk.DISABLED)
        self.log_output.grid(row=8, column=0, columnspan=4, sticky="nsew")

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=0)
        frame.columnconfigure(2, weight=0)
        frame.columnconfigure(3, weight=0)
        frame.rowconfigure(8, weight=1)

    def _setup_clipboard_shortcuts(self) -> None:
        for seq, handler in (
            ("<Command-c>", self._on_copy),
            ("<Command-v>", self._on_paste),
            ("<Command-x>", self._on_cut),
            ("<Command-a>", self._on_select_all),
            ("<Control-c>", self._on_copy),
            ("<Control-v>", self._on_paste),
            ("<Control-x>", self._on_cut),
            ("<Control-a>", self._on_select_all),
        ):
            self.root.bind_all(seq, handler, add="+")

        self._build_context_menu()

    def _build_context_menu(self) -> None:
        self._context_menu = tk.Menu(self.root, tearoff=False)
        self._context_menu.add_command(label="Copy", command=lambda: self._copy_from_widget(self._focused_editable_widget()))
        self._context_menu.add_command(label="Paste", command=lambda: self._paste_to_widget(self._focused_editable_widget()))
        self._context_menu.add_command(label="Cut", command=lambda: self._cut_from_widget(self._focused_editable_widget()))
        self._context_menu.add_separator()
        self._context_menu.add_command(label="Select All", command=lambda: self._select_all_in_widget(self._focused_editable_widget()))

        for widget in (self.formula_input, self.name_entry):
            widget.bind("<Button-3>", self._show_context_menu, add="+")
            widget.bind("<Button-2>", self._show_context_menu, add="+")
            widget.bind("<Control-Button-1>", self._show_context_menu, add="+")

    def _show_context_menu(self, event: tk.Event) -> str:
        event.widget.focus_set()
        self._context_menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _focused_editable_widget(self) -> tk.Widget | None:
        widget = self.root.focus_get()
        if widget in (self.formula_input, self.name_entry):
            return widget
        return None

    def _is_supported_edit_widget(self, widget: tk.Widget | None) -> bool:
        return isinstance(widget, tk.Text) or isinstance(widget, (tk.Entry, ttk.Entry))

    def _get_selected_text(self, widget: tk.Widget) -> str:
        if isinstance(widget, tk.Text):
            try:
                return widget.get(tk.SEL_FIRST, tk.SEL_LAST)
            except tk.TclError:
                return ""
        if isinstance(widget, (tk.Entry, ttk.Entry)):
            try:
                if widget.selection_present():
                    return widget.selection_get()
            except tk.TclError:
                return ""
        return ""

    def _delete_selection(self, widget: tk.Widget) -> None:
        if isinstance(widget, tk.Text):
            try:
                widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
            except tk.TclError:
                return
            return
        if isinstance(widget, (tk.Entry, ttk.Entry)):
            try:
                if widget.selection_present():
                    first = int(widget.index(tk.SEL_FIRST))
                    last = int(widget.index(tk.SEL_LAST))
                    widget.delete(first, last)
            except tk.TclError:
                return

    def _copy_from_widget(self, widget: tk.Widget | None) -> bool:
        if not self._is_supported_edit_widget(widget):
            return False
        selected = self._get_selected_text(widget)
        if not selected:
            return False
        self.root.clipboard_clear()
        self.root.clipboard_append(selected)
        return True

    def _paste_to_widget(self, widget: tk.Widget | None) -> bool:
        if not self._is_supported_edit_widget(widget):
            return False
        try:
            clipboard_text = self.root.clipboard_get()
        except tk.TclError:
            return False
        if not clipboard_text:
            return False

        self._delete_selection(widget)
        if isinstance(widget, tk.Text):
            widget.insert(tk.INSERT, clipboard_text)
            return True
        if isinstance(widget, (tk.Entry, ttk.Entry)):
            widget.insert(widget.index(tk.INSERT), clipboard_text)
            return True
        return False

    def _cut_from_widget(self, widget: tk.Widget | None) -> bool:
        if not self._copy_from_widget(widget):
            return False
        if widget is None:
            return False
        self._delete_selection(widget)
        return True

    def _select_all_in_widget(self, widget: tk.Widget | None) -> bool:
        if isinstance(widget, tk.Text):
            widget.tag_add(tk.SEL, "1.0", tk.END)
            widget.mark_set(tk.INSERT, "1.0")
            widget.see(tk.INSERT)
            return True
        if isinstance(widget, (tk.Entry, ttk.Entry)):
            widget.select_range(0, tk.END)
            widget.icursor(tk.END)
            return True
        return False

    def _on_copy(self, event: tk.Event) -> str:
        if self._copy_from_widget(self._focused_editable_widget()):
            return "break"
        return ""

    def _on_paste(self, event: tk.Event) -> str:
        if self._paste_to_widget(self._focused_editable_widget()):
            return "break"
        return ""

    def _on_cut(self, event: tk.Event) -> str:
        if self._cut_from_widget(self._focused_editable_widget()):
            return "break"
        return ""

    def _on_select_all(self, event: tk.Event) -> str:
        if self._select_all_in_widget(self._focused_editable_widget()):
            return "break"
        return ""

    def on_clear(self) -> None:
        self.formula_input.delete("1.0", tk.END)
        self.name_var.set("")
        self.group_var.set(RenderGroup.NO_GROUP.value)
        self.quality_var.set(QUALITY_OPTIONS[0][0])
        self.repeat_var.set("1")
        self.play_var.set(False)
        self.status_var.set("Ready")
        self._append_log("Cleared form")

    def on_render(self) -> None:
        try:
            formula = self.formula_input.get("1.0", tk.END).strip()
            if not formula:
                raise ValueError("Formula is required")

            repeat = int(self.repeat_var.get().strip())
            if repeat < 1:
                raise ValueError("Repeat must be >= 1")

            request = RenderRequest(
                formula=formula,
                name=self.name_var.get().strip() or None,
                group=self.group_var.get().strip(),
                quality=QUALITY_LABEL_TO_VALUE[self.quality_var.get().strip()],
                repeat=repeat,
                play=self.play_var.get(),
            )

            plan = plan_formula_render(request=request, repo_root=REPO_ROOT)
            self._append_log(f"Plan: {plan.action} | {plan.reason}")

            if plan.action == "confirm_rerender":
                should_render = messagebox.askyesno(
                    title="Render already exists",
                    message=(
                        "A render with the same name and formula already exists.\n\n"
                        f"File: {plan.final_path}\n\n"
                        "Render again and overwrite?"
                    ),
                )
                if not should_render:
                    self.status_var.set("Render cancelled")
                    self._append_log("Cancelled by user")
                    return

            if plan.action == "render_alternative":
                messagebox.showinfo(
                    title="Saving as alternative",
                    message=(
                        "Found existing render with the same name but different formula.\n\n"
                        f"Will save as: {plan.output_name}"
                    ),
                )

            self._set_busy(True)
            self.status_var.set("Rendering...")
            threading.Thread(
                target=self._run_render,
                args=(request, plan.action == "confirm_rerender"),
                daemon=True,
            ).start()
        except Exception as exc:
            messagebox.showerror("Invalid input", str(exc))

    def _run_render(self, request: RenderRequest, allow_rerender: bool) -> None:
        try:
            result = render_formula(
                request=request,
                repo_root=REPO_ROOT,
                allow_rerender=allow_rerender,
            )
            self.root.after(0, lambda: self._on_render_done(result.final_path, result.output_name, result.action))
        except Exception as exc:
            self.root.after(0, lambda: self._on_render_failed(exc))

    def _on_render_done(self, path: Path, output_name: str, action: str) -> None:
        self._set_busy(False)
        self.status_var.set(f"Done: {path}")
        self._append_log(f"Rendered [{action}] -> {output_name}: {path}")
        messagebox.showinfo("Render finished", f"Rendered to:\n{path}")

    def _on_render_failed(self, error: Exception) -> None:
        self._set_busy(False)
        self.status_var.set("Render failed")
        self._append_log(f"ERROR: {error}")
        messagebox.showerror("Render failed", str(error))

    def _set_busy(self, busy: bool) -> None:
        state = tk.DISABLED if busy else tk.NORMAL
        self.render_button.configure(state=state)

    def _append_log(self, text: str) -> None:
        self.log_output.configure(state=tk.NORMAL)
        self.log_output.insert(tk.END, f"{text}\n")
        self.log_output.see(tk.END)
        self.log_output.configure(state=tk.DISABLED)


def main() -> int:
    root = tk.Tk()
    app = RenderUI(root)
    app._append_log("UI ready")
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
