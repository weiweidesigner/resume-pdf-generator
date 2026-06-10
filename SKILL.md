---
name: resume-pdf-generator
description: Turn a Chinese or English resume description into a polished PDF resume. Use when the user provides resume text, profile notes, work/project/education experience, or asks to generate, rewrite, typeset, export, or save a resume/CV PDF from text.
---

# Resume PDF Generator

## Workflow

1. Treat Markdown resume text as the source of truth. Do not rewrite, summarize, classify, or convert it into another schema unless the user explicitly asks.
2. Preserve headings, paragraphs, lists, bold text, contact lines, dates, metrics, project results, and ordering exactly as provided.
3. Save the user's resume text as a Markdown or plain text input file.
4. Run the renderer:

```bash
python scripts/render_resume_pdf.py --input resume.txt --output resume.pdf
```

Structured JSON is optional and should only be used when the user provides structured data or explicitly asks for schema-based rendering:

```bash
python scripts/render_resume_pdf.py --data resume.json --output resume.pdf
```

To also save the intermediate HTML:

```bash
python scripts/render_resume_pdf.py --input resume.txt --output resume.pdf --html resume.html
```

The PDF is always a single fixed A4 page. The renderer scales the page content down to fit; it never increases page height based on content.

## Dependency Setup

The renderer uses Playwright Chromium to print HTML to PDF. If dependencies are missing, run:

```bash
python scripts/render_resume_pdf.py --install-deps
```

Then rerun the render command.

## Output Rules

- Always return the generated PDF path.
- If HTML is requested or useful for debugging, return that path too.
- If dependency installation fails, report the exact command to retry.
- Keep the final PDF factual and professional; do not add decorative content that was not requested.
