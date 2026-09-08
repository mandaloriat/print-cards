"""Tests for print_cards.generator."""

from __future__ import annotations

import io
import struct
import zlib
from pathlib import Path

import pytest

from print_cards.generator import (
    GridLayout,
    PDFGenerator,
    PAGE_FORMATS,
    get_page_format,
    parse_hex_color,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_png(tmp_path: Path, name: str = "img.png", width: int = 100, height: int = 100) -> str:
    """Create a minimal valid PNG file and return its path as a string."""

    def _chunk(tag: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return length + tag + data + crc

    # IHDR
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)

    # IDAT – uncompressed RGB image (all white)
    raw_rows = b""
    for _ in range(height):
        raw_rows += b"\x00" + b"\xFF\xFF\xFF" * width  # filter=0, RGB
    idat = _chunk(b"IDAT", zlib.compress(raw_rows))

    iend = _chunk(b"IEND", b"")

    signature = b"\x89PNG\r\n\x1a\n"
    png_bytes = signature + ihdr + idat + iend

    path = tmp_path / name
    path.write_bytes(png_bytes)
    return str(path)


# ---------------------------------------------------------------------------
# get_page_format
# ---------------------------------------------------------------------------

class TestGetPageFormat:
    def test_known_formats(self):
        for fmt_name in PAGE_FORMATS:
            w, h = get_page_format(fmt_name)
            assert w > 0
            assert h > 0

    def test_unknown_format_raises(self):
        with pytest.raises(ValueError, match="Unknown page format"):
            get_page_format("B2")


# ---------------------------------------------------------------------------
# GridLayout.validate
# ---------------------------------------------------------------------------

class TestGridLayoutValidate:
    def _base(self, **kwargs) -> GridLayout:
        defaults = dict(
            rows=2, cols=3,
            element_width=60.0, element_height=40.0,
            page_format="A4",
        )
        defaults.update(kwargs)
        return GridLayout(**defaults)

    def test_valid_layout_does_not_raise(self):
        self._base().validate()

    def test_zero_rows_raises(self):
        with pytest.raises(ValueError, match="rows"):
            self._base(rows=0).validate()

    def test_zero_cols_raises(self):
        with pytest.raises(ValueError, match="cols"):
            self._base(cols=0).validate()

    def test_negative_element_width_raises(self):
        with pytest.raises(ValueError, match="element_width"):
            self._base(element_width=-1.0).validate()

    def test_invalid_image_fit_raises(self):
        with pytest.raises(ValueError, match="image_fit"):
            self._base(image_fit="bad-mode").validate()

    def test_negative_spacing_raises(self):
        with pytest.raises(ValueError, match="spacing_h"):
            self._base(spacing_h=-1.0).validate()

    def test_grid_too_wide_raises(self):
        # 10 columns * 30 mm = 300 mm > A4 width (210 mm)
        with pytest.raises(ValueError, match="too wide"):
            self._base(cols=10, element_width=30.0).validate()

    def test_grid_too_tall_raises(self):
        # 10 rows * 35 mm = 350 mm > A4 height (297 mm)
        with pytest.raises(ValueError, match="too tall"):
            self._base(rows=10, element_height=35.0).validate()

    def test_explicit_margins_respected(self):
        layout = self._base(
            rows=1, cols=1,
            element_width=50.0, element_height=50.0,
            margin_left=10.0, margin_top=10.0,
        )
        layout.validate()
        assert layout.resolved_margin_left() == 10.0
        assert layout.resolved_margin_top() == 10.0

    def test_auto_centering(self):
        layout = self._base(rows=1, cols=1, element_width=100.0, element_height=100.0)
        # A4 is 210 mm wide; grid is 100 mm → margin should be 55 mm
        assert abs(layout.resolved_margin_left() - 55.0) < 0.5
        assert abs(layout.resolved_margin_top() - 98.5) < 0.5

    def test_offset_is_applied_during_validation(self):
        layout = self._base(rows=1, cols=1, element_width=50.0, element_height=50.0, offset_x=-200.0)
        with pytest.raises(ValueError, match="too wide"):
            layout.validate()


# ---------------------------------------------------------------------------
# GridLayout dimension helpers
# ---------------------------------------------------------------------------

class TestGridLayoutDimensions:
    def test_total_grid_width(self):
        layout = GridLayout(rows=1, cols=3, element_width=50.0, element_height=30.0, spacing_h=5.0)
        # 3 * 50 + 2 * 5 = 160
        assert layout.total_grid_width_mm() == pytest.approx(160.0)

    def test_total_grid_height(self):
        layout = GridLayout(rows=4, cols=1, element_width=50.0, element_height=30.0, spacing_v=3.0)
        # 4 * 30 + 3 * 3 = 129
        assert layout.total_grid_height_mm() == pytest.approx(129.0)

    def test_page_dimensions_a4(self):
        layout = GridLayout(rows=1, cols=1, element_width=10.0, element_height=10.0, page_format="A4")
        assert abs(layout.page_width_mm() - 210.0) < 0.5
        assert abs(layout.page_height_mm() - 297.0) < 0.5


# ---------------------------------------------------------------------------
# PDFGenerator
# ---------------------------------------------------------------------------

class TestPDFGenerator:
    def test_image_box_fit_mode(self):
        result = PDFGenerator._image_box(
            image_width_pt=200.0,
            image_height_pt=100.0,
            box_x_pt=10.0,
            box_y_pt=20.0,
            box_width_pt=50.0,
            box_height_pt=50.0,
            mode="fit",
        )
        assert result == pytest.approx((10.0, 32.5, 50.0, 25.0, 0.0))

    def test_image_box_fill_mode(self):
        result = PDFGenerator._image_box(
            image_width_pt=200.0,
            image_height_pt=100.0,
            box_x_pt=10.0,
            box_y_pt=20.0,
            box_width_pt=50.0,
            box_height_pt=50.0,
            mode="fill",
        )
        assert result == pytest.approx((-15.0, 20.0, 100.0, 50.0, 1.0))

    def test_image_box_stretch_mode(self):
        result = PDFGenerator._image_box(
            image_width_pt=200.0,
            image_height_pt=100.0,
            box_x_pt=10.0,
            box_y_pt=20.0,
            box_width_pt=50.0,
            box_height_pt=50.0,
            mode="stretch",
        )
        assert result == pytest.approx((10.0, 20.0, 50.0, 50.0, 0.0))

    def test_image_box_crop_mode_does_not_upscale(self):
        result = PDFGenerator._image_box(
            image_width_pt=20.0,
            image_height_pt=10.0,
            box_x_pt=10.0,
            box_y_pt=20.0,
            box_width_pt=50.0,
            box_height_pt=50.0,
            mode="crop",
        )
        assert result == pytest.approx((25.0, 40.0, 20.0, 10.0, 0.0))

    def test_image_box_crop_mode_clips_large_image(self):
        result = PDFGenerator._image_box(
            image_width_pt=200.0,
            image_height_pt=100.0,
            box_x_pt=10.0,
            box_y_pt=20.0,
            box_width_pt=50.0,
            box_height_pt=50.0,
            mode="crop",
        )
        assert result == pytest.approx((-15.0, 20.0, 100.0, 50.0, 1.0))

    def test_generates_pdf_file(self, tmp_path):
        layout = GridLayout(
            rows=2, cols=2,
            element_width=80.0, element_height=60.0,
            spacing_h=5.0, spacing_v=5.0,
            page_format="A4",
        )
        img = _make_png(tmp_path)
        images = {
            (1, 1): img, (1, 2): img,
            (2, 1): img, (2, 2): img,
        }
        output = str(tmp_path / "out.pdf")
        PDFGenerator(layout).generate(images, output)
        assert Path(output).exists()
        assert Path(output).stat().st_size > 100

    def test_output_path_without_extension(self, tmp_path):
        layout = GridLayout(rows=1, cols=1, element_width=80.0, element_height=60.0)
        img = _make_png(tmp_path)
        output_no_ext = str(tmp_path / "result")
        PDFGenerator(layout).generate({(1, 1): img}, output_no_ext)
        assert Path(tmp_path / "result.pdf").exists()

    def test_missing_image_raises(self, tmp_path):
        layout = GridLayout(rows=1, cols=1, element_width=80.0, element_height=60.0)
        with pytest.raises(FileNotFoundError):
            PDFGenerator(layout).generate(
                {(1, 1): str(tmp_path / "ghost.png")},
                str(tmp_path / "out.pdf"),
            )

    def test_invalid_layout_raises(self, tmp_path):
        layout = GridLayout(rows=0, cols=1, element_width=80.0, element_height=60.0)
        with pytest.raises(ValueError):
            PDFGenerator(layout).generate({}, str(tmp_path / "out.pdf"))

    def test_sparse_images(self, tmp_path):
        """Only some cells populated – should not raise."""
        layout = GridLayout(rows=2, cols=2, element_width=80.0, element_height=60.0)
        img = _make_png(tmp_path)
        images = {(1, 1): img}  # only top-left
        output = str(tmp_path / "sparse.pdf")
        PDFGenerator(layout).generate(images, output)
        assert Path(output).exists()

    def test_output_directory_created(self, tmp_path):
        layout = GridLayout(rows=1, cols=1, element_width=50.0, element_height=50.0)
        img = _make_png(tmp_path)
        nested = tmp_path / "a" / "b" / "c" / "out.pdf"
        PDFGenerator(layout).generate({(1, 1): img}, str(nested))
        assert nested.exists()

    def test_single_card_centred_a4(self, tmp_path):
        """Single card must be centred: margin_left == margin_top check via layout."""
        layout = GridLayout(
            rows=1, cols=1,
            element_width=85.6, element_height=54.0,
            page_format="A4",
        )
        # Margin left = (210 - 85.6) / 2 ≈ 62.2 mm
        assert abs(layout.resolved_margin_left() - (210.0 - 85.6) / 2) < 0.1
        img = _make_png(tmp_path)
        output = str(tmp_path / "single.pdf")
        PDFGenerator(layout).generate({(1, 1): img}, output)
        assert Path(output).exists()

    def test_all_page_formats(self, tmp_path):
        """All registered page formats should produce a valid PDF."""
        img = _make_png(tmp_path)
        for fmt in PAGE_FORMATS:
            layout = GridLayout(
                rows=1, cols=1,
                element_width=40.0, element_height=40.0,
                page_format=fmt,
            )
            output = str(tmp_path / f"out_{fmt}.pdf")
            PDFGenerator(layout).generate({(1, 1): img}, output)
            assert Path(output).exists()

    def test_all_image_fit_modes(self, tmp_path):
        img = _make_png(tmp_path, width=120, height=60)
        for mode in ("fit", "fill", "stretch", "crop"):
            layout = GridLayout(
                rows=1,
                cols=1,
                element_width=40.0,
                element_height=40.0,
                image_fit=mode,
            )
            output = str(tmp_path / f"out_{mode}.pdf")
            PDFGenerator(layout).generate({(1, 1): img}, output)
            assert Path(output).exists()

    def test_bleed_generates_pdf(self, tmp_path):
        layout = GridLayout(
            rows=2, cols=2,
            element_width=60.0, element_height=85.0,
            spacing_h=4.0, spacing_v=4.0,
            bleed_width=2.0, bleed_color="#1d1d1d",
        )
        img = _make_png(tmp_path)
        images = {(1, 1): img, (1, 2): img, (2, 1): img, (2, 2): img}
        output = str(tmp_path / "bleed.pdf")
        PDFGenerator(layout).generate(images, output)
        assert Path(output).exists()
        assert Path(output).stat().st_size > 100

    def test_bleed_tile_is_larger_than_trim(self, tmp_path):
        """The bleed tile must extend beyond the trim box on every side."""
        img = _make_png(tmp_path, width=60, height=85)
        reader = PDFGenerator._build_bleed_tile(
            img, box_width_pt=60.0, box_height_pt=85.0,
            bleed_pt=6.0, color=(29, 29, 29), mode="fit",
        )
        w, h = reader.getSize()
        assert w > 60.0 and h > 85.0

    def test_bleed_tile_flattens_transparent_corner(self, tmp_path):
        """A fully transparent corner must become the bleed colour, not black."""
        from PIL import Image

        src = Image.new("RGBA", (80, 80), (200, 50, 50, 255))
        # punch a transparent block in the top-left corner
        for x in range(20):
            for y in range(20):
                src.putpixel((x, y), (0, 0, 0, 0))
        p = tmp_path / "rgba.png"
        src.save(p)

        reader = PDFGenerator._build_bleed_tile(
            str(p), box_width_pt=80.0, box_height_pt=80.0,
            bleed_pt=0.0, color=(29, 29, 29), mode="stretch",
        )
        tile = reader._image  # underlying PIL image
        assert tile.convert("RGB").getpixel((2, 2)) == (29, 29, 29)

    def test_crop_marks_generate_pdf(self, tmp_path):
        layout = GridLayout(
            rows=2, cols=2,
            element_width=60.0, element_height=85.0,
            spacing_h=4.0, spacing_v=4.0,
            crop_marks=3.0, crop_mark_color="#000000",
        )
        img = _make_png(tmp_path)
        images = {(1, 1): img, (1, 2): img, (2, 1): img, (2, 2): img}
        output = str(tmp_path / "crop.pdf")
        PDFGenerator(layout).generate(images, output)
        assert Path(output).exists()
        assert Path(output).stat().st_size > 100

    def test_crop_marks_with_bleed_generate_pdf(self, tmp_path):
        """Crop marks and bleed together must produce a valid PDF."""
        layout = GridLayout(
            rows=2, cols=2,
            element_width=60.0, element_height=85.0,
            spacing_h=4.0, spacing_v=4.0,
            bleed_width=2.0, bleed_color="#1d1d1d",
            crop_marks=3.0, crop_mark_color="#ff0000",
        )
        img = _make_png(tmp_path)
        images = {(1, 1): img, (1, 2): img, (2, 1): img, (2, 2): img}
        output = str(tmp_path / "crop_bleed.pdf")
        PDFGenerator(layout).generate(images, output)
        assert Path(output).exists()

    def test_crop_marks_emit_stroke_operators(self, tmp_path):
        """Enabling crop marks must add stroke drawing operators to the PDF."""
        layout = GridLayout(rows=1, cols=1, element_width=60.0, element_height=85.0)
        layout_marks = GridLayout(
            rows=1, cols=1, element_width=60.0, element_height=85.0,
            crop_marks=3.0,
        )
        img = _make_png(tmp_path)
        plain = tmp_path / "plain.pdf"
        marked = tmp_path / "marked.pdf"
        PDFGenerator(layout).generate({(1, 1): img}, str(plain))
        PDFGenerator(layout_marks).generate({(1, 1): img}, str(marked))
        # The marked PDF has extra path/stroke content, so it must be larger.
        assert marked.stat().st_size > plain.stat().st_size


# ---------------------------------------------------------------------------
# parse_hex_color
# ---------------------------------------------------------------------------

class TestParseHexColor:
    def test_full_hex(self):
        assert parse_hex_color("#1d1d1d") == (29, 29, 29)

    def test_without_hash(self):
        assert parse_hex_color("ffffff") == (255, 255, 255)

    def test_shorthand(self):
        assert parse_hex_color("#f0a") == (255, 0, 170)

    def test_invalid_length_raises(self):
        with pytest.raises(ValueError, match="Invalid hex colour"):
            parse_hex_color("#12345")

    def test_non_hex_digits_raise(self):
        with pytest.raises(ValueError, match="Invalid hex colour"):
            parse_hex_color("#zzzzzz")


class TestBleedValidation:
    def _base(self, **kwargs) -> GridLayout:
        defaults = dict(rows=1, cols=1, element_width=60.0, element_height=85.0)
        defaults.update(kwargs)
        return GridLayout(**defaults)

    def test_negative_bleed_raises(self):
        with pytest.raises(ValueError, match="bleed_width"):
            self._base(bleed_width=-1.0).validate()

    def test_bad_bleed_color_raises(self):
        with pytest.raises(ValueError, match="Invalid hex colour"):
            self._base(bleed_width=2.0, bleed_color="nope").validate()

    def test_bleed_disabled_ignores_color(self):
        # bleed_width == 0 -> colour never parsed, must not raise
        self._base(bleed_width=0.0, bleed_color="nope").validate()


class TestCropMarkValidation:
    def _base(self, **kwargs) -> GridLayout:
        defaults = dict(rows=1, cols=1, element_width=60.0, element_height=85.0)
        defaults.update(kwargs)
        return GridLayout(**defaults)

    def test_negative_crop_marks_raises(self):
        with pytest.raises(ValueError, match="crop_marks"):
            self._base(crop_marks=-1.0).validate()

    def test_bad_crop_mark_color_raises(self):
        with pytest.raises(ValueError, match="Invalid hex colour"):
            self._base(crop_marks=3.0, crop_mark_color="nope").validate()

    def test_crop_marks_disabled_ignores_color(self):
        # crop_marks == 0 -> colour never parsed, must not raise
        self._base(crop_marks=0.0, crop_mark_color="nope").validate()
