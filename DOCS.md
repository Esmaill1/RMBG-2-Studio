# RMBG-2-Studio — Comprehensive Documentation

> AI-powered batch background removal tool powered by [BRIA-RMBG-2.0](https://huggingface.co/briaai/RMBG-2.0)

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [API Reference](#api-reference)
5. [Configuration](#configuration)
6. [Installation](#installation)
   - [Local Setup (Linux/macOS)](#local-setup-linuxmacos)
   - [Local Setup (Windows)](#local-setup-windows)
   - [Docker (CPU)](#docker-cpu)
   - [Docker (GPU)](#docker-gpu)
   - [Hugging Face Spaces](#hugging-face-spaces)
7. [GPU Optimization Details](#gpu-optimization-details)
8. [Frontend Design](#frontend-design)
9. [Background Cleanup System](#background-cleanup-system)
10. [Environment Variables](#environment-variables)
11. [Troubleshooting](#troubleshooting)
12. [License](#license)

---

## Overview

RMBG-2-Studio is a web application that removes backgrounds from images using the **BRIA-RMBG-2.0** model (BiRefNet architecture). It provides a clean, modern RTL Arabic-language interface for uploading multiple images, processing them in batch, and downloading the results individually or as a ZIP archive.

### Key Features

| Feature | Description |
|---------|-------------|
| **Batch Processing** | Upload and process multiple images simultaneously |
| **Unified Backend** | Unified (`flask_app.py`) with GPU acceleration and CPU fallback |
| **Auto-adaptive GPU** | Automatically adjusts batch size, torch.compile, and memory management based on GPU VRAM |
| **ZIP Download** | Export all processed results as a compressed archive |
| **Auto Cleanup** | Background thread removes output files older than 3 hours |
| **CPU Quantization** | Dynamic INT8 quantization on CPU for faster inference |
| **GPU Pipeline Parallelism** | Asynchronous PNG saving alongside GPU inference |
| **GPU Preprocessing** | kornia-based GPU-accelerated image transforms |
| **FP8 Support** | Experimental float8 inference on Hopper GPUs (H200/H100) |
| **Flash Attention** | CUDA SDP (Scaled Dot Product) flash attention enabled |
| **Modern UI** | RTL Arabic interface with glassmorphism, grain textures, and smooth animations |

---

## Architecture

RMBG-2-Studio follows a **single-server architecture** where the Flask backend serves both the web UI and the ML inference pipeline:

```
┌──────────────────────────────────────────────────────────┐
│                      Client Browser                       │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │ index.html   │  │  app.js      │  │   style.css     │ │
│  │ (RTL Arabic) │  │ (Fetch API)  │  │  (Glassmorphism)│ │
│  └─────────────┘  └──────────────┘  └─────────────────┘ │
└───────────────────────────┬──────────────────────────────┘
                            │ HTTP (FormData / JSON)
                            ▼
┌──────────────────────────────────────────────────────────┐
│                   Flask Server                            │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  Routes:                                            │ │
│  │    GET  /            → render index.html             │ │
│  │    POST /api/remove-bg → process images              │ │
│  │    POST /api/zip       → create ZIP download         │ │
│  │    POST /api/delete-all → clear output directory     │ │
│  │    GET  /output/<name> → serve processed image       │ │
│  └─────────────────────────────────────────────────────┘ │
│  ┌───────────────────┐  ┌──────────────────────────────┐ │
│  │ Cleanup Thread    │  │  ML Inference Pipeline        │ │
│  │ (daemon, 30min)   │  │  BRIA-RMBG-2.0 (BiRefNet)    │ │
│  │ deletes files >3h │  │  CPU: quantized INT8          │ │
│  └───────────────────┘  │  GPU: FP16 + batch + compile │ │
│                          └──────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│                output_images/ directory                    │
│  (stores processed PNG files, auto-cleaned after 3 hrs)   │
└──────────────────────────────────────────────────────────┘
```

### CPU vs GPU Modes

Both CPU and GPU modes are unified inside `flask_app.py`. The server automatically determines which mode to execute based on hardware availability:

| Aspect | CPU Mode (Auto-detected) | GPU Mode (Auto-detected) |
|--------|----------------------|--------------------------|
| Device detection | `devicetorch.get(torch)` — auto | Hardcoded `torch.device('cuda')` |
| Model precision | FP32 (default) | FP16 (`torch.float16`) |
| Quantization | Dynamic INT8 on `torch.nn.Linear` | None (GPU is fast enough) |
| Preprocessing | `torchvision.transforms` (CPU) | `kornia` (GPU-accelerated) |
| Batch processing | Sequential (one at a time) | Batched chunks (auto-sized) |
| Image saving | Synchronous | Asynchronous via `ThreadPoolExecutor` |
| Max upload size | 50 MB | 200 MB |
| `torch.compile` | Not available | Available (≥24GB VRAM recommended) |
| FP8 inference | Not available | Available (Hopper GPUs only) |
| Flash Attention | Not available | Enabled (`enable_flash_sdp`) |
| Warmup | None | Synthetic batch warmup at startup |
| Thread count optimization | `torch.set_num_threads(cpu_count)` | Not needed |

---

## Project Structure

```
RMBG-2-Studio/
├── app/
│   ├── flask_app.py          # Unified Flask server (CPU & GPU optimized)
│   ├── requirements.txt      # App dependencies (torch installed separately by setup)
│   ├── static/
│   │   ├── app.js            # Frontend JavaScript (Fetch API, drag & drop)
│   │   └── style.css         # CSS (RTL, glassmorphism, animations)
│   ├── templates/
│   │   └── index.html        # Main HTML template (RTL Arabic)
│   └── env/                  # Windows virtual environment (gitignored)
├── output_images/             # Processed PNG output directory (gitignored)
├── venv/                      # Linux/macOS virtual environment (gitignored)
├── download_model.py          # Pre-download model to HuggingFace cache
├── Dockerfile                 # CPU-only Docker image
├── Dockerfile.gpu             # GPU (CUDA 12.4) Docker image
├── setup.sh                   # Linux/macOS interactive setup script
├── setup.bat                  # Windows automated setup script
├── run.bat                    # Windows launcher (activates venv + starts server)
├── clean.bat                  # Windows cleanup (deletes outputs + model cache)
├── .gitignore                 # Ignores venv, outputs, binaries, IDE files
├── README.md                  # Project overview (HuggingFace Spaces metadata)
├── DEPLOYMENT.md              # HuggingFace Spaces deployment guide
├── STANDALONE.md              # Legacy Gradio standalone documentation
└── DOCS.md                    # This comprehensive documentation file
```

---

## API Reference

All endpoints are served by the Flask application on the configured port (default: `7860`).

### `GET /`

Renders the main web interface (`index.html`). No parameters.

**Response**: HTML page with RTL Arabic UI for image upload and processing.

---

### `POST /api/remove-bg`

Removes backgrounds from uploaded images. Accepts multipart form data with one or more image files.

**Request**:
- Content-Type: `multipart/form-data`
- Field name: `images` — one or more image files
- Accepted formats: `png`, `jpg`, `jpeg`, `gif`, `webp`
- Max upload: 50 MB (CPU) / 200 MB (GPU)

**Response** (JSON):
```json
{
  "success": true,
  "results": [
    {
      "filename": "photo.png",
      "url": "/output/photo.png",
      "original_name": "photo.jpg"
    },
    {
      "filename": "photo_1.png",
      "url": "/output/photo_1.png",
      "original_name": "another_photo.jpg"
    }
  ]
}
```

**Error Response**:
```json
{
  "error": "No image files provided"
}
```

**Processing details**:
- CPU backend: Processes images sequentially, one at a time
- GPU backend: Processes images in batched chunks (size determined by `MAX_BATCH_SIZE`)
- Duplicate filenames are handled by appending a counter (`photo_1.png`, `photo_2.png`, etc.)
- Failed images are silently skipped — the API returns only successfully processed results

---

### `POST /api/zip`

Creates and returns a ZIP archive of specified processed images.

**Request**:
- Content-Type: `application/json`
- Body:
```json
{
  "filenames": ["photo.png", "another.png"]
}
```

**Response**: ZIP file download with Content-Type `application/zip`.

- Download name: `rmbg_results_HHMMSS.zip`
- Compression: `ZIP_DEFLATED`
- Only files that exist in the output directory are included

**Error Response**:
```json
{
  "error": "No filenames provided"
}
```

---

### `POST /api/delete-all`

Deletes all files from the output directory.

**Request**: No body required.

**Response** (JSON):
```json
{
  "success": true,
  "count": 5
}
```

`count` indicates the number of files deleted. Files that cannot be deleted (e.g., locked by OS) are silently skipped.

---

### `GET /output/<filename>`

Serves a processed image file from the output directory.

**Parameters**:
- `filename` — the exact filename returned by `/api/remove-bg`

**Response**: The PNG image file with appropriate MIME type.

---

## Configuration

### CPU Backend Configuration (`flask_app.py`)

| Setting | Default | Description |
|---------|---------|-------------|
| `MAX_CONTENT_LENGTH` | 50 MB | Maximum upload size |
| `OUTPUT_FOLDER` | Auto-detected | Output directory (see Environment Variables) |
| `CLEANUP_AGE_SECONDS` | 10800 (3 hrs) | Age threshold for file cleanup |
| `CLEANUP_INTERVAL_SECONDS` | 1800 (30 min) | Cleanup check interval |
| `MODEL_NAME` | `cocktailpeanut/rm` | HuggingFace model identifier |
| `ALLOWED_EXTENSIONS` | `png, jpg, jpeg, gif, webp` | Accepted image formats |
| `PORT` | 7860 | Server port |

### GPU Mode Configuration (within `flask_app.py`)

| Setting | Default | Auto-Adaptive | Description |
|---------|---------|---------------|-------------|
| `MAX_CONTENT_LENGTH` | 200 MB | — | Maximum upload size |
| `MAX_BATCH_SIZE` | Auto | Based on VRAM | Batch size for GPU inference |
| `TORCH_COMPILE` | Auto | On if ≥24GB | Enable `torch.compile()` JIT optimization |
| `TORCH_COMPILE_MODE` | `default` | — | `torch.compile` mode |
| `FP8_INFERENCE` | `0` (off) | — | Enable FP8 on Hopper GPUs |
| `USE_EMPTY_CACHE` | Auto | On if <16GB | Call `torch.cuda.empty_cache()` after each batch |

**Auto-Adaptive Batch Size Table**:

| GPU VRAM | Recommended Batch Size | torch.compile | Empty Cache |
|----------|----------------------|---------------|-------------|
| < 6 GB | 4 | Off | On |
| 6–12 GB | 8 | Off | On |
| 12–24 GB | 16 | Off | On |
| 24–48 GB | 32 | On | Off |
| 48–96 GB | 64 | On | Off |
| > 96 GB | 128 | On | Off |

---

## Installation

### Local Setup (Linux/macOS)

The `setup.sh` script provides an interactive setup with CPU or GPU mode selection.

```bash
# 1. Clone the repository
git clone https://github.com/your-repo/RMBG-2-Studio.git
cd RMBG-2-Studio

# 2. Run the setup script
chmod +x setup.sh
./setup.sh
```

The script will:
1. Ask you to choose CPU (option 1) or GPU/CUDA (option 2)
2. Check Python version (3.8+ required)
3. Create a virtual environment at `./venv`
4. Install PyTorch (CPU-only index or default CUDA)
5. Install application dependencies from `app/requirements.txt`
6. Pre-download and cache the model locally

**After setup**:
```bash
# Activate the virtual environment
source venv/bin/activate

# Run the server (auto-detects CPU/GPU and launches)
./run.sh
```

The browser opens automatically at `http://127.0.0.1:7860`.

---

### Local Setup (Windows)

Double-click `setup.bat` or run it from a command prompt.

The script performs these steps:
1. **[1/7] Check Python** — Verifies Python 3.8+ is installed and in PATH
2. **[2/7] Check Visual C++ Redistributable** — Downloads and installs if missing (required for PyTorch)
3. **[3/7] Create virtual environment** — Creates `./venv`, recreates if existing venv has broken PyTorch
4. **[4/7] Activate venv** — Activates the virtual environment
5. **[5/7] Install PyTorch** — Auto-detects NVIDIA GPU via `nvidia-smi`. Installs CUDA PyTorch from `https://download.pytorch.org/whl/cu128` if GPU found, otherwise CPU-only from `https://download.pytorch.org/whl/cpu`
6. **[6/7] Install app dependencies** — Runs `pip install -r app/requirements.txt`
7. **[7/7] Pre-download model** — Runs `download_model.py` to cache the model

**After setup**: Double-click `run.bat` to start the server. It:
- Activates the virtual environment
- Starts `python flask_app.py`
- The browser opens automatically

**Cleanup**: Double-click `clean.bat` to:
- Delete all processed images from `output_images/`
- Delete the HuggingFace model cache (~176 MB)
- Requires re-running `setup.bat` to restore the model

---

### Docker (CPU)

Build and run the CPU-only Docker image:

```bash
# Build
docker build -f Dockerfile -t rmbg2-studio:cpu .

# Run
docker run -p 7860:7860 rmbg2-studio:cpu
```

**Dockerfile details**:
- Base image: `python:3.10-slim`
- System libs: `libgl1`, `libglib2.0-0` (for OpenCV)
- PyTorch: CPU-only from `https://download.pytorch.org/whl/cpu`
- Runs as non-root user `user` (UID 1000) for security
- Creates `/app/output_images` with correct permissions
- Entry point: `python flask_app.py`
- Exposed port: 7860

---

### Docker (GPU)

Build and run the GPU-enabled Docker image (requires NVIDIA Docker runtime):

```bash
# Build
docker build -f Dockerfile.gpu -t rmbg2-studio:gpu .

# Run with GPU access
docker run --gpus all -p 7860:7860 rmbg2-studio:gpu
```

**Dockerfile.gpu details**:
- Base image: `nvidia/cuda:12.4.0-runtime-ubuntu22.04`
- Python: 3.10 from deadsnakes PPA
- System libs: `libgl1`, `libglib2.0-0`
- PyTorch: Default (includes CUDA 12.x)
- Entry point: `python flask_app.py`
- Environment: `CUDA_VISIBLE_DEVICES=0`
- Runs as non-root user `user` (UID 1000)

---

### Hugging Face Spaces

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full HuggingFace Spaces deployment guide. Quick summary:

1. Create a new Space at [huggingface.co/new-space](https://huggingface.co/new-space)
2. Select **Docker** as the SDK
3. Choose **CPU basic** (free) or **T4 small** for faster processing
4. Push the code to the Space's git repository
5. The Space auto-rebuilds on every push

---

## GPU Optimization Details

When running in GPU mode, the unified server (`flask_app.py`) implements several advanced optimizations:

### 1. Auto-Adaptive Configuration

On startup, the server detects GPU VRAM and compute capability, then configures:

- **Batch size**: Scales from 4 (4GB VRAM) to 128 (96GB+ VRAM)
- **torch.compile**: Enabled only on GPUs with ≥24GB VRAM (5–15 min JIT warmup)
- **Empty cache**: Enabled on GPUs with <16GB VRAM to prevent OOM
- **FP8**: Only on Hopper GPUs (compute capability ≥ 9.0)

### 2. GPU-Accelerated Preprocessing (kornia)

Instead of `torchvision.transforms` on CPU, the GPU backend uses `kornia` for:

- `image_to_tensor` — converts PIL/numpy images to GPU tensors
- `resize` — GPU-accelerated bilinear interpolation to 1024×1024
- Normalization — computed directly on GPU with pre-allocated `NORM_MEAN` / `NORM_STD` tensors

For batch processing, `preprocess_gpu_batch()` concatenates multiple images into a single GPU tensor before resize/normalize, minimizing CPU→GPU transfer overhead.

### 3. Batched Inference

Images are processed in chunks of `MAX_BATCH_SIZE`:

```python
for chunk_start in range(0, len(images), MAX_BATCH_SIZE):
    chunk_end = min(chunk_start + MAX_BATCH_SIZE, len(images))
    chunk_images = images[chunk_start:chunk_end]
    batch_tensor = preprocess_gpu_batch(chunk_images)
    preds = birefnet(batch_tensor)[-1].sigmoid().cpu()
```

### 4. Pipeline Parallelism

PNG saving runs in a separate `ThreadPoolExecutor` (4 workers) alongside GPU inference:

```python
save_executor = ThreadPoolExecutor(max_workers=4)
save_futures.append(save_executor.submit(save_result_async, processed, output_path))
```

PNG files are saved with `compress_level=1` for maximum speed.

### 5. FP16 Inference with Autocast

The model loads in `torch.float16` and inference uses `torch.autocast`:

```python
with torch.autocast(device_type="cuda", dtype=torch.float16):
    preds = birefnet(batch_tensor)[-1].sigmoid().cpu()
```

### 6. Flash Attention

SDP (Scaled Dot Product) flash attention is enabled at startup:

```python
torch.backends.cuda.enable_flash_sdp(True)
```

### 7. Warmup Inference

A synthetic warmup batch is run at startup to:
- Complete `torch.compile` JIT compilation (if enabled)
- Pre-allocate GPU memory
- Measure warmup time for logging

### 8. FP8 (Experimental)

FP8 inference uses `torch.float8_e4m3fn` datatype, only available on Hopper GPUs (H100/H200, compute capability ≥ 9.0). It reduces memory usage and can improve throughput, but may cause quality degradation. Enable via environment variable `FP8_INFERENCE=1`.

---

## Frontend Design

The web interface is an RTL (right-to-left) Arabic-language single-page application.

### HTML (`index.html`)

- Language: `ar` (Arabic), direction: `rtl`
- Fonts: **Lalezar** (display/headings), **Tajawal** (body text) — loaded from Google Fonts
- Icons: **Phosphor Icons** (`@phosphor-icons/web`) — loaded from unpkg CDN
- UI title: "ستوديو الهلال" (Crescent Studio)
- Subtitle: "اداة إزالة الخلفيات" (Background Removal Tool)

### Layout Structure

```
┌─────────────────────────────────────────────────────────┐
│  Header: "ستوديو الهلال" + model badge (BRIA-RMBG 2.0) │
├─────────────────────────────────────────────────────────┤
│  Upload Zone: Drag & drop or click to upload            │
│  (supports JPG, PNG, WEBP, max 200MB)                   │
├─────────────────────────────────────────────────────────┤
│  Progress Bar: Shows during processing                   │
├─────────────────────────────────────────────────────────┤
│  Results Header: "الصور المعالجة" + Download/Clear btns │
├─────────────────────────────────────────────────────────┤
│  Results Grid: Card layout for processed images          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                │
│  │  Image   │ │  Image   │ │  Image   │                │
│  │ (checker │ │ (checker │ │ (checker │                │
│  │  board)  │ │  board)  │ │  board)  │                │
│  │ filename │ │ filename │ │ filename │                │
│  │  ↓ save  │ │  ↓ save  │ │  ↓ save  │                │
│  └──────────┘ └──────────┘ └──────────┘                │
├─────────────────────────────────────────────────────────┤
│  Toast notifications (success/error)                     │
└─────────────────────────────────────────────────────────┤
```

### CSS (`style.css`) Design System

| Token | Value | Purpose |
|-------|-------|---------|
| `--bg-deep` | `#f7f6f2` | Page background |
| `--bg-surface` | `#eae9e4` | Elevated surfaces |
| `--bg-elevated` | `#dedcd6` | Hover/active states |
| `--bg-card` | `#ffffff` | Card backgrounds |
| `--accent-primary` | `#D4A843` | Gold accent (buttons, highlights) |
| `--accent-secondary` | `#2BA89A` | Teal accent (subtle backgrounds) |
| `--text-bright` | `#1a1a22` | Heading text |
| `--text-main` | `#4a4a56` | Body text |
| `--text-muted` | `#8a8a96` | Secondary/muted text |
| `--danger` | `#d83030` | Error/delete actions |
| `--font-display` | Lalezar | Headings |
| `--font-body` | Tajawal | Body text |
| `--radius` | 14px | Default border radius |
| `--radius-lg` | 20px | Large border radius |

**Visual effects**:
- **Grain overlay**: Fixed SVG noise texture at 2% opacity for texture
- **Grid overlay**: Diagonal line pattern at 6% opacity
- **Glassmorphism**: `backdrop-filter: blur(20px)` on cards, headers, and buttons
- **Checkerboard pattern**: CSS-only transparency indicator on result images
- **Animations**: `cardEnter` (slide+scale), `shimmer` (progress bar), `staggerIn` (page load), `portalPulse` (upload zone glow ring), `spin` (loading spinner)
- **Responsive**: Breakpoints at 768px and 480px

### JavaScript (`app.js`) Behavior

| Feature | Implementation |
|---------|---------------|
| **Upload** | Click or drag & drop → `FormData` with `images` field → `POST /api/remove-bg` |
| **Progress** | Animated progress bar with shimmer effect, percentage-based width |
| **Result cards** | Prepended to grid with `cardEnter` animation, filename + download link |
| **Delete card** | Fade+scale animation → `remove()` from DOM |
| **Download All** | Collects filenames from cards → `POST /api/zip` → blob download trigger |
| **Clear All** | Confirm dialog → `POST /api/delete-all` → clears grid |
| **Toast** | Bottom-left positioned, success (gold) or error (red), auto-dismiss 3s |
| **File validation** | Only `image/*` MIME types accepted |

---

## Background Cleanup System

Both backends run a daemon thread that periodically deletes old output files:

```python
CLEANUP_AGE_SECONDS = 3 * 60 * 60      # 3 hours
CLEANUP_INTERVAL_SECONDS = 30 * 60      # 30 minutes
```

- The thread runs `cleanup_job()` in an infinite loop
- Every 30 minutes, it scans `OUTPUT_FOLDER`
- Files with `mtime` older than 3 hours are deleted
- Errors are caught and logged — the thread never crashes
- Thread is marked as `daemon=True` so it exits when the main process stops

---

## Environment Variables

| Variable | Default | Backend | Description |
|----------|---------|---------|-------------|
| `PORT` | `7860` | Both | Server listening port |
| `OUTPUT_FOLDER` | Auto-detected | Both | Path to output image directory |
| `CUDA_VISIBLE_DEVICES` | `0` (GPU Docker) | GPU | GPU device selection |
| `MAX_BATCH_SIZE` | Auto (by VRAM) | GPU | Override auto-adaptive batch size |
| `TORCH_COMPILE` | Auto (by VRAM) | GPU | Enable/disable `torch.compile` (`1`/`0`) |
| `TORCH_COMPILE_MODE` | `default` | GPU | `torch.compile` optimization mode |
| `FP8_INFERENCE` | `0` | GPU | Enable FP8 inference on Hopper GPUs (`1`/`0`) |

**OUTPUT_FOLDER auto-detection logic**:
1. If `OUTPUT_FOLDER` env var is set → use that path
2. If `/app` directory exists (Docker container) → `/app/output_images`
3. Otherwise → `<project_root>/output_images`

---

## Troubleshooting

### Common Issues

#### `libgl1-mesa-glx` not found (Docker)
- **Cause**: Deprecated package in newer Debian versions
- **Fix**: Use `libgl1` instead — already fixed in current `Dockerfile`

#### Push rejected — binary files (HuggingFace Spaces)
- **Cause**: Trying to upload images without Git LFS
- **Fix**: Run `git rm --cached icon.png` and other images, then commit and push
- The `.gitignore` excludes `*.png`, `*.jpg`, `*.jpeg`, `icon.png`, `screenshots/`

#### Application Error / Build Failed (HuggingFace Spaces)
- **Cause**: Missing packages or path issues
- **Fix**: Check the Space's **Logs** tab for detailed errors

#### GPU not detected (GPU backend)
- **Cause**: `torch.cuda.is_available()` returns `False` — usually means the CPU-only PyTorch was installed
- **Fix**: Reinstall PyTorch with CUDA: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128`. Running `setup.bat` or `setup.sh` handles this automatically.

#### torch.compile warmup appears stuck
- **Cause**: JIT compilation takes 5–15 minutes on first run
- **Fix**: This is normal behavior. Wait for warmup to complete. To disable: `TORCH_COMPILE=0`

#### Out of memory (GPU)
- **Cause**: Batch size too large for available VRAM
- **Fix**: Set `MAX_BATCH_SIZE` environment variable to a lower value (e.g., `4` or `8`)

#### Slow CPU inference
- **Cause**: No quantization or limited CPU threads
- **Fix**: The CPU backend auto-applies INT8 quantization and sets `torch.set_num_threads` to CPU count. Verify these are active in startup logs.

#### Model download fails
- **Cause**: Network issues or HuggingFace access problems
- **Fix**: The model will be downloaded on first run. If that also fails, check internet connectivity and HuggingFace access to `cocktailpeanut/rm`

#### Visual C++ Redistributable missing (Windows)
- **Cause**: PyTorch requires VC++ runtime
- **Fix**: `setup.bat` auto-downloads and installs it. If that fails, manually download from https://aka.ms/vs/17/release/vc_redist.x64.exe

---

## Model Information

| Property | Value |
|----------|-------|
| **Model ID** | `cocktailpeanut/rm` |
| **Base model** | [BRIA-RMBG-2.0](https://huggingface.co/briaai/RMBG-2.0) |
| **Architecture** | BiRefNet (Bilateral Reference Network) |
| **Input size** | 1024 × 1024 |
| **Output** | Sigmoid mask (probability map) |
| **Normalization** | ImageNet mean `[0.485, 0.456, 0.406]`, std `[0.229, 0.224, 0.225]` |
| **trust_remote_code** | Required (`True`) |

The model is loaded via `AutoModelForImageSegmentation.from_pretrained()` and run in `torch.inference_mode()` for maximum speed.

---

## License

MIT License — see the [README.md](README.md) header metadata for details.
