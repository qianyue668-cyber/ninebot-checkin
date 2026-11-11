# -*- coding: utf-8 -*-
"""
九号账号验证码登录 + 签到测试服务 v3
- http://127.0.0.1:8787  页面内嵌九号官网同款网易盾滑块
- 滑块通过 → 本服务端(带签名)调九号接口发送短信
- 填码登录(/login/sms,自动补前置会话)→ 保存 accessToken JWT
- 一键用 JWT 测试签到接口(状态查询 + 签到)
仅供测试本人账号自动签到可行性使用。
"""
import base64
import hashlib
import json
import socket
import time
import urllib.request
import urllib.parse
import urllib.error
import ssl
import http.cookiejar
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Windows 中文主机名下 socket.getfqdn 会触发 GBK 解码错误,直接短路掉
socket.getfqdn = lambda name="": name

CLIENT_KEY = "YA3B4KlBwym1"
AUTH_BASE = "https://account.ninebot.com"
GW = "https://cn-cbu-gateway.ninebot.com"
UA_APP = ("Mozilla/5.0 (iPhone; CPU iPhone OS 15_1 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Mobile/15E148 Segway v6 C 609033420")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
TOKEN_FILE = "ninebot_token.json"

CTX = ssl.create_default_context()


def log(*a):
    print(time.strftime("[%H:%M:%S]"), *a, flush=True)


def make_sign(obj):
    r = "&".join(f"{k}={obj[k]}" for k in sorted(obj))
    return hashlib.sha256(r.encode("utf-8")).hexdigest()


def auth_headers(sign_obj):
    ts = str(int(time.time() * 1000))
    sign_obj = dict(sign_obj)
    sign_obj.update({"timestamp": ts, "clientKey": CLIENT_KEY})
    return {
        "User-Agent": UA,
        "Content-Type": "application/json",
        "clientId": "USER_RIGHTS_CENTER_SELF",
        "region": "bj",
        "timestamp": ts,
        "sign": make_sign(sign_obj),
    }, ts


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def http_req(url, method="GET", headers=None, data=None, jar=None):
    if jar is None:
        jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), _NoRedirect())
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        resp = opener.open(req, timeout=20)
        return resp.status, dict(resp.headers), resp.read(), jar
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read(), jar


def jwt_decode(token):
    try:
        p = token.split(".")[1]
        p += "=" * (-len(p) % 4)
        return json.loads(base64.urlsafe_b64decode(p))
    except Exception as e:
        return {"decode_error": str(e)}


PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>九号账号 · 验证码登录 + 签到测试</title>
<script src="https://cstaticdun.126.net/load.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, "Microsoft YaHei", sans-serif; background:#f4f5f7; min-height:100vh;
         display:flex; align-items:center; justify-content:center; padding:16px; }
  .card { background:#fff; border-radius:16px; box-shadow:0 8px 30px rgba(0,0,0,.08);
          width:100%; max-width:460px; padding:32px 28px; }
  h1 { font-size:20px; margin-bottom:6px; }
  h2 { font-size:15px; margin:22px 0 4px; color:#555; }
  .sub { color:#888; font-size:13px; margin-bottom:20px; line-height:1.6; }
  label { display:block; font-size:13px; font-weight:600; margin:14px 0 6px; }
  input { width:100%; height:44px; border:1px solid #ddd; border-radius:8px; padding:0 12px; font-size:15px; }
  input:focus { outline:2px solid #111; border-color:transparent; }
  button { width:100%; height:46px; border:none; border-radius:8px; background:#111; color:#fff;
           font-size:15px; font-weight:600; cursor:pointer; margin-top:16px; }
  button:disabled { background:#bbb; cursor:not-allowed; }
  button.sec { background:#fff; color:#111; border:2px solid #111; }
  .msg { margin-top:16px; padding:12px; border-radius:8px; font-size:13px; line-height:1.7;
         word-break:break-all; display:none; white-space:pre-wrap; }
  .ok  { background:#e8f7ee; color:#0a7a3d; display:block; }
  .err { background:#fdecec; color:#c0392b; display:block; }
  .info{ background:#eef3fd; color:#2456c4; display:block; }
</style>
</head>
<body>
<div class="card">
  <h1>九号账号 · 验证码登录 + 签到测试</h1>
  <div class="sub">内嵌九号官网同款网易盾滑块。全部流程: 滑块 → 发短信 → 填码登录 → 自动保存令牌 → 测试签到接口。请求只发往 account.ninebot.com / cn-cbu-gateway.ninebot.com 和本地服务。</div>

  <label>手机号</label>
  <input id="phone" placeholder="11位手机号" maxlength="11">

  <button id="sendBtn" disabled>发送验证码</button>

  <label>短信验证码</label>
  <input id="smsCode" placeholder="6位数字" maxlength="6">
  <button id="loginBtn" disabled>提交验证码并登录(自动测签到接口)</button>

  <h2>签到测试(登录成功后可用)</h2>
  <button id="statusBtn" class="sec" disabled>查询签到状态</button>
  <label>deviceId(签到用,可先留空试)</label>
  <input id="deviceId" placeholder="抓包获得的 device_id,可留空">
  <button id="signBtn" class="sec" disabled>执行签到</button>

  <div id="msg" class="msg"></div>
</div>
<script>
const $ = id => document.getElementById(id);
const msgBox = $("msg");
let leftSec = 0, timer = null, TOKEN = "";

function show(cls, text) { msgBox.className = "msg " + cls; msgBox.textContent = text; }
function enableAll() { $("statusBtn").disabled = false; $("signBtn").disabled = false; }

$("phone").value = localStorage.getItem("nb_phone") || "";
$("phone").addEventListener("input", e => {
  localStorage.setItem("nb_phone", e.target.value.trim());
  $("sendBtn").disabled = !/^1\\d{10}$/.test(e.target.value.trim());
});
if (/^1\\d{10}$/.test($("phone").value.trim())) $("sendBtn").disabled = false;
$("smsCode").addEventListener("input", e => {
  $("loginBtn").disabled = !/^\\d{6}$/.test(e.target.value.trim());
});

function tick() {
  leftSec--;
  if (leftSec <= 0) { clearInterval(timer); $("sendBtn").disabled = false; $("sendBtn").textContent = "重新发送"; }
  else $("sendBtn").textContent = leftSec + "s 后可重发";
}

function popupCaptcha() {
  return new Promise((resolve, reject) => {
    if (!window.initNECaptcha) return reject(new Error("验证码组件加载失败(检查网络)"));
    window.initNECaptcha({
      captchaId: "78160de0d8604344b094f6e36df10083",
      element: "#captcha-host",
      mode: "popup",
      width: "320px",
      apiVersion: 2,
      lang: "zh-CN",
      popupStyles: { position: "fixed", top: "20%" },
      feedbackEnable: false,
      onVerify: (err, data) => {
        if (err) reject(new Error("verify error: " + (err && (err.msg || err.message || err.code || JSON.stringify(err)))));
        else resolve(data.validate);
      },
      onError: (err) => { window.__captchaErr = String(err && (err.msg || err.message || err)); },
      onClose: () => reject(new Error("captcha canceled"))
    }, ins => ins.verify(), err => reject(err));
  });
}

$("sendBtn").onclick = async () => {
  const phone = $("phone").value.trim();
  try { show("info", "正在弹出滑块验证..."); const validate = await popupCaptcha();
    show("info", "滑块通过,正在发送验证码...");
    const r = await fetch("/api/sendcode", { method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ phone, validate }) });
    const j = await r.json();
    if (j.upstream && (j.upstream.resultCode === "90000" || j.upstream.resultCode === "9000")) {
      show("ok", "✅ 短信已发送!请查收短信并填入验证码框。\\n" + JSON.stringify(j.upstream));
      leftSec = 60; $("sendBtn").disabled = true; $("sendBtn").textContent = "60s 后可重发";
      timer = setInterval(tick, 1000);
    } else {
      show("err", "❌ 发送失败\\n" + JSON.stringify(j.upstream || j, null, 2));
    }
  } catch (e) { show("err", "❌ " + (e.message || e)); }
};

$("loginBtn").onclick = async () => {
  const phone = $("phone").value.trim(), smsCode = $("smsCode").value.trim();
  try {
    show("info", "正在提交验证码登录(自动补前置会话)...");
    const r = await fetch("/api/login", { method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ phone, smsCode }) });
    const j = await r.json();
    if (j.ok && j.accessToken) {
      TOKEN = j.accessToken;
      show("ok", "🎉 登录成功!accessToken 已保存。\\nJWT: " + j.accessToken.slice(0, 40) + "...\\n\\n正在自动测试签到状态接口...");
      enableAll();
      $("statusBtn").click();
    } else {
      show("err", "❌ 登录失败\\n" + JSON.stringify(j, null, 2));
    }
  } catch (e) { show("err", "❌ " + (e.message || e)); }
};

$("statusBtn").onclick = async () => {
  try {
    show("info", "查询签到状态(网关)...");
    const r = await fetch("/api/checkin_status", { method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ token: TOKEN }) });
    const j = await r.json();
    show(j.ok ? "ok" : "err", "【签到状态接口】\\n" + JSON.stringify(j.upstream || j, null, 2));
  } catch (e) { show("err", "❌ " + (e.message || e)); }
};

$("signBtn").onclick = async () => {
  try {
    show("info", "执行签到(网关)...");
    const r = await fetch("/api/checkin", { method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ token: TOKEN, deviceId: $("deviceId").value.trim() }) });
    const j = await r.json();
    show(j.ok ? "ok" : "err", "【签到接口】\\n" + JSON.stringify(j.upstream || j, null, 2));
  } catch (e) { show("err", "❌ " + (e.message || e)); }
};
</script>
<div id="captcha-host"></div>
</div>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path == "/":
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._send({"error": "not found"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(n) or b"{}")

        if self.path == "/api/sendcode":
            phone, validate = payload.get("phone", ""), payload.get("validate", "")
            log(f"[sendcode] phone={phone} validate={validate[:24]}...")
            h, _ = auth_headers({"account": phone, "url": "/v3/region"})
            st, _, body, _ = http_req(f"{AUTH_BASE}/p/v3/region?account={phone}", headers=h)
            region = "bj"
            try:
                rj = json.loads(body)
                region = (rj.get("data") or {}).get("region") or "bj"
            except Exception:
                pass
            data = {"account": phone, "areaCode": "86", "rawTemplate": "login", "language": "zh",
                    "validate": validate}
            h, _ = auth_headers({**data, "url": "/v4/code/phone"})
            h["region"] = region
            st, _, body, _ = http_req(f"{AUTH_BASE}/p/v4/code/phone", method="POST",
                                      headers=h, data=json.dumps(data).encode())
            log(f"[sendcode] resp: HTTP {st} {body[:200]}")
            try:
                self._send({"upstream": json.loads(body)})
            except Exception:
                self._send({"upstream": {"raw": body.decode("utf-8", "replace")[:400]}})

        elif self.path == "/api/login":
            phone, smsCode = payload.get("phone", ""), payload.get("smsCode", "")
            log(f"[login] phone={phone} smsCode={smsCode}")
            jar = http.cookiejar.CookieJar()
            # 1) 前置会话
            st0, _, _, jar = http_req(f"{AUTH_BASE}/codeLogin", headers={"User-Agent": UA}, jar=jar)
            log(f"[login] pre-visit /codeLogin -> HTTP {st0}")
            # 2) 提交验证码
            form = urllib.parse.urlencode({"country": "CN", "areaCode": "86",
                                           "phone": phone, "smsCode": smsCode}).encode()
            st, hdrs, body, jar = http_req(
                f"{AUTH_BASE}/login/sms", method="POST",
                headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded",
                         "Origin": AUTH_BASE, "Referer": f"{AUTH_BASE}/codeLogin"},
                data=form, jar=jar)
            loc = hdrs.get("Location", "")
            log(f"[login] /login/sms -> HTTP {st} loc={loc}")
            cookies = {c.name: c.value for c in jar}
            log(f"[login] cookies: {list(cookies)}")
            token = cookies.get("accessToken", "")
            if not token:
                err = hdrs.get("Set-Cookie", "")[:80]
                self._send({"ok": False, "status": st, "location": loc, "cookies": list(cookies),
                            "hint": f"未拿到 accessToken(可能验证码错误/过期)。errorcode cookie: {err}"})
                return
            # 3) 跟随登录后跳转,巩固会话
            if loc:
                http_req(loc if loc.startswith("http") else AUTH_BASE + loc,
                         headers={"User-Agent": UA}, jar=jar)
            jwt_payload = jwt_decode(token)
            log(f"[login] SUCCESS jwt payload: {json.dumps(jwt_payload, ensure_ascii=False)[:300]}")
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                json.dump({"phone": phone, "accessToken": token, "jwt": jwt_payload,
                           "time": time.strftime("%Y-%m-%d %H:%M:%S")}, f, ensure_ascii=False, indent=2)
            self._send({"ok": True, "accessToken": token, "jwt": jwt_payload})

        elif self.path == "/api/checkin_status":
            token = payload.get("token", "")
            if not token and __import__("os").path.exists(TOKEN_FILE):
                token = json.load(open(TOKEN_FILE, encoding="utf-8")).get("accessToken", "")
            log(f"[checkin_status] token={token[:30]}...")
            headers = {"User-Agent": UA_APP, "Authorization": token,
                       "language": "zh", "Accept": "application/json",
                       "Origin": "https://h5-bj.ninebot.com", "Referer": "https://h5-bj.ninebot.com/"}
            st, _, body, _ = http_req(f"{GW}/portal/api/user-sign/v2/status?t={int(time.time()*1000)}",
                                      headers=headers)
            log(f"[checkin_status] HTTP {st} {body[:250]}")
            try:
                self._send({"ok": st == 200, "status": st, "upstream": json.loads(body)})
            except Exception:
                self._send({"ok": st == 200, "status": st, "raw": body.decode("utf-8", "replace")[:400]})

        elif self.path == "/api/checkin":
            token = payload.get("token", "")
            device_id = payload.get("deviceId", "")
            if not token and __import__("os").path.exists(TOKEN_FILE):
                token = json.load(open(TOKEN_FILE, encoding="utf-8")).get("accessToken", "")
            log(f"[checkin] token={token[:30]}... deviceId={device_id!r}")
            headers = {"User-Agent": UA_APP, "Authorization": token,
                       "language": "zh", "Accept": "application/json",
                       "Content-Type": "application/json",
                       "Origin": "https://h5-bj.ninebot.com", "Referer": "https://h5-bj.ninebot.com/"}
            data = {"deviceId": device_id} if device_id else {}
            st, _, body, _ = http_req(f"{GW}/portal/api/user-sign/v2/sign", method="POST",
                                      headers=headers, data=json.dumps(data).encode())
            log(f"[checkin] HTTP {st} {body[:250]}")
            try:
                self._send({"ok": st == 200, "status": st, "upstream": json.loads(body)})
            except Exception:
                self._send({"ok": st == 200, "status": st, "raw": body.decode("utf-8", "replace")[:400]})
        else:
            self._send({"error": "not found"}, 404)


if __name__ == "__main__":
    port = 8787
    print(f"九号账号验证码测试服务 v3 已启动: http://127.0.0.1:{port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
