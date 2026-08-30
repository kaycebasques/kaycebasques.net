"""Playwright script to generate and download ETF correlation charts from etfreplay.com."""

import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sys
from playwright.sync_api import Page, sync_playwright

from correlations.helpers import launch_browser

URL = "https://www.etfreplay.com/correlation.aspx"


def get_workspace_root() -> Path:
    """Returns the Bazel workspace root directory."""
    if "BUILD_WORKSPACE_DIRECTORY" in os.environ:
        return Path(os.environ["BUILD_WORKSPACE_DIRECTORY"]).resolve()
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / "MODULE.bazel").is_file() or (parent / "WORKSPACE").is_file():
            return parent
    return Path.cwd().resolve()


def resolve_correlations_file(target: str, workspace_root: Path | None = None) -> tuple[Path, Path]:
    """Resolves correlations file path argument to (correlations_file, output_correlations_dir).

    Requires path format starting with '//' representing the repository root, e.g.:
      '//src/blog/2026/08/dragon/correlations.json'
    """
    clean = target.strip()
    if not clean.startswith("//"):
        raise ValueError(
            f"Invalid path '{target}'. Path must start with '//' representing the repository root "
            f"(e.g. '//src/blog/2026/08/dragon/correlations.json')."
        )

    ws = workspace_root or get_workspace_root()
    relative_path = clean[2:]
    correlations_file = (ws / relative_path).resolve()

    if not correlations_file.is_file():
        raise FileNotFoundError(f"Correlations file not found: {correlations_file}")

    return correlations_file, correlations_file.parent / "correlations"


def load_correlations(correlations_path: Path) -> dict[str, str | None]:
    """Loads tickers and proxies mapping from correlations.json.

    Expected correlations.json format:
      {
        "tickers": ["SGOL", ...],
        "proxies": {"BITW": "BITO"}
      }

    Returns:
      tickers_map: dict[str, str | None] mapping ticker -> proxy (or None)
    """
    with open(correlations_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid correlations.json format in {correlations_path}, expected a JSON object.")

    raw_tickers = data.get("tickers")
    if not isinstance(raw_tickers, list) or not raw_tickers:
        raise ValueError(f"No tickers found in correlations file: {correlations_path}")

    raw_proxies = data.get("proxies", {})
    if not isinstance(raw_proxies, dict):
        raise ValueError(f"Expected 'proxies' to be a dict in {correlations_path}")

    proxies_map: dict[str, str] = {}
    for k, v in raw_proxies.items():
        if v is not None:
            v_str = str(v).strip().upper()
            if v_str:
                proxies_map[str(k).strip().upper()] = v_str

    tickers_map: dict[str, str | None] = {}
    for item in raw_tickers:
        ticker = str(item).strip().upper()
        if ticker:
            tickers_map[ticker] = proxies_map.get(ticker)

    if not tickers_map:
        raise ValueError(f"No valid tickers found in {correlations_path}")

    return tickers_map


def download_chart(
    page: Page,
    t1: str,
    t2: str,
    proxy1: str | None = None,
    proxy2: str | None = None,
    output_dir: Path | None = None,
    lookback: str = "120",
    start_date: str = "03-Jan-2000",
    end_date: str | None = None,
) -> Path:
    """Configures correlation options, runs calculation, checks for errors, and downloads screenshot."""
    if output_dir is None:
        output_dir = get_workspace_root() / "tmp"

    query1 = proxy1 or t1
    query2 = proxy2 or t2

    page.select_option("#ddl_lookback", str(lookback))
    page.fill("#txt_start", start_date)

    if not end_date:
        now = datetime.now()
        if now.weekday() >= 5:
            delta = timedelta(days=now.weekday() - 4)
            now = now - delta
        end_date = now.strftime("%d-%b-%Y")

    page.fill("#txt_end", end_date)
    page.fill("#ContentPlaceHolder1_gvETFs_txtETF_0", query1)
    page.fill("#ContentPlaceHolder1_gvETFs_txtETF_1", query2)

    page.click("#btn_select")
    page.wait_for_timeout(100)  # Wait for the "processing" popup to appear
    while page.is_visible('img[alt="processing"][src="/images/activity.gif"]'):
        page.wait_for_timeout(500)
    page.wait_for_timeout(3000)  # Wait for image download and rendering

    # Check for error message on page
    err_locator = page.locator("#ContentPlaceHolder1_lbl_error")
    if err_locator.count() > 0:
        err_msg = err_locator.inner_text().strip()
        if err_msg:
            raise RuntimeError(
                f"ETFReplay returned error for '{query1}' vs '{query2}': '{err_msg}'. "
                f"Please provide a valid 'proxy' in snapshot.json for unsupported tickers."
            )

    chartbox = page.locator("div.chartbox")
    if chartbox.count() == 0 or not chartbox.is_visible():
        raise RuntimeError(
            f"Correlation chart was not generated for '{query1}' vs '{query2}'. "
            f"Ticker '{query1}' or '{query2}' is unavailable on ETFReplay. "
            f"Please provide a valid 'proxy' in snapshot.json for unsupported tickers."
        )

    pair_name = f"{min(t1, t2)}-{max(t1, t2)}"
    img_path = output_dir / f"{pair_name}.png"
    img_path.parent.mkdir(parents=True, exist_ok=True)

    chartbox.screenshot(path=str(img_path))

    p1_str = f" (proxy: {proxy1})" if proxy1 else ""
    p2_str = f" (proxy: {proxy2})" if proxy2 else ""
    print(f"Saved chart for {t1}{p1_str} vs {t2}{p2_str} -> {img_path}")
    return img_path


def generate_rst_index(
    output_dir: Path,
    tickers_map: dict[str, str | None],
) -> Path:
    """Generates correlations/index.rst displaying all correlation charts."""
    tickers = list(tickers_map.keys())
    lines: list[str] = []

    title = "Correlations"
    lines.append("=" * len(title))
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")

    for t1 in tickers:
        lines.append(t1)
        lines.append("=" * len(t1))
        lines.append("")

        for t2 in tickers:
            if t1 == t2:
                continue
            pair_name = f"{min(t1, t2)}-{max(t1, t2)}.png"
            sub_header = f"{t1} vs {t2}"
            lines.append(sub_header)
            lines.append("-" * len(sub_header))
            lines.append("")
            p1 = tickers_map.get(t1)
            if p1:
                lines.append(f"{t1} proxy: {p1}")
                lines.append("")
            p2 = tickers_map.get(t2)
            if p2:
                lines.append(f"{t2} proxy: {p2}")
                lines.append("")
            lines.append(f".. image:: {pair_name}")
            lines.append("")

    rst_path = output_dir / "index.rst"
    rst_path.parent.mkdir(parents=True, exist_ok=True)
    rst_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated reStructuredText index at: {rst_path}")
    return rst_path


def run_correlations(
    tickers_map: dict[str, str | None],
    output_dir: Path,
    lookback: str = "120",
    start_date: str = "03-Jan-2000",
    end_date: str | None = None,
    force: bool = False,
    headless: bool = True,
) -> list[Path]:
    """Runs correlation matrix generation using Playwright."""
    results: list[Path] = []
    tickers = list(tickers_map.keys())
    total_pairs = (len(tickers) * (len(tickers) - 1)) // 2
    print(f"Generating correlations for {len(tickers)} tickers ({total_pairs} unique pairs)...")
    print(f"Output directory: {output_dir}")

    needed_pairs: list[tuple[str, str, str, Path]] = []
    for i, a in enumerate(tickers):
        for b in tickers[i + 1 :]:
            pair_name = f"{min(a, b)}-{max(a, b)}"
            img_path = output_dir / f"{pair_name}.png"

            if not force and img_path.exists() and img_path.stat().st_size > 1000:
                print(f"Skipping existing chart: {pair_name}")
                results.append(img_path)
            else:
                needed_pairs.append((a, b, pair_name, img_path))

    if needed_pairs:
        with sync_playwright() as p:
            browser = launch_browser(p, headless=headless)
            page = browser.new_page()
            page.goto(URL, wait_until="domcontentloaded")

            for idx, (a, b, pair_name, img_path) in enumerate(needed_pairs, 1):
                proxy_a = tickers_map.get(a)
                proxy_b = tickers_map.get(b)
                label_a = f"{a} (proxy: {proxy_a})" if proxy_a else a
                label_b = f"{b} (proxy: {proxy_b})" if proxy_b else b
                print(f"[{idx}/{len(needed_pairs)}] Processing {label_a} vs {label_b}...")

                res = download_chart(
                    page=page,
                    t1=a,
                    t2=b,
                    proxy1=proxy_a,
                    proxy2=proxy_b,
                    output_dir=output_dir,
                    lookback=lookback,
                    start_date=start_date,
                    end_date=end_date,
                )
                results.append(res)

            browser.close()

    generate_rst_index(output_dir, tickers_map)
    print(f"Finished. All charts and index.rst saved to {output_dir}.")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download correlation charts from etfreplay.com using hermetic Playwright."
    )
    parser.add_argument(
        "correlations_path",
        help="Path to correlations.json starting with '//' from repo root (e.g. '//src/blog/2026/08/dragon/correlations.json')",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Custom output directory for saved chart images (default: <correlations_dir>/correlations)",
    )
    parser.add_argument(
        "--lookback",
        default="120",
        help="Lookback days for correlation (default: 120)",
    )
    parser.add_argument(
        "--start-date",
        default="03-Jan-2000",
        help="Start date (default: 03-Jan-2000)",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="End date (default: latest weekday)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite of existing chart images",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run browser in headless mode (default: True)",
    )
    args = parser.parse_args()
    ws_root = get_workspace_root()

    correlations_file, default_output_dir = resolve_correlations_file(args.correlations_path, ws_root)
    print(f"Loaded correlations file: {correlations_file}")
    tickers_map = load_correlations(correlations_file)
    print(f"Active tickers: {', '.join(f'{k}->{v}' if v else k for k, v in tickers_map.items())}")

    out_dir = Path(args.output_dir).resolve() if args.output_dir else default_output_dir

    run_correlations(
        tickers_map=tickers_map,
        output_dir=out_dir,
        lookback=args.lookback,
        start_date=args.start_date,
        end_date=args.end_date,
        force=args.force,
        headless=args.headless,
    )


if __name__ == "__main__":
    main()
