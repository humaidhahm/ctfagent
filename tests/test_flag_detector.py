import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.core.flag_detector import regex_scan, validate_flag


class TestRegexScan:
    def test_picoctf_flag(self):
        text = "The flag is picoCTF{th1s_1s_4_fl4g}"
        result = regex_scan(text)
        assert "picoCTF{th1s_1s_4_fl4g}" in result

    def test_ctf_flag(self):
        text = "Flag: CTF{simple_flag_here}"
        result = regex_scan(text)
        assert "CTF{simple_flag_here}" in result

    def test_flag_format(self):
        text = "flag{this_is_a_flag}"
        result = regex_scan(text)
        assert "flag{this_is_a_flag}" in result

    def test_htb_flag(self):
        text = "HTB{htb_flag_format}"
        result = regex_scan(text)
        assert "HTB{htb_flag_format}" in result

    def test_no_flag(self):
        text = "This text has no flag pattern in it"
        result = regex_scan(text)
        assert result == []

    def test_multiple_flags(self):
        text = "First: picoCTF{flag1} Second: CTF{flag2}"
        result = regex_scan(text)
        assert len(result) == 2

    def test_flag_with_underscores(self):
        text = "picoCTF{th1s_1s_a_l0ng_3r_fl4g_w1th_numb3rs}"
        result = regex_scan(text)
        assert len(result) == 1

    def test_partial_bracket(self):
        text = "flag{missing close bracket"
        result = regex_scan(text)
        assert result == []


class TestValidateFlag:
    def test_valid_picoctf(self):
        assert validate_flag("picoCTF{test_flag}")

    def test_valid_ctf(self):
        assert validate_flag("CTF{test}")

    def test_empty(self):
        assert not validate_flag("")

    def test_no_brackets(self):
        assert not validate_flag("just_a_string")

    def test_no_closing(self):
        assert not validate_flag("CTF{no_close")

    def test_with_format_match(self):
        assert validate_flag("picoCTF{test}", "picoCTF{...}")

    def test_with_format_mismatch(self):
        assert not validate_flag("CTF{test}", "picoCTF{...}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
