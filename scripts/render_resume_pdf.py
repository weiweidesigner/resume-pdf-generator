#!/usr/bin/env python3
"""Render resume text or JSON into a polished PDF."""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


SECTION_ALIASES = {
    "个人简介": "summary",
    "简介": "summary",
    "summary": "summary",
    "岗位优势": "strengths",
    "核心优势": "strengths",
    "核心能力": "strengths",
    "优势": "strengths",
    "教育背景": "education",
    "教育经历": "education",
    "education": "education",
    "工作经历": "work",
    "工作经验": "work",
    "work": "work",
    "项目经历": "projects",
    "项目经验": "projects",
    "projects": "projects",
    "专业技能": "skills",
    "技能": "skills",
    "skills": "skills",
    "项目链接": "links",
    "链接": "links",
    "links": "links",
    "个人影响力": "influence",
    "影响力": "influence",
}


CSS = r"""
@page { margin: 0; background: #ffffff; }
* { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
html, body {
  width: 100%;
  min-height: 100%;
  margin: 0;
  padding: 0;
  overflow-x: hidden;
  overflow-y: auto;
  background: #ffffff;
}
body {
  color: #1a1a1a;
  font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", Arial, sans-serif;
  font-size: 9.3pt;
  line-height: 1.42;
}
.page {
  width: 100vw;
  min-height: 100vh;
  padding: 24px 28px;
  overflow: visible;
  background: #fff;
}
.page-content {
  width: 100%;
  min-height: 100%;
  overflow: visible;
}
.fit {
  width: 100%;
  transform-origin: top left;
}
header {
  border-bottom: 1.5pt solid #2563eb;
  padding-bottom: 8pt;
  margin-bottom: 12pt;
}
h1 {
  margin: 0 0 4pt;
  color: #000;
  font-size: 20pt;
  line-height: 1.1;
}
.role-tag {
  display: block;
  margin: 0 0 4pt;
  color: #2563eb;
  font-size: 11.5pt;
  font-weight: 700;
}
.contact-info {
  color: #4b5563;
  font-size: 9pt;
}
section { margin-bottom: 10pt; break-inside: avoid; }
h2 {
  margin: 0 0 6pt;
  padding: 3pt 0 3pt 7pt;
  border-left: 3.5pt solid #2563eb;
  background: #f3f4f6;
  color: #111;
  font-size: 12.2pt;
  break-after: avoid;
}
h3 {
  margin: 7pt 0 2pt;
  color: #111;
  font-size: 10.5pt;
  break-after: avoid;
}
h4, h5, h6 {
  margin: 6pt 0 2pt;
  color: #111827;
  font-size: 9.6pt;
  break-after: avoid;
}
p { margin: 0 0 4.5pt; text-align: justify; }
ul, ol { margin: 0 0 6pt; padding-left: 15pt; }
li { margin-bottom: 2.5pt; }
strong { color: #000; font-weight: 700; }
.md-heading-line {
  display: block;
  color: #4b5563;
  font-size: 9.2pt;
}
.md-heading-line strong {
  color: #111;
}
.item-group { margin-bottom: 9pt; break-inside: avoid; }
.item-header {
  display: block;
  margin-bottom: 2pt;
  font-size: 10pt;
  font-weight: 700;
}
.item-date {
  float: right;
  color: #4b5563;
  font-weight: 400;
}
.item-meta {
  margin-bottom: 4pt;
  color: #6b7280;
  font-size: 9pt;
}
.subsection-title {
  margin: 7pt 0 3pt;
  padding-left: 6pt;
  border-left: 3pt solid #93c5fd;
  color: #111827;
  font-size: 9.5pt;
  font-weight: 700;
}
.project-details {
  margin-bottom: 6pt;
  padding: 6pt;
  border-radius: 4pt;
  background: #f9fafb;
  font-size: 9pt;
}
.links-container {
  padding: 10pt 12pt;
  border: 1px solid #e5e7eb;
  border-radius: 6pt;
  background: #f8fafc;
}
.link-item { margin-bottom: 6pt; font-size: 10pt; }
a { color: #2563eb; text-decoration: none; font-weight: 600; }
.bold-text { color: #000; font-weight: 700; }
body.pdf-mode {
  width: 210mm;
  min-height: auto;
  overflow: visible;
}
body.pdf-mode .page {
  width: 210mm;
  min-height: auto;
  padding: 8mm 8mm 0;
  overflow: visible;
}
body.pdf-mode .page-content {
  width: 100%;
  min-height: auto;
  overflow: visible;
}
"""


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def inline_markdown(text: str) -> str:
    escaped = esc(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"(https?://[^\s<]+)", r'<a href="\1">\1</a>', escaped)
    return escaped


def is_markdown_input(text: str) -> bool:
    return bool(re.search(r"^#{1,6}\s+", text, re.M) or re.search(r"^\s*[-*]\s+", text, re.M) or "**" in text)


def render_direct_markdown_html(markdown_text: str) -> str:
    """Render Markdown directly to resume HTML without semantic rewriting."""
    lines = markdown_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    first_heading_rendered = False

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            blocks.append(f'<p>{"<br>".join(inline_markdown(line.rstrip("  ")) for line in paragraph)}</p>')
            paragraph = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            blocks.append("<ul>" + "".join(f"<li>{inline_markdown(item)}</li>" for item in list_items) + "</ul>")
            list_items = []

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            flush_paragraph()
            flush_list()
            continue
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        bullet = re.match(r"^\s*[-*]\s+(.+?)\s*$", line)
        if heading:
            flush_paragraph()
            flush_list()
            level = len(heading.group(1))
            text = heading.group(2).strip()
            if not first_heading_rendered:
                blocks.append(f"<header><h1>{inline_markdown(text)}</h1></header>")
                first_heading_rendered = True
            elif level <= 2:
                blocks.append(f"<section><h2>{inline_markdown(text)}</h2>")
            else:
                blocks.append(f"<h{min(level, 6)}>{inline_markdown(text)}</h{min(level, 6)}>")
            continue
        if bullet:
            flush_paragraph()
            list_items.append(bullet.group(1).strip())
            continue
        flush_list()
        paragraph.append(line.strip())

    flush_paragraph()
    flush_list()

    content = []
    section_open = False
    for block in blocks:
        if block.startswith("<section>"):
            if section_open:
                content.append("</section>")
            section_open = True
            content.append(block)
        else:
            content.append(block)
    if section_open:
        content.append("</section>")
    return render_document_frame("".join(content))


def render_document_frame(content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <style>{CSS}</style>
</head>
<body>
  <main class="page"><div class="page-content"><div class="fit">{content}</div></div></main>
</body>
</html>
"""


def install_deps() -> None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "playwright"])
    subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])


def normalize_lines(text: str) -> list[str]:
    return [line.strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if line.strip()]


def split_heading(line: str) -> str | None:
    clean = re.sub(r"^[#*\-\s]+", "", line).strip().rstrip("：:")
    return SECTION_ALIASES.get(clean.lower()) or SECTION_ALIASES.get(clean)


def strip_markdown(value: str) -> str:
    value = re.sub(r"^#+\s*", "", value.strip())
    value = re.sub(r"\*\*(.*?)\*\*", r"\1", value)
    value = re.sub(r"`([^`]*)`", r"\1", value)
    value = re.sub(r"^[\-*•]\s*", "", value)
    return value.strip()


def heading_match(line: str) -> tuple[int, str] | None:
    match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
    if not match:
        return None
    return len(match.group(1)), strip_markdown(match.group(2)).rstrip("：:")


def parse_title_pair(text: str, default_first_key: str, default_second_key: str) -> dict[str, str]:
    parts = [part.strip() for part in re.split(r"\s*[｜|]\s*", strip_markdown(text)) if part.strip()]
    if len(parts) >= 2:
        return {default_first_key: parts[0], default_second_key: parts[1]}
    return {default_first_key: parts[0] if parts else "", default_second_key: ""}


def append_text(target: dict[str, Any], line: str) -> None:
    clean = strip_markdown(line)
    if not clean:
        return
    if re.match(r"^\d{4}[.\-/年]", clean) or "至今" in clean:
        target["date"] = clean
        return
    if clean.startswith("项目结果："):
        target.setdefault("details", []).append({"title": "项目结果", "items": [clean.replace("项目结果：", "", 1).strip()]})
        return
    if clean.startswith("邮箱：") or clean.startswith("手机：") or clean.startswith("微信："):
        target.setdefault("contact", []).append(clean)
        return
    if clean.startswith("- "):
        target.setdefault("bullets", []).append(clean[2:].strip())
    elif target.get("description") or target.get("summary"):
        target.setdefault("bullets", []).append(clean)
    else:
        target["description"] = clean


def parse_markdown_resume(text: str) -> dict[str, Any]:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    data: dict[str, Any] = {
        "name": "个人简历",
        "headline": "",
        "contact": [],
        "summary": [],
        "strengths": [],
        "education": [],
        "work": [],
        "projects": [],
        "skills": [],
        "links": [],
        "custom_sections": [],
    }
    current_section = ""
    current_item: dict[str, Any] | None = None
    pending_strength: str | None = None
    custom: dict[str, Any] | None = None

    def finish_item() -> None:
        nonlocal current_item
        if not current_item:
            return
        if current_section == "work":
            data["work"].append(current_item)
        elif current_section == "projects":
            data["projects"].append(current_item)
        elif current_section == "education":
            data["education"].append(current_item)
        current_item = None

    def finish_custom() -> None:
        nonlocal custom
        if custom and (custom.get("paragraphs") or custom.get("bullets")):
            data["custom_sections"].append(custom)
        custom = None

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        heading = heading_match(line)
        if heading:
            level, title = heading
            section_key = SECTION_ALIASES.get(title) or SECTION_ALIASES.get(title.lower())
            if level == 1 and not section_key:
                data["name"] = title
                continue
            if level == 2:
                if not section_key and data.get("name") == "个人简历" and not current_section:
                    data["name"] = title
                    continue
                finish_item()
                finish_custom()
                current_section = section_key or f"custom:{title}"
                if section_key == "strengths":
                    data["strengths_title"] = title
                pending_strength = None
                if current_section.startswith("custom:"):
                    custom = {"title": title, "paragraphs": [], "bullets": []}
                continue
            if level >= 3:
                finish_item()
                pending_strength = None
                if current_section == "work":
                    parsed = parse_title_pair(title, "role", "company")
                    current_item = {"company": parsed.get("company", ""), "role": parsed.get("role", ""), "date": "", "description": "", "bullets": []}
                elif current_section == "projects":
                    current_item = {"name": title, "role": "", "date": "", "summary": "", "details": []}
                elif current_section == "education":
                    current_item = {"school": title, "degree": "", "date": "", "details": []}
                elif current_section.startswith("custom:") and custom is not None:
                    custom.setdefault("paragraphs", []).append(title)
                continue

        clean = strip_markdown(line)
        if not clean:
            continue
        if clean.startswith("对，代表项目里应该") or clean.startswith("可以改成下面这一版"):
            continue
        if current_section == "":
            if not data["headline"] and not any(clean.startswith(prefix) for prefix in ("邮箱：", "手机：", "微信：")):
                data["headline"] = clean
            elif clean.startswith(("邮箱：", "手机：", "微信：")):
                data["contact"].append(clean)
            else:
                data["summary"].append(clean)
        elif current_section == "summary":
            data["summary"].append(clean)
        elif current_section == "strengths":
            if re.match(r"^\*\*.*\*\*\s*$", line) or (len(clean) <= 18 and not clean.endswith("。")):
                pending_strength = clean
            elif pending_strength:
                data["strengths"].append({"title": pending_strength, "description": clean})
                pending_strength = None
            else:
                data["strengths"].append({"title": "", "description": clean})
        elif current_section == "skills":
            if re.match(r"^\*\*.*\*\*\s*$", line):
                pending_strength = clean
            elif pending_strength:
                data["skills"].append(f"{pending_strength}：{clean}")
                pending_strength = None
            else:
                data["skills"].append(clean)
        elif current_section == "links":
            data["links"].extend(parse_links([clean]))
        elif current_section == "influence":
            data.setdefault("custom_sections", [])
            if custom is None:
                custom = {"title": "个人影响力", "paragraphs": [], "bullets": []}
            if raw.lstrip().startswith(("-", "*", "•")):
                custom["bullets"].append(clean)
            else:
                custom["paragraphs"].append(clean)
        elif current_section == "work" and current_item is not None:
            append_text(current_item, clean)
        elif current_section == "projects" and current_item is not None:
            if clean.startswith("项目结果："):
                current_item.setdefault("details", []).append({"title": "项目结果", "items": [clean.replace("项目结果：", "", 1).strip()]})
            elif current_item.get("summary"):
                current_item.setdefault("details", []).append({"title": "关键说明", "items": [clean]})
            else:
                current_item["summary"] = clean
        elif current_section == "education" and current_item is not None:
            if clean.startswith(("本科：", "硕士：")):
                current_item.setdefault("details", []).append(clean)
            elif re.search(r"\d{4}", clean):
                current_item["date"] = clean
            else:
                current_item.setdefault("details", []).append(clean)
        elif current_section.startswith("custom:") and custom is not None:
            if raw.lstrip().startswith(("-", "*", "•")):
                custom["bullets"].append(clean)
            else:
                custom["paragraphs"].append(clean)

    finish_item()
    finish_custom()
    if pending_strength:
        if current_section == "skills":
            data["skills"].append(pending_strength)
        else:
            data["strengths"].append({"title": "", "description": pending_strength})
    return data


def parse_text_resume(text: str) -> dict[str, Any]:
    if re.search(r"^#{1,3}\s+", text, re.M):
        return parse_markdown_resume(text)
    lines = normalize_lines(text)
    result: dict[str, Any] = {"name": "", "headline": "", "contact": [], "summary": []}
    if not lines:
        raise SystemExit("Resume input is empty.")

    first_heading = next((index for index, line in enumerate(lines) if split_heading(line)), len(lines))
    intro = lines[:first_heading]
    body = lines[first_heading:]

    if intro:
        first = re.sub(r"^[#\s]+", "", intro[0]).strip()
        if len(first) > 30 and not ("｜" in first or "|" in first):
            result["name"] = "个人简历"
            result["summary"].append(first)
        elif "｜" in first or "|" in first:
            parts = re.split(r"\s*[｜|]\s*", first)
            result["name"] = parts[0]
            if len(parts) > 1:
                result["headline"] = parts[1]
            if len(parts) > 2:
                result["contact"].extend(parts[2:])
        else:
            result["name"] = first
        for line in intro[1:]:
            if re.search(r"@|电话|手机|1\d{10}|https?://|岁|年经验|城市", line, re.I):
                result["contact"].append(line)
            elif not result.get("headline"):
                result["headline"] = line
            else:
                result["summary"].append(line)

    current = "summary"
    buckets: dict[str, list[str]] = {key: [] for key in set(SECTION_ALIASES.values())}
    for line in body:
        heading = split_heading(line)
        if heading:
            current = heading
            continue
        buckets.setdefault(current, []).append(re.sub(r"^[\-*•]\s*", "", line))

    if buckets.get("summary"):
        result["summary"].extend(buckets["summary"])
    result["strengths"] = [{"title": "", "description": item} for item in buckets.get("strengths", [])]
    result["education"] = [{"school": item, "degree": "", "date": ""} for item in buckets.get("education", [])]
    result["work"] = [{"company": item, "role": "", "date": "", "bullets": []} for item in buckets.get("work", [])]
    result["projects"] = [{"name": item, "summary": "", "details": []} for item in buckets.get("projects", [])]
    result["skills"] = buckets.get("skills", [])
    result["links"] = parse_links(buckets.get("links", []))
    if not result["name"]:
        result["name"] = "个人简历"
    return result


def parse_links(lines: list[str]) -> list[dict[str, str]]:
    links = []
    for line in lines:
        match = re.search(r"(https?://\S+)", line)
        if match:
            label = line.replace(match.group(1), "").strip(" ：:-") or "链接"
            links.append({"label": label, "url": match.group(1)})
        elif line:
            links.append({"label": line, "url": ""})
    return links


def load_resume(args: argparse.Namespace) -> dict[str, Any]:
    if args.data:
        return json.loads(Path(args.data).read_text(encoding="utf-8"))
    if args.input:
        return parse_text_resume(Path(args.input).read_text(encoding="utf-8"))
    if args.text:
        return parse_text_resume(args.text)
    stdin = sys.stdin.read()
    if stdin.strip():
        return parse_text_resume(stdin)
    raise SystemExit("Provide --text, --input, --data, or stdin.")


def load_source_text(args: argparse.Namespace) -> str:
    if args.input:
        return Path(args.input).read_text(encoding="utf-8")
    if args.text:
        return args.text
    stdin = sys.stdin.read()
    if stdin.strip():
        return stdin
    raise SystemExit("Provide --text, --input, --data, or stdin.")


def render_list(items: list[Any], ordered: bool = False) -> str:
    if not items:
        return ""
    tag = "ol" if ordered else "ul"
    rows = []
    for item in items:
        if isinstance(item, dict):
            title = item.get("title") or item.get("name") or ""
            desc = item.get("description") or item.get("summary") or ""
            text = f'<span class="bold-text">{esc(title)}：</span>{esc(desc)}' if title and desc else esc(title or desc)
        else:
            text = esc(item)
        rows.append(f"<li>{text}</li>")
    return f"<{tag}>{''.join(rows)}</{tag}>"


def render_section(title: str, body: str) -> str:
    return f"<section><h2>{esc(title)}</h2>{body}</section>" if body.strip() else ""


def render_resume_html(data: dict[str, Any]) -> str:
    name = data.get("name") or "个人简历"
    headline = data.get("headline") or data.get("role") or "简历"
    contact = data.get("contact") or []
    if isinstance(contact, str):
        contact = [contact]

    sections: list[str] = []
    summary = data.get("summary") or []
    if isinstance(summary, str):
        summary = [summary]
    sections.append(render_section("个人简介", "".join(f"<p>{esc(item)}</p>" for item in summary)))
    sections.append(render_section(data.get("strengths_title") or "岗位优势", render_list(data.get("strengths") or [], ordered=True)))
    sections.append(render_section("教育背景", render_item_groups(data.get("education") or [], "school", "degree")))
    sections.append(render_section("工作经历", render_item_groups(data.get("work") or [], "company", "role")))
    sections.append(render_section("项目经历", render_projects(data.get("projects") or [])))
    sections.append(render_section("专业技能", render_list(data.get("skills") or [])))
    sections.append(render_section("项目链接", render_links(data.get("links") or [])))
    for custom in data.get("custom_sections") or []:
        body = "".join(f"<p>{esc(item)}</p>" for item in custom.get("paragraphs", []))
        body += render_list(custom.get("bullets") or [])
        sections.append(render_section(custom.get("title") or "补充信息", body))

    return render_document_frame(f"""
  <header>
    <div><h1>{esc(name)}</h1><span class="role-tag">{esc(headline)}</span></div>
    <div class="contact-info">{esc(" ｜ ".join(str(item) for item in contact))}</div>
  </header>
  {''.join(sections)}
""")


def render_item_groups(items: list[dict[str, Any]], title_key: str, meta_key: str) -> str:
    parts = []
    for item in items:
        title = item.get(title_key) or item.get("name") or item.get("title") or ""
        meta = item.get(meta_key) or item.get("role") or ""
        date = item.get("date") or ""
        description = item.get("description") or item.get("summary") or ""
        bullets = item.get("bullets") or item.get("details") or []
        parts.append(
            '<div class="item-group">'
            f'<div class="item-header">{esc(title)}<span class="item-date">{esc(date)}</span></div>'
            f'<div class="item-meta">{esc(meta)}</div>'
            f'{"<p>" + esc(description) + "</p>" if description else ""}'
            f'{render_list(bullets)}'
            "</div>"
        )
    return "".join(parts)


def render_projects(projects: list[dict[str, Any]]) -> str:
    parts = []
    for project in projects:
        header = project.get("name") or project.get("title") or ""
        role = project.get("role") or ""
        date = project.get("date") or ""
        summary = project.get("summary") or project.get("description") or ""
        detail_html = ""
        for detail in project.get("details") or []:
            if isinstance(detail, dict):
                detail_html += f'<div class="subsection-title">{esc(detail.get("title"))}</div>{render_list(detail.get("items") or [])}'
            else:
                detail_html += f"<p>{esc(detail)}</p>"
        summary_html = f'<div class="project-details">{esc(summary)}</div>' if summary else ""
        parts.append(
            '<div class="item-group">'
            f'<div class="item-header">{esc(header)}<span class="item-date">{esc(date)}</span></div>'
            f'<div class="item-meta">{esc(role)}</div>'
            f"{summary_html}{detail_html}</div>"
        )
    return "".join(parts)


def render_links(links: list[Any]) -> str:
    if not links:
        return ""
    rows = []
    for item in links:
        if isinstance(item, dict):
            label = item.get("label") or item.get("name") or item.get("url") or "链接"
            url = item.get("url") or ""
        else:
            label, url = str(item), ""
        if url:
            rows.append(f'<div class="link-item">🔗 <a href="{esc(url)}">{esc(label)}</a></div>')
        else:
            rows.append(f'<div class="link-item">{esc(label)}</div>')
    return f'<div class="links-container">{"".join(rows)}</div>'


async def html_to_pdf(html_text: str, output_pdf: Path, min_height_px: int = 1123) -> None:
    try:
        from playwright.async_api import async_playwright
    except ModuleNotFoundError as exc:
        raise SystemExit("Missing dependency: run `python scripts/render_resume_pdf.py --install-deps` first.") from exc

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 794, "height": max(min_height_px, 1123)}, device_scale_factor=1)
        await page.set_content(html_text, wait_until="load")
        await page.emulate_media(media="screen")
        height_px = await page.evaluate(
            """() => {
                document.body.classList.add('pdf-mode');
                const page = document.querySelector('.page');
                const fit = document.querySelector('.fit');
                if (fit) {
                    fit.style.transform = 'none';
                    fit.style.width = '100%';
                    fit.style.height = 'auto';
                    fit.dataset.scale = '1';
                }
                const doc = document.documentElement;
                const body = document.body;
                const pageHeight = page ? page.scrollHeight : 0;
                return Math.ceil(Math.max(
                    pageHeight,
                    doc.scrollHeight,
                    body.scrollHeight,
                    body.offsetHeight
                ) + 12);
            }"""
        )
        await page.pdf(
            path=str(output_pdf),
            width="210mm",
            height=f"{max(int(height_px), min_height_px)}px",
            print_background=True,
            margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"},
            prefer_css_page_size=False,
        )
        await browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Render resume text or JSON into PDF.")
    parser.add_argument("--text", help="Resume description text.")
    parser.add_argument("--input", help="Plain text or Markdown resume file.")
    parser.add_argument("--data", help="Structured resume JSON file.")
    parser.add_argument("--output", help="Output PDF path.")
    parser.add_argument("--html", help="Optional output HTML path.")
    parser.add_argument("--single-page", action="store_true", help="Deprecated: output is always one page with adaptive height.")
    parser.add_argument("--min-height", type=int, default=1123, help="Minimum PDF page height in px. Default approximates A4 height.")
    parser.add_argument("--install-deps", action="store_true", help="Install Playwright and Chromium.")
    args = parser.parse_args()

    if args.install_deps:
        install_deps()
        print("Dependencies installed.")
        return 0
    if not args.output:
        raise SystemExit("--output is required unless --install-deps is used.")

    if args.data:
        html_text = render_resume_html(load_resume(args))
    else:
        html_text = render_direct_markdown_html(load_source_text(args))
    if args.html:
        html_path = Path(args.html).expanduser().resolve()
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html_text, encoding="utf-8")
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(html_to_pdf(html_text, output, min_height_px=args.min_height))
    print(json.dumps({"ok": True, "pdf": str(output), "html": str(Path(args.html).resolve()) if args.html else None}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
