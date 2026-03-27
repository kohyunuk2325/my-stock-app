import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse # 💡 화면(HTML)을 보여주기 위한 도구 추가!
import FinanceDataReader as fdr
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

cache = {
    "market": None,
    "themes": None,
    "last_updated": 0
}
CACHE_TTL = 60 

def fetch_realtime_data():
    current_time = time.time()
    if cache["themes"] is not None and (current_time - cache["last_updated"]) < CACHE_TTL:
        return  

    print(f"⏳ [{datetime.now().strftime('%H:%M:%S')}] 실시간 데이터 수집 중...")
    
    try:
        kospi_df = fdr.DataReader('KS11').tail(2)
        kosdaq_df = fdr.DataReader('KQ11').tail(2)
        
        k_curr, k_prev = kospi_df.iloc[-1]['Close'], kospi_df.iloc[-2]['Close']
        kq_curr, kq_prev = kosdaq_df.iloc[-1]['Close'], kosdaq_df.iloc[-2]['Close']

        cache["market"] = {
            "kospi": {"value": round(k_curr, 2), "change": round(k_curr - k_prev, 2)},
            "kosdaq": {"value": round(kq_curr, 2), "change": round(kq_curr - kq_prev, 2)},
            "status": "상승장" if k_curr > k_prev else "하락장"
        }
    except Exception as e:
        print(f"지수 수집 오류: {e}")

    krx_df = fdr.StockListing('KRX')
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    url = "https://finance.naver.com/sise/theme.naver"
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    themes_data = []
    theme_rows = soup.select('table.type_1.theme tr')
    
    for idx, row in enumerate(theme_rows):
        cols = row.select('td')
        if len(cols) < 2: continue
        
        a_tag = cols[0].select_one('a')
        if not a_tag: continue 
            
        theme_name = a_tag.text.strip()
        theme_link = "https://finance.naver.com" + a_tag['href']
        
        detail_res = requests.get(theme_link, headers=headers)
        detail_soup = BeautifulSoup(detail_res.text, 'html.parser')
        
        stock_names = [s.text.strip() for s in detail_soup.select('.type_5 .name a')]
        theme_stocks_df = krx_df[krx_df['Name'].isin(stock_names)].copy()
        
        if theme_stocks_df.empty: continue
            
        change_col = 'ChangesRatio' if 'ChangesRatio' in theme_stocks_df.columns else 'ChagesRatio'
        
        stocks_list = []
        theme_total_volume = 0
        theme_total_change = 0
        
        for _, stock in theme_stocks_df.iterrows():
            price = int(stock['Close'])
            change_percent = float(stock[change_col])
            volume = int(stock['Amount']) if 'Amount' in stock.index else int(stock['Volume'] * price)
            
            theme_total_volume += (volume // 100000000) # 억 단위로 변환
            theme_total_change += change_percent
            
            stocks_list.append({
                "name": str(stock['Name']),
                "changePercent": round(change_percent, 2),
                "volume": (volume // 100000000)
            })
            
        stocks_list.sort(key=lambda x: x['volume'], reverse=True)
        leading_stocks = [s['name'] for s in stocks_list[:2]] # 1, 2등 대장주
                
        themes_data.append({
            "name": theme_name,
            "volume": theme_total_volume,
            "changePercent": round(theme_total_change / len(stocks_list), 2) if stocks_list else 0,
            "leadingStocks": leading_stocks
        })
        
        if len(themes_data) >= 15: break
        
    themes_data.sort(key=lambda x: x['volume'], reverse=True)
    cache["themes"] = themes_data
    cache["last_updated"] = current_time
    print("✅ 데이터 수집 완료!")


# ==========================================
# 🎨 [프론트엔드] 웹사이트 화면을 그려주는 마법의 HTML 코드!
# ==========================================
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>나만의 퀀트 대시보드</title>
    <style>
        /* CSS: 예쁜 페인트칠하기 */
        body { font-family: 'Malgun Gothic', sans-serif; background-color: #121212; color: #ffffff; padding: 20px; margin: 0; }
        h1 { text-align: center; color: #00e5ff; font-size: 1.8em; margin-bottom: 20px;}
        .theme-card { background-color: #1e1e1e; border-radius: 12px; padding: 18px; margin-bottom: 15px; box-shadow: 0 4px 8px rgba(0,0,0,0.5); border-left: 5px solid #00e5ff; }
        .theme-title { font-size: 1.3em; font-weight: bold; color: #ffeb3b; margin-bottom: 8px; }
        .theme-volume { color: #aaaaaa; font-size: 0.95em; margin-bottom: 12px; }
        .leader-box { background-color: #2c2c2c; padding: 12px; border-radius: 8px; }
        .leader-box span { color: #ff5252; font-weight: bold; }
        .red { color: #ff5252; font-weight: bold; }
        .blue { color: #448aff; font-weight: bold; }
        #loading { text-align: center; color: #aaaaaa; font-size: 1.2em; margin-top: 50px; }
    </style>
</head>
<body>

    <h1>🚀 실시간 주식 테마 대시보드</h1>
    
    <div id="dashboard">
        <div id="loading">⏳ 실시간 데이터를 불러오는 중입니다...<br>(약 10초 정도 걸릴 수 있어요!)</div>
    </div>

    <script>
        /* JavaScript: 로봇이 서버(API)에서 데이터를 가져와서 화면에 붙여넣는 엘리베이터 역할 */
        async function loadData() {
            try {
                // 우리 파이썬 서버의 API 주소로 데이터를 요청합니다!
                const response = await fetch('/api/themes');
                const data = await response.json();

                if (data.error) {
                    document.getElementById('dashboard').innerHTML = '<h3 style="color:red; text-align:center;">❌ ' + data.error + '</h3>';
                    return;
                }

                let html = '';
                // 가져온 테마 갯수만큼 카드를 만듭니다.
                data.forEach(theme => {
                    let colorClass = theme.changePercent > 0 ? 'red' : 'blue';
                    let sign = theme.changePercent > 0 ? '+' : '';
                    
                    html += `
                        <div class="theme-card">
                            <div class="theme-title">📂 ${theme.name} 테마</div>
                            <div class="theme-volume">💰 테마 총 거래대금: ${theme.volume.toLocaleString()}억 원</div>
                            <div class="leader-box">
                                👑 <b>대장주:</b> <span>${theme.leadingStocks.join(', ')}</span> <br><br>
                                📈 <b>테마 평균 등락률:</b> <span class="${colorClass}">${sign}${theme.changePercent}%</span>
                            </div>
                        </div>
                    `;
                });
                
                // 완성된 카드들을 화면에 짜잔! 하고 보여줍니다.
                document.getElementById('dashboard').innerHTML = html;
            } catch (error) {
                document.getElementById('dashboard').innerHTML = '<h3 style="color:red; text-align:center;">❌ 서버와 연결이 끊어졌습니다. 파이썬 앱이 켜져 있는지 확인하세요.</h3>';
            }
        }
        
        // 웹페이지가 켜지자마자 데이터를 가져옵니다.
        loadData();
    </script>

</body>
</html>
"""

# 💡 기본 주소('/')로 들어오면 예쁜 HTML 화면을 보여줍니다!
@app.get("/", response_class=HTMLResponse)
def read_root():
    return HTML_CONTENT

# 원래 있던 API 주소들 (데이터만 주는 창고 역할)
@app.get("/api/market")
def get_market():
    fetch_realtime_data()
    return cache.get("market", {"error": "데이터를 불러오는 중입니다."})

@app.get("/api/themes")
def get_themes_list():
    fetch_realtime_data()
    if not cache["themes"]: return {"error": "데이터가 없습니다."}
    return cache["themes"]

if __name__ == "__main__":
    print("🚀 주식 대시보드 백엔드 서버를 시작합니다...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
