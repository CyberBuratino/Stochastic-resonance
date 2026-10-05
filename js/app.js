/* Offline UI: no imports, fetches or server dependency. */
'use strict';
const $=id=>document.getElementById(id);
const ru={
  "brand": "Стохастический резонанс",
  "home": "Главная",
  "lab": "Демонстрация",
  "theory": "Теория по теме",
  "authors": "Авторы",
  "exit": "Выход",
  "title": "Стохастический<br>резонанс",
  "experiment": "01 / ЧИСЛЕННЫЙ ЭКСПЕРИМЕНТ",
  "labTitle": "Тепловое движение в потенциале",
  "parameters": "Параметры системы",
  "driveToggle": "Периодическая сила",
  "seed": "Зерно генератора",
  "resetHint": "Изменение параметров начинает новую реализацию с тем же зерном.",
  "weak": "Низкая T",
  "medium": "Средняя T",
  "strong": "Высокая T",
  "speed": "Темп показа",
  "slow": "Медленно ×1",
  "fast": "Быстро ×15",
  "start": "Старт",
  "pause": "Пауза",
  "stop": "Стоп",
  "export": "Скачать траекторию CSV ↓",
  "potential": "Частица в потенциале",
  "transitions": "Переходы",
  "trajectory": "Траектория и внешняя сила",
  "theoryHeading": "ОТ НАБЛЮДЕНИЯ К МОДЕЛИ",
  "project": "УЧЕБНЫЙ ПРОЕКТ",
  "authorName": "Капитонов Станислав · Корж Евгения",
  "authorDetails": "ВМК МГУ — факультет вычислительной математики и кибернетики.",
  "supervisor": "Преподаватель: Чичигина Ольга Александровна."
};
const en={
  "brand": "Stochastic resonance",
  "home": "Home",
  "lab": "Demonstration",
  "theory": "Theory",
  "authors": "Authors",
  "exit": "Exit",
  "title": "Stochastic<br>resonance",
  "experiment": "01 / NUMERICAL EXPERIMENT",
  "labTitle": "Thermal motion in a potential",
  "parameters": "System parameters",
  "driveToggle": "Periodic force",
  "seed": "Random seed",
  "resetHint": "Changing a parameter starts a new realization with the same seed.",
  "weak": "Low T",
  "medium": "Medium T",
  "strong": "High T",
  "speed": "Playback speed",
  "slow": "Slow ×1",
  "fast": "Fast ×15",
  "start": "Start",
  "pause": "Pause",
  "stop": "Stop",
  "export": "Download trajectory CSV ↓",
  "potential": "Particle in the potential",
  "transitions": "Transitions",
  "trajectory": "Trajectory and driving force",
  "theoryHeading": "FROM OBSERVATION TO MODEL",
  "project": "STUDENT PROJECT",
  "authorName": "Stanislav Kapitonov · Evgeniya Korzh",
  "authorDetails": "CMC MSU — Faculty of Computational Mathematics and Cybernetics.",
  "supervisor": "Teacher: Olga Alexandrovna Chichigina."
};
let lang='ru',p={...Physics.defaults},model=new Physics.Model(p),running=false,vertical=true,history=[],noticeKey='';
const text=(a,b)=>lang==='ru'?a:b;
function translate(){$('facultyLogo').alt=text('Логотип ВМК МГУ','CMC MSU logo');document.documentElement.lang=lang;document.title=text('Стохастический резонанс · Лаборатория','Stochastic resonance · Lab');document.querySelectorAll('[data-i18n]').forEach(e=>e.innerHTML=(lang==='ru'?ru:en)[e.dataset.i18n]);$('language').textContent=lang==='ru'?'EN':'RU';$('theoryContent').innerHTML=theory(lang);renderControls();updateStatus();updateNotice();updatePhysicsInfo();draw();}
const labels={T:['Температура T','Temperature T'],a:['Коэффициент a','Coefficient a'],b:['Коэффициент b','Coefficient b'],f:['Амплитуда силы f','Force amplitude f'],omega:['Частота ω','Angular frequency ω'],gamma:['Трение γ','Damping γ']};
function renderControls(){ $('parameters').innerHTML=''; for(const [k,[r,e]] of Object.entries(labels)){const [min,max]=Physics.limits[k], step=k==='omega'?.005:.01;const div=document.createElement('div');div.className='parameter';div.innerHTML=`<label for="n-${k}">${lang==='ru'?r:e}<input id="n-${k}" type="number" min="${min}" max="${max}" step="${step}" value="${p[k]}"></label><input id="r-${k}" type="range" aria-label="${lang==='ru'?r:e}" min="${min}" max="${max}" step="${step}" value="${p[k]}">`;$('parameters').append(div);['n-','r-'].forEach(prefix=>$(prefix+k).addEventListener('change',event=>{const v=event.target.valueAsNumber;if(!Number.isFinite(v)||v<min||v>max){noticeKey='invalid';updateNotice();renderControls();updatePhysicsInfo();return;}try{Physics.validate({...p,[k]:v});}catch(e){noticeKey='shape';updateNotice();renderControls();updatePhysicsInfo();return;}p[k]=v;reset();renderControls();updatePhysicsInfo();}));}}
function updateNotice(){$('notice').textContent=noticeKey==='shape'?text('При a > 0 коэффициент b должен быть положительным. Для плоского потенциала сначала установите a = 0.','When a > 0, b must be positive. Set a = 0 first for a flat potential.'):noticeKey==='invalid'?text('Введите число в указанном диапазоне.','Enter a number within the allowed range.'):noticeKey==='exit'?text('Расчёт остановлен. Чтобы выйти, закройте вкладку браузера.','Simulation stopped. Close this browser tab to exit.'):noticeKey==='error'?text('Расчёт прерван из-за численной ошибки. Нажмите «Стоп».','Numerical error. Press Stop to reset.') :'';}
function updateStatus(){$('status').textContent=running?text('● Расчёт идёт','● Running'):model.t?text('Ⅱ Пауза','Ⅱ Paused'):text('○ Готов к запуску','○ Ready');$('pause').disabled=!running;}
function reset(){model=new Physics.Model(p);history=[{t:0,x:model.x,v:0,drive:0}];noticeKey='';updateStatus();updateNotice();updatePhysicsInfo();draw();}
function route(){const hash=location.hash.slice(1),id=['home','lab','theory','authors'].includes(hash)?hash:'home';document.querySelectorAll('.page').forEach(e=>e.hidden=e.id!==id);document.querySelectorAll('nav a').forEach(e=>e.classList.toggle('active',e.hash==='#'+id));document.body.classList.toggle('home-page',id==='home');if(id!=='lab'){running=false;updateStatus();}draw();}
$('language').onclick=()=>{lang=lang==='ru'?'en':'ru';translate();};
$('start').onclick=()=>{running=true;updateStatus();};$('pause').onclick=()=>{running=false;updateStatus();};$('stop').onclick=()=>{running=false;reset();};
$('exit').onclick=()=>{running=false;location.hash='home';noticeKey='exit';updateNotice();alert(text('Расчёт остановлен. Закройте вкладку браузера для выхода.','Simulation stopped. Close the browser tab to exit.'));};
$('seed').onchange=()=>{const v=$('seed').valueAsNumber;if(!Number.isInteger(v)||v<0||v>4294967295){$('seed').value=p.seed;noticeKey='invalid';updateNotice();return;}p.seed=v;reset();};
document.querySelectorAll('[data-preset]').forEach(b=>b.onclick=()=>{p.T=Number(b.dataset.preset);reset();renderControls();updatePhysicsInfo();});
window.addEventListener('hashchange',route);window.addEventListener('resize',draw);
// Canvas plots use CSS size and device pixel ratio; axes always carry numeric ticks.
function chart(id,xmin,xmax,ymin,ymax,xlabel,ylabel,right,plotTop=28){const canvas=$(id),w=canvas.clientWidth,h=canvas.clientHeight;if(!w||!h)return null;const dpr=window.devicePixelRatio||1;canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);const c=canvas.getContext('2d');c.scale(dpr,dpr);const left=58,top=plotTop,bottom=h-43,r=w-(right?65:22),X=x=>left+(x-xmin)/(xmax-xmin)*(r-left),Y=y=>bottom-(y-ymin)/(ymax-ymin)*(bottom-top);c.font='13px system-ui';c.lineWidth=1;for(let i=0;i<=4;i++){const x=xmin+(xmax-xmin)*i/4,y=ymin+(ymax-ymin)*i/4;c.strokeStyle='#293b4d';c.beginPath();c.moveTo(X(x),top);c.lineTo(X(x),bottom);c.moveTo(left,Y(y));c.lineTo(r,Y(y));c.stroke();c.fillStyle='#b2c4d4';c.textAlign='center';c.fillText(format(x),X(x),bottom+21);c.textAlign='right';c.fillText(format(y),left-9,Y(y)+4);if(right){c.textAlign='left';c.fillStyle='#ffb56b';c.fillText(format(right[0]+(right[1]-right[0])*i/4),r+9,Y(y)+4);}}c.fillStyle='#cbd9e5';c.textAlign='left';c.fillText(ylabel,4,17);c.textAlign='right';c.fillText(xlabel,r,h-3);if(right){c.fillStyle='#ffb56b';c.fillText('F [1]',w-3,17);}return {c,X,Y,left,top,right:r,bottom};}
function format(n){return Math.abs(n)>=100?n.toFixed(0):Number(n.toFixed(2)).toString();}
function line(g,points,color,width=2){const {c,X,Y}=g;c.save();c.beginPath();c.rect(g.left,g.top,g.right-g.left,g.bottom-g.top);c.clip();c.strokeStyle=color;c.lineWidth=width;c.beginPath();points.forEach(([x,y],i)=>i?c.lineTo(X(x),Y(y)):c.moveTo(X(x),Y(y)));c.stroke();c.restore();}
function updatePhysicsInfo(){
  $('driveEnabled').checked=p.driveEnabled;
  for(const k of ['f','omega'])for(const prefix of ['n-','r-'])if($(prefix+k))$(prefix+k).disabled=!p.driveEnabled;
  $('thermalInfo').textContent=text('Приведённая температура, kB = 1. Интенсивность шума D = γT = ','Reduced temperature, kB = 1. Noise intensity D = γT = ')+Physics.noiseIntensity(p).toFixed(3);
  const barrier=Physics.barrier(p),fc=Physics.criticalForce(p);
  $('shapeInfo').textContent=p.a>0?text('Барьер ΔU = ','Barrier ΔU = ')+barrier.toFixed(3)+text('; порог силы fc = ','; force threshold fc = ')+fc.toFixed(3):text(p.b?'Одна яма; межъямных переходов нет.':'Плоский потенциал; межъямных переходов нет.',p.b?'Single well; no interwell transitions.':'Flat potential; no interwell transitions.');
  $('rotate').textContent=vertical?text('Повернуть график: время вправо ↻','Rotate graph: time to the right ↻'):text('Повернуть график: время вверх ↻','Rotate graph: time upward ↻');
  $('rotate').setAttribute('aria-pressed',String(vertical));
  $('trajectory').dataset.orientation=vertical?'vertical':'horizontal';
  $('axesHint').textContent=vertical?text('Время — вверх, координата — вправо. Верхняя шкала — сила F. Последние 3 периода; все величины безразмерные.','Time increases upward, position to the right. Top scale: force F. Last 3 periods; all quantities dimensionless.'):text('Время — вправо. Координата — левая ось, сила — правая. Последние 3 периода; все величины безразмерные.','Time increases to the right. Position: left axis; force: right axis. Last 3 periods; all quantities dimensionless.');

}
$('driveEnabled').onchange=()=>{p.driveEnabled=$('driveEnabled').checked;reset();renderControls();updatePhysicsInfo();};
$('rotate').onclick=()=>{vertical=!vertical;updatePhysicsInfo();draw();};
function draw(){
  if($('lab').hidden)return;
  const center=Physics.wellPosition(p),F=Physics.drive(model.t,p);
  // Same horizontal range and canvas margins connect particle and vertical trace.
  const extent=Math.max(1.5,1.85*center,Math.abs(model.x)*1.12,...history.map(v=>Math.abs(v.x)*1.12));
  const effective=x=>Physics.potential(x,p)-x*F;
  const samples=Array.from({length:301},(_,i)=>{const x=-extent+2*extent*i/300;return [x,effective(x)];});
  const low=Math.min(-.1,...samples.map(v=>v[1]));
  const high=Math.max(.5,Physics.barrier(p)*1.2,effective(model.x)+.3);
  let g=chart('potential',-extent,extent,low-.15*(high-low),high,'x [1]','Ueff [1]',null,65);
  if(g){
    line(g,samples,'#49e2bc',3);
    const {c,X}=g,track=30;
    c.strokeStyle='#9fb3c6';c.lineWidth=1.5;c.beginPath();c.moveTo(g.left,track);c.lineTo(g.right,track);c.stroke();
    c.setLineDash([4,5]);c.beginPath();c.moveTo(X(model.x),track);c.lineTo(X(model.x),g.Y(effective(model.x)));c.stroke();c.setLineDash([]);
    c.fillStyle='#ffb56b';c.beginPath();c.arc(X(model.x),track,8,0,2*Math.PI);c.fill();
  }
  const windowSize=6*Math.PI/p.omega,start=Math.max(0,model.t-windowSize),end=Math.max(model.t,p.dt);
  const scaleF=Math.max(p.f,.01);
  if(vertical){
    g=chart('trajectory',-extent,extent,start,end,'x [1]','t [1]',null,65);
    if(g){
      line(g,history.map(v=>[v.x,v.t]),'#49e2bc',2.5);
      if(p.driveEnabled)line(g,history.map(v=>[v.drive/scaleF*extent,v.t]),'#ffb56b',2);
      const {c,X}=g;c.fillStyle='#ffb56b';c.textAlign='right';c.fillText('F [1]',g.right,16);
      for(let i=0;i<=4;i++){c.textAlign='center';c.fillText(format(-scaleF+2*scaleF*i/4),X(-extent+2*extent*i/4),45);}
    }
  }else{
    g=chart('trajectory',start,end,-extent,extent,'t [1]','x [1]',[-scaleF,scaleF]);
    if(g){line(g,history.map(v=>[v.t,v.x]),'#49e2bc',2.5);if(p.driveEnabled)line(g,history.map(v=>[v.t,v.drive/scaleF*extent]),'#ffb56b',2);}
  }
  $('time').textContent=model.t.toFixed(1);$('position').textContent=model.x.toFixed(2);$('transitions').textContent=p.a>0?model.transitions:'—';
}
let previous=0,accumulated=0;
function frame(now){const elapsed=Math.min((now-previous)/1000,.1);previous=now;if(running&&!document.hidden){accumulated+=elapsed*Number($('speed').value);const steps=Math.floor(accumulated);accumulated-=steps;try{for(let i=0;i<steps;i++){model.step();if(model.steps%5===0)history.push({t:model.t,x:model.x,v:model.v,drive:Physics.drive(model.t,p)});}const cutoff=model.t-6*Math.PI/p.omega;while(history.length&&history[0].t<cutoff)history.shift();}catch(e){running=false;noticeKey='error';updateNotice();updateStatus();}draw();}requestAnimationFrame(frame);}
function download(name,data){const url=URL.createObjectURL(new Blob(['\uFEFF'+data],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function metadata(params){return '# model: inertial Langevin; covariance=2gammaT delta; D=gamma*T; dimensionless\n'+Object.entries({...params,D:Physics.noiseIntensity(params)}).map(([k,v])=>'# '+k+'='+v).join('\n')+'\n';}
$('export').onclick=()=>download('trajectory.csv',metadata(p)+'t,x,v,force\n'+history.map(v=>[v.t,v.x,v.v,v.drive].join(',')).join('\n'));
reset();translate();route();requestAnimationFrame(frame);
