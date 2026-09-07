# HH Goa 2026 — Task #3 Build Plan
## Face ID + Blockchain Verification

Source: [hhgoa.com](https://hhgoa.com/) task list + [Task 3 doc](https://docs.google.com/document/d/1i6VkPPa7bvNAp590icepw_T0nRq3awqiFE5yChgjry4/edit?tab=t.0)

---

## 1. What You're Actually Building

Not a website. Not an app. A **pipeline** that runs end to end and gets judged by watching it run.

**The four hard requirements:**

1. Detect and encode a face from an input photo (any library or API allowed)
2. Run a genuine reverse-image search and find at least one **real** matching social media post — no hardcoded or faked results
3. Write that match's data to a blockchain as a tamper-evident, verifiable record
4. Submit:
   - GitHub repo with: working code, how to run it, which blockchain you used, and known limitations
   - One **unedited** screen recording of the full pipeline running start to finish

No hosting, no UI needed. Judging is on the pipeline itself.

---

## 2. Honest Risk Assessment — Read This Before You Start

Don't spend equal time on all four parts. They are not equally hard.

| Step | Real difficulty | Why |
|---|---|---|
| Face detection/encoding | Low | Solved problem, mature libraries, hours of work |
| Reverse image search | **High — this is the actual bottleneck** | No clean free API exists for arbitrary face search |
| Blockchain write | Medium (but easy to over-engineer) | Simple if you don't try to be clever |
| Recording + packaging | Low, but budget real time for it | It's "unedited" — you need a clean take |

**Do the reverse image search first. Before writing any other code.** If you can't get a real match back from a real API, the rest of the project doesn't matter. Most teams will burn day 1 on face detection because it's satisfying and easy, then discover on day 2 that the search step doesn't work. Don't be that team.

---

## 3. Phase 1 — Derisk the Reverse Image Search (Do This First)

### Options, ranked by usability for a hackathon:

- **Bing Visual Search API (Microsoft Azure)**
  - Has an actual, documented API — usable in a pipeline
  - Free tier available for testing
  - Best default choice
- **Google Cloud Vision API (Web Detection feature)**
  - Has a real API, returns "pages with matching images" and "visually similar images"
  - Second choice — test both, pick whichever returns better face matches
- **PimEyes / FaceCheck.id**
  - Built specifically for face search, more accurate
  - Paid, and using these on real people raises consent/ethics questions — flag this as a limitation in your README if you use it, and avoid using anyone's face without permission
- **Google Lens scraping**
  - No official API, fragile, breaks under load, against ToS
  - Avoid — don't build your core pipeline on something that can break during judging

### What to do:
1. Pick ONE primary API (Bing Visual Search recommended)
2. Get API keys today
3. Test with 2–3 real photos (use your own team's photos — consent is trivial then)
4. Confirm the API returns an actual matching post/page, not just "visually similar stock photos"
5. If it fails to find real matches reliably, this is a blocker — solve it before moving to Phase 2

**Do not proceed to Phase 2 until this works.**

---

## 4. Phase 2 — Face Detection + Encoding

### Library options:
- **`face_recognition`** (Python, built on dlib) — simplest, well documented, good for a hackathon
- **DeepFace** — more modern, supports multiple backend models, slightly more setup
- **AWS Rekognition / Azure Face API** — cloud option if you want fewer local dependencies

### What to build:
- Input: a photo
- Output: a face embedding/encoding (a vector representing the face)
- Basic checks: handle no-face-detected, multiple-faces-in-photo cases

This part is genuinely easy. Don't over-invest time here — get it working and move on.

---

## 5. Phase 3 — Wire Face Pipeline to Search

- Take the encoded face / original photo (whichever your chosen search API needs as input)
- Query your reverse image search API
- Parse the response:
  - Extract matching URL(s)
  - Extract whatever metadata is available: platform, post date, image source
- Handle the "no match found" case gracefully — this will happen sometimes, and it's fine, just don't let it crash the pipeline

---

## 6. Phase 4 — Blockchain Write (Keep This Simple)

**Important: the requirement is "tamper-evident record," not "novel smart contract architecture."** Don't build a custom Solidity contract system unless someone on your team has done this before. It's a time sink for no extra judging credit.

### Recommended approach:
1. Pick a **testnet** — do not use mainnet (costs real money, unnecessary risk)
   - Polygon Amoy testnet, or
   - A local chain via Hardhat/Ganache (simplest, fully offline, no faucet delays)
2. Hash the match data: image URL + metadata + timestamp → single hash (SHA-256 is fine)
3. Write that hash to the chain — either:
   - A minimal smart contract with a `storeRecord(hash)` function, or
   - Just a transaction with the hash embedded in the data field (even simpler, still tamper-evident)
4. Get the transaction ID / hash back
5. Confirm you can retrieve and verify it — show this working in your recording

### What to avoid:
- Building a custom token or NFT system (not required, wastes time)
- Mainnet transactions (costs money, no benefit for judging)
- Overcomplicating "verification" — a retrievable, timestamped, hashed record on a public/testnet chain satisfies "tamper-evident"

---

## 7. Phase 5 — Package for Judging

### GitHub repo must include:
- Working code (obviously)
- README with:
  - Setup instructions (someone should be able to clone and run it)
  - Which blockchain/testnet you used and why
  - **Known limitations — be explicit and honest.** Judges trust a team more when it says "reverse search only works reliably on clear, front-facing photos" than a team that pretends it's flawless.

### Screen recording:
- One take, unedited, full pipeline running start to finish
- Budget time for at least one recording where something fails on camera — that's normal for a raw recording, don't panic and re-record five times looking for a "perfect" run
- Show the full loop: input photo → face detection → search result → blockchain write → retrieval/verification

---

## 8. Suggested Time Allocation (assuming ~1–2 day build window)

- **20%** — Phase 1 (derisking search API) — do not skip or shortcut this
- **15%** — Phase 2 (face detection)
- **20%** — Phase 3 (wiring search)
- **25%** — Phase 4 (blockchain)
- **20%** — Phase 5 (README, limitations, clean recording, buffer for re-runs)

---

## 9. Open Question You Need to Answer Now

Does anyone on your team have prior exposure to Solidity, Web3.js, or smart contracts?

- **If yes** — Phase 4 is low-risk, proceed as planned.
- **If no** — this is where you'll lose the most time. Consider the simplest possible blockchain interaction (writing a hash to a testnet transaction, no custom contract) rather than anything more ambitious. Decide this now, not on day 2 when you're already behind.
