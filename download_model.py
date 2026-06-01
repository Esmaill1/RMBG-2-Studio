from transformers import AutoModelForImageSegmentation

print('Pre-downloading model to HuggingFace cache...')
model = AutoModelForImageSegmentation.from_pretrained('briaai/RMBG-2.0', trust_remote_code=True)
print('Model downloaded and cached! Future runs will load offline.')