'use strict';

/* Educational calculations mirror the Python analyzer. All plotted data is synthetic. */
const CurveMath = (() => {
  function finitePoints(points, xKey, yKey) {
    if (points.length < 2 || points.some(p => !Number.isFinite(p[xKey]) || !Number.isFinite(p[yKey]))) throw Error('曲線需要至少兩個有限值資料點。');
    const sorted = [...points].sort((a,b) => a[xKey]-b[xKey]);
    if (sorted.some((p,i) => i && p[xKey] <= sorted[i-1][xKey])) throw Error('掃描軸需要唯一且遞增的取樣點。');
    return sorted;
  }
  function vth(points, thresholdA) {
    if (!(thresholdA > 0) || !Number.isFinite(thresholdA)) throw Error('閾值電流須為正的有限值。');
    const curve = finitePoints(points,'Vg_V','Id_A');
    if (new Set(curve.map(p=>p.Vds_V)).size!==1) throw Error('VTH 比較必須使用固定 VDS。');
    if (curve.some((p,i)=>i && p.Id_A < curve[i-1].Id_A-1e-12)) throw Error('轉移曲線非單調，無法唯一抽取 VTH。');
    const crossings=[];
    for(let i=0;i<curve.length-1;i++){
      const a=curve[i], b=curve[i+1];
      if(a.Id_A===thresholdA)crossings.push(a.Vg_V);
      if((a.Id_A-thresholdA)*(b.Id_A-thresholdA)<0)crossings.push(a.Vg_V+(thresholdA-a.Id_A)*(b.Vg_V-a.Vg_V)/(b.Id_A-a.Id_A));
      if(b.Id_A===thresholdA)crossings.push(b.Vg_V);
    }
    const unique=[...new Set(crossings.map(x=>Number(x.toFixed(14))))];
    if(unique.length===0)throw Error('閾值電流超出曲線範圍，請調整門檻。');
    if(unique.length!==1)throw Error('閾值有多個交點，請檢查掃描資料。');
    return unique[0];
  }
  function ron(points, low=0.01, high=0.10) {
    if(!Number.isFinite(low)||!Number.isFinite(high)||low<0||high<=low)throw Error('RON 擬合範圍不正確。');
    if(points.some(p=>!Number.isFinite(p.Vg_V)||!Number.isFinite(p.Vds_V)||!Number.isFinite(p.Id_A)))throw Error('輸出曲線含缺值或非有限值。');
    if(new Set(points.map(p=>p.Vg_V)).size!==1)throw Error('RON 抽取必須使用固定 VGS。');
    const curve=finitePoints(points.filter(p=>p.Vds_V>=low-1e-12 && p.Vds_V<=high+1e-12),'Vds_V','Id_A');
    const mx=curve.reduce((s,p)=>s+p.Vds_V,0)/curve.length,my=curve.reduce((s,p)=>s+p.Id_A,0)/curve.length;
    let ssx=0,sxy=0;curve.forEach(p=>{ssx+=(p.Vds_V-mx)**2;sxy+=(p.Vds_V-mx)*(p.Id_A-my)});
    const slope=sxy/ssx,intercept=my-slope*mx;
    if(!(slope>0)||!Number.isFinite(slope))throw Error('RON 擬合斜率必須為正。');
    const residual=curve.reduce((s,p)=>s+(p.Id_A-slope*p.Vds_V-intercept)**2,0),total=curve.reduce((s,p)=>s+(p.Id_A-my)**2,0);
    return {ron:1/slope,r2:1-residual/total,n:curve.length,slope,intercept};
  }
  function parseCSV(text){
    const lines=text.trim().split(/\r?\n/),headers=lines.shift().split(',');
    const required=['device_id','sweep','stress_time_s','temperature_C','Vg_V','Vds_V','Id_A','Ig_A','cycle'];
    if(!required.every(k=>headers.includes(k))||!lines.length)throw Error('合成範例缺少必要欄位。');
    return lines.map(line=>{
      const fields=line.split(',');if(fields.length!==headers.length)throw Error('CSV 欄位數不一致。');
      const row={};headers.forEach((key,i)=>{row[key]=['device_id','sweep'].includes(key)?fields[i]:fields[i].trim()===''?NaN:Number(fields[i])});
      if(!row.device_id||!['transfer','output'].includes(row.sweep)||required.slice(2).some(k=>!Number.isFinite(row[k])))throw Error('CSV 含不合法欄位值。');
      if(row.stress_time_s<0||row.temperature_C< -273.15)throw Error('應力時間與溫度超出可接受範圍。');
      return row;
    });
  }
  function extract(rows, device, stress, threshold, high){
    const group=rows.filter(p=>p.device_id===device && p.stress_time_s===stress && p.temperature_C===25);
    if(!group.length||new Set(group.map(p=>p.cycle)).size!==1)throw Error('找不到唯一的元件與應力量測組。');
    const transfer=group.filter(p=>p.sweep==='transfer'),output=group.filter(p=>p.sweep==='output');
    return {vth:vth(transfer,threshold),...ron(output,.01,high),transfer,output};
  }
  return {vth,ron,parseCSV,extract};
})();
if(typeof module!=='undefined'&&module.exports)module.exports=CurveMath;

if(typeof document!=='undefined'){
  const $=s=>document.querySelector(s);
  const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const nav=$('#site-nav'),menu=$('.menu-toggle');
  menu.addEventListener('click',()=>{const open=menu.getAttribute('aria-expanded')!=='true';menu.setAttribute('aria-expanded',String(open));nav.classList.toggle('is-open',open);menu.querySelector('span').textContent=open?'−':'＋'});
  nav.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{menu.setAttribute('aria-expanded','false');nav.classList.remove('is-open');menu.querySelector('span').textContent='＋'}));
  let dataRows=[], latest=null;
  function renderReadings(readings){$('#reading-list').innerHTML=readings.map((p,i)=>`<details><summary><span class="reading-number">${String(i+1).padStart(2,'0')}</span><span class="reading-title">${esc(p.label)}<small>${esc(p.year)} · ${esc(p.access)}</small></span></summary><div class="reading-body"><p class="paper-title">${esc(p.title)}</p><p><strong>閱讀問題：</strong>${esc(p.question)}</p><p>${esc(p.method)}</p><p><strong>預計交付：</strong>${esc(p.deliverable)}</p><a href="${esc(p.doi)}" target="_blank" rel="noreferrer">DOI ↗</a><a href="${esc(p.source)}" target="_blank" rel="noreferrer">原始來源 ↗</a></div></details>`).join('')}
  function renderProjects(projects){$('#project-list').innerHTML=projects.map((p,i)=>`<article class="project-item"><span class="project-no">${String(i+1).padStart(2,'0')}</span><div><h3>${esc(p.name)}</h3><p>${esc(p.description)}</p><div class="project-meta">${p.tags.map(t=>`<span>${esc(t)}</span>`).join('')}</div><p class="project-role">${esc(p.context)}</p><div class="inline-links"><a href="${esc(p.url)}" target="_blank" rel="noreferrer">${esc(p.kind)} ↗</a><a href="${esc(p.source)}" target="_blank" rel="noreferrer">原始碼 ↗</a></div></div><a class="project-arrow" href="${esc(p.url)}" target="_blank" rel="noreferrer" aria-label="開啟${esc(p.name)}">↗</a></article>`).join('')}
  function renderMilestones(items,phase='all'){$('#milestone-list').innerHTML=items.filter(m=>phase==='all'||m.phase===phase).map(m=>`<li><span class="milestone-date">${esc(m.date)}<small>${esc(m.year)}</small></span><div><h4>${esc(m.title)}</h4><p>${esc(m.description)}</p></div><span class="planned">規劃檢核</span></li>`).join('')}
  function drawPlot(baseline,stressed,threshold,svth,bvth){
    const svg=$('#transfer-plot'),width=Math.max(280,Math.min(760,svg.getBoundingClientRect().width)),left=53,right=width-17,top=48,bottom=280;
    svg.setAttribute('viewBox',`0 0 ${width} 330`);
    const all=[...baseline,...stressed],xmax=Math.max(...all.map(p=>p.Vg_V)),ymax=Math.max(...all.map(p=>p.Id_A))*1000*1.08;
    const x=v=>left+(right-left)*v/xmax,y=v=>bottom-(bottom-top)*v/ymax;
    let content='<title>合成資料 Vg–Id 轉移曲線</title><desc>淺灰虛線為基準，綠線為選定應力時間；橘色虛線為定電流閾值。</desc>';
    for(let i=0;i<=4;i++){const xx=xmax*i/4,yy=ymax*i/4;content+=`<path d="M${x(xx)} ${top}V${bottom}M${left} ${y(yy)}H${right}" stroke="#e1e6dc" stroke-width="1"/><text x="${x(xx)}" y="${bottom+20}" text-anchor="middle">${xx.toFixed(1)}</text><text x="${left-10}" y="${y(yy)+4}" text-anchor="end">${yy.toFixed(2)}</text>`}
    const line=points=>[...points].sort((a,b)=>a.Vg_V-b.Vg_V).map(p=>`${x(p.Vg_V)},${y(p.Id_A*1000)}`).join(' ');
    content+=`<polyline data-curve="baseline" points="${line(baseline)}" fill="none" stroke="#929f98" stroke-width="2" stroke-dasharray="5 4"/><polyline data-curve="selected" points="${line(stressed)}" fill="none" stroke="#27736b" stroke-width="2.4"/><path d="M${left} ${y(threshold*1000)}H${right}" stroke="#a65c3e" stroke-dasharray="4 5"/><circle cx="${x(svth)}" cy="${y(threshold*1000)}" r="4.5" fill="#a65c3e"/><circle cx="${x(bvth)}" cy="${y(threshold*1000)}" r="3" fill="#929f98"/>`;
    const legendOne=Math.max(115,width-245),legendTwo=width-110;
    content+=`<text x="${left}" y="22" fill="#62716d">ID (mA)</text><text x="${right}" y="${bottom+43}" text-anchor="end" fill="#62716d">VGS (V)</text><path d="M${legendOne} 17h15" stroke="#929f98" stroke-width="2" stroke-dasharray="5 4"/><text x="${legendOne+20}" y="21">baseline</text><path d="M${legendTwo} 17h15" stroke="#27736b" stroke-width="2.4"/><text x="${legendTwo+20}" y="21">應力後</text>`;
    svg.innerHTML=`<g font-family="Segoe UI,Microsoft JhengHei,sans-serif" font-size="11" fill="#62716d">${content}</g>`;
  }
  function updateDemo(){
    const message=$('#demo-message');
    try{
      if(!dataRows.length)return;
      if(!$('#threshold-input').validity.valid)throw Error('請輸入 0.1–1.5 mA，間隔為 0.1 mA。');
      const device=$('#device-select').value,stress=Number($('#stress-select').value),threshold=Number($('#threshold-input').value)/1000,high=Number($('#window-select').value);
      const current=CurveMath.extract(dataRows,device,stress,threshold,high),baseline=CurveMath.extract(dataRows,device,0,threshold,high);
      if(current.transfer[0].Vds_V!==baseline.transfer[0].Vds_V||current.output[0].Vg_V!==baseline.output[0].Vg_V)throw Error('應力與基準的量測偏壓不一致。');
      latest={device_id:device,stress_time_s:stress,temperature_C:25,current_threshold_A:threshold,transfer_vds_V:.1,ron_vgs_V:5,ron_vds_min_V:.01,ron_vds_max_V:high,vth_V:current.vth,ron_ohm:current.ron,delta_vth_V:current.vth-baseline.vth,normalized_ron:current.ron/baseline.ron,r_squared:current.r2,fit_points:current.n,data_origin:'synthetic'};
      const n=latest;$('#demo-metrics').innerHTML=`<div><span>VTH</span><strong>${n.vth_V.toFixed(4)}<small>V</small></strong></div><div><span>低場 RON</span><strong>${n.ron_ohm.toFixed(4)}<small>Ω</small></strong></div><div><span>ΔVTH</span><strong>${(n.delta_vth_V*1000).toFixed(2)}<small>mV</small></strong></div><div><span>RON / RON,0</span><strong>${n.normalized_ron.toFixed(4)}<small>×</small></strong></div>`;
      drawPlot(baseline.transfer,current.transfer,threshold,current.vth,baseline.vth);
      message.classList.remove('error');message.textContent=`${device} · 低場擬合 ${current.n} 點 · R² = ${current.r2.toFixed(6)} · 與相同條件 t = 0 比較`;
      $('#download-results').disabled=false;
    }catch(error){latest=null;$('#download-results').disabled=true;message.classList.add('error');message.textContent=error.message;$('#demo-metrics').querySelectorAll('strong').forEach(x=>x.textContent='—');$('#transfer-plot').innerHTML='<text x="380" y="170" text-anchor="middle" fill="#a65c3e" font-size="15">請修正抽取條件後重新計算</text>'}
  }
  $('#analyzer-controls').addEventListener('submit',event=>event.preventDefault());
  $('#analyzer-controls').addEventListener('input',updateDemo);
  let resizeFrame;window.addEventListener('resize',()=>{cancelAnimationFrame(resizeFrame);resizeFrame=requestAnimationFrame(updateDemo)});
  $('#download-results').addEventListener('click',()=>{
    if(!latest)return;const csv=Object.keys(latest).join(',')+'\r\n'+Object.values(latest).join(',')+'\r\n';
    const url=URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download=`synthetic_${latest.device_id}_${latest.stress_time_s}s_metrics.csv`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  async function boot(){
    const response=await fetch('data/portfolio.json');if(!response.ok)throw Error('無法讀取作品與選讀清單。');const portfolio=await response.json();
    renderReadings(portfolio.readings);renderProjects(portfolio.projects);renderMilestones(portfolio.milestones);
    document.querySelectorAll('[data-phase]').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('[data-phase]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));renderMilestones(portfolio.milestones,button.dataset.phase)}));
    const dataResponse=await fetch('projects/gan-reliability-analyzer/data/synthetic_measurements.csv');if(!dataResponse.ok)throw Error('合成範例載入失敗；仍可下載原始碼與範例資料。');dataRows=CurveMath.parseCSV(await dataResponse.text());updateDemo();
  }
  boot().catch(error=>{$('#demo-message').textContent=error.message;$('#demo-message').classList.add('error')});
}
