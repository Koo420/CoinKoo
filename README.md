# CoinKoo
A coinflip chart generator that packs a punch.
CoinKoo — Coin-Flip Candlestick Generator (GUI)

> A tiny desktop app that simulates a market by flipping a coin for each tick and draws **1–N minute candlestick charts**. Built for visuals, demos, and intuition building — **not** trading advice.
---

## ✨ Features

- **GUI app (Tk/ttk)** — no terminal wrangling needed  
- **Candlesticks from coin flips**
  - Each candle = `ticks_per_candle` coin flips (+tick or −tick)
  - Effective ticks per candle auto-scale with timeframe (or override manually)
- **Timeframe aware** — e.g. 5m candles scale base ticks × 5 (unless overridden)
- **NYC timeline & “23-hour day”**
  - Labels in **New York time (UTC−4)**
  - Skips **17:00–18:00 NY** to model a 23-hour trading day
- **Full-day mode** — auto-calculates candle count for a full (23h) session
- **Session volatility boosts (optional)**
  - London **08:00–17:00 UTC**
  - New York **13:30–20:00 UTC**
  - Multiplier per session (e.g. ×1.5)
- **Themes & styling**
  - **Vintage** and **Dark Sleek**
  - Pick **up/down candle colors** and **chart background**
  - Grid on/off
- **Presets**
  - Save/Load/Delete presets → `Configs/*.json`
- **Outputs**
  - Each run saves to `Outputs/<timestamp>/`
  - `chart.png` and `data.csv`
- **Shortcuts**
  - **Ctrl+G** Generate · **Ctrl+O** Open last output · **Ctrl+Q** Quit

---

## 📁 Project Layout

```

CoinKoo/
├─ coinf\_gui.py            # → Run this
├─ Configs/                # Presets (created on demand)
├─ Outputs/                # Generated charts & CSV (created on demand)
└─ settings.json           # Last-used app settings (auto-created)

````

---

## 🛠️ Requirements

- **Python**: 3.10+ recommended  
- **Matplotlib**: for plotting  
- **Tkinter**: usually included with system Python; Linux may need a package

### Quick install (per OS)

**Ubuntu/Debian**
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-tk python3-matplotlib
````

**Fedora**

```bash
sudo dnf install -y python3 python3-pip python3-tkinter python3-matplotlib
```

**Arch/Manjaro**

```bash
sudo pacman -S python tk python-matplotlib
```

**macOS**

```bash
# If using Python.org installer, Tkinter is included.
python3 -m pip install matplotlib
# If Tk missing with Homebrew Python:
brew install tcl-tk
```

**Windows (PowerShell)**

```powershell
py -m pip install matplotlib
```

> ⚠️ If you see “externally managed environment” or want isolation, use a **virtualenv**:

```bash
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install matplotlib
```

---

## ▶️ Run

From the `CoinKoo` folder:

```bash
python3 coinf_gui.py
```

The app opens; generated files appear under:

```
Outputs/<YYYY-MM-DD_HH-MM-SS>/
  ├─ chart.png
  └─ data.csv
```

If you enable **Use custom folder name**, outputs go to `Outputs/<your-name>/`.

---

## ⚙️ Controls (Quick Guide)

### Controls tab

* **Number of candles** — how many candles (disabled in *Full trading day* mode)
* **Timeframe (minutes)** — e.g. `1`, `5`, `7`, …
* **Base ticks per 1-minute** — default effective ticks = `base × timeframe`
* **Override effective ticks/candle** — force a specific ticks/candle (ignores scaling)
* **Tick size** — price step per tick
* **Start price** — initial price
* **Up probability (0..1)** — `0.5` = fair coin
* **Random seed / Auto-seed** — reproducible vs. fresh randomness
* **Style** — up/down candle colors, chart background, show grid
* **Output** — optional custom folder name under `Outputs/`
* **Configs** — Save / Load / Delete presets (`Configs/*.json`)
* **Actions** — Generate, Open Last Output, Copy Paths, Quit

### Advanced tab

* **Enable advanced controls** (master toggle)
* **Boost London session ×M** — UTC 08:00–17:00
* **Boost New York session ×M** — UTC 13:30–20:00
* **Full trading day mode (23h)** — sets `num_candles = floor(23*60 / timeframe_minutes)`

---

## 🧠 How it works (short)

Each candle simulates `ticks_per_candle` coin flips. Each flip changes price by `±tick_size` with “up” probability `up_prob`.
High/low track extrema within the tick loop; open/close are first/last prices.
By default, **effective ticks per candle** are `base_ticks × timeframe_minutes` (unless override is enabled).
Time labels are **NY local (UTC−4)** and **skip 17:00–18:00 NY** to model a 23-hour market.
Optional **session boosts** multiply `tick_size` during specified UTC sessions.

---

## 📤 Output Format

**`data.csv`**

```
time(NY UTC-4),open,high,low,close
2025-09-16 09:00,10000.000000,10003.000000,9997.000000,10001.000000
...
```

**`chart.png`**
PNG snapshot of the generated candlestick chart using your selected styling.

---

## 🔧 Troubleshooting

* **Matplotlib not found**

  ```
  ModuleNotFoundError: No module named 'matplotlib'
  ```

  Install it in your environment:

  ```bash
  python3 -m pip install matplotlib
  ```

* **Tkinter missing (Linux)**

  * Debian/Ubuntu: `sudo apt install python3-tk`
  * Fedora: `sudo dnf install python3-tkinter`
  * Arch: `sudo pacman -S tk`

* **“Externally managed environment” warning**
  Use a virtual environment (see above).

* **Combobox dropdown colors look odd**
 The app themes dropdowns via Tk’s option database; some desktop themes can override it. Try the other app theme or a clean env/DE.

**Chat Control**

Scroll up = zoom in centered at the mouse position

Scroll down = zoom out from the mouse position

Double-click on the chart = reset zoom (autoscale to data)

Keyboard: + or = zooms in (center), - zooms out (center)

---

---

## 🤝 Contributing

1. Open an issue to propose changes.
2. Keep PRs focused (bug fix or a single feature).
3. Please test on at least one of: Windows, macOS, Linux (GNOME/KDE).

---
