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
import sys
from datetime import datetime, timezone
from pathlib import Path

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
    # -------------------------------------------------------------
    console.print(f"\n[bold yellow]STEP 4: Search & Biometric Verification Report[/bold yellow]")

    table = Table(box=box.ROUNDED, show_lines=True, title="🔍 Verified Social Matches vs Candidates")
    table.add_column("#", width=3, justify="right")
    table.add_column("Status", width=12, justify="center")
    table.add_column("Similarity", width=10, justify="right")
    table.add_column("Platform", style="bold", width=14)
    table.add_column("Domain", width=18)
    table.add_column("Title / Snippet", width=35, overflow="fold")
    table.add_column("URL", width=55, overflow="fold")

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

        table.add_row(
            str(i),
            status_text,
            sim_text,
            m.platform or "—",
            m.domain,
            m.title[:60] if m.title else "—",
            m.url[:80],
            style=row_style,
        )

    console.print(table)

    # -------------------------------------------------------------
    # STEP 5: Tamper-Evident Record Preparation (Phase 4 Ready)
    # -------------------------------------------------------------
    console.print(f"\n[bold yellow]STEP 5: Tamper-Evident Blockchain Record Payload[/bold yellow]")

    verified = search_resp.verified_matches
    social_candidates = search_resp.social_matches

    # Cryptographic record payload
    record_payload = {
        "schema": "HH_GOA_TASK3_RECORD_V1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "face_biometric_hash_sha256": emb_hash,
        "input_image_name": Path(image_path).name,
        "confidence_score": round(primary_face.confidence, 4),
        "verified_matches_count": len(verified),
        "verified_matches": [
            {
                "url": m.url,
                "platform": m.platform,
                "similarity_score": m.biometric_similarity,
            }
            for m in verified
        ],
        "top_social_candidates": [
            {"platform": m.platform, "url": m.url, "domain": m.domain}
            for m in social_candidates[:5]
        ],
    }

    record_json_str = json.dumps(record_payload, sort_keys=True)
    record_hash = hashlib.sha256(record_json_str.encode()).hexdigest()

    blockchain_summary = (
        f"[bold]Record Payload Hash (SHA-256):[/bold] [bold bright_green]{record_hash}[/bold bright_green]\n"
        f"[bold]Face Embedding Hash:[/bold] {emb_hash}\n"
        f"[bold]Verified Matches:[/bold] {len(verified)}\n"
        f"[bold]Social Candidates Found:[/bold] {len(social_candidates)}\n"
        f"[bold]Ready to Write to Chain:[/bold] Polygon Amoy / Local Hardhat"
    )
    console.print(Panel(blockchain_summary, title="⛓️ Blockchain Record Ready", border_style="green"))

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

