# SITE-11 stage 2 re-run (logged design change): canonical feature per commitment, owner = named decider in the changing record.
import json, subprocess, os, re
M = json.load(open("data/model-stage1.json"))
ENV = {k: os.environ[k] for k in ["HOME", "PATH", "USER"]}; ENV["LANG"] = "en_US.UTF-8"
S2 = """Below are commitments, product decisions and feature dependencies extracted from a company's records. Features may be named by codename or plain name; match them.
For EACH commitment:
- feature: one canonical plain feature name (e.g. "SSO (SAML)", "Audit log export"), the same string for every commitment on the same feature.
- current state, using decisions about its feature and about any feature it depends on (a delay or cut of a dependency delays the dependent feature). Order by date; a later 'reverse' restores the earlier plan. A 'rescope' that removes a capability affects only commitments whose scope_details include that capability.
  States: as_promised | changed | partially_changed | fulfilled.
- affecting_decisions: the decision records that determine the current state (include the original decision record, not only follow-ups).
- owner: the PERSON named as the decider in the record that made the change (e.g. "Decision (Dana Ortiz, PM)" gives Dana Ortiz; "Decision (CEO)" gives CEO). Do NOT use a later follow-up ticket or a channel name. null if no change.
- owner_record: the record id where that decider is named.
Return ONLY JSON: {"links":[{"commitment_record":..,"feature":..,"current_state":..,"affecting_decisions":[{"record":..,"date":..,"effect":..,"via_dependency":true|false}],"owner":..,"owner_record":..}]} with one entry per commitment."""
log = []; links = None
for attempt in (1, 2):
    try:
        out = subprocess.run(["claude", "-p", S2 + "\n\nCOMMITMENTS:\n" + json.dumps(M["commitments"]) + "\n\nDECISIONS:\n" + json.dumps(M["decisions"]) + "\n\nDEPENDENCIES:\n" + json.dumps(M["dependencies"]),
                              "--model", "opus", "--output-format", "json", "--tools", "", "--strict-mcp-config", "--setting-sources", "", "--no-session-persistence"], capture_output=True, text=True, env=ENV, timeout=590)
        links = json.loads(re.search(r"\{.*\}", json.loads(out.stdout)["result"], re.S).group(0))["links"]; break
    except Exception as e: log.append(f"stage2 retry: {e}")
json.dump({"extractor": {"stage1": "reused from site10 (frozen)", "stage2_model": "opus", "S2": S2}, "commitments": M["commitments"], "decisions": M["decisions"], "dependencies": M["dependencies"], "links": links, "log": log}, open("data/model.json", "w"), indent=1)
print("links", len(links or []), "log", log)
