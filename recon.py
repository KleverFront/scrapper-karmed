"""Reconnaissance: log in, dump the patients module and the endpoints its JS calls."""
import re
from pathlib import Path

import httpx

from karmed.client import KarmedClient

OUT = Path("raw/recon")
ENDPOINT_RE = re.compile(
    r"""\$\.(?:post|get|ajax)\(\s*["']([^"']+)["']"""
    r"""|url\s*:\s*["']([^"']+\.php[^"']*)["']"""
    r"""|\.open\(\s*["'](?:GET|POST)["']\s*,\s*["']([^"'?]+\.php)"""
)
SCRIPT_RE = re.compile(r"""<script[^>]+src=["']([^"']+)["']""", re.I)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    client = KarmedClient()
    client.login()
    print("login ok")
    page = client.get("modules/pacientes/")
    (OUT / "pacientes.html").write_text(page.text)
    print("pacientes page:", page.url, len(page.text), "bytes")

    host = page.url.host  # derive the target host instead of hardcoding it
    sources = {"pacientes.html": page.text}
    for src in SCRIPT_RE.findall(page.text):
        if src.startswith("http") and host not in src:
            continue
        js = None
        # relative "../js/" resolves to modules/js/ (404); the real files live one level up
        for url in (page.url.join(src), page.url.join("../" + src)):
            try:
                js = client.get(str(url)).text
                break
            except httpx.HTTPStatusError:
                continue
        if js is None:
            print("skip", src)
            continue
        name = re.sub(r"[^\w.-]", "_", str(url).split(host + "/")[-1])
        (OUT / name).write_text(js)
        sources[name] = js

    for name, text in sources.items():
        found = sorted({next(g for g in groups if g) for groups in ENDPOINT_RE.findall(text)})
        if found:
            print(f"\n[{name}]")
            for ep in found:
                print("  ", ep)
    client.close()


if __name__ == "__main__":
    main()
