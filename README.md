# FaceChain Forensics — Image & Photo Forensics Verifier

**FaceChain Forensics** is an end-to-end digital image and photo forensics platform. It adapts the FaceChain Verifier pipeline into a production-grade investigative MVP combining **cryptographic evidence acquisition**, **metadata analysis**, **Error Level Analysis (ELA)**, **biometric face verification (YuNet + SFace)**, **versioned evidence manifests**, and **Ethereum Sepolia blockchain anchoring**.

---

## Key Forensic Features

### 1. Evidence Acquisition & Hashing
- **Format Support:** JPEG, PNG, and WebP uploads.
- **Strict Validation:** File type magic byte verification, upload size caps, and Pillow decoding check to prevent file corruption or payload masquerading.
- **Untouched Original:** Original uploaded files are preserved unmodified in immutable evidence storage (`storage/evidence/<id>/original.<ext>`).
- **Immediate SHA-256:** Cryptographic hash computed immediately on the uploaded byte stream upon arrival.
- **UTC Timestamps:** Acquisition timestamp recorded in ISO-8601 UTC.
- **Working Copies:** All forensic transformations and visual analyses operate exclusively on isolated working copies.

### 2. Metadata Analysis
- **EXIF Extraction:** Extracts camera hardware (Make, Model, Lens), capture settings (ISO, Exposure Time, F-Number, Focal Length, Flash, White Balance), and timestamps.
- **GPS Geolocation:** Parses GPS IFD tags (Latitude, Longitude, Altitude) and computes decimal degree coordinates with direct mapping links.
- **Inconsistency & Tamper Detection:**
  - Flags editing suite signatures (`Photoshop`, `Lightroom`, `GIMP`, `Canva`, `Snapseed`, `Pixelmator`).
  - Flags capture vs modification timestamp discrepancies.
- **Missing vs Suspicious Categorization:** Clearly differentiates routinely stripped tags (e.g. social media apps) from active tampering indicators.
- **Forensic Caveats:** Clear notices explaining that metadata presence/absence alone does not prove or disprove authenticity.

### 3. Image Manipulation Analysis (ELA)
- **JPEG Error Level Analysis:** Recompresses working copies at known quality (default 90%) and magnifies pixel-wise differences by 15x scale factor.
- **Statistical Compression Metrics:** Calculates mean error, maximum delta, standard deviation, and high-contrast pixel ratio.
- **Encoding Properties:** Reports progressive JPEG scan, quantization table presence, and chroma subsampling.
- **Methodological Handling for PNG & WebP:**
  - **PNG:** Clearly labels JPEG ELA as methodologically invalid for lossless formats, and performs lossless structure analysis (alpha channel transparency gradients, chunk types, bit depth).
  - **WebP:** Inspects VP8 lossy vs VP8L lossless container properties and animation frames.
- **No Fake AI Scores:** Rejects arbitrary single-number authenticity scores in favor of transparent, observable investigative metrics.

### 4. Biometric Face Analysis & Public Search
- **YuNet Face Detector:** Fast ONNX-based face detection reporting bounding boxes, confidence, and 5-point facial landmarks.
- **OpenCV SFace Recognizer:** Generates normalized 128-dimensional facial embedding vectors.
- **Normalized Face Crop:** Extracts and isolates the primary detected face crop.
- **Google Lens Reverse Search (Optional):** Queries SerpApi for public visual matches and correlates candidates using cosine similarity.
- **Third-Party Disclosure:** Explicitly informs the user when media is transmitted to external search providers.
- **Biometric Disclaimer:** Results are labeled strictly as investigative biometric aids, never definitive identity proof.

### 5. Evidence Manifest & Blockchain Ledger
- **Versioned Evidence Manifest (v1.0):** Contains evidence ID, original file SHA-256, acquisition metadata, canonical analysis findings hash, tool versions (OpenCV, Pillow, Python, models), and UTC timestamps.
- **Canonical Serialization:** Formatted using deterministic JSON serialization (`sort_keys=True, separators=(',', ':')`) and SHA-256 digested.
- **Self-Contained Integrity:** Manifest does *not* contain its own digest or mutable blockchain transaction IDs.
- **Ethereum Sepolia Anchoring (Optional):** Anchors the manifest SHA-256 digest in transaction input data (`FACECHAIN:v1:<hash>`).
- **Strict Receipt Verification:** Transactions are never marked confirmed without polling and verifying receipt status (`status == 1`).
- **Privacy Guarantee:** No image binaries, biometric facial embeddings, GPS coordinates, or PII are ever stored on-chain.

### 6. Official Forensic Evidence Report
- Single-click downloadable JSON report containing complete findings, tool versions, hashes, limitations, and verification stamps.

---

## Technology Stack

- **Backend:** Python 3.10+, FastAPI, Uvicorn, Pillow, OpenCV (`cv2.FaceDetectorYN`, `cv2.FaceRecognizerSF`), Web3.py.
- **Database:** SQLite (`data/forensics.db`).
- **Frontend:** React 19, Vite, TypeScript, Vanilla CSS design system, Lucide icons.
- **Testing:** pytest (backend, 23 tests), Vitest (frontend, 6 tests).

---

## Quick Start & Local Setup

### 1. Prerequisites
- Python 3.10+ (with virtual environment)
- Node.js 18+ and npm

### 2. Backend Setup
```bash
# Clone the repository
git clone https://github.com/codewithMohak/facechain-verifier.git
cd facechain-verifier

# Activate Python virtual environment
# Windows:
.\.venv\Scripts\Activate.ps1
# Linux/macOS:
# source .venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` to configure your settings:
```text
# Blockchain Anchoring (Optional - defaults to false)
BLOCKCHAIN_ANCHOR_ENABLED=false
SEPOLIA_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/YOUR_ALCHEMY_KEY
PRIVATE_KEY=your_wallet_private_key
WALLET_ADDRESS=0xYourWalletAddress

# SerpApi / Google Lens Reverse Search (Optional)
SERPAPI_KEY=your_serpapi_key_here
```
> **Note:** The application works completely without external keys. With `BLOCKCHAIN_ANCHOR_ENABLED=false`, local evidence hashing and manifest verification run smoothly without Ethereum transactions.

### 4. Running the Backend Server
```bash
uvicorn src.api.app:app --reload --port 8000
```
API Documentation will be live at:
- Swagger UI: `http://localhost:8000/docs`
- Health Endpoint: `http://localhost:8000/api/v1/health`

### 5. Frontend Setup & Launch
In a new terminal window:
```bash
cd frontend
npm install
npm run dev
```
Open your browser to:
- `http://localhost:5173`

---

## Running the Automated Test Suites

### Backend Unit & Integration Tests (pytest)
```bash
pytest -v
```
Runs 23 automated tests covering:
- Image file validation and rejection of corrupted/unsupported formats
- Immediate SHA-256 hashing and working copy generation
- Metadata extraction, missing field detection, and editing software tagging
- Error Level Analysis (JPEG) and lossless handling (PNG, WebP)
- Face detection and SFace encoding with OpenCV ONNX models
- Manifest canonical serialization and tamper detection
- Blockchain states, revert handling, and receipt confirmation
- Full FastAPI endpoints (upload, get, analyze, verify, report, and secure file streaming)

### Frontend Component & API Tests (Vitest)
```bash
cd frontend
npm test
```
Runs 6 automated tests covering:
- Navbar brand and network status indicators
- EvidenceList empty and populated rendering
- EvidenceUpload format validations and dropzone
- Typed API client endpoint construction

---

## CLI Pipeline Execution (Legacy Mode)

The original CLI verification pipeline is preserved and can be run directly:
```bash
python main.py
```
This runs the full end-to-end command-line workflow: face detection, SFace encoding, Google Lens public search, Sepolia transaction anchoring, and recalculation verification.

---

## API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Service health, model status, and blockchain configuration |
| `POST` | `/api/v1/evidence` | Upload image evidence (JPEG, PNG, WebP) |
| `GET` | `/api/v1/evidence` | List acquired evidence items (paginated) |
| `GET` | `/api/v1/evidence/{id}` | Retrieve full evidence record by ID |
| `POST` | `/api/v1/evidence/{id}/analyze` | Execute forensic pipeline (metadata, ELA, face, search, manifest) |
| `GET` | `/api/v1/evidence/{id}/report` | Retrieve or download official forensic report JSON |
| `POST` | `/api/v1/evidence/{id}/verify` | Recalculate original hash, manifest digest, and verify on-chain record |
| `POST` | `/api/v1/evidence/{id}/anchor` | Anchor evidence manifest hash to Ethereum Sepolia |
| `GET` | `/api/v1/evidence/{id}/files/{file_type}` | Securely stream image files (`original`, `working`, `ela`, `face_crop`) |
| `POST` | `/api/v1/legacy/verify` | Verify legacy verification metadata records against Sepolia |

---

## Security & Path Traversal Protections

- All evidence files are stored in isolated directories under `storage/evidence/<evidence_id>/`.
- The file streaming endpoint strictly verifies that requested paths resolve within the evidence root directory using path containment checks to eliminate path traversal vulnerabilities.
- Uploaded files are decoded into fresh memory objects before being accepted.
- Private keys and API keys are restricted to environment variables and never exposed to the client or saved in report exports.

---

## Legal & Forensic Notice

*FaceChain Forensics provides automated computational indicators, compression error visualizations, and cryptographic integrity proofs. Results represent mathematical indicators at the time of analysis and do not constitute a judicial certification or courtroom guarantee of image authenticity.*
