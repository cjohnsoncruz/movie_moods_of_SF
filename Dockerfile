# Use Debian Bookworm slim for up-to-date security patches
FROM python:3.12-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install and patch system dependencies (add CMake and pkg-config for shapely build)
RUN apt-get update \
    && apt-get dist-upgrade -y \
    && apt-get install -y --no-install-recommends \
       build-essential python3-dev libgeos-dev cmake pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY src/requirements_movie_sf.txt /app/
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements_movie_sf.txt

# Copy the rest of the code
COPY src /app/src

# Create a non-root user and switch to it
RUN groupadd --system app && useradd --system --gid app app
RUN mkdir -p /app/data && chown -R app:app /app/data
USER app

# Expose Dash's port
EXPOSE 8050

# Run the app
CMD ["python", "src/app.py"]
