FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /usr/sbin/nologin appuser
COPY pyproject.toml README.md /app/
RUN pip install --no-cache-dir -e .
COPY app /app/app
COPY ttn_bot /app/ttn_bot
COPY config /app/config
COPY assets /app/assets
COPY data /app/data
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini

USER appuser
CMD ["python", "-m", "app.main"]
