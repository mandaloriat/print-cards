"""Command-line interface for print-cards."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

from .generator import GridLayout, PDFGenerator, PAGE_FORMATS, IMAGE_FIT_MODES


def _prompt(message: str, default: Optional[str] = None) -> str:
    """Print *message* and return stripped user input.

    If *default* is provided it is shown in brackets and returned when the
    user enters nothing.
    """
    if default is not None:
        full_message = f"{message} [{default}]: "
    else:
        full_message = f"{message}: "
    try:
        value = input(full_message).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    if not value and default is not None:
        return default
    return value


def _prompt_float(message: str, default: Optional[float] = None) -> float:
    """Prompt until the user enters a valid float."""
    default_str = str(default) if default is not None else None
    while True:
        raw = _prompt(message, default_str)
        try:
            return float(raw)
        except ValueError:
            print(f"  Please enter a valid number (e.g. 85.6).")


def _prompt_int(message: str, default: Optional[int] = None) -> int:
    """Prompt until the user enters a valid integer."""
    default_str = str(default) if default is not None else None
    while True:
        raw = _prompt(message, default_str)
        try:
            value = int(raw)
            if value < 1:
                print("  Please enter a positive integer.")
                continue
            return value
        except ValueError:
            print("  Please enter a valid integer.")


def _prompt_image_path(row: int, col: int) -> str:
    """Prompt until the user provides a path to an existing image file."""
    while True:
        path = _prompt(f"  Image file for element ({row},{col})")
        if not path:
            print("  Path cannot be empty.")
            continue
        expanded = os.path.expandvars(os.path.expanduser(path))
        if Path(expanded).is_file():
            return str(Path(expanded).resolve())
        print(f"  File not found: {expanded}. Please try again.")


def _prompt_back_image_path() -> Optional[str]:
    """Optionally prompt for a single back image used for all grid positions.

    Returns the resolved path, or *None* if the user leaves the prompt blank.
    """
    while True:
        try:
            raw = input(
                "  Back image file (leave empty to specify per position): "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        if not raw:
            return None
        expanded = os.path.expandvars(os.path.expanduser(raw))
        if Path(expanded).is_file():
            return str(Path(expanded).resolve())
        print(f"  File not found: {expanded}. Please try again.")


def _prompt_output_path(default_dir: Path) -> str:
    """Prompt for the output PDF file path."""
    default_path = str(default_dir / "output.pdf")
    while True:
        path = _prompt("Output PDF file path", default_path)
        expanded = os.path.expandvars(os.path.expanduser(path))
        if not expanded.lower().endswith(".pdf"):
            expanded += ".pdf"
        parent = Path(expanded).parent
        if not parent.exists():
            confirm = _prompt(
                f"  Directory '{parent}' does not exist. Create it? [y/N]", "N"
            )
            if confirm.lower() in ("y", "yes"):
                parent.mkdir(parents=True, exist_ok=True)
            else:
                continue
        return expanded


def _install_dir() -> Path:
    """Return the directory where the package is installed (or CWD as fallback)."""
    try:
        return Path(__file__).parent.resolve()
    except Exception:
        return Path.cwd()


def _build_layout_from_args(args: "argparse.Namespace") -> GridLayout:  # noqa: F821
    """Construct a *GridLayout* from parsed argparse arguments."""
    return GridLayout(
        rows=args.rows,
        cols=args.cols,
        element_width=args.element_width,
        element_height=args.element_height,
        spacing_h=args.spacing_h,
        spacing_v=args.spacing_v,
        margin_top=args.margin_top,
        margin_bottom=args.margin_bottom,
        margin_left=args.margin_left,
        margin_right=args.margin_right,
        offset_x=args.offset_x,
        offset_y=args.offset_y,
        page_format=args.format,
        image_fit=args.image_fit,
        bleed_width=args.bleed_width,
        bleed_color=args.bleed_color,
        crop_marks=args.crop_marks,
        crop_mark_color=args.crop_mark_color,
    )


def _build_layout_interactive() -> GridLayout:
    """Interactively ask the user for all layout parameters."""
    print("=== print-cards: Grid Layout Setup ===\n")

    valid_formats = ", ".join(sorted(PAGE_FORMATS))
    fmt = _prompt(f"Page format ({valid_formats})", "A4")
    while fmt not in PAGE_FORMATS:
        print(f"  Unknown format. Valid options: {valid_formats}")
        fmt = _prompt(f"Page format", "A4")

    rows = _prompt_int("Number of rows")
    cols = _prompt_int("Number of columns")

    ew = _prompt_float("Element width (mm)")
    eh = _prompt_float("Element height (mm)")

    sh = _prompt_float("Horizontal spacing between elements (mm)", 0.0)
    sv = _prompt_float("Vertical spacing between elements (mm)", 0.0)
    valid_image_fit = ", ".join(IMAGE_FIT_MODES)
    image_fit = _prompt(f"Image fit mode ({valid_image_fit})", "fit")
    while image_fit not in IMAGE_FIT_MODES:
        print(f"  Unknown image fit mode. Valid options: {valid_image_fit}")
        image_fit = _prompt("Image fit mode", "fit")

    print(
        "\nLeave margin fields empty to auto-centre the grid on the page.\n"
    )
    mt_raw = _prompt("Top margin (mm) [auto]", "")
    mb_raw = _prompt("Bottom margin (mm) [auto]", "")
    ml_raw = _prompt("Left margin (mm) [auto]", "")
    mr_raw = _prompt("Right margin (mm) [auto]", "")
    ox_raw = _prompt("Horizontal offset (mm) [0]", "0")
    oy_raw = _prompt("Vertical offset (mm) [0]", "0")

    print(
        "\nBleed extends each card by a solid-colour border into the gaps, so "
        "small sheet misalignment leaves no white edge. Leave 0 to disable.\n"
    )
    bw_raw = _prompt_float("Bleed width (mm)", 0.0)
    bc_raw = "#ffffff"
    if bw_raw > 0:
        bc_raw = _prompt("Bleed colour (hex, e.g. #1d1d1d)", "#ffffff")

    print(
        "\nCrop marks are thin ticks in the gaps pointing at each card's trim "
        "edges, to guide cutting. They sit outside the bleed. Leave 0 to "
        "disable.\n"
    )
    cm_raw = _prompt_float("Crop mark length (mm)", 0.0)
    cmc_raw = "#000000"
    if cm_raw > 0:
        cmc_raw = _prompt("Crop mark colour (hex)", "#000000")

    def _parse_optional_float(s: str) -> Optional[float]:
        s = s.strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None

    return GridLayout(
        rows=rows,
        cols=cols,
        element_width=ew,
        element_height=eh,
        spacing_h=sh,
        spacing_v=sv,
        margin_top=_parse_optional_float(mt_raw),
        margin_bottom=_parse_optional_float(mb_raw),
        margin_left=_parse_optional_float(ml_raw),
        margin_right=_parse_optional_float(mr_raw),
        offset_x=float(ox_raw),
        offset_y=float(oy_raw),
        page_format=fmt,
        image_fit=image_fit,
        bleed_width=bw_raw,
        bleed_color=bc_raw,
        crop_marks=cm_raw,
        crop_mark_color=cmc_raw,
    )


def run(args=None) -> None:
    """Entry-point that can be called from CLI or tests."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="print-cards",
        description=(
            "Generate a PDF with images arranged in a grid for printing on "
            "pre-cut sheets."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "All dimension values are in millimetres.\n\n"
            "Examples:\n"
            "  print-cards --rows 2 --cols 4 --element-width 85.6 --element-height 54\n"
            "  print-cards -r 3 -c 3 --element-width 63 --element-height 88 "
            "--spacing-h 2 --spacing-v 2\n"
            "  print-cards  (fully interactive mode)\n"
        ),
    )

    parser.add_argument(
        "--rows", "-r", type=int, default=None,
        help="Number of rows (positive integer)",
    )
    parser.add_argument(
        "--cols", "-c", type=int, default=None,
        help="Number of columns (positive integer)",
    )
    parser.add_argument(
        "--format", "-f",
        default=None,
        choices=list(PAGE_FORMATS),
        metavar="FORMAT",
        help=(
            f"Page format. Choices: {', '.join(sorted(PAGE_FORMATS))}. "
            "Default: A4"
        ),
    )
    parser.add_argument(
        "--element-width", type=float, default=None,
        help="Width of each element in mm",
    )
    parser.add_argument(
        "--element-height", type=float, default=None,
        help="Height of each element in mm",
    )
    parser.add_argument(
        "--image-fit",
        default="fit",
        choices=list(IMAGE_FIT_MODES),
        help="How each image is placed inside its box: fit, fill, stretch, or crop (default: fit)",
    )
    parser.add_argument(
        "--spacing-h", type=float, default=0.0,
        help="Horizontal spacing between elements in mm (default: 0)",
    )
    parser.add_argument(
        "--spacing-v", type=float, default=0.0,
        help="Vertical spacing between elements in mm (default: 0)",
    )
    parser.add_argument(
        "--margin-top", type=float, default=None,
        help="Top margin in mm (default: auto-centred)",
    )
    parser.add_argument(
        "--margin-bottom", type=float, default=None,
        help="Bottom margin in mm (default: auto-centred)",
    )
    parser.add_argument(
        "--margin-left", type=float, default=None,
        help="Left margin in mm (default: auto-centred)",
    )
    parser.add_argument(
        "--margin-right", type=float, default=None,
        help="Right margin in mm (default: auto-centred)",
    )
    parser.add_argument(
        "--bleed-width", type=float, default=0.0,
        help=(
            "Bleed border in mm added around every card and extending into the "
            "gaps, so slight sheet misalignment leaves no white edge "
            "(default: 0 = disabled)"
        ),
    )
    parser.add_argument(
        "--bleed-color", "--bleed-colour", default="#ffffff",
        metavar="HEX",
        help="Bleed colour as a hex string, e.g. #1d1d1d (default: #ffffff)",
    )
    parser.add_argument(
        "--crop-marks", type=float, default=0.0,
        metavar="MM",
        help=(
            "Length in mm of crop (trim) marks drawn in the gaps at each card "
            "corner to guide cutting; they sit outside the bleed "
            "(default: 0 = disabled)"
        ),
    )
    parser.add_argument(
        "--crop-mark-color", "--crop-mark-colour", default="#000000",
        metavar="HEX",
        help="Crop mark colour as a hex string (default: #000000)",
    )
    parser.add_argument(
        "--offset-x", type=float, default=0.0,
        help="Horizontal offset in mm applied after centring/margins (negative shifts left)",
    )
    parser.add_argument(
        "--offset-y", type=float, default=0.0,
        help="Vertical offset in mm applied after centring/margins (negative shifts up)",
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="Output PDF file path (will also be asked interactively if omitted)",
    )
    parser.add_argument(
        "--image", action="append", default=None,
        metavar="ROW,COL,PATH",
        help=(
            "Image file for a specific grid position, given as ROW,COL,PATH "
            "(1-based indices). May be repeated for every position. When all "
            "positions are covered the tool runs fully non-interactively."
        ),
    )
    parser.add_argument(
        "--back",
        default=None,
        metavar="PATH",
        help=(
            "A single image file used for every grid position not explicitly "
            "covered by --image. Convenient when all cards share the same back face."
        ),
    )

    parsed = parser.parse_args(args)

    # --- Decide if we have enough CLI args for a fully non-interactive run ---
    need_interactive_layout = (
        parsed.rows is None
        or parsed.cols is None
        or parsed.element_width is None
        or parsed.element_height is None
    )

    if need_interactive_layout:
        # Fallback to fully interactive layout setup, but honour any values
        # already supplied on the command line.
        if parsed.format is not None:
            print(f"Note: --format {parsed.format} specified via CLI.")
        layout = _build_layout_interactive()
    else:
        if parsed.format is None:
            parsed.format = "A4"
        layout = _build_layout_from_args(parsed)

    # Validate layout before collecting images
    try:
        layout.validate()
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # --- Collect image paths ---
    # Parse any --image ROW,COL,PATH arguments supplied on the command line.
    cli_images: Dict[Tuple[int, int], str] = {}
    if parsed.image:
        for img_spec in parsed.image:
            parts = img_spec.split(",", 2)
            if len(parts) != 3:
                print(
                    f"Error: --image value must be ROW,COL,PATH, got: {img_spec!r}",
                    file=sys.stderr,
                )
                sys.exit(1)
            try:
                row_idx, col_idx = int(parts[0]), int(parts[1])
            except ValueError:
                print(
                    f"Error: ROW and COL in --image must be integers, got: {img_spec!r}",
                    file=sys.stderr,
                )
                sys.exit(1)
            cli_images[(row_idx, col_idx)] = parts[2]

    # Resolve the --back image path if supplied.
    back_path: Optional[str] = None
    if parsed.back:
        expanded = os.path.expandvars(os.path.expanduser(parsed.back))
        back_path = str(Path(expanded).resolve())

    all_positions = {
        (r, c)
        for r in range(1, layout.rows + 1)
        for c in range(1, layout.cols + 1)
    }

    remaining = all_positions - cli_images.keys()

    if back_path is not None or not remaining:
        # Non-interactive: every position is covered by --image and/or --back.
        images = {
            pos: (cli_images[pos] if pos in cli_images else back_path)
            for pos in all_positions
        }
    else:
        print(
            f"\nLayout: {layout.rows} row(s) × {layout.cols} col(s) on {layout.page_format} "
            f"({layout.element_width}×{layout.element_height} mm per element)\n"
            "Please provide an image file for each grid position:\n"
        )
        back_path = _prompt_back_image_path()
        images = {}
        for row in range(1, layout.rows + 1):
            for col in range(1, layout.cols + 1):
                if back_path is not None:
                    images[(row, col)] = back_path
                else:
                    images[(row, col)] = _prompt_image_path(row, col)

    # --- Output path ---
    if parsed.output:
        output_path = os.path.expandvars(os.path.expanduser(parsed.output))
        if not output_path.lower().endswith(".pdf"):
            output_path += ".pdf"
    else:
        print()
        output_path = _prompt_output_path(_install_dir())

    # --- Generate ---
    print(f"\nGenerating PDF …")
    try:
        generator = PDFGenerator(layout)
        generator.generate(images, output_path)
    except (ValueError, FileNotFoundError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"PDF saved to: {output_path}")


def main() -> None:
    """Console-script entry point."""
    run()


if __name__ == "__main__":
    main()
