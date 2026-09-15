/**
 * geometry.js - Pure bbox / coordinate-space math used by the annotation overlay.
 *
 * Extracted verbatim from app.js in v1.8.3 B0b (no behaviour change).
 */

export function normalizeAnnotationBbox(bbox) {
    if (!bbox) return { x: 0, y: 0, width: 0, height: 0 };

    if (Array.isArray(bbox) && bbox.length >= 4) {
        return {
            x: Number(bbox[0]) || 0,
            y: Number(bbox[1]) || 0,
            width: Math.max((Number(bbox[2]) || 0) - (Number(bbox[0]) || 0), 0),
            height: Math.max((Number(bbox[3]) || 0) - (Number(bbox[1]) || 0), 0)
        };
    }

    if (typeof bbox === 'object') {
        if ('x' in bbox || 'y' in bbox || 'width' in bbox || 'height' in bbox) {
            return {
                x: Number(bbox.x) || 0,
                y: Number(bbox.y) || 0,
                width: Number(bbox.width) || 0,
                height: Number(bbox.height) || 0
            };
        }
        if ('x1' in bbox || 'y1' in bbox || 'x2' in bbox || 'y2' in bbox) {
            const x1 = Number(bbox.x1) || 0;
            const y1 = Number(bbox.y1) || 0;
            const x2 = Number(bbox.x2) || 0;
            const y2 = Number(bbox.y2) || 0;
            return { x: x1, y: y1, width: Math.max(x2 - x1, 0), height: Math.max(y2 - y1, 0) };
        }
    }

    return { x: 0, y: 0, width: 0, height: 0 };
}

export function bboxFromPolygon(polygon) {
    if (!Array.isArray(polygon) || polygon.length === 0) return null;

    let points = [];
    if (Array.isArray(polygon[0])) {
        points = polygon.filter(p => Array.isArray(p) && p.length >= 2).map(p => [Number(p[0]) || 0, Number(p[1]) || 0]);
    } else {
        for (let i = 0; i < polygon.length - 1; i += 2) {
            points.push([Number(polygon[i]) || 0, Number(polygon[i + 1]) || 0]);
        }
    }

    if (points.length === 0) return null;
    const xs = points.map(p => p[0]);
    const ys = points.map(p => p[1]);
    const x1 = Math.min(...xs);
    const y1 = Math.min(...ys);
    const x2 = Math.max(...xs);
    const y2 = Math.max(...ys);
    return { x: x1, y: y1, width: Math.max(0, x2 - x1), height: Math.max(0, y2 - y1) };
}

export function normalizeCoordSpace(value) {
    const v = String(value || '').trim().toLowerCase();
    if (v === 'image_abs_px') return 'image_abs_px';
    if (v === 'image_norm') return 'image_norm';
    return '';
}

export function normalizeBboxToImageMatrix(matrix, coordSpace, imageWidth, imageHeight) {
    const srcSpace = normalizeCoordSpace(coordSpace);

    if (matrix && typeof matrix === 'object') {
        const sx = Number(matrix.scale_x);
        const sy = Number(matrix.scale_y);
        const ox = Number(matrix.offset_x);
        const oy = Number(matrix.offset_y);
        if ([sx, sy, ox, oy].every(Number.isFinite)) {
            return {
                src_space: String(matrix.src_space || srcSpace || 'image_abs_px').toLowerCase(),
                dst_space: String(matrix.dst_space || 'image_abs_px').toLowerCase(),
                scale_x: sx,
                scale_y: sy,
                offset_x: ox,
                offset_y: oy,
            };
        }
    }

    if (srcSpace === 'image_norm' && imageWidth > 0 && imageHeight > 0) {
        return {
            src_space: 'image_norm',
            dst_space: 'image_abs_px',
            scale_x: imageWidth,
            scale_y: imageHeight,
            offset_x: 0,
            offset_y: 0,
        };
    }

    return {
        src_space: srcSpace || 'image_abs_px',
        dst_space: 'image_abs_px',
        scale_x: 1,
        scale_y: 1,
        offset_x: 0,
        offset_y: 0,
    };
}

export function remapBboxToImageSpace(x, y, width, height, matrix) {
    const sx = Number(matrix?.scale_x ?? 1);
    const sy = Number(matrix?.scale_y ?? 1);
    const ox = Number(matrix?.offset_x ?? 0);
    const oy = Number(matrix?.offset_y ?? 0);

    const x1 = sx * x + ox;
    const y1 = sy * y + oy;
    const x2 = sx * (x + width) + ox;
    const y2 = sy * (y + height) + oy;

    const left = Math.min(x1, x2);
    const top = Math.min(y1, y2);
    const w = Math.max(Math.abs(x2 - x1), 0);
    const h = Math.max(Math.abs(y2 - y1), 0);

    return {
        x: left,
        y: top,
        width: w,
        height: h,
    };
}
