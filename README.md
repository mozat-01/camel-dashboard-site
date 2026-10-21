# Treasure Camel 看板

固定链接的静态看板。每天由 GitHub Actions 自动抓数、渲染、推送，Cloudflare Pages 监听仓库自动部署。
**链接永远不变**，更新看板＝往仓库 push 一个新的 `site/index.html`。

```
server-game.letskix.com 后台 API ─┐
                                  ├─ fetch.py ─→ data.json ─→ render.py ─→ site/index.html
Redshift MCP（逐日兑换/跨游戏留存）┘                                              │
                                                              GitHub Actions 自动 commit + push
                                                                                 ↓
                                                        Cloudflare Pages 一推就部署（URL 固定）
```

只用 Python 标准库，无需 `pip install`。

---

## 本地跑

```bash
cp config.ci.env config.env     # 首次：从模板建配置
# 编辑 config.env，填 CAMEL_PASSWORD=<管理员密码>，并把 OUT_HTML 改回 ../04-Treasure-Camel.html
./run.sh
```

不想把密码写进文件：

```bash
read -s -p "密码: " CAMEL_PASSWORD && export CAMEL_PASSWORD && ./run.sh; unset CAMEL_PASSWORD
```

环境变量优先级高于 `config.env`。

---

## 部署（一次性）

1. **建 GitHub 仓库**，把这个目录整个推上去
2. **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `CAMEL_PASSWORD`
   - Value: 后台管理员密码
   - 🛑 凭据只能放这里。`config.env` 已在 `.gitignore` 里，别手动加回来
3. **Cloudflare → Pages → Connect to Git** 选这个仓库
   - Build command：**留空**（HTML 已渲染好，不需要构建）
   - Build output directory：**`site`**
4. 部署完拿到 `xxx.pages.dev`，之后全自动

Actions 一天跑 5 次（UTC 23:30 / 02:30 / 06:30 / 10:30 / 14:30），也可在 Actions 页手动触发。

---

## 认证：密码自动换票

后台是 REST 风格，会话即资源：

```
POST /app/41011/v1/admin/session   {"password": "..."}
  → 204 + Set-Cookie: treasure_camel_admin=...（Max-Age=86400，24 小时）
DELETE 同一路径 = 登出
```

⚠️ **只认 POST**，用 GET 试会返回 404 —— 早期因此误判成「后台没有登录接口」，白绕了很久。

脚本每次跑都重新登录换票，所以 24 小时的有效期根本碰不到，**不需要人工维护 Cookie**。
`config.env` 里的 `CAMEL_COOKIE` 只是没有密码时的兜底。

---

## 停机维护与 guard

游戏更新时后台**整站返回 503**（页面标题 `Treasure Camel · Game update`），所有路径都挡，包括登录接口。
定时跑一定会撞上，所以：

- `fetch.py` 把 502/503/504 当作停机维护，按 30s→60s→120s→240s→480s 退避重试（累计约 15 分钟）
- 仍不恢复就退出非 0，**不写半截 data.json**
- Actions 里的 guard：`data.json` 6 个关键块少于 4 个就跳过渲染和发布

⇒ 停机的结果是「页面数据停在上一天」，而不是「页面变空白或半截」。

---

## 配置项（config.env / config.ci.env）

| 键 | 说明 |
|---|---|
| `CAMEL_PASSWORD` | 管理员密码。CI 用 Secrets 注入，本地写 `config.env` |
| `CAMEL_COOKIE` | 兜底，手填 Cookie。填了密码就忽略这项 |
| `WINDOW_START` | 统计窗口起始日 |
| `WINDOW_END` | **留空＝自动取昨天**（沙特日）。定时跑时保持留空 |
| `RETENTION_START` | 逐日留存表起始日 |
| `FUNNEL_DAYS` | 漏斗与 Credits 来源只看最近 N 天 |
| `HIT_DAYS` | 单次 Spin 结果分布只看最近 N 天 |
| `CROSSGAME_START` | 跨游戏留存对比起始日（Redshift 侧） |
| `OUT_HTML` | 输出路径。CI 固定 `site/index.html` |

---

## 页面结构（固定，不随数据变）

| 区块 | 内容 |
|---|---|
| 页首 | 5 个 KPI：去重活跃 / 活跃日留存 D7 / 命中率 / 兑换笔数 / credits 免费占比 |
| Scale 规模 | 逐日表：活跃 · 新玩家 · Spin · 人均 · 兑换人数 · 兑换 Coins · RTP · 净消耗 |
| Funnel 变现 | 激活与兑换漏斗 · Credits 来源 · 单次 Spin 结果分布 |
| Retention 留存 | 活跃日留存 · 新玩家 cohort · 跨游戏对比 |
| Leaderboard 周榜 | 赛期（参与/渗透/结算/领奖率）· 主榜分数 |

**页面里没有任何文字判读**，全是数字和口径标签。要加结论另起文档，别往页面里塞。

图表配色用 dataviz 规范分类色板前三槽，深浅两色都过了对比度验证器。
浅色模式下绿色对背景只有 2.74:1，规范要求「可见标注**或**表格兜底」——
直接标注已按需求去掉，靠折叠数据表兜底，**那个表别删**。

---

## 改动指引

| 想改什么 | 改哪 |
|---|---|
| 窗口、各面板看几天 | `config.ci.env`（CI）/ `config.env`（本地） |
| 页面样式、图表配色 | `style.css` |
| 表格与图表生成逻辑 | `render.py` |
| 加新指标 | `fetch.py` 存进 `data.json` → `render.py` 读出来 |
| 跑的频率 | `.github/workflows/daily.yml` 的 cron |

---

## 已知口径坑

- **后台会回补历史数据**：同一已结束窗口隔天重读数字会变；当日数据在当天读会严重偏低
  （实测 09-29 当天读到活跃 23，次日读到 68）。所以 `WINDOW_END` 留空＝只取到昨天。
- **兑换两个口径不一致**：Redshift 的笔数对应后台的「尝试」而非「成功」（Coins 在发起时就扣），
  逐日表的笔数会略高于 KPI 里的成功数。差额核查过，原因是结算延迟与历史 SKU，**不是资损**。
- **后台域名别写错**：是 `server-game.letskix.com`，**不带 `-test`**。`-test` 是测试服，接口返回 401。
- `spins` 接口 `limit` 上限是 **100**，传更大直接 400。
- `glory` 接口对不存在的赛期返回 `{"error":...}`，代码里已跳过。
- 单日 `summary` 对未成熟的留存返回 `0/0`，渲染层显示「—」而不是 0%。
