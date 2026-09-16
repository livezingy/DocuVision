/**
 * text.js - Pure text / role-label normalisation helpers.
 *
 * Extracted verbatim from app.js in v1.8.3 B0b (no behaviour change).
 */

export function formatAzureRoleLabel(type) {
    const normalized = String(type || 'paragraph').toLowerCase();
    const roleMap = {
        doc_title: 'Title',
        paragraph_title: 'SectionHeading',
        abstract_title: 'SectionHeading',
        reference_title: 'SectionHeading',
        content_title: 'SectionHeading',
        figure_table_chart_title: 'FigureCaption',
        page_header: 'PageHeader',
        page_footer: 'PageFooter',
        section_header: 'SectionHeading',
        table_header: 'TableHeader',
        figure_caption: 'FigureCaption',
        list_item: 'ListItem',
        text_block: 'Paragraph',
        text: 'Paragraph',
        paragraph: 'Paragraph',
        title: 'Title',
        subtitle: 'Subtitle',
        table: 'Table',
        figure: 'Figure',
        image: 'Figure',
        header: 'PageHeader',
        footer: 'PageFooter',
        reference: 'Reference',
        equation: 'Formula',
        list: 'ListItem'
    };

    if (roleMap[normalized]) {
        return roleMap[normalized];
    }

    return normalized
        .split('_')
        .map(p => p ? p.charAt(0).toUpperCase() + p.slice(1) : '')
        .join('');
}

/**
 * Normalize text to ensure proper spacing between words
 */
export function normalizeTextForDisplay(text) {
    if (!text) return text;

    // Add space between lowercase letter and uppercase letter (word boundary)
    text = text.replace(/([a-z])([A-Z])/g, '$1 $2');

    // Add space between letter and number (if not already spaced)
    text = text.replace(/([a-zA-Z])(\d)/g, '$1 $2');
    text = text.replace(/(\d)([a-zA-Z])/g, '$1 $2');

    // Clean up multiple spaces
    text = text.replace(/ +/g, ' ');

    return text.trim();
}

export function normalizePanelParagraphText(text) {
    const value = normalizeTextForDisplay(text || '');
    if (!value) return value;

    // Flatten OCR line breaks for panel readability while keeping sentence spacing.
    return value
        .replace(/\r\n/g, '\n')
        .replace(/[ \t]*\n[ \t]*/g, ' ')
        .replace(/ +/g, ' ')
        .trim();
}

export function isLikelyCollapsedText(text) {
    const value = String(text || '');
    if (!value) return false;

    const noSpaceLength = value.replace(/\s+/g, '').length;
    const spaceCount = (value.match(/\s/g) || []).length;

    // Long text with almost no spaces is usually collapsed OCR text.
    if (noSpaceLength >= 40 && spaceCount <= 1) {
        return true;
    }

    // Long alpha chunks without spacing are suspicious.
    if (/[A-Za-z]{25,}/.test(value)) {
        return true;
    }

    return false;
}

export function toAzureTypeLabel(type) {
    const normalized = String(type || 'paragraph').toLowerCase();
    const map = {
        doc_title: 'Title',
        paragraph_title: 'SectionHeading',
        abstract_title: 'SectionHeading',
        reference_title: 'SectionHeading',
        content_title: 'SectionHeading',
        figure_table_chart_title: 'FigureCaption',
        table_caption: 'FigureCaption',
        page_header: 'PageHeader',
        page_footer: 'PageFooter',
        section_header: 'SectionHeading',
        table_header: 'TableHeader',
        figure_caption: 'FigureCaption',
        list_item: 'ListItem',
        text: 'Paragraph',
        paragraph: 'Paragraph',
        text_block: 'Paragraph',
        title: 'Title',
        subtitle: 'Subtitle',
        table: 'Table',
        figure: 'Figure',
        image: 'Figure',
        header: 'PageHeader',
        footer: 'PageFooter',
        equation: 'Formula',
        list: 'ListItem',
        reference: 'Reference'
    };

    return map[normalized] || normalized
        .split('_')
        .map(p => p ? p.charAt(0).toUpperCase() + p.slice(1) : '')
        .join('');
}
