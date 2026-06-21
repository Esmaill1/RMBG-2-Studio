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

# RMBG-2 Studio

AI-powered batch background removal tool using [BRIA-RMBG-2.0](https://huggingface.co/briaai/RMBG-2.0).

## Features

- **Batch Processing**: Upload multiple images at once
- **Real-time Progress**: See processing status for each image
- **Download All**: Export all results as a ZIP file
- **Modern UI**: Clean, responsive interface

## Usage

1. Drag & drop images or click to upload
2. Wait for processing (progress bar updates per image)
3. Download individual images or use "Download All (ZIP)"

## Model

This app uses [BRIA-RMBG-2.0](https://huggingface.co/briaai/RMBG-2.0), a state-of-the-art background removal model.

## Local Development

```bash
cd app
pip install -r requirements.txt
python flask_app.py
```

Then open http://127.0.0.1:5000

## License

MIT License
