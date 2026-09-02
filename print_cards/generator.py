"""PDF generation logic for print-cards."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from reportlab.lib.pagesizes import A3, A4, A5, LETTER, LEGAL, landscape, portrait
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


# ---------------------------------------------------------------------------
# Page format registry
# ---------------------------------------------------------------------------

PAGE_FORMATS: Dict[str, Tuple[float, float]] = {
    "A3": A3,
    "A4": A4,
    "A5": A5,
    "Letter": LETTER,
    "Legal": LEGAL,
    "A3L": landscape(A3),
    "A4L": landscape(A4),
    "A5L": landscape(A5),
    "LetterL": landscape(LETTER),
    "LegalL": landscape(LEGAL),
}

IMAGE_FIT_MODES = ("fit", "fill", "stretch", "crop")


def parse_hex_color(value: str) -> Tuple[int, int, int]:
    """Parse a ``#RGB`` / ``#RRGGBB`` hex string into an ``(r, g, b)`` tuple.

    Raises:
        ValueError: If *value* is not a valid hex colour.
    """
    s = value.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) != 6:
        raise ValueError(
            f"Invalid hex colour {value!r}: expected '#RGB' or '#RRGGBB'"
        )
    try:
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    except ValueError:
        raise ValueError(f"Invalid hex colour {value!r}: non-hex digits")


def get_page_format(name: str) -> Tuple[float, float]:
    """Return the ReportLab page size tuple for the given format name.

    Args:
        name: Page format name (e.g. 'A4', 'Letter').

    Returns:
        A tuple ``(width, height)`` in ReportLab points.

    Raises:
        ValueError: If *name* is not a known page format.
    """
    key = name.strip()
    if key not in PAGE_FORMATS:
        valid = ", ".join(sorted(PAGE_FORMATS))
        raise ValueError(f"Unknown page format '{name}'. Valid formats: {valid}")
    return PAGE_FORMATS[key]


# ---------------------------------------------------------------------------
# Layout configuration
# ---------------------------------------------------------------------------

@dataclass
class GridLayout:
    """All measurements are in millimetres."""

    rows: int
    cols: int
    element_width: float
    element_height: float
    spacing_h: float = 0.0
    spacing_v: float = 0.0
    margin_top: Optional[float] = None
    margin_bottom: Optional[float] = None
    margin_left: Optional[float] = None
    margin_right: Optional[float] = None
    offset_x: float = 0.0
    offset_y: float = 0.0
    page_format: str = "A4"
    image_fit: str = "fit"
    bleed_width: float = 0.0
    bleed_color: str = "#ffffff"
    crop_marks: float = 0.0
    crop_mark_color: str = "#000000"

    def page_size_pt(self) -> Tuple[float, float]:
        """Return page size in ReportLab points."""
        return get_page_format(self.page_format)

    def total_grid_width_mm(self) -> float:
        """Total width occupied by the grid (elements + inner spacings)."""
        return self.cols * self.element_width + (self.cols - 1) * self.spacing_h

    def total_grid_height_mm(self) -> float:
        """Total height occupied by the grid (elements + inner spacings)."""
        return self.rows * self.element_height + (self.rows - 1) * self.spacing_v

    def page_width_mm(self) -> float:
        pw, _ = self.page_size_pt()
        return pw / mm

    def page_height_mm(self) -> float:
        _, ph = self.page_size_pt()
        return ph / mm

    def resolved_margin_left(self) -> float:
        if self.margin_left is not None:
            return self.margin_left
        return (self.page_width_mm() - self.total_grid_width_mm()) / 2.0

    def resolved_margin_top(self) -> float:
        if self.margin_top is not None:
            return self.margin_top
        return (self.page_height_mm() - self.total_grid_height_mm()) / 2.0

    def validate(self) -> None:
        """Raise *ValueError* if the layout does not fit on the page."""
        if self.rows < 1:
            raise ValueError("rows must be >= 1")
        if self.cols < 1:
            raise ValueError("cols must be >= 1")
        if self.element_width <= 0:
            raise ValueError("element_width must be > 0")
        if self.element_height <= 0:
            raise ValueError("element_height must be > 0")
        if self.spacing_h < 0:
            raise ValueError("spacing_h must be >= 0")
        if self.spacing_v < 0:
            raise ValueError("spacing_v must be >= 0")
        if self.image_fit not in IMAGE_FIT_MODES:
            valid = ", ".join(IMAGE_FIT_MODES)
            raise ValueError(f"image_fit must be one of: {valid}")
        if self.bleed_width < 0:
            raise ValueError("bleed_width must be >= 0")
        if self.bleed_width > 0:
            # Raises ValueError if the colour cannot be parsed.
            parse_hex_color(self.bleed_color)
        if self.crop_marks < 0:
            raise ValueError("crop_marks must be >= 0")
        if self.crop_marks > 0:
            # Raises ValueError if the colour cannot be parsed.
            parse_hex_color(self.crop_mark_color)

        ml = self.resolved_margin_left() + self.offset_x
        mt = self.resolved_margin_top() + self.offset_y

        if ml < 0:
            raise ValueError(
                f"Grid is too wide for the page: grid width {self.total_grid_width_mm():.1f} mm "
                f"> page width {self.page_width_mm():.1f} mm"
            )
        if mt < 0:
            raise ValueError(
                f"Grid is too tall for the page: grid height {self.total_grid_height_mm():.1f} mm "
                f"> page height {self.page_height_mm():.1f} mm"
            )

        # Check explicit right / bottom margins don't push grid off page
        if self.margin_right is not None:
            used = ml + self.total_grid_width_mm() + self.margin_right
            if used > self.page_width_mm() + 0.01:
                raise ValueError(
                    f"Left margin + grid + right margin ({used:.1f} mm) exceeds page width "
                    f"({self.page_width_mm():.1f} mm)"
                )
        if self.margin_bottom is not None:
            used = mt + self.total_grid_height_mm() + self.margin_bottom
            if used > self.page_height_mm() + 0.01:
                raise ValueError(
                    f"Top margin + grid + bottom margin ({used:.1f} mm) exceeds page height "
                    f"({self.page_height_mm():.1f} mm)"
                )


# ---------------------------------------------------------------------------
# PDF generator
# ---------------------------------------------------------------------------

class PDFGenerator:
    """Generates a single-page PDF with images placed on a grid."""

    def __init__(self, layout: GridLayout) -> None:
        self.layout = layout

    @staticmethod
    def _image_box(
        image_width_pt: float,
        image_height_pt: float,
        box_x_pt: float,
        box_y_pt: float,
        box_width_pt: float,
        box_height_pt: float,
        mode: str,
    ) -> Tuple[float, float, float, float, bool]:
        """Return drawImage geometry and whether the image must be clipped."""
        if image_width_pt <= 0 or image_height_pt <= 0:
            raise ValueError("Image dimensions must be > 0")

        if mode == "stretch":
            return box_x_pt, box_y_pt, box_width_pt, box_height_pt, False

        width_ratio = box_width_pt / image_width_pt
        height_ratio = box_height_pt / image_height_pt

        if mode == "fit":
            scale = min(width_ratio, height_ratio)
        elif mode == "fill":
            scale = max(width_ratio, height_ratio)
        elif mode == "crop":
            scale = min(1.0, max(width_ratio, height_ratio))
        else:
            raise ValueError(f"Unknown image_fit mode: {mode}")

        draw_width_pt = image_width_pt * scale
        draw_height_pt = image_height_pt * scale
        draw_x_pt = box_x_pt + (box_width_pt - draw_width_pt) / 2.0
        draw_y_pt = box_y_pt + (box_height_pt - draw_height_pt) / 2.0
        clip = mode in {"fill", "crop"} and (
            draw_width_pt > box_width_pt + 0.01 or draw_height_pt > box_height_pt + 0.01
        )
        return draw_x_pt, draw_y_pt, draw_width_pt, draw_height_pt, clip

    @staticmethod
    def _build_bleed_tile(
        img_path: str,
        box_width_pt: float,
        box_height_pt: float,
        bleed_pt: float,
        color: Tuple[int, int, int],
        mode: str,
    ) -> "ImageReader":
        """Build an ImageReader for a card padded with a solid bleed border.

        The source image is placed inside the *trim* box (``box_width_pt`` ×
        ``box_height_pt``) according to *mode*, on top of a solid *color*
        background so any transparency (e.g. rounded corners) is flattened to
        the bleed colour rather than black.  A *bleed_pt* border of the same
        colour is added on every side, so the returned tile is larger than the
        trim box and, when drawn, extends into the gaps between cards.
        """
        from PIL import Image

        src = Image.open(img_path).convert("RGBA")
        sw, sh = src.size

        # Pixel density (px per point) that preserves source detail without
        # upscaling it, floored at 300 dpi and capped to bound memory use.
        density = max(sw / box_width_pt, sh / box_height_pt, 300.0 / 72.0)
        density = min(density, 1200.0 / 72.0)

        trim_w = max(1, round(box_width_pt * density))
        trim_h = max(1, round(box_height_pt * density))
        bleed_px = max(0, round(bleed_pt * density))

        wr = trim_w / sw
        hr = trim_h / sh
        if mode == "stretch":
            new_w, new_h = trim_w, trim_h
        else:
            if mode == "fit":
                scale = min(wr, hr)
            elif mode == "fill":
                scale = max(wr, hr)
            elif mode == "crop":
                scale = min(1.0, max(wr, hr))
            else:
                scale = min(wr, hr)
            new_w = max(1, round(sw * scale))
            new_h = max(1, round(sh * scale))

        resized = src.resize((new_w, new_h), Image.LANCZOS)

        # Compose the art on a solid trim region (clips overflow for fill/crop),
        # then centre that region on a solid tile that includes the bleed ring.
        region = Image.new("RGBA", (trim_w, trim_h), color + (255,))
        region.paste(resized, ((trim_w - new_w) // 2, (trim_h - new_h) // 2), resized)

        tile = Image.new("RGB", (trim_w + 2 * bleed_px, trim_h + 2 * bleed_px), color)
        tile.paste(region.convert("RGB"), (bleed_px, bleed_px))
        return ImageReader(tile)

    def generate(
        self,
        images: Dict[Tuple[int, int], str],
        output_path: str,
    ) -> None:
        """Create the PDF at *output_path*.

        Args:
            images: Mapping of ``(row, col)`` → image file path.  Rows and
                columns are 1-based.
            output_path: Destination ``.pdf`` file path.

        Raises:
            ValueError: If the layout is invalid.
            FileNotFoundError: If an image file is missing.
        """
        self.layout.validate()

        for (row, col), img_path in images.items():
            if not Path(img_path).is_file():
                raise FileNotFoundError(
                    f"Image file not found for element ({row},{col}): {img_path}"
                )

        page_size = self.layout.page_size_pt()
        page_w_pt, page_h_pt = page_size

        output_path = str(output_path)
        if not output_path.lower().endswith(".pdf"):
            output_path += ".pdf"

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        c = canvas.Canvas(output_path, pagesize=page_size)

        ml_mm = self.layout.resolved_margin_left() + self.layout.offset_x
        mt_mm = self.layout.resolved_margin_top() + self.layout.offset_y

        ew_pt = self.layout.element_width * mm
        eh_pt = self.layout.element_height * mm
        sh_pt = self.layout.spacing_h * mm
        sv_pt = self.layout.spacing_v * mm
        ml_pt = ml_mm * mm
        mt_pt = mt_mm * mm

        use_bleed = self.layout.bleed_width and self.layout.bleed_width > 0
        # Kept even when bleed is disabled: it is the distance crop marks are
        # pushed outward so they sit *outside* the card's own bleed ring.
        bleed_pt = (self.layout.bleed_width or 0.0) * mm
        if use_bleed:
            bleed_rgb = parse_hex_color(self.layout.bleed_color)

        for row in range(1, self.layout.rows + 1):
            for col in range(1, self.layout.cols + 1):
                img_path = images.get((row, col))
                if img_path is None:
                    continue

                # x increases left→right; y increases bottom→top in ReportLab
                x_pt = ml_pt + (col - 1) * (ew_pt + sh_pt)
                # Row 1 is the topmost row
                y_from_top_pt = mt_pt + (row - 1) * (eh_pt + sv_pt)
                y_pt = page_h_pt - y_from_top_pt - eh_pt

                if use_bleed:
                    # Draw the card enlarged by the bleed on every side so the
                    # ink extends into the gaps between cards; the die-cut trim
                    # box stays centred on (x_pt, y_pt, ew_pt, eh_pt).
                    tile = self._build_bleed_tile(
                        img_path, ew_pt, eh_pt, bleed_pt, bleed_rgb,
                        self.layout.image_fit,
                    )
                    c.drawImage(
                        tile,
                        x_pt - bleed_pt,
                        y_pt - bleed_pt,
                        width=ew_pt + 2 * bleed_pt,
                        height=eh_pt + 2 * bleed_pt,
                        preserveAspectRatio=False,
                        mask="auto",
                    )
                    continue

                image = ImageReader(img_path)
                image_width_pt, image_height_pt = image.getSize()
                draw_x_pt, draw_y_pt, draw_width_pt, draw_height_pt, clip = self._image_box(
                    image_width_pt=image_width_pt,
                    image_height_pt=image_height_pt,
                    box_x_pt=x_pt,
                    box_y_pt=y_pt,
                    box_width_pt=ew_pt,
                    box_height_pt=eh_pt,
                    mode=self.layout.image_fit,
                )

                if clip:
                    c.saveState()
                    clip_path = c.beginPath()
                    clip_path.rect(x_pt, y_pt, ew_pt, eh_pt)
                    c.clipPath(clip_path, stroke=0, fill=0)

                c.drawImage(
                    img_path,
                    draw_x_pt,
                    draw_y_pt,
                    width=draw_width_pt,
                    height=draw_height_pt,
                    preserveAspectRatio=False,
                    mask="auto",
                )

                if clip:
                    c.restoreState()

        # --- Crop marks -----------------------------------------------------
        # Drawn in a second pass, on top of every card, so a neighbour's bleed
        # tile (drawn later in the loop above) can never cover them.  Each trim
        # corner gets an outward-pointing horizontal + vertical tick, offset by
        # the bleed so the marks stay *outside* the card's ink and only show in
        # the gaps between cards, indicating exactly where the trim edges are.
        if self.layout.crop_marks and self.layout.crop_marks > 0:
            mark_len_pt = self.layout.crop_marks * mm
            r, g, b = parse_hex_color(self.layout.crop_mark_color)
            c.setStrokeColorRGB(r / 255.0, g / 255.0, b / 255.0)
            c.setLineWidth(0.3)
            c.setLineCap(0)  # butt caps so ticks end exactly at the trim line
            off = bleed_pt
            for row in range(1, self.layout.rows + 1):
                for col in range(1, self.layout.cols + 1):
                    if images.get((row, col)) is None:
                        continue
                    x_pt = ml_pt + (col - 1) * (ew_pt + sh_pt)
                    y_from_top_pt = mt_pt + (row - 1) * (eh_pt + sv_pt)
                    y_pt = page_h_pt - y_from_top_pt - eh_pt
                    left, right = x_pt, x_pt + ew_pt
                    bottom, top = y_pt, y_pt + eh_pt

                    # bottom-left corner
                    c.line(left - off - mark_len_pt, bottom, left - off, bottom)
                    c.line(left, bottom - off - mark_len_pt, left, bottom - off)
                    # bottom-right corner
                    c.line(right + off, bottom, right + off + mark_len_pt, bottom)
                    c.line(right, bottom - off - mark_len_pt, right, bottom - off)
                    # top-left corner
                    c.line(left - off - mark_len_pt, top, left - off, top)
                    c.line(left, top + off, left, top + off + mark_len_pt)
                    # top-right corner
                    c.line(right + off, top, right + off + mark_len_pt, top)
                    c.line(right, top + off, right, top + off + mark_len_pt)

        c.save()
