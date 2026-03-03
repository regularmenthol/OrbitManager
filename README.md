# Orbit Sample Manager

A desktop sample manager for the Venus Instruments **Orbit** Eurorack module. Lets you organise, preview, and transfer samples across the module's 7 colour banks, 8 preset slots, and 8 sample slots (4L + 4R) per preset — then export directly to your SD card in the correct file structure.

---

## Features

- **Visual colour bank sidebar** — BLUE, CYAN, GREEN, ORANGE, PINK, RED, YELLOW
- **8 preset slots per bank** — tabbed interface with populated slots highlighted in colour
- **4 Left + 4 Right sample slots per preset** — resizable split view
- **Drag & drop import** — drag `.wav` files from Finder/Explorer
- **Click to import** — click any empty slot to open a file picker
- **Automatic conversion** — files that don't match Orbit's required format (mono, 16-bit, 44.1kHz) are flagged and converted on import with a preview dialog
- **Drag to rearrange** — drag samples between slots, presets, and color banks
- **Hold Cmd/Ctrl while dragging** to copy instead of move
- **Hover navigation** — hover over a colour bank or slot tab for 1 second while dragging to switch to it
- **Sample preview** — play any sample directly in the app
- **Reveal original file** — jump to the source file in Finder/Explorer
- **Duration display** — shown on each populated slot
- **SD card import** — browse to your SD card and selectively import samples with a hierarchical checkbox tree
- **SD card export** — selectively export your project samples to an SD card in the correct folder structure
- **Project persistence** — auto-saves after every change, reopens your last project on launch

---

## Requirements

- Python 3.10+
- PyQt6 (required)
- soundfile, resampy, numpy (required only when converting non-Orbit-compatible files)

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/orbit-manager.git
cd orbit-manager
```

### 2. Create a virtual environment (recommended)

```bash
python3 -m venv venv
source venv/bin/activate      # macOS / Linux
venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** `soundfile`, `resampy`, and `numpy` are only needed if you import audio files that need conversion (wrong sample rate, bit depth, or stereo). If you're only working with files already in Orbit format (mono 16-bit 44.1kHz WAV), you can skip them:
> ```bash
> pip install PyQt6
> ```

### 4. Run

```bash
python main.py
```

---

## Usage

### Projects

- **File → New Project** — choose a name and save location
- **File → Open Project** — open an existing project folder
- Project auto-saves after every change

### Importing samples

1. Select a **colour bank** in the left sidebar
2. Select a **SLOT tab** (0–7)
3. **Drag a file** from Finder/Explorer into any slot, or **click an empty slot** to browse
4. If the file needs conversion, a dialog will show exactly what will change before proceeding

### Rearranging

- **Drag** a populated slot to move it to another slot
- **Hold Cmd (macOS) / Ctrl (Windows)** while dragging to copy instead of move
- Drag across slot tabs or colour banks — **hover over a tab or bank for 1 second** to navigate while dragging

### SD Card

- **File → Import from SD Card** — browse to your SD card root, then choose which samples to bring into the project using the checkbox tree
- **File → Export to SD Card** — choose which project samples to write to your SD card

---

## Project file structure

```
MyProject/
├── project.json          ← metadata (original filenames, durations, source paths)
├── BLUE/
│   ├── BLUE_SLOT0_L0.wav
│   ├── BLUE_SLOT0_R0.wav
│   └── ...
├── CYAN/
│   └── ...
└── ...
```

The SD card uses the same structure, just without the `project.json`.

---

## Building a standalone app

To distribute without requiring Python to be installed:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed main.py --name "OrbitManager"
```

The built app will be in the `dist/` folder.

---

## Dependencies

| Package | Purpose | Required |
|---|---|---|
| PyQt6 | UI framework | Always |
| soundfile | Audio file I/O for conversion | Only for conversion |
| resampy | High-quality resampling | Only for conversion |
| numpy | Array operations for audio | Only for conversion |

