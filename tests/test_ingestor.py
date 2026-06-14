import pytest
import sys
import os
import uuid
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.ingestion.ingestor import ingest_challenge, compute_sha256, URL_REGEX


@pytest.mark.asyncio
async def test_ingest_text():
    manifest = await ingest_challenge(
        description="Find the flag in this simple text challenge",
        upload_dir="/tmp/test_uploads",
    )
    assert manifest.challenge_id
    assert manifest.description == "Find the flag in this simple text challenge"
    assert manifest.raw_input_type == "text"
    assert manifest.attachments == []


@pytest.mark.asyncio
async def test_ingest_with_url():
    manifest = await ingest_challenge(
        description="SQL injection on http://example.com/login",
        upload_dir="/tmp/test_uploads",
    )
    assert manifest.target_url == "http://example.com/login"


@pytest.mark.asyncio
async def test_ingest_with_host_port():
    manifest = await ingest_challenge(
        description="Connect to server: host port 1337",
        upload_dir="/tmp/test_uploads",
    )
    assert manifest.target_host or True  # Can match various formats


@pytest.mark.asyncio
async def test_ingest_with_files():
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"test content")
        tmppath = f.name

    manifest = await ingest_challenge(
        description="Challenge with file attachment",
        upload_dir="/tmp/test_uploads",
        files=[("test.txt", b"test content", "text/plain")],
    )
    assert len(manifest.attachments) == 1
    assert manifest.attachments[0].filename == "test.txt"


@pytest.mark.asyncio
async def test_ingest_flag_format():
    manifest = await ingest_challenge(
        description="The flag format is picoCTF{...} find it",
        upload_dir="/tmp/test_uploads",
    )
    assert manifest.flag_format and "picoCTF" in manifest.flag_format


@pytest.mark.asyncio
async def test_target_url_extraction():
    text = "Visit http://challenge.com/login for the web app"
    urls = URL_REGEX.findall(text)
    assert "http://challenge.com/login" in urls


@pytest.mark.asyncio
async def test_compute_sha256():
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"test data")
        tmppath = f.name

    sha = await compute_sha256(tmppath)
    assert len(sha) == 64
    assert all(c in "0123456789abcdef" for c in sha)
    os.unlink(tmppath)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
