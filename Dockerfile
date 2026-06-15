FROM python:3.14-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlmap \
    gobuster \
    ffuf \
    binwalk \
    exiftool \
    steghide \
    zsteg \
    tshark \
    binutils \
    foremost \
    hashcat \
    john \
    curl \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pip --upgrade

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir \
    prompt-toolkit

COPY . .

RUN mkdir -p /app/uploads

CMD ["python", "-m", "cli.client"]
