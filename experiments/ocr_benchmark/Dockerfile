FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-ron tesseract-ocr-rus && rm -rf /var/lib/apt/lists/*
WORKDIR /bench
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ocrbench ./ocrbench
COPY configs ./configs
ENV HOME=/tmp HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
CMD ["python", "-m", "ocrbench", "--help"]
