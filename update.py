#!/usr/bin/env python3
"""
update.py — 自動抓取台股收盤價並更新 index.html
"""

import re
import json
import time
import subprocess
from datetime import datetime, timedelta
from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

STOCK_CODES = [
    '2317','2382','3443','6669','2376','2357','6805','2383','3515','2408',
    '6770','2433','3016','6451','3450','2455','2454','3661','2354','3231',
    '6531','2328','3691','3081','3707','4991','3532','8358','6274','6488',
    '6799','4977','4989','2330','3481','6261','2381','3711','2313','2324',
    '2356','8299','5347','6196','3374','3037','2449','3009','2439','2303',
]

INDEX_HTML = '/Users/xiezhikai/Desktop/stock-tracker/index.html'

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'zh-TW,zh;q=0.9',
}


def twse_close(stock_no: str, date_str: str) -> Optional[float]:
    """查詢上市股最新收盤價（TWSE API）"""
    url = (
        f'https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY'
        f'?stockNo={stock_no}&date={date_str}&response=json'
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        if data.get('stat') == 'OK' and data.get('data'):
            last_row = data['data'][-1]
            # 欄位：日期,成交量,成交金額,開盤,最高,最低,收盤,漲跌,筆數
            close_str = last_row[6].replace(',', '')
            return float(close_str)
    except Exception as e:
        print(f'  [TWSE] {stock_no} 錯誤: {e}')
    return None


def cnyes_close(stock_no: str) -> Optional[float]:
    """查詢上櫃股最新收盤價（cnyes 網頁）"""
    url = f'https://www.cnyes.com/twstock/{stock_no}'
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')

        # og:description 格式：「{名稱}({代號}) 即時行情 {價格} {漲跌%}...」
        meta = soup.find('meta', property='og:description')
        if meta:
            content = meta.get('content', '')
            m = re.search(r'即時行情\s+([\d,]+\.?\d*)', content)
            if m:
                return float(m.group(1).replace(',', ''))

        # 備用：class 含 "price" 的元素，取第一個純數字
        for el in soup.select('[class*="price"]'):
            txt = el.get_text(strip=True).split('-')[0].split('+')[0].replace(',', '').strip()
            if re.match(r'^\d+\.?\d*$', txt):
                v = float(txt)
                if v > 1:  # 排除百分比等小數
                    return v

    except Exception as e:
        print(f'  [cnyes] {stock_no} 錯誤: {e}')
    return None


def yfinance_close(stock_no: str) -> Optional[float]:
    """備用：用 yfinance（Yahoo Finance）抓收盤價，自動嘗試 .TW 和 .TWO"""
    if not HAS_YFINANCE:
        return None
    for suffix in ['.TW', '.TWO']:
        try:
            ticker = yf.Ticker(stock_no + suffix)
            hist = ticker.history(period='5d')
            if not hist.empty:
                price = float(hist['Close'].iloc[-1])
                if price > 0:
                    return round(price, 2)
        except Exception:
            pass
    return None


def fetch_all_prices() -> Dict[str, Optional[float]]:
    """抓股價順序：cnyes → TWSE API → Yahoo Finance（三層備用）"""
    today = datetime.today()
    date_candidates = [
        (today - timedelta(days=i)).strftime('%Y%m%d')
        for i in range(0, 10)
    ]

    prices: Dict[str, Optional[float]] = {}

    for code in STOCK_CODES:
        source = 'cnyes'
        # 第一優先：cnyes
        price = cnyes_close(code)
        time.sleep(0.4)

        # 第二優先：TWSE API
        if price is None:
            source = 'TWSE'
            for date_str in date_candidates[:3]:
                price = twse_close(code, date_str)
                if price is not None:
                    break
                time.sleep(0.3)

        # 第三優先：Yahoo Finance（Google Finance 同源）
        if price is None:
            source = 'Yahoo'
            price = yfinance_close(code)
            time.sleep(0.3)

        if price is not None:
            print(f'  {code}: {price}  [{source}]')
        else:
            print(f'  {code}: 查無資料')
        prices[code] = price

    return prices


def update_html(prices: Dict[str, Optional[float]], today_str: str):
    """更新 index.html 的 PRICES 區塊與 LAST_UPDATE"""
    with open(INDEX_HTML, 'r', encoding='utf-8') as f:
        html = f.read()

    # 建立新的 PRICES 物件字串（維持原本的排版風格，每行 5 個）
    codes = list(STOCK_CODES)
    lines = []
    for i in range(0, len(codes), 5):
        chunk = codes[i:i+5]
        parts = []
        for c in chunk:
            v = prices.get(c)
            val = str(v) if v is not None else 'null'
            parts.append(f"  '{c}':{val}")
        lines.append(', '.join(parts) + ',')

    prices_body = '\n'.join(lines).rstrip(',') + ','
    new_prices_block = f'const PRICES = {{\n{prices_body}\n}};'

    # 取代 PRICES 區塊
    html = re.sub(
        r'const PRICES\s*=\s*\{[^}]*\};',
        new_prices_block,
        html,
        flags=re.DOTALL,
    )

    # 取代 LAST_UPDATE
    html = re.sub(
        r"const LAST_UPDATE\s*=\s*'[^']*';",
        f"const LAST_UPDATE = '{today_str}';",
        html,
    )

    with open(INDEX_HTML, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'\nindex.html 已更新（LAST_UPDATE = {today_str}）')


def git_push(today_str: str):
    """git add / commit / push"""
    cmds = [
        ['git', 'add', 'index.html'],
        ['git', 'commit', '-m', f'更新股價 {today_str}'],
        ['git', 'push'],
    ]
    cwd = '/Users/xiezhikai/Desktop/stock-tracker'
    for cmd in cmds:
        print(f'\n$ {" ".join(cmd)}')
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(result.stderr.strip())
        if result.returncode != 0:
            print(f'警告：指令失敗（exit {result.returncode}）')


def main():
    today_str = datetime.today().strftime('%Y-%m-%d')
    print(f'=== 股價更新腳本 {today_str} ===\n')

    print('正在抓取股價...')
    prices = fetch_all_prices()

    found = sum(1 for v in prices.values() if v is not None)
    print(f'\n共抓到 {found}/{len(prices)} 支股票的收盤價')

    update_html(prices, today_str)
    git_push(today_str)

    print('\n完成！')


if __name__ == '__main__':
    main()
