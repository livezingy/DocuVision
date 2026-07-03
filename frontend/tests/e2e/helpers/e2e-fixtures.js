/**
 * Shared fixture paths for Pro UI E2E (repo samples with tiny fallbacks).
 */

const path = require('path');
const fs = require('fs');

const TINY_PNG_BASE64 =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';

const TINY_PDF_BYTES = Buffer.from(
  [
    '%PDF-1.4',
    '1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj',
    '2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj',
    '3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj',
    'xref',
    '0 4',
    '0000000000 65535 f ',
    '0000000009 00000 n ',
    '0000000052 00000 n ',
    '0000000101 00000 n ',
    'trailer<</Size 4/Root 1 0 R>>',
    'startxref',
    '149',
    '%%EOF',
  ].join('\n'),
  'utf8',
);

function repoRootFromHere() {
  return path.join(__dirname, '..', '..', '..', '..');
}

function ensureFixtureDir() {
  const dir = path.join(__dirname, '..', 'fixtures');
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  return dir;
}

function sampleImagePath() {
  const candidate = path.join(
    repoRootFromHere(),
    'test_data',
    'testfiles',
    'invoices',
    'sample-invoice.png',
  );
  if (fs.existsSync(candidate)) {
    return candidate;
  }
  const fallback = path.join(ensureFixtureDir(), 'tiny.png');
  if (!fs.existsSync(fallback)) {
    fs.writeFileSync(fallback, Buffer.from(TINY_PNG_BASE64, 'base64'));
  }
  return fallback;
}

function samplePdfPath() {
  const candidate = path.join(
    repoRootFromHere(),
    'test_data',
    'testfiles',
    'GeneralFiles',
    'bank_statement_sample.pdf',
  );
  if (fs.existsSync(candidate)) {
    return candidate;
  }
  const fallback = path.join(ensureFixtureDir(), 'tiny.pdf');
  if (!fs.existsSync(fallback)) {
    fs.writeFileSync(fallback, TINY_PDF_BYTES);
  }
  return fallback;
}

module.exports = {
  sampleImagePath,
  samplePdfPath,
  TINY_PDF_BYTES,
};
