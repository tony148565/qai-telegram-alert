#!/usr/bin/env python3
"""
秋AI-灵枢 | QAI-Synapse 专业 Telegram 警报机器人
Version: 2.0 (Schema v2.0 专业级)
Author: 无秋 (X: @mackeybht)
License: Personal Use Only

功能特性：
- 完整支持 Pine Script v2.0 Schema (entry / sl_hit / partial_exit / trade_closed / daily_summary 等)
- 签名验证（与 Pine 简单签名机制一致）
- 富文本 HTML 消息 + 表情符号
- SQLite 持久化警报历史 + Web 仪表盘
- 多 Chat ID 支持
- 生产级日志 + 错误重试
- 环境变量配置
"""

import os
import json
import logging
import sqlite3
import hashlib
from datetime import datetime
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv
import requests
import pytz

# ==================== 配置加载 ====================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_IDS = [int(x.strip()) for x in os.getenv("CHAT_IDS", "").split(",") if x.strip()]
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
PORT = int(os.getenv("PORT", 8080))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
TZ = pytz.timezone(os.getenv("TZ", "Asia/Hong_Kong"))
MAX_HISTORY = int(os.getenv("MAX_ALERT_HISTORY", 100))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

if not BOT_TOKEN or not CHAT_IDS:
    raise ValueError("❌ BOT_TOKEN 和 CHAT_IDS 必须在 .env 中配置！")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ==================== 日志配置 ====================
os.makedirs("logs", exist_ok=True)
logger = logging.getLogger("QAI-Telegram-Bot")
logger.setLevel(getattr(logging, LOG_LEVEL))

# 控制台
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
))
logger.addHandler(console_handler)

# 文件（轮转）
file_handler = RotatingFileHandler(
    "logs/qai_bot.log", maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)s | %(funcName)s | %(message)s"
))
logger.addHandler(file_handler)

# ==================== Flask App ====================
app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

# ==================== SQLite 数据库 ====================
DB_PATH = "qai_alerts.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event TEXT NOT NULL,
            ticker TEXT,
            tf TEXT,
            message TEXT,
            tqi REAL,
            signal_id TEXT,
            raw_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    logger.info("✅ SQLite 数据库初始化完成")

init_db()

def save_alert(event: str, ticker: str, tf: str, message: str, tqi: float = None, signal_id: str = None, raw_json: str = None):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO alerts (timestamp, event, ticker, tf, message, tqi, signal_id, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"),
            event, ticker, tf, message, tqi, signal_id, raw_json
        ))
        conn.commit()
        # 清理旧记录
        c.execute("DELETE FROM alerts WHERE id NOT IN (SELECT id FROM alerts ORDER BY id DESC LIMIT ?)", (MAX_HISTORY,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"保存警报失败: {e}")

def get_recent_alerts(limit: int = 20):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT timestamp, event, ticker, tf, tqi, message FROM alerts ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

# ==================== Telegram 发送函数 ====================
def send_telegram_message(chat_id: int, text: str, parse_mode: str = "HTML", disable_web_page_preview: bool = True) -> bool:
    """发送消息到 Telegram，支持重试"""
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview
    }
    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                return True
            else:
                logger.warning(f"Telegram 发送失败 (尝试 {attempt+1}/3): {resp.text}")
        except Exception as e:
            logger.error(f"Telegram 请求异常 (尝试 {attempt+1}/3): {e}")
    return False

def broadcast_message(text: str, parse_mode: str = "HTML"):
    """广播到所有配置的 Chat ID"""
    success = 0
    for chat_id in CHAT_IDS:
        if send_telegram_message(chat_id, text, parse_mode):
            success += 1
    logger.info(f"📢 广播完成: {success}/{len(CHAT_IDS)} 个聊天成功")
    return success > 0

# ==================== 签名验证（与 Pine Script 保持一致） ====================
def verify_signature(payload: dict, provided_sig: str) -> bool:
    if not WEBHOOK_SECRET:
        return True  # 未设置密钥则跳过验证（生产环境强烈建议设置）
    
    try:
        event = payload.get("event", "")
        ts = payload.get("timestamp", "")
        # 模拟 Pine 的简单签名逻辑
        base = f"{ts}|{event}|{int(float(payload.get('price', 0)) * 1000)}"
        expected = str(abs((int(ts) % 1000000007) + len(base) * 31) % 100000000)
        return provided_sig == expected or provided_sig == "no_secret_configured"
    except Exception as e:
        logger.error(f"签名验证异常: {e}")
        return False

# ==================== 消息格式化器 ====================
def format_entry_message(data: dict) -> str:
    action = data.get("action", "buy")
    is_long = action == "buy"
    emoji = "🟢" if is_long else "🔴"
    direction = "多头 LONG" if is_long else "空头 SHORT"
    
    ticker = data.get("ticker", "UNKNOWN")
    tf = data.get("tf", "?")
    price = data.get("price", 0)
    sl = data.get("sl", 0)
    tp1 = data.get("tp1", 0)
    tp2 = data.get("tp2", 0)
    tp3 = data.get("tp3", 0)
    rr = data.get("rr", "1.0")
    pool = data.get("pool_strength", 0)
    tqi = data.get("tqi", 0)
    priority = data.get("priority", "MEDIUM")
    struct_aligned = data.get("structure_aligned", False)
    adx = data.get("adx", 0)
    signal_id = data.get("signal_id", "")
    
    priority_emoji = {"HIGH": "🔥", "MEDIUM": "✅", "LOW": "⚠️"}.get(priority, "✅")
    
    msg = f"""<b>{emoji} {direction} 入场信号 | QAI-Synapse</b>

<b>品种:</b> <code>{ticker}</code> | <b>时间框架:</b> <code>{tf}</code>
<b>入场价:</b> <code>{price}</code>
<b>止损 SL:</b> <code>{sl}</code>
<b>止盈 TP1:</b> <code>{tp1}</code>   <b>TP2:</b> <code>{tp2}</code>   <b>TP3:</b> <code>{tp3}</code>

<b>风险回报比:</b> <code>{rr}R</code>     <b>池子强度:</b> <code>{pool}/100</code>
<b>综合质量 TQI:</b> <code>{tqi}</code> {priority_emoji} <b>{priority}</b>

<b>市场结构:</b> {"🟢 对齐" if struct_aligned else "🔴 逆向"}     <b>ADX:</b> <code>{adx}</code>
<b>Signal ID:</b> <code>{signal_id}</code>

<i>流动性扫取 + 实体反转 | 高概率反转信号</i>
<i>Generated by 秋AI-灵枢 v1.3 | {datetime.now(TZ).strftime("%H:%M:%S")}</i>"""
    return msg

def format_sl_hit_message(data: dict) -> str:
    be_active = data.get("be_active", "false") == "true"
    emoji = "🛡️" if be_active else "🛑"
    title = "保本止损 (Break-Even)" if be_active else "止损命中 (SL Hit)"
    
    return f"""<b>{emoji} {title}</b>

<b>品种:</b> <code>{data.get('ticker')}</code>
<b>当前价:</b> <code>{data.get('price')}</code> | <b>SL:</b> <code>{data.get('sl')}</code>
<b>入场价:</b> <code>{data.get('entry')}</code>
<b>TQI:</b> <code>{data.get('tqi', 0)}</code>

<i>Signal ID: {data.get('signal_id', '—')}</i>
<i>{datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")}</i>"""

def format_partial_exit_message(data: dict) -> str:
    level = data.get("level", 1)
    percent = data.get("percent", 0)
    remaining = data.get("remaining", 0)
    emoji = "🎯" if level < 3 else "🏆"
    title = f"狙击手部分平仓 TP{level}" if level < 3 else "狙击手最终平仓 TP3"
    
    return f"""<b>{emoji} {title}</b>

<b>品种:</b> <code>{data.get('ticker')}</code> | <b>当前价:</b> <code>{data.get('price')}</code>
<b>平仓比例:</b> <code>{percent}%</code>     <b>剩余仓位:</b> <code>{remaining}%</code>
<b>TQI:</b> <code>{data.get('tqi', 0)}</code>

<i>Signal ID: {data.get('signal_id', '—')}</i>"""

def format_trade_closed_message(data: dict) -> str:
    is_win = data.get("is_win", "false") == "true"
    emoji = "✅" if is_win else "❌"
    realized = data.get("realized_r", "详见仪表盘")
    
    return f"""<b>{emoji} 交易关闭总结</b>

<b>品种:</b> <code>{data.get('ticker')}</code> | <b>入场→平仓:</b> <code>{data.get('entry')} → {data.get('close_price')}</code>
<b>已实现 R:</b> <code>{realized}</code>     <b>盈亏%:</b> <code>{data.get('pnl_pct', 0)}%</code>
<b>TQI:</b> <code>{data.get('tqi', 0)}</code>

<i>Signal ID: {data.get('signal_id', '—')}</i>
<i>{datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")}</i>"""

def format_daily_summary(data: dict) -> str:
    win_rate = data.get("win_rate", 0)
    return f"""<b>📅 每日战绩总结 | {data.get('date')}</b>

<b>品种:</b> <code>{data.get('ticker')}</code> | <b>时间框架:</b> <code>{data.get('tf')}</code>
<b>交易次数:</b> <code>{data.get('trades')}</code>     <b>胜负:</b> <code>{data.get('wins')}胜 / {data.get('trades',0)-data.get('wins',0)}负</code>
<b>胜率:</b> <code>{win_rate}%</code>     <b>今日已实现R:</b> <code>{data.get('realized_r', 0)}R</code>

<i>Generated by 秋AI-灵枢 | 每天早上 8:00 (HKT) 自动推送</i>"""

def format_generic_event(data: dict) -> str:
    event = data.get("event", "unknown")
    emoji_map = {
        "test_alert": "✅",
        "drawdown_alert": "⚠️",
        "kill_switch": "🛑",
        "trailing_sl_move": "📉"
    }
    emoji = emoji_map.get(event, "📡")
    
    return f"""<b>{emoji} {event.upper()} 事件</b>

<b>品种:</b> <code>{data.get('ticker')}</code>
<b>价格:</b> <code>{data.get('price', '—')}</code>
<b>TQI:</b> <code>{data.get('tqi', '—')}</code>

<pre>{json.dumps(data, indent=2, ensure_ascii=False)[:800]}</pre>

<i>{datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")}</i>"""

# ==================== Webhook 主处理 ====================
@app.route("/webhook", methods=["POST"])
def webhook():
    if request.method != "POST":
        return jsonify({"error": "Method not allowed"}), 405
    
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            logger.warning("收到空 JSON")
            return jsonify({"status": "error", "msg": "Empty payload"}), 400
        
        # 签名验证
        provided_sig = data.get("signature", "")
        if not verify_signature(data, provided_sig):
            logger.warning(f"签名验证失败: {provided_sig}")
            return jsonify({"status": "error", "msg": "Invalid signature"}), 403
        
        event = data.get("event", "unknown")
        schema = data.get("schema_version", "1.0")
        ticker = data.get("ticker", "N/A")
        tf = data.get("tf", "N/A")
        tqi = data.get("tqi", 0)
        signal_id = data.get("signal_id", "")
        
        logger.info(f"📥 收到事件: {event} | {ticker} | TQI:{tqi}")
        
        # 根据事件类型格式化消息
        if event == "entry":
            text = format_entry_message(data)
        elif event == "sl_hit":
            text = format_sl_hit_message(data)
        elif event == "partial_exit":
            text = format_partial_exit_message(data)
        elif event == "trade_closed":
            text = format_trade_closed_message(data)
        elif event == "daily_summary":
            text = format_daily_summary(data)
        else:
            text = format_generic_event(data)
        
        # 广播到所有 Chat
        broadcast_message(text)
        
        # 保存到数据库
        save_alert(event, ticker, tf, text, tqi, signal_id, json.dumps(data, ensure_ascii=False))
        
        return jsonify({"status": "success", "event": event, "processed": True}), 200
        
    except Exception as e:
        logger.exception(f"Webhook 处理异常: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 500

# ==================== 健康检查 ====================
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "version": "2.0",
        "bot_configured": bool(BOT_TOKEN),
        "chats": len(CHAT_IDS),
        "timestamp": datetime.now(TZ).isoformat()
    })

# ==================== Web 仪表盘 ====================
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>秋AI-灵枢 | 警报仪表盘</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #60a5fa; text-align: center; }
        table { width: 100%; border-collapse: collapse; background: #1e2937; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1); }
        th, td { padding: 14px 18px; text-align: left; border-bottom: 1px solid #334155; }
        th { background: #334155; color: #94a3b8; font-weight: 600; }
        tr:hover { background: #334155; }
        .event { font-weight: 700; padding: 4px 10px; border-radius: 9999px; font-size: 0.85rem; }
        .event.entry { background: #166534; color: #4ade80; }
        .event.sl_hit { background: #7f1d1d; color: #f87171; }
        .event.partial { background: #1e40af; color: #60a5fa; }
        .event.trade_closed { background: #713f12; color: #fbbf24; }
        .event.daily { background: #312e81; color: #a5b4fc; }
        .tqi { font-family: monospace; font-weight: 700; }
        .footer { text-align: center; margin-top: 30px; color: #64748b; font-size: 0.9rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧠 秋AI-灵枢 Telegram 警报仪表盘</h1>
        <p style="text-align:center; color:#94a3b8;">实时接收 TradingView Webhook | Schema v2.0 | 最后更新: {{ now }}</p>
        
        <table>
            <thead>
                <tr>
                    <th>时间</th>
                    <th>事件</th>
                    <th>品种 / TF</th>
                    <th>TQI</th>
                    <th>消息预览</th>
                </tr>
            </thead>
            <tbody>
                {% for row in alerts %}
                <tr>
                    <td>{{ row[0] }}</td>
                    <td><span class="event {{ row[1] }}">{{ row[1] }}</span></td>
                    <td><code>{{ row[2] }}</code> / <code>{{ row[3] }}</code></td>
                    <td class="tqi">{{ row[4] if row[4] else '—' }}</td>
                    <td style="max-width: 520px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{{ row[5][:120] }}...</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <div class="footer">
            Powered by 秋AI-灵枢 v1.3 • Flask + python-telegram-bot • 
            <a href="/health" style="color:#60a5fa;">健康检查</a> • 
            共保留最近 {{ max_history }} 条记录
        </div>
    </div>
</body>
</html>
"""

@app.route("/dashboard", methods=["GET"])
def dashboard():
    alerts = get_recent_alerts(25)
    return render_template_string(
        DASHBOARD_HTML,
        alerts=alerts,
        now=datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"),
        max_history=MAX_HISTORY
    )

# ==================== 启动 ====================
if __name__ == "__main__":
    logger.info("🚀 秋AI-灵枢 Telegram Bot 启动中...")
    logger.info(f"监听端口: {PORT} | Chat 数量: {len(CHAT_IDS)} | 调试模式: {DEBUG}")
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG)