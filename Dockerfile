# syntax=docker/dockerfile:1

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Runtime libs for Pillow/PyMuPDF on slim image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       fonts-dejavu-core \
       libjpeg62-turbo \
       zlib1g \
       libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (better layer caching).
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /app/requirements.txt

# Copy project and install package in editable-compatible way.
COPY pyproject.toml README.md /app/
COPY src /app/src
RUN pip install .

# Runtime directories (can be mounted by compose/server).
RUN mkdir -p /data/outputs /data/tmp

EXPOSE 8000

CMD ["uvicorn", "barcode_tool.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
