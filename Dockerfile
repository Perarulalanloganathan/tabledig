# tabledig with OCR support.  Build:  docker build -t tabledig .
# Run:    docker run --rm -v "$PWD":/data tabledig extract /data/report.pdf --attr Revenue
FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir ".[ocr,excel,mcp]"
WORKDIR /data
ENTRYPOINT ["tabledig"]
