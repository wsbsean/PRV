import json, os, statistics, urllib.request, datetime as dt, xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

ROOT=os.path.dirname(os.path.abspath(__file__)); DATA=os.path.join(ROOT,"data")
FEED="https://www.trumpstruth.org/feed?limit=500"
UTC=dt.timezone.utc
def now(): return dt.datetime.now(UTC)
def fetch():
    req=urllib.request.Request(FEED,headers={"User-Agent":"PostPulse/1.0 public-monitor"})
    with urllib.request.urlopen(req,timeout=30) as r: return r.read()
def parse(xml):
    root=ET.fromstring(xml); out=[]
    for item in root.findall(".//item"):
        d=item.findtext("pubDate"); link=item.findtext("link") or ""
        if not d: continue
        try: t=parsedate_to_datetime(d).astimezone(UTC)
        except: continue
        out.append({"id":link or d,"timestamp":t.isoformat(),"url":link})
    return out
def load():
    p=os.path.join(DATA,"posts.json")
    try:return json.load(open(p,encoding="utf8"))
    except:return []
def save(x): json.dump(x,open(os.path.join(DATA,"posts.json"),"w",encoding="utf8"),indent=2)
def count(posts,start,end): return sum(start<=dt.datetime.fromisoformat(x["timestamp"])<end for x in posts)
def bins(posts,window_hours,days=7):
    end=now().replace(minute=0,second=0,microsecond=0); start=end-dt.timedelta(days=days)
    step=dt.timedelta(hours=window_hours); cur=start; out=[]
    while cur<end:
        e=cur+step; out.append({"current":count(posts,cur,e),"baseline":0,"ts":cur.isoformat()});cur=e
    # baseline is comparable-period median across prior days
    for i,x in enumerate(out):
        vals=[]
        for j in range(1,8):
            a=cur-dt.timedelta(days=j)-dt.timedelta(hours=window_hours*(len(out)-i-1))
            # not used; dashboard uses baseline averages, chart current vs rolling average
        x["baseline"]=sum(z["current"] for z in out)/max(len(out),1)
    return out
def calc(posts):
    t=now(); periods={"1h":dt.timedelta(hours=1),"6h":dt.timedelta(hours=6),"12h":dt.timedelta(hours=12),"24h":dt.timedelta(hours=24),"3d":dt.timedelta(days=3),"7d":dt.timedelta(days=7),"30d":dt.timedelta(days=30),"90d":dt.timedelta(days=90)}
    # Daily/hourly baselines use all complete available historical periods; current windows are recent.
    def avg_for(delta,unit):
        vals=[]; end=t.replace(minute=0,second=0,microsecond=0)
        if unit=="day": end=t.replace(hour=0,minute=0,second=0,microsecond=0); step=dt.timedelta(days=1)
        elif unit=="week": end=t-dt.timedelta(days=t.weekday(),hours=t.hour,minutes=t.minute,seconds=t.second,microseconds=t.microsecond); step=dt.timedelta(days=7)
        else: step=delta
        cur=end
        for _ in range(90):
            a=cur-step; vals.append(count(posts,a,cur));cur=a
        return statistics.mean(vals) if vals else 0
    base={"avg_day":avg_for(dt.timedelta(days=1),"day"),"avg_week":avg_for(dt.timedelta(days=7),"week"),"avg_12h":avg_for(dt.timedelta(hours=12),"x"),"avg_6h":avg_for(dt.timedelta(hours=6),"x"),"avg_hour":avg_for(dt.timedelta(hours=1),"x")}
    summary={}
    for k,d in [("12h",dt.timedelta(hours=12)),("24h",dt.timedelta(days=1)),("7d",dt.timedelta(days=7))]:
        c=count(posts,t-d,t); b={"12h":base["avg_12h"],"24h":base["avg_day"],"7d":base["avg_week"]}[k];summary[k]={"current":c,"baseline":b,"pct":((c-b)/b*100 if b else 0)}
    series={}
    for key,hours in [("1h",1),("6h",6),("12h",12),("24h",24),("3d",72),("7d",168),("30d",720),("90d",2160)]:
        step=dt.timedelta(hours=hours); n=24 if hours<=24 else 30; arr=[]
        for i in range(n-1,-1,-1):
            e=t-dt.timedelta(hours=i*hours);a=e-step;c=count(posts,a,e);arr.append({"current":c,"baseline":c})
        b=sum(x["current"] for x in arr)/len(arr) if arr else 0
        for x in arr:x["baseline"]=b
        series[key]=arr
    alerts=[]
    for k in ("12h","24h","7d"):
        s=summary[k]; low=s["baseline"]*0.5; high=s["baseline"]*1.5
        if s["current"]>high: alerts.append({"label":"HIGH ACTIVITY","level":"high","window":k,"current":s["current"],"low":round(low,1),"high":round(high,1),"pct":s["pct"]})
        elif s["current"]<low: alerts.append({"label":"LOW ACTIVITY","level":"low","window":k,"current":s["current"],"low":round(low,1),"high":round(high,1),"pct":s["pct"]})
    return {"generated_at":t.isoformat(),"account":{"name":"Donald Trump","handle":"realDonaldTrump","platform_label":"Truth Social"},"history_days":len({x["timestamp"][:10] for x in posts}),"baseline":base,"summary":summary,"series":series,"alerts":alerts}
def main():
    posts=load()
    try:new=parse(fetch())
    except Exception as e: print("Feed error:",e);new=[]
    by={x["id"]:x for x in posts}
    for x in new:by[x["id"]]=x
    posts=sorted(by.values(),key=lambda x:x["timestamp"])
    # Keep two years locally; enough for useful baselines without growing the repo forever.
    cutoff=(now()-dt.timedelta(days=730)).isoformat();posts=[x for x in posts if x["timestamp"]>=cutoff]
    save(posts);json.dump(calc(posts),open(os.path.join(DATA,"statistics.json"),"w",encoding="utf8"),indent=2)
if __name__=="__main__":main()
