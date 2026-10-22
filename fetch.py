#!/usr/bin/env python3
"""Treasure Camel 看板 · 抓数层
读 config.env → 拉后台 API + Redshift → 写 data.json
凭据只从 config.env 读取，不打印、不落盘到 data.json。
"""
import json, os, sys, time, urllib.request, urllib.error, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
# 2026-10-22 起改用 -test 域名。
# ⚠️ 别被名字骗了：`-test` 不是测试服，和 server-game.letskix.com 是**同一套后端**
#    （09-12~10-21 窗口活跃 490 / spin 377,419，与旧域名数据接得上）。
#    README/HANDOFF 里原先写的「-test 是测试服、接口返回 401」是错的，
#    那次 401 是会话问题不是服务器问题。
# ⚠️ Cookie 按域名隔离，换域名必须重新登录。
HOST = os.environ.get("CAMEL_HOST") or "https://server-game-test.letskix.com"
BASE = "/app/41011/v1/admin/analytics"


# 停机维护时后台整站返回 503（页面标题 "Treasure Camel · Game update"），
# 所有路径都挡，包括登录接口。游戏更新是常态，定时跑一定会撞上，所以统一退避重试。
MAINTENANCE_WAITS = [30, 60, 120, 240, 480]   # 秒，累计约 15 分钟


def is_maintenance(code):
    return code in (502, 503, 504)


def http_json(req, what, tries=3):
    """发请求并解析 JSON；503 当作停机维护，按 MAINTENANCE_WAITS 退避重试。

    返回 (data, None) 或在彻底失败时 (None, 原因)。401 直接上抛由调用方处理。
    """
    waits = list(MAINTENANCE_WAITS)
    attempt = 0
    while True:
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                body = r.read()
                return (json.loads(body.decode()) if body else {}), None
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise
            if is_maintenance(e.code) and waits:
                w = waits.pop(0)
                print(f"  后台停机维护中（HTTP {e.code}），{w}s 后重试…（{what}）")
                time.sleep(w)
                continue
            if is_maintenance(e.code):
                return None, f"后台持续停机维护（HTTP {e.code}），已等待约 15 分钟仍未恢复"
            attempt += 1
            if attempt >= tries:
                return None, f"HTTP {e.code}"
            time.sleep(3)
        except Exception as e:
            attempt += 1
            if attempt >= tries:
                return None, str(e)
            time.sleep(3)


def login(password, username="admin"):
    """用管理员账号密码换一张会话 Cookie。

    后台是 REST 风格，会话即资源：
        POST /v1/admin/session  {"username": "admin", "password": "..."}
    成功返回 204 + Set-Cookie（treasure_camel_admin，Max-Age=86400 即 24 小时）。

    ⚠️ 只认 POST，用 GET 试会返回 404 —— 早期因此误判成「后台没有登录接口」。
    ⚠️ 2026-10-22 接口增加了 username 字段（前端输入框默认值就是 admin）；
       在此之前只要 password。用 CAMEL_USERNAME 可覆盖。
    """
    body = json.dumps({"username": username, "password": password}).encode()
    req = urllib.request.Request(
        f"{HOST}/app/41011/v1/admin/session", data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "User-Agent": "camel-dashboard/1.0"})
    waits = list(MAINTENANCE_WAITS)
    while True:
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                cookies = [v for k, v in r.getheaders() if k.lower() == "set-cookie"]
            break
        except urllib.error.HTTPError as e:
            if e.code == 401:
                sys.exit("登录失败：管理员密码不对（接口返回 401）。")
            if is_maintenance(e.code) and waits:
                w = waits.pop(0)
                print(f"  后台停机维护中（HTTP {e.code}），{w}s 后重试登录…")
                time.sleep(w)
                continue
            if is_maintenance(e.code):
                sys.exit(f"后台停机维护中（HTTP {e.code}），已等待约 15 分钟仍未恢复。"
                         "游戏更新期间整站都会 503，稍后再跑即可——本次不发布，保留上一版页面。")
            sys.exit(f"登录失败：HTTP {e.code}")
        except Exception as e:
            sys.exit(f"登录失败：连不上后台（{e}）")
    # Set-Cookie 整行形如 "name=value; Path=...; HttpOnly"，只取 name=value 段
    pairs = [c.split(";", 1)[0].strip() for c in cookies if "=" in c]
    if not pairs:
        sys.exit("登录返回里没有 Set-Cookie，后台行为可能变了，需要重新确认登录协议。")
    return "; ".join(pairs)


def load_config():
    cfg = {}
    with open(os.path.join(HERE, "config.env"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    # 环境变量优先，便于 CI 用 Secrets 注入而不落盘
    for k in ("CAMEL_USERNAME", "CAMEL_PASSWORD", "CAMEL_COOKIE"):
        if os.environ.get(k):
            cfg[k] = os.environ[k]
    cfg.setdefault("CAMEL_USERNAME", "admin")
    # 有密码就自动换票（24 小时有效，每次跑都重新换，不用管过期）；
    # 没密码才退回手填 Cookie。
    if cfg.get("CAMEL_PASSWORD"):
        print(f"· 用 {cfg['CAMEL_USERNAME']} 登录后台换会话（{HOST}）")
        cfg["CAMEL_COOKIE"] = login(cfg["CAMEL_PASSWORD"], cfg["CAMEL_USERNAME"])
    elif not cfg.get("CAMEL_COOKIE"):
        sys.exit("config.env 里 CAMEL_PASSWORD 和 CAMEL_COOKIE 都是空的，"
                 "填 CAMEL_PASSWORD 即可自动登录（推荐）。")
    cfg.setdefault("RETENTION_START", "2026-09-15")
    cfg.setdefault("FUNNEL_DAYS", "10")
    cfg.setdefault("HIT_DAYS", "7")
    if not cfg.get("WINDOW_END"):
        # 沙特日的「昨天」＝ UTC+3 当前时间减一天
        riy = dt.datetime.utcnow() + dt.timedelta(hours=3)
        cfg["WINDOW_END"] = (riy - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    return cfg


def api(cfg, path, **params):
    params.setdefault("sourceApp", "loops")
    params.setdefault("includeTest", "false")
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(
        f"{HOST}{BASE}/{path}?{qs}",
        headers={"Accept": "application/json", "Cookie": cfg["CAMEL_COOKIE"],
                 "User-Agent": "camel-dashboard/1.0"})
    try:
        data, err = http_json(req, what=path)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            sys.exit("后台返回 401：会话失效了。填了 CAMEL_PASSWORD 的话重跑即可自动换票；"
                     "用手填 Cookie 的话按 config.env 里的说明重取一次。")
        raise
    if err:
        sys.exit(f"抓 {path} 失败：{err}。本次不发布，保留上一版页面。")
    return data


def daterange(a, b):
    d0 = dt.date.fromisoformat(a); d1 = dt.date.fromisoformat(b)
    while d0 <= d1:
        yield d0.isoformat(); d0 += dt.timedelta(days=1)


def riyadh_day(iso_ts):
    t = dt.datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    return (t + dt.timedelta(hours=3)).date().isoformat()


def mondays(a, b):
    """窗口内所有周榜赛期 id（沙特周一）"""
    d = dt.date.fromisoformat(a)
    d -= dt.timedelta(days=d.weekday())           # 回退到周一
    out = []
    end = dt.date.fromisoformat(b)
    while d <= end:
        out.append(d.isoformat()); d += dt.timedelta(days=7)
    return out


def redshift(sql, tries=6):
    sys.path.insert(0, HERE)
    import mcpq
    for i in range(tries):
        try:
            s = mcpq.session()
            r = mcpq.call(s, "query", {"sql": sql}, timeout=600)
            t = r["result"]["content"][0]["text"]
            if '"error"' not in t[:40]:
                return json.loads(t)["rows"]
        except Exception:
            pass
        time.sleep(8)
    print("  ⚠️ Redshift 连不上，这部分留空", file=sys.stderr)
    return []


def main():
    cfg = load_config()
    A, B = cfg["WINDOW_START"], cfg["WINDOW_END"]
    RS, CG = cfg["RETENTION_START"], cfg.get("CROSSGAME_START", "2026-10-01")
    FD, HD = int(cfg["FUNNEL_DAYS"]), int(cfg["HIT_DAYS"])
    RA = (dt.date.fromisoformat(B) - dt.timedelta(days=FD - 1)).isoformat()
    out = {"window": {"start": A, "end": B, "retention_start": RS, "crossgame_start": CG,
                      "funnel_from": RA, "funnel_days": FD, "hit_days": HD},
           "fetched_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M")}

    print(f"窗口 {A} ~ {B}（漏斗/发放只看 {RA} ~ {B}）")
    print("· 全窗 summary")
    out["summary"] = api(cfg, "summary", **{"from": A, "to": B})

    print(f"· 最近 {FD} 天 summary（漏斗 + Credits 来源）")
    out["recent"] = api(cfg, "summary", **{"from": RA, "to": B})

    print(f"· 最后一个完整日 summary（{B}，用于顶部 KPI）")
    out["lastday"] = api(cfg, "summary", **{"from": B, "to": B})

    print(f"· 跨游戏对比同窗 summary（{CG} ~ {B}）")
    out["crosswin"] = api(cfg, "summary", **{"from": CG, "to": B})

    print("· 逐日留存", end="", flush=True)
    out["retention_daily"] = []
    for d in daterange(RS, B):
        j = api(cfg, "summary", **{"from": d, "to": d})
        ar = j["activeRetention"]["retention"]
        co = j["retention"]
        out["retention_daily"].append({
            "date": d, "active": j["gameplay"]["activePlayers"],
            "ar": [{"d": x["day"], "num": x["returnedPlayerDays"],
                    "den": x["eligiblePlayerDays"], "rate": x["rate"]} for x in ar],
            "co": [{"d": x["day"], "num": x["returnedPlayers"],
                    "den": x["eligiblePlayers"], "rate": x["rate"]} for x in co]})
        print(".", end="", flush=True)
    print()

    print("· 逐日新玩家")
    h = api(cfg, "spins", **{"from": "2026-09-01", "to": B, "limit": 1})
    first = {}
    for r in h.get("rows", []):
        d = riyadh_day(r["settledAt"])
        if r["uid"] not in first or d < first[r["uid"]]:
            first[r["uid"]] = d
    newp = {}
    for d in first.values():
        newp[d] = newp.get(d, 0) + 1
    out["new_players"] = newp

    print("· 逐日 spin 明细（命中率）", end="", flush=True)
    hits = {}
    for d in daterange(A, B):
        j = api(cfg, "spins", **{"from": d, "to": d, "limit": 100})
        rows = [r for r in j.get("rows", []) if int(r["wager"]) > 0]
        if not rows:
            continue
        n = len(rows)
        hit = [r for r in rows if int(r["payout"]) > 0]
        win = [r for r in rows if r["result"] == "WIN"]
        mult = sorted(int(r["payout"]) / int(r["wager"]) for r in hit)
        hits[d] = {"spins": n, "hit": len(hit), "win": len(win),
                   "sub1": sum(1 for m in mult if m < 1),
                   "median_mult": round(mult[len(mult) // 2], 2) if mult else None,
                   "wager": sum(int(r["wager"]) for r in rows),
                   "payout": sum(int(r["payout"]) for r in rows)}
        print(".", end="", flush=True)
    print()
    out["hit_daily"] = hits

    print("· 周榜赛期")
    out["glory"] = []
    for pid in mondays(A, B):
        g = api(cfg, "glory", period=pid)
        if g.get("error"):
            continue
        rk = sorted((int(x["score"]) for x in g["leaderboards"]["rank"]), reverse=True)
        pa = dt.date.fromisoformat(pid)
        pb = min(pa + dt.timedelta(days=6), dt.date.fromisoformat(B))
        wk = api(cfg, "summary", **{"from": pa.isoformat(), "to": pb.isoformat()})
        out["glory"].append({
            "id": pid, "from": pa.isoformat(), "to": (pa + dt.timedelta(days=6)).isoformat(),
            "settled_at": g["period"]["settledAt"],
            "participants": g["authoritative"]["participants"],
            "score_events": g["authoritative"]["scoreEvents"],
            "settled_rewards": g["authoritative"]["settledRewards"],
            "claimed_rewards": g["authoritative"]["claimedRewards"],
            "settled_coins": g["authoritative"]["settledCoins"],
            "week_active": wk["gameplay"]["activePlayers"],
            "rank_top1": rk[0] if rk else 0,
            "rank_top10": rk[9] if len(rk) > 9 else (rk[-1] if rk else 0),
            "rank_median": rk[len(rk) // 2] if rk else 0,
            "rank_total": sum(rk)})

    print("· Redshift：跨游戏留存")
    d1c = (dt.date.fromisoformat(B) - dt.timedelta(days=1)).isoformat()
    d3c = (dt.date.fromisoformat(B) - dt.timedelta(days=3)).isoformat()
    d7c = (dt.date.fromisoformat(B) - dt.timedelta(days=7)).isoformat()
    lo = (dt.date.fromisoformat(CG) - dt.timedelta(days=1)).isoformat()
    out["crossgame"] = redshift(f"""WITH a AS (
 SELECT REPLACE(REPLACE(SPLIT_PART(remark,':',1),' activity cost coins',''),' activity second spin cost coins','') AS g,
        user_id, DATE(DATEADD(hour,3,create_on)) AS dt
 FROM dms.loops_treasure_adjust WHERE adjust_type=10005
   AND create_on>=TIMESTAMP '{lo} 21:00:00' AND create_on<TIMESTAMP '{B} 21:00:00'
 GROUP BY 1,2,3)
SELECT a.g, COUNT(DISTINCT a.user_id) uu,
 SUM(CASE WHEN a.dt<=DATE '{d1c}' THEN 1 ELSE 0 END) den1,
 SUM(CASE WHEN a.dt<=DATE '{d1c}' AND r1.user_id IS NOT NULL THEN 1 ELSE 0 END) num1,
 SUM(CASE WHEN a.dt<=DATE '{d3c}' THEN 1 ELSE 0 END) den3,
 SUM(CASE WHEN a.dt<=DATE '{d3c}' AND r3.user_id IS NOT NULL THEN 1 ELSE 0 END) num3,
 SUM(CASE WHEN a.dt<=DATE '{d7c}' THEN 1 ELSE 0 END) den7,
 SUM(CASE WHEN a.dt<=DATE '{d7c}' AND r7.user_id IS NOT NULL THEN 1 ELSE 0 END) num7
FROM a LEFT JOIN a r1 ON r1.g=a.g AND r1.user_id=a.user_id AND r1.dt=a.dt+1
 LEFT JOIN a r3 ON r3.g=a.g AND r3.user_id=a.user_id AND r3.dt=a.dt+3
 LEFT JOIN a r7 ON r7.g=a.g AND r7.user_id=a.user_id AND r7.dt=a.dt+7
GROUP BY 1 ORDER BY den1 DESC""")

    print("· Redshift：逐日兑换")
    lo2 = (dt.date.fromisoformat(A) - dt.timedelta(days=1)).isoformat()
    out["exchange_daily"] = redshift(f"""SELECT DATE(DATEADD(hour,3,create_on)) AS d,
 COUNT(DISTINCT user_id) ppl, COUNT(*) n, SUM(ABS(coins_adjust)) c
FROM dms.loops_treasure_adjust WHERE adjust_type=10005 AND game_app_id=300012 AND coins_adjust<0
 AND create_on>=TIMESTAMP '{lo2} 21:00:00' AND create_on<TIMESTAMP '{B} 21:00:00'
GROUP BY 1 ORDER BY 1""")
    out["exchange_total"] = redshift(f"""SELECT COUNT(DISTINCT user_id) ppl, COUNT(*) n, SUM(ABS(coins_adjust)) c
FROM dms.loops_treasure_adjust WHERE adjust_type=10005 AND game_app_id=300012 AND coins_adjust<0
 AND create_on>=TIMESTAMP '{lo2} 21:00:00' AND create_on<TIMESTAMP '{B} 21:00:00'""")

    with open(os.path.join(HERE, "data.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n✅ data.json 已写入（{B} 为止）")


if __name__ == "__main__":
    main()
