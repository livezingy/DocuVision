/**
 * Unit tests for modules/utils/geometry.js (v1.8.3 B0b extraction).
 *
 * Covers the v1.8 / v1.8.1 coordinate-space regression area: preprocessed-space and
 * normalised-space bboxes must map to absolute image pixels deterministically.
 */
import { describe, it, expect } from 'vitest';
import {
    normalizeAnnotationBbox,
    bboxFromPolygon,
    normalizeCoordSpace,
    normalizeBboxToImageMatrix,
    remapBboxToImageSpace,
} from '../../modules/utils/geometry.js';

describe('normalizeAnnotationBbox', () => {
    it('returns zeros for missing input', () => {
        expect(normalizeAnnotationBbox(null)).toEqual({ x: 0, y: 0, width: 0, height: 0 });
        expect(normalizeAnnotationBbox(undefined)).toEqual({ x: 0, y: 0, width: 0, height: 0 });
        expect(normalizeAnnotationBbox('nope')).toEqual({ x: 0, y: 0, width: 0, height: 0 });
    });

    it('converts an [x1, y1, x2, y2] array into x/y/width/height', () => {
        expect(normalizeAnnotationBbox([10, 20, 40, 60])).toEqual({
            x: 10, y: 20, width: 30, height: 40,
        });
    });

    it('clamps inverted corner arrays to zero size instead of negative', () => {
        expect(normalizeAnnotationBbox([40, 60, 10, 20])).toEqual({
            x: 40, y: 60, width: 0, height: 0,
        });
    });

    it('accepts an object with x/y/width/height and coerces strings', () => {
        expect(normalizeAnnotationBbox({ x: '5', y: '6', width: '7', height: '8' })).toEqual({
            x: 5, y: 6, width: 7, height: 8,
        });
    });

    it('accepts an object with x1/y1/x2/y2 corners', () => {
        expect(normalizeAnnotationBbox({ x1: 1, y1: 2, x2: 11, y2: 22 })).toEqual({
            x: 1, y: 2, width: 10, height: 20,
        });
    });

    it('returns zeros for an object without any known key', () => {
        expect(normalizeAnnotationBbox({})).toEqual({ x: 0, y: 0, width: 0, height: 0 });
    });
});

describe('bboxFromPolygon', () => {
    it('computes the bounding box of a flat coordinate list', () => {
        expect(bboxFromPolygon([1, 2, 5, 8])).toEqual({ x: 1, y: 2, width: 4, height: 6 });
    });

    it('computes the bounding box of a nested point list', () => {
        expect(bboxFromPolygon([[0, 0], [10, 0], [10, 5]])).toEqual({
            x: 0, y: 0, width: 10, height: 5,
        });
    });

    it('returns null for empty or malformed polygons', () => {
        expect(bboxFromPolygon([])).toBeNull();
        expect(bboxFromPolygon(null)).toBeNull();
        expect(bboxFromPolygon([[1]])).toBeNull();
    });
});

describe('normalizeCoordSpace', () => {
    it('accepts the two known spaces, case/whitespace insensitive', () => {
        expect(normalizeCoordSpace('image_abs_px')).toBe('image_abs_px');
        expect(normalizeCoordSpace('  IMAGE_NORM ')).toBe('image_norm');
    });

    it('returns an empty string for unknown spaces', () => {
        expect(normalizeCoordSpace('preprocessed')).toBe('');
        expect(normalizeCoordSpace(undefined)).toBe('');
    });
});

describe('normalizeBboxToImageMatrix', () => {
    it('passes an explicit finite matrix through, lowercasing the spaces', () => {
        expect(normalizeBboxToImageMatrix(
            { scale_x: 2, scale_y: 3, offset_x: 1, offset_y: 4, src_space: 'IMAGE_NORM', dst_space: 'image_abs_px' },
            'image_norm', 100, 200,
        )).toEqual({
            src_space: 'image_norm', dst_space: 'image_abs_px',
            scale_x: 2, scale_y: 3, offset_x: 1, offset_y: 4,
        });
    });

    it('derives scale from the image size for image_norm input', () => {
        expect(normalizeBboxToImageMatrix(null, 'image_norm', 100, 200)).toEqual({
            src_space: 'image_norm', dst_space: 'image_abs_px',
            scale_x: 100, scale_y: 200, offset_x: 0, offset_y: 0,
        });
    });

    it('falls back to identity when the matrix is incomplete', () => {
        expect(normalizeBboxToImageMatrix({ scale_x: 'a' }, 'image_abs_px', 100, 200)).toEqual({
            src_space: 'image_abs_px', dst_space: 'image_abs_px',
            scale_x: 1, scale_y: 1, offset_x: 0, offset_y: 0,
        });
    });
});

describe('remapBboxToImageSpace', () => {
    it('applies scale then offset (normalised -> absolute pixels)', () => {
        expect(remapBboxToImageSpace(10, 20, 30, 40, {
            scale_x: 2, scale_y: 0.5, offset_x: 5, offset_y: -1,
        })).toEqual({ x: 25, y: 9, width: 60, height: 20 });
    });

    it('behaves as identity without a matrix', () => {
        expect(remapBboxToImageSpace(3, 4, 5, 6, null)).toEqual({
            x: 3, y: 4, width: 5, height: 6,
        });
    });

    it('keeps the box non-negative under a negative scale', () => {
        expect(remapBboxToImageSpace(10, 20, 30, 40, { scale_x: -1, scale_y: 1 })).toEqual({
            x: -40, y: 20, width: 30, height: 40,
        });
    });
});
