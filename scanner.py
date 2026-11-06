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
    """Prefer user-supplied ticker list; otherwise try ASX directory and fallback."""
    custom=ROOT/'tickers.txt'
    if custom.exists():
        raw=custom.read_text().splitlines()
    else:
        raw=[]
        try:
            r=requests.get('https://www.asx.com.au/asx/research/ASXListedCompanies.csv',timeout=20,headers={'User-Agent':'Mozilla/5.0'})
            r.raise_for_status()
            for line in csv.reader(io.StringIO(r.text)):
                if len(line)>1 and len(line[1].strip()) in (3,4) and line[1].strip().isalpha():
                    raw.append(line[1].strip())
                    COMPANY_NAMES[line[1].strip().upper()]=line[0].strip()
        except Exception as e:
            print('Directory unavailable:',e)
    raw=raw or DEFAULT
    tickers=[]
    for item in raw:
        code=item.strip().upper().replace('.AX','')
        if code.isalpha() and 2<=len(code)<=5 and code not in tickers:
            tickers.append(code)
    return tickers[:1200]

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
    codes=universe(); results=[]; errors=[]
    print('Universe:',len(codes))
    for i in range(0,len(codes),30):
        batch=codes[i:i+30]
        try:
            raw=yf.download(' '.join(c+'.AX' for c in batch),period='1y',interval='1d',group_by='ticker',auto_adjust=True,threads=True,progress=False,timeout=25)
            for code in batch:
                try:
                    symbol=code+'.AX'
                    h=raw[symbol] if isinstance(raw.columns,pd.MultiIndex) else raw
                    if not h.empty:
                        item=score(h,code)
                        if item:
                            item['name']=COMPANY_NAMES.get(code) or KNOWN_NAMES.get(code)
                            results.append(item)
                except Exception as e:errors.append(f'{code}: {str(e)[:80]}')
        except Exception as e:errors.append(f'batch {i}: {str(e)[:80]}')
        time.sleep(1)
    results.sort(key=lambda r:r['short_score'],reverse=True)
    payload={'updated_utc':datetime.now(timezone.utc).isoformat(),'source':'Yahoo Finance via yfinance (unofficial, may be delayed)','universe_size':len(codes),'scanned':len(results),'errors_count':len(errors),'method':'Rule-based technical screen; scores are not probabilities, forecasts or validated trading signals.','stocks':results}
    if not results:
        print('No valid results; retaining prior dataset to avoid publishing fake/stale replacement')
        raise SystemExit(1)
    (DATA/'stocks.json').write_text(json.dumps(payload,separators=(',',':')))
    print('Scanned:',len(results),'errors:',len(errors))

if __name__=='__main__':main()
