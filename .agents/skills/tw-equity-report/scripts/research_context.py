#!/usr/bin/env python3
"""Build a compact FinMind baseline Markdown context (<= max-chars) for research verification.

Reads an existing scripts/equity/{code}-{YYYYMMDD}/ work folder or a direct data_{code}.json
file without writing into the repository work folder unless --out explicitly targets it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DEFAULT_MAX_CHARS = 2200


def resolve_data_json_path(target: Path) -> Path:
    """Resolve either a data_{code}.json file or a work folder containing exactly one."""
    resolved = Path(target)
    if resolved.is_file():
        return resolved
    if resolved.is_dir():
        matches = sorted(resolved.glob("data_*.json"))
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise FileNotFoundError(f"No data_*.json file found inside directory: {resolved}")
        raise ValueError(f"Expected one data_*.json inside {resolved}, found {len(matches)}")
    raise FileNotFoundError(f"Input path does not exist: {resolved}")


def _fmt_num(val: Any, decimals: int = 2, suffix: str = "") -> str:
    if val is None or isinstance(val, bool):
        return "n/a"
    try:
        num = float(val)
    except (TypeError, ValueError):
        return "n/a"
    return f"{num:,.{decimals}f}{suffix}"


def _fmt_signed(val: Any, decimals: int = 1, suffix: str = "%") -> str:
    if val is None or isinstance(val, bool):
        return "n/a"
    try:
        num = float(val)
    except (TypeError, ValueError):
        return "n/a"
    return f"{num:+,.{decimals}f}{suffix}"


def _fmt_nt_billions(val: Any) -> str:
    if val is None or isinstance(val, bool):
        return "n/a"
    try:
        num = float(val) / 1e9
    except (TypeError, ValueError):
        return "n/a"
    return f"NT${num:,.2f}B"


def build_context_markdown(data: dict[str, Any], *, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """Format key FinMind metrics from data_{code}.json into a bounded Markdown summary."""
    limit = max(200, int(max_chars))
    code = str(data.get("code") or "unknown").strip()
    asof = str(data.get("asof") or "unknown").strip()

    price_metrics = (data.get("price") or {}).get("metrics") or {}
    val = data.get("valuation") or {}
    per = val.get("PER") or {}
    pbr = val.get("PBR") or {}
    peers_data = data.get("peers") or {}
    peer_rows = peers_data.get("rows") or []
    peer_codes = [str(r.get("code")) for r in peer_rows if isinstance(r, dict) and r.get("code") and str(r.get("code")) != code]
    peer_med = peers_data.get("median") or {}

    rev = data.get("revenue") or {}
    rev_last12 = rev.get("last12") or []
    latest_rev = rev_last12[-1] if rev_last12 and isinstance(rev_last12[-1], dict) else {}

    fin = data.get("financials") or {}
    quarters = [q for q in (fin.get("quarters") or []) if isinstance(q, dict)]
    last4_quarters = quarters[-4:]
    cash_conv = fin.get("cash_conversion") or {}
    cb = fin.get("core_baseline") or {}
    gaps = [str(g).strip() for g in (data.get("gaps") or []) if str(g).strip()]

    header = f"# FinMind Ground-Truth Baseline: {code} (as of {asof})"
    price_line = (
        f"- **Price/Trend**: close={_fmt_num(price_metrics.get('close'))}, "
        f"MA20={_fmt_num(price_metrics.get('ma20'))} (5d slope={_fmt_signed(price_metrics.get('ma20_slope_5d'), 2, '')}), "
        f"MA60={_fmt_num(price_metrics.get('ma60'))} (5d slope={_fmt_signed(price_metrics.get('ma60_slope_5d'), 2, '')}), "
        f"alignment={price_metrics.get('alignment') or 'n/a'}"
    )
    val_line = (
        f"- **Valuation**: PER={_fmt_num(per.get('current'))}x (5y P{ _fmt_num(per.get('current_percentile'), 0) }), "
        f"PBR={_fmt_num(pbr.get('current'))}x (5y P{ _fmt_num(pbr.get('current_percentile'), 0) }), "
        f"div_yield={_fmt_num(val.get('dividend_yield'), 2, '%')} | "
        f"Peers[{','.join(peer_codes) or 'none'}] med PER={_fmt_num(peer_med.get('PER'))}x, PBR={_fmt_num(peer_med.get('PBR'))}x"
    )
    rev_line = (
        f"- **Revenue**: latest={rev.get('latest_period') or latest_rev.get('period') or 'n/a'} "
        f"{_fmt_nt_billions(latest_rev.get('revenue'))} "
        f"(MoM={_fmt_signed(latest_rev.get('mom_pct'))}, YoY={_fmt_signed(latest_rev.get('yoy_pct'))}); "
        f"YTD={_fmt_nt_billions(rev.get('ytd'))} (YTD YoY={_fmt_signed(rev.get('ytd_yoy_pct'))})"
    )

    implied_sh = fin.get("implied_shares")
    shares_b = (float(implied_sh) / 1e9) if isinstance(implied_sh, (int, float)) and not isinstance(implied_sh, bool) else None
    fin_line = (
        f"- **Financials**: latest_q={fin.get('latest_quarter') or 'n/a'}, "
        f"TTM EPS={_fmt_num(fin.get('ttm_eps'))}, BVPS={_fmt_num(fin.get('bvps_latest'))}, "
        f"cash_conv={_fmt_num(cash_conv.get('ratio'))}x, shares={_fmt_num(shares_b, 3, 'B')}"
    )

    if cb.get("applicable"):
        vol_tags = ",".join(str(x) for x in (cb.get("volatility_reasons") or []))
        vol_note = f", high_vol=True ({vol_tags})" if cb.get("high_volatility") else ", high_vol=False"
        cb_line = (
            f"- **Core Baseline**: applicable=True, CY EPS={_fmt_num(cb.get('cy_eps'))}, "
            f"NTM EPS={_fmt_num(cb.get('ntm_eps'))}, 6m_med_YoY={_fmt_signed(cb.get('yoy6_median_pct'))}{vol_note}"
        )
    else:
        reason = str(cb.get("reason") or "not applicable").strip()
        cb_line = f"- **Core Baseline**: applicable=False ({reason})"

    q_header = ["| Quarter | EPS | GM% | OPM% | DSI |", "| --- | --- | --- | --- | --- |"]
    q_rows = [
        f"| {q.get('quarter') or 'n/a'} | {_fmt_num(q.get('eps'))} | "
        f"{_fmt_num(q.get('gross_margin_pct'), 1, '%')} | {_fmt_num(q.get('operating_margin_pct'), 1, '%')} | "
        f"{_fmt_num(q.get('dsi_days'), 1)} |"
        for q in last4_quarters
    ]

    def _assemble(gaps_slice: list[str], rows_slice: list[str]) -> str:
        sections = [header, price_line, val_line, rev_line, fin_line, cb_line]
        if rows_slice:
            sections.append("")
            sections.extend(q_header)
            sections.extend(rows_slice)
        gap_text = "; ".join(gaps_slice) if gaps_slice else "None"
        sections.append(f"- **Data Gaps**: {gap_text}")
        return "\n".join(sections).strip() + "\n"

    candidate = _assemble(gaps, q_rows)
    if len(candidate) <= limit:
        return candidate

    # Trim gaps progressively first, then drop older quarterly rows while preserving core metrics.
    trimmed_gaps = list(gaps)
    while len(candidate) > limit and trimmed_gaps:
        trimmed_gaps.pop()
        suffix_gaps = trimmed_gaps + ([f"(+{len(gaps) - len(trimmed_gaps)} more)"] if len(gaps) > len(trimmed_gaps) else [])
        candidate = _assemble(suffix_gaps, q_rows)

    trimmed_rows = list(q_rows)
    while len(candidate) > limit and len(trimmed_rows) > 1:
        trimmed_rows.pop(0)
        suffix_gaps = ["(truncated)" if gaps else "None"] if gaps else []
        candidate = _assemble(suffix_gaps, trimmed_rows)

    if len(candidate) > limit:
        candidate = _assemble(["(truncated)" if gaps else "None"] if gaps else [], [])

    if len(candidate) > limit:
        return candidate[: max(0, limit - 4)].rstrip() + "...\n"
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="Work folder (scripts/equity/{code}-{YYYYMMDD}) or data_{code}.json path")
    parser.add_argument("--out", default="", help="Optional UTF-8 Markdown output file path (recommended in scratch run dir)")
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS, help="Strict character budget (default: 2200)")
    args = parser.parse_args(argv)

    data_path = resolve_data_json_path(args.target)
    data = json.loads(data_path.read_text(encoding="utf-8"))
    summary = build_context_markdown(data, max_chars=args.max_chars)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(summary, encoding="utf-8")
    else:
        print(summary, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
