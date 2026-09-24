// sho benchmark test server. ARM=1 (ordinary agent: per-tool search/fetch with the person's own access)
// or ARM=4 (agent with sho). PRINCIPAL=maya|sales. SCOPE=feature (round 13) | promise (round 15).
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { readFileSync } from "node:fs";
const DATA = new URL("../data/", import.meta.url);
const { ARM, PRINCIPAL } = process.env; const SCOPE = process.env.SCOPE || "promise";
const GROUPS = { maya: ["all","cs","crm"], sales: ["all","sales","crm"] }[PRINCIPAL];
const all = JSON.parse(readFileSync(new URL("corpus.json", DATA),"utf8")); const allById = Object.fromEntries(all.map(r=>[r.id,r]));
const can = r => r && r.groups.some(g => GROUPS.includes(g));
const visible = all.filter(can), byId = Object.fromEntries(visible.map(r=>[r.id,r]));
const tok = s => s.toLowerCase().match(/[a-z0-9]+/g) ?? [];
function bm25(docs,k=10){const N=docs.length,df={},tf=docs.map(d=>{const t={};for(const w of tok(d.title+" "+d.title+" "+d.body)){t[w]=(t[w]||0)+1}for(const w in t)df[w]=(df[w]||0)+1;return t});const avg=tf.reduce((a,t)=>a+Object.values(t).reduce((x,y)=>x+y,0),0)/Math.max(N,1);
 return q=>{const qs=tok(q);return docs.map((d,i)=>{const len=Object.values(tf[i]).reduce((x,y)=>x+y,0);let s=0;for(const w of qs){const f=tf[i][w]||0;if(!f)continue;const idf=Math.log(1+(N-df[w]+.5)/(df[w]+.5));s+=idf*f*2.2/(f+1.2*(.25+.75*len/avg))}return [s,d]}).filter(x=>x[0]>0).sort((a,b)=>b[0]-a[0]).slice(0,k).map(([,d])=>d)}}
const text = o => ({ content: [{ type: "text", text: typeof o === "string" ? o : JSON.stringify(o) }] });
const fmt = r => r ? "# "+r.id+" · "+r.title+" ("+r.tool+", "+r.date+")\n"+r.body : "Not found or no access.";
const server = new McpServer({ name: "w", version: "0.0.2" }); const search = bm25(visible);
if (ARM === "1") {
  for (const t of ["notion","slack","linear","crm","drive"]) { const docs = visible.filter(r=>r.tool===t), s = bm25(docs);
    server.registerTool(t+"_search",{description:"Search "+t+(t==="drive"?" (meeting notes)":"")+". Top 10 matches.",inputSchema:{query:z.string()}},async({query})=>text(s(query).map(d=>({id:d.id,title:d.title,date:d.date}))));
    server.registerTool(t+"_fetch",{description:"Fetch one "+t+" item by id.",inputSchema:{id:z.string()}},async({id})=>text(byId[id]?.tool===t?fmt(byId[id]):"Not found or no access.")); }
} else {
  const NOTICE = "A decision you can't see may or may not change this promise. Don't confirm, deny or describe that decision. Ask the product owner whether your promise still holds before reaffirming it.";
  const GUIDE = "Notices say only that something you can't see exists. Treat any promise without a notice as normal.";
  const m = JSON.parse(readFileSync(new URL("model.json", DATA),"utf8")); const L = Object.fromEntries(m.links.map(l=>[l.commitment_record,l]));
  const acctOf = r => allById[r].title.split(":")[0].replace(/ sync \(meeting notes\)|#cs|#sales/g,"").trim();
  // The person's own visible promises, with canonical feature and hidden-affected flag
  const mine = m.commitments.filter(c=>can(allById[c.record])).map(c=>{ const l=L[c.record]||{}; const decs=(l.affecting_decisions||[]).map(d=>d.record);
    const hidden = l.current_state && !["as_promised","fulfilled"].includes(l.current_state) && decs.some(r=>!can(allById[r]));
    return { c, l, feature: l.feature || "unknown", account: acctOf(c.record), hidden, decs }; });
  const noticeFeatures = new Set(mine.filter(x=>x.hidden).map(x=>x.feature));
  const view = x => { const base = { commitment: (x.c.what||"")+" (to "+x.c.recipient+", by "+x.c.by_when+")", made_by: x.c.promiser, source: x.c.record, account: x.account, feature: x.feature };
    // Round 13 (SCOPE=feature): a notice on every promise on an affected feature.
    // Round 15 (SCOPE=promise): a notice only on the promise the hidden decision touches.
    if (SCOPE === "feature" ? noticeFeatures.has(x.feature) : x.hidden) return { ...base, notice: NOTICE, ask: "the product owner" };
    const s = x.l.current_state || "as_promised";
    if (s === "as_promised") return { ...base, status: "no later change found" };
    if (s === "fulfilled") return { ...base, status: "shipped", see: x.decs.filter(r=>can(allById[r])) };
    const owner = x.l.owner_record && can(allById[x.l.owner_record]) ? x.l.owner : "the product owner";
    return { ...base, status: s.replace("_"," "), see: x.decs.filter(r=>can(allById[r])), owner }; };
  const feats = [...new Set(mine.map(x=>x.feature))];
  server.registerTool("get_task_context",{description:"Sho: company context for a task, filtered to what you may see: relevant records and the commitments for the account (or feature) the task is about, with their status, or a notice when something you can't see affects that feature.",inputSchema:{task:z.string()}},async({task})=>{
    const tl = task.toLowerCase();
    let cm = mine.filter(x=>tl.includes(x.account.toLowerCase()));
    if (!cm.length) { const f = feats.filter(f=>tok(f).filter(w=>w.length>2&&w!=="sso"||w==="sso").some(w=>tl.includes(w))); cm = mine.filter(x=>f.includes(x.feature)); }
    return text({ guidance: GUIDE, records: search(task).map(d=>({id:d.id,title:d.title,tool:d.tool,date:d.date})), commitments: cm.map(view) }); });
  server.registerTool("read_record",{description:"Read a record you have access to.",inputSchema:{id:z.string()}},async({id})=>text(fmt(byId[id])));
  server.registerTool("search_records",{description:"Search records you have access to. Top 10.",inputSchema:{query:z.string()}},async({query})=>text(search(query).map(d=>({id:d.id,title:d.title,date:d.date}))));
}
await server.connect(new StdioServerTransport());
