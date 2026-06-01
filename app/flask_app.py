"""
Flask Web Application for RMBG-2-Studio
Background Removal and Replacement using BRIA-RMBG-2.0
"""

import os
import sys
import uuid
import warnings
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from io import BytesIO

# Third-party imports
import torch
import numpy as np
from PIL import Image, ImageEnhance
from flask import Flask, request, jsonify, send_from_directory, render_template, send_file
from torchvision import transforms
from werkzeug.utils import secure_filename

# ML imports
import devicetorch
from transformers import AutoModelForImageSegmentation

# Configure warnings
warnings.filterwarnings('ignore', category=FutureWarning, module='timm')

# Initialize Flask app
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload

# Output folder - allow override via environment variable
OUTPUT_FOLDER = os.environ.get('OUTPUT_FOLDER', None)
if OUTPUT_FOLDER is None:
    if os.path.exists('/app'):
        OUTPUT_FOLDER = '/app/output_images'
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        OUTPUT_FOLDER = os.path.join(os.path.dirname(script_dir), 'output_images')

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Cleanup Configuration
CLEANUP_AGE_SECONDS = 3 * 60 * 60  # 3 hours
CLEANUP_INTERVAL_SECONDS = 30 * 60 # Check every 30 minutes

def cleanup_job():
    """Background thread to clean old files"""
    import time
    
    
    while True:
        try:
            now = time.time()
            if os.path.exists(OUTPUT_FOLDER):
                for filename in os.listdir(OUTPUT_FOLDER):
                    file_path = os.path.join(OUTPUT_FOLDER, filename)
                    # Check if file and older than limit
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

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_job, daemon=True)
cleanup_thread.start()

# Allowed extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# ============== Model Loading ==============
MODEL_NAME = "cocktailpeanut/rm"

def load_model():
    print(f"Loading {MODEL_NAME} model...")
    model = AutoModelForImageSegmentation.from_pretrained(
        MODEL_NAME, trust_remote_code=True
    )
    print("Model loaded successfully.")
    return model

print("Loading BRIA-RMBG-2.0 model...")

device = devicetorch.get(torch)
if device == 'cpu':
    cpu_count = os.cpu_count() or 1
    torch.set_num_threads(max(1, cpu_count))
    print(f"Optimized for CPU: Using {torch.get_num_threads()} threads")

birefnet = load_model()
birefnet = devicetorch.to(torch, birefnet)
birefnet.eval()

# CPU Optimization: Dynamic Quantization
if device == 'cpu':
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


# ============== Utility Functions ==============
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_filename(prefix="no_bg"):
    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    return f"{prefix}_{timestamp}_{unique_id}.png"


def remove_background(image):
    """Remove background from PIL Image using BRIA-RMBG-2.0"""
    image_size = image.size
    input_images = transform_image(image).unsqueeze(0)
    input_images = devicetorch.to(torch, input_images)
    
    # Use inference_mode for faster CPU inference
    with torch.inference_mode():
        preds = birefnet(input_images)[-1].sigmoid().cpu()
    
    pred = preds[0].squeeze()
    pred_pil = transforms.ToPILImage()(pred)
    mask = pred_pil.resize(image_size)
    image.putalpha(mask)
    devicetorch.empty_cache(torch)
    return image




# ============== API Routes ==============
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/remove-bg', methods=['POST'])
def api_remove_bg():
    """API endpoint to remove background from uploaded images (Sequential Processing)"""
    if 'images' not in request.files:
        return jsonify({'error': 'No image files provided'}), 400
    
    files = request.files.getlist('images')
    if not files:
        return jsonify({'error': 'No files selected'}), 400
    
    results = []
    
    for file in files:
        if file.filename == '' or not allowed_file(file.filename):
            continue
            
        try:
            # Load and process image
            image = Image.open(file.stream).convert('RGB')
            processed = remove_background(image)
            
            # Save result
            original_base = os.path.splitext(secure_filename(file.filename))[0]
            filename = f"{original_base}.png"
            
            # Handle duplicates
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
            # Continue processing — displaying errors isn't helpful for partial results
            
    return jsonify({
        'success': True,
        'results': results
    })


import zipfile

@app.route('/api/zip', methods=['POST'])
def api_download_zip():
    """Create and return a zip file of specific images"""
    data = request.get_json()
    if not data or 'filenames' not in data:
        return jsonify({'error': 'No filenames provided'}), 400
        
    filenames = data['filenames']
    if not filenames:
        return jsonify({'error': 'List is empty'}), 400

    # Create in-memory zip
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
    """Delete all files in the output directory"""
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
    """Serve processed images"""
    return send_from_directory(OUTPUT_FOLDER, filename)


# ============== Run Server ==============
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 7860))
    print("\n" + "="*50)
    print("  RMBG-2-Studio Flask Server")
    print("="*50)
    print(f"  URL: http://127.0.0.1:{port}")
    print("  The browser will open automatically...")
    print("="*50 + "\n")
    
    def open_browser():
        webbrowser.open(f"http://127.0.0.1:{port}")
    timer = threading.Timer(2, open_browser)
    timer.daemon = True
    timer.start()
    
    app.run(host='0.0.0.0', port=port, debug=False)

