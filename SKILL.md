---
name: resume-pdf-generator
description: Generate a resume/CV PDF from Chinese or English resume Markdown. Use when the user asks to create a resume, generate a CV, typeset resume content, convert Markdown resume text into PDF, or export a polished resume PDF while preserving the original headings, paragraphs, lists, dates, metrics, and project results.
---

# Resume Generator

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

The PDF is always one page with A4 width (`210mm`) and adaptive height. The renderer keeps Markdown in one column, does not compress content into A4 height, and increases page height to fit the full resume.

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
