let DATA=null, range="12h";
const $=s=>document.querySelector(s);
async function load(){try{DATA=await fetch("data/statistics.json?"+Date.now()).then(r=>r.json());render()}catch(e){$("#status").textContent="No data yet. Run the GitHub Action to collect the first dataset."}}
function render(){
 const a=DATA.account, s=DATA.summary;
 $("#accountSub").textContent=`${a.platform_label} · @${a.handle}`;
 $("#updated").textContent=`Updated ${new Date(DATA.generated_at).toLocaleString()}`;
 $("#status").textContent=`Current data covers ${DATA.history_days} days of collected activity. Baselines use historical posting counts for comparable periods.`;
 $("#cards").innerHTML=card("Last 12 hours",s["12h"].current,s["12h"].baseline,s["12h"].pct)+card("Today",s["24h"].current,s["24h"].baseline,s["24h"].pct)+card("This week",s["7d"].current,s["7d"].baseline,s["7d"].pct);
 $("#baseline").innerHTML=row("Average posts/day",DATA.baseline.avg_day.toFixed(1))+row("Average posts/week",DATA.baseline.avg_week.toFixed(1))+row("Average posts/12 hours",DATA.baseline.avg_12h.toFixed(1))+row("Average posts/6 hours",DATA.baseline.avg_6h.toFixed(1))+row("Average posts/hour",DATA.baseline.avg_hour.toFixed(2))+row("History",DATA.history_days+" days");
 $("#alerts").innerHTML=DATA.alerts.length?DATA.alerts.map(x=>`<div class="alert"><strong class="${x.level}">${x.label}</strong><small>${x.window}: ${x.current} posts · expected ${x.low}–${x.high} · ${x.pct>0?"+":""}${x.pct.toFixed(0)}%</small></div>`).join(""):`<div class="alert"><strong class="normalc">No unusual activity</strong><small>Current windows are inside their expected ranges.</small></div>`;
 draw();
}
function card(label,current,base,pct){let c=pct>50?"high":pct<-50?"low":"normalc";return `<div class="card"><div class="label">${label}</div><div class="value">${current}</div><div class="sub">Normal ${base.toFixed(1)} · <span class="delta ${c}">${pct>0?"+":""}${pct.toFixed(0)}%</span></div></div>`}
function row(a,b){return `<div class="row"><span>${a}</span><span>${b}</span></div>`}
function draw(){
 const cvs=$("#chart"),ctx=cvs.getContext("2d"),r=cvs.getBoundingClientRect(),d=devicePixelRatio||1;cvs.width=r.width*d;cvs.height=r.height*d;ctx.scale(d,d);
 const w=r.width,h=r.height,vals=DATA.series[range]||DATA.series["12h"]; if(!vals.length)return;
 const max=Math.max(...vals.map(x=>Math.max(x.current,x.baseline)),1)*1.25, pad=35;
 ctx.strokeStyle="#252c37";ctx.fillStyle="#6e7887";ctx.font="11px system-ui";
 for(let i=0;i<5;i++){let y=pad+(h-pad*1.4)*i/4;ctx.beginPath();ctx.moveTo(pad,y);ctx.lineTo(w-10,y);ctx.stroke();ctx.fillText(Math.round(max*(1-i/4)),4,y+4)}
 function line(key,style){ctx.strokeStyle=style;ctx.lineWidth=2;ctx.beginPath();vals.forEach((v,i)=>{let x=pad+(w-pad-12)*i/(vals.length-1||1),y=pad+(h-pad*1.4)*(1-v[key]/max);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke()}
 line("baseline","#5f6877");line("current","#eef2f7");
}
document.querySelectorAll(".ranges button").forEach(b=>b.onclick=()=>{document.querySelectorAll(".ranges button").forEach(x=>x.classList.remove("selected"));b.classList.add("selected");range=b.dataset.range;draw()});
load();window.addEventListener("resize",draw);