FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first so code changes don't invalidate this layer.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

COPY db ./db
COPY sql ./sql

# Raw AEMO downloads are cached here; mount a volume to keep them between runs.
VOLUME ["/app/data"]

RUN useradd --create-home nemsa && mkdir -p /app/data && chown nemsa /app/data
USER nemsa

ENTRYPOINT ["nemsa"]
CMD ["--help"]
