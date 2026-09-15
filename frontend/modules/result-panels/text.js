/**
 * Text panel (v1.8.3 B3) - result-panels sub-module (D9).
 * Moved verbatim from app.js. The four text-normalisation helpers it calls already
 * live in utils/text.js (B0b) and the shared /blocks cache lives in preview-state.js
 * (B1a follow-up), so every read expression stays byte-identical.
 */
import { escapeHtml } from '../utils/dom.js';
import {
    normalizeTextForDisplay, normalizePanelParagraphText, isLikelyCollapsedText, toAzureTypeLabel,
} from '../utils/text.js';
import { lastFetchedBlocks } from '../preview-state.js';

/**
 * Collect text-bearing elements from Phase1-style result.view.pages[].elements (payload.text).
 */
export function collectViewPageTextElements(view) {
    if (!view || !Array.isArray(view.pages)) return [];
    const out = [];
    for (const page of view.pages) {
        const pageNum = page.page_num || page.page || 1;
        const elements = page.elements || [];
        let i = 0;
        for (const elem of elements) {
            if (!elem || typeof elem !== 'object') continue;
            const payload = elem.payload || {};
            const text = (typeof payload.text === 'string' ? payload.text : '').trim();
            if (!text) continue;
            const kind = String(elem.kind || elem.type || 'paragraph').toLowerCase();
            out.push({
                id: elem.id || `view_${pageNum}_${i++}`,
                type: kind,
                text,
                confidence: payload.confidence ?? elem.confidence,
                page: pageNum
            });
        }
    }
    return out;
}

/**
 * Update Content Text view
 */
export function updateContentText(result) {
    const contentTextContent = document.getElementById('contentTextContent');
    if (!contentTextContent) return;

    // Prefer flat /blocks data when already fetched; fall back to result fields.
    const blocksData = lastFetchedBlocks;
    const textBlocks = result.text_blocks || [];
    let semanticTextBlocks;
    if (blocksData) {
        semanticTextBlocks = blocksData.blocks.filter(b => {
              const t = String(b.type || b.role || '').toLowerCase();
              return [
                  'doc_title', 'paragraph_title', 'abstract_title', 'reference_title', 'content_title',
                  'figure_table_chart_title', 'table_caption',
                  'title', 'subtitle', 'paragraph', 'text', 'text_block', 'section_header',
                  'header', 'footer', 'page_header', 'page_footer', 'reference',
                  'reference_content', 'abstract', 'content', 'algorithm',
                  'list_item', 'list', 'equation', 'figure_caption', 'aside_text',
                  'number', 'formula_number'
              ].includes(t)
                  && !!(b.text || b.content);
          }).map((b, i) => ({
              id: b.id || `block_${i}`,
              type: String(b.type || b.role || 'paragraph').toLowerCase(),
              text: b.text || b.content || '',
              confidence: b.confidence,
              page: b.page || 1
          }));
    } else {
        const fromView = collectViewPageTextElements(result.view || {});
        semanticTextBlocks = fromView.length ? fromView : (result.semantic_text_blocks || []);
    }
    const fullText = result.full_text || '';
    const layout = result.layout || {};
    const elements = layout.elements || [];

    // Keep type richness closer to Azure (Title/SectionHeading/Paragraph/...) and
    // prioritize semantic blocks (backend-aggregated) over OCR text lines.
    const textLikeTypes = new Set([
        'doc_title', 'paragraph_title', 'abstract_title', 'reference_title', 'content_title',
        'figure_table_chart_title',
        'title', 'subtitle', 'text', 'paragraph', 'text_block',
        'section_header', 'header', 'footer', 'page_header', 'page_footer',
        'reference', 'reference_content', 'abstract', 'content', 'algorithm',
        'list_item', 'list', 'equation', 'figure_caption', 'table_caption',
        'aside_text', 'number', 'formula_number'
    ]);

    const layoutTextElements = elements.filter(el => {
        const type = String(el.type || el.type_name || '').toLowerCase();
        const textValue =
            (typeof el.text === 'string' ? el.text : '') ||
            (typeof el.content === 'string' ? el.content : '');
        return !!textValue && textLikeTypes.has(type);
    });

    const semanticElements = semanticTextBlocks
        .filter(el => el && typeof el === 'object')
        .map((el, idx) => ({
            id: el.id || `semantic_${idx}`,
            type: String(el.type || 'paragraph').toLowerCase(),
            text: (typeof el.text === 'string' ? el.text : '') || (typeof el.content === 'string' ? el.content : ''),
            confidence: el.confidence,
            page: el.page
        }))
        .filter(el => !!el.text);

    const textElements = semanticElements.length > 0 ? semanticElements : layoutTextElements.map(el => ({
        type: String(el.type || el.type_name || 'paragraph').toLowerCase(),
        text: (typeof el.text === 'string' ? el.text : '') || (typeof el.content === 'string' ? el.content : ''),
        confidence: el.confidence,
        page: el.page
    }));

    const ocrCandidates = textBlocks
        .map(b => normalizePanelParagraphText(b.text || ''))
        .filter(Boolean)
        .sort((a, b) => b.length - a.length);

    // Fixed type display order for the Text panel
    const TYPE_DISPLAY_ORDER = [
        'PageHeader', 'Title', 'SectionHeading', 'FigureCaption',
        'Paragraph', 'Reference', 'Formula', 'ListItem', 'PageFooter'
    ];

    let html = '';

    if (textElements.length > 0) {
        // --- Group by page first, then by type label ---
        const pageMap = {};
        textElements.forEach(el => {
            const pageNum = el.page || 1;
            const rawType = String(el.type || el.type_name || 'paragraph').toLowerCase();
            const typeLabel = toAzureTypeLabel(rawType);

            if (!pageMap[pageNum]) pageMap[pageNum] = {};
            if (!pageMap[pageNum][typeLabel]) pageMap[pageNum][typeLabel] = [];

            let rawText = String(el.text || el.content || '');
            if (isLikelyCollapsedText(rawText) && ocrCandidates.length > 0) {
                const better = ocrCandidates.find(candidate => candidate.length >= rawText.length * 0.65);
                if (better) rawText = better;
            }

            pageMap[pageNum][typeLabel].push({
                text: normalizePanelParagraphText(rawText),
                confidence: el.confidence
            });
        });

        const sortedPages = Object.keys(pageMap).map(Number).sort((a, b) => a - b);
        const multiPage = sortedPages.length > 1;

        sortedPages.forEach(pageNum => {
            if (multiPage) {
                html += `<div class="text-page-section">`;
                html += `<h3 class="text-page-title">Page ${pageNum}</h3>`;
            }

            const groups = pageMap[pageNum];
            const allTypes = Object.keys(groups);
            const sortedTypes = [
                ...TYPE_DISPLAY_ORDER.filter(t => allTypes.includes(t)),
                ...allTypes.filter(t => !TYPE_DISPLAY_ORDER.includes(t)).sort()
            ];

            sortedTypes.forEach(typeLabel => {
                html += '<div class="text-section">';
                html += `<h4 class="text-section-title">${escapeHtml(typeLabel)}</h4>`;

                groups[typeLabel].forEach((item) => {
                    html += '<div class="text-block">';
                    html += '<div class="text-block-header">';
                    html += `<span class="block-type">${escapeHtml(typeLabel)}</span>`;
                    if (item.confidence !== undefined && item.confidence !== null) {
                        const confidence = Number(item.confidence || 0);
                        const confidencePercent = confidence > 1 ? confidence : confidence * 100;
                        if (confidencePercent > 0) {
                            html += `<span class="block-confidence">Confidence: ${confidencePercent.toFixed(1)}%</span>`;
                        }
                    }
                    html += '</div>';
                    html += `<p class="text-block-content" style="white-space: pre-wrap;">${escapeHtml(item.text)}</p>`;
                    html += '</div>';
                });

                html += '</div>';
            });

            if (multiPage) {
                html += '</div>';
            }
        });
    } else if (textBlocks.length > 0) {
        textBlocks.slice(0, 50).forEach((block, index) => {
            const normalizedText = normalizeTextForDisplay(block.text || '');
            html += '<div class="text-block">';
            html += '<div class="text-block-header">';
            html += `<span class="block-type">Text Block ${index + 1}</span>`;
            if (block.confidence !== undefined) {
                html += `<span class="block-confidence">Confidence: ${(block.confidence * 100).toFixed(1)}%</span>`;
            }
            html += '</div>';
            html += `<p class="text-block-content" style="white-space: pre-wrap;">${escapeHtml(normalizedText)}</p>`;
            html += '</div>';
        });
    } else if (fullText) {
        const normalizedText = normalizeTextForDisplay(fullText);
        html += '<div class="text-block">';
        html += '<div class="text-block-header">';
        html += '<span class="block-type">Full Text</span>';
        html += '</div>';
        const displayText = normalizedText.length > 10000 ? normalizedText.substring(0, 10000) + '...' : normalizedText;
        html += `<p class="text-block-content" style="white-space: pre-wrap;">${escapeHtml(displayText)}</p>`;
        html += '</div>';
    }

    if (!html) {
        html = '<div class="empty-state" style="padding: 40px; text-align: center; color: var(--text-tertiary);">No text extracted</div>';
    }

    contentTextContent.innerHTML = html;
}
