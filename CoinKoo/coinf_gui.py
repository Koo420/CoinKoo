#!/usr/bin/env python3
import os, csv, json, random, webbrowser, sys, subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import tkinter as tk
from tkinter import ttk, messagebox, colorchooser

# Matplotlib
try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
except Exception as e:
    raise SystemExit(
        "Matplotlib is required.\n"
        "Ubuntu/Debian: sudo apt install python3-matplotlib\n"
        "Else:          python3 -m pip install matplotlib"
    ) from e

# ===================== NY Trading Day Settings =====================
NY_UTC_OFFSET_HOURS = -4               # Fixed NY offset for labeling/session checks
SKIP_HOUR_START_NY = 17                # Skip 17:00–18:00 NY each day
SKIP_HOUR_END_NY   = 18

def is_in_skipped_hour_ny(t_local_ny: datetime) -> bool:
    return t_local_ny.hour == SKIP_HOUR_START_NY and (0 <= t_local_ny.minute < 60)

def advance_ny_time_skipping_hour(t_local_ny: datetime, minutes: float) -> datetime:
    """Advance NY local time by minutes, skipping 17:00–18:00 NY."""
    if is_in_skipped_hour_ny(t_local_ny):
        t_local_ny = t_local_ny.replace(hour=SKIP_HOUR_END_NY, minute=0, second=0, microsecond=0)
    remaining = minutes
    cur = t_local_ny
    while remaining > 0:
        boundary = cur.replace(hour=SKIP_HOUR_START_NY, minute=0, second=0, microsecond=0)
        if cur >= boundary:
            boundary = boundary + timedelta(days=1)
        delta_to_boundary = (boundary - cur).total_seconds() / 60.0
        if remaining < delta_to_boundary:
            return cur + timedelta(minutes=remaining)
        else:
            cur = boundary.replace(hour=SKIP_HOUR_END_NY)
            remaining -= max(0.0, delta_to_boundary)
    return cur

def ny_local_midnight_today() -> datetime:
    now = datetime.now()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)

def ny_to_utc_minutes_of_day(t_local_ny: datetime) -> int:
    """Convert naive NY local to UTC minute-of-day for session windows."""
    t_utc = t_local_ny - timedelta(hours=NY_UTC_OFFSET_HOURS)  # -(-4) = +4
    return (t_utc.hour * 60 + t_utc.minute) % (24*60)

# ===================== Palettes =====================
def get_palette(theme: str):
    t = (theme or "Vintage").strip().lower()
    if t == "dark sleek":
        return {
            "APP_BG": "#0F172A", "CARD_BG": "#1E293B",
            "TXT": "#E2E8F0", "TXT2": "#94A3B8",
            "BORDER_SOFT": "#334155", "BORDER_STRONG": "#0B1220",
            "ACCENT": "#2563EB",
            "STATUS_BG": "#0B1220", "STATUS_TXT": "#BBD1F7",
            "CHART_BG_DEFAULT": "#FFFFFF", "AXIS": "#94A3B8",
            "ENTRY_BG": "#0B1220", "ENTRY_FG": "#FFFFFF", "ENTRY_FG_DISABLED": "#8BA0B8",
            "SCALE_TROUGH": "#0B1220", "SCALE_BAR": "#2563EB", "SCALE_KNOB": "#E2E8F0",
            "BTN_TXT": "#FFFFFF", "BTN_SEC_BG": "#273447", "BTN_SEC_TXT": "#E2E8F0",
        }
    # Vintage
    return {
        "APP_BG": "#DDDAD0", "CARD_BG": "#F8F3CE",
        "TXT": "#57564F", "TXT2": "#7A7A73",
        "BORDER_SOFT": "#DDDAD0", "BORDER_STRONG": "#57564F",
        "ACCENT": "#57564F",
        "STATUS_BG": "#DDDAD0", "STATUS_TXT": "#57564F",
        "CHART_BG_DEFAULT": "#F8F3CE", "AXIS": "#7A7A73",
        "ENTRY_BG": "#FFFFFF", "ENTRY_FG": "#57564F", "ENTRY_FG_DISABLED": "#7A7A73",
        "SCALE_TROUGH": "#EEEAD8", "SCALE_BAR": "#57564F", "SCALE_KNOB": "#57564F",
        "BTN_TXT": "#F8F3CE", "BTN_SEC_BG": "#EFE8C9", "BTN_SEC_TXT": "#57564F",
    }

# ===================== Model =====================
@dataclass
class Candle:
    t: datetime  # New York local (naive)
    o: float
    h: float
    l: float
    c: float

def simulate_candle(open_price: float, ticks_per_candle: int, tick_size: float,
                    up_prob: float, rng: Optional[random.Random] = None):
    if rng is None: rng = random
    price = open_price
    high, low = price, price
    for _ in range(ticks_per_candle):
        step = tick_size if rng.random() < up_prob else -tick_size
        price += step
        if price > high: high = price
        if price < low:  low = price
    return open_price, high, low, price

def simulate_series(num_candles: int, ticks_per_candle: int, minutes_per_candle: float,
                    tick_size: float, start_price: float, up_prob: float, *,
                    start_time_ny=None, seed=None,
                    session_volatility: Optional[List[Tuple[int,int,float]]]=None) -> List[Candle]:
    rng = random.Random(seed)
    if start_time_ny is None: start_time_ny = ny_local_midnight_today()
    if is_in_skipped_hour_ny(start_time_ny):
        start_time_ny = start_time_ny.replace(hour=SKIP_HOUR_END_NY, minute=0, second=0, microsecond=0)

    candles: List[Candle] = []
    prev_close = start_price
    cur_t = start_time_ny

    for _ in range(num_candles):
        mult = 1.0
        if session_volatility:
            minute_of_day_utc = ny_to_utc_minutes_of_day(cur_t)
            for s_start, s_end, m in session_volatility:
                if s_start <= s_end:
                    in_win = s_start <= minute_of_day_utc < s_end
                else:
                    in_win = (minute_of_day_utc >= s_start) or (minute_of_day_utc < s_end)
                if in_win:
                    mult = max(mult, m)

        o, h, l, c = simulate_candle(prev_close, ticks_per_candle, tick_size*mult, up_prob, rng)
        candles.append(Candle(t=cur_t, o=o, h=h, l=l, c=c))
        prev_close = c
        cur_t = advance_ny_time_skipping_hour(cur_t, minutes_per_candle)
    return candles

# ===================== Plotting =====================
def draw_candles(ax, candles: List[Candle], title: str, *,
                 up_color: str, down_color: str, chart_bg: str, show_grid: bool, pal: dict):
    ax.clear()
    fg = pal["TXT"]; grid_rgba = _rgba(pal["TXT2"], 0.22); axis_col = pal["AXIS"]; fig_bg = pal["APP_BG"]
    ax.set_facecolor(chart_bg or pal["CHART_BG_DEFAULT"]); ax.figure.set_facecolor(fig_bg)

    xs = list(range(len(candles)))
    for x, cd in zip(xs, candles):
        color = up_color if cd.c >= cd.o else down_color
        ax.vlines(x, cd.l, cd.h, linewidth=1.4, color=color, zorder=2)
        top, bot = max(cd.o, cd.c), min(cd.o, cd.c)
        body_h = max(top - bot, 1e-9)
        ax.add_patch(plt.Rectangle((x - 0.34, bot), 0.68, body_h,
                                   edgecolor=color, facecolor=color, linewidth=0.9, zorder=3))

    stride = max(1, len(candles)//10) if len(candles) else 1
    ax.set_xticks(xs[::stride]); ax.set_xticklabels([c.t.strftime("%H:%M") for c in candles[::stride]], color=fg)

    if candles:
        lows, highs = [c.l for c in candles], [c.h for c in candles]
        pmin, pmax = min(lows), max(highs)
        pad = (pmax - pmin) * 0.04 if pmax > pmin else 1.0
        ax.set_ylim(pmin - pad, pmax + pad); ax.set_xlim(-1, len(candles))

    ax.set_title(title, color=fg, fontsize=13, fontweight="bold")
    ax.set_ylabel("Price", color=fg)
    ax.grid(show_grid, alpha=1.0, linestyle="--", color=grid_rgba)
    for s in ax.spines.values(): s.set_color(axis_col); s.set_linewidth(1.0)
    ax.tick_params(axis='y', colors=fg); ax.tick_params(axis='x', colors=fg)

def _rgba(hex_color: str, alpha: float):
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)/255.0; g = int(hex_color[2:4], 16)/255.0; b = int(hex_color[4:6], 16)/255.0
    return (r, g, b, alpha)

# ===================== Settings / Presets =====================
BASE_DIR = os.path.dirname(__file__)
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
CONFIGS_DIR = os.path.join(BASE_DIR, "Configs")

def load_settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except Exception: return {}

def save_settings(d: dict):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f: json.dump(d, f, indent=2)
    except Exception: pass

def ensure_configs_dir(): os.makedirs(CONFIGS_DIR, exist_ok=True)
def list_presets() -> List[str]:
    ensure_configs_dir(); names=[]
    for fn in sorted(os.listdir(CONFIGS_DIR)):
        if fn.lower().endswith(".json"): names.append(os.path.splitext(fn)[0])
    return names
def preset_path(name: str) -> str:
    ensure_configs_dir()
    safe = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in name).strip() or "preset"
    return os.path.join(CONFIGS_DIR, f"{safe}.json")

# ===================== GUI Base Elements =====================
class Card(tk.Frame):
    def __init__(self, master, palette: dict, **kw):
        self.palette = palette
        super().__init__(master, bg=self.palette["CARD_BG"], bd=2, relief="ridge",
                         highlightthickness=2, highlightbackground=self.palette["BORDER_STRONG"],
                         highlightcolor=self.palette["BORDER_STRONG"], **kw)
        inner = tk.Frame(self, bg=self.palette["CARD_BG"], bd=1, relief="solid",
                         highlightthickness=1, highlightbackground=self.palette["BORDER_SOFT"])
        inner.pack(fill="both", expand=True, padx=4, pady=4)
        self.inner = inner
    def update_palette(self, palette: dict):
        self.palette = palette
        self.configure(bg=palette["CARD_BG"],
                       highlightbackground=palette["BORDER_STRONG"], highlightcolor=palette["BORDER_STRONG"])
        self.inner.configure(bg=palette["CARD_BG"], highlightbackground=palette["BORDER_SOFT"])

class LabeledRow(ttk.Frame):
    def __init__(self, master, label, builder, *, help_text=None):
        super().__init__(master)
        self.columnconfigure(1, weight=1)
        ttk.Label(self, text=label).grid(row=0, column=0, sticky="w", padx=(0,8))
        self.widget = builder(self)
        self.widget.grid(row=0, column=1, sticky="ew")
        if help_text:
            ttk.Label(self, text=help_text, style="Subtle.TLabel").grid(row=1, column=1, sticky="w", pady=(2,0))

# ===================== App =====================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.title("CoinKoo — Coin-Flip Candlestick Generator")
        self.geometry("1240x810"); self.minsize(1080, 700)

        # Theme
        self.theme_choice = tk.StringVar(value=self.settings.get("theme", "Dark Sleek"))
        self.palette = get_palette(self.theme_choice.get())

        # Simulation
        self.var_num = tk.StringVar(value=str(self.settings.get("num_candles", 100)))
        self.var_tf  = tk.StringVar(value=str(self.settings.get("timeframe", 1)))
        self.var_base= tk.StringVar(value=str(self.settings.get("base_ticks", 30)))
        self.var_override = tk.BooleanVar(value=self.settings.get("override", False))
        self.var_eff  = tk.StringVar(value=str(self.settings.get("eff_ticks", "")))
        self.var_tick_size = tk.StringVar(value=str(self.settings.get("tick_size", 1.0)))
        self.var_start_price = tk.StringVar(value=str(self.settings.get("start_price", 10000)))
        self.var_up_prob = tk.StringVar(value=str(self.settings.get("up_prob", 0.5)))
        self.var_seed = tk.StringVar(value=str(self.settings.get("seed", "")))
        self.var_auto_seed = tk.BooleanVar(value=self.settings.get("auto_seed", False))

        # Style (defaults per theme)
        saved_up = self.settings.get("up_color"); saved_down = self.settings.get("down_color")
        if self.theme_choice.get().lower() == "dark sleek":
            default_up = "#22C55E"; default_down = "#EF4444"
        else:
            default_up = "#000000"; default_down = "#EF4444"
        self.var_up_color = tk.StringVar(value=saved_up or default_up)
        self.var_down_color = tk.StringVar(value=saved_down or default_down)
        default_chart_bg = self.settings.get("chart_bg") or self.palette["CHART_BG_DEFAULT"]
        self.var_chart_bg = tk.StringVar(value=default_chart_bg)
        self.var_show_grid = tk.BooleanVar(value=self.settings.get("grid", True))

        # Output
        self.var_custom_name = tk.BooleanVar(value=self.settings.get("custom_name_on", False))
        self.var_name = tk.StringVar(value=self.settings.get("custom_name", ""))

        # Advanced
        self.var_adv_on = tk.BooleanVar(value=self.settings.get("adv_on", False))
        self.var_adv_london = tk.BooleanVar(value=self.settings.get("adv_london", True))
        self.var_adv_ny = tk.BooleanVar(value=self.settings.get("adv_ny", True))
        self.var_adv_lon_mult = tk.StringVar(value=str(self.settings.get("adv_lon_mult", 1.5)))
        self.var_adv_ny_mult  = tk.StringVar(value=str(self.settings.get("adv_ny_mult", 1.5)))
        self.var_full_day = tk.BooleanVar(value=self.settings.get("full_day", False))

        # State
        self.last_candles: List[Candle] = []; self.last_title: str = "Preview"
        self.last_dir = None; self.last_png = None; self.last_csv = None

        # Styles
        self.style = ttk.Style()
        try: self.style.theme_use("clam")
        except: pass
        self._apply_styles()

        self._cards: List[Card] = []
        self._build_layout()
        self._bind_shortcuts()
        self._update_eff_label()
        self._refresh_presets_list()
        self._redraw_current()

        self.theme_choice.trace_add("write", lambda *_: self._on_theme_change())

    # ---------- ttk Styles ----------
    def _apply_styles(self):
        pal = self.palette
        self.configure(bg=pal["APP_BG"])

        # Core
        self.style.configure("TFrame", background=pal["APP_BG"])
        self.style.configure("TLabel", background=pal["CARD_BG"], foreground=pal["TXT"])
        self.style.configure("Title.TLabel", background=pal["CARD_BG"], foreground=pal["TXT"], font=("Segoe UI Semibold", 14))
        self.style.configure("Section.TLabel", background=pal["CARD_BG"], foreground=pal["TXT"], font=("Segoe UI Semibold", 11))
        self.style.configure("Subtle.TLabel", background=pal["CARD_BG"], foreground=pal["TXT2"])

        # Entry + selection colors
        self.style.configure("TEntry", fieldbackground=pal["ENTRY_BG"], foreground=pal["ENTRY_FG"])
        self.style.map("TEntry",
                       fieldbackground=[("disabled", pal["ENTRY_BG"])],
                       foreground=[("disabled", pal["ENTRY_FG_DISABLED"])])

        # Combobox
        self.style.configure("TCombobox",
                             fieldbackground=pal["ENTRY_BG"],
                             foreground=pal["ENTRY_FG"],
                             background=pal["ENTRY_BG"])
        try:
            self.style.map("TCombobox", arrowcolor=[("!disabled", pal["TXT"])])
        except Exception:
            pass

        # Make dropdown listbox themed + selection highlight
        try:
            self.option_add("*TCombobox*Listbox*Background", pal["ENTRY_BG"])
            self.option_add("*TCombobox*Listbox*Foreground", pal["ENTRY_FG"])
            self.option_add("*TCombobox*Listbox*selectBackground", pal["ACCENT"])
            self.option_add("*TCombobox*Listbox*selectForeground", pal["BTN_TXT"])
            self.option_add("*TCombobox*Listbox*highlightColor", pal["BORDER_SOFT"])
            self.option_add("*TCombobox*Listbox*highlightBackground", pal["BORDER_SOFT"])
            # Entry text selection
            self.option_add("*selectBackground", pal["ACCENT"])
            self.option_add("*selectForeground", pal["BTN_TXT"])
            self.option_add("*insertBackground", pal["TXT"])
        except Exception:
            pass

        # Scales / sliders
        self.style.configure("Horizontal.TScale", background=pal["CARD_BG"])
        try: self.style.configure("Horizontal.TScale", troughcolor=pal["SCALE_TROUGH"])
        except Exception: pass

        # Checks & buttons
        self.style.configure("TCheckbutton", background=pal["CARD_BG"], foreground=pal["TXT"])
        self.style.configure("Accent.TButton", background=pal["ACCENT"], foreground=pal["BTN_TXT"], padding=8)
        self.style.map("Accent.TButton", background=[("active", pal["ACCENT"]), ("pressed", pal["ACCENT"])])
        self.style.configure("Secondary.TButton", background=pal["BTN_SEC_BG"], foreground=pal["BTN_SEC_TXT"], padding=8)
        self.style.map("Secondary.TButton", background=[("active", pal["BTN_SEC_BG"]), ("pressed", pal["BTN_SEC_BG"])])

        # Status
        self.style.configure("Status.TLabel", background=pal["STATUS_BG"], foreground=pal["STATUS_TXT"], padding=8, anchor="w")

    def _update_all_cards(self):
        for c in self._cards: c.update_palette(self.palette)

    # ---------- Layout ----------
    def _build_layout(self):
        outer = ttk.Frame(self, padding=12); outer.pack(fill=tk.BOTH, expand=True)

        # LEFT column
        left_card = Card(outer, self.palette); left_card.pack(side=tk.LEFT, fill=tk.Y, padx=(0,10))
        self._cards.append(left_card)
        left = ttk.Frame(left_card.inner, padding=10); left.pack(fill=tk.Y)

        # Header (outside tabs)
        hdr = Card(left, self.palette); hdr.pack(fill=tk.X, pady=(0,10)); self._cards.append(hdr)
        hdr_in = ttk.Frame(hdr.inner, padding=12); hdr_in.pack(fill=tk.X)
        ttk.Label(hdr_in, text="📈 Coin-Flip Candlestick Generator", style="Title.TLabel").pack(anchor="w")
        ttk.Label(hdr_in, text="Set parameters, click Generate. Files save to Outputs/<timestamp>/",
                  style="Subtle.TLabel").pack(anchor="w", pady=(4,0))
        tr = ttk.Frame(hdr_in); tr.pack(anchor="w", pady=(8,0))
        ttk.Label(tr, text="Theme:").pack(side=tk.LEFT)
        self.cmb_theme = ttk.Combobox(tr, values=["Vintage", "Dark Sleek"], state="readonly", width=12, textvariable=self.theme_choice)
        self.cmb_theme.pack(side=tk.LEFT, padx=(6,0))
        ttk.Checkbutton(tr, text="Show grid", variable=self.var_show_grid, command=self._redraw_current).pack(side=tk.LEFT, padx=(10,0))

        # Tabs
        nb = ttk.Notebook(left); nb.pack(fill=tk.BOTH, expand=True)
        tab_controls = ttk.Frame(nb); nb.add(tab_controls, text="Controls")
        tab_advanced = ttk.Frame(nb); nb.add(tab_advanced, text="Advanced")

        # -------- Controls tab --------
        sim = Card(tab_controls, self.palette); sim.pack(fill=tk.X, pady=10); self._cards.append(sim)
        sim_in = ttk.Frame(sim.inner, padding=12); sim_in.pack(fill=tk.X)
        ttk.Label(sim_in, text="Simulation", style="Section.TLabel").pack(anchor="w", pady=(0,8))

        self.entry_num = self._row(sim_in, "Number of candles", lambda m: ttk.Entry(m, textvariable=self.var_num))
        self._row(sim_in, "Timeframe (minutes)",     lambda m: ttk.Entry(m, textvariable=self.var_tf))
        self._row(sim_in, "Base ticks per 1-minute", lambda m: ttk.Entry(m, textvariable=self.var_base))

        orow = ttk.Frame(sim_in); orow.pack(fill=tk.X, pady=4)
        ttk.Checkbutton(orow, text="Override effective ticks/candle", variable=self.var_override,
                        command=self._toggle_override).pack(side=tk.LEFT)
        self.entry_eff = ttk.Entry(orow, textvariable=self.var_eff, width=10); self.entry_eff.pack(side=tk.LEFT, padx=(10,0))
        self.eff_label = ttk.Label(sim_in, text="", style="Subtle.TLabel"); self.eff_label.pack(anchor="w", pady=(4,0))
        self._toggle_override()

        self._row(sim_in, "Tick size",             lambda m: ttk.Entry(m, textvariable=self.var_tick_size))
        self._row(sim_in, "Start price",           lambda m: ttk.Entry(m, textvariable=self.var_start_price))
        self._row(sim_in, "Up probability (0..1)", lambda m: ttk.Entry(m, textvariable=self.var_up_prob))

        seed_row = ttk.Frame(sim_in); seed_row.pack(fill=tk.X, pady=4)
        ttk.Label(seed_row, text="Random seed").pack(side=tk.LEFT)
        ttk.Entry(seed_row, textvariable=self.var_seed, width=12).pack(side=tk.LEFT, padx=(8,0))
        ttk.Checkbutton(seed_row, text="Auto-seed", variable=self.var_auto_seed).pack(side=tk.LEFT, padx=(10,0))

        # Style
        sty = Card(tab_controls, self.palette); sty.pack(fill=tk.X, pady=10); self._cards.append(sty)
        sty_in = ttk.Frame(sty.inner, padding=12); sty_in.pack(fill=tk.X)
        ttk.Label(sty_in, text="Style", style="Section.TLabel").pack(anchor="w", pady=(0,8))
        r1 = ttk.Frame(sty_in); r1.pack(fill=tk.X, pady=2)
        ttk.Label(r1, text="Up color").pack(side=tk.LEFT)
        self.btn_upc = ttk.Button(r1, text=self.var_up_color.get(), command=self._pick_up, style="Accent.TButton")
        self.btn_upc.pack(side=tk.LEFT, padx=(8,18))
        ttk.Label(r1, text="Down color").pack(side=tk.LEFT)
        self.btn_dwc = ttk.Button(r1, text=self.var_down_color.get(), command=self._pick_down, style="Accent.TButton")
        self.btn_dwc.pack(side=tk.LEFT, padx=(8,0))
        r2 = ttk.Frame(sty_in); r2.pack(fill=tk.X, pady=6)
        ttk.Label(r2, text="Chart background").pack(side=tk.LEFT)
        self.btn_bg = ttk.Button(r2, text=self.var_chart_bg.get(), command=self._pick_bg, style="Secondary.TButton")
        self.btn_bg.pack(side=tk.LEFT, padx=(8,0))

        # Output
        out = Card(tab_controls, self.palette); out.pack(fill=tk.X, pady=10); self._cards.append(out)
        out_in = ttk.Frame(out.inner, padding=12); out_in.pack(fill=tk.X)
        ttk.Label(out_in, text="Output", style="Section.TLabel").pack(anchor="w", pady=(0,8))
        oc = ttk.Frame(out_in); oc.pack(fill=tk.X, pady=2)
        ttk.Checkbutton(oc, text="Use custom folder name", variable=self.var_custom_name, command=self._toggle_custom).pack(side=tk.LEFT)
        self.entry_name = ttk.Entry(oc, textvariable=self.var_name, width=22)
        self.entry_name.pack(side=tk.LEFT, padx=(8,0))
        self._toggle_custom()

        # Presets
        cfg = Card(tab_controls, self.palette); cfg.pack(fill=tk.X, pady=10); self._cards.append(cfg)
        cfg_in = ttk.Frame(cfg.inner, padding=12); cfg_in.pack(fill=tk.X)
        ttk.Label(cfg_in, text="Configs", style="Section.TLabel").pack(anchor="w", pady=(0,8))
        row1 = ttk.Frame(cfg_in); row1.pack(fill=tk.X, pady=4)
        ttk.Label(row1, text="Preset name").pack(side=tk.LEFT)
        self.var_preset_name = tk.StringVar(value="")
        self.preset_entry = ttk.Entry(row1, textvariable=self.var_preset_name, width=24); self.preset_entry.pack(side=tk.LEFT, padx=(8,12))
        ttk.Button(row1, text="Save", style="Accent.TButton", command=self.save_preset).pack(side=tk.LEFT)
        ttk.Button(row1, text="Delete", style="Secondary.TButton", command=self.delete_preset).pack(side=tk.LEFT, padx=(8,0))
        row2 = ttk.Frame(cfg_in); row2.pack(fill=tk.X, pady=4)
        ttk.Label(row2, text="Load preset").pack(side=tk.LEFT)
        self.var_preset_select = tk.StringVar(value="")
        self.cmb_presets = ttk.Combobox(row2, textvariable=self.var_preset_select, state="readonly", width=22)
        self.cmb_presets.pack(side=tk.LEFT, padx=(8,12))
        ttk.Button(row2, text="Load", style="Secondary.TButton", command=self.load_preset).pack(side=tk.LEFT)

        # Actions
        act = Card(tab_controls, self.palette); act.pack(fill=tk.X, pady=10); self._cards.append(act)
        act_in = ttk.Frame(act.inner, padding=12); act_in.pack(fill=tk.X)
        ttk.Button(act_in, text="Generate", style="Accent.TButton", command=self.on_generate).pack(side=tk.LEFT)
        ttk.Button(act_in, text="Open Last Output", style="Secondary.TButton", command=self.open_last).pack(side=tk.LEFT, padx=(8,0))
        ttk.Button(act_in, text="Copy Paths", style="Secondary.TButton", command=self.copy_paths).pack(side=tk.LEFT, padx=(8,0))
        ttk.Button(act_in, text="Quit", style="Secondary.TButton", command=self._quit).pack(side=tk.LEFT, padx=(8,0))

        # -------- Advanced tab --------
        adv = Card(tab_advanced, self.palette); adv.pack(fill=tk.X, pady=10); self._cards.append(adv)
        adv_in = ttk.Frame(adv.inner, padding=12); adv_in.pack(fill=tk.X)
        ttk.Label(adv_in, text="Advanced", style="Section.TLabel").pack(anchor="w", pady=(0,8))

        top_adv = ttk.Frame(adv_in); top_adv.pack(fill=tk.X, pady=(0,8))
        ttk.Checkbutton(top_adv, text="Enable advanced controls", variable=self.var_adv_on,
                        command=self._refresh_advanced_enabled).pack(side=tk.LEFT)

        help_txt = ("Session boosts use UTC windows: London 08:00–17:00, New York 13:30–20:00.\n"
                    "Timeline is New York (UTC−4). Trading day skips 17:00–18:00 NY.")
        ttk.Label(adv_in, text=help_txt, style="Subtle.TLabel").pack(anchor="w", pady=(0,8))

        rowL = ttk.Frame(adv_in); rowL.pack(fill=tk.X, pady=3)
        self.chk_lon = ttk.Checkbutton(rowL, text="Boost London session", variable=self.var_adv_london)
        self.chk_lon.pack(side=tk.LEFT)
        ttk.Label(rowL, text="×").pack(side=tk.LEFT, padx=(8,2))
        self.ent_lon = ttk.Entry(rowL, textvariable=self.var_adv_lon_mult, width=8); self.ent_lon.pack(side=tk.LEFT)

        rowN = ttk.Frame(adv_in); rowN.pack(fill=tk.X, pady=3)
        self.chk_ny = ttk.Checkbutton(rowN, text="Boost New York session", variable=self.var_adv_ny)
        self.chk_ny.pack(side=tk.LEFT)
        ttk.Label(rowN, text="×").pack(side=tk.LEFT, padx=(8,2))
        self.ent_ny = ttk.Entry(rowN, textvariable=self.var_adv_ny_mult, width=8); self.ent_ny.pack(side=tk.LEFT)

        rowF = ttk.Frame(adv_in); rowF.pack(fill=tk.X, pady=(8,0))
        self.chk_full = ttk.Checkbutton(rowF, text="Full trading day mode (23h, auto candle count)",
                                        variable=self.var_full_day, command=self._refresh_full_day_state)
        self.chk_full.pack(side=tk.LEFT)

        # Status bar
        self.status = ttk.Label(self, text="Ready.", style="Status.TLabel", anchor="w")
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

        # RIGHT (chart)
        right_card = Card(outer, self.palette); right_card.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True); self._cards.append(right_card)
        chart_wrap = ttk.Frame(right_card.inner, padding=10); chart_wrap.pack(fill=tk.BOTH, expand=True)
        self.fig, self.ax = plt.subplots(figsize=(9.6, 6.1), dpi=110)
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_wrap)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # live eff label updates
        for v in (self.var_tf, self.var_base, self.var_override, self.var_eff):
            v.trace_add("write", lambda *_: self._update_eff_label())

        self._refresh_advanced_enabled()
        self._refresh_full_day_state()

    def _row(self, parent, label, builder):
        row = LabeledRow(parent, label, builder)
        row.pack(fill=tk.X, pady=4)
        return row.widget

    # ---------- Theme handling ----------
    def _on_theme_change(self):
        self.palette = get_palette(self.theme_choice.get())
        # Default sensible chart colors per theme
        if self.theme_choice.get().lower() == "dark sleek":
            if self.var_up_color.get().lower() in ["#000000", "black"]:
                self.var_up_color.set("#22C55E"); self.btn_upc.config(text=self.var_up_color.get())
            if self.var_chart_bg.get().lower() in ["#f8f3ce", "#ddd ad0".replace(" ","")]:
                self.var_chart_bg.set("#FFFFFF"); self.btn_bg.config(text=self.var_chart_bg.get())
        self._apply_styles(); self._update_all_cards()
        self.btn_upc.config(text=self.var_up_color.get()); self.btn_dwc.config(text=self.var_down_color.get()); self.btn_bg.config(text=self.var_chart_bg.get())
        self._redraw_current()

    # ---------- Color pickers ----------
    def _pick_up(self):
        c = colorchooser.askcolor(color=self.var_up_color.get(), title="Pick Up Candle Color")[1]
        if c: self.var_up_color.set(c); self.btn_upc.config(text=c); self._redraw_current()
    def _pick_down(self):
        c = colorchooser.askcolor(color=self.var_down_color.get(), title="Pick Down Candle Color")[1]
        if c: self.var_down_color.set(c); self.btn_dwc.config(text=c); self._redraw_current()
    def _pick_bg(self):
        c = colorchooser.askcolor(color=self.var_chart_bg.get(), title="Pick Chart Background")[1]
        if c: self.var_chart_bg.set(c); self.btn_bg.config(text=c); self._redraw_current()

    # ---------- UI toggles ----------
    def _toggle_override(self):
        self.entry_eff.configure(state=(tk.NORMAL if self.var_override.get() else tk.DISABLED))
        self._update_eff_label()
    def _toggle_custom(self):
        self.entry_name.configure(state=(tk.NORMAL if self.var_custom_name.get() else tk.DISABLED))

    def _refresh_advanced_enabled(self):
        state = (tk.NORMAL if self.var_adv_on.get() else tk.DISABLED)
        for w in (getattr(self, "chk_lon", None), getattr(self, "ent_lon", None),
                  getattr(self, "chk_ny", None), getattr(self, "ent_ny", None),
                  getattr(self, "chk_full", None)):
            if w: w.configure(state=state)

    def _refresh_full_day_state(self):
        if self.var_full_day.get():
            self.entry_num.configure(state=tk.DISABLED)
            self.status.configure(text="Full trading day mode (23h) — candle count from timeframe.")
        else:
            self.entry_num.configure(state=tk.NORMAL)
            self.status.configure(text="Ready.")

    def _update_eff_label(self):
        try:
            tf = max(0.1, float(self.var_tf.get())); base = max(1, int(float(self.var_base.get())))
            if self.var_override.get():
                eff = int(float(self.var_eff.get())) if self.var_eff.get().strip() else None
                txt = "Effective ticks/candle: (override not set)" if eff is None else f"Effective ticks/candle: {eff} (override)"
            else:
                eff = max(1, int(round(base * tf))); txt = f"Effective ticks/candle: {eff} (scaled)"
            self.eff_label.config(text=txt)
        except Exception:
            self.eff_label.config(text="Effective ticks/candle: —")

    # ---------- Render ----------
    def _redraw_current(self):
        candles = self.last_candles
        title = self.last_title if candles else "Preview"
        draw_candles(
            self.ax,
            candles,
            title,
            up_color=self.var_up_color.get(),
            down_color=self.var_down_color.get(),
            chart_bg=self.var_chart_bg.get(),
            show_grid=self.var_show_grid.get(),
            pal=self.palette,
        )
        self.fig.tight_layout()
        self.canvas.draw_idle()

    # ---------- Actions ----------
    def on_generate(self, *_):
        try:
            tf = self._as_float(self.var_tf.get(), "Timeframe (minutes)", 0.1)
            base = self._as_int(self.var_base.get(), "Base ticks per 1-minute", 1)
            tick_size = self._as_float(self.var_tick_size.get(), "Tick size", 1e-12)
            start_price = self._as_float(self.var_start_price.get(), "Start price")
            up_prob = self._as_float(self.var_up_prob.get(), "Up probability", 0.0, 1.0)

            if self.var_auto_seed.get():
                seed = int(datetime.now().timestamp()); self.var_seed.set(str(seed))
            else:
                seed = int(float(self.var_seed.get())) if self.var_seed.get().strip() else None

            if self.var_override.get():
                if not self.var_eff.get().strip():
                    raise ValueError("Override enabled but no effective ticks/candle provided.")
                eff = self._as_int(self.var_eff.get(), "Effective ticks/candle", 1); src = "override"
            else:
                eff = max(1, int(round(base * tf))); src = "scaled"

            start_time_ny = ny_local_midnight_today()

            if self.var_full_day.get():
                num = max(1, int((23*60) // tf))  # 23h day
            else:
                num = self._as_int(self.var_num.get(), "Number of candles", 1)

            # Session volatility (UTC minutes-of-day)
            session_vol = None
            if self.var_adv_on.get():
                session_vol = []
                if self.var_adv_london.get():
                    m = max(1.0, float(self.var_adv_lon_mult.get() or 1.0))
                    session_vol.append((8*60, 17*60, m))  # London 08:00–17:00 UTC
                if self.var_adv_ny.get():
                    m = max(1.0, float(self.var_adv_ny_mult.get() or 1.0))
                    session_vol.append((13*60+30, 20*60, m))  # NY 13:30–20:00 UTC

            candles = simulate_series(
                num_candles=num,
                ticks_per_candle=eff,
                minutes_per_candle=tf,
                tick_size=tick_size,
                start_price=start_price,
                up_prob=up_prob,
                start_time_ny=start_time_ny,
                seed=seed,
                session_volatility=session_vol
            )

            # Outputs
            base_dir = os.path.join(BASE_DIR, "Outputs"); os.makedirs(base_dir, exist_ok=True)
            folder = self._sanitize(self.var_name.get().strip()) if (self.var_custom_name.get() and self.var_name.get().strip()) \
                     else datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            out_dir = os.path.join(base_dir, folder); os.makedirs(out_dir, exist_ok=True)
            png_path = os.path.join(out_dir, "chart.png")
            csv_path = os.path.join(out_dir, "data.csv")

            title = f"Coin-Flip Chart (NY time UTC−4) — {num} candles, tf={tf}m, ticks/candle={eff} [{src}]"
            draw_candles(self.ax, candles, title,
                         up_color=self.var_up_color.get(), down_color=self.var_down_color.get(),
                         chart_bg=self.var_chart_bg.get(), show_grid=self.var_show_grid.get(), pal=self.palette)
            self.fig.tight_layout(); self.canvas.draw_idle()

            self.fig.savefig(png_path, dpi=170); self._save_csv(candles, csv_path)
            self.last_candles, self.last_title = candles, title
            self.last_dir, self.last_png, self.last_csv = out_dir, png_path, csv_path

            self._set_status(f"Saved PNG → {png_path}\nSaved CSV → {csv_path}", ok=True)
            self._persist()

        except Exception as e:
            self._set_status(str(e), ok=False); messagebox.showerror("Error", str(e))

    def open_last(self, *_):
        if not self.last_dir or not os.path.isdir(self.last_dir):
            self._set_status("No output yet. Generate first.", ok=False); return
        self._open_folder(self.last_dir)

    def copy_paths(self, *_):
        txts = [p for p in (self.last_png, self.last_csv) if p]
        if not txts: self._set_status("Nothing to copy yet. Generate first.", ok=False); return
        self.clipboard_clear(); self.clipboard_append("\n".join(txts))
        self._set_status("Copied output paths to clipboard.", ok=True)

    # ---------- Presets ----------
    def current_config(self) -> dict:
        return {
            "theme": self.theme_choice.get(),
            "num_candles": int(float(self.var_num.get() or 100)),
            "timeframe": float(self.var_tf.get() or 1.0),
            "base_ticks": int(float(self.var_base.get() or 30)),
            "override": self.var_override.get(),
            "eff_ticks": self.var_eff.get(),
            "tick_size": float(self.var_tick_size.get() or 1.0),
            "start_price": float(self.var_start_price.get() or 10000),
            "up_prob": float(self.var_up_prob.get() or 0.5),
            "seed": self.var_seed.get(),
            "auto_seed": self.var_auto_seed.get(),
            "up_color": self.var_up_color.get(),
            "down_color": self.var_down_color.get(),
            "chart_bg": self.var_chart_bg.get(),
            "grid": self.var_show_grid.get(),
            "custom_name_on": self.var_custom_name.get(),
            "custom_name": self.var_name.get(),
            "adv_on": self.var_adv_on.get(),
            "adv_london": self.var_adv_london.get(),
            "adv_ny": self.var_adv_ny.get(),
            "adv_lon_mult": float(self.var_adv_lon_mult.get() or 1.5),
            "adv_ny_mult": float(self.var_adv_ny_mult.get() or 1.5),
            "full_day": self.var_full_day.get(),
        }

    def apply_config(self, cfg: dict):
        self.theme_choice.set(cfg.get("theme", self.theme_choice.get()))
        self.palette = get_palette(self.theme_choice.get())
        self.var_num.set(str(cfg.get("num_candles", 100)))
        self.var_tf.set(str(cfg.get("timeframe", 1.0)))
        self.var_base.set(str(cfg.get("base_ticks", 30)))
        self.var_override.set(bool(cfg.get("override", False)))
        self.var_eff.set(str(cfg.get("eff_ticks", "")))
        self.var_tick_size.set(str(cfg.get("tick_size", 1.0)))
        self.var_start_price.set(str(cfg.get("start_price", 10000)))
        self.var_up_prob.set(str(cfg.get("up_prob", 0.5)))
        self.var_seed.set(str(cfg.get("seed", "")))
        self.var_auto_seed.set(bool(cfg.get("auto_seed", False)))
        self.var_up_color.set(cfg.get("up_color", self.var_up_color.get()))
        self.var_down_color.set(cfg.get("down_color", self.var_down_color.get()))
        self.var_chart_bg.set(cfg.get("chart_bg", self.var_chart_bg.get()))
        self.var_show_grid.set(bool(cfg.get("grid", True)))
        self.var_custom_name.set(bool(cfg.get("custom_name_on", False)))
        self.var_name.set(cfg.get("custom_name", ""))
        self.var_adv_on.set(bool(cfg.get("adv_on", False)))
        self.var_adv_london.set(bool(cfg.get("adv_london", True)))
        self.var_adv_ny.set(bool(cfg.get("adv_ny", True)))
        self.var_adv_lon_mult.set(str(cfg.get("adv_lon_mult", 1.5)))
        self.var_adv_ny_mult.set(str(cfg.get("adv_ny_mult", 1.5)))
        self.var_full_day.set(bool(cfg.get("full_day", False)))

        self._apply_styles(); self._update_all_cards()
        self.btn_upc.config(text=self.var_up_color.get()); self.btn_dwc.config(text=self.var_down_color.get()); self.btn_bg.config(text=self.var_chart_bg.get())
        self._toggle_override(); self._toggle_custom(); self._refresh_advanced_enabled(); self._refresh_full_day_state(); self._update_eff_label()
        self._redraw_current()

    def save_preset(self):
        name = getattr(self, "var_preset_name", tk.StringVar()).get().strip()
        if not name:
            messagebox.showwarning("Preset", "Enter a preset name first."); return
        path = preset_path(name); cfg = self.current_config()
        try:
            with open(path, "w", encoding="utf-8") as f: json.dump(cfg, f, indent=2)
            self._set_status(f"Preset saved → {path}", ok=True); self._refresh_presets_list(select=name)
        except Exception as e:
            messagebox.showerror("Preset", str(e))

    def load_preset(self):
        name = getattr(self, "var_preset_select", tk.StringVar()).get().strip()
        if not name:
            messagebox.showwarning("Preset", "Choose a preset to load."); return
        path = preset_path(name)
        try:
            with open(path, "r", encoding="utf-8") as f: cfg = json.load(f)
            self.apply_config(cfg); self._set_status(f"Preset loaded: {name}", ok=True)
        except Exception as e:
            messagebox.showerror("Preset", str(e))

    def delete_preset(self):
        name = (getattr(self, "var_preset_select", tk.StringVar()).get().strip()
                or getattr(self, "var_preset_name", tk.StringVar()).get().strip())
        if not name:
            messagebox.showwarning("Preset", "Choose or enter a preset to delete."); return
        path = preset_path(name)
        if not os.path.exists(path):
            messagebox.showwarning("Preset", "Preset file not found."); return
        try:
            os.remove(path); self._set_status(f"Preset deleted: {name}", ok=True); self._refresh_presets_list(select="")
        except Exception as e:
            messagebox.showerror("Preset", str(e))

    def _refresh_presets_list(self, select: str = ""):
        items = list_presets()
        if hasattr(self, "cmb_presets"):
            self.cmb_presets["values"] = items
        if select and select in items:
            self.var_preset_select.set(select)
        elif items and self.var_preset_select.get() not in items:
            self.var_preset_select.set(items[0])
        else:
            if not items:
                self.var_preset_select.set("")

    # ---------- helpers ----------
    def _open_folder(self, path):
        try:
            if sys.platform.startswith("darwin"): subprocess.call(["open", path])
            elif os.name == "nt": os.startfile(path)  # type: ignore
            else: subprocess.call(["xdg-open", path])
        except Exception: webbrowser.open(f"file://{path}")

    def _save_csv(self, candles: List[Candle], path: str):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["time(NY UTC-4)","open","high","low","close"])
            for c in candles:
                w.writerow([c.t.strftime("%Y-%m-%d %H:%M"),
                            f"{c.o:.6f}", f"{c.h:.6f}", f"{c.l:.6f}", f"{c.c:.6f}"])

    def _sanitize(self, name: str) -> str:
        bad = '<>:"/\\|?*'; return "".join("_" if ch in bad else ch for ch in name)

    def _set_status(self, text: str, ok: bool):
        pal = self.palette; self.status.configure(text=text, foreground=(pal["TXT"] if ok else "#f87171"))

    def _as_int(self, val: str, name: str, min_val: Optional[int]=None, max_val: Optional[int]=None) -> int:
        v = int(float(val))
        if min_val is not None and v < min_val: raise ValueError(f"{name} must be ≥ {min_val}.")
        if max_val is not None and v > max_val: raise ValueError(f"{name} must be ≤ {max_val}.")
        return v

    def _as_float(self, val: str, name: str, min_val: Optional[float]=None, max_val: Optional[float]=None) -> float:
        v = float(val)
        if min_val is not None and v < min_val: raise ValueError(f"{name} must be ≥ {min_val}.")
        if max_val is not None and v > max_val: raise ValueError(f"{name} must be ≤ {max_val}.")
        return v

    def _bind_shortcuts(self):
        self.bind("<Control-g>", self.on_generate); self.bind("<Control-G>", self.on_generate)
        self.bind("<Control-q>", self._quit); self.bind("<Control-Q>", self._quit)
        self.bind("<Control-o>", self.open_last); self.bind("<Control-O>", self.open_last)

    def _quit(self, *_):
        self._persist(); self.destroy()

    def _persist(self):
        save_settings(self.current_config())

if __name__ == "__main__":
    app = App()
    app.mainloop()

