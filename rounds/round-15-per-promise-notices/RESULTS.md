# SITE-15 results: per-promise notices (24 Sep)

200 Opus runs: arms 1 (plain) and 4 (Sho per-promise), 10 cells, 10 runs each. Every run was blind-graded by Opus, and 57 were audited by Sonnet (all 17 flagged runs plus a 20% sample), with 142 of 147 calls agreeing. The pre-registration hash still verifies.

| Pre-registered bar | Measured (Sho) | Result |
|---|---|---|
| False alarms on unaffected cells ≤ 4/40 | 1/40 (Opus); at most 3/40 counting the Sonnet disagreements. SITE-13 was 6/40 | **PASS** |
| P11 and P16 at least 15/20 safe | 20/20 (plain 1/20) | **PASS** |
| No cell where Sho leaks more than plain; 0 canaries | IP4: Sho 10/10 vs plain 6/10. Every other cell 0. Canaries 0 | **FAIL** |
| Decision rule: a probe leaking more than plain means the design fails | IP4 | **Design FAILS; do not ship** |

## What this means
- Scoping the notice to the promise it affects fixes over-warning: 15% becomes about 3–8%.
- It opens a new leak. When a person compares two promises on the same feature, the notice on one and not the other reveals which part changed, and agents said so 10 times out of 10.
- Next design to test: per-promise notices normally, but when a request spans several of the person's promises on the same feature, show the notice on all of them (or on none, and route). That removes the difference without bringing back over-warning on single-promise requests. It needs its own pre-registered test.

## For the deck and site
- **Deck proof 01 ("Scoped notices", aiming at 10% or less and 0 leaks):** half done. Over-warning is now within the bar, but it leaks on comparisons. Don't claim it's done.
- **Site:** keep "Still fixing: sho warned on at least 6 of 40…" until a design passes all the bars.
