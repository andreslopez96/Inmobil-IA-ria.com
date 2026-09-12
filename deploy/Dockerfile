FROM python:3.11.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    INMOBIL_PROJECT_ROOT=/app

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
       gcc \
       texlive-fonts-recommended \
       texlive-latex-extra \
       texlive-latex-recommended \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.lock pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir -r requirements.lock \
    && python -m pip install --no-cache-dir --no-deps --no-build-isolation .

COPY config ./config
COPY assets ./assets

CMD ["python", "-m", "inmobil_iaria", "doctor"]
