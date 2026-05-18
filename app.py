import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from telegram import Bot
from telegram.error import TelegramError
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== 配置 ====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # 支持多个，用逗号分隔
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

bot = Bot(token=TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

def send_telegram_message(text: str, parse_mode: str = "HTML"):
    """发送 Telegram 消息（支持多 Chat ID）"""
    if not bot or not TELEGRAM_CHAT_ID:
        logger.error("Telegram 配置缺失")
        return False
    
    chat_ids = [cid.strip() for cid in TELEGRAM_CHAT_ID.split(",") if cid.strip()]
    success = True
    
    for chat_id in chat_ids:
        try:
            bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=True
            )
            logger.info(f"消息已发送到 {chat_id}")
        except TelegramError as e:
            logger.error(f"发送失败到 {chat_id}: {e}")
            success = False
    return success

def format_entry_message(data: dict) -> str:
    """格式化入场信号"""
    action = "🟢 LONG | 多头入场" if data.get("action") == "buy" else "🔴 SHORT | 空头入场"
    price = data.get("price", "—")
    sl = data.get("sl", "—")
    tp1 = data.get("tp1", "—")
    tp2 = data.get("tp2", "—")
    tp3 = data.get("tp3", "—")
    rr = data.get("rr", "—")
    tqi = data.get("tqi", "—")
    pool = data.get("pool_strength", "—")
    struct = "🟢 牛市结构" if data.get("structure_aligned") == "true" else "🔴 熊市结构"
    
    msg = f"""<b>{action}</b>
━━━━━━━━━━━━━━━
<b>品种</b>: {data.get('ticker', '—')} | <b>TF</b>: {data.get('tf', '—')}
<b>入场价</b>: {price}
<b>止损 SL</b>: {sl}
<b>TP1 / TP2 / TP3</b>: {tp1} / {tp2} / {tp3}
<b>计划 R:R</b>: {rr}R
<b>池子强度</b>: {pool}/100
<b>TQI 质量分</b>: {tqi}/100
<b>市场结构</b>: {struct}
<b>信号ID</b>: <code>{data.get('signal_id', '—')}</code>
━━━━━━━━━━━━━━━
<i>流动性扫取 + 实体反转 | 高概率反转信号</i>"""
    return msg

def format_exit_message(data: dict, event: str) -> str:
    """格式化出场消息"""
    if event == "partial_exit":
        level = data.get("level", 1)
        emoji = "🎯" if level < 3 else "🏆"
        title = f"狙击手 TP{level} | Sniper Partial TP{level}"
        pct = data.get("percent", 0)
        remaining = data.get("remaining", 0)
        msg = f"""{emoji} <b>{title}</b>
━━━━━━━━━━━━━━━
<b>品种</b>: {data.get('ticker')}
<b>分批比例</b>: {pct}%
<b>剩余仓位</b>: {remaining}%
<b>当前价格</b>: {data.get('price')}
<b>TQI</b>: {data.get('tqi', '—')}/100
<b>信号ID</b>: <code>{data.get('signal_id', '—')}</code>"""
    
    elif event == "sl_hit":
        be = "🛡️ 保本止损" if data.get("be_active") == "true" else "🛑 止损命中"
        msg = f"""{be}
━━━━━━━━━━━━━━━
<b>品种</b>: {data.get('ticker')}
<b>入场价</b>: {data.get('entry')}
<b>止损价</b>: {data.get('sl')}
<b>当前价</b>: {data.get('price')}
<b>TQI</b>: {data.get('tqi', '—')}/100"""
    
    elif event == "trade_closed":
        is_win = "✅ 胜单" if data.get("is_win") == "true" else "❌ 负单"
        msg = f"""🏁 <b>交易关闭总结</b>
━━━━━━━━━━━━━━━
<b>品种</b>: {data.get('ticker')}
<b>入场 → 平仓</b>: {data.get('entry')} → {data.get('close_price')}
<b>已实现 R</b>: {data.get('realized_r', '详见仪表盘')}
<b>结果</b>: {is_win}
<b>盈亏%</b>: {data.get('pnl_pct', '—')}%
<b>TQI</b>: {data.get('tqi', '—')}/100"""
    
    else:
        msg = f"未知出场事件: {event}\n{json.dumps(data, ensure_ascii=False, indent=2)}"
    
    return msg

def format_daily_summary(data: dict) -> str:
    """每日战绩总结"""
    win_rate = data.get("win_rate", 0)
    emoji = "🔥" if win_rate >= 60 else "📊"
    msg = f"""{emoji} <b>每日战绩总结 | Daily Performance</b>
━━━━━━━━━━━━━━━
<b>日期</b>: {data.get('date', '—')}
<b>交易笔数</b>: {data.get('trades', 0)}
<b>胜单 / 负单</b>: {data.get('wins', 0)} / {data.get('trades', 0) - data.get('wins', 0)}
<b>胜率</b>: {win_rate}%
<b>累计实现 R</b>: {data.get('realized_r', 0)}R
━━━━━━━━━━━━━━━
<i>每天早上 8:00 UTC 自动推送</i>"""
    return msg

def format_regime_change(data: dict) -> str:
    """市场结构变化"""
    event_type = data.get("type", "")
    if "bos" in event_type:
        emoji = "🚀"
        title = "BOS | 结构突破确认"
    else:
        emoji = "🔄"
        title = "CHOCH | 性格改变（趋势反转）"
    
    struct = "🟢 牛市结构" if data.get("is_bullish_structure") else "🔴 熊市结构"
    msg = f"""{emoji} <b>{title}</b>
━━━━━━━━━━━━━━━
<b>品种</b>: {data.get('ticker')} | <b>TF</b>: {data.get('tf')}
<b>当前价格</b>: {data.get('price')}
<b>市场结构</b>: {struct}
<b>TQI</b>: {data.get('tqi', '—')}/100
━━━━━━━━━━━━━━━
<i>结构变化信号 | 关注趋势反转机会</i>"""
    return msg

@app.route('/webhook/entry', methods=['POST'])
@app.route('/webhook/exit', methods=['POST'])
@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """统一 Webhook 处理入口"""
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"status": "error", "msg": "无效 JSON"}), 400
        
        # 验证 schema
        if data.get("schema_version") != "2.0":
            logger.warning("非 v2.0 schema，跳过处理")
            return jsonify({"status": "ignored"}), 200
        
        event = data.get("event", "unknown")
        logger.info(f"收到事件: {event} | TQI: {data.get('tqi', '—')}")
        
        # 分发处理
        if event == "entry":
            msg = format_entry_message(data)
        elif event in ["partial_exit", "sl_hit", "break_even", "trade_closed"]:
            msg = format_exit_message(data, event)
        elif event == "daily_summary":
            msg = format_daily_summary(data)
        elif event == "regime_change":
            msg = format_regime_change(data)
        elif event == "drawdown_alert":
            msg = f"⚠️ <b>最大回撤保护警报</b>\n当前 Max DD: {data.get('max_dd')}% (阈值 {data.get('threshold')}%)"
        elif event == "kill_switch":
            msg = f"🛑 <b>KILL SWITCH 紧急保护</b>\nMax DD: {data.get('max_dd')}% | 连败: {data.get('loss_streak')}次\n建议立即评估全平仓！"
        elif event == "test_alert":
            msg = "✅ <b>Webhook 测试成功</b>\n专业级智能 Webhook 系统 v2.0 运行正常！"
        else:
            msg = f"📡 未知事件: {event}\n{json.dumps(data, ensure_ascii=False, indent=2)[:500]}"
        
        # 发送 Telegram
        send_telegram_message(msg)
        
        return jsonify({"status": "success", "event": event}), 200
    
    except Exception as e:
        logger.error(f"处理异常: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "version": "QAI-Synapse V1.3 Webhook Relay", "time": datetime.utcnow().isoformat()})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
