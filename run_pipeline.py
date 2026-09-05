#!/usr/bin/env python3
"""
HH Goa 2026 — Task #3: End-to-End Face ID + Social Verification Pipeline
========================================================================

Complete Pipeline Execution:
  1. Detect & 5-point align face from input photo
  2. Extract 128-dimensional biometric embedding vector
  3. Pre-process into high-res canonical headshot
  4. Query Reverse Image Search (Google Lens via SerpApi)
  5. Biometric Verification Filtering (Cosine similarity against candidate faces)
  6. Prepare tamper-evident cryptographic hash for blockchain recording

Usage:
    source .venv/bin/activate
    python run_pipeline.py --image samples/Anuj.jpg
    python run_pipeline.py --image samples/2.jpeg --face-index 0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Suppress internal OpenCV C++ warnings
os.environ["OPENCV_LOG_LEVEL"] = "OFF"

# Ensure local imports
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import box

from face_pipeline import FacePipeline
from reverse_search import search_image, BiometricVerifier, PROVIDERS

console = Console()


def render_banner():
    console.print()
    console.print(
        Panel(
            "[bold white]HH Goa 2026 — Task #3 Build Pipeline[/bold white]\n"
            "[cyan]Biometric Face ID + Reverse Search + Verification Filter[/cyan]",
            border_style="bright_blue",
            padding=(1, 2),
        )
    )


def run_pipeline(
    image_path: str,
    provider: str = "serpapi",
    face_index: int | None = None,
    verify_biometrics: bool = True,
    save_json: str | None = None,
):
    render_banner()

    # -------------------------------------------------------------
    # STEP 1: Biometric Face Detection & 128D Embedding (Phase 2)
    # -------------------------------------------------------------
    console.print("\n[bold yellow]STEP 1: Biometric Face Detection & 128D Embedding[/bold yellow]")
    with console.status("[bold green]Loading neural models and analyzing face..."):
        pipeline = FacePipeline()
        face_result = pipeline.process_image(image_path, face_index=face_index)

    if not face_result.has_face:
        console.print(
            Panel(
                f"[bold red]Face Detection Failed:[/bold red] {face_result.error}",
                border_style="red",
            )
        )
        return

    primary_face = face_result.primary_face
    emb = primary_face.embedding
    emb_hash = hashlib.sha256(json.dumps(emb).encode()).hexdigest()

    # Face details panel
    face_summary = (
        f"[bold]Image:[/bold] {face_result.image_path} ({face_result.image_width}x{face_result.image_height})\n"
        f"[bold]Faces Detected:[/bold] {face_result.faces_detected} (Primary selected: Face #{primary_face.index})\n"
        f"[bold]Detector Confidence:[/bold] {primary_face.confidence * 100:.1f}%\n"
        f"[bold]Bounding Box (x,y,w,h):[/bold] {primary_face.box}\n"
        f"[bold]5-Point Facial Landmarks:[/bold] {primary_face.landmarks}\n"
        f"[bold]Biometric Vector:[/bold] 128-dimensional float32 embedding\n"
        f"[bold]Embedding Preview:[/bold] [{', '.join(f'{x:.3f}' for x in emb[:5])}, ...]\n"
        f"[bold]Biometric Hash (SHA-256):[/bold] [green]{emb_hash}[/green]\n"
        f"[bold]Optimized Headshot Crop:[/bold] {primary_face.cropped_headshot_path}"
    )
    console.print(Panel(face_summary, title="👤 Biometric Profile Extracted", border_style="cyan"))

    # -------------------------------------------------------------
    # STEP 2: Reverse Image Search with Canonical Headshot (Phase 1/3)
    # -------------------------------------------------------------
    search_input = primary_face.cropped_headshot_path or image_path
    console.print(f"\n[bold yellow]STEP 2: Reverse Image Search with Aligned Headshot[/bold yellow]")
    console.print(f"   Provider    : [bold cyan]{provider}[/bold cyan]")
    console.print(f"   Query Target: [dim]{search_input}[/dim]")

    with console.status(f"[bold green]Querying {provider} reverse image search..."):
        search_resp = search_image(search_input, provider=provider)

    if search_resp.error:
        console.print(Panel(f"[bold red]Search Error:[/bold red] {search_resp.error}", border_style="red"))
        return

    console.print(f"   Raw Matches Found: [bold]{search_resp.match_count}[/bold]")
    console.print(f"   Social Media Candidates: [bold]{len(search_resp.social_matches)}[/bold]")

    # -------------------------------------------------------------
    # STEP 3: Biometric Verification Filtering
    # -------------------------------------------------------------
    if verify_biometrics and search_resp.match_count > 0:
        console.print(f"\n[bold yellow]STEP 3: Biometric Verification Filter (Lookalike Rejection)[/bold yellow]")
        console.print("   Downloading candidate avatars & computing biometric cosine similarity...")

        verifier = BiometricVerifier(face_pipeline=pipeline)
        with console.status("[bold green]Verifying candidates against authentic 128D embedding..."):
            search_resp = verifier.verify_response(search_resp, emb)

    # -------------------------------------------------------------
    # STEP 4: Render Results Table
    # STEP 4: Decision Diamond — Verified Matches vs Discarded Lookalikes
    # -------------------------------------------------------------
    console.print(f"\n[bold yellow]STEP 4: Search & Biometric Verification Report[/bold yellow]")
    console.print(f"\n[bold yellow]STEP 4: Biometric Decision Diamond (Threshold ≥ 0.363)[/bold yellow]")

    table = Table(box=box.ROUNDED, show_lines=True, title="🔍 Verified Social Matches vs Candidates")
    table.add_column("#", width=3, justify="right")
    table.add_column("Status", width=12, justify="center")
    table.add_column("Similarity", width=10, justify="right")
    table.add_column("Platform", style="bold", width=14)
    table.add_column("Domain", width=18)
    table.add_column("Title / Snippet", width=35, overflow="fold")
    table.add_column("URL", width=55, overflow="fold")
    verified_matches = [m for m in search_resp.matches if m.biometrically_verified]
    discarded_lookalikes = [m for m in search_resp.matches if not m.biometrically_verified]

    for i, m in enumerate(search_resp.matches[:25], 1):
        if m.biometrically_verified:
            status_text = "[bold green]✅ VERIFIED[/bold green]"
            sim_text = f"[bold green]{(m.biometric_similarity or 0) * 100:.1f}%[/bold green]"
            row_style = "green"
        elif m.verification_status == "lookalike":
            status_text = "[dim red]❌ Lookalike[/dim red]"
            sim_text = f"[dim red]{(m.biometric_similarity or 0) * 100:.1f}%[/dim red]"
            row_style = "dim"
        elif m.verification_status == "no_face_detected":
            status_text = "[dim]No face in thumb[/dim]"
            sim_text = "—"
            row_style = ""
        else:
            status_text = f"[dim]{m.verification_status}[/dim]"
            sim_text = "—"
            row_style = ""
    # --- Table 1: Verified Identity Matches (YES Branch) ---
    table_verified = Table(
        box=box.HEAVY_EDGE,
        show_lines=True,
        title=f"✅  Verified Identity Matches (Score ≥ 0.363) — [bold green]{len(verified_matches)} Found[/bold green]",
        title_style="bold green",
    )
    table_verified.add_column("#", width=3, justify="right", style="dim")
    table_verified.add_column("Biometric Score", width=16, justify="center")
    table_verified.add_column("Platform", style="bold green", width=14)
    table_verified.add_column("Domain", width=20)
    table_verified.add_column("Title / Snippet", width=35, overflow="fold")
    table_verified.add_column("Verified URL", width=55, overflow="fold")

        table.add_row(
            str(i),
            status_text,
            sim_text,
            m.platform or "—",
            m.domain,
            m.title[:60] if m.title else "—",
            m.url[:80],
            style=row_style,
    if verified_matches:
        for i, m in enumerate(verified_matches, 1):
            sim_pct = (m.biometric_similarity or 0) * 100
            table_verified.add_row(
                str(i),
                f"[bold green]{sim_pct:.1f}% Match[/bold green]",
                m.platform or "Web Profile",
                m.domain,
                m.title[:60] if m.title else "—",
                m.url[:85],
            )
        console.print(table_verified)
    else:
        console.print(
            Panel(
                "[yellow]No candidate met the biometric threshold (≥ 0.363).\n"
                "All returned results were discarded as lookalikes or unverified links.[/yellow]",
                title="⚠️  No Verified Matches",
                border_style="yellow",
            )
        )

    console.print(table)
    # --- Summary Box: Discarded Lookalikes (NO Branch) ---
    console.print()
    discard_lines = [
        f"[bold red]Total Discarded Lookalikes:[/bold red] {len(discarded_lookalikes)}",
        "[dim]These links failed the biometric face match and are strictly purged from the blockchain payload.[/dim]",
        "",
        "[bold]Sample Filtered-Out Candidates:[/bold]",
    ]
    for m in discarded_lookalikes[:4]:
        score_str = f"Similarity: {(m.biometric_similarity or 0)*100:.1f}%" if m.biometric_similarity is not None else m.verification_status
        discard_lines.append(f"  ❌ [{score_str}] {m.domain} — {m.url[:70]}")

    console.print(
        Panel(
            "\n".join(discard_lines),
            title=f"❌ Discarded Lookalikes ({len(discarded_lookalikes)} Purged)",
            border_style="red",
            padding=(0, 2),
        )
    )

    # -------------------------------------------------------------
    # STEP 5: Tamper-Evident Record Preparation (Phase 4 Ready)
    # -------------------------------------------------------------
    console.print(f"\n[bold yellow]STEP 5: Tamper-Evident Blockchain Record Payload[/bold yellow]")

    verified = search_resp.verified_matches
    social_candidates = search_resp.social_matches

    # Cryptographic record payload
    # Cryptographic record payload contains ONLY verified matches
    record_payload = {
        "schema": "HH_GOA_TASK3_RECORD_V1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "face_biometric_hash_sha256": emb_hash,
        "input_image_name": Path(image_path).name,
        "confidence_score": round(primary_face.confidence, 4),
        "verified_matches_count": len(verified),
        "verified_matches_count": len(verified_matches),
        "verified_matches": [
            {
                "url": m.url,
                "platform": m.platform,
                "similarity_score": m.biometric_similarity,
            }
            for m in verified
            for m in verified_matches
        ],
        "top_social_candidates": [
            {"platform": m.platform, "url": m.url, "domain": m.domain}
            for m in social_candidates[:5]
        ],
        "lookalikes_purged_count": len(discarded_lookalikes),
    }

    record_json_str = json.dumps(record_payload, sort_keys=True)
    record_hash = hashlib.sha256(record_json_str.encode()).hexdigest()

    blockchain_summary = (
        f"[bold]Record Payload Hash (SHA-256):[/bold] [bold bright_green]{record_hash}[/bold bright_green]\n"
        f"[bold]Face Embedding Hash:[/bold] {emb_hash}\n"
        f"[bold]Verified Matches:[/bold] {len(verified)}\n"
        f"[bold]Social Candidates Found:[/bold] {len(social_candidates)}\n"
        f"[bold]Ready to Write to Chain:[/bold] Polygon Amoy / Local Hardhat"
        f"[bold]Biometric Face Hash (E1):[/bold] {emb_hash}\n"
        f"[bold]Verified Identity Records Included:[/bold] {len(verified_matches)}\n"
        f"[bold]Lookalikes Excluded & Purged:[/bold] {len(discarded_lookalikes)}\n"
        f"[bold]Status:[/bold] [bold green]Ready for Smart Contract / Testnet Write[/bold green]"
    )
    console.print(Panel(blockchain_summary, title="⛓️ Blockchain Record Ready", border_style="green"))
    console.print(Panel(blockchain_summary, title="⛓️ Tamper-Evident Blockchain Payload", border_style="green"))

    # Save to disk
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
        description="HH Goa 2026 Task #3 — End-to-End Face ID Pipeline",
    )
    parser.add_argument("--image", "-i", required=True, help="Path to input photo")
    parser.add_argument("--provider", "-p", default="serpapi", choices=list(PROVIDERS.keys()))
    parser.add_argument("--face-index", "-f", type=int, default=None, help="Target face index if multi-face")
    parser.add_argument("--no-verify", action="store_true", help="Skip biometric candidate verification")
    parser.add_argument("--save-json", "-o", default=None, help="Output JSON audit file")

    args = parser.parse_args()
    run_pipeline(
        image_path=args.image,
        provider=args.provider,
        face_index=args.face_index,
        verify_biometrics=not args.no_verify,
        save_json=args.save_json,
    )


if __name__ == "__main__":
    main()

