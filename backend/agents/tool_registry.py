from importlib import import_module
from typing import Optional

from backend.tools.base import BaseTool


_TOOL_LOADERS: dict[str, tuple[str, str]] = {
    "sqlmap": ("backend.tools.web.sqlmap", "SQLMapTool"),
    "gobuster": ("backend.tools.web.gobuster", "GobusterTool"),
    "ffuf": ("backend.tools.web.ffuf", "FfufTool"),
    "curl_probe": ("backend.tools.web.curl_probe", "CurlProbeTool"),
    "encoding_detector": ("backend.tools.crypto.encoding_detector", "EncodingDetectorTool"),
    "cipher_cracker": ("backend.tools.crypto.cipher_cracker", "CipherCrackerTool"),
    "rsa_solver": ("backend.tools.crypto.rsa_solver", "RSASolverTool"),
    "binwalk_tool": ("backend.tools.forensics.binwalk_tool", "BinwalkTool"),
    "exiftool_tool": ("backend.tools.forensics.exiftool_tool", "ExifToolTool"),
    "steghide_tool": ("backend.tools.forensics.steghide_tool", "SteghideTool"),
    "zsteg_tool": ("backend.tools.forensics.zsteg_tool", "ZstegTool"),
    "tshark_tool": ("backend.tools.forensics.tshark_tool", "TsharkTool"),
    "ocr_tool": ("backend.tools.forensics.ocr_tool", "OCRTool"),
    "checksec_tool": ("backend.tools.pwn.checksec_tool", "ChecksecTool"),
    "strings_tool": ("backend.tools.pwn.strings_tool", "StringsTool"),
    "pwntools_runner": ("backend.tools.pwn.pwntools_runner", "PwntoolsRunnerTool"),
    "ropgadget_tool": ("backend.tools.pwn.ropgadget_tool", "ROPgadgetTool"),
    "remote_connect": ("backend.tools.pwn.remote_connect", "RemoteConnectTool"),
    "session_read": ("backend.tools.pwn.session_read", "SessionReadTool"),
    "heartbleed_tool": ("backend.tools.pwn.heartbleed_tool", "HeartbleedTool"),
    "re_strings_tool": ("backend.tools.re.strings_tool", "REStringsTool"),
    "radare2_tool": ("backend.tools.re.radare2_tool", "Radare2Tool"),
    "download_file": ("backend.tools.general.download_file", "DownloadFileTool"),
    "file_reader": ("backend.tools.general.file_reader", "FileReaderTool"),
    "binary_calc": ("backend.tools.general.binary_calc", "BinaryCalcTool"),
    "sqlite_query": ("backend.tools.general.sqlite_query", "SQLiteQueryTool"),
    "file_decoder": ("backend.tools.forensics.file_decoder", "FileDecoderTool"),
    "password_profiler": ("backend.tools.osint.password_profiler", "PasswordProfilerTool"),
    "cupp": ("backend.tools.osint.cupp_tool", "CuppTool"),
}

_TOOL_CLASSES: dict[str, type[BaseTool]] = {}
_TOOL_CACHE: dict[str, BaseTool] = {}


def _load_tool_class(name: str) -> Optional[type[BaseTool]]:
    if name in _TOOL_CLASSES:
        return _TOOL_CLASSES[name]

    loader = _TOOL_LOADERS.get(name)
    if loader is None:
        return None

    module_name, class_name = loader
    module = import_module(module_name)
    cls = getattr(module, class_name)
    _TOOL_CLASSES[name] = cls
    return cls


def get_tool(name: str) -> Optional[BaseTool]:
    cls = _load_tool_class(name)
    if cls is None:
        return None
    if name not in _TOOL_CACHE:
        _TOOL_CACHE[name] = cls()
    return _TOOL_CACHE[name]


def list_tools() -> list[str]:
    return list(_TOOL_LOADERS.keys())
