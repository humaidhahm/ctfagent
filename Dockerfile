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

RUN pip install --no-cache-dir pip --upgrade

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir \
    prompt-toolkit

COPY . .

RUN mkdir -p /app/uploads /app/data

ENV CTFAGENT_DOCKER=1
ENV CTFAGENT_ENV_FILE=/app/data/.env

CMD ["python", "run.py", "--docker"]
