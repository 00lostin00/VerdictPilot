FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 runner

WORKDIR /app
COPY runner.py /app/runner.py
RUN chmod 0555 /app/runner.py

USER runner
ENTRYPOINT ["python", "/app/runner.py"]
