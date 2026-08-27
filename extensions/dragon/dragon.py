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


class PortfolioDirective(Directive):
    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = False

    def run(self) -> list[nodes.Node]:
        date = self.arguments[0].strip()
        snapshots_path = Path(__file__).parent / "snapshots.json"

        try:
            with open(snapshots_path, "r", encoding="utf-8") as f:
                snapshots = json.load(f)
        except Exception as e:
            error = self.state_machine.reporter.error(
                f"Failed to read snapshots.json: {e}",
                line=self.lineno,
            )
            return [error]

        if date not in snapshots:
            error = self.state_machine.reporter.error(
                f"Snapshot not found for date: {date}",
                line=self.lineno,
            )
            return [error]

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

        # Summary table by asset class
        ac_totals: dict[str, int] = {}
        for ticker, val in data.items():
            meta = tickers_meta.get(ticker.lower()) or tickers_meta.get(ticker.upper()) or {}
            ac = meta.get("ac", "other")
            ac_totals[ac] = ac_totals.get(ac, 0) + val

        summary_table = nodes.table(classes=["portfolio-summary"])
        summary_table += nodes.title(text="Summary")
        s_tgroup = nodes.tgroup(cols=3)
        summary_table += s_tgroup

        s_tgroup += nodes.colspec(colwidth=1)
        s_tgroup += nodes.colspec(colwidth=1)
        s_tgroup += nodes.colspec(colwidth=1)

        s_thead = nodes.thead()
        s_tgroup += s_thead
        s_head_row = nodes.row()
        s_thead += s_head_row

        for header in ["Asset Class", "Value", "Weight"]:
            entry = nodes.entry()
            entry += nodes.paragraph(text=header)
            s_head_row += entry

        s_tbody = nodes.tbody()
        s_tgroup += s_tbody

        for ac, ac_val in ac_totals.items():
            ac_slug = ac.strip().lower().replace(" ", "_")
            row = nodes.row(classes=[f"ac-{ac_slug}"])
            s_tbody += row

            entry_ac = nodes.entry()
            entry_ac += nodes.paragraph(text=format_asset_class(ac))
            row += entry_ac

            entry_val = nodes.entry()
            entry_val += nodes.paragraph(text=str(ac_val))
            row += entry_val

            weight = (ac_val / total * 100) if total else 0
            weight_str = f"{round(weight, 1):g}%"
            entry_weight = nodes.entry()
            entry_weight += nodes.paragraph(text=weight_str)
            row += entry_weight

        # Detailed ticker table
        ticker_table = nodes.table(classes=["portfolio-details"])
        ticker_table += nodes.title(text="Details")
        tgroup = nodes.tgroup(cols=4)
        ticker_table += tgroup

        tgroup += nodes.colspec(colwidth=1)
        tgroup += nodes.colspec(colwidth=1)
        tgroup += nodes.colspec(colwidth=1)
        tgroup += nodes.colspec(colwidth=1)

        thead = nodes.thead()
        tgroup += thead
        head_row = nodes.row()
        thead += head_row

        for header in ["Ticker", "Asset Class", "Value", "Weight"]:
            entry = nodes.entry()
            entry += nodes.paragraph(text=header)
            head_row += entry

        tbody = nodes.tbody()
        tgroup += tbody

        for ticker, val in data.items():
            meta = tickers_meta.get(ticker.lower()) or tickers_meta.get(ticker.upper()) or {}
            row_classes = []
            ac = meta.get("ac")
            if ac:
                ac_slug = ac.strip().lower().replace(" ", "_")
                row_classes.append(f"ac-{ac_slug}")

            row = nodes.row(classes=row_classes)
            tbody += row

            entry_ticker = nodes.entry()
            p_ticker = nodes.paragraph()
            url = meta.get("url")
            if url:
                p_ticker += nodes.reference(text=str(ticker), refuri=url)
            else:
                p_ticker += nodes.inline(text=str(ticker))
            entry_ticker += p_ticker
            row += entry_ticker

            entry_ac = nodes.entry()
            entry_ac += nodes.paragraph(text=format_asset_class(ac))
            row += entry_ac

            entry_val = nodes.entry()
            entry_val += nodes.paragraph(text=str(val))
            row += entry_val

            weight = (val / total * 100) if total else 0
            weight_str = f"{round(weight, 1):g}%"
            entry_weight = nodes.entry()
            entry_weight += nodes.paragraph(text=weight_str)
            row += entry_weight

        return [summary_table, ticker_table]


def setup(app: Sphinx) -> dict[str, bool]:
    app.add_directive("portfolio", PortfolioDirective)
    return {
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
