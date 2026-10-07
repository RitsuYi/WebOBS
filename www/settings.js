"use strict";
const form=document.getElementById('configuration');
const fields=()=>[...form.querySelectorAll('input[name],select[name]')];
let config=null,defaults=null,token=null,canEdit=false,hardware=[],mappingTypes={};
const mappingLabels={'cpu.usage':'CPU 使用率','cpu.frequencyMhz':'CPU 频率','cpu.voltageV':'CPU 电压','cpu.powerW':'CPU 功耗','gpu.usage':'GPU 使用率','gpu.frequencyMhz':'GPU 频率','gpu.voltageV':'GPU 电压','gpu.powerW':'GPU 功耗','system.powerW':'整机实测功率'};
const units={Load:'%',Clock:'MHz',Voltage:'V',Power:'W',Temperature:'°C',Fan:'RPM'};
const autoSources={'cpu.usage':'Total CPU Usage（Windows 整体使用率）','cpu.voltageV':'主板 Vcore（优先 NCT6798D）','cpu.powerW':'CPU Package Power / CPU Package'};
const fmt=(n,d=0)=>typeof n==='number'&&Number.isFinite(n)?n.toFixed(d):'—';
const node=(tag,text,className)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(className)e.className=className;return e;};
function status(message,kind=''){form.classList.remove('dirty','saved','error');if(kind)form.classList.add(kind);document.getElementById('save-state').textContent=message;}
async function request(url,options){const r=await fetch(url,options);const data=await r.json();if(!r.ok)throw Error(data.error||`HTTP ${r.status}`);return data;}
function populate(value){
 for(const el of fields()){
  const v=el.name.startsWith('sensor:')?value.sensors[el.name.slice(7)]??'':value[el.name];
  if(el.type==='checkbox')el.checked=!!v;else el.value=v??'';
  el.disabled=!canEdit;
 }
 renderFormula();document.getElementById('brightness-value').value=form.elements.brightness.value+'%';
}
function collect(){
 const next=structuredClone(config);next.sensors=structuredClone(config.sensors);
 for(const el of fields()){
  if(el.name.startsWith('sensor:')){if(el.value)next.sensors[el.name.slice(7)]=el.value;else delete next.sensors[el.name.slice(7)];}
  else next[el.name]=el.type==='checkbox'?el.checked:el.type==='number'||el.type==='range'?Number(el.value):el.value;
 }
 return next;
}
function option(select,value,label){select.append(new Option(label,value));}
function sensorControls(){
 const current=config?collect():null;
 for(const [id,filter,label] of [['cpuDevice',d=>d.type==='Cpu','自动选择'],['gpuDevice',d=>d.type.startsWith('Gpu'),'自动选择独立显卡']]){
  const select=document.getElementById(id);select.replaceChildren();option(select,'',label);
  hardware.filter(filter).forEach(d=>option(select,d.id,d.name));
  const selected=current?.[id]??config?.[id];if(selected&&!hardware.some(d=>d.id===selected))option(select,selected,'当前绑定设备（未发现）');
 }
 const container=document.getElementById('sensor-mappings');container.replaceChildren();
 const sensors=hardware.flatMap(d=>(d.sensors??[]).map(s=>({...s,device:d.name,hardwareType:d.type})));
 for(const [key,label] of Object.entries(mappingLabels)){
  const row=node('div',undefined,'field'),select=node('select');select.name='sensor:'+key;select.id='map-'+key.replace('.','-');
  const title=node('label',label);title.htmlFor=select.id;row.append(title,select);option(select,'',autoSources[key]??'自动选择');
  const type=mappingTypes[key];
  const compatible=s=>key.startsWith('cpu.')?['Cpu','Motherboard','SuperIO'].includes(s.hardwareType):key.startsWith('gpu.')?s.hardwareType.startsWith('Gpu'):s.hardwareType!=='Cpu'&&!s.hardwareType.startsWith('Gpu');
  for(const sensor of sensors.filter(s=>s.type===type&&compatible(s)))option(select,sensor.id,`${sensor.device} · ${sensor.name} · ${sensor.value===null?'不可用':fmt(sensor.value,sensor.type==='Voltage'?3:1)+' '+(units[sensor.type]??'')}`);
  const chosen=current?.sensors[key]??config?.sensors[key];if(chosen&&!sensors.some(s=>s.id===chosen))option(select,chosen,'当前绑定传感器（未发现）');
  container.append(row);
 }
 const catalog=document.getElementById('sensor-catalog');catalog.replaceChildren();
 if(!sensors.length)catalog.append(node('p','暂无传感器。请安装硬件库或检查采集进程。'));
 for(const device of hardware){
  const table=node('table'),head=node('thead'),headRow=node('tr');headRow.append(node('th',device.name),node('th','类型'),node('th','读数'));head.append(headRow);table.append(head);
  const body=node('tbody');
  for(const sensor of device.sensors??[]){const row=node('tr');if(sensor.value===null)row.className='unavailable';row.append(node('td',sensor.name),node('td',sensor.type),node('td',sensor.value===null?'不可用':fmt(sensor.value,sensor.type==='Voltage'?3:1)+' '+(units[sensor.type]??'')));body.append(row);}
  table.append(body);catalog.append(table);
 }
 if(current)populate(current);
}
function renderFormula(){
 const mode=form.elements.powerMode.value,base=form.elements.basePowerW.value,eff=form.elements.psuEfficiency.value;
 document.getElementById('efficiency-field').hidden=mode!=='wall';
 document.getElementById('formula').textContent=mode==='measured'?'POWER METER → SYSTEM POWER':mode==='wall'?`(CPU + GPU + ${base} W) ÷ ${eff}%`:`CPU + GPU + ${base} W`;
}
async function loadSensors(){
 const result=await request('/api/sensors');hardware=result.hardware;mappingTypes=result.mappingTypes;sensorControls();
}
function telemetry(packet){
 if(!packet)return;
 const parent=document.getElementById('readings');parent.replaceChildren();
 for(const [name,unit,values] of [
  ['CPU',packet.cpu,[`使用率 ${fmt(packet.cpu.usage)}%`,`${fmt((packet.cpu.frequencyMhz??NaN)/1000,2)} GHz · ${fmt(packet.cpu.voltageV,2)} V`,`${fmt(packet.cpu.powerW)} W`]],
  ['GPU',packet.gpu,[`使用率 ${fmt(packet.gpu.usage)}%`,`${fmt(packet.gpu.frequencyMhz)} MHz · ${fmt(packet.gpu.voltageV,2)} V`,`${fmt(packet.gpu.powerW)} W`]],
  ['MEMORY',packet.memory,[`${fmt(packet.memory.usedGb,1)} / ${fmt(packet.memory.totalGb,1)} GB`,`整机 ${fmt(packet.systemPowerW)} W`,packet.demo?'DEMO':'LIVE']]]){
   const card=node('div',undefined,'reading');card.append(node('small',name),node('strong',fmt(unit.usage)+'%'));
   (name==='MEMORY'?[values[0],values[1]]:values.slice(1)).forEach(v=>card.append(node('span',v)));card.title=unit.name??values[0];
   parent.append(card);
 }
 const issues=document.getElementById('issues');issues.replaceChildren();packet.issues.forEach(message=>issues.append(node('p',message,'issue')));
 for(const [key,label] of [['voltageV','CPU 电压'],['usage','CPU 占用率'],['powerW','CPU 功耗']]){
  const source=packet.cpu.sensorSources?.[key];
  if(source)issues.append(node('p',`${label}来源：${source.device?source.device+' · ':''}${source.name}（${source.provider}）${source.calibration?' · 已应用此主板 Vcore 换算':''}`));
 }
 const state=document.getElementById('service-state');state.textContent=packet.demo?'● 演示模式':'● 本地采集中';
}
form.addEventListener('input',()=>{status('有未保存的修改','dirty');renderFormula();document.getElementById('brightness-value').value=form.elements.brightness.value+'%';});
form.addEventListener('submit',async event=>{
 event.preventDefault();if(!canEdit)return;
 const button=document.getElementById('save');button.disabled=true;
 try{
  const result=await request('/api/config',{method:'POST',headers:{'Content-Type':'application/json','X-WebOBS-Token':token},body:JSON.stringify(collect())});
  config=result.config;populate(config);status(result.restartRequired?'已保存 · 部分参数需要重启程序':'已保存 · 参数已实时生效','saved');
  document.getElementById('save-detail').textContent=result.restartRequired?'重启程序以应用网络或采集授权设置':'保存在本机 config.json';
 }catch(error){status(error.message,'error');}finally{button.disabled=!canEdit;}
});
document.getElementById('refresh-sensors').addEventListener('click',()=>loadSensors().catch(error=>status(error.message,'error')));
document.getElementById('reset').addEventListener('click',()=>{if(defaults){populate(defaults);status('已恢复默认值，点击保存配置生效','dirty');}});
for(const button of document.querySelectorAll('[data-preset]'))button.addEventListener('click',()=>{
 const presets={eco:{sampleIntervalMs:2000,sensorIntervalMs:3000},balanced:{sampleIntervalMs:1000,sensorIntervalMs:1500},smooth:{sampleIntervalMs:500,sensorIntervalMs:1000}};
 const value=collect();Object.assign(value,presets[button.dataset.preset]);populate(value);document.querySelectorAll('[data-preset]').forEach(b=>b.classList.toggle('selected',b===button));status('性能预设已选择，点击保存生效','dirty');
});
async function initialize(){
 try{
  const result=await request('/api/config');config=result.config;token=result.token;canEdit=result.canEdit;defaults=result.defaults;
  populate(config);await loadSensors();
  document.getElementById('read-only').hidden=canEdit;
  document.getElementById('save').disabled=!canEdit;document.getElementById('reset').disabled=!canEdit;
  status(canEdit?'配置已加载':'局域网访问 · 只读');
  const health=await request('/api/health'),links=document.getElementById('lan-links');
  const port=health.port;for(const ip of health.addresses){const a=node('a',`http://${ip}:${port}`);a.href=`http://${ip}:${port}`;links.append(a);}
  document.getElementById('read-only').textContent=`当前通过局域网访问，配置为只读。请在运行程序的电脑上打开 http://localhost:${port}/settings 修改参数。`;
  const events=new EventSource('/api/events');events.onmessage=e=>{try{telemetry(JSON.parse(e.data));}catch(error){console.error(error);}};
  events.onerror=()=>{document.getElementById('service-state').textContent='● 服务已断开';};
  telemetry(await request('/api/telemetry'));
 }catch(error){status(error.message,'error');document.getElementById('service-state').textContent='● 连接失败';}
}
initialize();
