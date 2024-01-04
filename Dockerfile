ARG IMAGE_TAG=2.1.0-cuda11.8-cudnn8-runtime

FROM pytorch/pytorch:${IMAGE_TAG}

VOLUME /root/.cache

WORKDIR /app

COPY ./scripts /app/scripts

ENV DEBIAN_FRONTEND noninteractive
RUN apt-get update \
  && apt-get install apt-transport-https software-properties-common lsb-release -y \
  && add-apt-repository ppa:alex-p/tesseract-ocr-devel \
  && scripts/install/ghostscript_install.sh \
  && apt-get install -y $(cat scripts/install/apt-requirements.txt) \
  && rm -rf /var/lib/apt/lists/*

COPY ./pyproject.toml ./poetry.lock ./

RUN pip install pip==23.3.1 \
  && pip install poetry==1.5.0 \
  && poetry config virtualenvs.create false \
  && poetry install --no-dev --no-interaction --no-ansi --no-root

COPY . .


ARG TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata
ENV TESSDATA_PREFIX=${TESSDATA_PREFIX}

# Test to make sure the TESSDATA_PREFIX is set correctly
RUN find / -name tessdata 2> /dev/null | grep "${TESSDATA_PREFIX}"

