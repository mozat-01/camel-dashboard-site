#!/bin/bash
# Treasure Camel 看板 · 一键刷新
# fetch 失败（含后台停机维护）时不渲染，保留上一版页面，不让线上变空白。
set -u
cd "$(dirname "$0")"
PY=/usr/bin/python3
echo "[$(date '+%F %T')] 开始"

# 先做语法预检：抓数要 1~2 分钟，渲染脚本的语法错不该等到那时才暴露
$PY -c "import ast,sys; [ast.parse(open(f,encoding='utf-8').read(), f) for f in ('fetch.py','render.py')]" || {
    echo "[$(date '+%F %T')] 脚本语法错误，终止"; exit 1; }

cp -f data.json data.json.prev 2>/dev/null || true

if ! $PY fetch.py; then
    echo "[$(date '+%F %T')] 抓数失败 → 跳过渲染，保留上一版页面"
    [ -f data.json.prev ] && mv -f data.json.prev data.json
    exit 1
fi

# guard：data.json 明显残缺就不发布（阈值按实际字段数调）
n=$($PY -c "import json;d=json.load(open('data.json'));print(sum(1 for k in ('summary','recent','lastday','glory','retention_daily','hit_daily') if d.get(k)))" 2>/dev/null || echo 0)
if [ "$n" -lt 4 ]; then
    echo "[$(date '+%F %T')] data.json 关键块只有 $n/6 → 跳过渲染，保留上一版页面"
    [ -f data.json.prev ] && mv -f data.json.prev data.json
    exit 1
fi

$PY render.py || { echo "[$(date '+%F %T')] 渲染失败"; exit 1; }
rm -f data.json.prev
echo "[$(date '+%F %T')] 完成"
