#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
九号出行 自动签到脚本(供 GitHub Actions / 本地 python 运行)
环境变量:
  NINEBOT_ACCOUNTS  JSON 数组: [{"name":"主号","token":"eyJ...","deviceId":""}, ...]
  NINEBOT_TOKEN     单账号快捷方式(与 NINEBOT_ACCOUNTS 二选一)
  NINEBOT_DEVICE_ID 单账号的 deviceId(可选)
  BARK_KEY          可选, Bark 推送
说明:
  - token 通过仓库里的 login_helper.py(免抓包验证码登录)获取, 约 30 天有效
  - Authorization 头使用裸 token(不要加 Bearer 前缀)
"""
import base64
import gzip
import json
import os
import random
import ssl
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

GW = "https://cn-cbu-gateway.ninebot.com"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 15_1 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Mobile/15E148 Segway v6 C 609033420")
CTX = ssl.create_default_context()
TIMEOUT = 25


def log(msg):
    print(time.strftime("[%Y-%m-%d %H:%M:%S]"), msg, flush=True)


def mask(tok):
    return tok[:12] + "..." + tok[-6:] if len(tok) > 24 else "***"


def read_body(resp):
    b = resp.read()
    if b[:2] == b"\x1f\x8b":
        try:
            b = gzip.decompress(b)
        except Exception:
            pass
    return b.decode("utf-8", "replace")


def gw(method, path, token, data=None):
    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh-Hans;q=0.9",
        "Origin": "https://h5-bj.ninebot.com",
        "Referer": "https://h5-bj.ninebot.com/",
        "language": "zh",
        "Authorization": token,  # 注意: 裸 token, 无 Bearer 前缀
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(data).encode()
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(f"{GW}{path}", data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, context=CTX, timeout=TIMEOUT) as r:
                return json.loads(read_body(r))
        except urllib.error.HTTPError as e:
            try:
                return json.loads(read_body(e))
            except Exception:
                last_err = f"HTTP {e.code}"
        except Exception as e:
            last_err = str(e)
        time.sleep(2 + attempt * 2)
    return {"code": -1, "msg": f"network error: {last_err}"}


def jwt_exp(token):
    try:
        p = token.split(".")[1]
        p += "=" * (-len(p) % 4)
        return json.loads(base64.urlsafe_b64decode(p)).get("exp", 0)
    except Exception:
        return 0


def bark_push(key, title, body):
    if not key:
        return
    try:
        url = ("https://api.day.app/" + key + "/" + urllib.parse.quote(title, safe="")
               + "/" + urllib.parse.quote(body, safe="") + "?group=ninebot-checkin")
        with urllib.request.urlopen(url, timeout=10) as r:
            log("Bark 推送: " + r.read().decode("utf-8", "replace")[:120])
    except Exception as e:
        log("Bark 推送失败: " + str(e))


def run_account(acc, idx):
    name = acc.get("name") or f"账号{idx + 1}"
    token = (acc.get("token") or "").strip()
    device_id = (acc.get("deviceId") or "").strip()
    result = {"name": name, "ok": False, "msg": ""}

    if not token:
        result["msg"] = "缺少 token"
        return result
    exp = jwt_exp(token)
    if exp:
        left = exp - time.time()
        log(f"[{name}] token 到期时间: {time.strftime('%Y-%m-%d %H:%M', time.localtime(exp))}"
            + (f"(剩余 {left/86400:.1f} 天)" if left > 0 else "(已过期!)"))
        if left <= 0:
            result["msg"] = "token 已过期, 请用 login_helper.py 重新获取"
            return result

    log(f"[{name}] 查询签到状态... token={mask(token)}")
    st = gw("GET", f"/portal/api/user-sign/v2/status?t={int(time.time() * 1000)}", token)
    if st.get("code") != 0:
        result["msg"] = f"状态查询失败: {st.get('msg')}(token 可能失效)"
        return result
    d = st.get("data") or {}
    days = d.get("consecutiveDays", 0)
    result["days"] = days
    log(f"[{name}] 连续签到 {days} 天, 今日{'已签' if d.get('currentSignStatus') == 1 else '未签'}")

    if d.get("currentSignStatus") == 1:
        result["ok"] = True
        result["msg"] = f"今日已签到(连续{days}天)"
        return result

    log(f"[{name}] 执行签到...")
    body = {"deviceId": device_id} if device_id else {}
    r = gw("POST", "/portal/api/user-sign/v2/sign", token, body)
    code, msg = r.get("code"), r.get("msg", "")
    if code == 0:
        result["ok"] = True
        result["msg"] = "签到成功"
    elif code == 540004 or "already signed" in msg:
        result["ok"] = True
        result["msg"] = "今日已签到(连续%d天)" % days
    else:
        result["msg"] = f"签到失败: code={code} {msg}"
        if not device_id:
            result["msg"] += "(提示: 若持续失败, 请抓包补充 deviceId)"
    # 签到后重查状态
    st2 = gw("GET", f"/portal/api/user-sign/v2/status?t={int(time.time() * 1000)}", token)
    if st2.get("code") == 0:
        d2 = st2.get("data") or {}
        result["days"] = d2.get("consecutiveDays", days)
        if d2.get("currentSignStatus") == 1 and code == 0:
            result["msg"] = f"签到成功(连续{result['days']}天)"
    return result


def main():
    accounts = []
    raw = os.environ.get("NINEBOT_ACCOUNTS", "").strip()
    if raw:
        try:
            accounts = json.loads(raw)
        except Exception as e:
            log("NINEBOT_ACCOUNTS 解析失败: " + str(e))
            sys.exit(1)
    elif os.environ.get("NINEBOT_TOKEN", "").strip():
        accounts = [{"name": "默认账号", "token": os.environ["NINEBOT_TOKEN"],
                     "deviceId": os.environ.get("NINEBOT_DEVICE_ID", "")}]
    else:
        log("未配置账号: 请设置 NINEBOT_ACCOUNTS 或 NINEBOT_TOKEN")
        sys.exit(1)

    time.sleep(random.uniform(0, 120))  # Actions 高峰错峰
    results = [run_account(a, i) for i, a in enumerate(accounts)]

    lines = []
    for r in results:
        mark = "✅" if r["ok"] else "❌"
        lines.append(f"{mark} {r['name']}: {r['msg']}")
        log(f"{mark} {r['name']}: {r['msg']}")
    bark_push(os.environ.get("BARK_KEY", ""), "九号出行签到结果", "\n".join(lines))
    sys.exit(0 if all(r["ok"] for r in results) else 1)


if __name__ == "__main__":
    main()
