"""
SciForge Ingestion Engine
Extracts structured text, equations, sections, figures, and metadata from scientific PDFs, images, and notes.
"""
import re
import os
import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from backend.models import SourceDocument, ExtractedSection, ExtractedEquation

class OCRDependencyError(RuntimeError):
    """Raised when a scanned PDF needs OCR but Tesseract is unavailable."""


class PaperIngestionEngine:
    """
    Ingests scientific papers and extracts structured IR:
    - Text blocks & hierarchy
    - Equations (LaTeX & math notations)
    - Figures and diagrams references
    - Citations and bibliography
    """

    EQUATION_PATTERNS = [
        r'\$\$([\s\S]*?)\$\$',
        r'\\begin\{equation\*?\}([\s\S]*?)\\end\{equation\*?\}',
        r'\\begin\{align\*?\}([\s\S]*?)\\end\{align\*?\}',
        r'\\\[([\s\S]*?)\\\]',
        r'(?:(?:\b[A-Za-z0-9_]+\s*=\s*[^.\n]+)|(?:\b[A-Za-z]\([knt]\)\s*=\s*[^.\n]+))(?=\s*(?:\([0-9]+\)|$))'
    ]

    @classmethod
    def ingest_pdf(cls, file_path: Path, doc_id: str, ocr_language: Optional[str] = None) -> SourceDocument:
        """Parse PDF document using PyMuPDF and extract structured IR."""
        ocr_language = ocr_language or os.getenv("SCIFORGE_OCR_LANGUAGE", "eng")
        doc = fitz.open(str(file_path))
        num_pages = len(doc)
        full_text = []
        sections: List[ExtractedSection] = []
        equations: List[ExtractedEquation] = []
        eq_counter = 1
        figures_count = 0

        current_section = ExtractedSection(title="Introduction", page=1, content="")

        for page_idx in range(num_pages):
            page = doc[page_idx]
            page_text = page.get_text("text")
            if not page_text.strip() and page.get_images(full=True):
                try:
                    text_page = page.get_textpage_ocr(
                        language=ocr_language,
                        dpi=300,
                        full=True,
                    )
                    page_text = page.get_text("text", textpage=text_page)
                except RuntimeError as exc:
                    raise OCRDependencyError(
                        f"OCR failed on PDF page {page_idx + 1}. Install Tesseract OCR and "
                        f"the '{ocr_language}' language data, then ensure Tesseract is on PATH."
                    ) from exc
            full_text.append(f"--- Page {page_idx + 1} ---\n" + page_text)

            # Count images/figures
            images = page.get_images(full=True)
            figures_count += len(images)

            # Parse lines for headings, equations, and paragraphs
            lines = page_text.split('\n')
            for line in lines:
                line_str = line.strip()
                if not line_str:
                    continue

                # Section Heading detection (e.g., "1. Introduction", "II. METHODOLOGY", "Abstract")
                if re.match(r'^(?:[0-9]+\.|\b[IVXLCDM]+\.|\bAbstract\b|\bIntroduction\b|\bMethods\b|\bResults\b|\bDiscussion\b|\bConclusion\b)', line_str, re.IGNORECASE) and len(line_str) < 80:
                    if current_section.content.strip():
                        sections.append(current_section)
                    current_section = ExtractedSection(title=line_str, page=page_idx + 1, content="")
                else:
                    current_section.content += line_str + " "

            # Extract LaTeX equations or mathematical expressions
            for pat in cls.EQUATION_PATTERNS:
                for match in re.finditer(pat, page_text):
                    eq_str = match.group(1) if match.groups() else match.group(0)
                    eq_clean = eq_str.strip()
                    if len(eq_clean) > 3 and not any(e.latex == eq_clean for e in equations):
                        equations.append(ExtractedEquation(
                            id=f"eq_{eq_counter}",
                            latex=eq_clean,
                            name=f"Equation {eq_counter}",
                            page=page_idx + 1,
                            description="Mathematical relationship extracted from paper",
                            tag="SOURCE"
                        ))
                        eq_counter += 1

        if current_section.content.strip():
            sections.append(current_section)

        # Fallback if no sections were identified
        if not sections:
            sections.append(ExtractedSection(
                title="Overview & Theory",
                page=1,
                content="\n".join(full_text[:3])
            ))

        doc.close()

        return SourceDocument(
            id=doc_id,
            filename=file_path.name,
            num_pages=num_pages,
            raw_text="\n\n".join(full_text),
            sections=sections,
            equations=equations,
            figures_found=figures_count,
            references=cls._extract_references("\n\n".join(full_text))
        )

    @classmethod
    def ingest_text(cls, text_content: str, filename: str, doc_id: str) -> SourceDocument:
        """Parse raw text, handwritten transcript, or markdown notes."""
        lines = text_content.split('\n')
        sections: List[ExtractedSection] = []
        equations: List[ExtractedEquation] = []
        eq_counter = 1

        current_sec = ExtractedSection(title="Core Notes", page=1, content="")
        for line in lines:
            line_s = line.strip()
            if line_s.startswith('#'):
                if current_sec.content.strip():
                    sections.append(current_sec)
                current_sec = ExtractedSection(title=line_s.lstrip('#').strip(), page=1, content="")
            else:
                current_sec.content += line_s + "\n"

            # Check for math
            if '$' in line_s or '=' in line_s and any(c in line_s for c in '+-*/^_'):
                math_match = re.search(r'\$([^$]+)\$', line_s)
                if math_match:
                    latex = math_match.group(1).strip()
                    equations.append(ExtractedEquation(
                        id=f"eq_{eq_counter}",
                        latex=latex,
                        name=f"Note Equation {eq_counter}",
                        page=1,
                        description="Derivation note",
                        tag="DERIVED"
                    ))
                    eq_counter += 1

        if current_sec.content.strip():
            sections.append(current_sec)

        return SourceDocument(
            id=doc_id,
            filename=filename,
            num_pages=max(1, len(text_content) // 2500),
            raw_text=text_content,
            sections=sections,
            equations=equations,
            figures_found=0,
            references=cls._extract_references(text_content)
        )

    @classmethod
    def _extract_references(cls, text: str) -> List[str]:
        """Detect bibliographic citations."""
        ref_block = re.search(r'(?:References|BIBLIOGRAPHY)[\s\S]{0,100}\n([\s\S]+)$', text, re.IGNORECASE)
        refs = []
        if ref_block:
            ref_lines = ref_block.group(1).split('\n')
            for line in ref_lines:
                clean = line.strip()
                if clean and re.match(r'^(?:\[[0-9]+\]|[0-9]+\.|\([0-9]{4}\))', clean):
                    refs.append(clean)
        return refs[:10]
