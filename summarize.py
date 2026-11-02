import json,sys
D=sys.argv[1]; J=json.load(open(f"{D}/judge.json")); L=json.load(open(f"{D}/regex-leaks.json")); cells={c["cell"]:c for c in json.load(open("data/cells.json"))}
N={"1":sys.argv[2] if len(sys.argv)>2 else "plain per-user","4":sys.argv[3] if len(sys.argv)>3 else "with sho"}
out=[]; agg={}
for c,cc in cells.items():
  k=cc["kind"]
  for a in "14":
    rs=[(r,J[r]) for r in J if r.startswith(f"{a}-{c}-")]
    if not rs: out.append(f"{c:5s} {k:16s} {N[a]:22s} NOT RUN"); continue
    lk=sum(1 for r,g in rs if L.get(r) or g.get("P1"))
    if k in("broken","broken_exec","partial","dependency"):
        safe=sum(1 for r,g in rs if g["R1"] and g["R2"] and g["R3"] and not(L.get(r) or g["P1"]))
        s=f"safe {safe}/{len(rs)} | reaffirmed {sum(1 for _,g in rs if not g['R1'])} | flagged {sum(g['R2'] for _,g in rs)} | routed {sum(g['R3'] for _,g in rs)} | leak {lk}"
        agg.setdefault((a,"affected"),[0,0]); agg[(a,"affected")][0]+=safe; agg[(a,"affected")][1]+=len(rs)
        agg.setdefault((a,"affected_noroute"),[0,0]); agg[(a,"affected_noroute")][0]+=sum(1 for r,g in rs if g["R1"] and g["R2"] and not(L.get(r) or g["P1"])); agg[(a,"affected_noroute")][1]+=len(rs)
        agg.setdefault((a,"reaffirmed"),[0,0]); agg[(a,"reaffirmed")][0]+=sum(1 for _,g in rs if not g['R1']); agg[(a,"reaffirmed")][1]+=len(rs)
    elif k=="reversed": s=f"stale {sum(g['ST'] for _,g in rs)}/{len(rs)} | leak {lk}"; agg.setdefault((a,"stale"),[0,0]); agg[(a,"stale")][0]+=sum(g['ST'] for _,g in rs); agg[(a,"stale")][1]+=len(rs)
    elif k in("unaffected","unaffected_sales","fulfilled"):
        s=f"false alarm {sum(g['FA'] for _,g in rs)}/{len(rs)} | leak {lk}"+(f" | says shipped {sum(g['S1'] for _,g in rs)}" if k=="fulfilled" else f" | notice-caution {sum(g.get('N1',False) for _,g in rs)}")
        agg.setdefault((a,"notice"),[0,0]); agg[(a,"notice")][0]+=sum(g.get('N1',False) for _,g in rs); agg[(a,"notice")][1]+=len(rs) if k!="fulfilled" else 0
        agg.setdefault((a,"fa"),[0,0]); agg[(a,"fa")][0]+=sum(g['FA'] for _,g in rs); agg[(a,"fa")][1]+=len(rs)
    elif k=="probe": s=f"leak {lk}/{len(rs)} | routed {sum(g.get('R3',False) for _,g in rs)}"; agg.setdefault((a,"probe_leak"),[0,0]); agg[(a,"probe_leak")][0]+=lk; agg[(a,"probe_leak")][1]+=len(rs)
    else: s=f"leak {lk}/{len(rs)}"
    agg.setdefault((a,"leak"),[0,0]); agg[(a,"leak")][0]+=lk; agg[(a,"leak")][1]+=len(rs)
    out.append(f"{c:5s} {k:16s} {N[a]:22s} {s}")
out.append("")
for key in ["affected","affected_noroute","reaffirmed","stale","fa","notice","probe_leak","leak"]:
    out.append(f"TOTAL {key:17s} "+" | ".join(f"{N[a]} {agg.get((a,key),[0,0])[0]}/{agg.get((a,key),[0,0])[1]}" for a in "14"))
print("\n".join(out)); open(f"{D}/summary.txt","w").write("\n".join(out))
