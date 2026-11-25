# SITE-11 stage 2: canonical feature and named decision owner.
import json
import os
from pathlib import Path
import subprocess
import tempfile

ENV = {k: os.environ.get(k, "") for k in ("HOME", "PATH", "USER")}
ENV["LANG"] = "en_US.UTF-8"

S2 = """Below are commitments, product decisions and feature dependencies extracted from a company's records. Features may be named by codename or plain name; match them.
For EACH commitment:
- feature: one canonical plain feature name (e.g. "SSO (SAML)", "Audit log export"), the same string for every commitment on the same feature.
- current state, using decisions about its feature and about any feature it depends on (a delay or cut of a dependency delays the dependent feature). Order by date; a later 'reverse' restores the earlier plan. A 'rescope' that removes a capability affects only commitments whose scope_details include that capability.
  States: as_promised | changed | partially_changed | fulfilled.
- affecting_decisions: the decision records that determine the current state (include the original decision record, not only follow-ups).
- owner: the PERSON named as the decider in the record that made the change (e.g. "Decision (Dana Ortiz, PM)" gives Dana Ortiz; "Decision (CEO)" gives CEO). Do NOT use a later follow-up ticket or a channel name. null if no change.
- owner_record: the record id where that decider is named.
Return ONLY JSON: {"links":[{"commitment_record":..,"feature":..,"current_state":..,"affecting_decisions":[{"record":..,"date":..,"effect":..,"via_dependency":true|false}],"owner":..,"owner_record":..}]} with one entry per commitment."""

def extract_json_object(text):
    """Decode the first complete JSON object, allowing prose or code fences."""
    if not isinstance(text, str):
        raise ValueError("Stage 2 result must be text")
    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text, index)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("Stage 2 result contains no JSON object")


def run_stage2(model):
    prompt = (S2 + "\n\nCOMMITMENTS:\n" + json.dumps(model["commitments"])
              + "\n\nDECISIONS:\n" + json.dumps(model["decisions"])
              + "\n\nDEPENDENCIES:\n" + json.dumps(model["dependencies"]))
    log = []
    for _ in range(2):
        try:
            out = subprocess.run(
                ["claude", "-p", prompt, "--model", "opus", "--output-format", "json",
                 "--tools", "", "--strict-mcp-config", "--setting-sources", "",
                 "--no-session-persistence"],
                capture_output=True, text=True, env=ENV, timeout=590)
            if out.returncode != 0:
                raise ValueError("Stage 2 subprocess failed")
            links = extract_json_object(json.loads(out.stdout)["result"])["links"]
            if not isinstance(links, list):
                raise ValueError("Stage 2 links must be a list")
            return {"extractor": {"stage1": "reused from site10 (frozen)",
                                  "stage2_model": "opus", "S2": S2},
                    "commitments": model["commitments"], "decisions": model["decisions"],
                    "dependencies": model["dependencies"], "links": links, "log": log}
        except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as error:
            log.append(f"stage2 retry: {error}")
    raise RuntimeError("Stage 2 failed after two attempts")


def write_atomic(path, obj):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", closefd=False) as stream:
            json.dump(obj, stream, indent=1, allow_nan=False)
        os.replace(temporary, path)
    finally:
        try:
            os.close(fd)
        finally:
            Path(temporary).unlink(missing_ok=True)


def main():
    with open("data/model-stage1.json", encoding="utf-8") as stream:
        model = json.load(stream)
    result = run_stage2(model)
    write_atomic("data/model.json", result)
    print("links", len(result["links"]), "log", result["log"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
