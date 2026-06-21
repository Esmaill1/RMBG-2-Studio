"""
Flask Web Application for RMBG-2-Studio
Background Removal using BRIA-RMBG-2.0
Auto-detects GPU: runs optimized GPU path if CUDA available, CPU path otherwise.
"""

import os
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
import sys
import uuid
import time
import warnings
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import zipfile

import torch
import torch.nn.functional as F
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from flask import Flask, request, jsonify, send_from_directory, render_template, send_file
from torchvision import transforms
from werkzeug.utils import secure_filename

try:
    import kornia
    USE_KORNIA = True
except ImportError:
    kornia = None
    USE_KORNIA = False

import devicetorch
from transformers import AutoModelForImageSegmentation

warnings.filterwarnings('ignore', category=FutureWarning, module='timm')
warnings.filterwarnings('ignore', category=DeprecationWarning, module='torch.ao.quantization')

USE_GPU = torch.cuda.is_available()

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024 if USE_GPU else 50 * 1024 * 1024

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

# Detect local model for offline loading
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
local_model_paths = [
    os.path.join(project_root, 'model'),
    os.path.join(project_root, 'model_gpu'),
    os.path.join(script_dir, 'model'),
]
model_source = "cocktailpeanut/rm"
for path in local_model_paths:
    if os.path.exists(os.path.join(path, 'config.json')):
        model_source = path
        print(f"Found local model files at: {path}. Loading in offline mode.")
        break

if USE_GPU:
    cuda_env = os.environ.get('CUDA_VISIBLE_DEVICES', None)
    if cuda_env:
        print(f"CUDA_VISIBLE_DEVICES set to: {cuda_env}")

    device = torch.device('cuda')
    gpu_props = torch.cuda.get_device_properties(torch.cuda.current_device())
    gpu_name = torch.cuda.get_device_name(torch.cuda.current_device())
    gpu_mem_total = gpu_props.total_memory / (1024 ** 3)
    compute_cap = gpu_props.major * 10 + gpu_props.minor

    if gpu_mem_total < 4:
        print("WARNING: GPU has less than 4GB VRAM. Performance will be limited.")

    recommended_batch = 1 if gpu_mem_total < 4 else \
                        2 if gpu_mem_total < 8 else \
                        4 if gpu_mem_total < 16 else \
                        8 if gpu_mem_total < 24 else \
                        16 if gpu_mem_total < 48 else \
                        32 if gpu_mem_total < 80 else 64
    MAX_BATCH_SIZE = int(os.environ.get('MAX_BATCH_SIZE', str(recommended_batch)))

    recommended_compile = '0'  # Off by default — warmup takes 5-15 min. Set TORCH_COMPILE=1 to enable.
    USE_TORCH_COMPILE = os.environ.get('TORCH_COMPILE', recommended_compile) == '1'
    TORCH_COMPILE_MODE = os.environ.get('TORCH_COMPILE_MODE', 'reduce-overhead')

    USE_EMPTY_CACHE = gpu_mem_total < 16
    USE_FP8 = os.environ.get('FP8_INFERENCE', '0') == '1'

    if USE_FP8 and compute_cap < 90:
        print(f"WARNING: FP8 requires compute capability >= 9.0. Your GPU has {compute_cap}. Disabling FP8.")
        USE_FP8 = False

    if USE_FP8:
        print("WARNING: FP8 inference is experimental and may cause quality degradation.")

    if not USE_KORNIA:
        print("WARNING: kornia not installed. GPU preprocessing will use torchvision (slower).")

    print(f"GPU detected: {gpu_name}")
    print(f"GPU Memory: {gpu_mem_total:.1f} GB")
    print(f"Compute Capability: {compute_cap}")
    print(f"Auto-adaptive config:")
    print(f"  Batch Size:     {MAX_BATCH_SIZE}")
    print(f"  torch.compile:  {'ON' if USE_TORCH_COMPILE else 'OFF'}")
    print(f"  FP8:            {'ON' if USE_FP8 else 'OFF'}")
    print(f"  kornia:         {'ON' if USE_KORNIA else 'OFF (fallback to torchvision)'}")

    print(f"Loading BRIA-RMBG-2.0 model (FP16) from {model_source}...")
    try:
        birefnet = AutoModelForImageSegmentation.from_pretrained(
            model_source, trust_remote_code=True, torch_dtype=torch.float16
        )
    except (ValueError, OSError) as e:
        if model_source != "cocktailpeanut/rm":
            print(f"WARNING: Failed to load from local source '{model_source}': {e}")
            print("Falling back to Hugging Face Hub ('cocktailpeanut/rm')...")
            birefnet = AutoModelForImageSegmentation.from_pretrained(
                "cocktailpeanut/rm", trust_remote_code=True, torch_dtype=torch.float16
            )
        else:
            raise e
    birefnet = birefnet.to(device)
    birefnet.eval()

    compile_status = "disabled"
    if USE_TORCH_COMPILE:
        print("WARNING: torch.compile() enabled. JIT compilation takes 5-15 minutes on first run.")
        try:
            birefnet = torch.compile(birefnet, mode=TORCH_COMPILE_MODE)
            compile_status = f"enabled (mode={TORCH_COMPILE_MODE})"
        except Exception as e:
            compile_status = f"failed: {e}"

    torch.backends.cuda.enable_flash_sdp(True)

    warmup_batch = 1  # Single-image warmup for fastest startup
    if USE_TORCH_COMPILE and compile_status.startswith("enabled"):
        print(f"Running warmup inference (batch={warmup_batch}) — includes torch.compile JIT (expect 5-15 min delay)...")
    else:
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

    # CUDA stream for overlapping preprocessing with inference
    preprocess_stream = torch.cuda.Stream()

    # GPU Preprocessing — optimized to resize on CPU to reduce PCIe transfer size
    # and normalize on GPU for speed.
    NORM_MEAN = torch.tensor([0.485, 0.456, 0.406], device=device, dtype=torch.float32).view(1, 3, 1, 1)
    NORM_STD = torch.tensor([0.229, 0.224, 0.225], device=device, dtype=torch.float32).view(1, 3, 1, 1)

    import torchvision.transforms.functional as TF

    def preprocess_gpu(image):
        # Resize on CPU to 1024x1024 (reduces PCIe transfer size by up to 50x)
        resized_pil = image.resize((1024, 1024), Image.BILINEAR)
        # Convert to tensor and scale to [0, 1] on CPU
        tensor = TF.to_tensor(resized_pil)
        # Asynchronously transfer to GPU using pinned memory
        tensor_gpu = tensor.pin_memory().to(device, non_blocking=True).unsqueeze(0)
        # Normalize on GPU
        return (tensor_gpu - NORM_MEAN) / NORM_STD

    def preprocess_gpu_batch(images):
        tensors = []
        for img in images:
            resized_pil = img.resize((1024, 1024), Image.BILINEAR)
            tensor = TF.to_tensor(resized_pil)
            tensors.append(tensor)
        # Stack on CPU, then transfer to GPU
        batch_tensor = torch.stack(tensors, dim=0).pin_memory().to(device, non_blocking=True)
        # Normalize on GPU
        return (batch_tensor - NORM_MEAN) / NORM_STD

    save_executor = ThreadPoolExecutor(max_workers=4)

    def save_result_async(processed, output_path):
        processed.save(output_path, 'PNG', compress_level=1)
        return output_path

    def remove_background_single(image):
        image_size = image.size  # (W, H)
        input_tensor = preprocess_gpu(image)
        autocast_dtype = torch.float8_e4m3fn if USE_FP8 else torch.float16
        with torch.inference_mode():
            with torch.autocast(device_type="cuda", dtype=autocast_dtype):
                preds = birefnet(input_tensor)[-1].sigmoid()
        # Resize mask on GPU, then transfer to CPU
        pred = preds[0]  # (1, H, W)
        if pred.shape[1] != image_size[1] or pred.shape[2] != image_size[0]:
            pred = F.interpolate(pred.unsqueeze(0), size=(image_size[1], image_size[0]),
                                 mode='bilinear', align_corners=False).squeeze(0)
        mask_np = (pred.squeeze().mul(255).byte().cpu().numpy())
        mask = Image.fromarray(mask_np, mode='L')
        image.putalpha(mask)
        if USE_EMPTY_CACHE:
            torch.cuda.empty_cache()
        return image

    def remove_background_batch(images):
        if len(images) == 1:
            return [remove_background_single(images[0])]

        original_sizes = [img.size for img in images]  # list of (W, H)
        autocast_dtype = torch.float8_e4m3fn if USE_FP8 else torch.float16

        # Pre-compute all chunks for stream overlap
        chunk_ranges = []
        for chunk_start in range(0, len(images), MAX_BATCH_SIZE):
            chunk_end = min(chunk_start + MAX_BATCH_SIZE, len(images))
            chunk_ranges.append((chunk_start, chunk_end))

        all_preds = []
        next_batch_tensor = None

        for ci, (chunk_start, chunk_end) in enumerate(chunk_ranges):
            # Use pre-computed tensor if available, otherwise compute now
            if next_batch_tensor is not None:
                torch.cuda.current_stream().wait_stream(preprocess_stream)
                batch_tensor = next_batch_tensor
                next_batch_tensor = None
            else:
                batch_tensor = preprocess_gpu_batch(images[chunk_start:chunk_end])

            # Start preprocessing next batch on separate stream
            if ci + 1 < len(chunk_ranges):
                next_start, next_end = chunk_ranges[ci + 1]
                with torch.cuda.stream(preprocess_stream):
                    next_batch_tensor = preprocess_gpu_batch(images[next_start:next_end])

            # Run inference on current batch
            with torch.inference_mode():
                with torch.autocast(device_type="cuda", dtype=autocast_dtype):
                    preds = birefnet(batch_tensor)[-1].sigmoid()
            all_preds.append(preds)
            if USE_EMPTY_CACHE:
                torch.cuda.empty_cache()

        results = []
        pred_offset = 0
        for chunk_preds in all_preds:
            for i in range(chunk_preds.shape[0]):
                global_idx = pred_offset + i
                w, h = original_sizes[global_idx]
                pred = chunk_preds[i]  # (1, 1024, 1024)
                # Resize mask on GPU
                if pred.shape[1] != h or pred.shape[2] != w:
                    pred = F.interpolate(pred.unsqueeze(0), size=(h, w),
                                         mode='bilinear', align_corners=False).squeeze(0)
                mask_np = pred.squeeze().mul(255).byte().cpu().numpy()
                mask = Image.fromarray(mask_np, mode='L')
                result_img = images[global_idx].copy()
                result_img.putalpha(mask)
                results.append(result_img)
            pred_offset += chunk_preds.shape[0]
        return results

else:
    device_str = devicetorch.get(torch)
    device = torch.device(device_str)

    if device_str == 'cpu':
        cpu_count = os.cpu_count() or 1
        torch.set_num_threads(max(1, cpu_count))
        print(f"No GPU detected. Running on CPU with {torch.get_num_threads()} threads.")
    else:
        print(f"No CUDA GPU detected. Running on {device_str} via devicetorch.")

    print(f"Loading BRIA-RMBG-2.0 model from {model_source}...")
    try:
        birefnet = AutoModelForImageSegmentation.from_pretrained(
            model_source, trust_remote_code=True
        )
    except (ValueError, OSError) as e:
        if model_source != "cocktailpeanut/rm":
            print(f"WARNING: Failed to load from local source '{model_source}': {e}")
            print("Falling back to Hugging Face Hub ('cocktailpeanut/rm')...")
            birefnet = AutoModelForImageSegmentation.from_pretrained(
                "cocktailpeanut/rm", trust_remote_code=True
            )
        else:
            raise e
    birefnet = devicetorch.to(torch, birefnet)
    birefnet.eval()

    if device_str == 'cpu':
        print("Applying Dynamic Quantization for CPU speedup...")
        try:
            birefnet = torch.quantization.quantize_dynamic(
                birefnet, {torch.nn.Linear}, dtype=torch.qint8
            )
        except Exception as e:
            print(f"Quantization warning: {e}")

    transform_image = transforms.Compose([
        transforms.Resize((1024, 1024)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    print(f"Model loaded on {device}")

    def remove_background(image):
        image_size = image.size
        input_images = transform_image(image).unsqueeze(0)
        input_images = devicetorch.to(torch, input_images)
        with torch.inference_mode():
            preds = birefnet(input_images)[-1].sigmoid().cpu()
        pred = preds[0].squeeze()
        pred_pil = transforms.ToPILImage()(pred)
        mask = pred_pil.resize(image_size)
        image.putalpha(mask)
        devicetorch.empty_cache(torch)
        return image

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_filename(prefix="no_bg"):
    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    return f"{prefix}_{timestamp}_{unique_id}.png"

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

    if USE_GPU:
        valid_images = []
        file_info = []
        for file in files:
            if file.filename == '' or not allowed_file(file.filename):
                continue
            try:
                image = Image.open(file.stream)
                image = ImageOps.exif_transpose(image)
                image = image.convert('RGB')
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
            t_start = time.time()
            processed_images = remove_background_batch(valid_images)
            torch.cuda.synchronize()
            t_inference = time.time() - t_start
            print(f"Batch inference: {len(valid_images)} images in {t_inference:.2f}s ({t_inference/len(valid_images):.2f}s/img)")
        except Exception as e:
            print(f"Batch inference error: {e}")
            torch.cuda.empty_cache()
            return jsonify({'error': 'Inference failed'}), 500

        save_futures = []
        results = []
        for i, processed in enumerate(processed_images):
            original_base = file_info[i]['original_base']
            filename = f"{original_base}.png"
            counter = 1
            while os.path.exists(os.path.join(OUTPUT_FOLDER, filename)):
                filename = f"{original_base}_{counter}.png"
                counter += 1
            output_path = os.path.join(OUTPUT_FOLDER, filename)
            save_futures.append(save_executor.submit(save_result_async, processed, output_path))
            results.append({
                'filename': filename,
                'url': f'/output/{filename}',
                'original_name': file_info[i]['original_name']
            })

        for future in save_futures:
            future.result()

        total_time = time.time() - t_start
        time_str = f"{total_time:.1f}s"
        print(f"Total request: {len(valid_images)} images in {total_time:.2f}s (inference: {t_inference:.2f}s, save: {total_time-t_inference:.2f}s)")
        return jsonify({'success': True, 'results': results, 'processing_time': time_str})

    else:
        results = []
        for file in files:
            if file.filename == '' or not allowed_file(file.filename):
                continue
            try:
                image = Image.open(file.stream)
                image = ImageOps.exif_transpose(image)
                image = image.convert('RGB')
                processed = remove_background(image)

                original_base = os.path.splitext(secure_filename(file.filename))[0]
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
                    'original_name': file.filename
                })
            except Exception as e:
                print(f"Error processing {file.filename}: {e}")

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 7860))

    if USE_GPU:
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
        print(f"  Preprocessing:  {'kornia (GPU)' if USE_KORNIA else 'torchvision (GPU)'}")
        print(f"  PNG Save:       compress_level=1 (fast)")
        print(f"  Warmup:         {warmup_time:.2f}s")
        print(f"  URL:            http://127.0.0.1:{port}")
        print("  The browser will open automatically...")
        print("=" * 50 + "\n")
    else:
        print("\n" + "=" * 50)
        print("  RMBG-2-Studio Flask Server")
        print("=" * 50)
        print(f"  Device:         {device}")
        print(f"  URL:            http://127.0.0.1:{port}")
        print("  The browser will open automatically...")
        print("=" * 50 + "\n")

    def open_browser():
        webbrowser.open(f"http://127.0.0.1:{port}")
    timer = threading.Timer(2, open_browser)
    timer.daemon = True
    timer.start()

    app.run(host='0.0.0.0', port=port, debug=False, threaded=USE_GPU)
