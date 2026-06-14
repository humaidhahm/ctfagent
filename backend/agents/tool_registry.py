from typing import Optional
from backend.tools.base import BaseTool

_TOOL_CLASSES: dict[str, type[BaseTool]] = {}


def _ensure_loaded():
    if _TOOL_CLASSES:
        return
    from backend.tools.web.sqlmap import SQLMapTool
    from backend.tools.web.gobuster import GobusterTool
    from backend.tools.web.ffuf import FfufTool
    from backend.tools.web.curl_probe import CurlProbeTool
    from backend.tools.crypto.encoding_detector import EncodingDetectorTool
    from backend.tools.crypto.cipher_cracker import CipherCrackerTool
    from backend.tools.crypto.rsa_solver import RSASolverTool
    from backend.tools.forensics.binwalk_tool import BinwalkTool
    from backend.tools.forensics.exiftool_tool import ExifToolTool
    from backend.tools.forensics.steghide_tool import SteghideTool
    from backend.tools.forensics.zsteg_tool import ZstegTool
    from backend.tools.forensics.tshark_tool import TsharkTool
    from backend.tools.forensics.ocr_tool import OCRTool
    from backend.tools.forensics.file_decoder import FileDecoderTool
    from backend.tools.pwn.checksec_tool import ChecksecTool
    from backend.tools.pwn.strings_tool import StringsTool as PwnStringsTool
    from backend.tools.pwn.pwntools_runner import PwntoolsRunnerTool
    from backend.tools.pwn.ropgadget_tool import ROPgadgetTool
    from backend.tools.pwn.remote_connect import RemoteConnectTool
    from backend.tools.pwn.heartbleed_tool import HeartbleedTool
    from backend.tools.pwn.session_read import SessionReadTool
    from backend.tools.re.strings_tool import REStringsTool
    from backend.tools.re.radare2_tool import Radare2Tool
    from backend.tools.general.download_file import DownloadFileTool
    from backend.tools.general.file_reader import FileReaderTool
    from backend.tools.general.binary_calc import BinaryCalcTool
    from backend.tools.osint.password_profiler import PasswordProfilerTool
    from backend.tools.osint.cupp_tool import CuppTool
    _TOOL_CLASSES.update({
        "sqlmap": SQLMapTool,
        "gobuster": GobusterTool,
        "ffuf": FfufTool,
        "curl_probe": CurlProbeTool,
        "encoding_detector": EncodingDetectorTool,
        "cipher_cracker": CipherCrackerTool,
        "rsa_solver": RSASolverTool,
        "binwalk_tool": BinwalkTool,
        "exiftool_tool": ExifToolTool,
        "steghide_tool": SteghideTool,
        "zsteg_tool": ZstegTool,
        "tshark_tool": TsharkTool,
        "ocr_tool": OCRTool,
        "checksec_tool": ChecksecTool,
        "strings_tool": PwnStringsTool,
        "pwntools_runner": PwntoolsRunnerTool,
        "ropgadget_tool": ROPgadgetTool,
        "remote_connect": RemoteConnectTool,
        "session_read": SessionReadTool,
        "heartbleed_tool": HeartbleedTool,
        "re_strings_tool": REStringsTool,
        "radare2_tool": Radare2Tool,
        "download_file": DownloadFileTool,
        "file_reader": FileReaderTool,
        "binary_calc": BinaryCalcTool,
        "file_decoder": FileDecoderTool,
        "password_profiler": PasswordProfilerTool,
        "cupp": CuppTool,
    })


_TOOL_CACHE: dict[str, BaseTool] = {}


def get_tool(name: str) -> Optional[BaseTool]:
    _ensure_loaded()
    cls = _TOOL_CLASSES.get(name)
    if cls is None:
        return None
    if name not in _TOOL_CACHE:
        _TOOL_CACHE[name] = cls()
    return _TOOL_CACHE[name]


def list_tools() -> list[str]:
    _ensure_loaded()
    return list(_TOOL_CLASSES.keys())
