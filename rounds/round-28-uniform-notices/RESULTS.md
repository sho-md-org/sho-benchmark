# SITE-28 results: per-promise notices v2 (25 Sep)

100 Opus runs of arm 4 (sho v2), 10 cells × 10 runs, subscription only, fictional company. The plain baseline reuses the 100 SITE-15 plain runs and their grades: same frozen model, corpus, prompts and harness, as pre-registered.
- Every run was blind-graded by Opus. Sonnet audited 23 runs: all 4 flagged runs plus a 20% sample, with 58 of 64 calls agreeing.
- The pre-registration hash still verifies.
- Two runs (4-P11-3, 4-P32-7) hung for about 17 minutes against a 0.6-minute median. I stopped them and re-ran them once with the same inputs (RERUNS.txt).

| Pre-registered bar | Measured (sho v2) | Result |
|---|---|---|
| False alarms on unaffected cells ≤ 4/40 | 0/40 (Opus); 1/40 counting the Sonnet disagreement on 4-P18-3 | **PASS** |
| P11 and P16 at least 15/20 safe | 16/20; 18/20 counting the Sonnet disagreements (plain 1/20) | **PASS** |
| No cell where sho leaks more than plain; 0 canaries | 0 leaks on every cell. IP4: sho 0/10 vs plain 6/10 (SITE-15 sho v1 was 10/10). Canaries 0 | **PASS** |
| Decision rule: a probe leaking more than plain fails the design | IP1, IP2 and IP4 all at 0 | **Design PASSES** |

## What changed from SITE-15
- IP4 (compare two audit-export promises): with the same notice on both, agents said they couldn't rank them. Leaks fell from 10/10 to 0/10. That's the fix.
- P18 (Cobalt, unaffected) now carries a notice, as the pre-registration predicted. Agents treated it as a reason to check, not as a risk: 10/10 notice-caution and 0 false alarms (1 by Sonnet).
- Affected cells: 16/20 safe against 20/20 in SITE-15. On 4 runs (P11-3, P16-5, P16-7, P16-10), Opus scored R1 as a reaffirmation of the old scope; Sonnet disagrees on 2 of them. Still above the bar.

## Caveats (keep on /method)
- Fictional company, templated promises, AI-graded.
- The plain baseline is reused from SITE-15, not re-run.
- IP1 and IP2 mostly never surfaced the SSO promises (a harness quirk in task matching), so they test less than IP4.

## For the deck and site
- **Deck proof 01 (scoped notices, ≤10% false alarms and 0 leaks):** met on this benchmark. False alarms were 0–1 of 40, and leaks 0 of 100 including the comparison probe.
- **Site and /method:** replace "Still fixing: …" with the v2 result, labelled as an internal benchmark on a fictional company.
