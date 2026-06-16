from __future__ import annotations

import base64
import html
import mimetypes
import re
from pathlib import Path
from urllib.error import URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

try:
    import bleach
except ImportError:  # pragma: no cover - graceful fallback for unprepared environments
    bleach = None

try:
    import markdown as markdown_lib
except ImportError:  # pragma: no cover - graceful fallback for unprepared environments
    markdown_lib = None

BASE_DIR = Path(__file__).resolve().parent
IMG_TAG_RE = re.compile(r"<img\b([^>]*?)\bsrc=(['\"])(.*?)\2([^>]*)>", re.IGNORECASE | re.DOTALL)


def _is_within_root(candidate: Path, root: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _resolve_local_image_path(src: str, base_dir: Path | None = None) -> Path | None:
    base_dir = base_dir or BASE_DIR
    parsed = urlparse(src)
    path_text = unquote(parsed.path or src).lstrip("/")
    candidates = [
        base_dir / path_text,
        base_dir / "static" / path_text,
    ]
    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_file() and _is_within_root(candidate, base_dir):
                return candidate
        except OSError:
            continue
    return None


def _image_data_uri(src: str, base_dir: Path | None = None) -> str | None:
    src = (src or "").strip()
    if not src:
        return None
    if src.startswith("data:") or src.startswith("cid:"):
        return src

    parsed = urlparse(src)
    mime_type = None
    image_bytes = None

    if parsed.scheme in {"http", "https"}:
        try:
            request = Request(src, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=5) as response:
                image_bytes = response.read()
                mime_type = response.headers.get_content_type() or response.headers.get_content_type()
        except (URLError, TimeoutError, ValueError, OSError):
            return None
    else:
        local_path = _resolve_local_image_path(src, base_dir=base_dir)
        if not local_path:
            return None
        try:
            image_bytes = local_path.read_bytes()
        except OSError:
            return None
        mime_type = mimetypes.guess_type(local_path.name)[0]

    if not image_bytes:
        return None

    mime_type = mime_type or mimetypes.guess_type(parsed.path or src)[0] or "image/png"
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def embed_markdown_images(rendered_html: str, base_dir: Path | None = None) -> str:
    if not rendered_html:
        return rendered_html

    def _replace(match: re.Match[str]) -> str:
        before = match.group(1) or ""
        quote = match.group(2)
        src = match.group(3) or ""
        after = match.group(4) or ""
        embedded_src = _image_data_uri(src, base_dir=base_dir)
        if not embedded_src:
            return match.group(0)

        attrs = f"{before}src={quote}{embedded_src}{quote}{after}"
        if "alt=" not in attrs.lower():
            attrs = f'{attrs} alt=""'
        return f"<img{attrs}>"

    return IMG_TAG_RE.sub(_replace, rendered_html)


def render_markdown_html(raw_markdown: str, base_dir: Path | None = None) -> str:
    if not raw_markdown:
        return ""

    if bleach is None or markdown_lib is None:
        escaped_notice = html.escape(str(raw_markdown))
        paragraphs = [f"<p>{line}</p>" for line in escaped_notice.splitlines() if line.strip()]
        return "".join(paragraphs) or f"<p>{escaped_notice}</p>"

    rendered = markdown_lib.markdown(
        str(raw_markdown),
        extensions=["extra", "nl2br", "sane_lists", "fenced_code"],
    )
    rendered = embed_markdown_images(rendered, base_dir=base_dir)
    cleaned = bleach.clean(
        rendered,
        tags=[
            "p",
            "br",
            "strong",
            "em",
            "ul",
            "ol",
            "li",
            "blockquote",
            "pre",
            "code",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "a",
            "hr",
            "img",
            "div",
            "span",
        ],
        attributes={
            "a": ["href", "title", "rel", "target"],
            "img": ["src", "alt", "title", "width", "height"],
            "div": ["class"],
            "span": ["class"],
        },
        protocols=["http", "https", "mailto", "data"],
        strip=True,
    )
    return cleaned
