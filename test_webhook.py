#!/usr/bin/env python3
"""
QAI-灵枢 V1.3 Webhook 测试脚本
用法: python test_webhook.py https://你的域名/webhook
"""

import requests
import json
import sys
from datetime import datetime

def test_webhook(base_url):
    url = base_url.rstrip('/') + '/webhook'
    
    test_payloads = [
        {
            "schema_version": "2.0",
            "event": "test_alert",
            "ticker": "BTCUSDT.P",
            "tf": "15",
            "price": "67234.5",
            "tqi": 78,
            "signature": "test_signature"
        },
        {
            "schema_version": "2.0",
            "event": "entry",
            "action": "buy",
            "ticker": "BTCUSDT.P",
            "tf": "15",
            "price": "67250.0",
            "original_entry": "67250.0",
            "sl": "66890.0",
            "tp1": "67480.0",
            "tp2": "67850.0",
            "tp3": "68200.0",
            "rr": "1.2",
            "pool_strength": 72,
            "tqi": 81,
            "structure_aligned": "true",
            "adx": 48,
            "signal_id": "BTCUSDT.P-15-28471-6723450",
            "timestamp": str(int(datetime.now().timestamp() * 1000))
        },
        {
            "schema_version": "2.0",
            "event": "partial_exit",
            "action": "tp1",
            "level": 1,
            "ticker": "BTCUSDT.P",
            "tf": "15",
            "price": "67480.0",
            "percent": 50,
            "remaining": 50,
            "tqi": 81,
            "signal_id": "BTCUSDT.P-15-28471-6723450"
        }
    ]
    
    print(f"🚀 开始测试 Webhook: {url}\n")
    
    for i, payload in enumerate(test_payloads, 1):
        print(f"[{i}] 测试事件: {payload['event']}")
        try:
            resp = requests.post(url, json=payload, timeout=15)
            print(f"    状态码: {resp.status_code}")
            print(f"    响应: {resp.text[:200]}")
        except Exception as e:
            print(f"    ❌ 失败: {e}")
        print()
    
    print("✅ 测试完成！请检查 Telegram 是否收到消息。")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python test_webhook.py https://qai-telegram-alert.onrender.com")
        sys.exit(1)
    test_webhook(sys.argv[1])
