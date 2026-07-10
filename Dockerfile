FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY config ./config
RUN pip install --no-cache-dir .

VOLUME ["/app/reports", "/app/data"]
ENTRYPOINT ["repo-courier"]
CMD ["--config", "config/config.yaml"]
