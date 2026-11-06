"""Scheduled free-data ASX market screener; informational, not trading advice."""
import csv, io, json, math, os, time
from datetime import datetime, timezone
from pathlib import Path
import requests
import yfinance as yf
import pandas as pd

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
DATA.mkdir(exist_ok=True)
COMPANY_NAMES={}
KNOWN_NAMES={'BHP': 'BHP Group Limited', 'CBA': 'Commonwealth Bank of Australia', 'CSL': 'CSL Limited', 'WBC': 'Westpac Banking Corporation', 'NAB': 'National Australia Bank Limited', 'ANZ': 'ANZ Group Holdings Limited', 'MQG': 'Macquarie Group Limited', 'WES': 'Wesfarmers Limited', 'WOW': 'Woolworths Group Limited', 'RIO': 'Rio Tinto Limited', 'FMG': 'Fortescue Limited', 'TLS': 'Telstra Group Limited', 'GMG': 'Goodman Group', 'XRO': 'Xero Limited', 'NXT': 'NEXTDC Limited', 'MP1': 'Megaport Limited', 'PLS': 'Pilbara Minerals Limited', 'WDS': 'Woodside Energy Group Ltd', 'QAN': 'Qantas Airways Limited', 'REA': 'REA Group Ltd', 'CAR': 'CAR Group Limited', 'RMD': 'ResMed Inc.', 'COH': 'Cochlear Limited', 'COL': 'Coles Group Limited', 'AMP': 'AMP Limited', 'NST': 'Northern Star Resources Limited', 'NEU': 'Neuren Pharmaceuticals Limited', 'EML': 'EML Payments Limited', 'NEC': 'Nine Entertainment Co. Holdings Limited', 'BXB': 'Brambles Limited'}
DEFAULT=['BHP','CBA','CSL','WBC','NAB','ANZ','MQG','WES','WOW','RIO','FMG','TLS','GMG','TCL','ALL','XRO','NXT','MP1','SLC','CHC','PLS','LTR','IGO','MIN','PXA','HUB','NWL','AMP','NST','WDS','STO','QAN','REA','CAR','CPU','RMD','COH','JHX','COL','ORG','AGL','SUN','IAG','QBE','S32','ALD','AMC','SHL','PME','TWE','JBH','DMP','A2M','MFG','ZIP','NEA','GQG','SEK','SGP','GPT','SCG','VCX','MGR','DXS','RHC','ILU','ORI','BSL','LYC','PDN','BOE','DRO','HMC','SIG','LNW']

def universe():
    """Only explicitly user-confirmed Plus500 instruments, never general exchange lists."""
    path=ROOT/'plus500_watchlist.csv'
    rows=list(csv.DictReader(path.open(encoding='utf-8-sig',newline='')))
    confirmed=[]
    for row in rows:
        if row.get('verified','').strip().lower()!='yes':continue
        symbol=row.get('yahoo_symbol','').strip().upper()
        if not symbol or symbol in [r['yahoo_symbol'] for r in confirmed]:continue
        confirmed.append(dict(row,yahoo_symbol=symbol))
    return confirmed

def val(x):
    try:
        x=float(x)
        return x if math.isfinite(x) else None
    except (TypeError,ValueError):return None

def score(history, code):
    h=history.dropna(subset=['Close'])
    if len(h)<65:return None
    c=h['Close'].astype(float); v=h['Volume'].fillna(0).astype(float)
    last=val(c.iloc[-1]); prev=val(c.iloc[-2]); sma20=val(c.tail(20).mean()); sma50=val(c.tail(50).mean()); sma200=val(c.tail(200).mean()) if len(c)>=200 else None
    r5=val((last/c.iloc[-6]-1)*100) if len(c)>5 else None
    r20=val((last/c.iloc[-21]-1)*100) if len(c)>20 else None
    r60=val((last/c.iloc[-61]-1)*100) if len(c)>60 else None
    vol20=val(v.iloc[-21:-1].mean())
    volratio=val(v.iloc[-1]/vol20) if vol20 and vol20>0 else None
    hi20=val(h['High'].iloc[-21:-1].max())
    daily=val((last/prev-1)*100) if prev else None
    turnover=val(last*v.tail(20).mean())
    # Heuristic screen only. NOT calibrated probabilities or backtested forecasts.
    short=35
    short+=20 if last>sma20 else -10
    short+=15 if r5 is not None and r5>0 else -8
    short+=15 if volratio is not None and volratio>1.7 else (5 if volratio and volratio>1.2 else 0)
    short+=15 if hi20 and last>hi20 else 0
    short+=8 if r20 is not None and r20>0 else 0
    if turnover is not None and turnover<100000:short-=20
    long=35
    long+=20 if last>sma50 else -10
    long+=20 if sma200 and last>sma200 else 0
    long+=15 if r60 is not None and r60>0 else 0
    long+=10 if sma20>sma50 else 0
    # Long-term score is price-trend only; fundamentals not included.
    return dict(ticker=code,price=last,change_pct=daily,return_5d=r5,return_20d=r20,return_60d=r60,volume_ratio=volratio,avg_turnover_aud=turnover,short_score=max(0,min(100,short)),long_score=max(0,min(100,long)),sma20=sma20,sma50=sma50,sma200=sma200,breakout=bool(hi20 and last>hi20),history=[{'date':str(d.date()),'close':round(float(p),3)} for d,p in c.tail(90).items()])

def main():
    entries=universe(); results=[]; errors=[]
    print('Confirmed Plus500 watchlist:',len(entries))
    for i in range(0,len(entries),20):
        batch=entries[i:i+20]; symbols=[x['yahoo_symbol'] for x in batch]
        try:
            raw=yf.download(' '.join(symbols),period='1y',interval='1d',group_by='ticker',auto_adjust=True,threads=True,progress=False,timeout=30)
            for row in batch:
                symbol=row['yahoo_symbol']
                try:
                    history=raw[symbol] if isinstance(raw.columns,pd.MultiIndex) else raw
                    if history.empty:continue
                    item=score(history,row['plus500_name'])
                    if item:
                        item.update(ticker=row['plus500_name'],name=row['company_name'],country=row['country'],currency=row['currency'],yahoo_symbol=symbol,plus500_verified='User-confirmed from screenshots; availability must be rechecked')
                        results.append(item)
                except Exception as e:errors.append(f'{symbol}: {str(e)[:100]}')
        except Exception as e:errors.append(f'batch {i}: {str(e)[:100]}')
        time.sleep(1)
    if not results:raise SystemExit('No valid market data. Existing published data retained.')
    payload={'updated_utc':datetime.now(timezone.utc).isoformat(),'source':'Yahoo Finance via yfinance (unofficial, delayed; NOT Plus500 CFD quotes)','universe_size':len(entries),'scanned':len(results),'errors_count':len(errors),'method':'Technical watchlist only; no validated predictions. Plus500 availability based on user screenshots, not live broker verification.','stocks':results}
    (DATA/'stocks.json').write_text(json.dumps(payload,separators=(',',':')))
    print('Scanned:',len(results),'errors:',errors[:8])

if __name__=='__main__':main()
