FROM python:3.11-slim

# Install poetry dependency
RUN pip install poetry==2.1.1
# Install OpenCV dependencies
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    ffmpeg libsm6 libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Define environment variables for poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

# Install packages
COPY pyproject.toml poetry.lock ./
RUN touch README.md
RUN poetry install --no-root && rm -rf $POETRY_CACHE_DIR

# Copy app files
COPY pbn ./pbn

# Expose port 1000
EXPOSE 1000

WORKDIR /app/pbn

ENTRYPOINT ["poetry", "run", "python", "app.py"]