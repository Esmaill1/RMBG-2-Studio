FROM python:3.10-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create app user and directory
RUN useradd -m -u 1000 user
WORKDIR /app

# Copy requirements first for caching
COPY app/requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ .

# Create output directory
RUN mkdir -p /app/output_images && chown -R user:user /app

# Switch to non-root user
USER user

# Expose port
EXPOSE 7860

# Run the app
CMD ["python", "flask_app.py"]
