# print-cards

Programmino per creare pdf con disposte alcune immagini a griglia per agevolare la stampa su fogli pre-tagliati.

> **English summary:** A cross-platform CLI tool that generates a PDF with images arranged in a grid, perfectly centred on the page, so you can print on pre-cut sheets without alignment worries.

---

## Requirements

- Python 3.9+
- Works on **Linux**, **macOS**, and **Windows**

## Installation

```bash
pip install .
```

This installs the `print-cards` command.

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
```

| Option | Short | Description |
|---|---|---|
| `--rows` | `-r` | Number of rows (required unless interactive) |
| `--cols` | `-c` | Number of columns (required unless interactive) |
| `--format` | `-f` | Page format: `A3`, `A4` *(default)*, `A5`, `Letter`, `Legal`, and landscape variants (`A4L`, …) |
| `--element-width` | | Width of each element in **mm** |
| `--element-height` | | Height of each element in **mm** |
| `--spacing-h` | | Horizontal spacing between elements in mm (default: 0) |
| `--spacing-v` | | Vertical spacing between elements in mm (default: 0) |
| `--margin-top` | | Top margin in mm (default: auto-centred) |
| `--margin-bottom` | | Bottom margin in mm (default: auto-centred) |
| `--margin-left` | | Left margin in mm (default: auto-centred) |
| `--margin-right` | | Right margin in mm (default: auto-centred) |
| `--output` | `-o` | Output PDF path (asked interactively if omitted) |

Any dimension option left out on the command line will be asked interactively.

### Examples

**Business cards (85.6 × 54 mm), 2 columns × 5 rows, A4:**

```bash
print-cards -r 5 -c 2 --element-width 85.6 --element-height 54 --spacing-h 2 --spacing-v 2
```

The tool then asks for 10 image paths one by one:

```
Layout: 5 row(s) × 2 col(s) on A4 (85.6×54.0 mm per element)
Please provide an image file for each grid position:

  Image file for element (1,1): /path/to/front.png
  Image file for element (1,2): /path/to/back.png
  ...

Output PDF file path [/usr/local/lib/.../print_cards/output.pdf]: ~/Desktop/cards.pdf

Generating PDF …
PDF saved to: /home/user/Desktop/cards.pdf
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
pip install -e .
pip install pytest
pytest
```

