# QAI-Synapse V1.3 Telegram Webhook Relay

**秋AI-灵枢 V1.3 专业级 Telegram 警报中继服务**

完整支持 Schema v2.0 的所有事件类型：
- Entry (LONG/SHORT)
- Partial Exits (TP1/TP2/TP3 狙击手)
- SL Hit / Break-Even
- Trade Closed Summary
- Daily Performance Summary (每天 8:00 UTC)
- Regime Change (BOS/CHOCH)
- Drawdown Alert / Kill Switch
- Test Alert

## 快速部署（Render.com 推荐）

1. Fork 本仓库或上传代码到 GitHub
2. 登录 [render.com](https://render.com)
3. New Web Service → 连接仓库
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `gunicorn app:app --workers 2 --threads 4 --timeout 60`
6. 添加环境变量：
   - `TELEGRAM_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `WEBHOOK_SECRET`（可选）
7. 部署完成后复制 URL，填入指标设置

## 本地运行

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入真实值
python app.py
```

访问 `http://localhost:5000/health` 测试

## 指标端配置

在 **秋AI-灵枢 V1.3** → 🔔 警报 模块：
- Entry Webhook URL: `https://你的域名/webhook/entry`
- Exit Webhook URL: `https://你的域名/webhook/exit`
- Webhook Secret: 与 .env 中一致
- 开启「启用高级 Webhook 功能」+「每日战绩总结」+「市场结构变化」

## 文件说明

- `app.py` - 主程序（已适配 V1.3 全部事件）
- `requirements.txt` - 依赖
- `Procfile` - Render/Heroku 启动配置
- `render.yaml` - 一键部署配置（可选）

## 作者

无秋 | X: @mackeybht | 2026

---

**交易有风险，入市需谨慎。**
