# 九号出行 · 自动签到助手

九号出行(Segway-Ninebot)App 每日签到自动化:**免抓包**获取 token,网页一键签到,GitHub Actions 每天全自动。

## ✨ 特性

- 🚫 **免抓包**:内置网易盾滑块 + 短信验证码登录(走九号官网账号体系),直接拿到可用的 token
- 🌐 **纯静态单页**:`index.html` 可托管在 GitHub Pages,手机/电脑浏览器直接用,token 只存本地浏览器
- 🤖 **GitHub Actions 全自动**:每天北京时间 9 点左右自动签到,支持多账号 + Bark 推送
- 🔐 无任何第三方服务器,无统计,token 只存在你的浏览器 localStorage 或 GitHub Secrets

## 📁 文件

| 文件 | 用途 |
|---|---|
| `index.html` | 单页签到工具(GitHub Pages 托管 / 本地打开均可) |
| `checkin.py` | 签到脚本(GitHub Actions 定时运行 / 本地 python 运行) |
| `login_helper.py` | 免抓包登录助手(本地运行,滑块+验证码 → token) |
| `.github/workflows/checkin.yml` | Actions 定时任务定义 |

## 🚀 快速开始

### 第 1 步:获取 token(免抓包)

在电脑上:

```bash
pip install -r login_helper_requirements.txt   # 或直接无依赖运行(仅用标准库)
python login_helper.py
```

浏览器打开 `http://127.0.0.1:8787`:

1. 填手机号 → 拖动官方滑块 → 短信验证码发送到你的手机
2. 填入 6 位验证码 → 点"提交验证码并登录"
3. 登录成功,页面自动显示并保存 `accessToken`(eyJ 开头的 JWT)

> token 约 **30 天**有效,过期后重新运行一次登录助手即可。

### 第 2 步(二选一):使用方式

**A. 网页手动/半自动**:把 `index.html` 所在仓库开启 GitHub Pages(Settings → Pages),或直接本地双击打开。
页面上添加账号(粘贴 token)→ 点"全部签到"。开启"自动签到"后,每次打开页面会自动补签当天。

**B. GitHub Actions 全自动(推荐)**:

1. 把本仓库推送到你的 GitHub(建议 **Private**)
2. Settings → Secrets and variables → Actions → **New repository secret**
   - 名称:`NINEBOT_ACCOUNTS`
   - 值(多账号就是数组多元素):
     ```json
     [{"name":"主号","token":"eyJ...","deviceId":""}]
     ```
   - 可选:`SHOWDOC_PUSH_URL`(ShowDoc 推送地址,形如 `https://push.showdoc.com.cn/server/api/push/xxxx`,每次签到后推送成功/失败结果)
3. Actions → ninebot-checkin → **Run workflow** 手动跑一次验证
4. 之后每天 UTC 01:00(北京 9 点左右)自动执行,结果可推送 Bark

## ❓ FAQ

**签到返回 `系统错误`?**
Authorization 头必须是**裸 token**,不能带 `Bearer ` 前缀(已踩过坑)。

**`already signed in, cannot sign in again`?**
今天已经签过了,不是错误。

**token 过期了?**
页面会提前 3 天标红提醒。重新运行 `login_helper.py` 获取新 token,更新页面 localStorage 或 GitHub Secrets。

**deviceId 需要填吗?**
一般留空即可。若签到接口持续报错,再用抓包工具从 App 请求头里取 `device_id` 补上。

**GitHub 定时任务不准时/不跑了?**
Actions 的 cron 有 0~60 分钟随机延迟属正常;仓库 60 天无提交会被 GitHub 自动停用 cron,推个空提交或手动 Run 一次即可恢复。

## ⚠️ 声明

- 本项目仅用于**个人账号**的签到自动化,请自行评估与《九号出行用户条款》的冲突,勿用于任何商业用途
- 请勿把 token 提交进仓库(`.gitignore` 已防呆),泄露 token 等于泄露账号登录态

## 🙏 致谢与参考

- 接口来源参考: [waistu/Ninebot](https://github.com/waistu/Ninebot)、[KotoriMinami/qinglong-sign](https://github.com/KotoriMinami/qinglong-sign)
- 免抓包登录: 逆向自 `account.ninebot.com` 官网登录页公开前端代码(sha256 签名 + clientKey)
