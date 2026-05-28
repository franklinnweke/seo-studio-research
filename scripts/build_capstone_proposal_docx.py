from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import html


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "SEO Studio Capstone Project Proposal.docx"


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def run(text: str, *, bold: bool = False, size: int | None = None) -> str:
    props: list[str] = []
    if bold:
        props.append("<w:b/>")
    if size:
        props.append(f'<w:sz w:val="{size * 2}"/>')
    rpr = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
    return f"<w:r>{rpr}<w:t xml:space=\"preserve\">{esc(text)}</w:t></w:r>"


def paragraph(text: str = "", *, style: str | None = None, bold: bool = False, size: int | None = None) -> str:
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{ppr}{run(text, bold=bold, size=size)}</w:p>"


def bullet(text: str) -> str:
    return (
        '<w:p><w:pPr><w:pStyle w:val="ListParagraph"/>'
        '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>'
        f"{run(text)}</w:p>"
    )


def numbered(text: str) -> str:
    return (
        '<w:p><w:pPr><w:pStyle w:val="ListParagraph"/>'
        '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr></w:pPr>'
        f"{run(text)}</w:p>"
    )


def cell(text: str, width: int, *, header: bool = False) -> str:
    fill = '<w:shd w:fill="F4F6F9"/>' if header else ""
    bold = header
    return (
        "<w:tc>"
        f'<w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{fill}</w:tcPr>'
        f"{paragraph(text, bold=bold)}"
        "</w:tc>"
    )


def table(headers: list[str], rows: list[list[str]], widths: list[int]) -> str:
    grid = "".join(f'<w:gridCol w:w="{width}"/>' for width in widths)
    body = [
        "<w:tbl>"
        '<w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="9360" w:type="dxa"/>'
        '<w:tblBorders><w:top w:val="single" w:sz="4" w:color="DADCE0"/>'
        '<w:left w:val="single" w:sz="4" w:color="DADCE0"/>'
        '<w:bottom w:val="single" w:sz="4" w:color="DADCE0"/>'
        '<w:right w:val="single" w:sz="4" w:color="DADCE0"/>'
        '<w:insideH w:val="single" w:sz="4" w:color="DADCE0"/>'
        '<w:insideV w:val="single" w:sz="4" w:color="DADCE0"/></w:tblBorders></w:tblPr>'
        f"<w:tblGrid>{grid}</w:tblGrid>"
    ]
    body.append("<w:tr>" + "".join(cell(header, width, header=True) for header, width in zip(headers, widths)) + "</w:tr>")
    for row in rows:
        body.append("<w:tr>" + "".join(cell(value, width) for value, width in zip(row, widths)) + "</w:tr>")
    body.append("</w:tbl>")
    return "".join(body)


def document_xml() -> str:
    parts: list[str] = []
    parts.append(paragraph("SEO Studio", style="Title"))
    parts.append(paragraph("Capstone Project Proposal", style="Subtitle"))
    parts.append(paragraph("Team Members: Aladenoye Ayobami, Abel Michael, Nweke Chigozie"))
    parts.append(paragraph("Course: PROG8751 Capstone (Web Development)"))
    parts.append(paragraph("Date of Submission: May 29, 2026"))
    parts.append(paragraph("Instructor: Davneet Chawla"))

    parts.append(paragraph("1. Problem Statement", style="Heading1"))
    parts.append(paragraph("Many content teams, web developers, and small businesses need to prepare large sets of images and website metadata before publishing pages. The work is repetitive and error-prone: images must be compressed, converted, renamed, resized, and given useful alt text; websites must be checked for broken links; and pages need clear summaries, titles, and meta descriptions. These tasks are often handled manually across separate tools, which slows down delivery and produces inconsistent SEO and accessibility results."))
    parts.append(paragraph("The problem is especially important for teams that manage brand-sensitive websites. A generic AI caption or filename may describe the image, but it may not match the company's tone, service area, product language, or website context. SEO Studio addresses this by combining image optimization, website checking, and AI-assisted metadata generation in one workflow, with review steps that keep the user in control before exports are finalized."))

    parts.append(paragraph("2. Proposed Solution and Key Benefits", style="Heading1"))
    parts.append(paragraph("SEO Studio is a web-based optimization platform for preparing website images and metadata. Users can upload images or ZIP archives, compress and convert them, clean filenames, generate AI-powered filenames, alt text, captions, and descriptions, review the generated results, and export processed images and reports. The platform also supports website workflows such as crawling pages, checking broken links, generating page summaries, creating SEO titles and meta descriptions, taking website screenshots, and checking bulk URL lists."))
    parts.append(paragraph("A key part of the solution is brand-aware AI generation. Before generating image metadata, users can upload a brand document in .docx, .txt, or .pdf format. The platform extracts useful context from the document and uses it alongside image analysis so generated names, alt text, captions, and descriptions better match the company's website and brand language."))
    parts.append(paragraph("The project will also include an AI focus-aware image resizer. When a user requests a target crop size, the platform should identify the important subject in the image and propose a crop around that focal area. For example, if a brand is about dogs and the uploaded image contains a dog in the bottom-left corner, the crop preview should preserve the dog instead of blindly cropping from the center. Users will preview and approve AI crop suggestions before exporting."))

    parts.append(paragraph("3. Project Goals and Scope", style="Heading1"))
    parts.append(paragraph("High-Level Goals:", style="Heading2"))
    goals = [
        "Build a usable local POC for image upload, compression, conversion, filename cleanup, and export.",
        "Generate AI-powered image metadata that can use brand document context.",
        "Implement review workflows so users can edit, approve, regenerate, and download optimized outputs.",
        "Add AI focus-aware crop and resize behavior for fixed-dimension website image requirements.",
        "Add website quality tools, including crawling, Basic Auth support, broken link checking, screenshots, bulk URL checking, and AI SEO metadata generation.",
    ]
    for goal in goals:
        parts.append(numbered(goal))
    parts.append(paragraph("Out of Scope:", style="Heading2"))
    for item in [
        "Multi-tenant user accounts and permissions.",
        "Billing and subscriptions.",
        "Direct CMS publishing.",
        "Kubernetes or distributed microservices.",
        "Enterprise-scale crawling and high-volume image processing.",
        "Automated deployment to customer websites.",
    ]:
        parts.append(bullet(item))

    parts.append(paragraph("4. Proposed Technology Stack and Market Relevance", style="Heading1"))
    parts.append(paragraph("Frontend: Next.js, TypeScript, Tailwind CSS, shadcn/ui-style components, TanStack Query, TanStack Table, and lucide-react. This stack is relevant because React and Next.js are widely used in modern web development, while TanStack Query and Table support production-quality data workflows and review screens."))
    parts.append(paragraph("Backend: FastAPI with Python 3.11+, Pillow, httpx, BeautifulSoup4, pandas, and openpyxl. FastAPI provides strong API documentation through OpenAPI/Swagger, while Python has mature image processing, web crawling, data export, and AI integration libraries."))
    parts.append(paragraph("AI runtime: Ollama for local development, with support for vision and language models. The architecture will allow a vision model to analyze images and focal points, while a language model generates brand-aligned filenames, alt text, captions, and descriptions."))
    parts.append(paragraph("Data and storage: Local file storage and JSON metadata for the POC, with PostgreSQL planned for beta persistence. This keeps the POC lightweight while leaving a clear path toward persistent job history, uploaded file records, and generated metadata records."))

    parts.append(paragraph("5. Preliminary Timeline by Sprint Milestones", style="Heading1"))
    parts.append(table(
        ["Sprint", "Internal focus", "Official due date"],
        [
            ["Sprint 1", "Project setup, documented FastAPI APIs, dashboard shell, image upload, validation, ZIP upload, compression, conversion, filename cleanup, and initial exports.", "June 20, 2026 at 4:59 AM"],
            ["Sprint 2", "Brand document upload and extraction, local AI integration, AI image metadata generation, metadata review UI, regenerate actions, and improved image export flow.", "July 11, 2026 at 4:59 AM"],
            ["Sprint 3", "AI focus-aware crop and resize workflow, crop preview and approval, website crawler, Basic Auth support, broken link checker, and bulk URL checker.", "August 1, 2026 at 4:59 AM"],
            ["Sprint 4", "Website screenshot tool, AI SEO metadata generator, CSV/JSON/XLSX/ZIP export hardening, demo reliability, cleanup, logging, technical summary, and final showcase preparation.", "August 15, 2026 at 4:59 AM"],
        ],
        [1500, 5760, 2100],
    ))
    parts.append(paragraph("The team plans to complete the main implementation work between June and the end of July, while using the official sprint dates as checkpoints for demonstration, grading, and final showcase readiness."))

    parts.append(paragraph("6. Team Charter", style="Heading1"))
    parts.append(table(
        ["Area", "Owner(s)"],
        [
            ["Frontend", "Ayobami"],
            ["Backend", "Michael"],
            ["Database management", "Michael and Chigozie"],
            ["Documentation", "Chigozie"],
            ["Quality assurance", "Ayobami and Chigozie"],
        ],
        [3000, 6360],
    ))
    parts.append(paragraph("Communication Plan: The team will use WhatsApp for regular communication and quick coordination. Tasks will be tracked in a GitHub Projects board so sprint work, blockers, and completed items are visible to the full team."))
    parts.append(paragraph("Conflict Resolution: The team will first discuss disagreements in WhatsApp and compare options against project scope, sprint goals, technical risk, and user value. If a decision is still unresolved, the team will use majority agreement and document the rationale in the relevant GitHub issue or task."))

    parts.append(paragraph("7. Links", style="Heading1"))
    parts.append(paragraph("GitHub Repository: https://github.com/iobami/seo-studio"))

    sect = (
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="708" w:footer="708" w:gutter="0"/>'
        "</w:sectPr>"
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(parts)}{sect}</w:body></w:document>"
    )


STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:pPr><w:spacing w:after="160" w:line="320" w:lineRule="auto"/></w:pPr><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:pPr><w:spacing w:after="60"/></w:pPr><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:b/><w:sz w:val="52"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:pPr><w:spacing w:after="180"/></w:pPr><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:color w:val="555555"/><w:sz w:val="28"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="360" w:after="200"/></w:pPr><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:b/><w:color w:val="2E74B5"/><w:sz w:val="32"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/></w:pPr><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:b/><w:color w:val="2E74B5"/><w:sz w:val="26"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="540" w:hanging="280"/><w:spacing w:after="80" w:line="290" w:lineRule="auto"/></w:pPr></w:style>
  <w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:tblPr><w:tblBorders><w:top w:val="single" w:sz="4" w:color="DADCE0"/><w:left w:val="single" w:sz="4" w:color="DADCE0"/><w:bottom w:val="single" w:sz="4" w:color="DADCE0"/><w:right w:val="single" w:sz="4" w:color="DADCE0"/><w:insideH w:val="single" w:sz="4" w:color="DADCE0"/><w:insideV w:val="single" w:sz="4" w:color="DADCE0"/></w:tblBorders><w:tblCellMar><w:top w:w="80" w:type="dxa"/><w:start w:w="120" w:type="dxa"/><w:bottom w:w="80" w:type="dxa"/><w:end w:w="120" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>
</w:styles>
"""


NUMBERING = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="&#8226;"/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="540" w:hanging="280"/></w:pPr></w:lvl></w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="1"/></w:num>
  <w:abstractNum w:abstractNumId="2"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="540" w:hanging="280"/></w:pPr></w:lvl></w:abstractNum>
  <w:num w:numId="2"><w:abstractNumId w:val="2"/></w:num>
</w:numbering>
"""


def write_docx() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>""")
        docx.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>""")
        docx.writestr("word/_rels/document.xml.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
</Relationships>""")
        docx.writestr("word/document.xml", document_xml())
        docx.writestr("word/styles.xml", STYLES)
        docx.writestr("word/numbering.xml", NUMBERING)
        docx.writestr("docProps/core.xml", f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>SEO Studio Capstone Project Proposal</dc:title>
  <dc:creator>SEO Studio Team</dc:creator>
  <cp:lastModifiedBy>SEO Studio Team</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>""")
        docx.writestr("docProps/app.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>seo-studio</Application>
</Properties>""")
    print(OUTPUT)


if __name__ == "__main__":
    write_docx()
