# syntax=docker/dockerfile:1.7
FROM python:3.11-slim-bookworm

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlmap \
    gobuster \
    ffuf \
    binwalk \
    libimage-exiftool-perl \
    steghide \
    tshark \
    binutils \
    foremost \
    hashcat \
    john \
    curl \
    wget \
    git \
    ruby \
    ruby-dev \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

RUN gem install zsteg --no-document

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install pip --upgrade

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
    prompt-toolkit

COPY . .

RUN mkdir -p /app/uploads /app/data

ENV CTFAGENT_DOCKER=1
ENV CTFAGENT_ENV_FILE=/app/data/.env

CMD ["python", "run.py", "--docker"]
