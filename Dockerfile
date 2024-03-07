ARG BASE_IMAGE=python:3.10-bookworm
FROM ${BASE_IMAGE}

WORKDIR /app

ARG PIP_VERSION=24.0
ARG POETRY_VERSION=1.7.1
ARG GS_VERSION=10.02.1
ARG TORCH_VERSION=2.1.2

ENV DEBIAN_FRONTEND=noninteractive
ENV GS_URL=https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10021/ghostscript-${GS_VERSION}.tar.gz

RUN apt-get update \
  && apt-get -y install apt-transport-https lsb-release wget gnupg2 \
  && wget -O - https://notesalexp.org/debian/alexp_key.asc | apt-key add - \
  && echo "deb https://notesalexp.org/tesseract-ocr5/$(lsb_release -cs)/ $(lsb_release -cs) main" > /etc/apt/sources.list.d/notesalexp.list \
  && apt-get update \
  && apt-get install -y \
    build-essential \
    cmake \
    libmagic1 \
    libtesseract-dev \
    ocrmypdf \
    python3-dev \
    python3-pip \
    tesseract-ocr \
    tesseract-ocr-deu \
    tesseract-ocr-eng \
    tesseract-ocr-fra \
    tesseract-ocr-por \
    tesseract-ocr-rus \
    tesseract-ocr-spa \
  && rm -rf /var/lib/apt/lists/*

RUN wget -q ${GS_URL} \
  && tar -xvf ghostscript-${GS_VERSION}.tar.gz \
  && cd ghostscript-${GS_VERSION} \
  && ./configure \
  && make -j $(nproc) \
  && make install \
  && cd .. \
  && rm -rf ghostscript-${GS_VERSION} ghostscript-${GS_VERSION}.tar.gz

RUN pip install pip==${PIP_VERSION} \
  && pip install poetry==${POETRY_VERSION} \
  && poetry config virtualenvs.create false

# If BASE_IMAGE is pytorch/pytorch:tag then pytorch will be installed with cuda support.
# If pytorch is not installed, install the cpu version.
RUN python -c "import torch" \
  || pip install --extra-index-url https://download.pytorch.org/whl/cpu/ \
    torch==${TORCH_VERSION} \
    torchvision \
    torchaudio==${TORCH_VERSION}

COPY ./pyproject.toml ./poetry.lock ./

RUN poetry install --no-dev --no-interaction --no-ansi --no-root

ARG TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata
ENV TESSDATA_PREFIX=${TESSDATA_PREFIX}

# Test to make sure the TESSDATA_PREFIX is set correctly
RUN find / -name tessdata 2> /dev/null | grep "${TESSDATA_PREFIX}"

COPY . .
