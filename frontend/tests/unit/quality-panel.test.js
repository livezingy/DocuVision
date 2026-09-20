/**
 * v1.9 S1 (P-007, plan B) - renderQualityPanelPro KIE gating, 4 states.
 *
 * Judgment is split in two (2026-09-20 adjudication, see docs/architecture/v1.9-roadmap.md S1):
 * - summary lines (`KIE confidence` / `KIE fields`) gate on `kie_confidence_source != ""`,
 *   which the orchestrator guarantees non-empty only on attempted && succeeded - failure
 *   paths (runtime_error / skipped_doc_type, all attempted=True) must not show "0%";
 * - KIE warning blocks (kie_error_message / kie_production_reason) gate on kieAttempted -
 *   failure / skip reasons are useful, non-KIE layout tasks show no KIE meta at all.
 *
 * Uses jsdom (vitest's default browser-like environment) to simulate the DOM.
 */
import { beforeEach, describe, it, expect } from 'vitest';
import { renderQualityPanelPro } from '../../modules/result-panels/quality.js';

function setupDOM() {
    document.body.innerHTML = `<div id="qualityPanel" class="hidden"></div>`;
}

function makeResult(quality, extra = {}) {
    return { view: { tables: [] }, quality, ...extra };
}

describe('renderQualityPanelPro KIE gating (P-007)', () => {
    beforeEach(setupDOM);

    it('layout task (KIE never attempted): no KIE lines, panel hidden', () => {
        const panel = document.getElementById('qualityPanel');
        renderQualityPanelPro(makeResult({
            kie_attempted: false,
            kie_stage: '',
            kie_confidence_source: '',
            kie_confidence_avg: 0.0,
            kie_fields_count: 0,
        }));
        expect(panel.classList.contains('hidden')).toBe(true);
        expect(panel.textContent).not.toContain('KIE confidence');
        expect(panel.textContent).not.toContain('KIE fields');
    });

    it('KIE task completed: summary shows confidence + fields', () => {
        const panel = document.getElementById('qualityPanel');
        renderQualityPanelPro(makeResult({
            kie_attempted: true,
            kie_stage: 'completed',
            kie_confidence_source: 'qwen2.5-vl',
            kie_confidence_avg: 0.873,
            kie_fields_count: 12,
            kie_production_hit: true,
        }));
        expect(panel.classList.contains('hidden')).toBe(false);
        expect(panel.textContent).toContain('KIE confidence: 87%');
        expect(panel.textContent).toContain('KIE fields: 12');
    });

    it('KIE runtime_error: no summary lines but the warning block stays', () => {
        const panel = document.getElementById('qualityPanel');
        renderQualityPanelPro(makeResult({
            kie_attempted: true,
            kie_stage: 'runtime_error',
            kie_confidence_source: '',
            kie_confidence_avg: 0.0,
            kie_fields_count: 0,
            kie_error_message: 'KIE engine failed: model load error',
        }));
        expect(panel.classList.contains('hidden')).toBe(false);
        expect(panel.textContent).not.toContain('KIE confidence');
        expect(panel.textContent).not.toContain('KIE fields');
        expect(panel.textContent).toContain('kie_error');
        expect(panel.textContent).toContain('KIE engine failed: model load error');
    });

    it('KIE skipped_doc_type: no summary lines but the warning block stays', () => {
        const panel = document.getElementById('qualityPanel');
        renderQualityPanelPro(makeResult({
            kie_attempted: true,
            kie_stage: 'skipped_doc_type',
            kie_confidence_source: '',
            kie_confidence_avg: 0.0,
            kie_fields_count: 0,
            kie_error_message: 'Document type is not KIE-eligible',
        }));
        expect(panel.classList.contains('hidden')).toBe(false);
        expect(panel.textContent).not.toContain('KIE confidence');
        expect(panel.textContent).not.toContain('KIE fields');
        expect(panel.textContent).toContain('kie_error');
        expect(panel.textContent).toContain('Document type is not KIE-eligible');
    });
});
