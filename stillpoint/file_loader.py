from __future__ import annotations

import hashlib
import mimetypes
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".jsonl",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".csv", ".sql", ".sh", ".bash", ".css",
    ".xml", ".rst", ".log",
}
HTML_EXTENSIONS = {".html", ".htm"}


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0
    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style"}: self._skip += 1
        if tag.lower() in {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr"}: self.parts.append("\n")
    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style"} and self._skip: self._skip -= 1
        if tag.lower() in {"p", "div", "li", "h1", "h2", "h3", "h4", "tr"}: self.parts.append("\n")
    def handle_data(self, data):
        if not self._skip: self.parts.append(data)
    def text(self):
        raw="".join(self.parts)
        lines=[re.sub(r"\s+", " ", line).strip() for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()


def _safe_name(name):return re.sub(r"[^A-Za-z0-9._-]+","_",name)[:120] or "attachment"


def import_attachment(source,managed_root,task_id,allowed_roots=None):
    src=Path(source).expanduser().resolve()
    roots=[Path(r).expanduser().resolve() for r in (allowed_roots or [])]
    if roots and not any(src==r or r in src.parents for r in roots):
        raise PermissionError(f"attachment path is outside allowed import roots: {src}")
    if not src.exists() or not src.is_file():raise FileNotFoundError(str(src))
    digest=sha256(src);target_dir=Path(managed_root).resolve()/task_id;target_dir.mkdir(parents=True,exist_ok=True);target=target_dir/f"{digest[:16]}_{_safe_name(src.name)}"
    if not target.exists():shutil.copy2(src,target)
    return read_attachment(target)|{"original_name":src.name,"path":str(target)}


def _docx_text(p: Path) -> str:
    try:
        with zipfile.ZipFile(p) as z: xml=z.read("word/document.xml")
        root=ET.fromstring(xml)
        paras=[]
        for para in root.iter():
            if para.tag.endswith('}p'):
                text="".join(t.text or "" for t in para.iter() if t.tag.endswith('}t')).strip()
                if text: paras.append(text)
        return "\n".join(paras)
    except Exception as exc:
        raise ValueError(f"invalid DOCX: {p.name}") from exc


def read_attachment(path,max_chars=200000):
    p=Path(path).expanduser().resolve()
    if not p.exists() or not p.is_file():raise FileNotFoundError(str(p))
    data=p.read_bytes();digest=hashlib.sha256(data).hexdigest();suffix=p.suffix.lower()
    if suffix==".docx":
        text=_docx_text(p)
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif suffix in HTML_EXTENSIONS:
        parser=_HTMLText();parser.feed(data.decode("utf-8",errors="replace"));text=parser.text();media_type="text/html"
    elif suffix==".pdf":
        raise ValueError("PDF ingestion is not supported by this runtime")
    elif suffix in TEXT_EXTENSIONS or (mimetypes.guess_type(p.name)[0] or "").startswith("text/"):
        if b"\x00" in data[:8192]: raise ValueError(f"binary file is not supported as text: {p.name}")
        text=data.decode("utf-8",errors="replace");media_type=mimetypes.guess_type(p.name)[0] or "text/plain"
    else:
        raise ValueError(f"unsupported attachment type: {p.suffix or 'no extension'}")
    truncated=len(text)>max_chars
    return {"path":str(p),"name":p.name,"sha256":digest,"text":text[:max_chars],"truncated":"true" if truncated else "false","media_type":media_type,"size_bytes":len(data)}
