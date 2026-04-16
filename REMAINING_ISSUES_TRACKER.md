# Remaining Issues Tracker

Last updated: 2026-04-10
Branch: feature/main-followup-remaining-issues
Owner: DocuVision Team

## Objective
Track the remaining post-main stabilization work after Phase 2 convergence.

## Scope and Acceptance

### 1) KIE field extraction quality
- [x] Add 3-5 invoice samples with different layouts.
- [x] Define acceptance rule when kie_stage=completed: allow kie_fields_count=0 or require >0.
- [x] Record field hit/miss report per sample.
- [x] Add one regression test for the chosen acceptance rule.

Execution artifacts:
- Acceptance criteria: `backend/tests/KIE_ACCEPTANCE_CRITERIA.md`
- Regression/smoke skeleton: `backend/tests/test_kie_acceptance_baseline.py`
- Report generator: `backend/tests/generate_kie_hit_miss_report.py`
- Latest JSON report: `backend/tests/reports/kie_hit_miss_report.json`
- Latest Markdown report: `backend/tests/reports/kie_hit_miss_report.md`
- Ongoing docs tracker: `docs/architecture/KIE_TEST_RUN_TRACKER.md`

Latest run snapshot:
- generated_at_utc: 2026-04-10T00:19:43.010801+00:00
- base_url: http://127.0.0.1:8000
- summary: total=3, accepted=0, hit=0, miss=0, error=3
- note: all three samples returned submit_status_code=502 in current environment

### 2) Raw response contract stability
- [ ] Keep contract: return_raw=false => raw={}.
- [ ] Keep contract: return_raw=true => raw contains raw layer.
- [ ] Add API contract tests for both branches.
- [ ] Add CI check to prevent schema default refill regressions.

### 3) Coordinate-space policy stability
- [ ] Keep service default: use_doc_unwarping=false.
- [ ] Keep response contract: preprocessing.coordinate_space=original.
- [ ] Add startup log line that prints active coordinate policy.
- [ ] Add regression test for non-rotated and rotated page samples.

### 4) Text quality follow-up
- [ ] Build a small sample set for multi-line English spacing behavior.
- [ ] Compare content/text/raw outputs and document differences.
- [ ] Confirm whether issue is upstream model behavior and record workaround guidance.

### 5) Branch and release governance
- [ ] Confirm default branch is main.
- [ ] Enable branch protection for main (PR required, review required, no force push).
- [ ] Archive and close merged legacy feature branches.

## Suggested First Execution Order
1. Lock acceptance criteria for KIE fields.
2. Add API regression tests for return_raw and coordinate policy.
3. Run cloud validation on invoice sample set.
4. Finalize branch protection and closeout notes.
