"""OCR tool — extracts text from images for steganography/image-based challenges.
Wraps tesseract with preprocessing. Supports interactive user-assisted OCR."""

import subprocess
import tempfile
import os
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from backend.tools.base import BaseTool
from loguru import logger

_console = Console()


class OCRTool(BaseTool):
    name = "ocr_tool"
    description = "Extract text from images using OCR (tesseract). Good for image-based challenges with visible text/flags."

    async def run(self, filepath: str = "", lang: str = "eng") -> dict:
        if not filepath:
            return {"success": False, "output": "", "error": "No filepath provided", "command": "ocr_tool"}

        resolved = filepath
        if not Path(resolved).is_absolute():
            for base in [os.getcwd(), "uploads"]:
                p = Path(base) / resolved
                if p.exists():
                    resolved = str(p)
                    break

        is_image = Path(resolved).exists() and Path(resolved).suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp")

        if is_image:
            _console.print()
            _console.print(Panel(
                f"[bold #D29922]Image file:[/bold #D29922] [#00E5FF]{resolved}[/#00E5FF]\n\n"
                f"[#9CA3AF]Options:[/#9CA3AF]\n"
                f"  [bold]v[/bold] — View image with [#3FB950]xdg-open[/#3FB950] then [#D29922]type text manually[/#D29922]\n"
                f"  [bold]v+o[/bold] — View image then [#3FB950]run OCR automatically[/#3FB950]\n"
                f"  [bold]o[/bold] — [#3FB950]Run OCR[/#3FB950] directly (skip viewer)",
                border_style="#D29922",
                title="[bold]Image OCR — Manual Assistance[/bold]",
            ))
            choice = input("  Choice [v/v+o/o]: ").strip().lower()

            if choice in ("v", "v+o"):
                _console.print(f"[#9CA3AF]Opening [#00E5FF]{resolved}[/#00E5FF] with xdg-open...[/#9CA3AF]")
                subprocess.Popen(["xdg-open", resolved], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if choice == "v":
                _console.print("[#D29922]Look at the image, then enter the text you see:[/#D29922]")
                user_text = input("  Text from image: ").strip()
                if user_text:
                    _console.print("[#3FB950]✓ Manual text captured[/#3FB950]")
                    return {
                        "success": True,
                        "output": f"{user_text}",
                        "error": "",
                        "command": f"ocr_tool --filepath {filepath} --lang {lang} [manual input]",
                    }

            if choice == "v+o":
                _console.print("[#9CA3AF]Press Enter after you've viewed the image to continue with OCR...[/#9CA3AF]")
                input()

        text = ocr_image(resolved, lang)
        if not text.strip():
            text = ocr_with_preprocessing(resolved)
        success = bool(text.strip()) and "File not found" not in text and "tesseract not installed" not in text
        return {
            "success": success,
            "output": text[:2000] if success else text,
            "error": "" if success else text,
            "command": f"ocr_tool --filepath {filepath} --lang {lang}",
        }


def ocr_image(image_path: str, lang: str = "eng") -> str:
    """Extract text from an image using tesseract OCR."""
    if not Path(image_path).exists():
        return f"File not found: {image_path}"

    # Check if tesseract is available
    try:
        subprocess.run(["tesseract", "--version"], capture_output=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "tesseract not installed. Run: sudo apt install tesseract-ocr"

    try:
        result = subprocess.run(
            ["tesseract", image_path, "stdout", "-l", lang, "--psm", "6"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return f"OCR failed: {result.stderr[:200]}"
    except Exception as e:
        return f"OCR error: {e}"


def ocr_with_preprocessing(image_path: str) -> str:
    """Apply ImageMagick preprocessing before OCR for better results."""
    try:
        subprocess.run(["convert", "--version"], capture_output=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ocr_image(image_path)

    with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
        tmp_path = tmp.name
        cmd = [
            "convert", image_path,
            "-colorspace", "gray",
            "-contrast-stretch", "5%",
            "-threshold", "50%",
            "-deskew", "40%",
            tmp_path,
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=30)
            if Path(tmp_path).stat().st_size == 0:
                return ocr_image(image_path)
            text = ocr_image(tmp_path)
            if not text.strip():
                cmd_neg = [
                    "convert", image_path,
                    "-colorspace", "gray",
                    "-negate",
                    "-threshold", "50%",
                    "-deskew", "40%",
                    tmp_path,
                ]
                subprocess.run(cmd_neg, capture_output=True, timeout=30)
                if Path(tmp_path).stat().st_size == 0:
                    return ocr_image(image_path)
                text = ocr_image(tmp_path)
            return text
        except Exception:
            return ocr_image(image_path)
