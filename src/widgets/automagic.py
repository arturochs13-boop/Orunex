"""Automations dashboard for Orunex.

The panel talks to the real automation daemon and only shows tasks that exist
in its store. No sample or simulated workflows are rendered here.
"""
import json
import os
import re
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

THEME = {
    "bg": "#F8F9FA",
    "surface": "#FFFFFF",
    "surface_soft": "#F8F9FA",
    "surface_muted": "#F2F4F7",
    "border": "#E6E9EE",
    "border_strong": "#D9DEE6",
    "blue": "#0668E1",
    "blue_soft": "#EDF4FF",
    "blue_border": "#CFE2FF",
    "red": "#E15241",
    "red_soft": "#FEF1EF",
    "text": "#111318",
    "text_dim": "#667085",
    "muted": "#98A2B3",
}

FREQUENCY_TO_BACKEND = {
    "Daily": "diario",
    "Hourly": "hora",
    "Every minute": "minuto",
}
FREQUENCY_TO_LABEL = {value: key for key, value in FREQUENCY_TO_BACKEND.items()}

NODE_LIBRARY = [
    {"name": "Local shell", "integ": "Local shell", "fields": ["Command or instruction"]},
    {"name": "Files", "integ": "Files", "fields": ["Path", "Action"]},
    {"name": "Browser", "integ": "Browser", "fields": ["URL", "Action"]},
    {"name": "Documents", "integ": "Documents", "fields": ["Document type", "Topic"]},
    {"name": "System", "integ": "System", "fields": ["Action"]},
    {"name": "Custom", "integ": "Custom", "fields": ["Instruction"]},
]


def _backend_frequency(value: str) -> str:
    return FREQUENCY_TO_BACKEND.get(value, value if value in FREQUENCY_TO_BACKEND.values() else "diario")


def _display_frequency(value: str) -> str:
    return FREQUENCY_TO_LABEL.get(str(value).lower(), str(value).title())


def fit_window(window, width, height):
    try:
        scale = ctk.ScalingTracker.get_window_scaling(window) or 1.0
    except Exception:
        scale = 1.0
    available_w = int(window.winfo_screenwidth() / scale)
    available_h = int(window.winfo_screenheight() / scale)
    final_w = min(width, max(680, available_w - 40))
    final_h = min(height, max(520, available_h - 80))
    x = max(0, (available_w - final_w) // 2)
    y = max(0, (available_h - final_h) // 2)
    window.geometry(f"{final_w}x{final_h}+{x}+{y}")


class AutomagicCanvas(ctk.CTkToplevel):
    def __init__(self, parent, cerebro_run_fn=None, user_name="User"):
        super().__init__(parent)
        self.title("Automations")
        fit_window(self, 1180, 800)
        self.minsize(960, 620)
        self.configure(fg_color=THEME["bg"])
        self.attributes("-topmost", True)

        self.cerebro_run_fn = cerebro_run_fn
        self.user_name = user_name
        self.active_items = []

        self._setup_ui()
        self.refresh_dashboard()

    def _setup_ui(self):
        header = ctk.CTkFrame(self, fg_color=THEME["surface"], corner_radius=0)
        header.pack(fill="x")

        title_block = ctk.CTkFrame(header, fg_color="transparent")
        title_block.pack(side="left", padx=28, pady=18)
        ctk.CTkLabel(
            title_block,
            text="Automations",
            font=("Segoe UI", 22, "bold"),
            text_color=THEME["text"],
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_block,
            text="Build scheduled local workflows with clear targets.",
            font=("Segoe UI", 11),
            text_color=THEME["text_dim"],
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        ctk.CTkButton(
            header,
            text="Close",
            width=70,
            height=32,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=THEME["border"],
            text_color=THEME["text_dim"],
            hover_color=THEME["surface_muted"],
            command=self.destroy,
        ).pack(side="right", padx=24)

        ctk.CTkFrame(self, height=1, fg_color=THEME["border"]).pack(fill="x")

        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=24, pady=18)

        # Left: quick bridge library
        self.sidebar = ctk.CTkFrame(
            main_frame,
            width=250,
            fg_color=THEME["surface"],
            corner_radius=14,
            border_width=1,
            border_color=THEME["border"],
        )
        self.sidebar.pack(side="left", fill="y", padx=(0, 16))
        self.sidebar.pack_propagate(False)

        ctk.CTkLabel(
            self.sidebar,
            text="AUTOMATION TARGETS",
            font=("Segoe UI", 10, "bold"),
            text_color=THEME["text_dim"],
            anchor="w",
        ).pack(fill="x", padx=16, pady=(18, 4))
        ctk.CTkLabel(
            self.sidebar,
            text="Choose where the workflow is headed.",
            font=("Segoe UI", 10),
            text_color=THEME["muted"],
            anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 10))

        for app in NODE_LIBRARY:
            ctk.CTkButton(
                self.sidebar,
                text=app["name"],
                anchor="w",
                height=36,
                corner_radius=8,
                fg_color=THEME["surface_soft"],
                border_width=1,
                border_color=THEME["border"],
                text_color=THEME["text"],
                hover_color=THEME["surface_muted"],
                font=("Segoe UI", 11),
                command=lambda item=app: self._show_bridge_form(item),
            ).pack(fill="x", padx=14, pady=4)

        ctk.CTkLabel(
            self.sidebar,
            text="Targets label the workflow. The scheduled\n"
                 "command runs locally after you confirm the details.",
            font=("Segoe UI", 9),
            text_color=THEME["muted"],
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=16, pady=(16, 0))

        # Right: active automations
        self.dashboard = ctk.CTkFrame(
            main_frame,
            fg_color=THEME["surface"],
            corner_radius=14,
            border_width=1,
            border_color=THEME["border"],
        )
        self.dashboard.pack(side="right", fill="both", expand=True)

        dash_header = ctk.CTkFrame(self.dashboard, fg_color="transparent")
        dash_header.pack(fill="x", padx=20, pady=(18, 6))
        ctk.CTkLabel(
            dash_header,
            text="ACTIVE AUTOMATIONS",
            font=("Segoe UI", 10, "bold"),
            text_color=THEME["text_dim"],
            anchor="w",
        ).pack(side="left")

        self.refresh_btn = ctk.CTkButton(
            dash_header,
            text="Refresh",
            width=76,
            height=30,
            corner_radius=7,
            fg_color=THEME["surface_soft"],
            border_width=1,
            border_color=THEME["border"],
            text_color=THEME["text_dim"],
            hover_color=THEME["surface_muted"],
            font=("Segoe UI", 10),
            command=self.refresh_dashboard,
        )
        self.refresh_btn.pack(side="right")

        self.scroll_frame = ctk.CTkScrollableFrame(
            self.dashboard,
            fg_color="transparent",
            scrollbar_button_color=THEME["border"],
            scrollbar_button_hover_color=THEME["border_strong"],
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # Footer: natural-language generator
        self.footer = ctk.CTkFrame(
            self,
            fg_color=THEME["surface"],
            height=82,
            corner_radius=14,
            border_width=1,
            border_color=THEME["border"],
        )
        self.footer.pack(fill="x", padx=24, pady=(0, 24))
        self.footer.pack_propagate(False)

        self.prompt_entry = ctk.CTkEntry(
            self.footer,
            placeholder_text="Describe the workflow to schedule...",
            font=("Segoe UI", 11),
            height=40,
            fg_color=THEME["surface_soft"],
            border_color=THEME["border"],
            text_color=THEME["text"],
            corner_radius=9,
        )
        self.prompt_entry.pack(side="left", fill="x", expand=True, padx=(16, 8), pady=20)
        self.prompt_entry.bind("<Return>", lambda _event: self._on_generate_prompt())

        self.gen_btn = ctk.CTkButton(
            self.footer,
            text="Generate workflow",
            width=160,
            height=40,
            font=("Segoe UI", 11, "bold"),
            fg_color=THEME["blue"],
            text_color="#FFFFFF",
            hover_color="#0059C7",
            corner_radius=9,
            command=self._on_generate_prompt,
        )
        self.gen_btn.pack(side="right", padx=(0, 16), pady=20)

    def _show_bridge_form(self, app):
        form = ctk.CTkToplevel(self)
        form.title(f"Configure {app['name']}")
        fit_window(form, 470, 620)
        form.configure(fg_color=THEME["bg"])
        form.attributes("-topmost", True)
        form.transient(self)

        ctk.CTkLabel(
            form,
            text=f"Configure {app['name']}",
            font=("Segoe UI", 20, "bold"),
            text_color=THEME["text"],
            anchor="w",
        ).pack(fill="x", padx=28, pady=(24, 2))
        ctk.CTkLabel(
            form,
            text="Describe what the automation should do. Orunex will turn it\n"
                 "into a local command for the schedule.",
            font=("Segoe UI", 10),
            text_color=THEME["text_dim"],
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=28, pady=(0, 14))

        entries = {}
        for field in app["fields"]:
            ctk.CTkLabel(
                form,
                text=field.upper(),
                font=("Segoe UI", 9, "bold"),
                text_color=THEME["text_dim"],
                anchor="w",
            ).pack(fill="x", padx=28, pady=(6, 2))
            entry = ctk.CTkEntry(
                form,
                placeholder_text=f"Enter {field.lower()}...",
                fg_color=THEME["surface"],
                border_color=THEME["border"],
                text_color=THEME["text"],
                height=38,
            )
            entry.pack(fill="x", padx=28, pady=(0, 6))
            entries[field] = entry

        ctk.CTkLabel(
            form,
            text="FREQUENCY",
            font=("Segoe UI", 9, "bold"),
            text_color=THEME["text_dim"],
            anchor="w",
        ).pack(fill="x", padx=28, pady=(8, 2))
        freq_var = ctk.StringVar(value="Daily")
        ctk.CTkOptionMenu(
            form,
            values=list(FREQUENCY_TO_BACKEND.keys()),
            variable=freq_var,
            fg_color=THEME["surface"],
            button_color=THEME["blue"],
            button_hover_color="#0059C7",
            dropdown_fg_color=THEME["surface"],
            dropdown_hover_color=THEME["surface_muted"],
            dropdown_text_color=THEME["text"],
            text_color=THEME["text"],
        ).pack(fill="x", padx=28, pady=(0, 8))

        status_lbl = ctk.CTkLabel(
            form, text="", font=("Segoe UI", 9), text_color=THEME["text_dim"]
        )
        status_lbl.pack(fill="x", padx=28)

        def save():
            params = {field: entry.get().strip() for field, entry in entries.items()}
            if not any(params.values()):
                status_lbl.configure(
                    text="Add at least one detail for this workflow.",
                    text_color=THEME["red"],
                )
                return
            bridge_task = (
                f"Create an automation for {app['name']} with these details: {params}. "
                f"Frequency: {freq_var.get()}."
            )
            status_lbl.configure(text="Building the command...", text_color=THEME["text_dim"])
            self.update_idletasks()
            self._synth_and_add(bridge_task, app["integ"], _backend_frequency(freq_var.get()))
            form.destroy()

        ctk.CTkButton(
            form,
            text="Create automation",
            font=("Segoe UI", 11, "bold"),
            fg_color=THEME["blue"],
            text_color="#FFFFFF",
            hover_color="#0059C7",
            height=42,
            corner_radius=9,
            command=save,
        ).pack(fill="x", padx=28, pady=(18, 8))
        ctk.CTkButton(
            form,
            text="Cancel",
            fg_color="transparent",
            border_width=1,
            border_color=THEME["border"],
            text_color=THEME["text_dim"],
            hover_color=THEME["surface_muted"],
            command=form.destroy,
        ).pack(fill="x", padx=28, pady=(0, 20))

    def _synth_and_add(self, task_text, integ, freq):
        if not self.cerebro_run_fn:
            return
        self.refresh_btn.configure(text="Building...", state="disabled")
        try:
            raw = self.cerebro_run_fn(
                f"NODE ARCHITECT: {task_text}. "
                "Return only JSON in the form {\"cmd\": \"...\"}.",
                self.user_name,
            )
            match = re.search(r"\{.*\}", raw or "", re.DOTALL)
            if match:
                command_data = json.loads(match.group(0))
                from _orunex_libs.automation_daemon import get_daemon

                get_daemon().add_task(
                    command_data["cmd"], freq, "12:00", integration=integ
                )
        except Exception as exc:
            print(f"Automation synthesis error: {exc}")
        finally:
            self.refresh_btn.configure(text="Refresh", state="normal")
            self.refresh_dashboard()

    def _on_generate_prompt(self):
        prompt = self.prompt_entry.get().strip()
        if not prompt or not self.cerebro_run_fn:
            return

        self.gen_btn.configure(state="disabled", text="Building...")
        try:
            raw = self.cerebro_run_fn(
                f"NODE ARCHITECT: {prompt}. "
                "Return a JSON list in the form "
                "[{\"cmd\": \"...\", \"integ\": \"...\", \"freq\": \"...\"}].",
                self.user_name,
            )
            match = re.search(r"\[.*\]", raw or "", re.DOTALL)
            if match:
                tasks = json.loads(match.group(0))
                from _orunex_libs.automation_daemon import get_daemon

                for task in tasks:
                    get_daemon().add_task(
                        task["cmd"],
                        _backend_frequency(str(task.get("freq", "diario"))),
                        task.get("time", "12:00"),
                        integration=task.get("integ", "System"),
                    )
                self.prompt_entry.delete(0, "end")
        except Exception as exc:
            print(f"Automation generation error: {exc}")
        finally:
            self.gen_btn.configure(state="normal", text="Generate workflow")
            self.refresh_dashboard()

    def refresh_dashboard(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        try:
            from _orunex_libs.automation_daemon import get_daemon

            tasks = get_daemon().get_all_tasks()
        except Exception:
            tasks = []

        if not tasks:
            empty = ctk.CTkFrame(
                self.scroll_frame,
                fg_color=THEME["surface_soft"],
                corner_radius=10,
                border_width=1,
                border_color=THEME["border"],
            )
            empty.pack(fill="x", padx=10, pady=12)
            ctk.CTkLabel(
                empty,
                text="No automations yet.",
                font=("Segoe UI", 13, "bold"),
                text_color=THEME["text"],
            ).pack(pady=(26, 2))
            ctk.CTkLabel(
                empty,
                text="Choose a target or describe a workflow below.",
                font=("Segoe UI", 10),
                text_color=THEME["text_dim"],
            ).pack(pady=(0, 26))
            return

        for task in tasks:
            self._create_list_item(task)

    def _create_list_item(self, task):
        item = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=THEME["surface_soft"],
            corner_radius=10,
            border_width=1,
            border_color=THEME["border"],
        )
        item.pack(fill="x", pady=4, padx=4)

        integration = str(task.get("integration", "System"))
        if integration == "Sistema":
            integration = "System"
        status = str(task.get("status", "activo")).lower()
        is_active = status == "activo"

        info = ctk.CTkFrame(item, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=16, pady=12)

        title_row = ctk.CTkFrame(info, fg_color="transparent")
        title_row.pack(fill="x")
        ctk.CTkLabel(
            title_row,
            text="●",
            font=("Segoe UI", 10),
            text_color=THEME["blue"] if is_active else THEME["muted"],
        ).pack(side="left")
        ctk.CTkLabel(
            title_row,
            text=integration,
            font=("Segoe UI", 11, "bold"),
            text_color=THEME["text"],
        ).pack(side="left", padx=(6, 10))
        ctk.CTkLabel(
            title_row,
            text=_display_frequency(str(task.get("frequency", "diario"))),
            font=("Segoe UI", 9),
            text_color=THEME["text_dim"],
        ).pack(side="left")
        ctk.CTkLabel(
            title_row,
            text="Active" if is_active else "Paused",
            font=("Segoe UI", 9, "bold"),
            text_color=THEME["blue"] if is_active else THEME["text_dim"],
        ).pack(side="right")

        command = str(task.get("command", "No command"))
        if len(command) > 96:
            command = command[:93] + "..."
        ctk.CTkLabel(
            info,
            text=command,
            font=("Consolas", 9),
            text_color=THEME["text_dim"],
            anchor="w",
            justify="left",
        ).pack(fill="x", pady=(5, 0))

        actions = ctk.CTkFrame(item, fg_color="transparent")
        actions.pack(side="right", fill="y", padx=12)
        ctk.CTkButton(
            actions,
            text="Pause" if is_active else "Resume",
            width=64,
            height=28,
            corner_radius=6,
            fg_color=THEME["surface"],
            border_width=1,
            border_color=THEME["border"],
            text_color=THEME["text_dim"],
            hover_color=THEME["surface_muted"],
            font=("Segoe UI", 9),
            command=lambda task_id=task["id"]: self._toggle_task(task_id),
        ).pack(pady=(18, 3))
        ctk.CTkButton(
            actions,
            text="Delete",
            width=64,
            height=28,
            corner_radius=6,
            fg_color="transparent",
            text_color=THEME["red"],
            hover_color=THEME["red_soft"],
            font=("Segoe UI", 9),
            command=lambda task_id=task["id"]: self._delete_task(task_id),
        ).pack()

    def _toggle_task(self, task_id):
        from _orunex_libs.automation_daemon import get_daemon

        if get_daemon().toggle_task(task_id):
            self.refresh_dashboard()

    def _delete_task(self, task_id):
        if not messagebox.askyesno(
            "Delete automation?",
            "This scheduled workflow will be removed permanently.",
        ):
            return
        from _orunex_libs.automation_daemon import get_daemon

        if get_daemon().remove_task(task_id):
            self.refresh_dashboard()
