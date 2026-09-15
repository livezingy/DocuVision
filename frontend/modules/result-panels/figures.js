/**
 * Figures panel (v1.8.3 B3) - result-panels sub-module (D9).
 * Moved verbatim from app.js, including the top-level style-injection block
 * (46 lines of CSS keyframes, attributed to this sub-module by design rev2).
 * The only non-whitelisted cross-domain dependency is D5's fetchAuthedImage;
 * it is injected at boot via the same-name module-scope binding trick, keeping
 * the call site byte-identical. app.js wires `initResultPanelsFigures({ fetchAuthedImage })`.
 */
import { escapeHtml } from '../utils/dom.js';

let fetchAuthedImage = async function () { return null; };

/**
 * Wire the cross-domain dependency from D5 preview-paging (app.js assembly).
 */
export function initResultPanelsFigures(deps = {}) {
    if (typeof deps.fetchAuthedImage === 'function') {
        fetchAuthedImage = deps.fetchAuthedImage;
    }
}

/**
 * Update Content Figures view.
 *
 * Primary source is result.figures (the P0-2 crop export: items with
 * crop_url). When crops are absent, falls back to layout figure elements so
 * the tab is never empty when the detector saw a figure but export was
 * disabled or failed. Split-figure integrity warnings from the backend are
 * surfaced per-card.
 */
export function updateContentFigures(result) {
    const contentFiguresList = document.getElementById('contentFiguresList');
    if (!contentFiguresList) return;

    const figuresExport = result.figures || {};
    const cropItems = Array.isArray(figuresExport.items) ? figuresExport.items : [];
    const warnings = Array.isArray(figuresExport.warnings) ? figuresExport.warnings : [];
    const warningIds = new Set();
    warnings.forEach(function (w) {
        (w.ids || []).forEach(function (id) { warningIds.add(id); });
    });

    // Layout elements used only for caption fallback (matched by id).
    const layout = result.layout || {};
    const layoutElements = layout.elements || [];

    const hasCrops = cropItems.length > 0;
    if (!hasCrops) {
        const layoutFigTypes = new Set(['figure', 'image', 'chart', 'figure_table_chart', 'picture', 'flowchart']);
        const layoutFigs = layoutElements.filter(el => layoutFigTypes.has(String(el.type || '').toLowerCase()));
        if (layoutFigs.length === 0) {
            const errs = Array.isArray(figuresExport.errors) ? figuresExport.errors : [];
            const msg = errs.length
                ? `Figure export failed: ${escapeHtml(errs[0].reason || 'unknown error')}`
                : 'No figures detected';
            contentFiguresList.innerHTML = `<div class="empty-state" style="padding: 40px; text-align: center; color: var(--text-tertiary);">${msg}</div>`;
            return;
        }
        // No crops (export off / failed) but layout saw figures — headers only,
        // never OCR/caption body text on the card.
        let html = '';
        layoutFigs.forEach((figure, index) => {
            html += '<div class="figure-card">';
            html += '<div class="figure-card-header">';
            html += `<span class="figure-name">Figure ${index + 1}${figure.page ? ` (Page ${figure.page})` : ''}</span>`;
            if (figure.confidence !== undefined) {
                html += `<span style="font-size: 0.75rem; color: var(--text-tertiary);">Confidence: ${(figure.confidence * 100).toFixed(1)}%</span>`;
            }
            html += '</div>';
            html += '<div class="figure-preview">';
            html += '<p style="color: var(--text-tertiary);">Figure detected (crop unavailable)</p>';
            html += '</div></div>';
        });
        contentFiguresList.innerHTML = html;
        return;
    }

    // Render crops with lazy auth-loaded images.
    // Page-by-page navigation mirrors the Tables Tab so multi-figure docs are
    // browsable one card at a time instead of as a long fused list.
    // Gallery shows original crops only. Merged reconstructions stay in the
    // API payload and are offered from the warning banner (false-positive
    // stacked-figure merges must not occupy a carousel slot).
    const allMapped = cropItems.map((item, index) => ({
        id: item.id || `figure_${index + 1}`,
        page: item.page || '?',
        confidence: item.confidence || 0,
        crop_url: item.crop_url || '',
        width_px: item.width_px || 0,
        height_px: item.height_px || 0,
        caption: item.caption || '',
        warned: warningIds.has(item.id),
        is_merged: !!item.is_merged,
        merged_from: item.merged_from || null,
        split_kind: item.split_kind || '',
        index: index
    }));
    window.mergedFigures = allMapped.filter(function (f) { return f.is_merged; });
    window.currentFigures = allMapped.filter(function (f) { return !f.is_merged; });
    window.currentFigureIndex = 0;
    window.viewingMergedIndex = null;

    if (window.currentFigures.length === 0) {
        contentFiguresList.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center; color: var(--text-tertiary);">No figures detected</div>';
        return;
    }

    let html = '';
    const splitWarnings = warnings.filter(function (w) {
        return w.kind === 'possible_vertical_split' || w.kind === 'possible_horizontal_split';
    });
    if (splitWarnings.length > 0 || window.mergedFigures.length > 0) {
        html += '<div class="figure-warnings-banner" id="figureMergedBanner" style="margin-bottom:10px;padding:8px 12px;border-radius:6px;background:rgba(245,158,11,0.10);border:1px solid rgba(245,158,11,0.35);font-size:0.8rem;color:var(--text-secondary);">';
        html += `⚠ ${splitWarnings.length || window.mergedFigures.length} possible split-figure warning(s). Gallery shows original crops only.`;
        window.mergedFigures.forEach(function (m, i) {
            html += ` <button type="button" class="figure-view-merged-btn" data-merged-index="${i}" style="margin-left:8px;padding:4px 8px;font-size:0.75rem;cursor:pointer;">View merged crop (Page ${m.page})</button>`;
        });
        html += ' <button type="button" class="figure-back-originals-btn" hidden style="margin-left:8px;padding:4px 8px;font-size:0.75rem;cursor:pointer;">Back to originals</button>';
        html += '</div>';
    }
    if (window.currentFigures.length > 1) {
        html += '<div class="figure-navigation" style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; padding: 12px; background: var(--bg-tertiary); border-radius: var(--radius-md);">';
        html += '<button class="figure-nav-btn" id="contentPrevFigureBtn" style="display: flex; align-items: center; gap: 6px; padding: 8px 16px; background: var(--bg-elevated); border: 1px solid var(--border-default); border-radius: var(--radius-sm); color: var(--text-secondary); cursor: pointer; transition: all var(--transition-fast);">';
        html += '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="15 18 9 12 15 6"></polyline></svg>';
        html += 'Previous</button>';
        html += `<span style="color: var(--text-primary); font-weight: 500;">Figure <span id="contentCurrentFigureIndex">1</span> of ${window.currentFigures.length}</span>`;
        html += '<button class="figure-nav-btn" id="contentNextFigureBtn" style="display: flex; align-items: center; gap: 6px; padding: 8px 16px; background: var(--bg-elevated); border: 1px solid var(--border-default); border-radius: var(--radius-sm); color: var(--text-secondary); cursor: pointer; transition: all var(--transition-fast);">';
        html += 'Next<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="9 18 15 12 9 6"></polyline></svg></button>';
        html += '</div>';
    }
    html += renderFigureCard(window.currentFigures[0], 0, window.currentFigures.length);
    contentFiguresList.innerHTML = html;

    function loadFigureCardImage(cardEl) {
        if (!cardEl) return;
        const img = cardEl.querySelector('img.figure-crop-img');
        if (!img) return;
        const url = img.dataset.cropUrl;
        if (!url) return;
        fetchAuthedImage(url, img).then(function (objUrl) {
            if (objUrl) img.src = objUrl;
            else img.alt = 'Figure crop unavailable';
        });
    }

    function paintVisibleFigure() {
        const figureCard = contentFiguresList.querySelector('.figure-card');
        if (!figureCard) return;
        const backBtn = contentFiguresList.querySelector('.figure-back-originals-btn');
        if (window.viewingMergedIndex != null && window.mergedFigures[window.viewingMergedIndex]) {
            const m = window.mergedFigures[window.viewingMergedIndex];
            figureCard.outerHTML = renderFigureCard(m, 0, 1);
            if (backBtn) backBtn.hidden = false;
        } else {
            const figs = window.currentFigures;
            const i = window.currentFigureIndex || 0;
            figureCard.outerHTML = renderFigureCard(figs[i], i, figs.length);
            if (backBtn) backBtn.hidden = true;
        }
        loadFigureCardImage(contentFiguresList.querySelector('.figure-card'));
    }

    loadFigureCardImage(contentFiguresList.querySelector('.figure-card'));

    contentFiguresList.querySelectorAll('.figure-view-merged-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            window.viewingMergedIndex = Number(btn.dataset.mergedIndex);
            paintVisibleFigure();
        });
    });
    const backOriginalsBtn = contentFiguresList.querySelector('.figure-back-originals-btn');
    if (backOriginalsBtn) {
        backOriginalsBtn.addEventListener('click', function () {
            window.viewingMergedIndex = null;
            paintVisibleFigure();
        });
    }

    if (window.currentFigures.length > 1) {
        const prevBtn = document.getElementById('contentPrevFigureBtn');
        const nextBtn = document.getElementById('contentNextFigureBtn');
        const currentIndexSpan = document.getElementById('contentCurrentFigureIndex');

        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                if (window.currentFigureIndex > 0) {
                    window.currentFigureIndex--;
                    window.viewingMergedIndex = null;
                    if (currentIndexSpan) currentIndexSpan.textContent = window.currentFigureIndex + 1;
                    paintVisibleFigure();
                    updateFigureNavButtons();
                }
            });
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                if (window.currentFigureIndex < window.currentFigures.length - 1) {
                    window.currentFigureIndex++;
                    window.viewingMergedIndex = null;
                    if (currentIndexSpan) currentIndexSpan.textContent = window.currentFigureIndex + 1;
                    paintVisibleFigure();
                    updateFigureNavButtons();
                }
            });
        }

        function updateFigureNavButtons() {
            if (prevBtn) {
                prevBtn.disabled = window.currentFigureIndex === 0;
                prevBtn.style.opacity = window.currentFigureIndex === 0 ? '0.5' : '1';
                prevBtn.style.cursor = window.currentFigureIndex === 0 ? 'not-allowed' : 'pointer';
            }
            if (nextBtn) {
                nextBtn.disabled = window.currentFigureIndex === window.currentFigures.length - 1;
                nextBtn.style.opacity = window.currentFigureIndex === window.currentFigures.length - 1 ? '0.5' : '1';
                nextBtn.style.cursor = window.currentFigureIndex === window.currentFigures.length - 1 ? 'not-allowed' : 'pointer';
            }
        }

        updateFigureNavButtons();
    }
}

/**
 * Render a single figure card (used by updateContentFigures pagination).
 * Mirrors renderTableCard so the Figures Tab browses one card at a time
 * instead of a fused long list.
 */
export function renderFigureCard(item, index, total) {
    const page = item.page || '?';
    const confidence = item.confidence || 0;
    const cap = String(item.caption || '').trim();
    let html = '<div class="figure-card">';
    html += '<div class="figure-card-header">';
    html += `<span class="figure-name">Figure ${index + 1}${total > 1 ? ` of ${total}` : ''}${page !== '?' ? ` (Page ${page})` : ''}`;
    if (confidence > 0) {
        html += ` <span style="font-size: 0.75rem; color: var(--text-tertiary);">Confidence: ${(confidence * 100).toFixed(1)}%</span>`;
    }
    if (item.warned && !item.is_merged) {
        html += ` <span style="font-size: 0.7rem; color: #f59e0b; margin-left:6px;">⚠ possible split</span>`;
    }
    if (item.is_merged) {
        html += ` <span style="font-size: 0.7rem; color: var(--text-tertiary); margin-left:6px;">(merged reconstruction)</span>`;
    }
    html += '</span>';
    if (cap) {
        const short = cap.length > 80 ? cap.slice(0, 77) + '...' : cap;
        html += `<span class="figure-caption-label" title="${escapeHtml(cap)}" style="font-size:0.75rem;color:var(--text-secondary);font-weight:400;max-width:55%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(short)}</span>`;
    }
    html += '</div>';
    html += '<div class="figure-preview">';
    html += `<img class="figure-crop-img" data-crop-url="${item.crop_url || ''}" alt="Figure ${index + 1} crop" />`;
    if (item.width_px && item.height_px) {
        html += `<p style="font-size:0.7rem;color:var(--text-tertiary);margin-top:4px;">${item.width_px} × ${item.height_px}px</p>`;
    }
    html += '</div></div>';
    return html;
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateX(100px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }

    @keyframes slideOut {
        from {
            opacity: 1;
            transform: translateX(0);
        }
        to {
            opacity: 0;
            transform: translateX(100px);
        }
    }

    @keyframes fadeOut {
        from {
            opacity: 1;
            transform: translateX(0);
        }
        to {
            opacity: 0;
            transform: translateX(-20px);
        }
    }

    .queue-item.failed .queue-item-icon {
        color: #f43f5e;
    }

    .option-badge.new {
        background: linear-gradient(135deg, #06b6d4, #0891b2);
    }
`;
document.head.appendChild(style);
