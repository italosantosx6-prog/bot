FROM python:3.11-slim
WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project
COPY . /app

# Install deps
RUN python -m pip install --upgrade pip setuptools
RUN pip install -r requirements.txt

ENV PYTHONUNBUFFERED=1

# Default command (not used by compose which specifies per-service commands)
CMD ["python", "bot.py"]
