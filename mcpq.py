import json,urllib.request,uuid
URL="https://ai-pg-mcp-test.loops-game.com/mcp"
def post(body,sid=None,timeout=900):
    h={'Content-Type':'application/json','Accept':'application/json, text/event-stream'}
    if sid: h['mcp-session-id']=sid
    req=urllib.request.Request(URL,data=json.dumps(body).encode(),headers=h,method='POST')
    r=urllib.request.urlopen(req,timeout=timeout)
    return r.headers.get('mcp-session-id'), r.read().decode()
def parse_sse(txt):
    out=[]
    for line in txt.splitlines():
        if line.startswith('data: '):
            try: out.append(json.loads(line[6:]))
            except Exception: pass
    return out
def session():
    sid,_=post({"jsonrpc":"2.0","id":1,"method":"initialize","params":{
        "protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"cli","version":"1"}}})
    post({"jsonrpc":"2.0","method":"notifications/initialized"},sid)
    return sid
def call(sid,tool,args,timeout=900):
    _,txt=post({"jsonrpc":"2.0","id":str(uuid.uuid4()),"method":"tools/call",
                "params":{"name":tool,"arguments":args}},sid,timeout)
    m=parse_sse(txt)
    return m[-1] if m else {"raw":txt[:400]}
