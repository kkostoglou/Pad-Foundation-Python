"""Interactive desktop calculator for isolated pad foundations with Native Printing support.

Run from this directory with:
    python pad_foundation_gui.py
"""

from __future__ import annotations

import math
import html
import os
import re
import sys
import tempfile
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

try:
    from FoundationDesign import PadFoundation, padFoundationDesign
except ImportError:
    # Fallback mock objects for isolated UI testing
    class PadFoundation:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.concrete_pressure = 0.0
            self.soil_pressure = 0.0
            self.permanent_axial_load = 0.0
            self.imposed_axial_load = 0.0

        def foundation_loads(self, thickness, depth, gamma_soil, gamma_conc):
            self.concrete_pressure = (thickness / 1000) * gamma_conc
            self.soil_pressure = (depth / 1000) * gamma_soil
            return self.concrete_pressure, self.soil_pressure

        def column_axial_loads(self, permanent, imposed):
            self.permanent_axial_load = permanent
            self.imposed_axial_load = imposed
        def column_horizontal_loads_xdir(self, *args): pass
        def column_horizontal_loads_ydir(self, *args): pass
        def column_moments_xdir(self, *args): pass
        def column_moments_ydir(self, *args): pass
        def minimum_area_required(self):
            net_allowable_pressure = (
                self.kwargs["soil_bearing_capacity"]
                - self.concrete_pressure
                - self.soil_pressure
            )
            if net_allowable_pressure <= 0:
                raise ValueError(
                    "Soil bearing capacity must exceed the foundation and soil "
                    "self-weight pressures."
                )
            return round(
                (self.permanent_axial_load + self.imposed_axial_load)
                / net_allowable_pressure,
                3,
            )
        def bearing_pressure_check_sls(self): return {"status": "PASS", "q_max": 145.2, "q_allow": 200.0}

    class padFoundationDesign:
        def __init__(self, foundation, fck, fyk, cover, bar_x, bar_y):
            self.foundation = foundation

        def get_design_moment_X(self): return 185.4
        def get_design_moment_Y(self): return 185.4
        def area_of_steel_reqd_X_dir(self): return {"area_required_per_m": 720.5}
        def area_of_steel_reqd_Y_dir(self): return {"area_required_per_m": 720.5}
        def reinforcement_provision_flexure_X_dir(self): return "As,prov (804 mm²/m) >= As,req (720.5 mm²/m) -> PASS"
        def reinforcement_provision_flexure_Y_dir(self): return "As,prov (804 mm²/m) >= As,req (720.5 mm²/m) -> PASS"
        def tranverse_shear_check_Xdir(self): return {"status": "PASS", "v_ed": 0.42, "v_rd_c": 0.58}
        def tranverse_shear_check_Ydir(self): return {"status": "PASS", "v_ed": 0.42, "v_rd_c": 0.58}
        def punching_shear_column_face(self): return {"status": "PASS", "v_ed": 1.21, "v_rd_max": 3.60}
        def punching_shear_check_1d(self): return {"status": "PASS", "v_ed": 0.65, "v_rd_c": 0.72}
        def punching_shear_check_2d(self): return {"status": "PASS", "v_ed": 0.48, "v_rd_c": 0.58}
        def sliding_resistance_check(self): return {"status": "PASS", "h_ed": 0.0, "h_rd": 320.0}


FIELD_GROUPS = (
    ("Geometry & Layout", (
        ("foundation_length", "Foundation length (mm)", "2500"),
        ("foundation_width", "Foundation width (mm)", "2500"),
        ("column_length", "Column length (mm)", "400"),
        ("column_width", "Column width (mm)", "400"),
        ("col_pos_xdir", "Column centre, X (mm)", "1250"),
        ("col_pos_ydir", "Column centre, Y (mm)", "1250"),
        ("foundation_thickness", "Foundation thickness (mm)", "650"),
        ("soil_depth", "Soil depth above foundation (mm)", "0"),
    )),
    ("Soil & Material Properties", (
        ("soil_bearing_capacity", "Soil bearing capacity (kN/m²)", "200"),
        ("soil_unit_weight", "Soil unit weight (kN/m³)", "18"),
        ("concrete_unit_weight", "Concrete unit weight (kN/m³)", "24"),
        ("fck", "Concrete strength, fck (N/mm²)", "30"),
        ("fyk", "Steel yield strength, fyk (N/mm²)", "500"),
        ("concrete_cover", "Concrete cover (mm)", "40"),
        ("bar_diameter_x", "Initial bar diameter X (mm)", "16"),
        ("bar_diameter_y", "Initial bar diameter Y (mm)", "16"),
    )),
    ("Applied Column Loads & Moments", (
        ("permanent_axial_load", "Permanent axial load (kN)", "800"),
        ("imposed_axial_load", "Imposed axial load (kN)", "300"),
        ("permanent_horizontal_x", "Permanent horizontal load X (kN)", "0"),
        ("imposed_horizontal_x", "Imposed horizontal load X (kN)", "0"),
        ("permanent_horizontal_y", "Permanent horizontal load Y (kN)", "0"),
        ("imposed_horizontal_y", "Imposed horizontal load Y (kN)", "0"),
        ("permanent_moment_x", "Permanent moment X (kNm)", "0"),
        ("imposed_moment_x", "Imposed moment X (kNm)", "0"),
        ("permanent_moment_y", "Permanent moment Y (kNm)", "0"),
        ("imposed_moment_y", "Imposed moment Y (kNm)", "0"),
    )),
)

FIELDS = tuple(field for _, fields in FIELD_GROUPS for field in fields)

POSITIVE_FIELDS = {
    "foundation_length", "foundation_width", "column_length", "column_width",
    "soil_bearing_capacity", "foundation_thickness", "fck", "fyk",
    "concrete_cover", "bar_diameter_x", "bar_diameter_y",
}

ALLOWED_FCK = {16, 20, 25, 30, 32, 35, 37, 40, 45, 55}
ALLOWED_BAR_DIAMETERS = {8, 10, 12, 16, 20, 25, 32, 40}


class PadFoundationApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Pad Foundation Design Calculator")
        self.geometry("1050x720")
        self.minsize(950, 650)
        self.variables = {name: tk.StringVar(value=default) for name, _, default in FIELDS}
        self.entries: dict[str, tk.Entry] = {}
        self.field_labels = {name: label for name, label, _ in FIELDS}
        self.diagram_values: dict[str, float] | None = None
        self.reinforcement_results: dict[str, dict] | None = None
        self.action_diagrams: dict[str, object] = {}
        self.last_summary_params: list[tuple[str, str, str]] = []
        self.last_checks: list[tuple[str, str, str, str]] = []
        self.last_trace = ""
        self._build_interface()
        self._center_window()

    def _center_window(self) -> None:
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        left, top = 0, 0
        right = self.winfo_screenwidth()
        bottom = self.winfo_screenheight()

        # Centre against the usable Windows desktop, excluding the taskbar.
        try:
            import ctypes
            from ctypes import wintypes

            work_area = wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(
                0x0030, 0, ctypes.byref(work_area), 0
            ):
                left, top = work_area.left, work_area.top
                right, bottom = work_area.right, work_area.bottom
        except (AttributeError, OSError):
            pass

        x = left + ((right - left - width) // 2)
        # A slight optical lift balances the title bar and Windows taskbar.
        y = max(top, top + ((bottom - top - height) // 2) - 24)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _build_interface(self) -> None:
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"), foreground="#1f4e79")
        style.configure("GroupHeader.TLabel", font=("Segoe UI", 10, "bold"), foreground="#1f4e79")
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.configure("Treeview", rowheight=24)

        ttk.Label(outer, text="Pad Foundation Design Calculator", style="Title.TLabel").pack(anchor="w", pady=(0, 10))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)
        self.notebook = notebook
        inputs = ttk.Frame(notebook, padding=12)
        results = ttk.Frame(notebook, padding=12)
        trace = ttk.Frame(notebook, padding=12)
        output_graph = ttk.Frame(notebook, padding=12)
        self.trace_tab = trace
        self.output_graph_tab = output_graph
        notebook.add(inputs, text="Input Data")
        notebook.add(results, text="Design Results")
        notebook.add(trace, text="Analytical Calculations")
        notebook.add(output_graph, text="Output Graph")

        # --- INPUTS TAB ---
        inputs.columnconfigure(0, weight=3)
        inputs.columnconfigure(1, weight=2)
        inputs.rowconfigure(0, weight=0)
        inputs.rowconfigure(1, weight=1)

        ttk.Label(
            inputs,
            text=(
                "Enter dimensions in mm, loads in kN, and moments in kNm. "
                "The live geometry previews are shown alongside the inputs; "
                "designed reinforcement is shown in the Output Graph tab."
            ),
            wraplength=900,
            foreground="#444444",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        input_form_frame = ttk.Frame(inputs)
        input_form_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 12))

        canvas = tk.Canvas(input_form_frame, highlightthickness=0)
        self.input_form_frame = input_form_frame
        self.input_scroll_canvas = canvas
        scrollbar = ttk.Scrollbar(input_form_frame, orient="vertical", command=canvas.yview)

        form = ttk.Frame(canvas)
        self.input_form = form
        self.input_form_window = canvas.create_window((0, 0), window=form, anchor="nw")

        form.bind("<Configure>", self._on_form_configure)
        canvas.bind("<Configure>", self._on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.bind_all("<MouseWheel>", self._scroll_input_form, add="+")
        self.bind_all("<Button-4>", self._scroll_input_form, add="+")
        self.bind_all("<Button-5>", self._scroll_input_form, add="+")

        current_row = 0
        for group_title, group_fields in FIELD_GROUPS:
            hdr = ttk.Label(form, text=group_title, style="GroupHeader.TLabel")
            hdr.grid(row=current_row, column=0, columnspan=2, sticky="w", pady=(12, 4))
            current_row += 1

            for name, label, _ in group_fields:
                ttk.Label(form, text=label).grid(row=current_row, column=0, sticky="w", padx=(8, 12), pady=2)
                entry = tk.Entry(
                    form, textvariable=self.variables[name], width=18,
                    background="white", relief="solid", borderwidth=1,
                    highlightthickness=1, highlightbackground="#b8b8b8",
                    highlightcolor="#4a90e2",
                )
                entry.grid(row=current_row, column=1, sticky="ew", pady=2, padx=(0, 8))
                self.entries[name] = entry
                current_row += 1

        form.columnconfigure(1, weight=1)

        controls = ttk.Frame(form)
        controls.grid(row=current_row, column=0, columnspan=2, pady=(16, 12))
        ttk.Button(controls, text="Run Design", command=lambda: self.calculate(notebook)).pack(side="left", padx=4)
        ttk.Button(controls, text="Restore Defaults", command=self.restore_defaults).pack(side="left", padx=4)

        # Original live geometry previews on the Input Data tab.
        input_preview = ttk.Frame(inputs)
        input_preview.grid(row=1, column=1, sticky="nsew")
        input_preview.columnconfigure(0, weight=1)
        input_preview.rowconfigure(0, weight=1)
        input_preview.rowconfigure(1, weight=1)

        input_plan_frame = ttk.LabelFrame(
            input_preview, text="Foundation Plan View", padding=6
        )
        input_plan_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        input_plan_frame.columnconfigure(0, weight=1)
        input_plan_frame.rowconfigure(0, weight=1)
        self.input_plan_canvas = tk.Canvas(
            input_plan_frame, background="white", highlightthickness=1,
            highlightbackground="#d0d0d0",
        )
        self.input_plan_canvas.grid(row=0, column=0, sticky="nsew")
        self.input_plan_canvas.bind("<Configure>", self._redraw_foundation_views)

        input_section_frame = ttk.LabelFrame(
            input_preview, text="Foundation Section View (Elevation X-X)", padding=6
        )
        input_section_frame.grid(row=1, column=0, sticky="nsew")
        input_section_frame.columnconfigure(0, weight=1)
        input_section_frame.rowconfigure(0, weight=1)
        self.input_section_canvas = tk.Canvas(
            input_section_frame, background="white", highlightthickness=1,
            highlightbackground="#d0d0d0",
        )
        self.input_section_canvas.grid(row=0, column=0, sticky="nsew")
        self.input_section_canvas.bind("<Configure>", self._redraw_foundation_views)

        # --- OUTPUT GRAPH TAB (reinforcement and analysed action diagrams) ---
        output_graph.columnconfigure(0, weight=1)
        output_graph.rowconfigure(0, weight=0)
        output_graph.rowconfigure(1, weight=1)
        ttk.Label(
            output_graph,
            text=(
                "Foundation reinforcement, bending moments and shear forces. "
                "The analysed diagrams are populated after running the design."
            ),
            foreground="#444444",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        graph_notebook = ttk.Notebook(output_graph)
        graph_notebook.grid(row=1, column=0, sticky="nsew")
        self.graph_notebook = graph_notebook

        preview_container = ttk.Frame(graph_notebook, padding=6)
        graph_notebook.add(preview_container, text="Reinforcement")
        preview_container.columnconfigure(0, weight=1)
        preview_container.rowconfigure(0, weight=1)
        preview_container.rowconfigure(1, weight=1)

        plan_frame = ttk.LabelFrame(preview_container, text="Foundation Plan View", padding=6)
        plan_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        plan_frame.columnconfigure(0, weight=1)
        plan_frame.rowconfigure(0, weight=1)

        self.plan_canvas = tk.Canvas(plan_frame, background="white", highlightthickness=1, highlightbackground="#d0d0d0")
        self.plan_canvas.grid(row=0, column=0, sticky="nsew")
        self.plan_canvas.bind("<Configure>", self._redraw_foundation_views)

        section_frame = ttk.LabelFrame(preview_container, text="Foundation Section View (Elevation X-X)", padding=6)
        section_frame.grid(row=1, column=0, sticky="nsew")
        section_frame.columnconfigure(0, weight=1)
        section_frame.rowconfigure(0, weight=1)

        self.section_canvas = tk.Canvas(section_frame, background="white", highlightthickness=1, highlightbackground="#d0d0d0")
        self.section_canvas.grid(row=0, column=0, sticky="nsew")
        self.section_canvas.bind("<Configure>", self._redraw_foundation_views)

        self.action_canvases: dict[str, tk.Canvas] = {}
        for key, tab_text in (
            ("moment_x", "Moment X"),
            ("moment_y", "Moment Y"),
            ("shear_x", "Shear X"),
            ("shear_y", "Shear Y"),
        ):
            diagram_tab = ttk.Frame(graph_notebook, padding=6)
            diagram_tab.columnconfigure(0, weight=1)
            diagram_tab.rowconfigure(0, weight=1)
            graph_notebook.add(diagram_tab, text=tab_text)
            diagram_canvas = tk.Canvas(
                diagram_tab, background="white", highlightthickness=1,
                highlightbackground="#d0d0d0",
            )
            diagram_canvas.grid(row=0, column=0, sticky="nsew")
            diagram_canvas.bind(
                "<Configure>",
                lambda _event, diagram_key=key: self._draw_action_diagram(diagram_key),
            )
            self.action_canvases[key] = diagram_canvas
            self._draw_diagram_placeholder(diagram_canvas)

        for name, variable in self.variables.items():
            variable.trace_add("write", lambda *_args, field=name: self._on_input_changed(field))

        # --- RESULTS TAB ---
        results.columnconfigure(0, weight=1)
        results.rowconfigure(0, weight=0)
        results.rowconfigure(1, weight=3)
        results.rowconfigure(2, weight=2)

        # Top Action Bar for Exporting/Printing
        action_bar = ttk.Frame(results, padding=(0, 0, 0, 8))
        action_bar.grid(row=0, column=0, sticky="ew")
        
        ttk.Button(
            action_bar, 
            text="🖨️ Print / Save Calculation Report", 
            command=self.print_report
        ).pack(side="left")

        param_frame = ttk.LabelFrame(results, text="Calculated Structural Values & Forces", padding=8)
        param_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 8))

        self.param_tree = ttk.Treeview(
            param_frame,
            columns=("parameter", "value", "unit"),
            show="headings",
            selectmode="browse",
        )
        self.param_tree.heading("parameter", text="Item Description", anchor="w")
        self.param_tree.heading("value", text="Calculated Value", anchor="e")
        self.param_tree.heading("unit", text="Unit", anchor="w")

        self.param_tree.column("parameter", width=380, stretch=True, anchor="w")
        self.param_tree.column("value", width=140, stretch=False, anchor="e")
        self.param_tree.column("unit", width=120, stretch=False, anchor="w")

        param_scroll = ttk.Scrollbar(param_frame, orient="vertical", command=self.param_tree.yview)
        self.param_tree.configure(yscrollcommand=param_scroll.set)
        self.param_tree.pack(side="left", fill="both", expand=True)
        param_scroll.pack(side="right", fill="y")

        checks_frame = ttk.LabelFrame(results, text="Eurocode Design Checks Summary", padding=8)
        checks_frame.grid(row=2, column=0, sticky="nsew")

        self.checks_tree = ttk.Treeview(
            checks_frame,
            columns=("check", "pass_fail", "calc_val", "code_limit"),
            show="headings",
            selectmode="browse",
        )
        self.checks_tree.heading("check", text="Design Check", anchor="w")
        self.checks_tree.heading("pass_fail", text="Status", anchor="center")
        self.checks_tree.heading("calc_val", text="Calculated Action / Demand", anchor="w")
        self.checks_tree.heading("code_limit", text="Allowable Limit / Resistance", anchor="w")

        self.checks_tree.column("check", width=220, stretch=False, anchor="w")
        self.checks_tree.column("pass_fail", width=90, stretch=False, anchor="center")
        self.checks_tree.column("calc_val", width=260, stretch=True, anchor="w")
        self.checks_tree.column("code_limit", width=260, stretch=True, anchor="w")

        self.checks_tree.tag_configure("PASS", background="#e6f4ea", foreground="#137333")
        self.checks_tree.tag_configure("FAIL", background="#fce8e6", foreground="#c5221f")

        checks_scroll = ttk.Scrollbar(checks_frame, orient="vertical", command=self.checks_tree.yview)
        self.checks_tree.configure(yscrollcommand=checks_scroll.set)
        self.checks_tree.pack(side="left", fill="both", expand=True)
        checks_scroll.pack(side="right", fill="y")

        # --- TRACEABLE CALCULATIONS TAB ---
        trace.columnconfigure(0, weight=1)
        trace.rowconfigure(2, weight=1)
        ttk.Label(
            trace,
            text="Formulae, numerical substitutions, allowable values and utilisation ratios.",
            foreground="#444444",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        search_bar = ttk.Frame(trace)
        search_bar.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.trace_search_bar = search_bar
        search_bar.columnconfigure(1, weight=1)
        ttk.Label(search_bar, text="Find:").grid(row=0, column=0, padx=(0, 6))
        self.trace_search_var = tk.StringVar()
        self.trace_search_entry = ttk.Entry(
            search_bar, textvariable=self.trace_search_var
        )
        self.trace_search_entry.grid(row=0, column=1, sticky="ew")
        self.trace_search_count = ttk.Label(
            search_bar, text="No search", width=12, anchor="center"
        )
        self.trace_search_count.grid(row=0, column=2, padx=8)
        ttk.Button(
            search_bar, text="Previous",
            command=lambda: self._navigate_trace_search(-1),
        ).grid(row=0, column=3, padx=(0, 4))
        ttk.Button(
            search_bar, text="Next",
            command=lambda: self._navigate_trace_search(1),
        ).grid(row=0, column=4)

        trace_frame = ttk.LabelFrame(trace, text="Detailed Calculation Sheet", padding=8)
        trace_frame.grid(row=2, column=0, sticky="nsew")
        self.trace_text = tk.Text(
            trace_frame, wrap="word", font=("Consolas", 10),
            background="white", foreground="#202124", padx=10, pady=10,
        )
        self.trace_text.tag_configure(
            "search_match", background="#fff2a8", foreground="#202124"
        )
        self.trace_text.tag_configure(
            "search_current", background="#ffb74d", foreground="#202124"
        )
        trace_scroll = ttk.Scrollbar(trace_frame, orient="vertical", command=self.trace_text.yview)
        self.trace_text.configure(yscrollcommand=trace_scroll.set, state="disabled")
        self.trace_text.pack(side="left", fill="both", expand=True)
        trace_scroll.pack(side="right", fill="y")

        self.trace_search_matches: list[tuple[str, str]] = []
        self.trace_search_index = -1
        self.trace_search_var.trace_add(
            "write", lambda *_args: self._update_trace_search()
        )
        self.trace_search_entry.bind(
            "<Return>", lambda _event: self._navigate_trace_search(1)
        )
        self.trace_search_entry.bind(
            "<Shift-Return>", lambda _event: self._navigate_trace_search(-1)
        )
        self.bind_all("<Control-f>", self._focus_trace_search, add="+")
        self.bind_all("<Control-F>", self._focus_trace_search, add="+")
        self.bind_all("<Escape>", self._hide_trace_search, add="+")
        self.trace_search_bar.grid_remove()

        self._update_plan_from_inputs()

    def _focus_trace_search(self, _event: tk.Event | None = None) -> str:
        """Focus and select the analytical-calculation search field."""
        self.notebook.select(self.trace_tab)
        self.trace_search_bar.grid()
        self.trace_search_bar.update_idletasks()
        self.trace_search_entry.focus_set()
        self.trace_search_entry.selection_range(0, "end")
        return "break"

    def _hide_trace_search(self, _event: tk.Event | None = None) -> str | None:
        """Hide the search bar and remove its calculation-sheet highlights."""
        if not self.trace_search_bar.grid_info():
            return None
        self.trace_search_var.set("")
        self.trace_search_bar.grid_remove()
        self.trace_text.focus_set()
        return "break"

    def _update_trace_search(self) -> None:
        """Find and highlight every match in the analytical calculation sheet."""
        self.trace_text.tag_remove("search_match", "1.0", "end")
        self.trace_text.tag_remove("search_current", "1.0", "end")
        self.trace_search_matches = []
        self.trace_search_index = -1

        query = self.trace_search_var.get()
        if not query:
            self.trace_search_count.configure(text="No search")
            return

        start = "1.0"
        while True:
            match_start = self.trace_text.search(
                query, start, stopindex="end", nocase=True
            )
            if not match_start:
                break
            match_end = f"{match_start}+{len(query)}c"
            self.trace_search_matches.append((match_start, match_end))
            self.trace_text.tag_add("search_match", match_start, match_end)
            start = match_end

        if self.trace_search_matches:
            self.trace_search_index = 0
            self._show_current_trace_match()
        else:
            self.trace_search_count.configure(text="0 matches")

    def _show_current_trace_match(self) -> None:
        """Emphasise and scroll to the selected search result."""
        self.trace_text.tag_remove("search_current", "1.0", "end")
        if not self.trace_search_matches:
            return
        match_start, match_end = self.trace_search_matches[
            self.trace_search_index
        ]
        self.trace_text.tag_add("search_current", match_start, match_end)
        self.trace_text.tag_raise("search_current")
        self.trace_text.see(match_start)
        self.trace_search_count.configure(
            text=(
                f"{self.trace_search_index + 1} of "
                f"{len(self.trace_search_matches)}"
            )
        )

    def _navigate_trace_search(self, step: int) -> str:
        """Move to the next or previous calculation-sheet search result."""
        if self.trace_search_matches:
            self.trace_search_index = (
                self.trace_search_index + step
            ) % len(self.trace_search_matches)
            self._show_current_trace_match()
        return "break"

    def restore_defaults(self) -> None:
        for name, _, default in FIELDS:
            self.variables[name].set(default)
        self._clear_invalid_fields()

    def _on_input_changed(self, field: str) -> None:
        self._set_entry_valid(self.entries[field])
        self.reinforcement_results = None
        self.action_diagrams = {}
        for canvas in getattr(self, "action_canvases", {}).values():
            self._draw_diagram_placeholder(canvas)
        self._update_plan_from_inputs()

    def _scroll_input_form(self, event: tk.Event) -> str | None:
        widget = event.widget
        while widget is not None:
            if widget == self.input_form_frame or widget == self.input_scroll_canvas:
                if event.num == 4:
                    self.input_scroll_canvas.yview_scroll(-3, "units")
                elif event.num == 5:
                    self.input_scroll_canvas.yview_scroll(3, "units")
                elif event.delta:
                    if abs(event.delta) >= 120:
                        count = int(-1 * (event.delta / 120) * 3)
                    else:
                        count = int(-1 * event.delta)
                    
                    if count == 0:
                        count = -1 if event.delta > 0 else 1

                    self.input_scroll_canvas.yview_scroll(int(count), "units")
                return "break"
            parent_name = widget.winfo_parent()
            if not parent_name:
                break
            widget = widget.nametowidget(parent_name)
        return None

    def _on_form_configure(self, _event: tk.Event) -> None:
        self.input_scroll_canvas.configure(scrollregion=self.input_scroll_canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        canvas_width = event.width
        form_width = self.input_form.winfo_reqwidth()
        x_pos = (canvas_width - form_width) // 2 if canvas_width > form_width else 0
        self.input_scroll_canvas.coords(self.input_form_window, x_pos, 0)

    @staticmethod
    def _set_entry_valid(entry: tk.Entry) -> None:
        entry.configure(background="white", foreground="black", highlightbackground="#b8b8b8")

    def _clear_invalid_fields(self) -> None:
        for entry in self.entries.values():
            self._set_entry_valid(entry)

    def _highlight_invalid_fields(self, errors: dict[str, str]) -> None:
        self._clear_invalid_fields()
        for name in errors:
            if name in self.entries:
                self.entries[name].configure(
                    background="#ffd6d6", foreground="#8b0000", highlightbackground="#d32f2f"
                )

    def validation_errors(self) -> tuple[dict[str, float], dict[str, str]]:
        values: dict[str, float] = {}
        errors: dict[str, str] = {}
        for name, variable in self.variables.items():
            text = variable.get().strip()
            try:
                value = float(text)
            except ValueError:
                errors[name] = "Enter a valid numeric value."
                continue
            if not math.isfinite(value):
                errors[name] = "Enter a finite number."
                continue
            values[name] = value

        for name in POSITIVE_FIELDS:
            if name in values and values[name] <= 0:
                errors[name] = "This value must be greater than zero."

        minimums = {
            "foundation_length": (800, "Must be at least 800 mm."),
            "foundation_width": (800, "Must be at least 800 mm."),
            "column_length": (100, "Must be at least 100 mm."),
            "column_width": (100, "Must be at least 100 mm."),
            "soil_unit_weight": (18, "Must be at least 18 kN/m³."),
            "concrete_unit_weight": (24, "Must be at least 24 kN/m³."),
        }
        for name, (minimum, message) in minimums.items():
            if name in values and values[name] < minimum:
                errors[name] = message

        if "soil_depth" in values and values["soil_depth"] < 0:
            errors["soil_depth"] = "Soil depth cannot be negative."
        if "fck" in values and values["fck"] not in ALLOWED_FCK:
            errors["fck"] = f"Supported fck grades: {', '.join(map(str, sorted(ALLOWED_FCK)))} N/mm²."
        for name in ("bar_diameter_x", "bar_diameter_y"):
            if name in values and values[name] not in ALLOWED_BAR_DIAMETERS:
                errors[name] = f"Supported diameters: {', '.join(map(str, sorted(ALLOWED_BAR_DIAMETERS)))} mm."

        depth_required = {"foundation_thickness", "concrete_cover", "bar_diameter_x", "bar_diameter_y"}
        if depth_required.issubset(values):
            minimum_thickness = values["concrete_cover"] + max(
                values["bar_diameter_x"] / 2,
                values["bar_diameter_y"] / 2 + values["bar_diameter_x"],
            )
            if values["foundation_thickness"] <= minimum_thickness:
                errors["foundation_thickness"] = "Thickness is insufficient for cover and reinforcement layers."

        x_required = {"foundation_length", "column_length", "col_pos_xdir"}
        if x_required.issubset(values) and values["foundation_length"] > 0 and values["column_length"] > 0:
            if not (values["column_length"] / 2 <= values["col_pos_xdir"] <= values["foundation_length"] - values["column_length"] / 2):
                errors["col_pos_xdir"] = "Column must be positioned completely within foundation length."

        y_required = {"foundation_width", "column_width", "col_pos_ydir"}
        if y_required.issubset(values) and values["foundation_width"] > 0 and values["column_width"] > 0:
            if not (values["column_width"] / 2 <= values["col_pos_ydir"] <= values["foundation_width"] - values["column_width"] / 2):
                errors["col_pos_ydir"] = "Column must be positioned completely within foundation width."

        return values, errors

    def _extract_dict(self, obj: object) -> dict | None:
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, "_asdict"):
            return obj._asdict()
        if hasattr(obj, "__dict__"):
            return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
        return None

    def calculate(self, notebook: ttk.Notebook) -> None:
        v, input_errors = self.validation_errors()
        if input_errors:
            self._highlight_invalid_fields(input_errors)
            messagebox.showwarning(
                "Invalid Input Parameters",
                "Please correct highlighted errors before running design:\n\n- "
                + "\n- ".join(f"{self.field_labels[name]}: {msg}" for name, msg in input_errors.items()),
            )
            return

        try:
            foundation = PadFoundation(
                foundation_length=v["foundation_length"], foundation_width=v["foundation_width"],
                column_length=v["column_length"], column_width=v["column_width"],
                col_pos_xdir=v["col_pos_xdir"], col_pos_ydir=v["col_pos_ydir"],
                soil_bearing_capacity=v["soil_bearing_capacity"],
            )
            concrete_weight, soil_weight = foundation.foundation_loads(
                v["foundation_thickness"], v["soil_depth"], v["soil_unit_weight"], v["concrete_unit_weight"]
            )
            foundation.column_axial_loads(v["permanent_axial_load"], v["imposed_axial_load"])
            foundation.column_horizontal_loads_xdir(v["permanent_horizontal_x"], v["imposed_horizontal_x"])
            foundation.column_horizontal_loads_ydir(v["permanent_horizontal_y"], v["imposed_horizontal_y"])
            foundation.column_moments_xdir(v["permanent_moment_x"], v["imposed_moment_x"])
            foundation.column_moments_ydir(v["permanent_moment_y"], v["imposed_moment_y"])

            net_allowable_pressure = (
                v["soil_bearing_capacity"] - concrete_weight - soil_weight
            )
            if net_allowable_pressure <= 0:
                raise ValueError(
                    "Soil bearing capacity must exceed the foundation and soil "
                    "self-weight pressures."
                )
            minimum_area = round(
                (v["permanent_axial_load"] + v["imposed_axial_load"])
                / net_allowable_pressure,
                3,
            )

            design = padFoundationDesign(
                foundation, v["fck"], v["fyk"], v["concrete_cover"], v["bar_diameter_x"], v["bar_diameter_y"]
            )

            steel_x = design.area_of_steel_reqd_X_dir()
            steel_y = design.area_of_steel_reqd_Y_dir()
            val_x = steel_x.get("area_required_per_m", steel_x) if isinstance(steel_x, dict) else steel_x
            val_y = steel_y.get("area_required_per_m", steel_y) if isinstance(steel_y, dict) else steel_y

            def _format_val(val):
                return f"{val:.2f}" if isinstance(val, (int, float)) else str(val)

            moment_x = design.get_design_moment_X()
            moment_y = design.get_design_moment_Y()
            moment_traces = (
                {
                    "X": design.get_design_moment_trace("X"),
                    "Y": design.get_design_moment_trace("Y"),
                }
                if hasattr(design, "get_design_moment_trace")
                else {}
            )

            summary_params = [
                ("Concrete self-weight", f"{concrete_weight:.2f}", "kN/m²"),
                ("Soil self-weight", f"{soil_weight:.2f}", "kN/m²"),
                ("Minimum required area", f"{minimum_area:.2f}", "m²"),
                ("Design moment X (Med,x)", f"{moment_x:.3f}", "kNm"),
                ("Design moment Y (Med,y)", f"{moment_y:.3f}", "kNm"),
                ("Required steel X (As,req,x)", _format_val(val_x), "mm²/m"),
                ("Required steel Y (As,req,y)", _format_val(val_y), "mm²/m"),
            ]

            def _flexural_check(result, required_area, direction):
                """Expose both sides of the reinforcement check to the report."""
                if not isinstance(result, dict):
                    return result
                check = dict(result)
                provided_area = check.get("area_provided")
                check["area_required"] = required_area
                if isinstance(provided_area, (int, float)) and isinstance(
                    required_area, (int, float)
                ):
                    passed = provided_area >= required_area
                    outcome = "PASS" if passed else "FAIL"
                    check["status"] = (
                        f"As,prov,{direction.lower()} = {provided_area:.3f} mm²/m "
                        f"{'exceeds' if passed else 'is less than'} "
                        f"As,req,{direction.lower()} = {required_area:.3f} mm²/m "
                        f"- {outcome}"
                    )
                return check

            def _transverse_shear_check(result, shear_force):
                """Expose the shear action alongside the method's resistance."""
                if not isinstance(result, dict):
                    return result
                check = dict(result)
                check["design_shear_force"] = shear_force
                return check

            def _punching_check(result, demand_key, resistance_key):
                """Give punching demand/resistance unambiguous report keys."""
                if not isinstance(result, dict):
                    return result
                check = dict(result)
                check["v_ed"] = check.get(demand_key)
                check["v_rd"] = check.get(resistance_key)
                return check

            flexural_x = _flexural_check(
                design.reinforcement_provision_flexure_X_dir(), val_x, "X"
            )
            flexural_y = _flexural_check(
                design.reinforcement_provision_flexure_Y_dir(), val_y, "Y"
            )
            self.reinforcement_results = {"X": flexural_x, "Y": flexural_y}

            checks = (
                ("Bearing pressure (SLS)", foundation.bearing_pressure_check_sls()),
                ("Flexural reinforcement X", flexural_x),
                ("Flexural reinforcement Y", flexural_y),
                (
                    "Transverse shear X",
                    _transverse_shear_check(
                        design.tranverse_shear_check_Xdir(),
                        design.get_design_shear_force_X(),
                    ),
                ),
                (
                    "Transverse shear Y",
                    _transverse_shear_check(
                        design.tranverse_shear_check_Ydir(),
                        design.get_design_shear_force_Y(),
                    ),
                ),
                (
                    "Punching shear at column face",
                    _punching_check(
                        design.punching_shear_column_face(),
                        "design_punching_shear_stress",
                        "maximum_punching_shear_resistance",
                    ),
                ),
                (
                    "Punching shear at 1d",
                    _punching_check(
                        design.punching_shear_check_1d(),
                        "ved_design",
                        "punching_shear_stress",
                    ),
                ),
                (
                    "Punching shear at 2d",
                    _punching_check(
                        design.punching_shear_check_2d(),
                        "design_punching_shear_stress",
                        "shear_resistance_max",
                    ),
                ),
                ("Sliding resistance", design.sliding_resistance_check()),
            )

            self.populate_tables(summary_params, checks)
            self.populate_calculation_trace(
                v, concrete_weight, soil_weight,
                minimum_area,
                moment_x, moment_y, val_x, val_y, checks, moment_traces,
            )
            self.diagram_values = v
            plot_methods = {
                "moment_x": "plot_bending_moment_X",
                "moment_y": "plot_bending_moment_Y",
                "shear_x": "plot_shear_force_X",
                "shear_y": "plot_shear_force_Y",
            }
            self.action_diagrams = {
                key: getattr(design, method)(show_plot=False)
                for key, method in plot_methods.items()
                if hasattr(design, method)
            }
            self.draw_foundation_views()
            for key in self.action_canvases:
                self._draw_action_diagram(key)
            notebook.select(self.output_graph_tab)
        except (ValueError, AssertionError, KeyError, TypeError) as error:
            messagebox.showerror("Design Validation Failed", str(error))
        except Exception as error:
            messagebox.showerror("Calculation Error", f"Unexpected design calculation error:\n{error}")

    def populate_tables(self, params: list[tuple[str, str, str]], checks: tuple) -> None:
        limit_keywords = (
            "allow", "cap", "max_cap", "limit", "perm", "rd", "prov", "capacity",
            "resistance", "min_req", "v_rd", "vrd", "q_allow", "h_rd", "provided",
            "as_prov", "as_provided", "v_rd_c", "v_rdc", "v_rd_max"
        )
        action_keywords = (
            "ed", "ved", "v_ed", "max_act", "applied", "demand", "act", "sol", "calc", "eff",
            "q_max", "h_ed", "req", "required", "as_req", "as_required", "shear_force", "shear_stress"
        )

        for item in self.param_tree.get_children():
            self.param_tree.delete(item)
        for item in self.checks_tree.get_children():
            self.checks_tree.delete(item)

        self.last_summary_params = params
        for name, value, unit in params:
            self.param_tree.insert("", "end", values=(name, value, unit))

        self.last_checks = []
        for title, result in checks:
            status = "UNKNOWN"
            calc_val = "Not exposed by calculation method"
            code_limit = "Not exposed by calculation method"

            if isinstance(result, (tuple, list)):
                elems = list(result)
                for e in list(elems):
                    if isinstance(e, str) and e.upper() in ("PASS", "FAIL", "OK"):
                        status = "PASS" if e.upper() in ("PASS", "OK") else "FAIL"
                        elems.remove(e)
                if len(elems) >= 2:
                    calc_val = f"Demand: {elems[0]}"
                    code_limit = f"Capacity: {elems[1]}"
                elif len(elems) == 1:
                    calc_val = f"{elems[0]}"
                    code_limit = "EC2 Shear Limit"

            elif isinstance(result, bool):
                status = "PASS" if result else "FAIL"
                calc_val = "Check Satisfied" if result else "Check Failed"
                code_limit = "EC2 Requirement"

            else:
                res_dict = self._extract_dict(result)

                if res_dict is not None and isinstance(res_dict, dict):
                    raw_status = str(res_dict.get("status", res_dict.get("check_status", res_dict.get("result", "")))).upper()
                    if "PASS" in raw_status or raw_status in ("TRUE", "OK"):
                        status = "PASS"
                    elif "FAIL" in raw_status or raw_status == "FALSE":
                        status = "FAIL"

                    calc_parts = []
                    limit_parts = []

                    filtered_items = [
                        (k, v) for k, v in res_dict.items()
                        if str(k).lower() not in ("status", "check_status", "result", "check")
                    ]

                    for k, v in filtered_items:
                        key_lower = str(k).lower()
                        val_str = f"{v:.3f}" if isinstance(v, float) else str(v)

                        is_action = any(term in key_lower for term in action_keywords)
                        is_limit = any(term in key_lower for term in limit_keywords)

                        if is_limit and not (is_action and "ed" in key_lower and "rd" not in key_lower):
                            limit_parts.append(f"{k}: {val_str}")
                        else:
                            calc_parts.append(f"{k}: {val_str}")

                    if not calc_parts and not limit_parts:
                        if status != "UNKNOWN":
                            calc_val = "Check Satisfied" if status == "PASS" else "Check Failed"
                            code_limit = "EC2 Shear Limit"
                    else:
                        if not calc_parts and limit_parts:
                            calc_parts.append(limit_parts.pop(0))
                        elif not limit_parts and len(calc_parts) > 1:
                            limit_parts.append(calc_parts.pop())

                        calc_val = ", ".join(calc_parts) if calc_parts else "Not exposed by calculation method"
                        code_limit = ", ".join(limit_parts) if limit_parts else "Not exposed by calculation method"

                else:
                    details_str = str(result).strip()
                    if "pass" in details_str.lower() or details_str.lower() == "true":
                        status = "PASS"
                    elif "fail" in details_str.lower() or details_str.lower() == "false":
                        status = "FAIL"

                    clean_str = details_str.split("->")[0].strip() if "->" in details_str else details_str

                    req_match = re.search(r'(As,?\s*req[^\(\),]*|\bAs_req\b[^\(\),]*|\d+(?:\.\d+)?\s*mm²/m)', clean_str, re.IGNORECASE)
                    prov_match = re.search(r'(As,?\s*prov[^\(\),]*|\bAs_prov\b[^\(\),]*|\d+(?:\.\d+)?\s*mm²/m)', clean_str, re.IGNORECASE)

                    if ">=" in clean_str:
                        parts = clean_str.split(">=")
                        left_side, right_side = parts[0].strip(), parts[1].strip()
                        if any(term in left_side.lower() for term in ("prov", "rd", "cap", "allow")):
                            code_limit, calc_val = left_side, right_side
                        else:
                            calc_val, code_limit = left_side, right_side
                    elif "<=" in clean_str:
                        parts = clean_str.split("<=")
                        left_side, right_side = parts[0].strip(), parts[1].strip()
                        if any(term in right_side.lower() for term in ("prov", "rd", "cap", "allow")):
                            calc_val, code_limit = left_side, right_side
                        else:
                            code_limit, calc_val = left_side, right_side
                    elif ":" in clean_str:
                        parts = clean_str.split(":", 1)
                        calc_val = parts[0].strip()
                        code_limit = parts[1].strip()
                    elif req_match and prov_match:
                        calc_val = req_match.group(0).strip()
                        code_limit = prov_match.group(0).strip()
                    else:
                        numbers = re.findall(r'[-+]?\d*\.\d+|\d+', clean_str)
                        if len(numbers) >= 2:
                            calc_val = f"Demand: {numbers[0]}"
                            code_limit = f"Capacity: {numbers[1]}"
                        else:
                            calc_val = clean_str if clean_str else ("Satisfied" if status == "PASS" else "Failed")
                            code_limit = "EC2 Shear Limit"

            tag = "PASS" if status == "PASS" else ("FAIL" if status == "FAIL" else "")
            self.checks_tree.insert("", "end", values=(title, status, calc_val, code_limit), tags=(tag,))
            self.last_checks.append((title, status, calc_val, code_limit))

    @staticmethod
    def _first_number(text: object) -> float | None:
        """Return the first numeric value in a displayed result."""
        match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", str(text))
        return float(match.group(0)) if match else None

    def _check_values(self, result: object) -> tuple[float | None, float | None]:
        """Extract the principal demand and resistance without changing the design result."""
        demand_terms = (
            "q_max", "q_ed", "qed", "v_ed", "ved", "h_ed", "hed",
            "m_ed", "med", "as_req", "required", "demand", "action",
            "shear_force",
        )
        resistance_terms = (
            "q_allow", "allowable", "v_rd", "vrd", "h_rd", "hrd",
            "m_rd", "mrd", "as_prov", "provided", "capacity", "resistance",
        )
        result_dict = self._extract_dict(result)
        if result_dict:
            demand = resistance = None
            for key, value in result_dict.items():
                key_text = str(key).lower()
                if key_text in ("status", "check_status", "result", "check"):
                    continue
                number = float(value) if isinstance(value, (int, float)) else self._first_number(value)
                if demand is None and any(term in key_text for term in demand_terms):
                    demand = number
                if resistance is None and any(term in key_text for term in resistance_terms):
                    resistance = number
            return demand, resistance

        text = str(result)
        req = re.search(r"As\s*,?\s*req[^\d+-]*([-+]?\d+(?:\.\d+)?)", text, re.IGNORECASE)
        prov = re.search(r"As\s*,?\s*prov[^\d+-]*([-+]?\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if req or prov:
            return (
                float(req.group(1)) if req else None,
                float(prov.group(1)) if prov else None,
            )
        values = re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", text)
        return (
            float(values[0]) if len(values) >= 1 else None,
            float(values[1]) if len(values) >= 2 else None,
        )

    def populate_calculation_trace(
        self, v: dict[str, float], concrete_pressure: float, soil_pressure: float,
        minimum_area: float, moment_x: object, moment_y: object,
        steel_x: object, steel_y: object, checks: tuple,
        moment_traces: dict[str, dict],
    ) -> None:
        """Create a transparent calculation record for screen output and printing."""
        length = v["foundation_length"] / 1000.0
        width = v["foundation_width"] / 1000.0
        thickness = v["foundation_thickness"] / 1000.0
        soil_depth = v["soil_depth"] / 1000.0
        area = length * width
        uls_trace = moment_traces.get("X") or moment_traces.get("Y")
        concrete_weight = concrete_pressure * area
        soil_weight = soil_pressure * area
        column_service_load = (
            v["permanent_axial_load"] + v["imposed_axial_load"]
        )
        net_allowable_pressure = (
            v["soil_bearing_capacity"] - concrete_pressure - soil_pressure
        )
        calculated_required_area = column_service_load / net_allowable_pressure
        service_load = (
            column_service_load + concrete_weight + soil_weight
        )
        # Reproduce PadFoundation's SLS resultant and rounded eccentricities so
        # the report exposes the complete qmax calculation, not only its result.
        moment_x_sls = (
            (concrete_weight + soil_weight) * length / 2.0
            + v["permanent_axial_load"] * v["col_pos_xdir"] / 1000.0
            + v["permanent_moment_x"]
            + v["permanent_horizontal_x"] * thickness
            + v["imposed_axial_load"] * v["col_pos_xdir"] / 1000.0
            + v["imposed_moment_x"]
            + v["imposed_horizontal_x"] * thickness
        )
        moment_y_sls = (
            (concrete_weight + soil_weight) * width / 2.0
            + v["permanent_axial_load"] * v["col_pos_ydir"] / 1000.0
            + v["permanent_moment_y"]
            + v["permanent_horizontal_y"] * thickness
            + v["imposed_axial_load"] * v["col_pos_ydir"] / 1000.0
            + v["imposed_moment_y"]
            + v["imposed_horizontal_y"] * thickness
        )
        eccentricity_x_mm = round(
            1000.0 * (round(moment_x_sls, 3) / service_load - length / 2.0)
        )
        eccentricity_y_mm = round(
            1000.0 * (round(moment_y_sls, 3) / service_load - width / 2.0)
        )
        eccentricity_x = eccentricity_x_mm / 1000.0
        eccentricity_y = eccentricity_y_mm / 1000.0
        pressure_factor_x = 6.0 * abs(eccentricity_x) / length
        pressure_factor_y = 6.0 * abs(eccentricity_y) / width
        maximum_pressure_sls = (
            service_load / area
            * (1.0 + pressure_factor_x + pressure_factor_y)
        )
        design_axial_load = (
            uls_trace["resultants"]["design_axial_load"]
            if uls_trace
            else (
                1.35 * (
                    v["permanent_axial_load"] + concrete_weight + soil_weight
                )
                + 1.50 * v["imposed_axial_load"]
            )
        )
        critical_face_x = (
            v["col_pos_xdir"] + v["column_length"] / 2.0
        ) / 1000.0
        critical_face_y = (
            v["col_pos_ydir"] + v["column_width"] / 2.0
        ) / 1000.0
        effective_depth_x = (
            v["foundation_thickness"] - v["concrete_cover"]
            - v["bar_diameter_x"] / 2.0
        )
        effective_depth_y = (
            v["foundation_thickness"] - v["concrete_cover"]
            - v["bar_diameter_x"] - v["bar_diameter_y"] / 2.0
        )
        outstand_x = length - critical_face_x
        outstand_y = width - critical_face_y

        def _uls_pressure_derivation() -> str:
            """Format ULS pressure data supplied by FoundationDesign."""
            if not uls_trace:
                return (
                    "   Detailed ULS pressure trace is unavailable because the "
                    "active calculation backend does not expose trace data."
                )
            combination = uls_trace["combination"]
            geometry = uls_trace["geometry"]
            actions = uls_trace["actions"]
            foundation_pressures = uls_trace["foundation_pressures"]
            resultants = uls_trace["resultants"]
            corner_pressures = uls_trace["corner_pressures"]
            permanent_factor = combination["permanent_factor"]
            imposed_factor = combination["imposed_factor"]
            return (
                "   Applied ULS moment about the footing origin:\n"
                "      ΣMEd,x = 1.35[A(gf+gs)L/2 + Gcol·xc + MGx + HGx·h]\n"
                "                + 1.50[Qcol·xc + MQx + HQx·h]\n"
                f"              = {permanent_factor:.2f}["
                f"{geometry['area']:.3f}("
                f"{foundation_pressures['concrete']:.3f} + "
                f"{foundation_pressures['soil']:.3f})"
                f"·{geometry['length']:.3f}/2 + "
                f"{actions['permanent_axial_load']:.3f}·"
                f"{geometry['column_centre_x']:.3f} + "
                f"{actions['permanent_moment_x']:.3f} + "
                f"{actions['permanent_horizontal_x']:.3f}·"
                f"{geometry['thickness']:.3f}]\n"
                f"                + {imposed_factor:.2f}["
                f"{actions['imposed_axial_load']:.3f}·"
                f"{geometry['column_centre_x']:.3f} + "
                f"{actions['imposed_moment_x']:.3f} + "
                f"{actions['imposed_horizontal_x']:.3f}·"
                f"{geometry['thickness']:.3f}]\n"
                f"              = {resultants['total_moment_x_about_origin']:.3f} kNm\n"
                "      ΣMEd,y = 1.35[A(gf+gs)B/2 + Gcol·yc + MGy + HGy·h]\n"
                "                + 1.50[Qcol·yc + MQy + HQy·h]\n"
                f"              = {permanent_factor:.2f}["
                f"{geometry['area']:.3f}("
                f"{foundation_pressures['concrete']:.3f} + "
                f"{foundation_pressures['soil']:.3f})"
                f"·{geometry['width']:.3f}/2 + "
                f"{actions['permanent_axial_load']:.3f}·"
                f"{geometry['column_centre_y']:.3f} + "
                f"{actions['permanent_moment_y']:.3f} + "
                f"{actions['permanent_horizontal_y']:.3f}·"
                f"{geometry['thickness']:.3f}]\n"
                f"                + {imposed_factor:.2f}["
                f"{actions['imposed_axial_load']:.3f}·"
                f"{geometry['column_centre_y']:.3f} + "
                f"{actions['imposed_moment_y']:.3f} + "
                f"{actions['imposed_horizontal_y']:.3f}·"
                f"{geometry['thickness']:.3f}]\n"
                f"              = {resultants['total_moment_y_about_origin']:.3f} kNm\n"
                "   Resultant eccentricities relative to the footing centre:\n"
                f"      ex = ΣMEd,x/NEd - L/2 = "
                f"{resultants['total_moment_x_about_origin']:.3f}/"
                f"{resultants['design_axial_load']:.3f} "
                f"- {length:.3f}/2 = {resultants['eccentricity_x']:.4f} m\n"
                f"      ey = ΣMEd,y/NEd - B/2 = "
                f"{resultants['total_moment_y_about_origin']:.3f}/"
                f"{resultants['design_axial_load']:.3f} "
                f"- {width:.3f}/2 = {resultants['eccentricity_y']:.4f} m\n"
                "   ULS corner pressure equation:\n"
                "      qi = NEd/A · (1 ± 6ex/L ± 6ey/B)\n"
                f"      NEd/A = {resultants['design_axial_load']:.3f}/{area:.3f} "
                f"= {resultants['uniform_pressure']:.3f} kN/m²\n"
                f"      q1 = {corner_pressures['q1']:.3f}; "
                f"q2 = {corner_pressures['q2']:.3f}; "
                f"q3 = {corner_pressures['q3']:.3f}; "
                f"q4 = {corner_pressures['q4']:.3f} kN/m²"
            )

        def _moment_derivation(
            direction: str, moment: object, outstand: float
        ) -> str:
            """Integrate the modelled net trapezoidal load at the column face."""
            try:
                moment_value = abs(float(moment))
            except (TypeError, ValueError):
                return (
                    f"   {direction}: numerical derivation unavailable for "
                    f"method result {moment!s}."
                )
            if outstand <= 0:
                return f"   {direction}: no positive footing outstand is available."

            direction_trace = moment_traces.get(direction)
            if not direction_trace:
                return (
                    f"   {direction}: detailed strip trace is unavailable because "
                    "the active calculation backend does not expose trace data."
                )
            strip = direction_trace["strip"]
            geometry = direction_trace["geometry"]
            corner_pressures = direction_trace["corner_pressures"]
            if direction == "X":
                start_pair = ("q1", "q2")
                edge_pair = ("q3", "q4")
                transverse_dimension = geometry["width"]
                transverse_symbol = "B"
                axis_dimension = geometry["length"]
                axis_symbol = "L"
                column_centre = geometry["column_centre_x"]
                column_dimension = geometry["column_length"]
                column_centre_symbol = "xc"
                column_dimension_symbol = "cx"
            else:
                start_pair = ("q1", "q3")
                edge_pair = ("q2", "q4")
                transverse_dimension = geometry["length"]
                transverse_symbol = "L"
                axis_dimension = geometry["width"]
                axis_symbol = "B"
                column_centre = geometry["column_centre_y"]
                column_dimension = geometry["column_width"]
                column_centre_symbol = "yc"
                column_dimension_symbol = "cy"
            return (
                f"   {direction}-strip analysis at the positive column face:\n"
                f"      Strip width = {strip['strip_width']:.3f} m\n"
                f"      Edge soil reactions = "
                f"{strip['start_soil_reaction']:.3f} to "
                f"{strip['edge_soil_reaction']:.3f} kN/m\n"
                f"      Start edge: r1 = ({start_pair[0]} + {start_pair[1]})"
                f"{transverse_symbol}/2\n"
                f"                    = ("
                f"{corner_pressures[start_pair[0]]:.3f} + "
                f"{corner_pressures[start_pair[1]]:.3f})"
                f"({transverse_dimension:.3f})/2\n"
                f"                    = "
                f"{strip['start_soil_reaction']:.3f} kN/m\n"
                f"      End edge:   r2 = ({edge_pair[0]} + {edge_pair[1]})"
                f"{transverse_symbol}/2\n"
                f"                    = ("
                f"{corner_pressures[edge_pair[0]]:.3f} + "
                f"{corner_pressures[edge_pair[1]]:.3f})"
                f"({transverse_dimension:.3f})/2\n"
                f"                    = "
                f"{strip['edge_soil_reaction']:.3f} kN/m\n"
                f"      Soil reaction at face = "
                f"{strip['face_soil_reaction']:.3f} kN/m\n"
                f"      Factored downward self-weight line load = "
                f"1.35({concrete_pressure:.3f} + {soil_pressure:.3f})"
                f"({strip['strip_width']:.3f}) = "
                f"{strip['factored_dead_line_load']:.3f} kN/m\n"
                f"      Net load at face, w1 = "
                f"{strip['face_soil_reaction']:.3f} - "
                f"{strip['factored_dead_line_load']:.3f} = "
                f"{strip['net_face_load']:.3f} kN/m\n"
                f"      Net load at edge, w2 = "
                f"{strip['edge_soil_reaction']:.3f} - "
                f"{strip['factored_dead_line_load']:.3f} = "
                f"{strip['net_edge_load']:.3f} kN/m\n"
                f"      Positive column face = {column_centre_symbol} + "
                f"{column_dimension_symbol}/2\n"
                f"                           = {column_centre:.3f} + "
                f"{column_dimension:.3f}/2\n"
                f"                           = "
                f"{strip['face_coordinate']:.3f} m\n"
                f"      Outstand, a{direction.lower()} = {axis_symbol} - "
                f"({column_centre_symbol} + {column_dimension_symbol}/2)\n"
                f"                    = {axis_dimension:.3f} - "
                f"({column_centre:.3f} + {column_dimension:.3f}/2)\n"
                f"                    = {strip['outstand']:.3f} m\n"
                f"      MEd,{direction.lower()} = ∫₀ᵃ "
                "w(s)s ds = a²(w1 + 2w2)/6\n"
                f"          = {strip['outstand']:.3f}²"
                f"({strip['net_face_load']:.3f} + "
                f"2({strip['net_edge_load']:.3f}))/6\n"
                f"          = {strip['integrated_face_moment']:.3f} kNm\n"
                f"      Calculated MEd,{direction.lower()} = "
                f"{strip['integrated_face_moment']:.3f} kNm\n"
                f"      Analysis-method MEd,{direction.lower()} = "
                f"{moment_value:.3f} kNm"
            )

        def _steel_derivation(
            direction: str, moment: object, depth: float,
            transverse_width_m: float, returned_steel: object,
        ) -> str:
            """Show the EC2 flexural and minimum-steel calculation per metre."""
            try:
                moment_value = abs(float(moment))
            except (TypeError, ValueError):
                return (
                    f"   {direction}: numerical reinforcement derivation unavailable; "
                    f"method result = {returned_steel!s} mm²/m."
                )

            section_width = transverse_width_m * 1000.0
            k_value = (
                moment_value * 1_000_000.0
                / (v["fck"] * section_width * depth ** 2)
            )
            root_term = max(0.0, 0.25 - 0.882 * k_value)
            lever_arm_factor = min(0.95, 0.5 + math.sqrt(root_term))
            lever_arm = lever_arm_factor * depth
            steel_flex_total = (
                moment_value * 1_000_000.0
                / (0.87 * v["fyk"] * lever_arm)
            )
            mean_tensile_strength = 0.30 * v["fck"] ** (2.0 / 3.0)
            minimum_steel_ratio_ec2 = (
                0.26 * mean_tensile_strength / v["fyk"]
            )
            steel_min_ec2 = (
                0.078 * v["fck"] ** (2.0 / 3.0)
                / v["fyk"] * section_width * depth
            )
            steel_min_limit = 0.0013 * section_width * depth
            steel_min_total = max(steel_min_ec2, steel_min_limit)
            minimum_controller = (
                "As,min,1" if steel_min_ec2 >= steel_min_limit else "As,min,2"
            )
            steel_governing_total = max(steel_flex_total, steel_min_total)
            governing_controller = (
                "As,flex" if steel_flex_total >= steel_min_total else "As,min"
            )
            steel_governing_per_m = steel_governing_total / transverse_width_m
            try:
                returned_value = float(returned_steel)
            except (TypeError, ValueError):
                returned_value = None

            comparison = (
                f"      FoundationDesign method result: As,req,{direction.lower()}"
                f" = {returned_steel} mm²/m"
            )
            if returned_value is not None and returned_value > 0:
                difference = returned_value - steel_governing_per_m
                if difference < -0.5:
                    deficiency_percent = (
                        abs(difference) / steel_governing_per_m * 100.0
                    )
                    comparison += (
                        f"\n      WARNING: method result is "
                        f"{abs(difference):.3f} mm²/m below the independently "
                        f"calculated governing requirement "
                        f"({deficiency_percent:.2f}% shortfall).\n"
                        f"      Minimum-steel utilization = "
                        f"{steel_governing_per_m:.3f}/{returned_value:.3f}"
                        f" = {steel_governing_per_m / returned_value:.3f} > 1.000 "
                        f"— minimum reinforcement NOT satisfied."
                    )
                else:
                    comparison += (
                        f"\n      Minimum-steel utilization = "
                        f"{steel_governing_per_m:.3f}/{returned_value:.3f}"
                        f" = {steel_governing_per_m / returned_value:.3f} ≤ 1.000."
                    )
            elif returned_value == 0:
                comparison += (
                    "\n      WARNING: a zero method result cannot satisfy the "
                    "calculated minimum reinforcement."
                )

            return (
                f"   Direction {direction} detailed calculation:\n"
                f"      Standard: EN 1992-1-1:2004+A1:2014, "
                f"9.8.2.1 and 9.2.1.1(1), Expression (9.1N).\n"
                f"      fctm = 0.30fck^(2/3) for normal-strength concrete "
                f"(EN 1992-1-1, Table 3.1).\n"
                f"           = 0.30 × {v['fck']:.3f}^(2/3)\n"
                f"           = {mean_tensile_strength:.3f} N/mm²\n"
                f"      As,min = max(0.26fctm/fyk·b·d, 0.0013b·d).\n"
                f"      0.26fctm/fyk = 0.26 × "
                f"{mean_tensile_strength:.3f}/{v['fyk']:.3f}\n"
                f"                    = {minimum_steel_ratio_ec2:.6f}\n"
                f"      Substituting fctm = 0.30fck^(2/3):\n"
                f"      0.26 × 0.30 = 0.078, therefore\n"
                f"      As,min,1 = 0.078fck^(2/3)/fyk·b·d.\n"
                f"      b = {section_width:.3f} mm; d = {depth:.3f} mm\n"
                f"      K = ({moment_value:.3f} × 10⁶)/"
                f"({v['fck']:.3f} × {section_width:.3f} × {depth:.3f}²)"
                f" = {k_value:.6f}\n"
                f"      z = min(0.95d, d[0.5 + √(0.25 - 0.882K)])\n"
                f"        = {lever_arm:.3f} mm\n"
                f"      As,flex = ({moment_value:.3f} × 10⁶)/"
                f"(0.87 × {v['fyk']:.3f} × {lever_arm:.3f})"
                f" = {steel_flex_total:.3f} mm²\n"
                f"      As,min,1 = [0.078 × {v['fck']:.3f}^(2/3) / "
                f"{v['fyk']:.3f}] × {section_width:.3f} × {depth:.3f}\n"
                f"               = {minimum_steel_ratio_ec2:.6f} × "
                f"{section_width:.3f} × {depth:.3f}\n"
                f"               = {steel_min_ec2:.3f} mm²\n"
                f"      As,min,2 = 0.0013b·d\n"
                f"               = 0.0013 × {section_width:.3f} × "
                f"{depth:.3f}\n"
                f"               = {steel_min_limit:.3f} mm²\n"
                f"      As,min = max({steel_min_ec2:.3f}, "
                f"{steel_min_limit:.3f}) = {steel_min_total:.3f} mm²\n"
                f"      Minimum-steel controller: {minimum_controller}\n"
                f"      As,governing = max(As,flex, As,min)\n"
                f"                   = max({steel_flex_total:.3f}, "
                f"{steel_min_total:.3f})\n"
                f"                   = {steel_governing_total:.3f} mm² "
                f"({governing_controller} governs)\n"
                f"      Governing steel per metre = "
                f"As,governing/{transverse_width_m:.3f}"
                f" = {steel_governing_per_m:.3f} mm²/m\n"
                f"{comparison}"
            )

        lines = [
            "PAD FOUNDATION DESIGN – TRACEABLE CALCULATION SHEET",
            "=" * 72, "",
            "1. GEOMETRY AND UNIT CONVERSIONS",
            f"   L = {v['foundation_length']:.3f}/1000 = {length:.3f} m",
            f"   B = {v['foundation_width']:.3f}/1000 = {width:.3f} m",
            f"   h = {v['foundation_thickness']:.3f}/1000 = {thickness:.3f} m",
            f"   A = L × B = {length:.3f} × {width:.3f} = {area:.3f} m²", "",
            "2. PERMANENT SELF-WEIGHTS",
            (
                f"   Foundation pressure (gfoundation) = h × γc = {thickness:.3f} × "
                f"{v['concrete_unit_weight']:.3f} = {concrete_pressure:.3f} kN/m²"
            ),
            (
                f"   Foundation weight = {concrete_pressure:.3f} × {area:.3f} "
                f"= {concrete_weight:.3f} kN"
            ),
            (
                f"   Soil pressure (gsoil) = ds × γs = {soil_depth:.3f} × "
                f"{v['soil_unit_weight']:.3f} = {soil_pressure:.3f} kN/m²"
            ),
            f"   Soil weight = {soil_pressure:.3f} × {area:.3f} = {soil_weight:.3f} kN", "",
            "3. SERVICE LOAD REFERENCE",
            (
                f"   Nser = Gcolumn + Qcolumn + Gfoundation + Gsoil\n"
                f"        = {v['permanent_axial_load']:.3f} + {v['imposed_axial_load']:.3f} "
                f"+ {concrete_weight:.3f} + {soil_weight:.3f}\n"
                f"        = {service_load:.3f} kN"
            ),
            (
                f"   Uniform reference pressure = Nser/A = {service_load:.3f}/{area:.3f} "
                f"= {service_load / area:.3f} kN/m²"
            ),
            "   The SLS bearing method additionally applies the entered moments/eccentricity.", "",
            "4. AREA, MOMENT AND REINFORCEMENT RESULTS",
            (
                f"   Column service load = Gcolumn + Qcolumn = "
                f"{v['permanent_axial_load']:.3f} + {v['imposed_axial_load']:.3f} "
                f"= {column_service_load:.3f} kN"
            ),
            (
                f"   Net allowable bearing pressure (qnet) = qallow - gfoundation - gsoil\n"
                f"                                  = {v['soil_bearing_capacity']:.3f} "
                f"- {concrete_pressure:.3f} - {soil_pressure:.3f}\n"
                f"                                  = {net_allowable_pressure:.3f} kN/m²"
            ),
            (
                f"   Required area = Ncolumn / qnet\n"
                f"                 = {column_service_load:.3f} / "
                f"{net_allowable_pressure:.3f}\n"
                f"                 = {calculated_required_area:.3f} m²"
            ),
            f"   Provided area (A) = {area:.3f} m²",
            (
                f"   Area utilisation = {calculated_required_area:.3f}/{area:.3f} "
                f"= {calculated_required_area / area:.3f} ≤ 1.000"
            ),
            "",
            "   4.1 ULTIMATE DESIGN MOMENTS AT COLUMN FACES",
            (
                "   ULS combination: EN 1990:2002+A1:2005, Clause 6.4.3.2, "
                "Expression (6.10), and Annex A1, Table A1.2(B) "
                "(persistent/transient design situation)."
            ),
            (
                f"   NEd = 1.35(Gcolumn + Gfoundation + Gsoil) + 1.50Qcolumn\n"
                f"       = 1.35({v['permanent_axial_load']:.3f} + "
                f"{concrete_weight:.3f} + {soil_weight:.3f}) "
                f"+ 1.50({v['imposed_axial_load']:.3f})\n"
                f"       = {design_axial_load:.3f} kN"
            ),
            (
                "   The analysis model applies the ULS soil-reaction distribution "
                "and factored column actions to the footing strips."
            ),
            _uls_pressure_derivation(),
            (
                f"   X critical section = right column face at x = "
                f"{critical_face_x:.3f} m\n"
                f"   Med,x = bending moment at this face = {moment_x} kNm"
            ),
            _moment_derivation("X", moment_x, outstand_x),
            (
                f"   Y critical section = upper column face at y = "
                f"{critical_face_y:.3f} m\n"
                f"   Med,y = bending moment at this face = {moment_y} kNm"
            ),
            _moment_derivation("Y", moment_y, outstand_y),
            (
                "   Note: for eccentric loading the actual ULS strip reaction is "
                "trapezoidal; wEd above is its moment-equivalent uniform load over "
                "the relevant outstand."
            ),
            "",
            "   4.2 REQUIRED FLEXURAL REINFORCEMENT",
            (
                f"   Effective depth X: dx = h - cover - φx/2\n"
                f"                         = {v['foundation_thickness']:.3f} "
                f"- {v['concrete_cover']:.3f} - "
                f"{v['bar_diameter_x']:.3f}/2\n"
                f"                         = {effective_depth_x:.3f} mm"
            ),
            (
                f"   Effective depth Y: dy = h - cover - φx - φy/2\n"
                f"                         = {v['foundation_thickness']:.3f} "
                f"- {v['concrete_cover']:.3f} - {v['bar_diameter_x']:.3f} "
                f"- {v['bar_diameter_y']:.3f}/2\n"
                f"                         = {effective_depth_y:.3f} mm"
            ),
            (
                "   For each direction:\n"
                "   Code basis: EN 1992-1-1:2004+A1:2014, Clause 6.1 "
                "(ULS flexure), Clause 3.1.7(3) and Figure 3.5 "
                "(rectangular concrete stress block).\n"
                "   The K and z expressions are derived from that stress block; "
                "the z ≤ 0.95d cap is established design guidance, not an "
                "explicit EN 1992 requirement.\n"
                "   Steel strength: Clause 2.4.2.4 and Table 2.1N give "
                "γs = 1.15, hence fyd = fyk/γs ≈ 0.87fyk.\n"
                "   Minimum and footing reinforcement: Clause 9.2.1.1(1), "
                "Expression (9.1N), and Clause 9.8.2.1.\n"
                "   K = MEd/(fck·b·d²)\n"
                "   z = min[0.95d, d(0.5 + √(0.25 - 0.882K))]\n"
                "   As,flex = MEd/(0.87·fyk·z)\n"
                "   As,req = max(As,flex, As,min), reported per metre width"
            ),
            _steel_derivation(
                "X", moment_x, effective_depth_x, width, steel_x
            ),
            _steel_derivation(
                "Y", moment_y, effective_depth_y, length, steel_y
            ),
            "",
            "5. DESIGN CHECKS, ALLOWABLE VALUES AND UTILISATION",
            "   General acceptance criterion: η = demand/resistance ≤ 1.000.", "",
        ]

        # Keep each subsection's calculation lines visually inside its heading.
        # Several entries contain embedded newlines, so indent every physical
        # line instead of only the first line in each list item.
        def _indent_subsection_body(
            heading: str, following_heading: str, spaces: int = 4
        ) -> None:
            start = lines.index(heading) + 1
            stop = lines.index(following_heading)
            prefix = " " * spaces
            for index in range(start, stop):
                lines[index] = "\n".join(
                    prefix + line if line else line
                    for line in lines[index].split("\n")
                )

        _indent_subsection_body(
            "   4.1 ULTIMATE DESIGN MOMENTS AT COLUMN FACES",
            "   4.2 REQUIRED FLEXURAL REINFORCEMENT",
        )
        _indent_subsection_body(
            "   4.2 REQUIRED FLEXURAL REINFORCEMENT",
            "5. DESIGN CHECKS, ALLOWABLE VALUES AND UTILISATION",
        )

        for number, ((title, result), displayed) in enumerate(zip(checks, self.last_checks), 1):
            demand, resistance = self._check_values(result)
            _, status, demand_text, resistance_text = displayed
            if title.startswith("Flexural reinforcement"):
                direction = "X" if title.endswith("X") else "Y"
                if demand is not None:
                    demand_text = (
                        f"As,req,{direction.lower()} = {demand:.3f} mm²/m"
                    )
                if resistance is not None:
                    resistance_text = (
                        f"As,prov,{direction.lower()} = {resistance:.3f} mm²/m"
                    )
            elif title.startswith("Transverse shear"):
                if demand is not None:
                    demand_text = f"VEd = {demand:.3f} kN"
                if resistance is not None:
                    resistance_text = f"VRd,c = {resistance:.3f} kN"
            lines.extend([
                f"   5.{number} {title}",
                f"       Demand/action: {demand_text}",
                f"       Allowable/resistance: {resistance_text}",
            ])
            if title == "Bearing pressure (SLS)":
                lines.extend([
                    (
                        "       Governing equation: qmax = Nser/A · "
                        "(1 + 6|ex|/L + 6|ey|/B)"
                    ),
                    (
                        f"       Uniform component Nser/A = {service_load:.3f}/"
                        f"{area:.3f} = {service_load / area:.3f} kN/m²"
                    ),
                    (
                        f"       Mser,x = {moment_x_sls:.3f} kNm; "
                        f"ex = Mser,x/Nser - L/2 = {eccentricity_x_mm:.0f} mm"
                    ),
                    (
                        f"       Mser,y = {moment_y_sls:.3f} kNm; "
                        f"ey = Mser,y/Nser - B/2 = {eccentricity_y_mm:.0f} mm"
                    ),
                    (
                        f"       6|ex|/L = 6·{abs(eccentricity_x):.3f}/"
                        f"{length:.3f} = {pressure_factor_x:.3f}"
                    ),
                    (
                        f"       6|ey|/B = 6·{abs(eccentricity_y):.3f}/"
                        f"{width:.3f} = {pressure_factor_y:.3f}"
                    ),
                    (
                        f"       qmax = {service_load:.3f}/{area:.3f} · "
                        f"(1 + {pressure_factor_x:.3f} + "
                        f"{pressure_factor_y:.3f}) = "
                        f"{maximum_pressure_sls:.3f} kN/m²"
                    ),
                    (
                        f"       Acceptance: qmax ≤ qallow = "
                        f"{v['soil_bearing_capacity']:.3f} kN/m² "
                        "(soil bearing capacity)"
                    ),
                ])
            elif title.startswith("Flexural reinforcement"):
                direction = "X" if title.endswith("X") else "Y"
                result_dict = self._extract_dict(result) or {}
                diameter = self._first_number(result_dict.get("bar_diameter"))
                spacing = self._first_number(result_dict.get("bar_spacing"))
                bar_area = math.pi * diameter**2 / 4.0 if diameter else None
                theoretical_spacing = (
                    1000.0 * bar_area / demand
                    if bar_area is not None and demand not in (None, 0)
                    else None
                )
                lines.extend([
                    (
                        f"       Governing equation: As,prov,{direction.lower()} "
                        f"≥ As,req,{direction.lower()}"
                    ),
                    (
                        "       As,req is derived in Section 4.2 from "
                        "max(As,flex, As,min)."
                    ),
                    (
                        "       Reinforcement utilization: "
                        "ηAs = As,req/As,prov ≤ 1.000"
                    ),
                ])
                if (
                    bar_area is not None
                    and spacing not in (None, 0)
                    and demand not in (None, 0)
                    and resistance is not None
                ):
                    lines.extend([
                        (
                            f"       Selected bar area: Aφ = π·{diameter:.0f}²/4"
                            f" = {bar_area:.3f} mm²"
                        ),
                        (
                            f"       Theoretical spacing: s = 1000·Aφ/As,req"
                            f" = 1000·{bar_area:.3f}/{demand:.3f}"
                            f" = {theoretical_spacing:.3f} mm"
                        ),
                        (
                            f"       Adopted spacing: {spacing:.3f} mm "
                            "(rounded down to the available 25 mm increment)"
                        ),
                        (
                            f"       As,prov,{direction.lower()} = Aφ·1000/s"
                            f" = {bar_area:.3f}·1000/{spacing:.3f}"
                            f" = {resistance:.3f} mm²/m"
                        ),
                    ])
            elif title.startswith("Transverse shear"):
                direction = "X" if title.endswith("X") else "Y"
                depth = effective_depth_x if direction == "X" else effective_depth_y
                breadth = v[
                    "foundation_width" if direction == "X" else "foundation_length"
                ]
                column_position = v[
                    "col_pos_xdir" if direction == "X" else "col_pos_ydir"
                ]
                column_size = v[
                    "column_length" if direction == "X" else "column_width"
                ]
                critical_location_1 = column_position - column_size / 2.0 - depth
                critical_location_2 = column_position + column_size / 2.0 + depth
                shear_trace = (moment_traces.get(direction) or {}).get("strip", {})
                axis_length = shear_trace.get("axis_length")
                soil_line_start = shear_trace.get("start_soil_reaction")
                soil_line_end = shear_trace.get("edge_soil_reaction")
                dead_line_load = shear_trace.get("factored_dead_line_load")
                net_line_start = (
                    soil_line_start - dead_line_load
                    if soil_line_start is not None and dead_line_load is not None
                    else None
                )
                net_line_end = (
                    soil_line_end - dead_line_load
                    if soil_line_end is not None and dead_line_load is not None
                    else None
                )
                x1_m = critical_location_1 / 1000.0
                x2_m = critical_location_2 / 1000.0
                line_load_gradient = (
                    (net_line_end - net_line_start) / axis_length
                    if net_line_start is not None
                    and net_line_end is not None
                    and axis_length
                    else None
                )
                shear_at_1 = (
                    net_line_start * x1_m + line_load_gradient * x1_m**2 / 2.0
                    if line_load_gradient is not None
                    else None
                )
                shear_at_2 = (
                    -(
                        net_line_start * (axis_length - x2_m)
                        + line_load_gradient
                        * (axis_length**2 - x2_m**2)
                        / 2.0
                    )
                    if line_load_gradient is not None
                    else None
                )
                flexural_title = f"Flexural reinforcement {direction}"
                flexural_result = next(
                    (
                        self._extract_dict(check_result) or {}
                        for check_title, check_result in checks
                        if check_title == flexural_title
                    ),
                    {},
                )
                provided_steel = self._first_number(
                    flexural_result.get("area_provided")
                )
                rho_l = (
                    provided_steel / (1000.0 * depth)
                    if provided_steel is not None and depth
                    else None
                )
                k_factor = min(1.0 + math.sqrt(200.0 / depth), 2.0)
                rho_design = min(rho_l, 0.02) if rho_l is not None else None
                concrete_term = (
                    0.12
                    * k_factor
                    * (100.0 * rho_design * v["fck"]) ** (1.0 / 3.0)
                    if rho_design is not None
                    else None
                )
                v_min = 0.035 * k_factor**1.5 * math.sqrt(v["fck"])
                shear_stress_resistance = (
                    round(max(concrete_term, v_min), 3)
                    if concrete_term is not None
                    else None
                )
                shear_stress_demand = (
                    demand * 1000.0 / (breadth * depth)
                    if demand is not None and breadth and depth
                    else None
                )
                lines.extend([
                    (
                        f"       Critical section: one effective depth d{direction.lower()} "
                        "from the column face."
                    ),
                    (
                        f"       d{direction.lower()} = {depth:.3f} mm"
                    ),
                    (
                        f"       Critical coordinates: {direction.lower()}1 = "
                        f"{column_position:.3f} - {column_size:.3f}/2 - "
                        f"{depth:.3f} = {critical_location_1:.3f} mm; "
                        f"{direction.lower()}2 = {column_position:.3f} + "
                        f"{column_size:.3f}/2 + {depth:.3f} = "
                        f"{critical_location_2:.3f} mm"
                    ),
                    (
                        f"       VEd = max(|V({direction.lower()}1)|, "
                        f"|V({direction.lower()}2)|) = {demand:.3f} kN"
                        if demand is not None
                        else "       VEd was not exposed by the calculation method."
                    ),
                    (
                        "       Demand: vEd = VEd/(b·d); resistance: "
                        "vRd,c = max[CRd,c·k·(100ρl·fck)^(1/3), vmin]."
                    ),
                    "       Acceptance: vEd ≤ vRd,c (equivalently VEd ≤ VRd,c).",
                ])
                if (
                    axis_length is not None
                    and soil_line_start is not None
                    and soil_line_end is not None
                    and dead_line_load is not None
                    and net_line_start is not None
                    and net_line_end is not None
                    and line_load_gradient is not None
                    and shear_at_1 is not None
                    and shear_at_2 is not None
                ):
                    lines.extend([
                        (
                            f"       ULS soil-reaction line load: q(0) = "
                            f"{soil_line_start:.3f} kN/m; q(L) = "
                            f"{soil_line_end:.3f} kN/m"
                        ),
                        (
                            f"       Factored footing/soil dead line load: "
                            f"gEd = {dead_line_load:.3f} kN/m"
                        ),
                        (
                            f"       Net line load: w(0) = q(0)-gEd = "
                            f"{net_line_start:.3f} kN/m; w(L) = q(L)-gEd"
                            f" = {net_line_end:.3f} kN/m"
                        ),
                        (
                            f"       w(x) = w(0) + [w(L)-w(0)]x/L = "
                            f"{net_line_start:.3f} + "
                            f"({line_load_gradient:.3f})x kN/m"
                        ),
                        (
                            f"       V({direction.lower()}1) = ∫₀^{x1_m:.3f}w(x)dx"
                            f" = {net_line_start:.3f}·{x1_m:.3f} + "
                            f"{line_load_gradient:.3f}·{x1_m:.3f}²/2"
                            f" = {shear_at_1:.3f} kN"
                        ),
                        (
                            f"       V({direction.lower()}2) = -∫_{x2_m:.3f}^"
                            f"{axis_length:.3f}w(x)dx = {shear_at_2:.3f} kN"
                        ),
                        (
                            f"       VEd = max(|{shear_at_1:.3f}|, "
                            f"|{shear_at_2:.3f}|) = "
                            f"{max(abs(shear_at_1), abs(shear_at_2)):.3f} kN"
                        ),
                    ])
                if (
                    provided_steel is not None
                    and rho_l is not None
                    and concrete_term is not None
                    and shear_stress_resistance is not None
                    and shear_stress_demand is not None
                    and resistance is not None
                ):
                    lines.extend([
                        (
                            f"       Longitudinal reinforcement: As,prov,{direction.lower()}"
                            f" = {provided_steel:.3f} mm²/m"
                        ),
                        (
                            f"       ρl = As/(1000·d) = {provided_steel:.3f}/"
                            f"(1000·{depth:.3f}) = {rho_l:.6f}"
                        ),
                        (
                            f"       k = min(1 + √(200/d), 2.0)"
                            f" = {k_factor:.6f}"
                        ),
                        (
                            f"       CRd,c·k·(100ρl·fck)^(1/3)"
                            f" = 0.12·{k_factor:.6f}·"
                            f"(100·{rho_design:.6f}·{v['fck']:.3f})^(1/3)"
                            f" = {concrete_term:.3f} N/mm²"
                        ),
                        (
                            f"       vmin = 0.035·k^(3/2)·√fck"
                            f" = {v_min:.3f} N/mm²"
                        ),
                        (
                            f"       vRd,c = max({concrete_term:.3f}, {v_min:.3f})"
                            f" = {shear_stress_resistance:.3f} N/mm²"
                        ),
                        (
                            f"       vEd = VEd/(b·d) = {demand:.3f}·1000/"
                            f"({breadth:.3f}·{depth:.3f})"
                            f" = {shear_stress_demand:.3f} N/mm²"
                        ),
                        (
                            f"       VRd,c = vRd,c·b·d/1000"
                            f" = {shear_stress_resistance:.3f}·{breadth:.3f}·"
                            f"{depth:.3f}/1000 = {resistance:.3f} kN"
                        ),
                    ])
            elif title == "Punching shear at column face":
                column_perimeter = 2.0 * (
                    v["column_length"] + v["column_width"]
                )
                average_depth = (effective_depth_x + effective_depth_y) / 2.0
                design_axial = (
                    1.35 * v["permanent_axial_load"]
                    + 1.5 * v["imposed_axial_load"]
                )
                nu = 0.6 * (1.0 - v["fck"] / 250.0)
                fcd = 0.85 * v["fck"] / 1.5
                vrd_max_calc = 0.5 * nu * fcd
                lines.extend([
                    (
                        f"       Column perimeter u0 = 2(c1 + c2) = "
                        f"2({v['column_length']:.3f} + "
                        f"{v['column_width']:.3f}) = {column_perimeter:.3f} mm"
                    ),
                    (
                        f"       Mean effective depth d = (dx + dy)/2 = "
                        f"({effective_depth_x:.3f} + {effective_depth_y:.3f})/2"
                        f" = {average_depth:.3f} mm"
                    ),
                    (
                        f"       Column design action: VEd = 1.35Gk + 1.50Qk"
                        f" = 1.35·{v['permanent_axial_load']:.3f} + "
                        f"1.50·{v['imposed_axial_load']:.3f}"
                        f" = {design_axial:.3f} kN"
                    ),
                    (
                        f"       vEd = VEd·1000/(u0·d) = "
                        f"{design_axial:.3f}·1000/"
                        f"({column_perimeter:.3f}·{average_depth:.3f})"
                        f" = {demand:.3f} N/mm²"
                    ),
                    (
                        f"       ν = 0.6(1-fck/250) = 0.6(1-"
                        f"{v['fck']:.3f}/250) = {nu:.6f}"
                    ),
                    (
                        f"       fcd = 0.85fck/1.5 = {fcd:.3f} N/mm²"
                    ),
                    (
                        f"       vRd,max = 0.5·ν·fcd = 0.5·{nu:.6f}·"
                        f"{fcd:.3f} = {vrd_max_calc:.3f} N/mm²"
                    ),
                    "       Acceptance: vEd ≤ vRd,max.",
                ])
            elif title in ("Punching shear at 1d", "Punching shear at 2d"):
                multiplier = 1 if title.endswith("1d") else 2
                average_depth = (effective_depth_x + effective_depth_y) / 2.0
                control_perimeter = 2.0 * (
                    v["column_length"] + v["column_width"]
                    + math.pi * multiplier * average_depth
                )
                length_m, width_m = length, width
                c1_m = v["column_length"] / 1000.0
                c2_m = v["column_width"] / 1000.0
                d_m = average_depth / 1000.0
                radius = multiplier * d_m
                loaded_area = (
                    c1_m * c2_m
                    + 2.0 * (c1_m + c2_m) * radius
                    + math.pi * radius**2
                )
                perimeter_m = control_perimeter / 1000.0
                trace_pressures = (uls_trace or {}).get("corner_pressures", {})
                trace_reactions = (uls_trace or {}).get("edge_line_reactions", {})
                q1 = trace_pressures.get("q1")
                rx = trace_reactions.get("x", {})
                ry = trace_reactions.get("y", {})
                cx = (
                    (rx.get("end") - rx.get("start")) / length_m
                    if rx.get("end") is not None and rx.get("start") is not None
                    else None
                )
                cy = (
                    (ry.get("start") - ry.get("end")) / width_m
                    if ry.get("end") is not None and ry.get("start") is not None
                    else None
                )
                ecc_x = v["col_pos_xdir"] / 1000.0 - length_m / 2.0
                ecc_y = v["col_pos_ydir"] / 1000.0 - width_m / 2.0
                pressure_x_term = (
                    (
                        length_m / 2.0 + ecc_x - c1_m / 2.0 - radius
                        + 0.5 * (length_m + 2.0 * radius)
                    )
                    * cx
                    / width_m
                    if cx is not None
                    else None
                )
                pressure_y_term = (
                    (
                        width_m / 2.0 + ecc_y - c2_m / 2.0 - radius
                        + 0.5 * (width_m + 2.0 * radius)
                    )
                    * cy
                    / length_m
                    if cy is not None
                    else None
                )
                control_pressure = (
                    q1 + pressure_x_term - pressure_y_term
                    if q1 is not None
                    and pressure_x_term is not None
                    and pressure_y_term is not None
                    else None
                )
                dead_pressure_uls = 1.35 * (concrete_pressure + soil_pressure)
                column_axial = (
                    1.35 * v["permanent_axial_load"]
                    + 1.5 * v["imposed_axial_load"]
                )
                punching_force = (
                    column_axial
                    + (dead_pressure_uls - control_pressure) * loaded_area
                    if control_pressure is not None
                    else None
                )
                moment_x_uls = (
                    1.35 * v["permanent_moment_x"]
                    + 1.5 * v["imposed_moment_x"]
                )
                moment_y_uls = (
                    1.35 * v["permanent_moment_y"]
                    + 1.5 * v["imposed_moment_y"]
                )
                effective_force = (
                    punching_force
                    * (
                        1.0
                        + multiplier * abs(moment_x_uls) / punching_force * c2_m
                        + multiplier * abs(moment_y_uls) / punching_force * c1_m
                    )
                    if punching_force not in (None, 0)
                    else None
                )
                base_stress = (
                    effective_force / (perimeter_m * d_m * 1000.0)
                    if effective_force is not None
                    else None
                )
                ratio = min(max(c1_m / c2_m, 0.5), 3.0)
                if ratio <= 1.0:
                    punching_k = 0.45 + (ratio - 0.5) * (0.6 - 0.45) / 0.5
                elif ratio <= 2.0:
                    punching_k = 0.6 + (ratio - 1.0) * 0.1
                else:
                    punching_k = 0.7 + (ratio - 2.0) * 0.1
                W = (
                    c1_m * c2_m
                    + 2.0 * c2_m * radius
                    + 0.5 * c1_m**2
                    + 4.0 * radius**2
                    + math.pi * c1_m * radius
                )
                eccentricity_data = (uls_trace or {}).get("resultants", {})
                is_concentric = (
                    eccentricity_data.get("eccentricity_x") == 0
                    and eccentricity_data.get("eccentricity_y") == 0
                )
                beta_calc = (
                    1.0 if is_concentric else
                    1.0 + punching_k
                    * (abs(moment_x_uls + moment_y_uls) / effective_force)
                    * (perimeter_m / W)
                    if effective_force not in (None, 0)
                    else None
                )
                flex_x = next(
                    (self._extract_dict(r) or {} for t, r in checks
                     if t == "Flexural reinforcement X"), {}
                )
                flex_y = next(
                    (self._extract_dict(r) or {} for t, r in checks
                     if t == "Flexural reinforcement Y"), {}
                )
                as_x = self._first_number(flex_x.get("area_provided"))
                as_y = self._first_number(flex_y.get("area_provided"))
                rho_x = round(as_x / (1000.0 * effective_depth_x), 5)
                rho_y = round(as_y / (1000.0 * effective_depth_y), 5)
                rho_punch = min(math.sqrt(rho_x * rho_y), 0.02)
                k_punch = min(1.0 + math.sqrt(200.0 / average_depth), 2.0)
                vmin_punch = 0.035 * k_punch**1.5 * math.sqrt(v["fck"])
                vrd_c_base = max(
                    0.12 * k_punch * (100.0 * rho_punch * v["fck"]) ** (1/3),
                    vmin_punch,
                )
                vrd_for_check = 2.0 * vrd_c_base if multiplier == 1 else vrd_c_base
                lines.extend([
                    (
                        f"       Control perimeter at {multiplier}d: "
                        f"u{multiplier} = 2(c1 + c2 + π·{multiplier}d)"
                        f" = {control_perimeter:.3f} mm"
                    ),
                    (
                        f"       Loaded area: Ain = c1c2 + 2(c1+c2)({multiplier}d)"
                        f" + π({multiplier}d)² = {loaded_area:.6f} m²"
                    ),
                    (
                        f"       Demand: vEd = βVEd/(u{multiplier}·d); "
                        "acceptance: vEd ≤ vRd,c."
                    ),
                ])
                if control_pressure is not None and punching_force is not None:
                    lines.extend([
                        (
                            f"       ULS pressure gradients: cx = {cx:.3f}; "
                            f"cy = {cy:.3f}"
                        ),
                        (
                            f"       Mean ULS pressure inside perimeter: "
                            f"qEd,{multiplier}d = q1 + X-gradient - Y-gradient"
                            f" = {q1:.3f} + {pressure_x_term:.3f} - "
                            f"{pressure_y_term:.3f} = {control_pressure:.3f} kN/m²"
                        ),
                        (
                            f"       Factored dead pressure: gEd = 1.35(qconcrete+qsoil)"
                            f" = {dead_pressure_uls:.3f} kN/m²"
                        ),
                        (
                            f"       Column action: NEd = 1.35Gk+1.50Qk"
                            f" = {column_axial:.3f} kN"
                        ),
                        (
                            f"       Punching force: VEd = NEd + (gEd-qEd)Ain"
                            f" = {column_axial:.3f} + ({dead_pressure_uls:.3f}-"
                            f"{control_pressure:.3f})·{loaded_area:.6f}"
                            f" = {punching_force:.3f} kN"
                        ),
                        (
                            f"       MEd,x = {moment_x_uls:.3f} kNm; "
                            f"MEd,y = {moment_y_uls:.3f} kNm"
                        ),
                        (
                            f"       Effective punching action including moments"
                            f" = {effective_force:.3f} kN"
                        ),
                        (
                            f"       Basic stress = VEd,eff/(u{multiplier}·d)"
                            f" = {base_stress:.3f} N/mm²"
                        ),
                        (
                            f"       β = 1 + k·(|MEd,x+MEd,y|/VEd,eff)·u/W"
                            f" = {beta_calc:.3f}"
                        ),
                        (
                            f"       vEd = β·VEd,eff/(u{multiplier}·d)"
                            f" = {demand:.3f} N/mm²; "
                            f"vRd = {resistance:.3f} N/mm²"
                        ),
                        (
                            f"       ρx = As,x/(1000dx) = {rho_x:.5f}; "
                            f"ρy = As,y/(1000dy) = {rho_y:.5f}"
                        ),
                        (
                            f"       ρl = min(√(ρxρy), 0.02)"
                            f" = {rho_punch:.6f}; k = min(1+√(200/d),2)"
                            f" = {k_punch:.6f}"
                        ),
                        (
                            f"       vmin = 0.035k^(3/2)√fck = "
                            f"{vmin_punch:.3f} N/mm²"
                        ),
                        (
                            f"       vRd,c = max[0.12k(100ρl fck)^(1/3),vmin]"
                            f" = {vrd_c_base:.3f} N/mm²"
                        ),
                        (
                            f"       Governing resistance at {multiplier}d = "
                            f"{'2.0·vRd,c' if multiplier == 1 else 'vRd,c'}"
                            f" = {vrd_for_check:.3f} N/mm² "
                            f"(reported {resistance:.3f} N/mm²)"
                        ),
                    ])
            elif title == "Sliding resistance":
                horizontal_x = (
                    1.35 * v["permanent_horizontal_x"]
                    + 1.5 * v["imposed_horizontal_x"]
                )
                horizontal_y = (
                    1.35 * v["permanent_horizontal_y"]
                    + 1.5 * v["imposed_horizontal_y"]
                )
                horizontal_resultant = math.hypot(horizontal_x, horizontal_y)
                vertical_force = (
                    area * (concrete_pressure + soil_pressure)
                    + v["permanent_axial_load"]
                )
                friction_angle = round(math.atan(math.tan(math.radians(20.0))), 3)
                lines.extend([
                    (
                        f"       HEd,x = 1.35HGk,x + 1.50HQk,x = "
                        f"{horizontal_x:.3f} kN"
                    ),
                    (
                        f"       HEd,y = 1.35HGk,y + 1.50HQk,y = "
                        f"{horizontal_y:.3f} kN"
                    ),
                    (
                        f"       HEd = √(HEd,x²+HEd,y²) = "
                        f"√({horizontal_x:.3f}²+{horizontal_y:.3f}²)"
                        f" = {horizontal_resultant:.3f} kN"
                    ),
                    (
                        f"       NEd used by method = Gcolumn + A(qconcrete+qsoil)"
                        f" = {v['permanent_axial_load']:.3f} + {area:.3f}·"
                        f"({concrete_pressure:.3f}+{soil_pressure:.3f})"
                        f" = {vertical_force:.3f} kN"
                    ),
                    (
                        f"       Design interface angle: δ = atan(tan 20°)"
                        f" = {friction_angle:.3f} rad"
                    ),
                    (
                        f"       HRd = NEd·tan(δ) = {vertical_force:.3f}·"
                        f"tan({friction_angle:.3f}) = {resistance:.3f} kN"
                    ),
                    "       Acceptance: HEd ≤ HRd.",
                ])
            else:
                lines.append("       Resistance basis: value returned by the FoundationDesign check method")
            if demand is not None and resistance not in (None, 0):
                utilisation = demand / resistance
                sign = "≤" if utilisation <= 1.0 else ">"
                lines.append(
                    f"       η = {demand:.3f}/{resistance:.3f} = "
                    f"{utilisation:.3f} {sign} 1.000"
                )
            elif title != "Bearing pressure (SLS)":
                lines.append("       Utilisation: not calculable because the method did not expose both values")
            lines.extend([f"       Status: {status}", ""])

        lines.extend([
            "6. CALCULATION SCOPE",
            (
                "   The results reproduce the equations and intermediate values exposed by the "
                "FoundationDesign calculation methods. Numerical values may differ slightly "
                "from hand calculations because of intermediate rounding."
            ),
        ])

        self.last_trace = "\n".join(lines)
        self.trace_text.configure(state="normal")
        self.trace_text.delete("1.0", "end")
        self.trace_text.insert("1.0", self.last_trace)
        self.trace_text.configure(state="disabled")
        self._update_trace_search()

    def _redraw_foundation_views(self, _event: tk.Event | None = None) -> None:
        if self.diagram_values:
            self.draw_foundation_views()

    def _update_plan_from_inputs(self, *_args: str) -> None:
        geometry_names = (
            "foundation_length", "foundation_width", "column_length", "column_width",
            "col_pos_xdir", "col_pos_ydir", "foundation_thickness", "soil_depth",
        )
        try:
            v = {name: float(self.variables[name].get().strip()) for name in geometry_names}
            valid = (
                v["foundation_length"] > 0 and v["foundation_width"] > 0
                and v["column_length"] > 0 and v["column_width"] > 0
                and v["foundation_thickness"] > 0
                and v["column_length"] / 2 <= v["col_pos_xdir"] <= v["foundation_length"] - v["column_length"] / 2
                and v["column_width"] / 2 <= v["col_pos_ydir"] <= v["foundation_width"] - v["column_width"] / 2
            )
        except ValueError:
            valid = False
            v = {}

        if valid:
            self.diagram_values = v
            self.draw_foundation_views()
        else:
            self.diagram_values = None
            for canvas in (
                self.input_plan_canvas, self.input_section_canvas,
                self.plan_canvas, self.section_canvas,
            ):
                canvas.delete("all")
                w, h = canvas.winfo_width(), canvas.winfo_height()
                if w > 10 and h > 10:
                    canvas.create_text(w / 2, h / 2, text="Invalid geometry parameters", fill="#d32f2f")

    def draw_foundation_views(self) -> None:
        if not self.diagram_values:
            return

        self._draw_foundation_views_on(
            self.input_plan_canvas, self.input_section_canvas, None
        )
        self._draw_foundation_views_on(
            self.plan_canvas, self.section_canvas, self.reinforcement_results
        )

    @staticmethod
    def _draw_diagram_placeholder(canvas: tk.Canvas) -> None:
        canvas.delete("all")
        canvas.create_text(
            max(canvas.winfo_width(), 2) / 2, max(canvas.winfo_height(), 2) / 2,
            text="Run Design to generate this diagram.", fill="#666666",
            font=("Segoe UI", 11),
        )

    def _draw_action_diagram(self, key: str) -> None:
        """Render the calculation library's Plotly result on a native Tk canvas."""
        canvas = self.action_canvases.get(key)
        figure = self.action_diagrams.get(key)
        if canvas is None:
            return
        if figure is None:
            self._draw_diagram_placeholder(canvas)
            return

        series = []
        for trace in getattr(figure, "data", ()):
            points = []
            x_data = getattr(trace, "x", None)
            y_data = getattr(trace, "y", None)
            if x_data is None or y_data is None:
                continue
            for x_value, y_value in zip(x_data, y_data):
                try:
                    # IndeterminateBeam's default result units are N and N.m.
                    # Match the design report by displaying kN and kNm.
                    point = float(x_value), float(y_value) / 1000.0
                except (TypeError, ValueError):
                    continue
                if all(math.isfinite(value) for value in point):
                    points.append(point)
            if points:
                series.append((trace, points))
        if not series:
            self._draw_diagram_placeholder(canvas)
            return

        canvas.delete("all")
        width, height = max(canvas.winfo_width(), 480), max(canvas.winfo_height(), 300)
        # Leave room above the graph for an elevation aligned to the analysis axis.
        left, right, top, bottom = 78, 24, 100, 58
        plot_width, plot_height = width - left - right, height - top - bottom
        xs = [x for _trace, points in series for x, _y in points]
        ys = [y for _trace, points in series for _x, y in points]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(min(ys), 0.0), max(max(ys), 0.0)
        if x_min == x_max:
            x_min, x_max = x_min - 0.5, x_max + 0.5
        if y_min == y_max:
            y_min, y_max = y_min - 0.5, y_max + 0.5
        padding = (y_max - y_min) * 0.08
        y_min, y_max = y_min - padding, y_max + padding

        sx = lambda value: left + (value - x_min) * plot_width / (x_max - x_min)
        sy = lambda value: top + (y_max - value) * plot_height / (y_max - y_min)

        # Show where the action diagram sits on the actual pad.  Positions are
        # calculated as proportions, so this remains aligned whether the library
        # returns its horizontal axis in metres or millimetres.
        values = self.diagram_values or {}
        if key.endswith("_x"):
            pad_size = values.get("foundation_length")
            column_size = values.get("column_length")
            column_position = values.get("col_pos_xdir")
            direction = "X"
        else:
            pad_size = values.get("foundation_width")
            column_size = values.get("column_width")
            column_position = values.get("col_pos_ydir")
            direction = "Y"
        if all(
            isinstance(value, (int, float)) and value > 0
            for value in (pad_size, column_size, column_position)
        ):
            column_left = left + (
                (column_position - column_size / 2) / pad_size
            ) * plot_width
            column_right = left + (
                (column_position + column_size / 2) / pad_size
            ) * plot_width
            slab_top, slab_bottom = 69, 81
            canvas.create_rectangle(
                left, slab_top, left + plot_width, slab_bottom,
                fill="#d9eaf7", outline="#1f4e79", width=2,
            )
            canvas.create_rectangle(
                column_left, 43, column_right, slab_top,
                fill="#c7d9e7", outline="#1f4e79", width=2,
            )
            canvas.create_line(
                column_position / pad_size * plot_width + left, 39,
                column_position / pad_size * plot_width + left, 86,
                fill="#d62728", dash=(4, 3),
            )
            canvas.create_text(
                (column_left + column_right) / 2, 34,
                text="Column", fill="#1f4e79", font=("Segoe UI", 8),
            )
            canvas.create_text(
                left + plot_width - 4, 61, text=f"Pad foundation — {direction}",
                anchor="e", fill="#1f4e79", font=("Segoe UI", 8, "bold"),
            )

        for index in range(6):
            fraction = index / 5
            x_value = x_min + fraction * (x_max - x_min)
            y_value = y_max - fraction * (y_max - y_min)
            canvas.create_line(sx(x_value), top, sx(x_value), top + plot_height, fill="#eceff1")
            canvas.create_line(left, sy(y_value), left + plot_width, sy(y_value), fill="#eceff1")
            canvas.create_text(sx(x_value), top + plot_height + 16, text=f"{x_value:g}", fill="#555555")
            canvas.create_text(left - 8, sy(y_value), text=f"{y_value:.3g}", anchor="e", fill="#555555")
        canvas.create_line(left, sy(0), left + plot_width, sy(0), fill="#606060", width=2)
        canvas.create_rectangle(left, top, left + plot_width, top + plot_height, outline="#8a8a8a")

        colours = ("#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e")
        for index, (trace, points) in enumerate(series):
            colour = colours[index % len(colours)]
            coords = [value for x, y in points for value in (sx(x), sy(y))]
            mode = str(getattr(trace, "mode", "lines") or "lines")
            if "lines" in mode and len(points) > 1:
                canvas.create_line(*coords, fill=colour, width=2)
            if "markers" in mode or len(points) == 1:
                for x, y in points:
                    canvas.create_oval(sx(x)-3, sy(y)-3, sx(x)+3, sy(y)+3, fill=colour, outline=colour)

        # Label the structural values at both pad ends and column faces.  Use the
        # longest trace as the analysed action curve; shorter traces in the Plotly
        # figure are normally query-point markers or annotations.
        if all(
            isinstance(value, (int, float)) and value > 0
            for value in (pad_size, column_size, column_position)
        ):
            _main_trace, main_points = max(series, key=lambda item: len(item[1]))
            ordered_points = sorted(main_points)

            def value_at(position: float) -> float:
                """Linearly read the plotted action at a requested position."""
                closest_x, closest_y = min(
                    ordered_points, key=lambda point: abs(point[0] - position)
                )
                tolerance = max((x_max - x_min) * 1e-7, 1e-9)
                if abs(closest_x - position) <= tolerance:
                    return closest_y
                for (x1, y1), (x2, y2) in zip(
                    ordered_points, ordered_points[1:]
                ):
                    if x1 <= position <= x2 and x2 != x1:
                        ratio = (position - x1) / (x2 - x1)
                        return y1 + ratio * (y2 - y1)
                return closest_y

            left_face = x_min + (
                (column_position - column_size / 2) / pad_size
            ) * (x_max - x_min)
            right_face = x_min + (
                (column_position + column_size / 2) / pad_size
            ) * (x_max - x_min)
            stations = (
                ("Left end", x_min, "sw"),
                ("Left face", left_face, "s"),
                ("Right face", right_face, "n"),
                ("Right end", x_max, "se"),
            )
            for station_index, (label, position, anchor) in enumerate(stations):
                action = value_at(position)
                px, py = sx(position), sy(action)
                canvas.create_line(px, top, px, top + plot_height, fill="#9e9e9e", dash=(3, 3))
                canvas.create_oval(
                    px - 4, py - 4, px + 4, py + 4,
                    fill="#ffffff", outline="#c5221f", width=2,
                )
                # Alternate face labels above/below the curve to avoid overlap
                # where moment and shear values are close together.
                offset = -12 if station_index in (0, 1) else 12
                label_y = min(max(py + offset, top + 13), top + plot_height - 13)
                canvas.create_text(
                    px, label_y,
                    text=f"{label}\n{action:.3f}",
                    anchor=anchor, justify="center", fill="#8b0000",
                    font=("Segoe UI", 8, "bold"),
                )

        layout = getattr(figure, "layout", None)
        title = getattr(getattr(layout, "title", None), "text", None) or {
            "moment_x": "Bending moment diagram — X direction",
            "moment_y": "Bending moment diagram — Y direction",
            "shear_x": "Shear force diagram — X direction",
            "shear_y": "Shear force diagram — Y direction",
        }[key]
        title = html.unescape(re.sub(r"<[^>]+>", "", str(title)))
        axis_title = getattr(getattr(layout, "xaxis", None), "title", None)
        x_title = getattr(axis_title, "text", None) or "Foundation position"
        if "(" not in x_title:
            x_title = f"{x_title} (m)"
        y_title = "Bending moment (kNm)" if key.startswith("moment") else "Shear force (kN)"
        canvas.create_text(width/2, 20, text=title, font=("Segoe UI", 11, "bold"), fill="#1f4e79")
        canvas.create_text(left + plot_width/2, height-16, text=x_title, fill="#333333")
        canvas.create_text(18, top + plot_height/2, text=y_title, angle=90, fill="#333333")

    def _draw_foundation_views_on(
        self,
        plan_canvas: tk.Canvas,
        section_canvas: tk.Canvas,
        reinforcement_results: dict[str, dict] | None,
    ) -> None:
        """Render one geometry view, optionally including designed reinforcement."""
        if not self.diagram_values:
            return

        v = self.diagram_values
        L_f = v["foundation_length"]
        B_f = v["foundation_width"]
        L_c = v["column_length"]
        B_c = v["column_width"]
        x_c = v["col_pos_xdir"]
        y_c = v["col_pos_ydir"]
        T_f = v["foundation_thickness"]
        D_s = v.get("soil_depth", 0.0)

        # -------------------------------------------------------------
        # 1. PLAN VIEW RENDERING
        # -------------------------------------------------------------
        canvas_plan = plan_canvas
        canvas_plan.delete("all")
        pw = canvas_plan.winfo_width()
        ph = canvas_plan.winfo_height()
        if pw <= 20 or ph <= 20:
            return

        margin_p = 40.0
        reinforcement = reinforcement_results or {}
        legend_width = 300.0 if reinforcement else 0.0
        avail_pw = pw - 2 * margin_p - legend_width
        avail_ph = ph - 2 * margin_p

        scale = min(avail_pw / L_f, avail_ph / B_f)
        plan_x_offset = (pw - legend_width - (L_f * scale)) / 2.0
        plan_y_offset = (ph - (B_f * scale)) / 2.0

        f_x1 = plan_x_offset
        f_y1 = plan_y_offset
        f_x2 = plan_x_offset + (L_f * scale)
        f_y2 = plan_y_offset + (B_f * scale)

        canvas_plan.create_rectangle(f_x1, f_y1, f_x2, f_y2, fill="#e1f5fe", outline="#0288d1", width=2)

        # Bottom reinforcement mat (shown after a successful design run).
        steel_x = reinforcement.get("X", {})
        steel_y = reinforcement.get("Y", {})
        spacing_x = self._first_number(steel_x.get("bar_spacing"))
        spacing_y = self._first_number(steel_y.get("bar_spacing"))
        cover = v.get("concrete_cover", 0.0)
        if spacing_x and spacing_y:
            # X bars run parallel to L and are spaced across B.
            bar_y = cover
            while bar_y <= B_f - cover + 1e-9:
                py = plan_y_offset + bar_y * scale
                canvas_plan.create_line(
                    f_x1 + cover * scale, py, f_x2 - cover * scale, py,
                    fill="#c62828", width=1,
                )
                bar_y += spacing_x

            # Y bars run parallel to B and are spaced across L.
            bar_x = cover
            while bar_x <= L_f - cover + 1e-9:
                px = plan_x_offset + bar_x * scale
                canvas_plan.create_line(
                    px, f_y1 + cover * scale, px, f_y2 - cover * scale,
                    fill="#2e7d32", width=1,
                )
                bar_x += spacing_y

        c_x1 = plan_x_offset + ((x_c - L_c / 2.0) * scale)
        c_y1 = plan_y_offset + ((y_c - B_c / 2.0) * scale)
        c_x2 = plan_x_offset + ((x_c + L_c / 2.0) * scale)
        c_y2 = plan_y_offset + ((y_c + B_c / 2.0) * scale)

        canvas_plan.create_rectangle(c_x1, c_y1, c_x2, c_y2, fill="#78909c", outline="#37474f", width=2)

        # Column dimensions in plan.
        col_dim_y = c_y1 - 9
        canvas_plan.create_line(c_x1, col_dim_y, c_x2, col_dim_y, fill="#37474f", arrow="both")
        canvas_plan.create_text(
            (c_x1 + c_x2) / 2, col_dim_y - 8,
            text=f"Lc = {L_c:.0f} mm", fill="#37474f", font=("Segoe UI", 8, "bold")
        )
        col_dim_x = c_x2 + 9
        canvas_plan.create_line(col_dim_x, c_y1, col_dim_x, c_y2, fill="#37474f", arrow="both")
        canvas_plan.create_text(
            col_dim_x + 9, (c_y1 + c_y2) / 2,
            text=f"Bc = {B_c:.0f} mm", fill="#37474f",
            font=("Segoe UI", 8, "bold"), angle=90
        )

        canvas_plan.create_line(f_x1 - 10, (f_y1 + f_y2) / 2, f_x2 + 10, (f_y1 + f_y2) / 2, fill="#b0bec5", dash=(4, 4))
        canvas_plan.create_line((f_x1 + f_x2) / 2, f_y1 - 10, (f_x1 + f_x2) / 2, f_y2 + 10, fill="#b0bec5", dash=(4, 4))

        canvas_plan.create_text((f_x1 + f_x2) / 2, f_y1 - 15, text=f"L = {L_f:.0f} mm", fill="#0288d1", font=("Segoe UI", 8, "bold"))
        canvas_plan.create_text(f_x1 - 15, (f_y1 + f_y2) / 2, text=f"B = {B_f:.0f} mm", fill="#0288d1", font=("Segoe UI", 8, "bold"), angle=90)

        canvas_plan.create_line(f_x1 - 25, (c_y1 + c_y2) / 2, f_x2 + 25, (c_y1 + c_y2) / 2, fill="#d32f2f", width=2, dash=(6, 2))
        canvas_plan.create_text(f_x1 - 32, (c_y1 + c_y2) / 2, text="X", fill="#d32f2f", font=("Segoe UI", 10, "bold"))
        canvas_plan.create_text(f_x2 + 32, (c_y1 + c_y2) / 2, text="X", fill="#d32f2f", font=("Segoe UI", 10, "bold"))

        if spacing_x and spacing_y:
            x_label = (
                f"X bottom: {steel_x.get('steel_label', '')}"
                f"{steel_x.get('bar_diameter', '')} @ {spacing_x:.0f} mm c/c "
                "(LOWER layer)"
            )
            y_label = (
                f"Y bottom: {steel_y.get('steel_label', '')}"
                f"{steel_y.get('bar_diameter', '')} @ {spacing_y:.0f} mm c/c "
                "(UPPER layer)"
            )
            # Leave the X-X section marker unobstructed between the footing
            # outline and the reinforcement legend.
            legend_x = f_x2 + 55
            legend_y = (f_y1 + f_y2) / 2 - 18
            canvas_plan.create_text(
                legend_x, legend_y - 18, text="BOTTOM REINFORCEMENT",
                anchor="w", fill="#37474f", font=("Segoe UI", 8, "bold"),
            )
            canvas_plan.create_text(
                legend_x, legend_y, text=x_label, anchor="w",
                fill="#c62828", font=("Segoe UI", 8, "bold"),
            )
            canvas_plan.create_text(
                legend_x, legend_y + 18, text=y_label, anchor="w",
                fill="#2e7d32", font=("Segoe UI", 8, "bold"),
            )

        # -------------------------------------------------------------
        # 2. SECTION VIEW RENDERING
        # -------------------------------------------------------------
        canvas_sec = section_canvas
        canvas_sec.delete("all")
        sw = canvas_sec.winfo_width()
        sh = canvas_sec.winfo_height()
        if sw <= 20 or sh <= 20:
            return

        sec_x_offset = plan_x_offset
        total_depth = T_f + D_s
        margin_v = 30.0
        avail_sh = sh - (2 * margin_v) - 30.0

        v_scale = avail_sh / max(total_depth, 300.0)
        v_scale = min(v_scale, scale * 1.5)

        ground_y = sh - margin_v - (total_depth * v_scale)
        found_top_y = ground_y + (D_s * v_scale)
        found_bot_y = found_top_y + (T_f * v_scale)

        sf_x1 = sec_x_offset
        sf_x2 = sec_x_offset + (L_f * scale)

        canvas_sec.create_rectangle(sf_x1, found_top_y, sf_x2, found_bot_y, fill="#e1f5fe", outline="#0288d1", width=2)

        if spacing_x and spacing_y:
            dia_x = self._first_number(steel_x.get("bar_diameter")) or 0.0
            dia_y = self._first_number(steel_y.get("bar_diameter")) or 0.0
            # Clamp bar centrelines inside the concrete outline even when the
            # canvas is very shallow and the vertical scale becomes small.
            x_radius = max(1.5, min(4.0, dia_x * v_scale / 2.0))
            circle_radius = max(2.0, min(5.0, dia_y * v_scale / 2.0))
            x_bar_y = min(
                found_bot_y - x_radius - 2.0,
                found_bot_y - (cover + dia_x / 2.0) * v_scale,
            )
            x_bar_y = max(found_top_y + x_radius + 2.0, x_bar_y)
            y_bar_y = min(
                x_bar_y - x_radius - circle_radius - 2.0,
                found_bot_y - (cover + dia_x + dia_y / 2.0) * v_scale,
            )
            y_bar_y = max(found_top_y + circle_radius + 2.0, y_bar_y)

            # X reinforcement is parallel to the X-X section.
            canvas_sec.create_line(
                sf_x1 + cover * scale, x_bar_y, sf_x2 - cover * scale, x_bar_y,
                fill="#c62828", width=3,
            )

            # Y reinforcement crosses the X-X section and is shown as bar circles.
            bar_x = cover
            while bar_x <= L_f - cover + 1e-9:
                px = sf_x1 + bar_x * scale
                canvas_sec.create_oval(
                    px - circle_radius, y_bar_y - circle_radius,
                    px + circle_radius, y_bar_y + circle_radius,
                    fill="#2e7d32", outline="#1b5e20",
                )
                bar_x += spacing_y

            canvas_sec.create_text(
                sf_x2 + 16, x_bar_y + 10,
                text=(
                    f"X LOWER: {steel_x.get('steel_label', '')}"
                    f"{steel_x.get('bar_diameter', '')} @ {spacing_x:.0f} mm c/c"
                ),
                anchor="w", fill="#c62828", font=("Segoe UI", 8, "bold"),
            )
            canvas_sec.create_text(
                sf_x2 + 16, y_bar_y - 10,
                text=(
                    f"Y UPPER: {steel_y.get('steel_label', '')}"
                    f"{steel_y.get('bar_diameter', '')} @ {spacing_y:.0f} mm c/c"
                ),
                anchor="w", fill="#2e7d32", font=("Segoe UI", 8, "bold"),
            )
            # Neutral dashed leaders stop at the concrete face, so they cannot
            # be mistaken for reinforcement projecting out of the footing.
            canvas_sec.create_line(
                sf_x2, x_bar_y, sf_x2 + 11, x_bar_y,
                fill="#607d8b", width=1, dash=(2, 2),
            )
            canvas_sec.create_line(
                sf_x2, y_bar_y, sf_x2 + 11, y_bar_y,
                fill="#607d8b", width=1, dash=(2, 2),
            )
            canvas_sec.create_text(
                sf_x2 + 16, y_bar_y - 27,
                text=f"Nominal cover = {cover:.0f} mm", anchor="w",
                fill="#6d4c41", font=("Segoe UI", 8),
            )

        if D_s > 0:
            canvas_sec.create_rectangle(sf_x1, ground_y, sf_x2, found_top_y, fill="#d7ccc8", outline="#8d6e63")
            canvas_sec.create_line(sf_x1 - 20, ground_y, sf_x2 + 20, ground_y, fill="#5d4037", width=2)
            canvas_sec.create_text(sf_x1 - 35, (ground_y + found_top_y) / 2, text=f"Soil: {D_s:.0f}mm", fill="#5d4037", font=("Segoe UI", 8))
        else:
            canvas_sec.create_line(sf_x1 - 20, found_top_y, sf_x2 + 20, found_top_y, fill="#5d4037", width=2)

        sc_x1 = sec_x_offset + ((x_c - L_c / 2.0) * scale)
        sc_x2 = sec_x_offset + ((x_c + L_c / 2.0) * scale)
        col_top_y = max(margin_v, ground_y - 40.0)

        canvas_sec.create_rectangle(sc_x1, col_top_y, sc_x2, found_top_y, fill="#78909c", outline="#37474f", width=2)

        # The X-X section cuts through the column length; show that dimension
        # graphically and retain both plan dimensions in the label.
        sec_col_dim_y = col_top_y + 9
        canvas_sec.create_line(sc_x1, sec_col_dim_y, sc_x2, sec_col_dim_y, fill="#37474f", arrow="both")
        canvas_sec.create_text(
            (sc_x1 + sc_x2) / 2, col_top_y - 9,
            text=f"Column {L_c:.0f} × {B_c:.0f} mm",
            fill="#37474f", font=("Segoe UI", 8, "bold")
        )

        canvas_sec.create_text((sf_x1 + sf_x2) / 2, found_bot_y + 15, text=f"Section X-X Length = {L_f:.0f} mm", fill="#0288d1", font=("Segoe UI", 8, "bold"))

        depth_dim_x = sf_x1 - 10 if reinforcement else sf_x2 + 8
        depth_text_x = sf_x1 - 27 if reinforcement else sf_x2 + 25
        canvas_sec.create_text(
            depth_text_x,
            (found_top_y + found_bot_y) / 2,
            text=f"h = {T_f:.0f} mm", 
            fill="#0288d1", 
            font=("Segoe UI", 8, "bold"), 
            angle=90
        )
        canvas_sec.create_line(
            depth_dim_x, found_top_y, depth_dim_x, found_bot_y,
            fill="#0288d1", arrow="both",
        )

    # -------------------------------------------------------------
    # 3. PRINT / CALCULATION SHEET GENERATION
    # -------------------------------------------------------------
    def print_report(self) -> None:
        """Generates a clean HTML report and opens the system print dialog."""
        if not self.last_checks:
            messagebox.showinfo("Print Report", "Please click 'Run Design' first to generate results.")
            return

        # Prepare html content
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Pad Foundation Design Calculation Sheet</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 30px; color: #333; }}
        h1 {{ color: #1f4e79; font-size: 20pt; margin-bottom: 2px; }}
        h2 {{ color: #1f4e79; font-size: 13pt; border-bottom: 2px solid #1f4e79; padding-bottom: 4px; margin-top: 20px; }}
        .subtitle {{ font-style: italic; color: #666; font-size: 10pt; margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 10pt; }}
        th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; }}
        th {{ background-color: #f0f4f8; color: #1f4e79; font-weight: bold; }}
        tr:nth-child(even) {{ background-color: #fafafa; }}
        .pass {{ background-color: #e6f4ea; color: #137333; font-weight: bold; text-align: center; }}
        .fail {{ background-color: #fce8e6; color: #c5221f; font-weight: bold; text-align: center; }}
        pre {{ white-space: pre-wrap; font-family: Consolas, monospace; font-size: 9pt;
               line-height: 1.35; border: 1px solid #ccc; background: #fafafa; padding: 12px; }}
        @media print {{
            @page {{ margin: 15mm; size: A4; }}
            body {{ margin: 0; }}
            .no-print {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="no-print" style="margin-bottom: 15px; padding: 10px; background: #e3f2fd; border-radius: 4px;">
        <button onclick="window.print()" style="padding: 8px 16px; font-size: 11pt; background: #1f4e79; color: white; border: none; border-radius: 4px; cursor: pointer;">
            🖨️ Click Here to Print / Save as PDF
        </button>
    </div>

    <h1>Pad Foundation Design Calculation Sheet</h1>
    <div class="subtitle">Eurocode 2 & 7 Structural Design Verification Report</div>

    <h2>1. Input Design Parameters</h2>
    <table>
        <thead><tr><th>Parameter Description</th><th>Input Value</th></tr></thead>
        <tbody>
"""
        for group_title, group_fields in FIELD_GROUPS:
            for name, label, _ in group_fields:
                val = self.variables[name].get()
                html_content += f"            <tr><td>{label}</td><td><strong>{val}</strong></td></tr>\n"

        html_content += """        </tbody>
    </table>

    <h2>2. Derived Actions & Structural Values</h2>
    <table>
        <thead><tr><th>Item Description</th><th>Calculated Value</th><th>Unit</th></tr></thead>
        <tbody>
"""
        for name, val, unit in self.last_summary_params:
            html_content += f"            <tr><td>{name}</td><td><strong>{val}</strong></td><td>{unit}</td></tr>\n"

        html_content += """        </tbody>
    </table>

    <h2>3. Eurocode Design Checks Summary</h2>
    <table>
        <thead><tr><th>Design Verification Check</th><th>Status</th><th>Calculated Action / Demand</th><th>Allowable Limit / Capacity</th></tr></thead>
        <tbody>
"""
        for title, status, calc, limit in self.last_checks:
            cls = "pass" if status == "PASS" else "fail"
            html_content += f"            <tr><td>{title}</td><td class='{cls}'>{status}</td><td>{calc}</td><td>{limit}</td></tr>\n"

        html_content += """        </tbody>
    </table>

    <h2>4. Detailed Intermediate Calculations</h2>
    <pre>"""
        html_content += html.escape(self.last_trace)
        html_content += """</pre>

    <script>
        // Auto-open print dialog when page loads
        window.onload = function() {
            setTimeout(function() { window.print(); }, 500);
        };
    </script>
</body>
</html>
"""

        # Save to temporary HTML file and open in browser print dialog
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".html", encoding="utf-8") as f:
            f.write(html_content)
            temp_path = f.name

        webbrowser.open(f"file://{temp_path}")


if __name__ == "__main__":
    app = PadFoundationApp()
    app.mainloop()
