# Face-ID-Blockchain-Verification

This project builds an end-to-end face identity verification pipeline:

- detects a face in an input photo
- extracts a biometric embedding
- searches public web and social sources for likely matches
- re-verifies candidates using face similarity
- stores the verified match hash in a tamper-evident blockchain record

It is designed for workflows where you want both biometric verification and an
audit trail for the final identity match.

## What It Uses

- Face detection and alignment with OpenCV-based models
- Reverse image and social profile search providers
- Optional Gemini Vision analysis to improve identity and query extraction
- A local tamper-evident blockchain ledger

## Setup

Create a virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy the example environment file and add your API keys:

```powershell
Copy-Item .env.example .env
```

Required values depend on which providers you use. For example, add the search
provider keys you want to run with.

## How To Run

Run the full pipeline on a sample image:

```powershell
python run_pipeline.py --image samples\Anuj.jpg --provider serpapi
```

Useful options:

```powershell
python run_pipeline.py --image samples\Anuj.jpg --multi-provider
python run_pipeline.py --image samples\Anuj.jpg --no-social-lookup
python run_pipeline.py --image samples\Anuj.jpg --no-blockchain
```

The run saves an audit JSON file under `results/` and writes a blockchain
record if blockchain output is enabled.

To inspect or verify results later:

```powershell
python run_pipeline.py --show-chain
python run_pipeline.py --verify-only --record-json results\pipeline_run_<timestamp>.json
```

## Blockchain Used

The project uses a local tamper-evident blockchain ledger. The default `local`
mode stores each verified-match hash in `chain.json`, links each block to the
previous block, and validates the chain before completing the run. It does not
require a wallet, RPC connection, or external blockchain account.

## Output Files

- `results/pipeline_run_<timestamp>.json`: full audit trail for the run
- `chain.json`: local blockchain ledger
- `samples/crops/`: generated face crops and headshots

## Notes

- Reverse-image providers may return no public match or may rate limit requests.
- The blockchain record stores the canonical match hash, not the raw face image
  or full biometric vector.
