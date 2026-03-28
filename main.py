import pandas as pd
from pykrx import stock
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import warnings
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

# 불필요한 경고 메시지 숨기기
warnings.filterwarnings('ignore')

# 1. FastAPI 앱 생성 (이것이 웹 서버의 심장입니다!)
app = FastAPI()

def get_naver_theme(ticker):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={ticker}"
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(response.text, 'html.parser')
        theme = soup.select_one('#content > div.section.trade_compare > h4 > em > a')
        if theme:
            return theme.text.strip()
        return "개별주"
    except:
        return "N/A"

def get_master_betting_candidates():
    target_date = None
    
    # 최근 10일 중 장이 열렸던 마지막 날짜 찾기
    for i in range(10): 
        check_date = (datetime.today() - timedelta(days=i)).strftime("%Y%m%d")
        tickers = stock.get_market_ticker_list(check_date, market="KOSPI")
        if len(tickers) > 0: 
            target_date = check_date
            break
            
    if target_date is None:
        return "<p>최근 영업일 데이터를 찾을 수 없습니다.</p>"
        
    try:
        # 데이터 긁어오기
        df_kospi = stock.get_market_ohlcv(target_date, market="KOSPI")
        df_kosdaq = stock.get_market_ohlcv(target_date, market="KOSDAQ")
        
        if df_kospi.empty or '고가' not in df_kospi.columns:
            raise KeyError("서버 점검")
            
        df = pd.concat([df_kospi, df_kosdaq]).reset_index()
        
        if '티커' not in df.columns:
            df.rename(columns={'index': '티커'}, inplace=True)
            
        df['종목명'] = df['티커'].apply(lambda x: stock.get_market_ticker_name(x))
        df['거래대금(억)'] = (df['거래대금'] / 100000000).astype(int)
        
        noise_keywords = 'KODEX|TIGER|KBSTAR|스팩|인버스|레버리지|우B|우$|선물|H|ETN'
        df_clean = df[~df['종목명'].str.contains(noise_keywords, regex=True, na=False)].copy()
        
        df_top50 = df_clean.sort_values(by='거래대금(억)', ascending=False).head(50).copy()
        
        valid_mask = (df_top50['고가'] - df_top50['저가']) > 0
        df_top50.loc[valid_mask, '방어력점수'] = (
            (df_top50['종가'] - df_top50['저가']) / (df_top50['고가'] - df_top50['저가']) * 100
        ).astype(int)
        
        df_final = df_top50[df_top50['방어력점수'] >= 80].copy()
        df_final['테마'] = df_final['티커'].apply(get_naver_theme)
        
        # 보기 좋게 정렬
        result = df_final[['종목명', '테마', '방어력점수', '등락률', '거래대금(억)']].sort_values(by='거래대금(억)', ascending=False)
        
        # [웹사이트 전용 마법] 까만 텍스트 대신, 깔끔한 HTML 표(Table) 형태로 변환합니다!
        html_table = result.to_html(index=False, justify='center', border=1, classes='styled-table')
        return f"<h3>🎯 [{target_date}] 타깃 사냥 완료</h3>" + html_table
        
    except KeyError:
        return ("<h3>🌙 [시스템 안내] 거래소 데이터 서버 접속 실패</h3>"
                "<p>한국거래소(KRX) 야간 DB 점검 시간(밤 11시~12시)입니다.<br>"
                "내일 아침이나 낮에 접속하시면 완벽하게 작동합니다!</p>")
    except Exception as e:
        return f"<p>기타 에러 발생: {e}</p>"

# 2. 인터넷 주소로 접속했을 때 보여줄 화면 설정
@app.get("/", response_class=HTMLResponse)
def read_root():
    # 파이썬 결과를 가져와서 예쁜 웹페이지 틀(HTML/CSS) 안에 집어넣습니다.
    quant_data = get_master_betting_candidates()
    
    html_content = f"""
    <html>
        <head>
            <title>뉴하트 종가베팅 레이더</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: 'Malgun Gothic', sans-serif; padding: 20px; background-color: #f4f7f6; }}
                h2 {{ color: #2c3e50; }}
                .container {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
                .styled-table {{ border-collapse: collapse; margin: 25px 0; font-size: 0.9em; width: 100%; }}
                .styled-table thead tr {{ background-color: #009879; color: #ffffff; text-align: left; }}
                .styled-table th, .styled-table td {{ padding: 12px 15px; border-bottom: 1px solid #dddddd; text-align: center; }}
                .styled-table tbody tr:nth-of-type(even) {{ background-color: #f3f3f3; }}
                .styled-table tbody tr:last-of-type {{ border-bottom: 2px solid #009879; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>🔥 뉴하트&대가스타일 종가베팅 사냥 로봇 🔥</h2>
                <hr>
                {quant_data}
            </div>
        </body>
    </html>
    """
    return html_content

