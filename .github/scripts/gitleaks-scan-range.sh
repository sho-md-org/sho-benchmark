#!/usr/bin/env bash
# SHO-815b: the gitleaks passes behind the "Secret scan" workflow.
#
# usage: gitleaks-scan-range.sh <repository> <revision range> [report prefix]
#
# Both the event scan and the "Prove the event scan sees merge-only additions" control run this
# script, so the control cannot stay green while the event scan uses different options or fewer
# passes. GITLEAKS_BINARY names the gitleaks executable. Without a report prefix each pass prints
# its findings; with one, pass N writes <prefix>.N.json instead. Every pass runs, and the exit
# status is non-zero if any pass reported a finding or could not complete.
#
# Plain `git log -p` prints no patch for a merge, so a credential added only while resolving a
# merge (present in neither parent) never reaches the scanner when only a revision range is
# passed. Gitleaks appends the options of each pass to `git log -p -U0 <options> <range>`.
#
# Pass 1 shows, for every two-parent merge, the lines its result carries beyond an automatic
# re-merge of its parents (git 2.36 or newer), so commits that arrived through a parent are not
# reported again and reviewed `.gitleaksignore` fingerprints keep applying. Git skips that re-merge
# for octopus merges, so pass 2 shows each octopus merge against every parent instead. That pass
# reports content an octopus merge brings in through a parent under the merge commit's own
# fingerprint, so an ignored credential that arrives through an octopus merge needs its own
# `.gitleaksignore` entry for that merge commit. It fails closed.
#
# Git marks a path the automatic re-merge could not resolve with a `remerge CONFLICT` line, and
# gitleaks then reports that path with a `b/` prefix (for example `b/docs/a.txt`), so a
# `.gitleaks.toml` path allowlist for that file does not match. It also fails closed.
set -euo pipefail

usage="usage: gitleaks-scan-range.sh <repository> <revision range> [report prefix]"
: "${GITLEAKS_BINARY:?GITLEAKS_BINARY must name the gitleaks executable}"
repository="${1:?${usage}}"
range="${2:?${usage}}"
report_prefix="${3:-}"

passes=(
  '--diff-merges=remerge'
  '--diff-merges=separate --min-parents=3'
)

status=0
pass=0
for log_opts in "${passes[@]}"; do
  pass=$((pass + 1))
  if [[ -n "${report_prefix}" ]]; then
    output=(--report-format json --report-path "${report_prefix}.${pass}.json")
  else
    output=(--verbose)
  fi
  "${GITLEAKS_BINARY}" git --no-banner --no-color --redact "${output[@]}" \
    --log-opts="${log_opts} ${range}" "${repository}" || status=1
done
exit "${status}"
