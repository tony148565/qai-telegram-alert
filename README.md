# 秋AI-灵枢 | QAI-Synapse 专业 Telegram 警报机器人

**版本**: 2.0 (完整支持 Pine Script Schema v2.0)  
**作者**: 无秋 (X: @mackeybht)  
**适用对象**: 秋AI-灵枢 v1.3+ 用户

---

## ✨ 核心特性

- ✅ **完整事件支持**：entry（开仓）、sl_hit、partial_exit（TP1/TP2/TP3）、trade_closed、daily_summary、drawdown_alert、kill_switch、test_alert 等
- ✅ **专业富文本**：HTML 格式 + 表情符号 + 代码块，手机/PC 端均美观
- ✅ **签名验证**：与 Pine Script 简单签名机制一致，防止伪造
- ✅ **Web 仪表盘**：`/dashboard` 实时查看最近 25 条警报历史（带 SQLite 持久化）
- ✅ **多 Chat 支持**：可同时推送到多个 Telegram 群组/频道/个人
- ✅ **生产级**：日志轮转、异常重试、环境变量配置、健康检查
- ✅ **一键部署**：支持 Render / Railway / VPS / Docker

---

## 📋 部署详细流程（推荐 Render.com 免费版）

### 步骤 1：创建 Telegram Bot

1. 打开 Telegram，搜索 **@BotFather**
2. 发送 `/newbot`
3. 按提示输入 Bot 名称（如 `QAI_Synapse_Alert`）和用户名（必须以 `bot` 结尾）
4. 复制 **BOT_TOKEN**（格式：`123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`）

### 步骤 2：获取 Chat ID

**个人聊天**：
- 给你的 Bot 发送任意消息
- 访问 `https://api.telegram.org/bot<你的BOT_TOKEN>/getUpdates`
- 在 JSON 中找到 `"chat":{"id": 你的ID}`

**群组/超级群组**：
- 将 Bot 加入群组并设为管理员
- 发送 `/start` 或任意消息给 Bot
- 用上面方法获取负数 ID（例如 `-1001234567890`）

**多个 Chat**：用英文逗号分隔，例如 `-1001234567890,-1009876543210`

### 步骤 3：部署到 Render.com（最简单，免费 HTTPS）

1. 注册 [Render.com](https://render.com)（GitHub 登录即可）
2. 点击 **New +** → **Web Service**
3. 连接你的 GitHub 仓库（或直接上传 ZIP）
4. 配置：
   - **Name**: `qai-telegram-bot`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn -w 2 -b 0.0.0.0:$PORT app:app`
   - **Plan**: Free
5. 添加 **Environment Variables**（从 `.env.example` 复制）：
   ```
   BOT_TOKEN=你的真实token
   CHAT_IDS=-1001234567890,-1009876543210
   WEBHOOK_SECRET=your_super_secret_key_2026_qai   （必须与 Pine Script 一致！）
   PORT=10000
   TZ=Asia/Hong_Kong
   ```
6. 点击 **Create Web Service**
7. 部署完成后，复制你的 **Render URL**（例如 `https://qai-telegram-bot.onrender.com`）

### 步骤 4：配置 TradingView 警报

在 Pine Script **设置 → 警报** 中：

- **Webhook URL**: `https://你的Render域名/webhook`
- **Webhook JSON 格式**: 保持默认（或开启 `启用高级 Webhook 功能`）
- **Webhook Secret**: 填入与上面 `WEBHOOK_SECRET` **完全一致** 的值
- 建议开启 `每日战绩总结 Webhook`

**测试**：
1. 在 Pine Script 设置中开启 `一键测试警报`
2. 保存指标 → 打开警报设置 → 手动触发测试
3. 确认 Telegram 收到 `✅ WEBHOOK TEST PASSED` 消息

---

## 🛠️ 本地 / VPS 部署（Docker 推荐）

```bash
# 1. 克隆或下载项目
git clone <你的仓库> qai-telegram-bot
cd qai-telegram-bot

# 2. 配置环境变量
cp .env.example .env
nano .env   # 编辑真实值

# 3. Docker 一键启动（推荐）
docker build -t qai-bot .
docker run -d --name qai-bot -p 8080:8080 --env-file .env qai-bot

# 4. 或直接 Python 运行（需安装依赖）
pip install -r requirements.txt
python app.py
```

**systemd 服务文件**（VPS 推荐）见 `deploy/qai-bot.service`（可自行创建）。

---

## 📊 访问仪表盘

部署成功后访问：
- `https://你的域名/dashboard` → 实时警报历史表格
- `https://你的域名/health` → 健康检查 JSON

---

## 🔐 安全建议（生产必读）

1. **强烈建议设置 `WEBHOOK_SECRET`**（与 Pine Script 保持一致）
2. 使用 HTTPS（Render/Railway 自动提供）
3. 限制 Chat ID 只允许授权群组
4. 定期检查日志：`logs/qai_bot.log`
5. 建议开启 Render 的 **Auto-Deploy** + GitHub 连接

---

## 📁 项目文件说明

```
qai-telegram-bot/
├── app.py                  # 主程序（Flask + 所有逻辑）
├── requirements.txt        # 依赖
├── .env.example            # 环境变量模板
├── README.md               # 本文档
├── Dockerfile              # Docker 构建文件（可选）
└── logs/                   # 自动生成日志
```

---

## ❓ 常见问题

**Q: 收到 "Invalid signature"？**  
A: 检查 Pine Script 中的 `webhookSecret` 与 Flask `.env` 中的 `WEBHOOK_SECRET` 是否**完全一致**（包括大小写）。

**Q: 消息乱码？**  
A: 确保 Telegram Bot 支持 HTML parse_mode（默认已开启）。

**Q: 如何添加更多 Chat？**  
A: 修改 `.env` 中的 `CHAT_IDS`，重启服务即可。

**Q: 想自定义消息格式？**  
A: 编辑 `app.py` 中的 `format_xxx_message` 函数，保存后重启。

**Q: 支持多时间框架同时警报？**  
A: 完全支持！每个警报都会带 `tf` 字段。

---

## 📞 支持与反馈

- 作者 X: [@mackeybht](https://x.com/mackeybht)
- 指标更新群（可选）：联系作者加入

**© 2026 无秋 | 仅供个人学习研究使用 | 交易有风险**

---

**部署完成后，记得在 Pine Script 中开启 `启用高级 Webhook 功能 (Schema v2.0 + 签名)`，享受完整专业体验！**