import os
import sys

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'model')

if os.path.exists(os.path.join(MODEL_DIR, 'config.json')):
    print('Model already saved locally, skipping...')
    sys.exit(0)

print('Downloading model...')
os.makedirs(MODEL_DIR, exist_ok=True)

from transformers import AutoModelForImageSegmentation
model = AutoModelForImageSegmentation.from_pretrained('cocktailpeanut/rm', trust_remote_code=True)
model.save_pretrained(MODEL_DIR)
print('Model downloaded and saved!')