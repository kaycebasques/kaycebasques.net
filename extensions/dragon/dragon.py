import json
from pathlib import Path
from docutils import nodes
from docutils.parsers.rst import Directive
from sphinx.application import Sphinx


def format_asset_class(ac: str | None) -> str:
    if not ac:
        return ""
    mapping = {
        "bonds": "Bonds",
        "equities": "Equities",
        "managed_futures": "Managed Futures",
        "managed futures": "Managed Futures",
        "vol": "Long Vol",
        "long_vol": "Long Vol",
        "long vol": "Long Vol",
        "tips": "TIPS",
        "commodities": "Commodities",
        "crypto": "Crypto",
        "gold": "Gold",
        "long_usd": "Long USD",
        "long usd": "Long USD",
        "currencies": "Long USD",
        "currency": "Long USD",
    }
    key = ac.strip().lower()
    if key in mapping:
        return mapping[key]
    return ac.replace("_", " ").title()


def load_data(directive: Directive) -> tuple[dict, dict, int] | nodes.Node:
    date = directive.arguments[0].strip()
    snapshots_path = Path(__file__).parent / "snapshots.json"

    try:
        with open(snapshots_path, "r", encoding="utf-8") as f:
            snapshots = json.load(f)
    except Exception as e:
        return directive.state_machine.reporter.error(
            f"Failed to read snapshots.json: {e}",
            line=directive.lineno,
        )

    if date not in snapshots:
        return directive.state_machine.reporter.error(
            f"Snapshot not found for date: {date}",
            line=directive.lineno,
        )

    data = snapshots[date]
    total = sum(data.values())

    tickers_path = Path(__file__).parent / "tickers.json"
    tickers_meta = {}
    if tickers_path.exists():
        try:
            with open(tickers_path, "r", encoding="utf-8") as f:
                tickers_meta = json.load(f)
        except Exception:
            pass

    return data, tickers_meta, total, date


def build_snapshot_table(data: dict, tickers_meta: dict, total: int, date: str) -> nodes.table:
    ac_totals: dict[str, int] = {}
    ac_tickers: dict[str, list[str]] = {}
    for ticker, val in data.items():
        meta = tickers_meta.get(ticker.lower()) or tickers_meta.get(ticker.upper()) or {}
        ac = meta.get("ac", "other")
        ac_totals[ac] = ac_totals.get(ac, 0) + val
        ac_tickers.setdefault(ac, []).append(ticker)

    table = nodes.table(classes=["portfolio-snapshot"])
    table += nodes.title(text=f"Snapshot ({date})")
    tgroup = nodes.tgroup(cols=4)
    table += tgroup

    tgroup += nodes.colspec(colwidth=1)
    tgroup += nodes.colspec(colwidth=1)
    tgroup += nodes.colspec(colwidth=1)
    tgroup += nodes.colspec(colwidth=1)

    thead = nodes.thead()
    tgroup += thead
    head_row = nodes.row()
    thead += head_row

    for header in ["Asset Class", "Constituents", "Value", "Weight"]:
        entry = nodes.entry()
        entry += nodes.paragraph(text=header)
        head_row += entry

    tbody = nodes.tbody()
    tgroup += tbody

    for ac, ac_val in ac_totals.items():
        ac_slug = ac.strip().lower().replace(" ", "_")
        row = nodes.row(classes=[f"ac-{ac_slug}"])
        tbody += row

        entry_ac = nodes.entry()
        entry_ac += nodes.paragraph(text=format_asset_class(ac))
        row += entry_ac

        entry_tickers = nodes.entry()
        p_tickers = nodes.paragraph()
        tickers_list = ac_tickers.get(ac, [])
        for i, ticker_name in enumerate(tickers_list):
            if i > 0:
                p_tickers += nodes.inline(text=", ")
            t_meta = tickers_meta.get(ticker_name.lower()) or tickers_meta.get(ticker_name.upper()) or {}
            t_url = t_meta.get("url")
            if t_url:
                p_tickers += nodes.reference(text=str(ticker_name), refuri=t_url)
            else:
                p_tickers += nodes.inline(text=str(ticker_name))
            t_val = data.get(ticker_name, 0)
            t_weight = (t_val / total * 100) if total else 0
            t_weight_str = f"{round(t_weight, 1):g}%"
            p_tickers += nodes.inline(text=f" ({t_weight_str})")
        entry_tickers += p_tickers
        row += entry_tickers

        entry_val = nodes.entry()
        entry_val += nodes.paragraph(text=str(ac_val))
        row += entry_val

        weight = (ac_val / total * 100) if total else 0
        weight_str = f"{round(weight, 1):g}%"
        entry_weight = nodes.entry()
        entry_weight += nodes.paragraph(text=weight_str)
        row += entry_weight

    return table


class SnapshotDirective(Directive):
    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = False

    def run(self) -> list[nodes.Node]:
        res = load_data(self)
        if isinstance(res, nodes.Node):
            return [res]
        data, tickers_meta, total, date = res
        return [build_snapshot_table(data, tickers_meta, total, date)]


def setup(app: Sphinx) -> dict[str, bool]:
    app.add_directive("snapshot", SnapshotDirective)
    return {
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
