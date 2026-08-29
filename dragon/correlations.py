"""Playwright script to generate and download ETF correlation charts from etfreplay.com."""

import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sys
from playwright.sync_api import Page, sync_playwright

from dragon.helpers import launch_browser

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


def resolve_snapshot_file(target: str, workspace_root: Path | None = None) -> tuple[Path, Path]:
    """Resolves actual snapshot path argument to (snapshot_file, output_correlations_dir).

    Handles paths such as:
      - '//src/blog/2026/08/dragon/snapshot.json'
      - 'src/blog/2026/08/dragon/snapshot.json'
      - '/absolute/path/to/snapshot.json'
      - 'src/blog/2026/08/dragon' (directory containing snapshot.json)
    """
    ws = workspace_root or get_workspace_root()
    clean = target.strip()
    if clean.startswith("//"):
        clean = clean[2:]

    p = Path(clean)
    candidate_paths: list[Path] = []
    if p.is_absolute():
        candidate_paths.append(p)
        candidate_paths.append(p / "snapshot.json")
        candidate_paths.append(p / "snapshots.json")
    else:
        candidate_paths.append(ws / p)
        candidate_paths.append(ws / p / "snapshot.json")
        candidate_paths.append(ws / p / "snapshots.json")
        candidate_paths.append(Path.cwd() / p)
        candidate_paths.append(Path.cwd() / p / "snapshot.json")

    for candidate in candidate_paths:
        if candidate.is_file():
            return candidate.resolve(), candidate.resolve().parent / "correlations"

    searched = [str(c) for c in candidate_paths]
    raise FileNotFoundError(
        f"Could not find snapshot file at target path '{target}'.\n"
        f"Searched paths:\n  " + "\n  ".join(searched)
    )


def load_snapshot(snapshot_path: Path) -> tuple[dict[str, str | None], str | None, str | None]:
    """Loads tickers (skipping ones with proxy: null) and snapshot date.

    Returns:
      (active_tickers_map, end_date_formatted, raw_date_key)
    """
    with open(snapshot_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_date_key = None
    positions = None

    if "positions" in data and isinstance(data["positions"], dict):
        positions = data["positions"]
        raw_date_key = data.get("date")
    else:
        for k, v in data.items():
            if isinstance(v, dict):
                raw_date_key = k
                positions = v
                break

    if positions is None:
        raise ValueError(f"Could not find positions data in snapshot file: {snapshot_path}")

    end_date = None
    if raw_date_key:
        raw_str = str(raw_date_key).strip()
        dt = None
        for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y/%m/%d", "%d-%b-%Y"):
            try:
                dt = datetime.strptime(raw_str, fmt)
                break
            except ValueError:
                pass
        if dt:
            if dt.weekday() >= 5:
                dt = dt - timedelta(days=dt.weekday() - 4)
            end_date = dt.strftime("%d-%b-%Y")

    active_tickers: dict[str, str | None] = {}
    skipped_tickers: list[str] = []

    for ticker, info in positions.items():
        ticker_upper = str(ticker).strip().upper()
        if isinstance(info, dict):
            if "proxy" in info and info["proxy"] is None:
                skipped_tickers.append(ticker_upper)
                continue
            proxy_val = info.get("proxy")
            if proxy_val is not None:
                proxy_str = str(proxy_val).strip().upper()
                if proxy_str in ("NULL", "NONE", "FALSE", ""):
                    skipped_tickers.append(ticker_upper)
                    continue
                active_tickers[ticker_upper] = proxy_str
            else:
                active_tickers[ticker_upper] = None
        elif info is None:
            skipped_tickers.append(ticker_upper)
        else:
            active_tickers[ticker_upper] = None

    if skipped_tickers:
        print(f"Skipping tickers with null proxy: {', '.join(skipped_tickers)}")

    if not active_tickers:
        raise ValueError(f"No active tickers found in {snapshot_path}")

    return active_tickers, end_date, str(raw_date_key) if raw_date_key else None


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
        "snapshot_path",
        help="Path to snapshot.json (e.g. '//src/blog/2026/08/dragon/snapshot.json' or 'src/blog/2026/08/dragon/snapshot.json')",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Custom output directory for saved chart images (default: <snapshot_dir>/correlations)",
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
        help="End date (default: from snapshot date or current date)",
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

    snapshot_file, default_output_dir = resolve_snapshot_file(args.snapshot_path, ws_root)
    print(f"Loaded snapshot: {snapshot_file}")
    tickers_map, snapshot_end_date, raw_date_key = load_snapshot(snapshot_file)
    print(f"Active tickers: {', '.join(f'{k}->{v}' if v else k for k, v in tickers_map.items())}")

    out_dir = Path(args.output_dir).resolve() if args.output_dir else default_output_dir
    end_date = args.end_date or snapshot_end_date

    run_correlations(
        tickers_map=tickers_map,
        output_dir=out_dir,
        lookback=args.lookback,
        start_date=args.start_date,
        end_date=end_date,
        force=args.force,
        headless=args.headless,
    )


if __name__ == "__main__":
    main()
