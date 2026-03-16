"""Tests for print_cards.cli."""

from __future__ import annotations

import io
import struct
import zlib
from pathlib import Path
from unittest.mock import patch

import pytest

from print_cards.cli import run


# ---------------------------------------------------------------------------
# Helper – tiny valid PNG
# ---------------------------------------------------------------------------

def _make_png(tmp_path: Path, name: str = "img.png") -> str:
    def _chunk(tag: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return length + tag + data + crc

    w, h = 10, 10
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    raw = b"".join(b"\x00" + b"\xFF\xFF\xFF" * w for _ in range(h))
    idat = _chunk(b"IDAT", zlib.compress(raw))
    iend = _chunk(b"IEND", b"")
    data = b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


# ---------------------------------------------------------------------------
# run() via CLI args + mocked interactive prompts
# ---------------------------------------------------------------------------

class TestCLIRun:
    def test_basic_2x2_grid(self, tmp_path):
        img = _make_png(tmp_path)
        output = str(tmp_path / "result.pdf")

        # 4 image prompts, then no interactive output prompt (--output supplied)
        with patch("builtins.input", side_effect=[img, img, img, img]):
            run([
                "--rows", "2", "--cols", "2",
                "--element-width", "80", "--element-height", "60",
                "--output", output,
            ])

        assert Path(output).exists()

    def test_missing_required_args_triggers_interactive(self, tmp_path):
        """When rows/cols/dimensions are omitted, interactive prompts are used."""
        img = _make_png(tmp_path)
        output = str(tmp_path / "interactive.pdf")

        # Interactive layout: format, rows, cols, ew, eh, sh, sv, image_fit, mt, mb, ml, mr, ox, oy
        # then 1 image prompt
        layout_inputs = ["A4", "1", "1", "50", "50", "0", "0", "fit", "", "", "", "", "0", "0"]
        image_inputs = [img]
        with patch("builtins.input", side_effect=layout_inputs + image_inputs):
            run(["--output", output])

        assert Path(output).exists()

    def test_invalid_layout_exits(self, tmp_path, capsys):
        """Grid too wide for the page should cause sys.exit(1)."""
        with pytest.raises(SystemExit) as exc_info:
            with patch("builtins.input", return_value=""):
                run([
                    "--rows", "1", "--cols", "10",
                    "--element-width", "30",   # 10 * 30 = 300 > 210 mm (A4)
                    "--element-height", "30",
                    "--output", str(tmp_path / "x.pdf"),
                ])
        assert exc_info.value.code == 1

    def test_output_extension_appended(self, tmp_path):
        img = _make_png(tmp_path)
        output_no_ext = str(tmp_path / "no_ext")

        with patch("builtins.input", side_effect=[img]):
            run([
                "--rows", "1", "--cols", "1",
                "--element-width", "50", "--element-height", "50",
                "--output", output_no_ext,
            ])

        assert Path(tmp_path / "no_ext.pdf").exists()

    def test_spacing_and_margins(self, tmp_path):
        img = _make_png(tmp_path)
        output = str(tmp_path / "spaced.pdf")
        with patch("builtins.input", side_effect=[img, img, img, img]):
            run([
                "--rows", "2", "--cols", "2",
                "--element-width", "60", "--element-height", "40",
                "--spacing-h", "5", "--spacing-v", "5",
                "--margin-left", "20", "--margin-top", "20",
                "--output", output,
            ])
        assert Path(output).exists()

    def test_image_fit_flag(self, tmp_path):
        img = _make_png(tmp_path)
        output = str(tmp_path / "fill.pdf")
        with patch("builtins.input", side_effect=[img]):
            run([
                "--rows", "1", "--cols", "1",
                "--element-width", "60", "--element-height", "40",
                "--image-fit", "fill",
                "--output", output,
            ])
        assert Path(output).exists()

    def test_offset_flags(self, tmp_path):
        img = _make_png(tmp_path)
        output = str(tmp_path / "offset.pdf")
        with patch("builtins.input", side_effect=[img]):
            run([
                "--rows", "1", "--cols", "1",
                "--element-width", "60", "--element-height", "40",
                "--offset-x", "-4.5",
                "--output", output,
            ])
        assert Path(output).exists()

    def test_image_flag_noninteractive(self, tmp_path):
        """--image ROW,COL,PATH for every position runs with no prompts."""
        img = _make_png(tmp_path)
        output = str(tmp_path / "flag.pdf")
        run([
            "--rows", "2", "--cols", "2",
            "--element-width", "80", "--element-height", "60",
            "--image", f"1,1,{img}",
            "--image", f"1,2,{img}",
            "--image", f"2,1,{img}",
            "--image", f"2,2,{img}",
            "--output", output,
        ])
        assert Path(output).exists()

    def test_image_flag_partial_falls_back_to_interactive(self, tmp_path):
        """When only some positions are given via --image, the missing ones are
        still prompted interactively (all positions are re-prompted in interactive
        mode)."""
        img = _make_png(tmp_path)
        output = str(tmp_path / "partial.pdf")
        # 1×2 grid; only (1,1) supplied via flag → interactive mode prompts
        # for both (1,1) and (1,2)
        with patch("builtins.input", side_effect=[img, img]):
            run([
                "--rows", "1", "--cols", "2",
                "--element-width", "80", "--element-height", "60",
                "--image", f"1,1,{img}",
                "--output", output,
            ])
        assert Path(output).exists()

    def test_image_flag_bad_format_exits(self, tmp_path):
        """Malformed --image value causes sys.exit(1)."""
        with pytest.raises(SystemExit) as exc_info:
            run([
                "--rows", "1", "--cols", "1",
                "--element-width", "50", "--element-height", "50",
                "--image", "bad-value-no-commas",
                "--output", str(tmp_path / "x.pdf"),
            ])
        assert exc_info.value.code == 1
