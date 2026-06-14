import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.tools.crypto.encoding_detector import (
    decode_base64, decode_base32, decode_hex, decode_rot13,
    decode_atbash, decode_binary, decode_morse, decode_url_encoded,
    score_text, EncodingDetectorTool
)


class TestBase64:
    def test_basic(self):
        assert decode_base64("aGVsbG8gd29ybGQ=") == "hello world"
        assert "hello" in decode_base64("aGVsbG8=")

    def test_padding(self):
        assert decode_base64("YQ==") == "a"

    def test_invalid(self):
        assert decode_base64("!!!") is None


class TestBase32:
    def test_basic(self):
        assert decode_base32("NBSWY3DP") == "hello"

    def test_invalid(self):
        assert decode_base32("!!!") is None


class TestHex:
    def test_basic(self):
        assert decode_hex("68656c6c6f") == "hello"

    def test_odd_length(self):
        assert decode_hex("686") is None


class TestRot13:
    def test_basic(self):
        assert decode_rot13("uryyb") == "hello"

    def test_mixed_case(self):
        assert decode_rot13("Uryyb Jbeyq") == "Hello World"


class TestAtbash:
    def test_basic(self):
        assert decode_atbash("svool") == "hello"

    def test_sentence(self):
        assert decode_atbash("Gsv") == "The"


class TestBinary:
    def test_basic(self):
        result = decode_binary("01101000 01100101 01101100 01101100 01101111")
        assert result == "hello"

    def test_invalid(self):
        assert decode_binary("not binary") is None


class TestMorse:
    def test_basic(self):
        assert decode_morse(".... . .-.. .-.. ---") == "HELLO"

    def test_words(self):
        assert decode_morse(".... . .-.. .-.. --- / .-- --- .-. .-.. -..") == "HELLO WORLD"


class TestURLEncoding:
    def test_basic(self):
        assert decode_url_encoded("hello%20world") == "hello world"

    def test_special_chars(self):
        assert decode_url_encoded("%21%40%23") == "!@#"


class TestScoreText:
    def test_english(self):
        score = score_text("hello world this is english text")
        assert score > 0.3

    def test_gibberish(self):
        score = score_text("zxq jv fwbp mqk")
        assert score < 0.2


class TestEncodingDetectorTool:
    @pytest.mark.asyncio
    async def test_detect_base64(self):
        tool = EncodingDetectorTool()
        result = await tool.run(text="aGVsbG8gd29ybGQ=")
        assert result["encoding"] in ("base64", "base64_urlsafe")

    @pytest.mark.asyncio
    async def test_detect_hex(self):
        tool = EncodingDetectorTool()
        result = await tool.run(text="68656c6c6f")
        assert result["encoding"] == "hex"

    @pytest.mark.asyncio
    async def test_no_encoding(self):
        tool = EncodingDetectorTool()
        result = await tool.run(text="this is plain text")
        assert result["encoding"] == "unknown"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
