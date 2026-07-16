import httpx
from backend.tools.base import BaseTool
from loguru import logger


def _prepare_headers(headers: dict | None, data: str | None) -> dict:
    headers = headers or {}
    if data and isinstance(data, str) and "=" in data:
        has_content_type = any(k.lower() == "content-type" for k in headers)
        if not has_content_type:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
    return headers


class CurlProbeTool(BaseTool):
    name = "curl_probe"
    description = "Send HTTP requests to probe endpoints"

    async def run(self, url: str = "", method: str = "GET",
                  headers: dict = None, data: str = None,
                  follow_redirects: bool = True) -> dict:
        if not url:
            return {"success": False, "output": "", "error": "No url provided", "command": "curl_probe"}
        headers = _prepare_headers(headers, data)
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=follow_redirects) as client:
                if method.upper() == "GET":
                    resp = await client.get(url, headers=headers)
                elif method.upper() == "POST":
                    resp = await client.post(url, headers=headers, content=data)
                elif method.upper() == "PUT":
                    resp = await client.put(url, headers=headers, content=data)
                elif method.upper() == "DELETE":
                    resp = await client.delete(url, headers=headers)
                else:
                    resp = await client.request(method, url, headers=headers, content=data)

                body = resp.text[:30000]
                if len(resp.text) > 30000:
                    body += "\n...[TRUNCATED]..."

                # Auto-extract form fields from HTML to help LLM discover param names
                import re
                form_hint = ""
                if "input" in body.lower() and "name=" in body.lower():
                    matches = re.findall(r"""<input\s+[^>]*name=["']([^"']+)["']""", body, re.IGNORECASE)
                    if matches:
                        form_hint = "\n[DETECTED FORM FIELDS]: " + ", ".join(matches)
                    actions = re.findall(r"""<form\s+[^>]*action=["']([^"']*)["']""", body, re.IGNORECASE)
                    methods = re.findall(r"""<form\s+[^>]*method=["']([^"']*)["']""", body, re.IGNORECASE)
                    if actions:
                        form_hint += f"\n[DETECTED FORM ACTION]: {actions[0]}"
                    if methods:
                        form_hint += f"\n[DETECTED FORM METHOD]: {methods[0].upper()}"
                    # Auto-test SSTI with detected form fields
                    if matches and method.upper() == "GET":
                        from urllib.parse import urljoin
                        target_url = urljoin(url, actions[0]) if actions else url
                        ssti_payload = matches[0] + "={{7*7}}"
                        try:
                            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as probe_client:
                                ssti_resp = await probe_client.post(target_url, content=ssti_payload)
                            ssti_body = ssti_resp.text[:500]
                            if "49" in ssti_body or "{{7*7}}" not in ssti_body:
                                form_hint += f"\n[SSTI TEST]: POST with \"{ssti_payload}\" → {ssti_resp.status_code}. Body starts: {ssti_body[:200]}"
                        except Exception:
                            pass

                result = {
                    "success": resp.status_code < 500,
                    "output": f"Status: {resp.status_code}\nHeaders: {dict(resp.headers)}\n{form_hint}\n\nBody:\n{body}",
                    "error": "",
                    "command": f"{method} {url}",
                    "status_code": resp.status_code,
                    "headers": dict(resp.headers),
                }
                logger.info(f"curl_probe {method} {url} -> {resp.status_code}")
                return result
        except Exception as e:
            logger.error(f"curl_probe error: {e}")
            return {"success": False, "output": "", "error": str(e), "command": f"{method} {url}"}
