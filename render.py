#!/usr/bin/env python3
"""Treasure Camel 看板 · 渲染层  data.json → 固定模板 HTML（纯数据，无文字判读）"""
import json, os, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "data.json"), encoding="utf-8"))
CFG = {}
for line in open(os.path.join(HERE, "config.env"), encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1); CFG[k.strip()] = v.strip()

S, RC, W = D["summary"], D["recent"], D["window"]
n = lambda x: f"{int(x):,}"


def pf(a, b, dp=1):
    return f"{a/b*100:.{dp}f}%" if b else "—"


def bar(w, color="var(--m1)"):
    return f'<div class="bar"><i style="width:{max(0.5,min(100,w)):.1f}%;background:{color}"></i></div>'


PAYOUT_REASONS = {"theme122_payout", "theme122_free_spin_payout", "theme122_wager"}
LABELS = {"account_opening": "开户欢迎奖励", "emergency_recovery_supply": "紧急补给",
          "coin_purchase": "兑换到账", "daily_recovery_supply": "每日补给",
          "daily_login": "每日登录", "caravan_daily_order": "每日任务",
          "admin_coin_purchase_compensation": "后台补币", "support_goodwill": "客服补偿",
          "weekly_bridge_reward": "周榜奖励"}
PAID = {"coin_purchase"}

# ── Credits 来源（最近 N 天）──────────────────────────────────────
reasons = sorted([(r["reason"], int(r["credited"])) for r in RC["economy"]["walletReasons"]
                  if r["reason"] not in PAYOUT_REASONS and int(r["credited"]) > 0],
                 key=lambda x: -x[1])
grant = sum(v for _, v in reasons)
paid = sum(v for k, v in reasons if k in PAID)
free_share = (grant - paid) / grant if grant else 0
mxr = reasons[0][1] if reasons else 1
rgp, rac, rex = RC["gameplay"], RC["activation"], RC["exchanges"]
rnet = int(rgp["netCoins"])
rrtp = int(rgp["awardedCoins"]) / int(rgp["wageredCoins"]) * 100 if int(rgp["wageredCoins"]) else 0

gp, ex = S["gameplay"], S["exchanges"]
rev = {e["eventName"]: e for e in RC["funnel"]}
RE = lambda k, f="players": rev[k][f] if k in rev else 0
xr = (D.get("exchange_recent") or [{"ppl": 0}])[0]
xt = (D.get("exchange_total") or [{"ppl": 0}])[0]

# ── 命中率（最近 HIT_DAYS 天）─────────────────────────────────────
hd = D["hit_daily"]
days7 = sorted(hd)[-W["hit_days"]:]
sp7 = sum(hd[d]["spins"] for d in days7); ht7 = sum(hd[d]["hit"] for d in days7)
wn7 = sum(hd[d]["win"] for d in days7); s17 = sum(hd[d]["sub1"] for d in days7)
wg7 = sum(hd[d]["wager"] for d in days7); po7 = sum(hd[d]["payout"] for d in days7)
hrow = "".join(
    f'<tr><td class="mono">{d[5:]}</td><td class="num mono">{n(hd[d]["spins"])}</td>'
    f'<td class="num mono">{pf(hd[d]["hit"],hd[d]["spins"],2)}</td>'
    f'<td class="num mono">{pf(hd[d]["win"],hd[d]["spins"],2)}</td>'
    f'<td class="num mono">{pf(hd[d]["sub1"],hd[d]["hit"])}</td>'
    f'<td class="num mono">{hd[d]["median_mult"] if hd[d]["median_mult"] is not None else "—"}</td>'
    f'<td class="num mono">{pf(hd[d]["payout"],hd[d]["wager"],2)}</td></tr>' for d in days7)
hrow += (f'<tr class="hi"><td class="mono"><b>合计</b></td><td class="num mono"><b>{n(sp7)}</b></td>'
         f'<td class="num mono"><b>{pf(ht7,sp7,2)}</b></td><td class="num mono">{pf(wn7,sp7,2)}</td>'
         f'<td class="num mono">{pf(s17,ht7)}</td><td class="num mono">—</td>'
         f'<td class="num mono">{pf(po7,wg7,2)}</td></tr>')

# ── 逐日规模表 ───────────────────────────────────────────────────
xd = {r["d"][:10]: r for r in D["exchange_daily"]}
daily = [d for d in S["daily"] if d["activePlayers"] > 0]
MXS = max(d["spins"] for d in daily) or 1
MXC = max([int(v["c"]) for v in xd.values()] or [1]) or 1
rows = []
for d in daily:
    day = d["date"][:10]; ap = d["activePlayers"]; sp = d["spins"]
    r = xd.get(day, {}); xp = int(r.get("ppl", 0)); xc = int(r.get("c", 0))
    dr = int(d["awardedCoins"]) / int(d["wageredCoins"]) * 100 if int(d["wageredCoins"]) else 0
    rows.append(f'<tr><td class="mono">{day[5:]}</td><td class="num mono">{ap}</td>'
                f'<td class="num mono">{D["new_players"].get(day,0)}</td><td class="num mono">{n(sp)}</td>'
                f'<td>{bar(sp/MXS*100)}</td><td class="num mono">{sp//ap if ap else 0}</td>'
                f'<td class="num mono">{xp}</td><td class="num mono">{n(xc)}</td>'
                f'<td>{bar(xc/MXC*100,"var(--m2)")}</td><td class="num mono">{dr:.1f}%</td>'
                f'<td class="num mono">{int(d["netCoins"])/1e6:+,.1f}</td></tr>')

# ── 顶部 KPI：全部取最后一个完整日（前 1 天）────────────────────
LD = D.get("lastday") or {}
ld_gp = LD.get("gameplay", {})
ld_ex = LD.get("exchanges", {})
LDAY = W["end"]
ld_active = ld_gp.get("activePlayers", 0) or 0
ld_spins = ld_gp.get("spins", 0) or 0

# 当日 Credits 发放构成
ld_reasons = [(r["reason"], int(r["credited"]))
              for r in LD.get("economy", {}).get("walletReasons", [])
              if r["reason"] not in PAYOUT_REASONS and int(r["credited"]) > 0]
ld_grant = sum(v for _, v in ld_reasons)
ld_paid = sum(v for k, v in ld_reasons if k in PAID)
ld_free = (ld_grant - ld_paid) / ld_grant if ld_grant else 0

# 当日兑换（Redshift 口径，含人数）
ld_x = xd.get(LDAY, {})

# 当日命中率
ld_h = hd.get(LDAY)

# 留存：当日的 D1/D3/D7 都还没成熟，取最近一个成熟值并标出其 cohort 日
def latest_mature(key, idx):
    for r in reversed(D["retention_daily"]):
        if r["active"] and int(r[key][idx]["den"]):
            return r["date"], float(r[key][idx]["rate"]) * 100
    return None, None


r7_day, r7_val = latest_mature("ar", 2)
r1_day, r1_val = latest_mature("ar", 0)

# ── 漏斗（最近 N 天）─────────────────────────────────────────────
F = [("启动游戏", rac["startedPlayers"]), ("领取欢迎奖励", rac["starterGiftCollectedPlayers"]),
     ("开始游戏（≥1 Spin）", rac["spin1Players"]), ("持续玩（≥5 Spin）", rac["spin5Players"]),
     ("≥10 Spin", rac["spin10Players"]), ("深玩（≥25 Spin）", rac["spin25Players"])]
den = F[0][1] or 1
frows = []
for i, (lab, v) in enumerate(F):
    frows.append(f'<tr><td>{i+1:02d}　{lab}</td><td class="num mono">{v}</td>'
                 f'<td>{bar(v/den*100)}</td>'
                 f'<td class="num">{"分母" if i==0 else pf(v,F[i-1][1])}</td></tr>')
frows.append('<tr class="sub2"><td colspan="4">▼ 兑换路径</td></tr>')
for i, k in enumerate(["insufficient_balance_shown", "coin_store_viewed", "coin_pack_clicked"]):
    lab = {"insufficient_balance_shown": "Credits 不足（撞墙）", "coin_store_viewed": "进入商店",
           "coin_pack_clicked": "点击 coin pack"}[k]
    frows.append(f'<tr><td>{len(F)+i+1:02d}　{lab}</td>'
                 f'<td class="num mono">{RE(k)} <span class="note">/ {n(RE(k,"events"))} 次</span></td>'
                 f'<td>{bar(RE(k)/den*100,"var(--m2)")}</td><td class="num">—</td></tr>')
frows.append(f'<tr class="hi"><td><b>10　完成兑换（coins→credits）</b></td>'
             f'<td class="num mono"><b>{rex["successful"]} 笔</b> <span class="note">/ {xr["ppl"]} 人</span></td>'
             f'<td>{bar(int(xr["ppl"])/den*100,"var(--m2)")}</td>'
             f'<td class="num mono">扣 {n(rex["loopsCoinsDeducted"])}</td></tr>')

# ── Credits 来源（最近 N 天）─────────────────────────────────────
erows = []
for k, v in reasons:
    tag = '<span class="tag good">Coins 换</span>' if k in PAID else '<span class="tag">免费</span>'
    cls = ' class="hi"' if k in PAID else ''
    col = "var(--good)" if k in PAID else "var(--none)"
    erows.append(f'<tr{cls}><td>{LABELS.get(k,k)}</td><td class="num mono">{n(v)}</td>'
                 f'<td>{bar(v/mxr*100, col)}</td><td class="num mono">{pf(v,grant)}</td><td>{tag}</td></tr>')
erows.append('<tr class="sub2"><td colspan="5">▼ 汇总</td></tr>')
erows.append(f'<tr><td>非返奖发放合计</td><td class="num mono">{n(grant)}</td><td></td>'
             f'<td class="num mono">100%</td><td class="note">免费占 {free_share*100:.1f}%</td></tr>')
erows.append(f'<tr><td>净消耗（下注 − 返奖）</td><td class="num mono">{n(rnet)}</td><td></td>'
             f'<td class="num mono">{pf(rnet,grant)}</td><td class="note">RTP {rrtp:.2f}%</td></tr>')

# ── 逐日留存 ─────────────────────────────────────────────────────
def cell(x):
    if not int(x["den"]):
        return '<td class="num mono" style="color:var(--ink-4)">—</td>'
    return f'<td class="num mono">{float(x["rate"])*100:.1f}%</td>'


rtrows = []
for r in D["retention_daily"]:
    if not r["active"]:
        continue
    rtrows.append(f'<tr><td class="mono">{r["date"][5:]}</td><td class="num mono">{r["active"]}</td>'
                  + "".join(cell(x) for x in r["ar"])
                  + f'<td class="num mono" style="color:var(--ink-4)">{r["co"][0]["den"]}</td>'
                  + "".join(cell(x) for x in r["co"]) + '</tr>')

# ── 逐日留存折线图 ───────────────────────────────────────────────
SERIES = [("D1", "var(--s1)"), ("D3", "var(--s2)"), ("D7", "var(--s3)")]


def spark(rows, key, title, top=None):
    """rows: retention_daily; key: 'ar' 或 'co'。返回一个独立 SVG 图表。"""
    pts = [(r["date"][5:], [(float(x["rate"]) * 100 if int(x["den"]) else None) for x in r[key]])
           for r in rows if r["active"]]
    if not pts:
        return ""
    if top is None:
        vals = [v for _, vs in pts for v in vs if v is not None]
        top = max(10, min(100, (int(max(vals) / 10) + 1) * 10)) if vals else 100
    W, H, L, R, T, Bm = 760, 210, 36, 14, 12, 26
    pw, ph = W - L - R, H - T - Bm
    n = len(pts)
    X = lambda i: L + (pw * i / (n - 1) if n > 1 else pw / 2)
    Y = lambda v: T + ph * (1 - v / top)
    g = []
    for gv in range(0, top + 1, 20):
        g.append(f'<line x1="{L}" y1="{Y(gv):.1f}" x2="{L+pw}" y2="{Y(gv):.1f}" class="gl"/>'
                 f'<text x="{L-7}" y="{Y(gv)+3.5:.1f}" class="ax" text-anchor="end">{gv}%</text>')
    step = max(1, n // 9)
    for i in range(0, n, step):
        g.append(f'<text x="{X(i):.1f}" y="{H-8}" class="ax" text-anchor="middle">{pts[i][0]}</text>')
    ends = []
    for si, (nm, col) in enumerate(SERIES):
        seg, cur = [], []
        for i, (_, vs) in enumerate(pts):
            v = vs[si]
            if v is None:
                if len(cur) > 1: seg.append(cur)
                cur = []
            else:
                cur.append((X(i), Y(v)))
        if len(cur) > 1: seg.append(cur)
        for sgm in seg:
            d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in sgm)
            g.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="2" '
                     f'stroke-linejoin="round" stroke-linecap="round"/>')
        if seg:
            lx, ly = seg[-1][-1]
            tail = [vs[si] for _, vs in pts if vs[si] is not None]
            ends.append({"x": lx, "y": ly, "ly": ly, "c": col, "t": f"{nm} {tail[-1]:.0f}%" if tail else nm})
    for e in ends:
        g.append(f'<circle cx="{e["x"]:.1f}" cy="{e["y"]:.1f}" r="4" fill="{e["c"]}" '
                 f'stroke="var(--card)" stroke-width="2"/>')
    legend = " ".join(f'<span class="lg"><i style="background:{c}"></i>{nm}</span>' for nm, c in SERIES)
    jd = json.dumps([{"d": d, "v": vs} for d, vs in pts], ensure_ascii=False)
    cid = f"c{key}"
    return (f'<div class="chart" data-pts=\'{jd}\' data-l="{L}" data-pw="{pw}" id="{cid}">'
            f'<div class="chead"><span class="ct">{title}</span><span class="lgs">{legend}</span></div>'
            f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" role="img" aria-label="{title}">'
            f'<line class="cross" x1="0" y1="{T}" x2="0" y2="{T+ph}" style="display:none"/>'
            + "".join(g) + '</svg><div class="tip" style="display:none"></div></div>')


_av = [float(x["rate"]) * 100 for r in D["retention_daily"] if r["active"]
       for k in ("ar", "co") for x in r[k] if int(x["den"])]
_top = max(20, min(100, (int(max(_av) / 20) + 1) * 20)) if _av else 100
charts = spark(D["retention_daily"], "ar", "活跃日留存（可跨游戏横比）", _top) + \
         spark(D["retention_daily"], "co", "新玩家 cohort 留存", _top)

# ── 跨游戏 ───────────────────────────────────────────────────────
cg = []
for r in D["crossgame"]:
    if r["g"] in ("gcd", "Football King") or int(r["den1"]) < 20:
        continue
    f3 = lambda a, b: int(r[a]) / int(r[b]) * 100 if int(r[b]) else 0
    cg.append((r["g"], int(r["uu"]), f3("num1", "den1"), f3("num3", "den3"), f3("num7", "den7")))
car = S["activeRetention"]["retention"]
cg.append(("★ Treasure Camel", gp["activePlayers"],
           float(car[0]["rate"])*100, float(car[1]["rate"])*100, float(car[2]["rate"])*100))
cg.sort(key=lambda x: -x[2])
mx1 = cg[0][2] if cg else 1
HI = ' class="hi"'
grows = []
for name, uu, d1, d3, d7 in cg:
    cam = name.startswith("★")
    grows.append(f'<tr{HI if cam else ""}><td>{"<b>"+name+"</b>" if cam else name}</td>'
                 f'<td class="num mono">{n(uu)}</td><td class="num mono">{d1:.1f}%</td>'
                 f'<td>{bar(d1/mx1*96, "var(--m2)" if cam else "var(--m1)")}</td>'
                 f'<td class="num mono">{d3:.1f}%</td><td class="num mono">{d7:.1f}%</td></tr>')

# ── 周榜 ─────────────────────────────────────────────────────────
qrows, srows = [], []
for i, g in enumerate(D["glory"]):
    live = g["settled_at"] is None
    cls = HI if live else ""
    tag = ' <span class="tag">进行中</span>' if live else ''
    qrows.append(f'<tr{cls}><td class="mono">{chr(9312+i)} {g["from"][5:]}~{g["to"][5:]}{tag}</td>'
                 f'<td class="num mono">{g["participants"]}</td><td class="num mono">{g["week_active"]}</td>'
                 f'<td class="num mono">{pf(g["participants"],g["week_active"])}</td>'
                 f'<td class="num mono">{n(g["score_events"])}</td>'
                 f'<td class="num mono">{g["settled_rewards"] or "—"}</td>'
                 f'<td class="num mono">{g["claimed_rewards"] or "—"}</td>'
                 f'<td class="num mono">{pf(g["claimed_rewards"],g["settled_rewards"]) if g["settled_rewards"] else "—"}</td>'
                 f'<td class="num mono">{n(g["settled_coins"])}</td></tr>')
mxt = max((g["rank_top1"] for g in D["glory"]), default=1) or 1
for i, g in enumerate(D["glory"]):
    srows.append(f'<tr><td class="mono">{chr(9312+i)}</td><td class="num mono">{n(g["rank_top1"])}</td>'
                 f'<td>{bar(g["rank_top1"]/mxt*100,"var(--m2)")}</td>'
                 f'<td class="num mono">{n(g["rank_top10"])}</td><td class="num mono">{n(g["rank_median"])}</td>'
                 f'<td class="num mono">{n(g["rank_total"])}</td></tr>')

FW = f'{W["funnel_from"][5:]}~{W["end"][5:]}'
TIP_JS = """<script>
document.querySelectorAll('.chart').forEach(function(c){
  var pts=JSON.parse(c.dataset.pts), L=+c.dataset.l, pw=+c.dataset.pw, VB=760;
  var svg=c.querySelector('svg'), cross=c.querySelector('.cross'), tip=c.querySelector('.tip');
  var cs=getComputedStyle(c);
  var cols=[cs.getPropertyValue('--s1'),cs.getPropertyValue('--s2'),cs.getPropertyValue('--s3')];
  var names=['D1','D3','D7'];
  function hide(){cross.style.display='none';tip.style.display='none';}
  c.addEventListener('mousemove',function(e){
    var r=svg.getBoundingClientRect();
    var vx=(e.clientX-r.left)/r.width*VB;
    var i=Math.round((vx-L)/pw*(pts.length-1));
    if(i<0||i>=pts.length||pts.length<2){hide();return;}
    var x=L+pw*i/(pts.length-1);
    cross.setAttribute('x1',x);cross.setAttribute('x2',x);cross.style.display='';
    var p=pts[i];
    tip.innerHTML='<b>'+p.d+'</b>'+p.v.map(function(v,k){
      return '<div class="r"><i style="background:'+cols[k]+'"></i>'+names[k]+' '+
        (v==null?'—':v.toFixed(1)+'%')+'</div>';}).join('');
    tip.style.display='';
    var px=x/VB*r.width, tw=tip.offsetWidth;
    tip.style.left=Math.max(0,Math.min(r.width-tw,px-tw/2))+'px';
    tip.style.top='26px';
  });
  c.addEventListener('mouseleave',hide);
});
</script>"""
CSS = open(os.path.join(HERE, "style.css"), encoding="utf-8").read()
HTML = f'''<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Treasure Camel</title>
<style>{CSS}</style></head><body>
<header><div class="hin">
<h1>Treasure Camel</h1>
<div class="sub">顶部指标为 <b>{W["end"]}</b>（最后一个完整沙特日）· 下方窗口 {W["start"]} ~ {W["end"]}· 产品 Loops · 排除测试账号 · 抓取于 {D["fetched_at"]}</div>
<div class="kpis">
  <div class="kpi"><div class="k">去重活跃玩家</div><div class="v">{ld_active}</div><div class="s">{n(ld_spins)} 次 spin · 人均 {ld_spins//ld_active if ld_active else 0}</div></div>
  <div class="kpi"><div class="k">活跃日留存 D7</div><div class="v">{f"{r7_val:.1f}%" if r7_val is not None else "—"}</div><div class="s">{r7_day[5:] if r7_day else "—"} 开盘 · D1 {f"{r1_val:.1f}%" if r1_val is not None else "—"}（{r1_day[5:] if r1_day else "—"}）</div></div>
  <div class="kpi"><div class="k">命中率</div><div class="v">{pf(ld_h["hit"],ld_h["spins"],2) if ld_h else "—"}</div><div class="s">payout &gt; 0 · 样本 {n(ld_h["spins"]) if ld_h else "—"} spin</div></div>
  <div class="kpi"><div class="k">兑换（coins→credits）</div><div class="v">{ld_ex.get("successful",0)}<span style="font-size:15px;color:var(--ink-4)"> 笔</span></div><div class="s">扣 {n(ld_x.get("c",0))} Coins · {ld_x.get("ppl",0)} 人</div></div>
  <div class="kpi"><div class="k">credits 免费占比</div><div class="v">{ld_free*100:.1f}%</div><div class="s">当日发放 {n(ld_grant)} · Coins 换 {pf(ld_paid,ld_grant)}</div></div>
</div>
</div></header>
<div class="wrap">

<section><h2><span class="chap">Scale</span>规模</h2>
<div class="card"><div class="cb">
<table style="min-width:880px"><thead><tr><th>沙特日</th><th class="num">活跃</th><th class="num">新玩家</th><th class="num">Spin</th><th style="width:84px"></th><th class="num">人均</th><th class="num">兑换<br>人数</th><th class="num">兑换<br>Coins</th><th style="width:68px"></th><th class="num">RTP</th><th class="num">净消耗<span class="note">（百万）</span></th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>
</div></div></section>

<section><h2><span class="chap">Funnel</span>变现<span class="tag">最近 {W["funnel_days"]} 天 · {FW}</span></h2>
<div class="card"><div class="ch"><div class="t">激活与兑换漏斗</div><span class="tag">{FW}</span></div><div class="cb">
<table><thead><tr><th style="width:38%">环节</th><th class="num">人数</th><th style="width:150px"></th><th class="num">占上环</th></tr></thead>
<tbody>{"".join(frows)}</tbody></table>
</div></div>
<div class="card" style="margin-top:12px"><div class="ch"><div class="t">Credits 来源</div><span class="tag">{FW}</span></div><div class="cb">
<table><thead><tr><th style="width:34%">来源</th><th class="num">发放量</th><th style="width:130px"></th><th class="num">占比</th><th>性质</th></tr></thead>
<tbody>{"".join(erows)}</tbody></table>
</div></div>
<div class="card" style="margin-top:12px"><div class="ch"><div class="t">单次 Spin 结果分布</div><span class="tag">近 {W["hit_days"]} 日</span></div><div class="cb">
<table><thead><tr><th style="width:18%">沙特日</th><th class="num">样本 Spin</th><th class="num">命中率<span class="note">（payout&gt;0）</span></th><th class="num">净赢率<span class="note">（&gt;下注）</span></th><th class="num">命中中仍亏本</th><th class="num">返奖倍数中位</th><th class="num">样本 RTP</th></tr></thead>
<tbody>{hrow}</tbody></table>
</div></div></section>

<section><h2><span class="chap">Retention</span>留存</h2>
<div class="card"><div class="ch"><div class="t">逐日留存</div><span class="tag">{W["retention_start"][5:]} 起 · 未成熟不画点</span></div><div class="cb">
{charts}
<details class="tbl"><summary>展开数据表</summary>
<table style="min-width:760px"><thead><tr><th rowspan="2">沙特日</th><th class="num" rowspan="2">活跃</th><th class="num" colspan="3">活跃日留存</th><th class="num" rowspan="2">新玩家</th><th class="num" colspan="3">新玩家 cohort</th></tr>
<tr><th class="num">D1</th><th class="num">D3</th><th class="num">D7</th><th class="num">D1</th><th class="num">D3</th><th class="num">D7</th></tr></thead>
<tbody>{"".join(rtrows)}</tbody></table>
</details>
</div></div>
<div class="card" style="margin-top:12px"><div class="ch"><div class="t">跨游戏对比 · {W["crossgame_start"][5:]}~{W["end"][5:]} 同口径</div></div><div class="cb">
<table><thead><tr><th>游戏</th><th class="num">玩家</th><th class="num">D1</th><th style="width:110px"></th><th class="num">D3</th><th class="num">D7</th></tr></thead>
<tbody>{"".join(grows)}</tbody></table>
</div></div></section>

<section><h2><span class="chap">Leaderboard</span>Caravan Glory 周榜</h2>
<div class="card"><div class="ch"><div class="t">赛期</div></div><div class="cb">
<table style="min-width:820px"><thead><tr><th>赛期</th><th class="num">参与</th><th class="num">当周活跃</th><th class="num">渗透</th><th class="num">计分事件</th><th class="num">结算奖励</th><th class="num">已领</th><th class="num">领奖率</th><th class="num">结算金币</th></tr></thead>
<tbody>{"".join(qrows)}</tbody></table>
</div></div>
<div class="card" style="margin-top:12px"><div class="ch"><div class="t">主榜分数</div></div><div class="cb">
<table><thead><tr><th>赛期</th><th class="num">第 1 名</th><th style="width:130px"></th><th class="num">第 10 名</th><th class="num">中位数</th><th class="num">Top100 总分</th></tr></thead>
<tbody>{"".join(srows)}</tbody></table>
</div></div></section>

{TIP_JS}
<footer>窗口 {W["start"]} ~ {W["end"]}（完整沙特日）· 漏斗与 Credits 来源取最近 {W["funnel_days"]} 天 · 抓取于 {D["fetched_at"]} · ⚠️ 看板会回补历史数据，当日数据不可用</footer>
</div></body></html>'''
out = os.path.normpath(os.path.join(HERE, CFG.get("OUT_HTML", "../04-Treasure-Camel.html")))
open(out, "w", encoding="utf-8").write(HTML)
print(f"✅ {out}  ({len(HTML.encode())/1024:.1f} KB)")
