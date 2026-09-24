# SITE-10 Sho automatic model formation (frozen before agent runs). Headless Claude on the subscription.
import json, subprocess, os, re, concurrent.futures as cf
R = json.load(open("data/corpus.json"))
ENV = {k: os.environ[k] for k in ["HOME", "PATH", "USER"]}; ENV["LANG"] = "en_US.UTF-8"
S1 = """You extract company state from records. For EACH record below, identify:
- commitments: a promise actually made to a customer, partner or another team about a feature, date or scope. Include informal and second-hand promises. EXCLUDE non-promises ("exploring", "on the roadmap, no commitment", "we'll consider", a competitor's promise). Fields: promiser, recipient, what, scope_details (specific capabilities promised, e.g. 'IdP-initiated login', 'SIEM/Splunk streaming', 'CSV export'), by_when (as written).
- decisions: a decision that sets, changes, cuts, rescopes, reverses or confirms the delivery date or scope of a product feature, or announces it shipped. Fields: date, decided_by, subject, aliases (codenames and plain names you can infer), what, effect (set|delay|cut|rescope|reverse|confirm|shipped), new_date, scope_removed.
- dependencies: a statement that feature X depends on / is built on / ships after feature Y. Fields: feature, depends_on.
Use the record id exactly. Return ONLY JSON: {"commitments":[{"record":..,...}],"decisions":[{"record":..,...}],"dependencies":[{"record":..,"feature":..,"depends_on":..}]}"""
S2 = """Below are commitments, product decisions and feature dependencies extracted from a company's records. Features may be named by codename or plain name; match them.
For EACH commitment decide its CURRENT state using the decisions about its feature, and decisions about any feature it depends on (a delay or cut of a dependency delays the dependent feature). Order decisions by date; a later 'reverse' restores the earlier plan. A 'rescope' that removes a capability affects only commitments whose scope_details include that capability; other commitments on the same feature are unaffected.
States: as_promised | changed (delayed or cut past the promised time) | partially_changed (a promised capability was removed) | fulfilled (shipped) .
Return ONLY JSON: {"links":[{"commitment_record":..,"affecting_decisions":[{"record":..,"date":..,"effect":..,"via_dependency":true|false}],"latest_decision_record":..|null,"current_state":..,"owner":"<person who owns the latest decision, or null>"}]} with one entry per commitment."""
def call(prompt, model):
    out = subprocess.run(["claude", "-p", prompt, "--model", model, "--output-format", "json", "--tools", "", "--strict-mcp-config", "--setting-sources", "", "--no-session-persistence"], capture_output=True, text=True, env=ENV, timeout=590)
    return json.loads(re.search(r"\{.*\}", json.loads(out.stdout)["result"], re.S).group(0))
batches = [R[i:i+50] for i in range(0, len(R), 50)]
log = []
def s1(b):
    body = "\n\n".join(f"[{r['id']}] {r['title']} ({r['tool']}, {r['date']})\n{r['body']}" for r in b)
    for attempt in (1, 2):
        try: return call(S1 + "\n\nRECORDS:\n" + body, "sonnet")
        except Exception as e: log.append(f"stage1 retry: {e}")
    return {"commitments": [], "decisions": [], "dependencies": [], "error": True}
with cf.ThreadPoolExecutor(12) as ex: parts = list(ex.map(s1, batches))
C = [c for p in parts for c in p.get("commitments", [])]; D = [d for p in parts for d in p.get("decisions", [])]; P = [d for p in parts for d in p.get("dependencies", [])]
# Keep decisions and dependencies that mention a feature-like subject; pass all commitments.
links = None
for attempt in (1, 2):
    try: links = call(S2 + "\n\nCOMMITMENTS:\n" + json.dumps(C) + "\n\nDECISIONS:\n" + json.dumps(D) + "\n\nDEPENDENCIES:\n" + json.dumps(P), "opus"); break
    except Exception as e: log.append(f"stage2 retry: {e}")
json.dump({"extractor": {"stage1_model": "sonnet", "stage2_model": "opus", "S1": S1, "S2": S2, "batch": 50}, "commitments": C, "decisions": D, "dependencies": P,
           "links": (links or {}).get("links", []), "errors": sum(1 for p in parts if p.get("error")), "log": log}, open("data/model-stage1.json", "w"), indent=1)
print("commitments", len(C), "decisions", len(D), "dependencies", len(P), "links", len((links or {}).get("links", [])), "stage1 errors", sum(1 for p in parts if p.get("error")), "log", log[:3])
