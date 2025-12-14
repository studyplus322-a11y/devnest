# -*- coding: utf-8 -*-
from flask import Flask, jsonify
from threading import Thread
import datetime
import os

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>🚀 بوت مجتمع المبرمجين</title>
        <style>
            body {
                font-family: 'Arial', sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-align: center;
                padding: 50px;
            }
            .container {
                background: rgba(255,255,255,0.1);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 40px;
                max-width: 800px;
                margin: 0 auto;
            }
            h1 {
                font-size: 3em;
                margin-bottom: 20px;
            }
            .status {
                font-size: 1.5em;
                color: #4CAF50;
                margin: 20px 0;
            }
            .features {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-top: 30px;
            }
            .feature {
                background: rgba(255,255,255,0.2);
                padding: 20px;
                border-radius: 10px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 بوت مجتمع المبرمجين</h1>
            <div class="status">✅ البوت يعمل بشكل طبيعي</div>
            <p>تم التحديث: """ + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
            
            <div class="features">
                <div class="feature">🎮 نظام الألعاب</div>
                <div class="feature">🛡️ نظام الإدارة</div>
                <div class="feature">📊 نظام المستويات</div>
                <div class="feature">🎫 نظام التذاكر</div>
                <div class="feature">📜 نظام السجل</div>
                <div class="feature">⚙️ نظام الإعدادات</div>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/status')
def status():
    return jsonify({
        "status": "online",
        "timestamp": datetime.datetime.now().isoformat(),
        "service": "Discord Bot - Programmer Community",
        "version": "2.0.0"
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    server = Thread(target=run)
    server.daemon = True
    server.start()