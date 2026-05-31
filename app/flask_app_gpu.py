"""
Flask Web Application for RMBG-2-Studio — GPU-Optimized Version
Background Removal and Replacement using BRIA-RMBG-2.0
Auto-adaptive: adjusts batch size, torch.compile, and memory management
based on GPU VRAM. Works on any CUDA GPU from RTX 3050 (4GB) to H200 (80GB).
Hopper-exclusive features (FP8) are disabled automatically on older GPUs.
"""

import os
import sys
import uuid
import time
import warnings
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from io import BytesIO

import torch
import numpy as np
from PIL import Image, ImageEnhance
from flask import Flask, request, jsonify, send_from_directory, render_template, send_file
from torchvision import transforms
from werkzeug.utils import secure_filename
import zipfile

from transformers import AutoModelForImageSegmentation

warnings.filterwarnings('ignore', category=FutureWarning, module='timm')

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

OUTPUT_FOLDER = os.environ.get('OUTPUT_FOLDER', None)
if OUTPUT_FOLDER is None:
    if os.path.exists('/app'):
        OUTPUT_FOLDER = '/app/output_images'
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        OUTPUT_FOLDER = os.path.join(os.path.dirname(script_dir), 'output_images')

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

CLEANUP_AGE_SECONDS = 3 * 60 * 60
CLEANUP_INTERVAL_SECONDS = 30 * 60

def cleanup_job():
    while True:
        try:
            now = time.time()
            if os.path.exists(OUTPUT_FOLDER):
                for filename in os.listdir(OUTPUT_FOLDER):
                    file_path = os.path.join(OUTPUT_FOLDER, filename)
                    if os.path.isfile(file_path):
                        creation_time = os.path.getmtime(file_path)
                        if now - creation_time > CLEANUP_AGE_SECONDS:
                            try:
                                os.remove(file_path)
                                print(f"Cleaned up old file: {filename}")
                            except OSError:
                                pass
        except Exception as e:
            print(f"Cleanup error: {e}")
        time.sleep(CLEANUP_INTERVAL_SECONDS)

cleanup_thread = threading.Thread(target=cleanup_job, daemon=True)
cleanup_thread.start()

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# ============== GPU Device Setup ==============
if not torch.cuda.is_available():
    print("ERROR: No CUDA GPU detected. This GPU-optimized version requires a CUDA-capable GPU.")
    print("Use flask_app.py instead for CPU-only systems.")
    sys.exit(1)

cuda_env = os.environ.get('CUDA_VISIBLE_DEVICES', None)
if cuda_env:
    print(f"CUDA_VISIBLE_DEVICES set to: {cuda_env}")

device = torch.device('cuda')
gpu_props = torch.cuda.get_device_properties(torch.cuda.current_device())
gpu_name = torch.cuda.get_device_name(torch.cuda.current_device())
gpu_mem_total = gpu_props.total_memory / (1024 ** 3)
compute_cap = gpu_props.major * 10 + gpu_props.minor

print(f"GPU: {gpu_name}")
print(f"GPU Memory: {gpu_mem_total:.1f} GB total")
print(f"Compute Capability: {compute_cap} ({'Hopper' if compute_cap >= 90 else 'Pre-Hopper'})")

if gpu_mem_total < 4:
    print("WARNING: GPU has less than 4GB VRAM. Performance will be limited.")
    print("  Consider using flask_app.py (CPU version) with quantization instead.")

# ============== Performance Configuration (Auto-Adaptive) ==============
# Defaults are computed based on GPU VRAM to ensure safety on any GPU.
# Override any setting via environment variables if you want to push limits.

# Adaptive batch size: each 1024x1024 float16 image tensor is ~6MB
#   <6GB VRAM  ->  4  (safe for 4GB laptop GPUs like RTX 3050)
#   6-12GB     ->  8  (safe for 8GB GPUs like RTX 3050/3060/4060)
#   12-24GB    ->  16 (safe for 12-24GB GPUs like RTX 3080/4070/4090)
#   24+GB      ->  32 (H200/H100/A100 — trivial on 80GB)
recommended_batch = 4 if gpu_mem_total < 6 else 8 if gpu_mem_total < 12 else 16 if gpu_mem_total < 24 else 32
MAX_BATCH_SIZE = int(os.environ.get('MAX_BATCH_SIZE', str(recommended_batch)))

# Adaptive torch.compile: skip on weak GPUs (<8GB) where the memory overhead
# (~100-200MB) and compile time (30-60s) aren't worth the marginal speedup
# since Python dispatch overhead is proportionally tiny on slow GPUs
recommended_compile = '1' if gpu_mem_total >= 8 else '0'
USE_TORCH_COMPILE = os.environ.get('TORCH_COMPILE', recommended_compile) == '1'
TORCH_COMPILE_MODE = os.environ.get('TORCH_COMPILE_MODE', 'default')

# Adaptive empty_cache: release VRAM back to CUDA pool after inference on GPUs
# with <16GB to avoid memory pressure. On large GPUs (16+GB) keep pools warm.
USE_EMPTY_CACHE = gpu_mem_total < 16

# FP8 inference — Hopper exclusive (H200/H100), experimental
USE_FP8 = os.environ.get('FP8_INFERENCE', '0') == '1'

if USE_FP8 and compute_cap < 90:
    print("WARNING: FP8 inference requires Hopper GPU (compute capability >= 9.0).")
    print(f"  Your GPU has compute capability {compute_cap}. Disabling FP8.")
    USE_FP8 = False

if USE_FP8:
    print("WARNING: FP8 inference is experimental and may cause quality degradation.")
    print("  FP8 uses torch.float8_e4m3fn — only supported on Hopper GPUs (H200/H100).")

print(f"Auto-adaptive config for {gpu_mem_total:.1f}GB VRAM:")
print(f"  MAX_BATCH_SIZE: {MAX_BATCH_SIZE} (recommended: {recommended_batch})")
print(f"  torch.compile:  {'ON' if USE_TORCH_COMPILE else 'OFF'} (recommended: {'ON' if recommended_compile == '1' else 'OFF'})")
print(f"  empty_cache:    {'ON (memory-safe)' if USE_EMPTY_CACHE else 'OFF (max throughput)'}")
print(f"  FP8:            {'ON' if USE_FP8 else 'OFF'}")

# ============== Model Loading ==============
print("Loading BRIA-RMBG-2.0 model (float16)...")

birefnet = AutoModelForImageSegmentation.from_pretrained(
    "cocktailpeanut/rm", trust_remote_code=True, torch_dtype=torch.float16
)
birefnet = birefnet.to(device)
birefnet.eval()

# ============== torch.compile ==============
compile_status = "disabled"
if USE_TORCH_COMPILE:
    try:
        birefnet = torch.compile(birefnet, mode=TORCH_COMPILE_MODE)
        compile_status = f"enabled (mode={TORCH_COMPILE_MODE})"
        print(f"torch.compile() {compile_status}")
    except Exception as e:
        compile_status = f"failed: {e}"
        print(f"torch.compile() {compile_status}")

# ============== Flash Attention ==============
torch.backends.cuda.enable_flash_sdp(True)

# ============== Warmup ==============
warmup_batch = min(MAX_BATCH_SIZE, 4)
print(f"Running warmup inference (batch={warmup_batch})...")
warmup_start = time.time()
warmup_tensor = torch.randn(warmup_batch, 3, 1024, 1024, dtype=torch.float16, device=device)
with torch.inference_mode():
    autocast_dtype = torch.float8_e4m3fn if USE_FP8 else torch.float16
    with torch.autocast(device_type="cuda", dtype=autocast_dtype):
        _ = birefnet(warmup_tensor)[-1].sigmoid().cpu()
del warmup_tensor
torch.cuda.synchronize()
warmup_time = time.time() - warmup_start
print(f"Warmup complete in {warmup_time:.2f}s")

gpu_mem_allocated = torch.cuda.memory_allocated() / (1024 ** 3)
gpu_mem_reserved = torch.cuda.memory_reserved() / (1024 ** 3)
print(f"Model loaded on {device} ({gpu_name})")
print(f"GPU Memory: {gpu_mem_allocated:.2f} GB allocated, {gpu_mem_reserved:.2f} GB reserved")

transform_image = transforms.Compose([
    transforms.Resize((1024, 1024)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])

# ============== Utility Functions ==============
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_filename(prefix="no_bg"):
    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    return f"{prefix}_{timestamp}_{unique_id}.png"

def remove_background_single(image):
    image_size = image.size
    input_tensor = transform_image(image).unsqueeze(0).to(device, non_blocking=True)
    autocast_dtype = torch.float8_e4m3fn if USE_FP8 else torch.float16
    with torch.inference_mode():
        with torch.autocast(device_type="cuda", dtype=autocast_dtype):
            preds = birefnet(input_tensor)[-1].sigmoid().cpu()
    pred = preds[0].squeeze()
    pred_pil = transforms.ToPILImage()(pred)
    mask = pred_pil.resize(image_size)
    image.putalpha(mask)
    if USE_EMPTY_CACHE:
        torch.cuda.empty_cache()
    return image

def remove_background_batch(images):
    if len(images) == 1:
        return [remove_background_single(images[0])]

    original_sizes = [img.size for img in images]
    tensors = [transform_image(img) for img in images]

    autocast_dtype = torch.float8_e4m3fn if USE_FP8 else torch.float16
    all_preds = []
    for chunk_start in range(0, len(tensors), MAX_BATCH_SIZE):
        chunk_end = min(chunk_start + MAX_BATCH_SIZE, len(tensors))
        chunk_tensors = tensors[chunk_start:chunk_end]
        batch_tensor = torch.stack(chunk_tensors).to(device, non_blocking=True)

        with torch.inference_mode():
            with torch.autocast(device_type="cuda", dtype=autocast_dtype):
                preds = birefnet(batch_tensor)[-1].sigmoid().cpu()

        all_preds.append(preds)
        if USE_EMPTY_CACHE:
            torch.cuda.empty_cache()

    results = []
    pred_offset = 0
    for chunk_preds in all_preds:
        for i in range(chunk_preds.shape[0]):
            global_idx = pred_offset + i
            pred = chunk_preds[i].squeeze()
            pred_pil = transforms.ToPILImage()(pred)
            mask = pred_pil.resize(original_sizes[global_idx])
            result_img = images[global_idx].copy()
            result_img.putalpha(mask)
            results.append(result_img)
        pred_offset += chunk_preds.shape[0]

    return results

# ============== API Routes ==============
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/remove-bg', methods=['POST'])
def api_remove_bg():
    if 'images' not in request.files:
        return jsonify({'error': 'No image files provided'}), 400
    files = request.files.getlist('images')
    if not files:
        return jsonify({'error': 'No files selected'}), 400

    valid_images = []
    file_info = []
    for file in files:
        if file.filename == '' or not allowed_file(file.filename):
            continue
        try:
            image = Image.open(file.stream).convert('RGB')
            original_base = os.path.splitext(secure_filename(file.filename))[0]
            valid_images.append(image)
            file_info.append({
                'original_base': original_base,
                'original_name': file.filename
            })
        except Exception as e:
            print(f"Error opening {file.filename}: {e}")

    if not valid_images:
        return jsonify({'error': 'No valid images to process'}), 400

    try:
        processed_images = remove_background_batch(valid_images)
    except Exception as e:
        print(f"Batch inference error: {e}")
        torch.cuda.empty_cache()
        return jsonify({'error': 'Inference failed'}), 500

    results = []
    for i, processed in enumerate(processed_images):
        original_base = file_info[i]['original_base']
        filename = f"{original_base}.png"
        counter = 1
        while os.path.exists(os.path.join(OUTPUT_FOLDER, filename)):
            filename = f"{original_base}_{counter}.png"
            counter += 1
        output_path = os.path.join(OUTPUT_FOLDER, filename)
        processed.save(output_path, 'PNG')
        results.append({
            'filename': filename,
            'url': f'/output/{filename}',
            'original_name': file_info[i]['original_name']
        })

    return jsonify({'success': True, 'results': results})

@app.route('/api/zip', methods=['POST'])
def api_download_zip():
    data = request.get_json()
    if not data or 'filenames' not in data:
        return jsonify({'error': 'No filenames provided'}), 400
    filenames = data['filenames']
    if not filenames:
        return jsonify({'error': 'List is empty'}), 400
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname in filenames:
            file_path = os.path.join(OUTPUT_FOLDER, secure_filename(fname))
            if os.path.exists(file_path):
                zf.write(file_path, fname)
    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'rmbg_results_{datetime.now().strftime("%H%M%S")}.zip'
    )

@app.route('/api/delete-all', methods=['POST'])
def api_delete_all():
    try:
        deleted_count = 0
        if os.path.exists(OUTPUT_FOLDER):
            for filename in os.listdir(OUTPUT_FOLDER):
                file_path = os.path.join(OUTPUT_FOLDER, filename)
                if os.path.isfile(file_path):
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                    except OSError:
                        pass
        return jsonify({'success': True, 'count': deleted_count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/output/<filename>')
def serve_output(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)

# ============== Run Server ==============
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 7860))

    if gpu_mem_total < 6:
        gpu_tier = "Budget (<6GB)"
    elif gpu_mem_total < 12:
        gpu_tier = "Mid-Range (6-12GB)"
    elif gpu_mem_total < 24:
        gpu_tier = "High-End (12-24GB)"
    else:
        gpu_tier = "Datacenter (24+GB)"

    print("\n" + "=" * 50)
    print("  RMBG-2-Studio GPU Server")
    print("=" * 50)
    print(f"  GPU:            {gpu_name}")
    print(f"  VRAM:           {gpu_mem_total:.1f} GB [{gpu_tier}]")
    print(f"  Compute Cap:    {compute_cap} ({'Hopper' if compute_cap >= 90 else 'Pre-Hopper'})")
    print(f"  torch.compile:  {compile_status}")
    print(f"  FP8:            {'enabled' if USE_FP8 else 'disabled'}")
    print(f"  Batch Size:     {MAX_BATCH_SIZE} (adaptive)")
    print(f"  Empty Cache:    {'ON (memory-safe)' if USE_EMPTY_CACHE else 'OFF (max throughput)'}")
    print(f"  Warmup:         {warmup_time:.2f}s")
    print(f"  URL:            http://127.0.0.1:{port}")
    print("  The browser will open automatically...")
    print("=" * 50 + "\n")

    def open_browser():
        webbrowser.open(f"http://127.0.0.1:{port}")
    timer = threading.Timer(2, open_browser)
    timer.daemon = True
    timer.start()
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)