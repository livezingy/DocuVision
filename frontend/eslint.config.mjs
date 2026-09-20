// ESLint flat config - P-010 staged introduction (CI is NOT wired in this batch).
//
// `.mjs` on purpose: `playwright.config.js` is CommonJS (`require` / `module.exports`),
// so adding `"type": "module"` to package.json would break it, while a plain `.js`
// config makes Node warn on every run (package.json has no module type).
//
// Scope (P-010 complete): app.js + modules/** + shared/** (batch 1) and tests/** (batch 2,
// 2026-09-20). Tooling configs stay out: they are CommonJS one-offs with their own globals
// and carry no dead-code signal.
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
        // Tooling configs only - deliberately not linted (CommonJS one-offs with their own
        // globals, no dead-code signal).
        ignores: [
            'node_modules/**',
            'test-results/**',
            'playwright-report/**',
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
    {
        // Batch 2: unit tests are ESM running under jsdom - browser globals, same rules.
        files: ['tests/unit/**/*.js'],
        languageOptions: {
            ecmaVersion: 2023,
            sourceType: 'module',
            globals: {
                ...globals.browser,
            },
        },
        rules: {
            'no-unused-vars': ['error', { args: 'none' }],
            'no-undef': 'error',
        },
    },
    {
        // Batch 2: e2e specs + helpers are CommonJS running in Node (Playwright test
        // runner) - node globals, same rules.
        files: ['tests/e2e/**/*.js'],
        languageOptions: {
            ecmaVersion: 2023,
            sourceType: 'commonjs',
            globals: {
                ...globals.node,
            },
        },
        rules: {
            'no-unused-vars': ['error', { args: 'none' }],
            'no-undef': 'error',
        },
    },
];
