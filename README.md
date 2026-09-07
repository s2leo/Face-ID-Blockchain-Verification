# Face-ID-Blockchain-Verification

**HH Goa 2026 — Task #3**

Complete pipeline that detects faces, extracts biometric embeddings, performs multi-provider reverse image search with AI-powered vision analysis, verifies candidates biometrically, and records verified matches in a tamper-evident blockchain ledger.

## 🌟 Features

- **Biometric Face Detection**: YuNet + SFace for 128D face embeddings
- **AI Vision Analysis**: Gemini Vision extracts names from badges/text (critical for non-famous people)
- **Multi-Provider Search**: SerpAPI, Yandex, Google Vision, Bing, FaceCheck.id
- **Smart Social Lookup**: Finds Instagram/Facebook/LinkedIn profiles by name (bypasses CDN blocking)
- **Biometric Verification**: Filters false positives with cosine similarity matching
- **Blockchain Recording**: Local JSON chain (default) or Polygon Amoy testnet (optional)

## 📋 Prerequisites

- **Python 3.10+** (tested on 3.10)
- **Virtual environment** recommended
- **API Keys** (see Configuration below)

## 🚀 Quick Start

### 1. Setup Environment

**Linux/macOS:**
```bash
cd ~/Blockchain
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

**Windows (PowerShell):**
```powershell
cd C:\Blockchain
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

### 2. Configure API Keys

Edit `.env` and add your API keys:

```bash
# Required - Gemini Vision (FREE, 1000/day)
# Get from: https://aistudio.google.com
GEMINI_API_KEY=your_gemini_key_here

# Required - Reverse Search (Paid, $50/mo for 5000 searches)
# Get from: https://serpapi.com
SERPAPI_API_KEY=your_serpapi_key_here

# Optional - Additional providers
YANDEX_API_KEY=your_yandex_key_here
GOOGLE_CLOUD_API_KEY=your_google_key_here
FACECHECK_API_KEY=your_facecheck_key_here

# Optional - Polygon Amoy blockchain (default: local chain)
WALLET_ADDRESS=0x...
WALLET_PRIVATE_KEY=0x...
AMOY_RPC_URL=https://polygon-amoy.drpc.org
```

### 3. Run the Pipeline

**Basic usage:**
```bash
python run_pipeline.py --image samples/Anuj.jpg --provider serpapi
```

**Multi-provider (best results):**
```bash
python run_pipeline.py --image samples/shruti.png --multi-provider
```

**With person name (improves accuracy):**
```bash
python run_pipeline.py --image samples/shruti.png --provider serpapi --person-name "Shruti Haasan"
```

## 📖 Pipeline Steps

The complete pipeline executes these steps:

```
STEP 1:   Biometric Face Detection & 128D Embedding
          ├─ YuNet face detector (5-point landmarks)
          ├─ SFace 128D biometric embedding
          └─ SHA-256 hash of embedding (blockchain-ready)

STEP 1.5: Gemini Vision Analysis (NEW)
          ├─ Extract visible text (badges, nametags, logos)
          ├─ Identify public figures
          ├─ Generate targeted search queries
          └─ Context clues extraction

STEP 2:   Reverse Image Search
          ├─ Query selected provider(s)
          ├─ Classify results (social/web_profile/mention/web)
          └─ Platform detection (90+ social networks)

STEP 2b:  Social Profile Lookup (Option B)
          ├─ Extract person name from search results
          ├─ Search "Name" site:instagram.com
          ├─ Search "Name" site:facebook.com
          └─ 12 platforms: Instagram, Facebook, X, LinkedIn, etc.

STEP 3:   Biometric Verification
          ├─ Download candidate profile photos
          ├─ Extract face embeddings from each
          ├─ Compute cosine similarity vs. query face
          └─ Filter results above threshold (0.363)

STEP 6:   Blockchain Write (only if verified matches exist)
          ├─ Local mode: Write to chain.json
          └─ Polygon mode: Upload to Amoy testnet
```

**Note:** STEP 6 only runs when STEP 3 produces verified matches. Use `--no-verify` skips verification and blockchain write.

## 💻 Command Reference

### Basic Commands

```bash
# Single provider (default: serpapi)
python run_pipeline.py --image samples/Anuj.jpg

# Specific provider
python run_pipeline.py --image samples/Anuj.jpg --provider yandex

# Multi-provider merge (best coverage)
python run_pipeline.py --image samples/Anuj.jpg --multi-provider

# Custom provider combination (space-separated)
python run_pipeline.py --image samples/Anuj.jpg --multi-provider --providers serpapi yandex
```

### Pipeline Options

```bash
# Provide person name (skip name extraction)
python run_pipeline.py --image test.jpg --person-name "John Doe"

# Skip biometric verification (faster, no blockchain)
python run_pipeline.py --image test.jpg --no-verify

# Skip Gemini Vision analysis
python run_pipeline.py --image test.jpg --no-gemini

# Skip social profile lookup (Option B)
python run_pipeline.py --image test.jpg --no-social-lookup

# Select specific face from group photo (0-indexed)
python run_pipeline.py --image group.jpg --face-index 2

# Limit verification candidates (default: 25)
python run_pipeline.py --image test.jpg --max-verify-candidates 10
```

### Blockchain Options

```bash
# Local blockchain (default, writes to chain.json)
python run_pipeline.py --image test.jpg --blockchain-mode local

# Polygon Amoy testnet (requires wallet in .env)
python run_pipeline.py --image test.jpg --blockchain-mode polygon

# Custom chain file location
python run_pipeline.py --image test.jpg --chain-file my_chain.json

# Disable blockchain (testing only)
python run_pipeline.py --image test.jpg --no-blockchain
```

### Output Options

```bash
# Save results to JSON
python run_pipeline.py --image test.jpg --save-json results/output.json

# View blockchain ledger
python run_pipeline.py --show-chain

# View custom chain file
python run_pipeline.py --show-chain --chain-file my_chain.json

# Verify specific record
python run_pipeline.py --verify-only --record-json results/pipeline_run_12345.json
```

## 🔍 Verify Blockchain Implementation

### Test Local Blockchain
```bash
python -c "
from blockchain.local_chain import LocalChain
chain = LocalChain('test_chain.json')
block = chain.add_block({'test': 'record', 'hash': 'abc123'})
print(f'✅ Blockchain working: {len(chain.blocks)} blocks, valid={chain.validate_chain()}')
"
```

### View Chain Contents
```bash
# View main chain
cat chain.json | python -m json.tool

# Check chain validity
python run_pipeline.py --show-chain
```

### Full Integration Test
```bash
# Run pipeline and verify blockchain write
python run_pipeline.py --image samples/shruti.png --provider serpapi --person-name "Shruti Haasan"

# Check for STEP 6 in output
# Verify chain.json was created
ls -la chain.json
```

## 📂 Project Structure

```
~/Blockchain/
├── face_pipeline/
│   └── pipeline.py              # YuNet + SFace face detection
├── reverse_search/
│   ├── base.py                  # Data structures, platform detection
│   ├── serpapi_lens.py          # SerpAPI Google Lens
│   ├── yandex_visual.py         # Yandex reverse search
│   ├── google_vision.py         # Google Cloud Vision API
│   ├── bing_visual.py           # Bing Visual Search
│   ├── facecheck_id.py          # FaceCheck.id (face-specific)
│   ├── gemini_vision.py         # Gemini Vision Analyzer (AI text extraction)
│   ├── social_profile_finder.py # Name-based social profile search
│   └── biometric_verifier.py    # Biometric similarity verification
├── blockchain/
│   ├── local_chain.py           # Local JSON blockchain
│   ├── uploader.py              # Polygon Amoy uploader
│   ├── config.py                # Blockchain configuration
│   ├── record_builder.py        # Record hashing utilities
│   └── verify.py                # Verification utilities
├── samples/                      # Test images
├── results/                      # JSON output files
├── run_pipeline.py              # Main entry point
├── requirements.txt             # Python dependencies
├── .env                         # API keys (create from .env.example)
└── chain.json                   # Local blockchain ledger (created on first run)
```

## 🎯 Use Cases

### Famous Person (High Success Rate)
```bash
python run_pipeline.py --image celebrity.jpg --multi-provider --person-name "Celebrity Name"
```
**Expected:** High match count, multiple verified social profiles, blockchain record created

### Professional (LinkedIn Presence)
```bash
python run_pipeline.py --image professional.jpg --provider serpapi
```
**Expected:** LinkedIn/GitHub profiles found, moderate match count

### Non-Famous Individual (Badge/Event Photo)
```bash
python run_pipeline.py --image conference_badge.jpg --provider serpapi
```
**Expected:** Gemini extracts name from badge, searches by name, finds social profiles

### Private Individual (No Online Presence)
```bash
python run_pipeline.py --image private_person.jpg --provider serpapi
```
**Expected:** Few or no matches, no verified results, no blockchain write

## 🔧 Troubleshooting

### "No module named 'eth_account'"
```bash
pip install eth-account web3
```

### "Gemini API timeout"
- Switched to `gemini-flash-lite-latest` (fast, 2-3s response)
- Old thinking models (`gemini-3.6-flash`) timeout after 30s

### "STEP 6 not showing"
- STEP 6 only runs with **verified matches**
- Don't use `--no-verify` if you want blockchain write
- Ensure reverse search finds results (use famous person for testing)

### "ModuleNotFoundError: No module named 'cv2'"
```bash
pip install opencv-contrib-python
```

### "numpy version mismatch"
```bash
# For Python 3.10, use numpy 1.x
pip install "numpy>=1.24.0,<2.0.0"
```

## 🌐 Blockchain Modes

### Local Blockchain (Default)
- **Storage:** `chain.json` file
- **Cost:** Free
- **Speed:** Instant
- **Tamper-evident:** Yes (SHA-256 chain)
- **Public verification:** No (local file only)
- **Setup:** None required

### Polygon Amoy (Optional)
- **Storage:** Polygon Amoy testnet
- **Cost:** Free testnet MATIC from faucet
- **Speed:** 5-10 seconds per transaction
- **Tamper-evident:** Yes (public blockchain)
- **Public verification:** Yes (PolygonScan)
- **Setup:** Requires wallet address + private key in `.env`

**Get testnet MATIC:** https://faucet.polygon.technology/

## 📊 Output Files

### JSON Result Files
Located in `results/pipeline_run_<timestamp>.json`:
```json
{
  "image_path": "samples/Anuj.jpg",
  "face_embedding_hash": "ec03fd78...",
  "verified_matches_count": 5,
  "verified_matches": [...],
  "blockchain_mode": "local",
  "blockchain_block_index": 3,
  "blockchain_block_hash": "c6ab6974...",
  "blockchain_chain_file": "chain.json"
}
```

### Blockchain Chain File
Located at `chain.json`:
```json
{
  "schema": "LOCAL_FACE_ID_CHAIN_V1",
  "blocks": [
    {
      "index": 0,
      "timestamp": "2026-01-01T00:00:00+00:00",
      "data": {"type": "genesis"},
      "previous_hash": "0",
      "hash": "20475c84..."
    },
    {
      "index": 1,
      "timestamp": "2026-09-07T15:07:18+00:00",
      "data": {
        "record_hash": "abc123...",
        "record": {...}
      },
      "previous_hash": "20475c84...",
      "hash": "c6ab6974..."
    }
  ]
}
```

## ⚠️ Known Limitations

- **Local blockchain:** Not a decentralized public chain (use `--blockchain-mode polygon` for public ledger)
- **Polygon mode:** Requires testnet MATIC and funded wallet
- **Reverse search:** Providers may rate-limit or return no matches
- **Privacy:** Transaction stores hashes only, not face images or biometric vectors
- **Instagram/Facebook:** CDN blocking requires name-based search workaround (Option B)
- **Non-famous people:** Requires visible text (badges, nametags) or existing web mentions

## 🎓 API Rate Limits

| Service | Free Tier | Paid Tier | Notes |
|---------|-----------|-----------|-------|
| Gemini Vision | 1000/day | N/A | FREE forever, no credit card |
| SerpAPI | 100/mo | $50/mo (5000) | Required for Google Lens |
| Yandex | Unlimited | N/A | Screen scraping (no official API) |
| FaceCheck.id | N/A | Paid only | Face-specific search |

## 📚 Documentation

- **Project Summary:** `PROJECT_SUMMARY.md` (comprehensive technical doc)
- **API Configuration:** `.env.example` (template for API keys)
- **Chain Verification:** `python run_pipeline.py --show-chain`

## 🤝 Contributing

**Developer:** Anuj  
**Project:** HH Goa 2026 Task #3  
**Location:** `/home/anuj/Blockchain/`

## 📄 License

MIT License (see LICENSE file)

---

**Last Updated:** September 2026  
**Version:** 1.0  
**Status:** Production Ready
