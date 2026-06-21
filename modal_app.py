import os
import modal

# Define the local directory of the Flask app
LOCAL_APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app")

# Pre-download the model at image build time to avoid cold start latency
def download_model():
    from transformers import AutoModelForImageSegmentation
    print("Pre-downloading BRIA-RMBG-2.0 model...")
    # This downloads and caches the model into the container image filesystem (/root/.cache/huggingface)
    AutoModelForImageSegmentation.from_pretrained(
        "cocktailpeanut/rm", 
        trust_remote_code=True
    )
    print("BRIA-RMBG-2.0 model successfully cached.")

# Create the Modal image with all dependencies
image = (
    modal.Image.debian_slim()
    # Install system library dependencies needed by OpenCV (cv2)
    .apt_install("libgl1", "libglib2.0-0")
    # Install Python packages
    .pip_install(
        "torch",
        "torchvision",
        "transformers>=4.39.1,<4.50.0",
        "timm",
        "kornia",
        "devicetorch",
        "pillow",
        "opencv-python-headless",
        "numpy",
        "scikit-image",
        "flask>=3.0.0",
        "werkzeug",
        "fsspec",
        "huggingface-hub",
        "pydantic",
    )
    # Run the model pre-download function so it is baked into the image
    .run_function(download_model)
    # Mount the local app directory to /root/app inside the container
    .add_local_dir(LOCAL_APP_DIR, "/root/app")
)

# Define the Modal application
app = modal.App("rmbg-2-studio")

# Expose the Flask WSGI application using a T4 GPU
@app.function(
    gpu="t4",
    image=image,
    # Optional: Keep one container warm to prevent cold starts if desired
    # keep_warm=1,
)
@modal.wsgi_app()
def flask_app():
    import os
    import sys
    
    # Change working directory so Flask locates templates and static files correctly
    os.chdir("/root/app")
    sys.path.append("/root/app")
    
    # Import the app from flask_app.py
    from flask_app import app as web_app
    return web_app
