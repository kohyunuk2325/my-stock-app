from flask import Flask, render_template_string
import pandas as pd
import requests
import json
import time
from datetime import datetime
from bs4 import BeautifulSoup

app = Flask(__name__)

# ---------------------------------------------------------
# 🎨 1. 웹 화면 디자인 (황제주 전용 구역 추가)
# ---------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>NYU-HART MASTER SNIPER</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <style>
        body { background-color: #0d0d0d; color: #e0e0e0; font-family: 'Malgun Gothic', sans-serif; }
        
        /* 황제 섹션 디자인 */
        .king-section { 
            background: linear-gradient(135deg, #ffd700, #b8860b); 
            padding: 20px; border-radius: 20px; margin-bottom: 30px; 
            color: #000; box-shadow: 0 10px 30px rgba(255, 215, 0, 0.3);
            border: 2px solid #fff;
        }
        .king-badge { background: #000; color: #ffd700; padding: 5px 15px; border-radius: 50px; font-weight: bold; font-size: 0.8rem; }
        
        /* 일반 테마 디자인 */
        .theme-container { margin-bottom: 25px; border: 1px solid #333; border-radius: 15px; overflow: hidden; background: #1a1a1a; }
        .theme-header { background: #252525; padding: 12px 20px; font-weight: bold; border-bottom: 2px solid #ff4b4b; }
        .stock-card { padding: 12px 20px; border-bottom: 1px solid #2a2a2a; }
        .up-rank { color: #ff4b4b; font-weight: bold; font-size: 1.1rem; }
        .news-box { font-size: 0.85rem; color: #aaa; margin-top: 5px; background: #222; padding: 8px; border-radius: 5px; border-left: 3px solid #ff4b4b; }
        .badge-money { background-color: #444; color: #ffc107; font-size: 0.75rem; padding: 4px 8px; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container mt-4">
        <div class="text-center mb-4">
            <h2 class="text-danger">🔥 뉴하트 실시간 주도주 레이더</h2>
            <small class="text-muted">Master's Choice: Money & Strength | {{ now }}</small>
        </div>

        {% if leader_info %}
        <div class="king-section shadow-lg">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="king-badge">PREMIUM CHOICE</span>
                <span class="fw-bold">오늘의 주도 테마: {{ leader_info.theme }}</span>
            </div>
            <h1 class="display-5 fw-bold mb-1">👑 {{ leader_info.name }}</h1>
            <div class="d-flex justify-content-between align-items-end">
                <div>
                    <p class="mb-0">거래대금: <b>{{ leader_info.money }}억</b> | 현재가: {{ leader_info.price }}원</p>
                    <p class="small mb-0 mt-1">📰 {{ leader_info.news }}</p>
                </div>
                <div class="text-end">
                    <span class="display-6 fw-bold">+{{ leader_info.change }}%</span>
                </div>
            </div>
        </div>
        {% endif %}

        <hr style="border-color: #444; margin: 40px 0;">

        {% for theme, stocks in grouped_data.items() %}
        <div class="theme-container shadow">
            <div class="theme-header d-flex justify-content-between align-items-center">
                <span>📂 {{ theme }}</span>
                <span class="badge-money">테마 합산 {{ stocks|sum(attribute='money') }}억</span>
            </div>
            {% for s in stocks %}
            <div class="stock-card">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <span class="fw-bold">{{ s.name }}</span>
                        <small class="ms-2 text-muted">{{ s.price }}원</small>
                    </div>
                    <span class="up-rank">+{{ s.change }}%</span>
                </div>
                <div class="news-box">
                    📰 {{ s.news }} <span class="ms-1 text-warning">({{ s.money }}억)</span>
                </div>
            </div>
            {% endfor %}
        </div>
        {% endfor %}
    </div>
</body>
</html>
"""

# 🚨 [보안] 선생님의 앱키와 시크릿을 넣어주세요!
APP_KEY = "PSzH80xjOtplsJnSd7ObTOUhFDBqYYsxreET"
APP_SECRET = "Mv+5wP2b3XdyOBoI65ew3V0xnBdCWa9N0UYEC0/rR8WsPF36KzZPws2qKigbgcYqkutLhwY/hPoMPVS9amq/DE5BA2kAzaBaPwJVX2muBWO6EFFYa9RvAK7bVbrgsl79l5+++bwWo9aQ3ApNGzHXSj7aXpVzK4abyNCGk7aGffEmy1V5GqE="
URL_BASE = "https://openapi.koreainvestment.com:9443"

def get_theme_news(name, ticker):
    try:
        theme, news = "개별주", "이슈 분석 중..."
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(f"https://finance.naver.com/item/main.naver?code={ticker}", headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        t_tag = soup.select_one('#content > div.section.trade_compare > h4 > em > a')
        if t_tag: theme = t_tag.text.strip()
        s_res = requests.get(f"https://search.naver.com/search.naver?where=news&query={name}&sort=1", headers=headers)
        s_soup = BeautifulSoup(s_res.text, 'html.parser')
        n_tags = s_soup.select('.news_tit')
        if n_tags: news = n_tags[0].text.strip()
        return theme, news
    except:
        return "개별주", "최신 뉴스 없음"

def get_processed_data():
    try:
        auth_res = requests.post(f"{URL_BASE}/oauth2/tokenP", data=json.dumps({"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}))
        token = auth_res.json().get('access_token')
        
        headers = {"authorization": f"Bearer {token}", "appkey": APP_KEY, "appsecret": APP_SECRET, "tr_id": "FHPST01710000"}
        params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "20171", "FID_INPUT_ISCD": "0000", "FID_DIV_CLS_CODE": "0", "FID_BLNG_CLS_CODE": "0", "FID_TRGT_CLS_CODE": "111111111", "FID_TRGT_EXLS_CLS_CODE": "0000000000"}
        res = requests.get(f"{URL_BASE}/uapi/domestic-stock/v1/quotations/volume-rank", headers=headers, params=params)
        
        items = res.json().get('output', [])
        raw_stocks = []
        count = 0
        for i in items:
            name = i['hts_kor_isnm']
            if any(x in name for x in ['KODEX', 'TIGER', '스팩', '인버스', '레버리지', 'ETN', 'KBSTAR', 'SOL', 'ACE']): continue
            raw_stocks.append({'name': name, 'ticker': i['mksc_shrn_iscd'], 'price': i['stck_prpr'], 'change': float(i['prdy_ctrt']), 'money': int(i['acml_tr_pbmn']) // 100000000})
            count += 1
            if count >= 20: break # 속도를 위해 20개로 조정
            
        for s in raw_stocks:
            theme, news = get_theme_news(s['name'], s['ticker'])
            s['theme'], s['news'] = theme, news
            time.sleep(0.05)

        df = pd.DataFrame(raw_stocks)
        
        # 1. 주도 테마 선정 (테마별 거래대금 합계 1위)
        theme_money = df.groupby('theme')['money'].sum().sort_values(ascending=False)
        leading_theme_name = theme_money.index[0]
        
        # 2. 황제주 선정 (주도 테마 내 등락률 1위)
        leading_theme_stocks = df[df['theme'] == leading_theme_name].sort_values('change', ascending=False)
        leader_info = leading_theme_stocks.iloc[0].to_dict()
        
        # 3. 나머지 데이터 그룹화
        grouped = df.sort_values(['theme', 'change'], ascending=[True, False])
        final_grouped = {}
        for t_name, group in grouped.groupby('theme', sort=False):
            final_grouped[t_name] = group.to_dict('records')
            
        return final_grouped, leader_info
    except:
        return {}, None

@app.route('/')
def index():
    grouped_data, leader_info = get_processed_data()
    return render_template_string(HTML_TEMPLATE, grouped_data=grouped_data, leader_info=leader_info, now=datetime.now().strftime('%H:%M:%S'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
