#!/usr/bin/env python3
# InstaBox 保活（Python 3.7+，仅标准库）。用法：
#   INSTABOX_API_KEY=ibk_xxx python3 keepalive.py          # 常驻，每 3 分钟续租
#   INSTABOX_API_KEY=ibk_xxx python3 keepalive.py --once   # 续租一次（给 cron 用）
# 可选：INSTABOX_MACHINE=名字或m_id（留空=全部） INSTABOX_LEASE_TTL=300
import json, os, sys, time, urllib.request, urllib.error

API = os.environ.get("INSTABOX_API_URL", "https://api.instabox.sh")
KEY = os.environ.get("INSTABOX_API_KEY") or sys.exit("请设置 INSTABOX_API_KEY")
MACHINE = os.environ.get("INSTABOX_MACHINE", "")
TTL = int(os.environ.get("INSTABOX_LEASE_TTL", "300"))
LEASE = "keepalive"

def req(method, path, body=None, extra=None):
    h = {"X-API-Key": KEY, "Content-Type": "application/json"}
    h.update(extra or {})
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(API + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            t = resp.read().decode()
            return resp.status, (json.loads(t) if t else {})
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return 0, str(e)

def machines():
    if MACHINE and MACHINE.lower() != "all":
        c, b = req("GET", "/v1/machines/" + MACHINE)
        return [b] if c == 200 else []
    c, b = req("GET", "/v1/machines")
    if c != 200: return []
    return b if isinstance(b, list) else b.get("machines") or b.get("data") or b.get("items") or []

def wake(mid):
    for act in ("resume", "start"):
        c, _ = req("POST", f"/v1/machines/{mid}/{act}", extra={"Idempotency-Key": f"ka-{act}-{mid}-{time.time()}"})
        if c in (200, 202): break
    for _ in range(6):
        time.sleep(5)
        c, b = req("GET", f"/v1/machines/{mid}")
        if c == 200 and b.get("state") == "running": return True
    return False

def renew(m):
    mid, name = m.get("id"), m.get("name", m.get("id"))
    path = f"/v1/machines/{mid}/activity-leases/{LEASE}"
    c, b = req("PUT", path, {"ttlSeconds": TTL})
    if c == 409 and any(k in str(b) for k in ("not_running", "suspended", "stopped")) and wake(mid):
        c, b = req("PUT", path, {"ttlSeconds": TTL})
    ok = c in (200, 204)
    print(time.strftime("%F %T"), name, "续租 ok" if ok else f"失败 HTTP {c}: {b}", flush=True)
    return ok

def once():
    ms = machines()
    if not ms: print(time.strftime("%F %T"), "没有找到机器", flush=True); return False
    return all([renew(m) for m in ms])

if __name__ == "__main__":
    if "--once" in sys.argv: sys.exit(0 if once() else 1)
    while True:
        once(); time.sleep(TTL * 3 // 5)
