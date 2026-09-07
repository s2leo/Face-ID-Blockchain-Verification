#!/usr/bin/env python3
"""
HH Goa 2026 — Task #3: End-to-End Face ID + Social Verification Pipeline
========================================================================

Complete Pipeline Execution:
  1. Detect & 5-point align face from input photo
  2. Extract 128-dimensional biometric embedding vector
  3. Pre-process into high-res canonical headshot
  4a. [Option A] Query multiple reverse image search providers and merge results
  4b. [Option B] Name-based social profile lookup (Instagram/Facebook/X/LinkedIn)
  5. Biometric Verification Filtering (Cosine similarity against candidate faces)
  6. Prepare tamper-evident cryptographic hash for blockchain recording

Usage:
    python run_pipeline.py --image samples/Anuj.jpg
    python run_pipeline.py --image samples/shruti2.jpeg --provider yandex
    python run_pipeline.py --image samples/shruti2.jpeg --multi-provider
    python run_pipeline.py --image samples/shruti2.jpeg --multi-provider --person-name "Shruti Haasan"
    python run_pipeline.py --image samples/shruti2.jpeg --provider serpapi --no-social-lookup
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ["OPENCV_LOG_LEVEL"] = "OFF"
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from face_pipeline import FacePipeline
from reverse_search import (
    search_image,
    merge_responses,
    find_social_profiles,
    BiometricVerifier,
    PROVIDERS,
    SearchResponse,
    GeminiVisionAnalyzer,
    GeminiAnalysis,
)

console = Console()

# Default providers used when --multi-provider is set
MULTI_PROVIDER_DEFAULT = ["serpapi", "yandex"]


def render_banner():
    console.print()
    console.print(
        Panel(
            "[bold white]HH Goa 2026 — Task #3 Build Pipeline[/bold white]\n"
            "[cyan]Biometric Face ID + Multi-Provider Search + Blockchain Verification[/cyan]",
            border_style="bright_blue",
            padding=(1, 2),
        )
    )


def run_pipeline(
    image_path: str,
    provider: str = "serpapi",
    multi_provider: bool = False,
    multi_providers: list[str] | None = None,
    face_index: int | None = None,
    verify_biometrics: bool = True,
    social_lookup: bool = True,
    use_gemini: bool = True,
    person_name: str | None = None,
    save_json: str | None = None,
):
    render_banner()

    # -------------------------------------------------------------------------
    # STEP 1: Biometric Face Detection & 128D Embedding
    # -------------------------------------------------------------------------
    console.print("\n[bold yellow]STEP 1: Biometric Face Detection & 128D Embedding[/bold yellow]")
    with console.status("[bold green]Loading neural models and analyzing face..."):
        pipeline = FacePipeline()
        face_result = pipeline.process_image(image_path, face_index=face_index)

    if not face_result.has_face:
        console.print(Panel(
            f"[bold red]Face Detection Failed:[/bold red] {face_result.error}",
            border_style="red",
        ))
        return

    primary_face = face_result.primary_face
    emb = primary_face.embedding
    emb_hash = hashlib.sha256(json.dumps(emb).encode()).hexdigest()

    face_summary = (
        f"[bold]Image:[/bold] {face_result.image_path} ({face_result.image_width}x{face_result.image_height})\n"
        f"[bold]Faces Detected:[/bold] {face_result.faces_detected} — Primary: Face #{primary_face.index}\n"
        f"[bold]Detector Confidence:[/bold] {primary_face.confidence * 100:.1f}%\n"
        f"[bold]Bounding Box (x,y,w,h):[/bold] {primary_face.box}\n"
        f"[bold]5-Point Landmarks:[/bold] {primary_face.landmarks}\n"
        f"[bold]Biometric Embedding:[/bold] 128-dimensional float32 vector\n"
        f"[bold]Embedding Preview:[/bold] [{', '.join(f'{x:.3f}' for x in emb[:5])}, ...]\n"
        f"[bold]Embedding SHA-256:[/bold] [green]{emb_hash}[/green]\n"
        f"[bold]Headshot Crop:[/bold] {primary_face.cropped_headshot_path}"
    )
    console.print(Panel(face_summary, title="👤 Biometric Profile Extracted", border_style="cyan"))

    search_input = primary_face.cropped_headshot_path or image_path

    # -------------------------------------------------------------------------
    # STEP 1.5: Gemini Vision Analysis
    # Extracts person identity, visible text (badges/nametags), context clues,
    # and generates targeted search queries — critical for non-famous individuals
    # -------------------------------------------------------------------------
    gemini_analysis: GeminiAnalysis | None = None
    gemini_name: str | None = None          # name Gemini found (overrides image-search detection)
    gemini_queries: list[str] = []          # ready-to-use search queries from Gemini

    if use_gemini:
        console.print(f"\n[bold yellow]STEP 1.5: Gemini Vision Analysis[/bold yellow]")
        with console.status("[bold green]Asking Gemini to analyze the photo..."):
            analyzer = GeminiVisionAnalyzer()
            # Use the original image — more context than the headshot crop
            gemini_analysis = analyzer.analyze(image_path)

        if not gemini_analysis.succeeded:
            console.print(f"   [yellow]⚠ Gemini unavailable: {gemini_analysis.error}[/yellow]")
            console.print("   [dim]Continuing without Gemini — pipeline still works.[/dim]")
        else:
            gemini_name    = gemini_analysis.best_name
            gemini_queries = gemini_analysis.generated_queries

            # Build display lines
            lines = []
            if gemini_analysis.identified_person:
                conf = gemini_analysis.identification_confidence
                conf_colour = {"high": "bold green", "medium": "green", "low": "yellow"}.get(conf, "dim")
                lines.append(
                    f"[bold]Identity:[/bold] [{conf_colour}]{gemini_analysis.identified_person}[/{conf_colour}]"
                    f"  ([dim]{conf} confidence — {gemini_analysis.identification_source or 'model recognition'}[/dim])"
                )
            else:
                lines.append("[bold]Identity:[/bold] [dim]Not recognised as a public figure[/dim]")

            if gemini_analysis.person_name_from_text:
                lines.append(
                    f"[bold]Name from image text:[/bold] [bold cyan]{gemini_analysis.person_name_from_text}[/bold cyan]"
                    f"  [dim](read from badge / caption / nametag)[/dim]"
                )

            if gemini_analysis.visible_text:
                lines.append(f"[bold]Visible text:[/bold] {', '.join(gemini_analysis.visible_text[:8])}")

            if gemini_analysis.context_clues:
                lines.append(f"[bold]Context clues:[/bold] {', '.join(gemini_analysis.context_clues[:5])}")

            if gemini_analysis.face_description:
                lines.append(f"[bold]Face description:[/bold] {gemini_analysis.face_description}")

            if gemini_queries:
                lines.append(f"[bold]Generated queries:[/bold] {len(gemini_queries)} targeted search queries")
                for q in gemini_queries[:3]:
                    lines.append(f"   [dim]→ {q}[/dim]")

            if gemini_name:
                lines.append(
                    f"\n[bold bright_white]→ Using name for social lookup:[/bold bright_white] "
                    f"[bold cyan]{gemini_name}[/bold cyan]"
                )
            else:
                lines.append(
                    "\n[dim]No name found by Gemini — will fall back to title extraction "
                    "from search results.[/dim]"
                )

            border = "green" if gemini_name else "yellow"
            console.print(Panel(
                "\n".join(lines),
                title="🤖 Gemini Vision Report",
                border_style=border,
            ))

    # -------------------------------------------------------------------------
    # STEP 2: Reverse Image Search  [Option A — single or multi-provider]
    # -------------------------------------------------------------------------
    providers_to_run = multi_providers or (MULTI_PROVIDER_DEFAULT if multi_provider else [provider])
    provider_label = " + ".join(p.upper() for p in providers_to_run)

    console.print(f"\n[bold yellow]STEP 2: Reverse Image Search[/bold yellow]")
    console.print(f"   Mode        : {'[bold magenta]MULTI-PROVIDER[/bold magenta]' if len(providers_to_run) > 1 else '[bold cyan]Single Provider[/bold cyan]'}")
    console.print(f"   Provider(s) : [bold cyan]{provider_label}[/bold cyan]")
    console.print(f"   Query Image : [dim]{search_input}[/dim]")

    individual_responses: list[SearchResponse] = []
    for prov in providers_to_run:
        with console.status(f"[bold green]Querying {prov}..."):
            resp = search_image(search_input, provider=prov)
        if resp.error:
            console.print(f"   [yellow]⚠ {prov}: {resp.error}[/yellow]")
        else:
            console.print(
                f"   [green]✓[/green] {prov}: "
                f"[bold]{resp.match_count}[/bold] matches  "
                f"([green]{len(resp.social_matches)} social[/green]  "
                f"[cyan]{len(resp.web_profile_matches)} profiles[/cyan])"
            )
            individual_responses.append(resp)

    if not individual_responses:
        console.print(Panel("[bold red]All providers failed — cannot continue.[/bold red]", border_style="red"))
        return

    # Merge if multiple providers ran
    if len(individual_responses) > 1:
        search_resp = merge_responses(individual_responses, primary_provider=provider_label)
        console.print(
            f"   [bold]Merged total:[/bold] [bold]{search_resp.match_count}[/bold] unique matches  "
            f"([green]{len(search_resp.social_matches)} social[/green]  "
            f"[cyan]{len(search_resp.web_profile_matches)} profiles[/cyan]  "
            f"[yellow]{len(search_resp.social_mention_matches)} mentions[/yellow])"
        )
    else:
        search_resp = individual_responses[0]

    console.print(f"\n   Raw Matches       : [bold]{search_resp.match_count}[/bold]")
    console.print(f"   Social Platforms  : [bold green]{len(search_resp.social_matches)}[/bold green]"
                  f"  (direct hits on LinkedIn, Instagram, GitHub, etc.)")
    console.print(f"   Web Profiles      : [bold cyan]{len(search_resp.web_profile_matches)}[/bold cyan]"
                  f"  (profile pages on uni sites, IMDb, etc.)")
    console.print(f"   Social Mentions   : [bold yellow]{len(search_resp.social_mention_matches)}[/bold yellow]"
                  f"  (news/blog articles mentioning a social platform)")

    # -------------------------------------------------------------------------
    # STEP 2b: Name-based Social Profile Lookup  [Option B]
    # Instagram/Facebook/X block image crawlers — find profiles by name instead
    # -------------------------------------------------------------------------
    detected_name: str | None = person_name
    if social_lookup:
        console.print(f"\n[bold yellow]STEP 2b: Social Profile Lookup (Instagram / Facebook / X / LinkedIn)[/bold yellow]")

        # Name priority: --person-name flag > Gemini vision > title extraction
        forced_name = person_name or gemini_name
        if forced_name:
            source = "--person-name flag" if person_name else "Gemini Vision"
            console.print(f"   Name source     : [bold cyan]{forced_name}[/bold cyan]  [dim](from {source})[/dim]")
        else:
            console.print("   Extracting person name from match titles...")

        all_titles = [m.title for m in search_resp.matches if m.title]
        detected_name, profile_matches = find_social_profiles(
            match_titles=all_titles,
            person_name=forced_name,
        )

        # Also run Gemini's generated queries directly as Google searches
        if gemini_queries and detected_name:
            from reverse_search.social_profile_finder import _google_search
            import os as _os
            _api_key = _os.getenv("SERPAPI_API_KEY", "")
            if _api_key:
                console.print(f"   Running [bold]{len(gemini_queries)}[/bold] Gemini-generated queries...")
                seen_urls = {m.url for m in profile_matches}
                for query in gemini_queries:
                    results = _google_search(query, _api_key, num=5)
                    from reverse_search.base import SearchMatch
                    for item in results:
                        url = item.get("link", "")
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            profile_matches.append(SearchMatch(
                                url=url,
                                title=item.get("title", ""),
                                snippet=item.get("snippet", ""),
                                thumbnail=item.get("thumbnail", ""),
                                match_type="profile_search",
                            ))

        if detected_name:
            console.print(f"   Detected name   : [bold cyan]{detected_name}[/bold cyan]")
            console.print(f"   Profile hits    : [bold green]{len(profile_matches)}[/bold green]"
                          f"  (Instagram, Facebook, X, LinkedIn, YouTube, TikTok)")

            if profile_matches:
                # Deduplicate against existing results and append
                existing_urls = {m.url for m in search_resp.matches}
                new_profiles = [m for m in profile_matches if m.url not in existing_urls]
                search_resp.matches = search_resp.matches + new_profiles

                # Show what we found
                tbl = Table(box=box.SIMPLE, show_header=True, title="🔎 Social Profiles Found via Name Search")
                tbl.add_column("Platform", style="bold green", width=14)
                tbl.add_column("Title", width=45, overflow="fold")
                tbl.add_column("URL", width=70, overflow="fold")
                for m in new_profiles:
                    tbl.add_row(m.platform or "—", m.title[:45] if m.title else "—", m.url[:70])
                console.print(tbl)
            else:
                console.print("   [dim]No additional profile URLs found.[/dim]")
        else:
            console.print(
                "   [yellow]Could not detect a person name from match titles.[/yellow]\n"
                "   [dim]Tip: pass --person-name \"Full Name\" to force lookup.[/dim]"
            )

    # -------------------------------------------------------------------------
    # STEP 3: Biometric Verification Filtering
    # -------------------------------------------------------------------------
    if verify_biometrics and search_resp.match_count > 0:
        console.print(f"\n[bold yellow]STEP 3: Biometric Verification Filter (Lookalike Rejection)[/bold yellow]")
        console.print("   Downloading candidate thumbnails & computing cosine similarity...")
        verifier = BiometricVerifier(face_pipeline=pipeline)
        with console.status("[bold green]Verifying candidates against 128D embedding..."):
            search_resp = verifier.verify_response(search_resp, emb)

    # -------------------------------------------------------------------------
    # STEP 4: Results Tables
    # -------------------------------------------------------------------------
    console.print(f"\n[bold yellow]STEP 4: Biometric Decision Report (Threshold ≥ 0.363)[/bold yellow]")

    verified_matches = [m for m in search_resp.matches if m.biometrically_verified]
    discarded = [m for m in search_resp.matches if not m.biometrically_verified]

    # --- Verified Matches Table ---
    table_verified = Table(
        box=box.HEAVY_EDGE,
        show_lines=True,
        title=f"✅  Verified Identity Matches — [bold green]{len(verified_matches)} Found[/bold green]",
        title_style="bold green",
    )
    table_verified.add_column("#", width=3, justify="right", style="dim")
    table_verified.add_column("Score", width=12, justify="center")
    table_verified.add_column("Category", width=16, justify="center")
    table_verified.add_column("Platform", style="bold green", width=16)
    table_verified.add_column("Domain", width=22)
    table_verified.add_column("Title", width=35, overflow="fold")
    table_verified.add_column("URL", width=55, overflow="fold")

    if verified_matches:
        for i, m in enumerate(verified_matches, 1):
            sim_pct = (m.biometric_similarity or 0) * 100
            cat = m.category
            cat_text = {
                "social":          "[bold green]Social[/bold green]",
                "web_profile":     "[bold cyan]Web Profile[/bold cyan]",
                "social_mention":  "[bold yellow]Mention[/bold yellow]",
            }.get(cat, "[dim]Web[/dim]")
            table_verified.add_row(
                str(i),
                f"[bold green]{sim_pct:.1f}%[/bold green]",
                cat_text,
                m.platform or "—",
                m.domain,
                m.title[:35] if m.title else "—",
                m.url[:80],
            )
        console.print(table_verified)
    else:
        console.print(Panel(
            "[yellow]No candidate met the biometric threshold (≥ 0.363).\n\n"
            "Tips:\n"
            "• Use a clearer, front-facing photo\n"
            "• Try --multi-provider to combine Google Lens + Yandex\n"
            "• Pass --person-name \"Full Name\" to force the social profile lookup\n"
            "• The subject may have very limited public web presence[/yellow]",
            title="⚠️  No Verified Matches",
            border_style="yellow",
        ))

    # --- All Candidates Table (top 30) ---
    console.print()
    table_all = Table(
        box=box.ROUNDED,
        show_lines=True,
        title=f"🔍 All Candidates (top 30 of {search_resp.match_count})",
    )
    table_all.add_column("#", width=3, justify="right")
    table_all.add_column("Status", width=14, justify="center")
    table_all.add_column("Similarity", width=11, justify="right")
    table_all.add_column("Category", width=15, justify="center")
    table_all.add_column("Platform", style="bold", width=14)
    table_all.add_column("Domain", width=20)
    table_all.add_column("Title", width=40, overflow="fold")
    table_all.add_column("URL", width=60, overflow="fold")

    for i, m in enumerate(search_resp.matches[:30], 1):
        if m.biometrically_verified:
            status_text = "[bold green]✅ VERIFIED[/bold green]"
            sim_text = f"[bold green]{(m.biometric_similarity or 0)*100:.1f}%[/bold green]"
            row_style = "green"
        elif m.verification_status == "lookalike":
            status_text = "[dim red]❌ Lookalike[/dim red]"
            sim_text = f"[dim red]{(m.biometric_similarity or 0)*100:.1f}%[/dim red]"
            row_style = "dim"
        elif m.verification_status == "no_face_detected":
            status_text = "[dim]No face[/dim]"
            sim_text = "—"
            row_style = ""
        else:
            status_text = f"[dim]{m.verification_status}[/dim]"
            sim_text = "—"
            row_style = ""

        cat_text = {
            "social":          "[bold green]Social[/bold green]",
            "web_profile":     "[bold cyan]Web Profile[/bold cyan]",
            "social_mention":  "[bold yellow]Mention[/bold yellow]",
        }.get(m.category, "[dim]Web[/dim]")

        table_all.add_row(
            str(i), status_text, sim_text, cat_text,
            m.platform or "—", m.domain,
            m.title[:40] if m.title else "—",
            m.url[:60],
            style=row_style,
        )

    console.print(table_all)

    # --- Discarded summary ---
    if discarded:
        console.print()
        discard_lines = [
            f"[bold red]Total Discarded:[/bold red] {len(discarded)} candidates failed biometric threshold",
            "[dim]Excluded from blockchain payload.[/dim]",
            "",
            "[bold]Sample:[/bold]",
        ]
        for m in discarded[:4]:
            score_str = (
                f"{(m.biometric_similarity or 0)*100:.1f}%"
                if m.biometric_similarity is not None else m.verification_status
            )
            discard_lines.append(f"  ❌ [{score_str}] {m.domain} — {m.url[:65]}")
        console.print(Panel("\n".join(discard_lines),
                            title=f"❌ Discarded ({len(discarded)} Purged)",
                            border_style="red", padding=(0, 2)))

    # -------------------------------------------------------------------------
    # STEP 5: Tamper-Evident Blockchain Record Payload
    # -------------------------------------------------------------------------
    console.print(f"\n[bold yellow]STEP 5: Tamper-Evident Blockchain Record Payload[/bold yellow]")

    record_payload = {
        "schema": "HH_GOA_TASK3_RECORD_V1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "face_biometric_hash_sha256": emb_hash,
        "input_image_name": Path(image_path).name,
        "search_providers": providers_to_run,
        "detected_person_name": detected_name,
        "gemini_analysis": gemini_analysis.to_dict() if gemini_analysis and gemini_analysis.succeeded else None,
        "detector_confidence": round(primary_face.confidence, 4),
        "verified_matches_count": len(verified_matches),
        "verified_matches": [
            {
                "url": m.url,
                "platform": m.platform,
                "domain": m.domain,
                "category": m.category,
                "title": m.title,
                "biometric_similarity": m.biometric_similarity,
            }
            for m in verified_matches
        ],
        "top_social_platforms": [
            {"platform": m.platform, "category": m.category, "url": m.url, "domain": m.domain}
            for m in search_resp.social_matches[:5]
        ],
        "top_web_profiles": [
            {"platform": m.platform, "category": m.category, "url": m.url, "domain": m.domain}
            for m in search_resp.web_profile_matches[:5]
        ],
        "lookalikes_purged_count": len(discarded),
        "match_breakdown": {
            "total": search_resp.match_count,
            "social_platforms": len(search_resp.social_matches),
            "web_profiles": len(search_resp.web_profile_matches),
            "social_mentions": len(search_resp.social_mention_matches),
        },
    }

    record_json_str = json.dumps(record_payload, sort_keys=True)
    record_hash = hashlib.sha256(record_json_str.encode()).hexdigest()

    name_line = f"\n[bold]Detected Person:[/bold] [bold cyan]{detected_name}[/bold cyan]" if detected_name else ""
    gemini_line = ""
    if gemini_analysis and gemini_analysis.succeeded:
        if gemini_analysis.identified_person:
            gemini_line = f"\n[bold]Gemini ID:[/bold] [green]{gemini_analysis.identified_person}[/green]  [dim]({gemini_analysis.identification_confidence} confidence)[/dim]"
        elif gemini_analysis.visible_text:
            gemini_line = f"\n[bold]Gemini text:[/bold] [dim]{', '.join(gemini_analysis.visible_text[:4])}[/dim]"
    blockchain_summary = (
        f"[bold]Record Payload Hash (SHA-256):[/bold] [bold bright_green]{record_hash}[/bold bright_green]\n"
        f"[bold]Face Embedding Hash (SHA-256):[/bold] {emb_hash}"
        f"{name_line}"
        f"{gemini_line}\n"
        f"[bold]Search Provider(s):[/bold] {provider_label}\n"
        f"[bold]Verified Identity Matches:[/bold] {len(verified_matches)}\n"
        f"[bold]Match Breakdown:[/bold]  "
        f"[green]{len(search_resp.social_matches)} Social[/green]  |  "
        f"[cyan]{len(search_resp.web_profile_matches)} Web Profiles[/cyan]  |  "
        f"[yellow]{len(search_resp.social_mention_matches)} Mentions[/yellow]\n"
        f"[bold]Lookalikes Excluded:[/bold] {len(discarded)}\n"
        f"[bold]Status:[/bold] [bold green]✅ Ready for Blockchain Write[/bold green]"
    )
    console.print(Panel(blockchain_summary, title="⛓️  Tamper-Evident Blockchain Payload", border_style="green"))

    # Save full audit trail
    out_file = save_json or f"results/pipeline_run_{int(datetime.now().timestamp())}.json"
    Path(out_file).parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump({
            "record_hash_sha256": record_hash,
            "record_payload": record_payload,
            "face_result": face_result.to_dict(),
            "search_response": search_resp.to_dict(),
        }, f, indent=2, default=str)

    console.print(f"\n💾 Full audit trail saved to: [bold]{out_file}[/bold]\n")


def main():
    parser = argparse.ArgumentParser(
        description="HH Goa 2026 Task #3 — Face ID + Blockchain Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single provider
  python run_pipeline.py --image samples/Anuj.jpg --provider serpapi

  # Option A: merge Google Lens + Yandex
  python run_pipeline.py --image samples/shruti2.jpeg --multi-provider

  # Option B: force name for social lookup
  python run_pipeline.py --image samples/shruti2.jpeg --multi-provider --person-name "Shruti Haasan"

  # Skip social lookup
  python run_pipeline.py --image samples/Anuj.jpg --no-social-lookup
        """,
    )
    parser.add_argument("--image", "-i", required=True, help="Path to input photo")
    parser.add_argument(
        "--provider", "-p", default="serpapi", choices=list(PROVIDERS.keys()),
        help="Single provider (default: serpapi). Ignored when --multi-provider is set.",
    )
    parser.add_argument(
        "--multi-provider", action="store_true",
        help=f"Option A: run {' + '.join(MULTI_PROVIDER_DEFAULT)} and merge results",
    )
    parser.add_argument(
        "--providers", nargs="+", choices=list(PROVIDERS.keys()),
        metavar="PROVIDER",
        help="Custom list of providers for multi-provider mode e.g. --providers serpapi yandex facecheck",
    )
    parser.add_argument(
        "--face-index", "-f", type=int, default=None,
        help="Target face index in multi-face images",
    )
    parser.add_argument(
        "--no-verify", action="store_true",
        help="Skip biometric candidate verification step",
    )
    parser.add_argument(
        "--no-gemini", action="store_true",
        help="Skip Gemini Vision analysis (Step 1.5)",
    )
    parser.add_argument(
        "--no-social-lookup", action="store_true",
        help="Skip Option B name-based social profile lookup",
    )
    parser.add_argument(
        "--person-name", type=str, default=None,
        metavar="NAME",
        help='Option B: manually specify person name e.g. --person-name "Shruti Haasan"',
    )
    parser.add_argument(
        "--save-json", "-o", default=None,
        help="Output JSON audit file path",
    )

    args = parser.parse_args()

    run_pipeline(
        image_path=args.image,
        provider=args.provider,
        multi_provider=args.multi_provider,
        multi_providers=args.providers,
        face_index=args.face_index,
        verify_biometrics=not args.no_verify,
        use_gemini=not args.no_gemini,
        social_lookup=not args.no_social_lookup,
        person_name=args.person_name,
        save_json=args.save_json,
    )


if __name__ == "__main__":
    main()
