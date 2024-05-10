FROM python:3.9



# Set the working directory
WORKDIR /app

# set environment variables for poetry
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
ENV LANGUAGE=C.UTF-8

# Set the device to GPU
ENV TORCH_DEVICE=cuda



# Install system requirements
RUN apt-get update && \
    apt-get install -y git curl wget unzip apt-transport-https \
    ghostscript lsb-release

# Clone the marker repository
RUN git clone https://github.com/VikParuchuri/marker.git .

# create a directory for the app and .cache
RUN mkdir -p /app/.cache

# Set the cache directory
ENV CACHE_DIR=/app/.cache

# Install tesseract 5 (optional)
RUN echo "deb https://notesalexp.org/tesseract-ocr5/$(lsb_release -cs)/ $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/notesalexp.list > /dev/null && \
    apt-get update -oAcquire::AllowInsecureRepositories=true && \
    apt-get install -y --allow-unauthenticated notesalexp-keyring && \
    apt-get update && \
    apt-get install -y --allow-unauthenticated tesseract-ocr libtesseract-dev \
    libmagic1 ocrmypdf tesseract-ocr-eng tesseract-ocr-deu \
    tesseract-ocr-por tesseract-ocr-spa tesseract-ocr-rus \
    tesseract-ocr-fra tesseract-ocr-chi-sim tesseract-ocr-jpn \
    tesseract-ocr-kor tesseract-ocr-hin

# Upgrade pip, setuptools, and wheel
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir --upgrade setuptools wheel

# Install poetry
RUN pip install --no-cache-dir poetry


# Disable virtual env creation by poetry (not needed in Docker)
# and install dependencies based on the lock file without updating
RUN poetry config virtualenvs.create false \
  && poetry lock --no-update \
  && poetry install --no-dev  # Exclude development dependencies

RUN poetry remove torch

RUN mkdir -p /app/static

# Install torch with GPU support
RUN pip install torch torchvision torchaudio

# Set the tesseract data folder path for Ubuntu 22.04 with tesseract 5
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

# Copy the entrypoint script
COPY entrypoint.sh /entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Set the default command
CMD ["bash"]