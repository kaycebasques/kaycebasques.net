"""Test for dragon correlations using hermetic Playwright."""

import json
import os
from pathlib import Path
import tempfile
import unittest

from dragon.correlations import (
    download_chart,
    generate_rst_index,
    load_snapshot,
    resolve_snapshot_file,
    URL,
)
from dragon.helpers import get_chromium_executable, launch_browser
from playwright.sync_api import sync_playwright


class CorrelationsTest(unittest.TestCase):

    def test_chromium_executable_exists(self):
        """Verifies that hermetic chromium binary is located in Bazel runfiles."""
        executable = get_chromium_executable()
        self.assertTrue(Path(executable).exists(), f"Chromium binary not found at {executable}")
        self.assertTrue(os.access(executable, os.X_OK), f"Chromium binary not executable: {executable}")

    def test_resolve_snapshot_file(self):
        """Verifies resolving snapshot paths with // or relative path."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws = Path(tmp_dir)
            snap_file = ws / "src/blog/2026/08/dragon/snapshot.json"
            snap_file.parent.mkdir(parents=True, exist_ok=True)
            snap_file.write_text("{}")

            resolved, out_dir = resolve_snapshot_file("//src/blog/2026/08/dragon/snapshot.json", ws)
            self.assertEqual(resolved, snap_file)
            self.assertEqual(out_dir, snap_file.parent / "correlations")

            resolved2, out_dir2 = resolve_snapshot_file("src/blog/2026/08/dragon/snapshot.json", ws)
            self.assertEqual(resolved2, snap_file)
            self.assertEqual(out_dir2, snap_file.parent / "correlations")

    def test_load_snapshot_schema_and_skip_null_proxies(self):
        """Verifies skipping null proxy tickers and parsing updated schema."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            snap_file = Path(tmp_dir) / "snapshot.json"
            snap_file.write_text(json.dumps({
                "20260820": {
                    "BCD": {"value": 4906, "proxy": "BCI"},
                    "BITW": {"value": 2445, "proxy": "IBIT"},
                    "BWX": {"value": 4905},
                    "CAOS": {"value": 7359, "proxy": None},
                    "CTA": {"value": 2450, "proxy": None},
                    "DBMF": {"value": 2453},
                }
            }))

            tickers_map, end_date, date_key = load_snapshot(snap_file)
            self.assertEqual(date_key, "20260820")
            self.assertEqual(end_date, "20-Aug-2026")
            self.assertIn("BCD", tickers_map)
            self.assertEqual(tickers_map["BCD"], "BCI")
            self.assertIn("BITW", tickers_map)
            self.assertEqual(tickers_map["BITW"], "IBIT")
            self.assertIn("BWX", tickers_map)
            self.assertEqual(tickers_map["BWX"], None)
            self.assertNotIn("CAOS", tickers_map)
            self.assertNotIn("CTA", tickers_map)

    def test_generate_rst_index(self):
        """Verifies generating correlations/index.rst structure."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir) / "correlations"
            tickers_map = {
                "BCD": "BCI",
                "BWX": None,
                "DBMF": None,
            }
            rst_path = generate_rst_index(out_dir, tickers_map)
            self.assertTrue(rst_path.exists())
            content = rst_path.read_text()
            self.assertIn("Correlations", content)
            self.assertIn("BCD\n===", content)
            self.assertIn("Proxy: BCI", content)
            self.assertIn("BCD vs BWX", content)
            self.assertIn(".. image:: BCD-BWX.png", content)
            self.assertIn(".. image:: BCD-DBMF.png", content)
            self.assertIn(".. image:: BWX-DBMF.png", content)


    def test_download_chart_single_non_duplicate_image(self):
        """Verifies downloading correlation chart produces a single non-duplicated image."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir)
            with sync_playwright() as p:
                browser = launch_browser(p, headless=True)
                page = browser.new_page()
                page.goto(URL, wait_until="domcontentloaded")

                # BCD (proxy BCI) vs VEA -> creates BCD-VEA.png
                img_path = download_chart(page, t1="BCD", t2="VEA", proxy1="BCI", proxy2=None, output_dir=out_path)

                self.assertTrue(img_path.exists(), f"File {img_path} was not created")
                self.assertEqual(img_path.name, "BCD-VEA.png")
                self.assertGreater(img_path.stat().st_size, 1000, f"File {img_path} is too small")

                # Verify no duplicate VEA-BCD.png or subdirectories were created
                self.assertFalse((out_path / "VEA-BCD.png").exists())
                self.assertFalse((out_path / "BCD").exists())

                browser.close()

    def test_error_on_invalid_ticker_without_proxy(self):
        """Verifies raising an error when ticker is invalid on ETFReplay and no proxy is given."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir)
            with sync_playwright() as p:
                browser = launch_browser(p, headless=True)
                page = browser.new_page()
                page.goto(URL, wait_until="domcontentloaded")

                with self.assertRaises(RuntimeError) as ctx:
                    download_chart(page, t1="INVALIDTICKER12345", t2="SPY", proxy1=None, proxy2=None, output_dir=out_path)
                self.assertTrue(
                    "ETFReplay returned error" in str(ctx.exception)
                    or "unavailable on ETFReplay" in str(ctx.exception)
                )

                browser.close()


if __name__ == "__main__":
    unittest.main()
