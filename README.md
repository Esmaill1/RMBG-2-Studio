---
title: RMBG-2 Studio
emoji: ✂️
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: AI-powered batch background removal using BRIA-RMBG-2.0
---

# ✂️ RMBG-2 Studio

AI-powered batch background removal tool using [BRIA-RMBG-2.0](https://huggingface.co/briaai/RMBG-2.0) (BiRefNet architecture).

> **Full documentation**: See [DOCS.md](DOCS.md) for the complete technical reference, API docs, configuration guide, and troubleshooting.

## Features

| Feature | Description |
|---------|-------------|
| Batch Processing | Upload and process multiple images at once |
| Dual Backend | CPU-optimized and GPU-accelerated servers |
| Auto-adaptive GPU | Adjusts batch size, torch.compile, and memory based on VRAM |
| ZIP Download | Export all results as a compressed archive |
| Auto Cleanup | Background thread removes output files older than 3 hours |
| CPU Quantization | Dynamic INT8 quantization for faster CPU inference |
| GPU Pipeline | Asynchronous PNG saving alongside GPU inference |
| kornia Preprocessing | GPU-accelerated image transforms |
| FP8 Support | Experimental float8 inference on Hopper GPUs (H200/H100) |
| Modern RTL UI | Arabic-language interface with glassmorphism design |

## Quick Start

### Option 1: Local (Linux/macOS)

```bash
chmod +x setup.sh && ./setup.sh    # Interactive setup — choose CPU or GPU
source venv/bin/activate
python app/flask_app.py             # CPU mode
# OR
python app/flask_app_gpu.py         # GPU mode (requires NVIDIA CUDA)
```

Open **http://127.0.0.1:7860** — the browser opens automatically.

### Option 2: Local (Windows)

- Double-click **`setup.bat`** → automated 7-step setup
- Double-click **`run.bat`** → start the server
- Double-click **`clean.bat`** → delete outputs + model cache

### Option 3: Docker (CPU)

```bash
docker build -f Dockerfile -t rmbg2-studio:cpu .
docker run -p 7860:7860 rmbg2-studio:cpu
```

### Option 4: Docker (GPU — requires NVIDIA runtime)

```bash
docker build -f Dockerfile.gpu -t rmbg2-studio:gpu .
docker run --gpus all -p 7860:7860 rmbg2-studio:gpu
```

### Option 5: Hugging Face Spaces

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full deployment guide.

## How It Works

1. **Upload** — Drag & drop or click to select images (JPG, PNG, WEBP; max 50MB CPU / 200MB GPU)
2. **Process** — BRIA-RMBG-2.0 generates a sigmoid mask, applied as the alpha channel
3. **Download** — Save individual results or export all as ZIP

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web interface |
| `/api/remove-bg` | POST | Remove background from uploaded images |
| `/api/zip` | POST | Download selected results as ZIP |
| `/api/delete-all` | POST | Delete all output files |
| `/output/<filename>` | GET | Serve a processed image |

See [DOCS.md — API Reference](DOCS.md#api-reference) for full request/response details.

## Documentation Index

| Document | Content |
|----------|---------|
| [DOCS.md](DOCS.md) | Comprehensive technical documentation (architecture, API, config, GPU optimization, frontend, troubleshooting) |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Hugging Face Spaces deployment guide |
| [STANDALONE.md](STANDALONE.md) | Legacy Gradio standalone notes (dependency pinning, monkeypatching) |

## Model

Uses [`cocktailpeanut/rm`](https://huggingface.co/cocktailpeanut/rm) — a repackaged [BRIA-RMBG-2.0](https://huggingface.co/briaai/RMBG-2.0) model (BiRefNet architecture).

| Property | Value |
|----------|-------|
| Input resolution | 1024 × 1024 |
| Output | Sigmoid probability mask |
| Normalization | ImageNet mean/std |
| CPU inference | FP32 + INT8 dynamic quantization |
| GPU inference | FP16 + autocast (FP8 on Hopper) |

## License

MIT License
