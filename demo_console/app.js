const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const fmt = new Intl.NumberFormat("zh-TW", {maximumFractionDigits: 1});
const titles = {m1:["MODULE 1 · OPERATIONS","異常監控中心"],m3:["MODULE 3 · ANALYTICS","營運分析助理"],m2:["MODULE 2 · EXPERIMENTATION","實驗營運控制"],m4:["MODULE 4 · SUPPORT","整合支援"]};
let experiments = [];
let chatSession = null;
const recordingMode = new URLSearchParams(window.location.search).has('recording');

const recordingFixtures={
  '/api/m1/incidents':{incidents:[{incident_id:'site_b#2026-06-15T03',status:'DETECTED',client_site_id:'site_b',event_hour:'2026-06-15 03:00:00.000',detected_at:'2026-08-03T07:57:44Z'}]},
  '/api/m1/incidents/status':{incident:{incident_id:'site_b#2026-06-15T03',status:'INVESTIGATING',updated_at:'2026-08-03T07:59:47Z'}},
  '/api/m3/report':{comparison:{dau:{actual:91,baseline_avg_7d:205.6,pct_change:-55.7},sessions:{actual:89,baseline_avg_7d:201.1,pct_change:-55.7},new_players:{actual:30,baseline_avg_7d:26.4,pct_change:13.6}},evidence:{key:'gold/first_look_reports/site_b_2026-06-10.json',last_modified:'2026-08-02T01:02:00Z'}},
  '/api/m3/ask':{
    diagnosis:{category:'diagnosis',answer:'今天截至下午 1:00，你有權限查看的所有站點共有 124 位活躍使用者；過去 30 天截至相同時間平均約有 177 位，目前少了約 30%。\n\n異常監控系統已於上午 11:00 發出告警，目前技術人員正在排查中。原因尚未確認。',scope:{mode:'all_authorised_sites',sites:['site_a','site_b','site_c']},request:{service:'IAM + API Gateway + governed analytics',identity:'all-authorised-sites',duration_ms:384,completed_at:'2026-08-03T08:08:16Z'}},
    forecast:{category:'forecast_not_supported',answer:'目前系統可以分析已發生的數據變化，但尚未建立並驗證人數預測模型，因此無法判定明天是否會恢復。',request:{service:'IAM + API Gateway · deterministic boundary',identity:'all-authorised-sites',duration_ms:42,completed_at:'2026-08-03T01:05:00Z'}}
  },
  '/api/m2/experiments':{summary:{total:6,running:2,needs_action:2,draft:1},experiments:[
    {name:'onboarding-copy-test',experiment_id:'exp_01',client_site_id:'site_a',game_id:'product_01',state:'running',health:'healthy',health_detail:'hourly checks passed',allocation_enabled:true,srm_status:'passed',total_exposed:1240},
    {name:'navigation-layout-test',experiment_id:'exp_02',client_site_id:'site_b',game_id:'product_02',state:'stopped_early',health:'action',health_detail:'hourly guardrail crossed',allocation_enabled:false,srm_status:'passed',total_exposed:684},
    {name:'recommendation-order-test',experiment_id:'exp_03',client_site_id:'site_c',game_id:'product_03',state:'stopped_early',health:'action',health_detail:'sample ratio mismatch',allocation_enabled:false,srm_status:'breached',total_exposed:100},
    {name:'search-ranking-test',experiment_id:'exp_04',client_site_id:'site_a',game_id:'product_04',state:'running',health:'watch',health_detail:'sample building',allocation_enabled:true,srm_status:'insufficient_sample',total_exposed:72},
    {name:'notification-timing-test',experiment_id:'exp_05',client_site_id:'site_b',game_id:'product_05',state:'draft',health:'neutral',health_detail:'not started',allocation_enabled:false,srm_status:'not_checked',total_exposed:'—'},
    {name:'workspace-home-test',experiment_id:'exp_06',client_site_id:'site_c',game_id:'product_06',state:'analyzed',health:'healthy',health_detail:'review ready',allocation_enabled:false,srm_status:'passed',total_exposed:1520}
  ],request:{completed_at:'2026-08-02T01:03:00Z'}},
  '/api/m4/chat':{
    answered:{response:'這個 Token Request 使用了 JSON，但文件要求 application/x-www-form-urlencoded，而且缺少 grant_type=client_credentials。請調整 Content-Type 並補上 grant_type 後重新送出；partner_id 與 client_secret 可以沿用。',category:'ANSWERED',model_invoked:false,session_id:'recording-session',request:{service:'API Gateway + Lambda + governed knowledge',identity:'client-operator-partner',duration_ms:642,completed_at:'2026-08-03T01:04:00Z'}},
    outOfScope:{response:'目前整合支援資料中沒有參展資訊，因此無法確認這次是否會參展。若需要進一步確認，請聯絡您的業務窗口。',category:'OUT_OF_SCOPE',session_id:'recording-session',request:{service:'API Gateway + Lambda · model not invoked',identity:'client-operator-partner',duration_ms:118,completed_at:'2026-08-03T01:05:00Z'}}
  }
};
const supportQuestions={packet:`你們這個 API 一直打失敗，幫我看一下：

POST /oauth/token
Content-Type: application/json

{
  "partner_id": "[REDACTED]",
  "client_secret": "[REDACTED]",
  "environment": "sandbox"
}

Response: 400 invalid_request`,exhibition:'你們這次有要來 XX 展覽嗎？'};

function toast(message){const el=$("#toast");el.textContent=message;el.classList.add("show");setTimeout(()=>el.classList.remove("show"),2200)}
function safe(value){return String(value??"—").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
async function request(url, options={}){if(recordingMode&&recordingFixtures[url]){const question=JSON.parse(options.body||'{}').question||'';if(url==='/api/m4/chat')return structuredClone(/展覽|exhibition/i.test(question)?recordingFixtures[url].outOfScope:recordingFixtures[url].answered);if(url==='/api/m3/ask')return structuredClone(/明天|tomorrow/i.test(question)?recordingFixtures[url].forecast:recordingFixtures[url].diagnosis);return structuredClone(recordingFixtures[url])}const response=await fetch(url,{cache:"no-store",headers:{"Content-Type":"application/json"},...options});let data;try{data=await response.json()}catch{data={error:"AWS response was not JSON"}}if(!response.ok)throw new Error(data.error||data.message||`HTTP ${response.status}`);return data}

$$('.nav').forEach(button=>button.addEventListener('click',()=>{const id=button.dataset.screen;$$('.nav,.screen').forEach(el=>el.classList.remove('active'));button.classList.add('active');const screen=$(`#${id}`);screen.classList.add('active');$('#eyebrow').textContent=titles[id][0];$('#page-title').textContent=titles[id][1];screen.querySelectorAll('.mode-tab').forEach((tab,index)=>tab.classList.toggle('active',index===0));screen.querySelectorAll('.module-mode').forEach((panel,index)=>panel.classList.toggle('active',index===0))}));

$$('.mode-tab').forEach(tab=>tab.addEventListener('click',()=>{const screen=tab.closest('.screen');screen.querySelectorAll('.mode-tab').forEach(x=>x.classList.remove('active'));screen.querySelectorAll('.module-mode').forEach(x=>x.classList.remove('active'));tab.classList.add('active');screen.querySelector(`[data-panel="${tab.dataset.mode}"]`).classList.add('active');if(screen.id==='m1'&&tab.dataset.mode==='interface')requestAnimationFrame(()=>drawHourlyChart(currentMetric))}));

const hourlySeries={
  activeUsers:{title:'今日累積活躍人數',actual:[22,37,58,82,104,124],baseline:[29.9,59.7,88.3,118.1,148.0,177.1],range:25},
  sessions:{title:'今日累積工作階段',actual:[19,32,50,72,91,106],baseline:[23.2,47.3,70.6,95.5,119.7,144.9],range:22},
  processedEvents:{title:'今日累積處理量',actual:[209,327,513,735,929,1088],baseline:[237,477,716,966,1208,1460],range:220}
};
const hourlyLabels=['08','09','10','11','12','13'];
let currentMetric='activeUsers';
function drawHourlyChart(metricKey){const canvas=$('#hourly-chart');if(!canvas)return;const ctx=canvas.getContext('2d'),series=hourlySeries[metricKey],ratio=window.devicePixelRatio||1,w=canvas.clientWidth||920,h=canvas.clientHeight||255;canvas.width=Math.round(w*ratio);canvas.height=Math.round(h*ratio);ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,w,h);const pad={l:58,r:18,t:18,b:34},cw=w-pad.l-pad.r,ch=h-pad.t-pad.b;const values=[...series.actual,...series.baseline.map(x=>x+series.range)];const max=Math.ceil(Math.max(...values)*1.1/100)*100;const x=i=>pad.l+(cw*i/(hourlyLabels.length-1)),y=v=>pad.t+ch-(v/max*ch);ctx.font='11px Segoe UI';ctx.fillStyle='#7189a3';ctx.strokeStyle='#1d3851';ctx.lineWidth=1;for(let i=0;i<=4;i++){const gy=pad.t+ch*i/4;ctx.beginPath();ctx.moveTo(pad.l,gy);ctx.lineTo(w-pad.r,gy);ctx.stroke();ctx.fillText(fmt.format(Math.round(max*(1-i/4))),5,gy+4)}hourlyLabels.forEach((label,i)=>ctx.fillText(`${label}:00`,x(i)-14,h-9));ctx.fillStyle='rgba(61,214,198,.10)';ctx.beginPath();series.baseline.forEach((v,i)=>{const py=y(v+series.range);i?ctx.lineTo(x(i),py):ctx.moveTo(x(i),py)});[...series.baseline].reverse().forEach((v,ri)=>{const i=series.baseline.length-1-ri;ctx.lineTo(x(i),y(Math.max(0,v-series.range)))});ctx.closePath();ctx.fill();function line(values,color,dash=[]){ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=2.5;ctx.setLineDash(dash);values.forEach((v,i)=>i?ctx.lineTo(x(i),y(v)):ctx.moveTo(x(i),y(v)));ctx.stroke();ctx.setLineDash([])}line(series.baseline,'#7994ad',[6,6]);line(series.actual,'#3dd6c6');const anomalyIndex=3;ctx.fillStyle='#ff6b72';ctx.shadowColor='#ff6b72';ctx.shadowBlur=12;ctx.beginPath();ctx.arc(x(anomalyIndex),y(series.actual[anomalyIndex]),6,0,Math.PI*2);ctx.fill();ctx.shadowBlur=0;ctx.fillStyle='#ff9ba0';ctx.font='700 11px Segoe UI';ctx.fillText('告警',x(anomalyIndex)-13,y(series.actual[anomalyIndex])-13)}
$$('.metric-choice').forEach(button=>button.addEventListener('click',()=>{currentMetric=button.dataset.metric;$$('.metric-choice').forEach(x=>x.classList.remove('active'));button.classList.add('active');$('#chart-title').textContent=hourlySeries[currentMetric].title;drawHourlyChart(currentMetric)}));
window.addEventListener('resize',()=>{if($('#m1').classList.contains('active')&&$('#m1 [data-panel="interface"]').classList.contains('active'))drawHourlyChart(currentMetric)});
$('#open-first-look').addEventListener('click',()=>{$('.nav[data-screen="m3"]').click();$('#m3 .mode-tab[data-mode="interface"]').click()});
$('#start-investigation').addEventListener('click',async()=>{const button=$('#start-investigation');button.disabled=true;button.textContent='更新中…';try{const incidentId=$('.alert-detail').dataset.incidentId;const d=await request('/api/m1/incidents/status',{method:'POST',body:JSON.stringify({incident_id:incidentId,status:'INVESTIGATING'})});$('#incident-status').textContent='排查中';button.textContent='已標記為排查中';button.classList.add('completed');toast('告警狀態已更新：排查中')}catch(error){button.disabled=false;button.textContent='標記為排查中';toast(error.message)}});

function addAnalyticsMessage(role,text,meta='',extra=''){const div=document.createElement('div');div.className=`message ${role} ${extra}`;div.innerHTML=`<p>${safe(text)}</p>${meta?`<small>${safe(meta)}</small>`:''}`;$('#analytics-messages').append(div);$('#analytics-messages').scrollTop=$('#analytics-messages').scrollHeight;return div}
async function runAnalyticsQuestion(question){const input=$('#analytics-input'),button=$('#analytics-form button');if(!question)return;addAnalyticsMessage('user',question,'剛剛 · 全部授權站點');input.value='';button.disabled=true;const typing=addAnalyticsMessage('assistant','正在讀取最新完整資料…','','typing');try{const d=await request('/api/m3/ask',{method:'POST',body:JSON.stringify({question})});typing.remove();addAnalyticsMessage('assistant',d.answer,d.category==='diagnosis'?'截至 13:00 · 過去 30 天相同時間平均':'目前能力範圍',d.category==='forecast_not_supported'?'scope-blocked':'');$('#analytics-proof').textContent=d.category==='diagnosis'?'DIAGNOSIS · 全部授權站點 · 告警狀態：排查中':'FORECAST NOT SUPPORTED · 未執行預測、未猜測答案';toast(d.category==='diagnosis'?'已完成營運數據比較':'已清楚說明目前能力邊界')}catch(error){typing.remove();addAnalyticsMessage('assistant',`服務暫時無法完成回答：${error.message}`,'AWS request failed','error');toast(error.message)}finally{button.disabled=false;input.focus()}}
$('#analytics-form').addEventListener('submit',event=>{event.preventDefault();runAnalyticsQuestion($('#analytics-input').value.trim())});
$$('.analytics-prompt').forEach(button=>button.addEventListener('click',()=>{$$('.analytics-prompt').forEach(x=>x.classList.remove('active'));button.classList.add('active');$('#analytics-input').value=button.dataset.analyticsQuestion;runAnalyticsQuestion(button.dataset.analyticsQuestion)}));

function neutralLabel(value){return String(value??'—').replace(/game/gi,'product').replace(/player/gi,'user').replace(/payout/gi,'experience').replace(/ggr/gi,'quality metric').replace(/bet/gi,'interaction')}
function renderExperiments(filter='all'){const rows=filter==='action'?experiments.filter(x=>x.health==='action'):experiments;$('#experiment-rows').innerHTML=rows.slice(0,7).map((x,index)=>`<button class="tr exp-row ${index===0?'selected':''}" data-experiment-id="${safe(x.experiment_id)}"><span><strong>${safe(neutralLabel(x.name))}</strong><small>${safe(x.experiment_id)}</small></span><span>${safe(x.client_site_id)}<small>${safe(neutralLabel(x.game_id))}</small></span><span><i class="pill">${safe(x.state)}</i></span><span><i class="pill ${safe(x.health)}">${safe(x.health)}</i><small>${safe(neutralLabel(x.health_detail))}</small></span><span>${x.allocation_enabled?'ENABLED':'CONTROL ONLY'}</span><span>${safe(x.srm_status)}<small>n=${safe(x.total_exposed)}</small></span></button>`).join('')||'<div class="tr"><span>沒有符合條件的實驗</span></div>';$$('.exp-row').forEach(row=>row.addEventListener('click',()=>{$$('.exp-row').forEach(x=>x.classList.remove('selected'));row.classList.add('selected');renderExperimentDetail(row.dataset.experimentId)}));if(rows.length)renderExperimentDetail(rows[0].experiment_id)}
function renderExperimentDetail(id){const exp=experiments.find(x=>x.experiment_id===id);if(!exp)return;const srmBreach=exp.srm_status==='breached';const guardrailBreach=exp.health_detail?.includes('guardrail');$('#experiment-detail').innerHTML=`<label>${exp.state==='stopped_early'?'AUTO-STOP EVIDENCE':'MONITORING EVIDENCE'}</label><h3>${safe(neutralLabel(exp.name))}</h3><div class="decision-step ${srmBreach?'fail':'pass'}"><b>Initial / Exposure SRM</b><span>${srmBreach?'Breached':exp.srm_status}</span><small>${srmBreach?'Observed 72 / 28 · expected 50 / 50':'Allocation within expected ratio'} · n=${safe(exp.total_exposed)}</small></div><div class="decision-step ${guardrailBreach?'fail':srmBreach?'muted-step':'pass'}"><b>Hourly Guardrail</b><span>${guardrailBreach?'Breached':srmBreach?'Not run':'Passed'}</span><small>${guardrailBreach?'Sessions 68 · minimum 120':srmBreach?'SRM failed first':'No threshold crossed'}</small></div><div class="system-actions"><b>System actions</b><span>✓ state → ${safe(exp.state)}</span><span>✓ allocation → ${exp.allocation_enabled?'enabled':'disabled'}</span><span>✓ ${exp.state==='stopped_early'?'SNS event published':'health status persisted'}</span></div>`}
$('#load-experiments').addEventListener('click',loadExperiments);
async function loadExperiments(){const button=$('#load-experiments');button.disabled=true;button.textContent='同步中…';try{const d=await request('/api/m2/experiments');experiments=d.experiments;$('#exp-total').textContent=d.summary.total;$('#exp-running').textContent=d.summary.running;$('#exp-action').textContent=d.summary.needs_action;$('#exp-draft').textContent=d.summary.draft;$('#exp-updated').textContent=`AWS Registry · ${new Date(d.request.completed_at).toLocaleTimeString('zh-TW')}`;renderExperiments($('.filter.active').dataset.filter);toast('Registry 已同步')}catch(error){toast(error.message)}finally{button.disabled=false;button.textContent='重新整理 Registry'}}
$$('.filter').forEach(button=>button.addEventListener('click',()=>{$$('.filter').forEach(x=>x.classList.remove('active'));button.classList.add('active');renderExperiments(button.dataset.filter)}));

function addMessage(role,text,meta='',extra=''){const div=document.createElement('div');div.className=`message ${role} ${extra}`;div.innerHTML=`<p>${safe(text)}</p>${meta?`<small>${safe(meta)}</small>`:''}`;$('#messages').append(div);$('#messages').scrollTop=$('#messages').scrollHeight;return div}
async function runSupportQuestion(question){const input=$('#chat-input'),button=$('#chat-form button');if(!question)return;addMessage('user',question,'Integration partner · just now');input.value='';button.disabled=true;const typing=addMessage('assistant','正在檢查安全規則與支援範圍…','','typing');try{const d=await request('/api/m4/chat',{method:'POST',body:JSON.stringify({question,session_id:chatSession})});chatSession=d.session_id;typing.remove();addMessage('assistant',d.response,`${d.category} · ${d.request.duration_ms} ms`,d.category==='OUT_OF_SCOPE'?'scope-blocked':'');$('#chat-proof').textContent=`${d.category} · ${d.request.service} · IAM ${d.request.identity} · ${new Date(d.request.completed_at).toLocaleTimeString('zh-TW')}`;toast(d.category==='OUT_OF_SCOPE'?'範圍外問題已拒絕':'已收到受治理的整合支援回答')}catch(error){typing.remove();addMessage('assistant',`服務暫時無法完成回答：${error.message}`,'AWS request failed','error');toast(error.message)}finally{button.disabled=false;input.focus()}}
$('#chat-form').addEventListener('submit',event=>{event.preventDefault();runSupportQuestion($('#chat-input').value.trim())});
$$('.scenario-button').forEach(button=>button.addEventListener('click',()=>{$$('.scenario-button').forEach(x=>x.classList.remove('active'));button.classList.add('active');const question=supportQuestions[button.dataset.supportScenario];$('#chat-input').value=question;runSupportQuestion(question)}));

experiments=structuredClone(recordingFixtures['/api/m2/experiments'].experiments);renderExperiments();
requestAnimationFrame(()=>document.querySelector('.exp-row[data-experiment-id="exp_02"]')?.click());
$('#chat-input').value=supportQuestions.packet;
if(!recordingMode)fetch('/api/health').then(r=>r.json()).catch(()=>({status:'offline'}));

async function prepareCaptureScene(scene){
  const [moduleId,state='initial']=scene.split('-');
  const nav=$(`.nav[data-screen="${moduleId}"]`);
  if(!nav)return;
  nav.click();
  $(`#${moduleId} .mode-tab[data-mode="interface"]`)?.click();
  if(scene==='m1-result'){
    $('#start-investigation').click();
    await new Promise(resolve=>setTimeout(resolve,80));
  }
  if(scene==='m3-result')await runAnalyticsQuestion('今天人數為何突然掉這麼多？');
  if(scene==='m3-forecast'){
    await runAnalyticsQuestion('今天人數為何突然掉這麼多？');
    await runAnalyticsQuestion('明天人數就會回來嗎？');
  }
  if(scene==='m4-result')await runSupportQuestion(supportQuestions.packet);
  if(scene==='m4-out-of-scope'){
    await runSupportQuestion(supportQuestions.packet);
    await runSupportQuestion(supportQuestions.exhibition);
    $$('.scenario-button').forEach((button,index)=>button.classList.toggle('active',index===1));
  }
  window.scrollTo(0,0);
  document.documentElement.dataset.captureReady=state;
}

const captureScene=new URLSearchParams(window.location.search).get('capture');
if(recordingMode&&captureScene)setTimeout(()=>prepareCaptureScene(captureScene),50);
