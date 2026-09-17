// ESLint flat config - P-010 staged introduction (CI is NOT wired in this batch).
//
// `.mjs` on purpose: `playwright.config.js` is CommonJS (`require` / `module.exports`),
// so adding `"type": "module"` to package.json would break it, while a plain `.js`
// config makes Node warn on every run (package.json has no module type).
//
// Scope is deliberately the FIRST batch only: app.js + modules/** + shared/**.
// frontend/tests/** is the second batch and is ignored below, as are tooling configs.
// Only two high-value rules are on:
//   * no-unused-vars with args:"none" - `initXxx({ deps })` injects a dependency bag a
//     module may legitimately not consume, so unused *parameters* are the norm here;
//     an unused variable / import is the real signal (the P-008 dead-code class).
//   * no-undef with real globals - without the browser set the 33 modules flood the
//     report with `document` / `window` / `fetch` positives.
// The four extra globals are deliberate cross-script contracts, not accidents:
// shared/export-ui.js / demo-postprocess.js / ui-features.js publish them on `window`
// (classic scripts loaded by index.html, outside the ESM graph), and `katex` comes from
// the jsDelivr CDN tag in index.html.
// "Clear to zero, then wire CI" is P-010 stage 3 (see docs/R&D/PENDING.md).
import globals from 'globals';

export default [
    {
        // Second batch (tests) + tooling: intentionally not linted in this pass.
        ignores: [
            'node_modules/**',
            'test-results/**',
            'playwright-report/**',
            'tests/**',
            'vitest.config.js',
            'playwright.config.js',
            'eslint.config.mjs',
        ],
    },
    {
        files: ['app.js', 'modules/**/*.js', 'shared/**/*.js'],
        languageOptions: {
            ecmaVersion: 2023,
            sourceType: 'module',
            globals: {
                ...globals.browser,
                DocuVisionExport: 'readonly',
                DocuVisionDemo: 'readonly',
                DocuVisionUiFeatures: 'readonly',
                katex: 'readonly',
            },
        },
        rules: {
            'no-unused-vars': ['error', { args: 'none' }],
            'no-undef': 'error',
        },
    },
];
