# print-cards
A cross-platform CLI tool that generates a PDF with images arranged in a grid, perfectly centred on the page, so you can print on pre-cut sheets without alignment worries.

---

## Requirements

- Python 3.9+
- Works on **Linux**, **macOS**, and **Windows**

## Installation

```bash
python3 scripts/bootstrap.py
```

This command creates `.venv`, installs the Python CLI dependencies, and installs
the Electron GUI dependencies.

If you only need one side of the project:

```bash
python3 scripts/bootstrap.py --skip-gui
python3 scripts/bootstrap.py --skip-cli
```

For local development:

```bash
python3 scripts/bootstrap.py --editable
```

After bootstrap:

```bash
source .venv/bin/activate
print-cards
```

If you use `fish` instead of `bash`/`zsh`, activate the virtualenv with:

```fish
source .venv/bin/activate.fish
```

## Usage

### Fully interactive (no arguments needed)

```bash
print-cards
```

The tool will ask you interactively for:
1. Page format (A4, A3, A5, Letter, Legal, and landscape variants)
2. Number of rows and columns
3. Element dimensions (mm)
4. Spacing between elements (mm)
5. Margins (leave blank to auto-centre the grid)
6. An image file for every grid position `(row, col)` — row 1 is top, column 1 is left
7. Output PDF file path

### Command-line options

```
usage: print-cards [-h] [--rows ROWS] [--cols COLS] [--format FORMAT]
                   [--element-width ELEMENT_WIDTH] [--element-height ELEMENT_HEIGHT]
                   [--spacing-h SPACING_H] [--spacing-v SPACING_V]
                   [--margin-top MARGIN_TOP] [--margin-bottom MARGIN_BOTTOM]
                   [--margin-left MARGIN_LEFT] [--margin-right MARGIN_RIGHT]
                   [--output OUTPUT]
                   [--image ROW,COL,PATH ...]
```

| Option | Short | Description |
|---|---|---|
| `--rows` | `-r` | Number of rows (required unless interactive) |
| `--cols` | `-c` | Number of columns (required unless interactive) |
| `--format` | `-f` | Page format: `A3`, `A4` *(default)*, `A5`, `Letter`, `Legal`, and landscape variants (`A4L`, …) |
| `--element-width` | | Width of each element in **mm** |
| `--element-height` | | Height of each element in **mm** |
| `--image-fit` | | Image placement mode: `fit` *(default)*, `fill`, `stretch`, `crop` |
| `--spacing-h` | | Horizontal spacing between elements in mm (default: 0) |
| `--spacing-v` | | Vertical spacing between elements in mm (default: 0) |
| `--margin-top` | | Top margin in mm (default: auto-centred) |
| `--margin-bottom` | | Bottom margin in mm (default: auto-centred) |
| `--margin-left` | | Left margin in mm (default: auto-centred) |
| `--margin-right` | | Right margin in mm (default: auto-centred) |
| `--output` | `-o` | Output PDF path (asked interactively if omitted) |
| `--image` | | Image for a grid position as `ROW,COL,PATH`. Repeat for every cell. When all positions are covered the tool runs non-interactively (used by the GUI). |
| `--back` | | A single image file used for every grid position not explicitly covered by `--image`. Handy when all cards share the same back face. |

Any dimension option left out on the command line will be asked interactively.

Image placement modes:

* `fit`: preserve aspect ratio and show the whole image inside the box
* `fill`: preserve aspect ratio, fill the whole box, crop overflow
* `stretch`: force the image to the box dimensions, even if it distorts
* `crop`: keep native size when smaller, otherwise crop to the box without enlarging

### Examples

**Business cards (85.6 × 54 mm), 2 columns × 5 rows, A4:**

```bash
print-cards -r 5 -c 2 --element-width 85.6 --element-height 54 --spacing-h 2 --spacing-v 2
```

The tool then asks for 10 image paths one by one:

```
Layout: 5 row(s) × 2 col(s) on A4 (85.6×54.0 mm per element)
Please provide an image file for each grid position:

  Back image file (leave empty to specify per position): /path/to/back.png

Output PDF file path [/usr/local/lib/.../print_cards/output.pdf]: ~/Desktop/cards.pdf

Generating PDF …
PDF saved to: /home/user/Desktop/cards.pdf
```

Or, if you prefer to pass everything on the command line (e.g. 5 different fronts
but a single shared back):

```bash
print-cards -r 5 -c 2 --element-width 85.6 --element-height 54 \
  --image 1,1,card1.png --image 2,1,card2.png --image 3,1,card3.png \
  --image 4,1,card4.png --image 5,1,card5.png \
  --back back.png \
  --output ~/Desktop/cards.pdf
```

**Playing cards (63 × 88 mm), 3 × 3 grid, with explicit margins:**

```bash
print-cards -r 3 -c 3 --element-width 63 --element-height 88 \
  --spacing-h 2 --spacing-v 2 \
  --margin-left 15 --margin-top 15 \
  --output ~/Desktop/playing_cards.pdf
```

## How centring works

When no margins are specified, the grid is automatically centred on the page:

```
margin_left = (page_width  − (cols × element_width  + (cols−1) × spacing_h)) / 2
margin_top  = (page_height − (rows × element_height + (rows−1) × spacing_v)) / 2
```

## Development

```bash
python3 scripts/bootstrap.py --editable --skip-gui
pytest
```

## GUI (Electron)

A minimal Electron-based desktop GUI is available in the `gui/` directory.  It
lets you configure the grid layout, pick images for each cell with a file
chooser, and hit **Generate PDF** — without ever touching the terminal.

### Requirements

* Python 3.9+
* Node.js 18+ and npm

### Installation

```bash
python3 scripts/bootstrap.py
```

### Running

```bash
source .venv/bin/activate
cd gui
npm start
```

With `fish`, use `source .venv/bin/activate.fish` before `npm start`.

The app opens a window with two steps:

1. **Layout** — choose page format, rows/columns, element dimensions (mm),
   spacing, and optional margins (leave blank to auto-centre).
2. **Images** — a card appears for every grid position; click **Choose…** to
   pick an image file, set the output PDF path, then click **Generate PDF**.

The GUI calls `python3 -m print_cards.cli` internally, so the same Python
environment that can run `print-cards` from the command line is used.
