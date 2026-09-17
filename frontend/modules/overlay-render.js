/**
 * Document overlay rendering (v1.8.3 B3) - domain module (D10).
 *
 * The geometry half (normalizeAnnotationBbox / bboxFromPolygon / normalizeCoordSpace /
 * normalizeBboxToImageMatrix / remapBboxToImageSpace) already lives in utils/geometry.js
 * (B0b). This module holds the rendering half, moved verbatim.
 *
 * Cross-domain deps are injected at boot because F3 forbids domain->domain imports:
 *   - D5 preview-paging: previewHelpers / resolveResultPageCount /
 *     syncPreviewPaginationControls / revokeCurrentPageImageUrl / getPdfPageImage /
 *     adjustDocumentSize  (injected from app.js now; B4 re-points the wiring to the
 *     preview-nav.js / preview-render.js exports - call sites stay untouched)
 *   - D8 pipeline: fetchTaskBlocks
 *   - D9 result-panels: updateContentText (E9)
 *   - D4 shell-init: initAnnotationInteractions (E10)
 * The module-scope "same-name binding" trick keeps every call site byte-identical;
 * app.js wires `initOverlayRender({ ... })` at module scope.
 */
import { showNotification } from './notifications.js';
import { API_BASE_URL } from './api-config.js';
import {
    currentPreviewPage, currentQueueItem, currentOriginalFileUrl, currentTaskId,
    currentPageImageUrl, lastRenderedAnalysisResult,
    setPreviewPage, setPageImageUrl, setLastRenderedAnalysisResult, setLastFetchedBlocks,
} from './preview-state.js';
import { escapeHtml } from './utils/dom.js';
import { formatAzureRoleLabel } from './utils/text.js';

let enableOverlaySha256Validation = false;
const overlayLayerVisibility = {
    text: true,
    table: true,
    figure: true,
    header_footer: true,
    list: true,
    readingOrder: true,
};

let previewHelpers = function () { return {}; };
let resolveResultPageCount = function () { return 1; };
let syncPreviewPaginationControls = function () {};
let revokeCurrentPageImageUrl = function () {};
let getPdfPageImage = async function () { return null; };
let adjustDocumentSize = function () {};
let fetchTaskBlocks = async function () { return null; };
let updateContentText = function () {};
let initAnnotationInteractions = function () {};

/**
 * Wire the cross-domain dependencies (app.js assembly).
 */
export function initOverlayRender(deps = {}) {
    if (typeof deps.previewHelpers === 'function') previewHelpers = deps.previewHelpers;
    if (typeof deps.resolveResultPageCount === 'function') resolveResultPageCount = deps.resolveResultPageCount;
    if (typeof deps.syncPreviewPaginationControls === 'function') syncPreviewPaginationControls = deps.syncPreviewPaginationControls;
    if (typeof deps.revokeCurrentPageImageUrl === 'function') revokeCurrentPageImageUrl = deps.revokeCurrentPageImageUrl;
    if (typeof deps.getPdfPageImage === 'function') getPdfPageImage = deps.getPdfPageImage;
    if (typeof deps.adjustDocumentSize === 'function') adjustDocumentSize = deps.adjustDocumentSize;
    if (typeof deps.fetchTaskBlocks === 'function') fetchTaskBlocks = deps.fetchTaskBlocks;
    if (typeof deps.updateContentText === 'function') updateContentText = deps.updateContentText;
    if (typeof deps.initAnnotationInteractions === 'function') initAnnotationInteractions = deps.initAnnotationInteractions;
}

/**
 * Return SVG stroke/fill colors for a given block type.
 */
export function getSvgAnnotationColors(type) {
    const colorMap = {
        title:       { stroke: '#3b82f6', fill: 'rgba(59,130,246,0.10)' },
        subtitle:    { stroke: '#3b82f6', fill: 'rgba(59,130,246,0.10)' },
        heading:     { stroke: '#3b82f6', fill: 'rgba(59,130,246,0.10)' },
        paragraph:   { stroke: '#10b981', fill: 'rgba(16,185,129,0.08)' },
        text:        { stroke: '#10b981', fill: 'rgba(16,185,129,0.08)' },
        text_block:  { stroke: '#10b981', fill: 'rgba(16,185,129,0.08)' },
        table:       { stroke: '#f59e0b', fill: 'rgba(245,158,11,0.10)' },
        figure:      { stroke: '#ec4899', fill: 'rgba(236,72,153,0.10)' },
        image:       { stroke: '#ec4899', fill: 'rgba(236,72,153,0.10)' },
        header:      { stroke: '#8b5cf6', fill: 'rgba(139,92,246,0.08)' },
        page_header: { stroke: '#8b5cf6', fill: 'rgba(139,92,246,0.08)' },
        footer:      { stroke: '#6b7280', fill: 'rgba(107,114,128,0.08)' },
        page_footer: { stroke: '#6b7280', fill: 'rgba(107,114,128,0.08)' },
        list:        { stroke: '#06b6d4', fill: 'rgba(6,182,212,0.08)'  },
        list_item:   { stroke: '#06b6d4', fill: 'rgba(6,182,212,0.08)'  },
    };
    return colorMap[type] || { stroke: '#6b7280', fill: 'rgba(107,114,128,0.08)' };
}

export function getPageImageMeta(result, pageNum = 1) {
    const docInfo = (result && result.document_info) ? result.document_info : {};
    const meta = docInfo.page_image_meta;
    if (!meta || typeof meta !== 'object') return null;

    if (Array.isArray(meta.pages)) {
        const match = meta.pages.find(p => Number(p.page || 1) === Number(pageNum));
        return match || null;
    }

    return meta;
}

export async function computeImageSha256Hex(image) {
    const src = image?.currentSrc || image?.src || '';
    if (!src || !window.crypto || !window.crypto.subtle) return '';

    const response = await fetch(src, { cache: 'no-store' });
    if (!response.ok) return '';

    const buffer = await response.arrayBuffer();
    const digest = await window.crypto.subtle.digest('SHA-256', buffer);
    return Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, '0')).join('');
}

export async function validateImageCoordinateBinding(image, result, pageNum = 1) {
    if (!image || !result) return true;

    const expected = getPageImageMeta(result, pageNum);
    if (!expected) return true;

    const expectedWidth = Number(expected.width_px || 0);
    const expectedHeight = Number(expected.height_px || 0);
    if (expectedWidth <= 0 || expectedHeight <= 0) return true;

    const actualWidth = Number(image.naturalWidth || 0);
    const actualHeight = Number(image.naturalHeight || 0);

    if (actualWidth !== expectedWidth || actualHeight !== expectedHeight) {
        console.error(
            `[Layout] Image binding mismatch: expected ${expectedWidth}x${expectedHeight}, got ${actualWidth}x${actualHeight}`,
            expected
        );
        showNotification('Image size does not match coordinate metadata. Skipping overlays to avoid offset.', 'warning');
        return false;
    }

    if (!enableOverlaySha256Validation) {
        return true;
    }

    const expectedSha = String(expected.sha256 || '').trim().toLowerCase();
    if (!expectedSha) {
        return true;
    }

    try {
        const actualSha = (await computeImageSha256Hex(image)).toLowerCase();
        if (!actualSha) {
            showNotification('Unable to compute image SHA256. Skipping SHA verification.', 'info');
            return true;
        }
        if (actualSha !== expectedSha) {
            console.error(`[Layout] Image SHA256 mismatch: expected=${expectedSha}, actual=${actualSha}`);
            showNotification('Image SHA256 mismatch with coordinate metadata. Skipping overlays.', 'warning');
            return false;
        }
    } catch (error) {
        console.warn('[Layout] SHA256 verification failed:', error);
        showNotification('SHA256 verification failed. Proceeding with size validation only.', 'info');
    }

    return true;
}

export function getOverlayLayerType(type) {
    const normalized = String(type || '').toLowerCase();
    if (['table'].includes(normalized)) return 'table';
    if (['figure', 'image', 'chart', 'figure_title', 'figure_caption', 'table_caption', 'figure_table_chart_title'].includes(normalized)) return 'figure';
    if (['header', 'footer', 'page_header', 'page_footer'].includes(normalized)) return 'header_footer';
    if (['list', 'list_item'].includes(normalized)) return 'list';
    return 'text';
}

export function shouldRenderOverlayType(type) {
    const layerType = getOverlayLayerType(type);
    return overlayLayerVisibility[layerType] !== false;
}

/**
 * Render document with annotations overlay
 */
export async function renderDocumentWithAnnotations(result, pageNum = currentPreviewPage) {
    const documentPage = document.getElementById('documentPage');
    if (!documentPage) return;

    setLastRenderedAnalysisResult(result);

    const totalPages = resolveResultPageCount(result, currentQueueItem);
    const page = previewHelpers().normalizePreviewPage
        ? previewHelpers().normalizePreviewPage(pageNum, totalPages)
        : Math.min(Math.max(1, pageNum), totalPages);
    setPreviewPage(page);
    syncPreviewPaginationControls(totalPages, page);
    setLastFetchedBlocks(null);

    let imageUrl = currentOriginalFileUrl;
    if (currentTaskId) {
        try {
            // Always use backend page-image endpoint after analysis so the displayed
            // image stays in the same coordinate space as /blocks bboxes.
            revokeCurrentPageImageUrl();
            setPageImageUrl(await getPdfPageImage(currentTaskId, page));
            imageUrl = currentPageImageUrl;
        } catch (error) {
            console.error('Failed to get backend page image:', error);
            imageUrl = `${API_BASE_URL}/tasks/${currentTaskId}/page-image/${page}`;
        }
    }

    const html = `
        <div class="document-preview-content">
            <div class="svg-annotation-wrapper">
                <img id="documentImage" src="${imageUrl || ''}"
                     style="display:block; max-width:100%; height:auto; border-radius:8px;"
                     alt="Document">
                <svg id="annotationSvgOverlay"
                     style="position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;"
                     preserveAspectRatio="none"></svg>
            </div>
        </div>`;

    documentPage.innerHTML = html;

    const image = document.getElementById('documentImage');
    if (!image) return;

    const renderBlocks = async () => {
        adjustDocumentSize();
        if (!currentTaskId) return;

        const blocks = await fetchTaskBlocks(currentTaskId, page);
        if (!blocks || !Array.isArray(blocks.blocks) || blocks.blocks.length === 0) return;
        setLastFetchedBlocks(blocks);

        const svg = document.getElementById('annotationSvgOverlay');
        if (!svg) return;

        const imgW = Number(blocks.image_width) || image.naturalWidth || 1;
        const imgH = Number(blocks.image_height) || image.naturalHeight || 1;
        svg.setAttribute('viewBox', `0 0 ${imgW} ${imgH}`);

        const svgNS = 'http://www.w3.org/2000/svg';
        blocks.blocks.forEach((block, idx) => {
            const bbox = block.bbox || [];
            const x1 = Number(bbox[0] || 0);
            const y1 = Number(bbox[1] || 0);
            const x2 = Number(bbox[2] || 0);
            const y2 = Number(bbox[3] || 0);
            const w = Math.max(0, x2 - x1);
            const h = Math.max(0, y2 - y1);
            if (w <= 0 || h <= 0) return;

            const type = String(block.type || block.role || 'paragraph').toLowerCase();
            if (!shouldRenderOverlayType(type)) return;

            const colors = getSvgAnnotationColors(type);
            const role = formatAzureRoleLabel(type);
            const text = String(block.text || block.content || '');
            const displayContent = text.length > 100 ? text.substring(0, 100) + '...' : text;
            const rawConf = Number(block.confidence || 0);
            const confidencePercent = rawConf > 1 ? rawConf : rawConf * 100;
            const bboxStr = `${x1.toFixed(0)}, ${y1.toFixed(0)}, ${w.toFixed(0)} × ${h.toFixed(0)}`;

            // GLM trial P0-C: reading-order overlay. The /blocks endpoint
            // surfaces reading_order from the envelope view layer; we draw a
            // small badge at the top-left of text/title regions so
            // multi-column reading sequence is visible. Figure/table boxes
            // keep the number in the tooltip only (PaddleX often leaves
            // image block_order as None, so a badge would be a fallback
            // counter). Gated by the readingOrder overlay toggle.
            const readingOrder = Number(block.reading_order);
            const hasReadingOrder = !isNaN(readingOrder) && readingOrder > 0;

            const tooltipData = { role, content: text, displayContent, bbox: bboxStr, confidence: confidencePercent, readingOrder: hasReadingOrder ? readingOrder : null };

            const rect = document.createElementNS(svgNS, 'rect');
            rect.setAttribute('x', x1);
            rect.setAttribute('y', y1);
            rect.setAttribute('width', w);
            rect.setAttribute('height', h);
            rect.setAttribute('fill', colors.fill);
            rect.setAttribute('stroke', colors.stroke);
            rect.setAttribute('stroke-width', '2');
            rect.setAttribute('rx', '3');
            rect.classList.add('svg-annotation');
            rect.dataset.tooltipData = JSON.stringify(tooltipData);
            rect.dataset.elementType = type;
            rect.dataset.elementIndex = String(idx);
            rect.style.pointerEvents = 'auto';
            rect.style.cursor = 'pointer';
            svg.appendChild(rect);

            // Reading-order badge (P0-C). Drawn after the rect so it sits
            // on top; pointer-events disabled so it never steals rect clicks.
            const overlayLayer = getOverlayLayerType(type);
            if (hasReadingOrder && overlayLayerVisibility.readingOrder !== false && overlayLayer === 'text') {
                const badgeFontSize = Math.max(12, Math.min(w, h) * 0.12);
                const label = document.createElementNS(svgNS, 'text');
                label.setAttribute('x', x1 + 4);
                label.setAttribute('y', y1 + badgeFontSize + 2);
                label.setAttribute('font-size', badgeFontSize);
                label.setAttribute('font-family', 'Inter, system-ui, sans-serif');
                label.setAttribute('font-weight', '700');
                label.setAttribute('fill', colors.stroke);
                label.setAttribute('stroke', '#ffffff');
                label.setAttribute('stroke-width', '0.4');
                label.setAttribute('paint-order', 'stroke');
                label.classList.add('svg-reading-order-badge');
                label.dataset.elementType = type;
                label.style.pointerEvents = 'none';
                label.textContent = String(readingOrder);
                svg.appendChild(label);
            }
        });

        if (lastRenderedAnalysisResult) {
            updateContentText(lastRenderedAnalysisResult);
        }
        initAnnotationInteractions();
    };

    if (image.complete && image.naturalWidth > 0) {
        await renderBlocks();
    } else {
        image.addEventListener('load', renderBlocks, { once: true });
    }
}

/**
 * Render text preview (fallback)
 */
export function renderTextPreview(result) {
    const documentPage = document.getElementById('documentPage');
    if (!documentPage) return;

    const docInfo = result.document_info || {};
    const fileName = docInfo.file_name || 'Document';
    const pages = docInfo.pages || result.layout?.total_pages || result.page_count || 1;

    // Get text content for preview (Analysis view)
    const textBlocks = result.text_blocks || [];
    const fullText = result.full_text || '';
    const layout = result.layout || {};
    const elements = layout.elements || [];

    // Try to get text from various sources
    let previewText = '';
    if (fullText) {
        previewText = fullText.substring(0, 2000); // Limit preview length
    } else if (textBlocks.length > 0) {
        previewText = textBlocks.slice(0, 10).map(b => b.text || '').join('\n\n').substring(0, 2000);
    } else if (elements.length > 0) {
        const textElements = elements.filter(el => el.text && el.type !== 'table').slice(0, 10);
        previewText = textElements.map(el => el.text).join('\n\n').substring(0, 2000);
    }

    // Create document preview with extracted text content (Analysis view)
    let html = '<div class="document-preview-content">';
    html += '<div class="preview-header-info" style="margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #e5e7eb;">';
    html += `<h3 style="margin: 0 0 8px 0; color: #1f2937; font-size: 18px;">${escapeHtml(fileName)} (Text Preview)</h3>`;
    html += `<p style="margin: 0; color: #6b7280; font-size: 14px;">${pages} page${pages !== 1 ? 's' : ''} · Extracted Text</p>`;
    html += '</div>';

    if (previewText) {
        html += '<div class="preview-text-content" style="padding: 20px; background: #f9fafb; border-radius: 8px; max-height: 600px; overflow-y: auto;">';
        html += '<div style="white-space: pre-wrap; line-height: 1.6; color: #374151; font-size: 14px;">';
        html += escapeHtml(previewText);
        if ((fullText && fullText.length > 2000) || (textBlocks.length > 10) || (elements.length > 10)) {
            html += '<p style="margin-top: 15px; color: #6b7280; font-style: italic;">...</p>';
            html += '<p style="color: #6b7280; font-size: 12px;">(Preview truncated. Use the Text tab to view full content.)</p>';
        }
        html += '</div>';
        html += '</div>';
    } else {
        html += '<div class="preview-text-preview" style="padding: 40px; text-align: center; color: #6b7280;">';
        html += '<p>No text content available for preview</p>';
        html += '<p style="font-size: 14px; margin-top: 10px;">Use the tabs above to view structure, text, and tables</p>';
        html += '</div>';
    }

    html += '</div>';
    documentPage.innerHTML = html;
}

/**
 * Highlight corresponding item in results panel
 */
export function highlightResultItem(elementType, elementIndex) {
    // This would scroll to and highlight the corresponding item in the structure view
    // Implementation depends on structure view structure
    console.log('Highlighting:', elementType, elementIndex);
}
