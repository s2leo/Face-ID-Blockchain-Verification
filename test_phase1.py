#!/usr/bin/env python3
"""
Phase 1 — Reverse Image Search Test Runner
===========================================

Usage:
    # Activate venv first
    source .venv/bin/activate

    # Run with SerpApi (default, recommended)
    python test_phase1.py --image samples/avatar.jpg

    # Specify provider
    python test_phase1.py --image samples/avatar.jpg --provider serpapi
    python test_phase1.py --image samples/avatar.jpg --provider google_vision

    # Use a public image URL
    python test_phase1.py --image "https://example.com/photo.jpg"

    # Save raw JSON results
    python test_phase1.py --image samples/avatar.jpg --save-json results/run1.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure we can import the local package
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from reverse_search import search_image, PROVIDERS

console = Console()


def build_results_table(response) -> Table:
    """Build a rich Table from a SearchResponse."""
    table = Table(
        title=f"🔍  Reverse Search Results — {response.provider}",
        box=box.ROUNDED,
        show_lines=True,
        title_style="bold cyan",
    )

    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("Platform", style="bold", width=14)
    table.add_column("Domain", width=22)
    table.add_column("Title", width=35, overflow="fold")
    table.add_column("URL", width=55, overflow="fold")
    table.add_column("Type", width=8)
    table.add_column("Social?", width=7, justify="center")

    for i, match in enumerate(response.matches, 1):
        is_social_marker = "✅" if match.is_social else "—"
        platform_text = match.platform or "—"

        # Highlight social matches in green
        row_style = "green" if match.is_social else ""

        table.add_row(
            str(i),
            platform_text,
            match.domain,
            match.title[:80] if match.title else "—",
            match.url[:120],
            match.match_type,
            is_social_marker,
            style=row_style,
        )

    return table


def print_summary(response) -> None:
    """Print a summary panel."""
    social = response.social_matches
    status_emoji = "✅" if response.has_social_match else "❌"

    summary_lines = [
        f"Query Image   : {response.query_image}",
        f"Provider      : {response.provider}",
        f"Total Matches : {response.match_count}",
        f"Social Matches: {len(social)}",
        "",
        f"{status_emoji}  Hackathon Req #2 (find real social match): "
        f"{'PASSED' if response.has_social_match else 'NOT YET — no social media match found'}",
    ]

    if social:
        summary_lines.append("")
        summary_lines.append("🎯  Social Media Matches Found:")
        for m in social:
            summary_lines.append(f"   • [{m.platform}] {m.url}")

    border_style = "green" if response.has_social_match else "red"
    console.print(
        Panel(
            "\n".join(summary_lines),
            title="📊 Summary",
            border_style=border_style,
            padding=(1, 2),
        )
    )


def save_results(response, output_path: str) -> None:
    """Save results to a JSON file for Phase 3/4 audit trail."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    audit_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "phase_1_derisking",
        **response.to_dict(),
    }

    # Don't include raw_response in audit (can be huge)
    audit_record.pop("raw_response", None)
    # But keep match data
    # Remove the full raw_response from each match too if present

    with open(out, "w") as f:
        json.dump(audit_record, f, indent=2, default=str)

    console.print(f"\n💾 Results saved to: [bold]{out}[/bold]")


def main():
    parser = argparse.ArgumentParser(
        description="Phase 1 — Reverse Image Search Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--image", "-i",
        required=True,
        help="Path to local image file or a public image URL",
    )
    parser.add_argument(
        "--provider", "-p",
        default="serpapi",
        choices=list(PROVIDERS.keys()),
        help="Search provider to use (default: serpapi)",
    )
    parser.add_argument(
        "--save-json", "-o",
        default=None,
        help="Optional path to save results as JSON (for Phase 3/4 audit)",
    )
    parser.add_argument(
        "--all-providers",
        action="store_true",
        help="Run search across ALL configured providers",
    )

    args = parser.parse_args()

    # Header
    console.print()
    console.print(
        Panel(
            "[bold white]Phase 1: Derisking Reverse Image Search[/bold white]\n"
            "[dim]HH Goa 2026 — Task #3 Pipeline[/dim]",
            border_style="bright_blue",
            padding=(1, 2),
        )
    )

    if args.all_providers:
        providers_to_run = list(PROVIDERS.keys())
    else:
        providers_to_run = [args.provider]

    for provider_name in providers_to_run:
        console.print(f"\n🔄 Searching with [bold cyan]{provider_name}[/bold cyan]...")
        console.print(f"   Image: {args.image}")
        if not args.image.startswith(("http://", "https://")):
            console.print(
                "   [dim]📤 Local file detected — will auto-upload to temporary "
                "hosting for API access...[/dim]"
            )
        console.print()


        response = search_image(args.image, provider=provider_name)

        if response.error:
            console.print(
                Panel(
                    f"[bold red]Error:[/bold red] {response.error}",
                    title=f"❌ {provider_name}",
                    border_style="red",
                )
            )
            continue

        if response.match_count == 0:
            console.print(
                Panel(
                    "[yellow]No matches found.[/yellow]\n\n"
                    "Tips:\n"
                    "• Make sure the photo is of someone whose face appears publicly online\n"
                    "• Try a different photo or provider\n"
                    "• For face-based searches, ensure the image is clear and well-lit",
                    title=f"⚠️  {provider_name}",
                    border_style="yellow",
                )
            )
            continue

        # Show results table
        table = build_results_table(response)
        console.print(table)

        # Show summary
        print_summary(response)

        # Save if requested
        if args.save_json:
            # If running all providers, append provider name to filename
            if args.all_providers:
                base = Path(args.save_json)
                out_path = str(base.parent / f"{base.stem}_{provider_name}{base.suffix}")
            else:
                out_path = args.save_json
            save_results(response, out_path)

    console.print()


if __name__ == "__main__":
    main()

