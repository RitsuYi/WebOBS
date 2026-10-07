"use strict";
const svg = document.getElementById("cluster");
const polar = (cx, cy, r, angle) => {const a = angle * Math.PI / 180;return [cx + r * Math.sin(a), cy - r * Math.cos(a)];};
const point = p => p.map(n => n.toFixed(2)).join(" ");
const arc = (cx, cy, r, start, end) => `M ${point(polar(cx,cy,r,start))} A ${r} ${r} 0 ${end-start>180?1:0} 1 ${point(polar(cx,cy,r,end))}`;
const line = (a,b,attrs="") => `<path d="M ${point(a)} L ${point(b)}" ${attrs}/>`;
const text = (x,y,content,attrs="") => `<text x="${x}" y="${y}" ${attrs}>${content}</text>`;
// Each full dial is drawn in the reference image's 654-unit coordinate space.
const DIAL = {cy:332, radius:264, faceRadius:327, start:-132, sweep:264};
const VOLTAGE_MAX = 2;
const dialAngle = percent => DIAL.start + Math.max(0,Math.min(100,percent))*DIAL.sweep/100;
const defs = `<defs>
 <radialGradient id="sky"><stop stop-color="#073286"/><stop offset=".43" stop-color="#021844"/><stop offset="1" stop-color="#000207"/></radialGradient>
 <linearGradient id="horizon" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#0958d4" stop-opacity="0"/><stop offset=".55" stop-color="#226ce8" stop-opacity=".8"/><stop offset=".72" stop-color="#327ded" stop-opacity=".9"/><stop offset="1" stop-color="#001841" stop-opacity="0"/></linearGradient>
 <linearGradient id="floor" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#023277"/><stop offset=".5" stop-color="#010e2a"/><stop offset="1" stop-color="#000104"/></linearGradient>
 <linearGradient id="metal" x1="0" y1="0" x2=".3" y2="1"><stop stop-color="#d1d2dc"/><stop offset=".3" stop-color="#b9b9cf"/><stop offset=".55" stop-color="#787797"/><stop offset=".8" stop-color="#464563"/><stop offset="1" stop-color="#171c35"/></linearGradient>
 <radialGradient id="dial-haze" cx="95%" cy="56%" r="72%"><stop stop-color="#172040"/><stop offset=".5" stop-color="#030610"/><stop offset="1" stop-color="#000"/></radialGradient>
 <linearGradient id="dial-floor"><stop stop-color="#000"/><stop offset=".42" stop-color="#040519"/><stop offset=".72" stop-color="#0c103a"/><stop offset="1" stop-color="#131d51"/></linearGradient>
 <radialGradient id="spoke-fade" gradientUnits="userSpaceOnUse" cx="0" cy="0" r="327"><stop offset=".35" stop-color="#232327" stop-opacity="0"/><stop offset=".55" stop-color="#24252e" stop-opacity=".08"/><stop offset="1" stop-color="#51515b" stop-opacity=".42"/></radialGradient>
 <radialGradient id="needle-flare"><stop stop-color="#fff"/><stop offset=".12" stop-color="#fff5ff" stop-opacity=".9"/><stop offset=".35" stop-color="#e4a3bd" stop-opacity=".4"/><stop offset="1" stop-color="#b23b65" stop-opacity="0"/></radialGradient>
 <linearGradient id="needle-rim"><stop stop-color="#f86596" stop-opacity="0"/><stop offset=".5" stop-color="#e54177" stop-opacity=".85"/><stop offset="1" stop-color="#ad194f" stop-opacity="0"/></linearGradient>
 <linearGradient id="panel" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#021027"/><stop offset=".5" stop-color="#00050d"/><stop offset="1" stop-color="#000207"/></linearGradient>
 <linearGradient id="flare"><stop stop-color="#008fff" stop-opacity="0"/><stop offset=".45" stop-color="#147cff" stop-opacity=".6"/><stop offset=".5" stop-color="#b8efff"/><stop offset=".55" stop-color="#147cff" stop-opacity=".6"/><stop offset="1" stop-color="#008fff" stop-opacity="0"/></linearGradient>
 <linearGradient id="power-ring"><stop stop-color="#edf8ff"/><stop offset=".45" stop-color="#afc9ee"/><stop offset=".8" stop-color="#7792bf"/><stop offset="1" stop-color="#d6e8ff"/></linearGradient>
 <linearGradient id="needle" x1="0" y1="1" x2="0" y2="0"><stop stop-color="#871731" stop-opacity=".12"/><stop offset=".35" stop-color="#c64172" stop-opacity=".7"/><stop offset=".82" stop-color="#efa3c0"/><stop offset="1" stop-color="#fff5fd"/></linearGradient>
 <linearGradient id="dot"><stop stop-color="#b4c4ed"/><stop offset="1" stop-color="#50618d"/></linearGradient>
 <linearGradient id="active-dot"><stop stop-color="#fff2fa"/><stop offset=".35" stop-color="#ff1650"/><stop offset="1" stop-color="#b7002c"/></linearGradient>
 <filter id="blue-glow" x="-70%" y="-70%" width="240%" height="240%"><feGaussianBlur stdDeviation="5" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
 <filter id="text-glow" x="-50%" y="-80%" width="200%" height="260%"><feGaussianBlur stdDeviation="2.5" result="blur"/><feFlood flood-color="#7960ff" flood-opacity=".65"/><feComposite in2="blur" operator="in"/><feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>
 <filter id="readout-glow" x="-50%" y="-100%" width="200%" height="300%"><feGaussianBlur stdDeviation="3.2" result="blur"/><feFlood flood-color="#7960ff" flood-opacity=".5"/><feComposite in2="blur" operator="in"/><feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>
 <filter id="needle-glow" x="-150%" y="-30%" width="400%" height="160%"><feGaussianBlur stdDeviation="1.5"/><feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>
 <filter id="rim-glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="2.2"/><feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>
 <filter id="soft"><feGaussianBlur stdDeviation="13"/></filter>
 <clipPath id="floor-clip"><path d="M 240 354 H 1808 L 2048 740 H 0 Z"/></clipPath>
 <symbol id="cpu-icon" viewBox="0 0 60 60"><g fill="none" stroke="#70cfff" stroke-width="3"><rect x="13" y="13" width="34" height="34" rx="3"/><rect x="20" y="20" width="20" height="20" stroke-width="2"/><path d="M20 6v7m10-7v7m10-7v7M20 47v7m10-7v7m10-7v7M6 20h7m-7 10h7m-7 10h7M47 20h7m-7 10h7m-7 10h7"/></g></symbol>
 <symbol id="gpu-icon" viewBox="0 0 64 50"><g fill="none" stroke="#76ccff" stroke-width="3"><path d="M4 4v34h8m-4-28h51v26H9m8 6h33m-7-6v6"/><circle cx="24" cy="23" r="8"/><circle cx="44" cy="23" r="8"/><circle cx="24" cy="23" r="3"/><circle cx="44" cy="23" r="3"/><path d="m24 15 3 5-5 6m22-11 3 5-5 6" stroke-width="2"/></g></symbol>
 <symbol id="power-icon" viewBox="0 0 38 58"><path d="m26 0-23 31h12L8 58l27-35H22Z" fill="#72caff"/></symbol>
 <symbol id="temperature-icon" viewBox="0 0 40 40"><path d="M15 3v20a7 7 0 1 0 8 0V3a4 4 0 0 0-8 0Zm4 8v18m8-18h7m-7 7h5M1 36q5-5 10 0t10 0t10 0t8 0" fill="none" stroke="#77cdff" stroke-width="2.8"/></symbol>
</defs>`;

function background(){
 let grid="";
 for(let i=-13;i<=13;i++) grid+=line([1024+i*28,354],[1024+i*210,740],`stroke="#075ac7" stroke-width=".8" opacity="${Math.abs(i)>10?.18:.48}"`);
 for(let i=0;i<18;i++){const y=354+Math.pow(i/17,2.25)*385;grid+=line([0,y],[2048,y],`stroke="#0873e5" stroke-width=".7" opacity="${.55-i*.017}"`);}
 return `<rect width="2048" height="768" fill="#000"/><rect x="20" y="4" width="2008" height="620" fill="url(#sky)"/>
 <path d="M 480 144 672 116 789 176 916 143 1014 188 1122 144 1282 188 1410 108 1540 155V354H480Z" fill="#030d27" opacity=".7"/>
 <rect x="600" y="158" width="848" height="220" fill="url(#horizon)"/>
 <path d="M510 309 654 302 795 331 907 310 1010 333 1098 317 1210 336 1344 306 1485 318 1576 341V368H490Z" fill="#020d24"/>
 <path d="M700 347 829 326 936 345 1027 335 1188 346 1334 323 1440 348V372H700Z" fill="#021538"/>
 <path d="M240 354H1808L2048 740H0Z" fill="url(#floor)"/>
 <g clip-path="url(#floor-clip)">${grid}</g>
 <ellipse cx="1024" cy="360" rx="450" ry="6" fill="#0075ff" opacity=".4" filter="url(#soft)"/>
 <rect x="647" y="241" width="235" height="9" fill="url(#flare)" filter="url(#blue-glow)"/>
 <rect x="1165" y="241" width="233" height="9" fill="url(#flare)" filter="url(#blue-glow)"/>
 <rect x="-30" y="183" width="230" height="3" fill="url(#flare)" filter="url(#blue-glow)"/>
 <rect x="1850" y="183" width="230" height="3" fill="url(#flare)" filter="url(#blue-glow)"/>
 <rect x="-26" y="532" width="207" height="3" fill="url(#flare)" filter="url(#blue-glow)"/>
 <rect x="1867" y="532" width="207" height="3" fill="url(#flare)" filter="url(#blue-glow)"/>
 <path d="M0 688 330 684 517 737 863 690H1180L1530 747 1740 690H2048M495 767 810 696H1240L1550 767" fill="none" stroke="#064582" opacity=".22"/>
 <path d="M28 0V36L40 49H562Q575 48 591 30L603 21Q611 15 625 15H1424Q1437 15 1448 25L1470 41Q1482 49 1496 49H2008L2020 37V0" fill="#00050d" stroke="#0868bc" stroke-width=".8"/>
 <rect x="773" y="10" width="500" height="5" fill="url(#flare)" opacity=".45" filter="url(#blue-glow)"/>
 <path d="M28 53 40 62H2020" fill="none" stroke="#033261" opacity=".4"/>
 <g stroke="#80d7ff" stroke-width="1.7" fill="none"><rect x="60" y="11" width="19" height="12"/><path d="M69.5 23v4M58 29h24"/><rect x="52" y="28" width="14" height="12" fill="#8bd7ff"/><rect x="73" y="28" width="14" height="12" fill="#8bd7ff"/><circle cx="59" cy="34" r="2" fill="#002257" stroke="none"/><circle cx="80" cy="34" r="2" fill="#002257" stroke="none"/></g>
 ${text(112,35,"LAN MONITOR",'class="blue-label" font-size="22"')}
 ${text(275,35,"CONNECTING",'id="address" class="blue-label" font-size="22"')}
 <circle cx="450" cy="28" r="6.8" fill="#1bd989" id="online-dot"/>
 ${text(468,35,"CONNECTING",'id="online" font-size="22" fill="#39dfa4"')}
 ${text(1888,35,"",'id="date" text-anchor="end" class="blue-label" font-size="22"')}
 ${text(1992,35,"",'id="clock" text-anchor="end" class="blue-label" font-size="22"')}`;
}

function dial(cx,id,majorCount,maxLabel){
 let spokes="",ticks="",labels="",floor="";
 for(let i=0;i<=108;i++){
  const angle=DIAL.start+i*DIAL.sweep/108;
  spokes+=line(polar(0,0,115,angle),polar(0,0,314,angle),'stroke="url(#spoke-fade)" stroke-width="2"');
 }
 // The reference has bright block ticks and dark radial hairlines, without a second tick ring.
 for(let i=0;i<=majorCount*2;i++){
  const major=i%2===0,angle=DIAL.start+i*DIAL.sweep/(majorCount*2);
  const width=major?8:7;
  // A filled rectangle gives the vertical top tick a nonzero, small filter box.
  ticks+=angle===0?`<rect x="${-width/2}" y="-309" width="${width}" height="${major?27:15}" fill="#fcfaff" filter="url(#text-glow)"/>`:
   line(polar(0,0,309,angle),polar(0,0,major?282:294,angle),`stroke="#fcfaff" stroke-width="${width}" filter="url(#text-glow)"`);
 }
 for(let i=0;i<=majorCount;i++){
  const p=polar(0,0,253,DIAL.start+i*DIAL.sweep/majorCount);
  const label=String(Math.round(i*maxLabel/majorCount)),size=i===0?50:43;
  const width=label.length===1?(i===0?30:27):label.length===2?56:79;
  labels+=text(p[0],p[1]+(i===0?18:14),label,`class="number" text-anchor="middle" font-size="${size}" textLength="${width}" lengthAdjust="spacingAndGlyphs"`);
 }
 for(let i=0;i<12;i++){
  const y=-10+Math.pow(i/11,2)*340;
  floor+=line([-330,y],[330,y],'stroke="#6670a5" stroke-width=".7" opacity=".08"');
 }
 for(let i=-5;i<=8;i++)floor+=line([0,-10],[i*102,330],'stroke="#6670a5" stroke-width=".7" opacity=".08"');
 const lowerScale=`M ${point(polar(0,0,319,212))} A 319 319 0 0 0 ${point(polar(0,0,319,148))}`;
 return `<g id="${id}-dial" transform="translate(${cx} ${DIAL.cy}) scale(${DIAL.radius/DIAL.faceRadius})">
 <defs><clipPath id="${id}-face-clip"><circle r="319"/></clipPath></defs>
 <circle r="327" fill="#000" stroke="#211e42" stroke-width="2"/>
 <circle r="324" fill="none" stroke="#5d4ed5" stroke-width="3" opacity=".64" filter="url(#rim-glow)"/>
 <circle r="321" fill="none" stroke="url(#metal)" stroke-width="7.5"/>
 <g clip-path="url(#${id}-face-clip)">
  <circle r="318" fill="url(#dial-haze)"/>
  <path d="M-325-42-204-45-95-43 32-57 92-58 145-49 180-53 240-46 325-25V-10H-325Z" fill="#000"/>
  <path d="M-325-10H325V330H-325Z" fill="url(#dial-floor)"/>
  ${floor}${spokes}
  <path id="${id}-zone-shadow" d="${arc(0,0,302,100,132)}" fill="none" stroke="#b72b55" stroke-width="20" opacity=".09" filter="url(#soft)"/>
  <path id="${id}-zone" d="${arc(0,0,304,100,132)}" fill="none" stroke="#a62a49" stroke-width="5" opacity=".5"/>
  ${ticks}${labels}
  <g id="${id}-needle" transform="rotate(${DIAL.start})" opacity="0">
   <path d="${arc(0,0,319,-12,12)}" fill="none" stroke="url(#needle-rim)" stroke-width="8" filter="url(#rim-glow)"/>
   <path class="needle" d="M0 0-3.1-310 0-321 3.1-310Z" fill="url(#needle)"/>
  </g>
  <g id="${id}-needle-flare" opacity="0">
   <ellipse rx="62" ry="36" fill="url(#needle-flare)" opacity=".65"/>
   <ellipse rx="57" ry="4.5" fill="url(#needle-flare)"/>
   <ellipse rx="8" ry="8" fill="url(#needle-flare)"/>
  </g>
 </g>
 ${text(0,-133,id==='cpu'?'CPU USAGE':'MEMORY USAGE',`id="${id}-label" class="dial-label" font-size="25" text-anchor="middle"`)}
 <text x="0" y="58" text-anchor="middle" class="readout" font-size="100"><tspan id="${id}-usage">—</tspan><tspan font-size="48" dx="3">%</tspan></text>
 ${id==='memory'?text(0,111,"— / — GB",'id="memory-detail" class="value" text-anchor="middle" font-size="28"'):''}
 <path d="${lowerScale}" fill="none" stroke="#41465c" stroke-width="9"/>
 ${id==='memory'?`${text(0,248,"GPU — V",'id="gpu-lower-voltage" class="value" text-anchor="middle" font-size="28"')}
 <path id="gpu-voltage-track" d="${lowerScale}" fill="none" stroke="#e3ddf7" stroke-width="9" pathLength="100" stroke-dasharray="0 100"/>
 ${text(-150,257,"0",'class="number" text-anchor="middle" font-size="28"')}${text(153,257,"2",'class="number" text-anchor="middle" font-size="28"')}`:
 `<path id="cpu-lower-track" d="${lowerScale}" fill="none" stroke="#e3ddf7" stroke-width="9" pathLength="100" stroke-dasharray="0 100"/>${text(0,248,"CPU — V",'id="cpu-lower-voltage" class="value" text-anchor="middle" font-size="28"')}${text(-150,257,"0",'class="number" text-anchor="middle" font-size="28"')}${text(153,257,"2",'class="number" text-anchor="middle" font-size="28"')}`}
 <g id="${id}-lower-ticks">${[148,164,180,196,212].map(a=>line(polar(0,0,312,a),polar(0,0,325,a),'stroke="#03040c" stroke-width="1.5"')).join('')}</g>
 </g>`;
}

function power(){
 return `<g>
 ${text(1024,211,"SYSTEM POWER",'id="center-label" text-anchor="middle" class="label" font-size="23" letter-spacing="4"')}
 <circle cx="1024" cy="362" r="141" fill="#040e24" fill-opacity=".65"/>
 <circle cx="1024" cy="362" r="137" fill="none" stroke="#3869ab" stroke-width="1.5"/>
 <circle cx="1024" cy="362" r="133" fill="none" stroke="url(#power-ring)" stroke-width="3.2" filter="url(#text-glow)"/>
 <circle cx="1024" cy="362" r="127" fill="none" stroke="#285584" stroke-width="1"/>
 <path id="power-track" d="${arc(1024,362,130,-135,135)}" fill="none" stroke="#eff7ff" stroke-width="6" pathLength="100" stroke-dasharray="0 100" filter="url(#text-glow)"/>
 <path d="${arc(1024,362,130,119,133)}" fill="none" stroke="#a4bce0" stroke-width="6"/>
 ${text(1024,380,"—",'id="power-value" class="readout" text-anchor="middle" font-size="61"')}
 ${text(1024,411,"W",'id="power-unit" class="label" text-anchor="middle" font-size="24"')}
 ${text(1024,468,"ESTIMATED",'id="power-source" text-anchor="middle" fill="#95b7d8" font-size="16" letter-spacing="3"')}
 <g color="#b6d4f5"><use href="#power-icon" x="946" y="451" width="12" height="20" opacity=".8"/><use href="#power-icon" x="1090" y="451" width="12" height="20" opacity=".8"/></g>
 <path d="M868 521H1180" stroke="#15417a" opacity=".45"/>
 ${text(1024,549,"PWR",'id="power-formula" text-anchor="middle" fill="#608bb9" font-size="17" letter-spacing="1.4"')}
 </g>`;
}

function footer(){
 return `<g>
 <path d="M63 610H733L750 628V690L733 707H55L42 690V628Z" fill="url(#panel)" stroke="#007acc" stroke-width="1.1"/>
 <path d="M63 610H733L750 628M42 628 63 610" fill="none" stroke="#3dbbff" stroke-width="1"/>
 <path d="M35 635 20 670M757 634 768 669M31 693 50 724H736L756 704" fill="none" stroke="#073160" opacity=".7"/>
 <use href="#cpu-icon" x="86" y="632" width="58" height="58" filter="url(#text-glow)"/>
 ${text(159,670,"CPU",'class="blue-label" font-size="29" font-weight="600"')}
 <path d="M252 626V693M423 626V693M590 626V693" stroke="#164877"/>
 ${text(275,647,"FREQUENCY",'class="blue-label" font-size="19"')}
 ${text(275,682,"— GHz",'id="cpu-frequency" class="value" font-size="29"')}
 ${text(453,647,"VOLTAGE",'class="blue-label" font-size="19"')}
 ${text(453,682,"— V",'id="cpu-voltage" class="value" font-size="29"')}
 ${text(624,647,"POWER",'class="blue-label" font-size="19"')}
 ${text(624,682,"— W",'id="cpu-power" class="value" font-size="29"')}
 <path d="M878 600H1170Q1190 604 1200 621Q1217 646 1197 669L1173 680H876Q844 675 840 647Q837 619 878 600Z" fill="url(#panel)" stroke="#008cfa" stroke-width="1.2"/>
 <ellipse cx="1024" cy="611" rx="120" ry="13" fill="#064bd6" opacity=".4" filter="url(#soft)"/>
 <path d="m884 629-12 11 12 11m280-22 12 11-12 11" fill="none" stroke="#f4f8ff" stroke-width="3" filter="url(#text-glow)"/>
 ${text(1024,638,"Monitor",'id="view-label" class="value" text-anchor="middle" font-size="31" font-weight="600"')}
 ${Array.from({length:6},(_,i)=>`<rect id="view-dot-${i}" x="${904+i*41}" y="658" width="32" height="10" rx="3" fill="${i===3?'url(#active-dot)':'url(#dot)'}"/>`).join('')}
 <rect id="ready-frame" x="964" y="696" width="120" height="41" rx="8" fill="#00100b" stroke="#19ba77" stroke-width="3.2"/>
 ${text(1024,728,"READY",'id="ready" text-anchor="middle" fill="#24c785" font-size="30" font-weight="600"')}
 <path d="M1266 610H1719L1736 628V690L1719 707H1266L1249 690V628Z" fill="url(#panel)" stroke="#007acc" stroke-width="1.1"/>
 <path d="M1266 610H1719L1736 628M1249 628 1266 610" fill="none" stroke="#3dbbff" stroke-width="1"/>
 <path d="M1242 634 1230 670M1742 634 1752 670M1240 696 1260 724H1722L1741 704" fill="none" stroke="#073160" opacity=".7"/>
 <use href="#gpu-icon" x="1280" y="633" width="62" height="44" filter="url(#text-glow)"/>
 ${text(1308,695,"GPU",'class="value" text-anchor="middle" font-size="22"')}
 <path d="M1363 626V693M1506 626V693M1618 626V693" stroke="#164877"/>
 ${text(1382,647,"FREQUENCY",'class="blue-label" font-size="19"')}
 ${text(1382,682,"— MHz",'id="gpu-frequency" class="value" font-size="28"')}
 ${text(1526,647,"VOLTAGE",'class="blue-label" font-size="19"')}
 ${text(1526,682,"— V",'id="gpu-voltage" class="value" font-size="28"')}
 ${text(1638,647,"POWER",'class="blue-label" font-size="19"')}
 ${text(1638,682,"— W",'id="gpu-power" class="value" font-size="28"')}
 <path d="M1790 610H1989L2006 628V690L1989 707H1790L1772 690V628Z" fill="url(#panel)" stroke="#007acc" stroke-width="1.1"/>
 <path d="M1790 610H1989L2006 628M1772 628 1790 610" fill="none" stroke="#3dbbff" stroke-width="1"/>
 <path d="M1765 639V691M2013 636 2028 672M1763 697 1783 724H1992L2013 702" fill="none" stroke="#073160" opacity=".7"/>
 <use href="#temperature-icon" x="1808" y="643" width="45" height="45" filter="url(#text-glow)"/>
 ${text(1870,647,"CPU PWR",'class="blue-label" font-size="19"')}
 ${text(1870,691,"— W",'id="cpu-power-secondary" class="value" font-size="38"')}
 <path d="M1871 699H1987" stroke="#0e2a44" stroke-width="2.5"/>
 <path id="cpu-water-bar" d="M1871 699H1987" stroke="#7fcfff" stroke-width="2.5" pathLength="100" stroke-dasharray="0 100"/>
 </g>
 `;
}

svg.innerHTML=defs+background()+dial(385,'cpu',10,100)+dial(1657,'memory',8,8)+power()+footer();
const nodes=Object.fromEntries([...svg.querySelectorAll('[id]')].map(e=>[e.id,e]));
const textValues=new WeakMap();
function setNodeText(element,value){
 const next=String(value);
 if(textValues.get(element)===next)return;
 textValues.set(element,next);
 const child=element.firstChild;
 // Keep the existing text node: replacing it also rebuilds SVG text layout data.
 if(child&&child.nodeType===3&&!child.nextSibling){if(child.data!==next)child.data=next;}
 else if(element.textContent!==next)element.textContent=next;
}
const setText=(id,value)=>setNodeText(nodes[id],value);
const SVG_NS='http://www.w3.org/2000/svg';
const shell=svg.parentElement;
const accessibleReading=document.getElementById('accessible-reading');
// Changing a descendant can invalidate a large SVG's filtered face in WebKit.
// Keep the detailed face static and give each changing area a bounded SVG.
function positionLayer(element,x,y,width,height){
 element.style.left=`${x/2048*100}%`;element.style.top=`${y/768*100}%`;
 element.style.width=`${width/2048*100}%`;element.style.height=`${height/768*100}%`;
}
function localSvg(name,viewBox){
 const layer=document.createElementNS(SVG_NS,'svg'),prefix=name+'-asset-';
 layer.setAttribute('viewBox',viewBox);layer.setAttribute('aria-hidden','true');
 layer.classList.add('cluster-svg');layer.dataset.assetPrefix=prefix;
 layer.append(document.createElementNS(SVG_NS,'defs'));
 for(const id of ['text-glow','readout-glow','needle-glow'])layer.style.setProperty('--'+id,`url(#${prefix}${id})`);
 return layer;
}
function populateAssets(layer){
 const prefix=layer.dataset.assetPrefix,added=new Set(),definitions=layer.querySelector('defs');
 function references(element){
  const found=new Set();
  for(const node of [element,...element.querySelectorAll('*')])for(const attr of [...node.attributes]){
   for(const match of attr.value.matchAll(/url\(#([^)]+)\)|^#(.+)$/g))found.add((match[1]||match[2]).replace(prefix,''));
  }
  return found;
 }
 function add(id){
  if(added.has(id)||!nodes[id])return;added.add(id);
  const copy=nodes[id].cloneNode(true);for(const dependency of references(copy))add(dependency);
  for(const node of [copy,...copy.querySelectorAll('[id]')])if(node.id)node.id=prefix+node.id;
  localize(copy,prefix);definitions.append(copy);
 }
 // Copy only definitions actually used by this small surface.
 for(const child of [...layer.children])if(child!==definitions)for(const id of references(child))add(id);
 if(layer.querySelector('.number,.label,.dial-label,.value'))add('text-glow');
 if(layer.querySelector('.readout'))add('readout-glow');
 if(layer.querySelector('.needle'))add('needle-glow');
}
function localize(element,prefix){
 for(const node of [element,...element.querySelectorAll('*')]){
  for(const attr of [...node.attributes]){
   if(attr.value.includes('url(#'))node.setAttribute(attr.name,attr.value.replace(/url\(#([^)]+)\)/g,(_,id)=>`url(#${prefix}${id})`));
  }
 }
}
function surface(name,x,y,width,height,ids,dialId){
 const layer=localSvg(name,`${x} ${y} ${width} ${height}`);
 layer.id=name+'-surface';layer.classList.add('instrument-layer','instrument-surface');
 positionLayer(layer,x,y,width,height);
 let parent=layer;
 if(dialId){parent=document.createElementNS(SVG_NS,'g');parent.setAttribute('transform',nodes[dialId+'-dial'].getAttribute('transform'));layer.append(parent);}
 for(const id of ids){
  const element=nodes[id].tagName==='tspan'?nodes[id].parentElement:nodes[id];
  localize(element,layer.dataset.assetPrefix);parent.append(element);
 }
 populateAssets(layer);shell.append(layer);
}
function needleLayers(id,cx){
 const layer=document.createElement('div');layer.id=id+'-motion';layer.className='instrument-layer dial-motion';layer.setAttribute('aria-hidden','true');
 positionLayer(layer,cx-DIAL.radius,DIAL.cy-DIAL.radius,DIAL.radius*2,DIAL.radius*2);
 const rotor=document.createElement('div'),orbit=document.createElement('div'),upright=document.createElement('div');
 rotor.className='needle-rotor';orbit.className='flare-orbit';upright.className='flare-upright';
 const needle=nodes[id+'-needle'],flare=nodes[id+'-needle-flare'];
 needle.removeAttribute('transform');needle.removeAttribute('opacity');flare.removeAttribute('opacity');
 const art=localSvg(id+'-needle','-327 -327 654 654'),tip=localSvg(id+'-flare','-62 -36 124 72');
 art.classList.add('needle-art');tip.classList.add('flare-art');
 localize(needle,art.dataset.assetPrefix);localize(flare,tip.dataset.assetPrefix);
 art.append(needle);tip.append(flare);populateAssets(art);populateAssets(tip);
 // SVG images are rasterized once; rotating inline SVG can still repaint its filters in WebKit.
 function cachedArt(source,className){
  source.setAttribute('xmlns',SVG_NS);
  const path=source.querySelector('.needle');if(path)path.setAttribute('filter',`url(#${source.dataset.assetPrefix}needle-glow)`);
  const image=document.createElement('img');image.className='cluster-svg '+className;image.alt='';image.draggable=false;
  image.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(source.outerHTML);return image;
 }
 rotor.append(cachedArt(art,'needle-art'));upright.append(cachedArt(tip,'flare-art'));orbit.append(upright);layer.append(rotor,orbit);shell.append(layer);
 return {layer,rotor,orbit,upright,animations:[]};
}
const needles={cpu:needleLayers('cpu',385),memory:needleLayers('memory',1657)};
const needleEntries=Object.entries(needles);
for(const [,needle] of needleEntries)needle.parts=[[needle.rotor,1],[needle.orbit,1],[needle.upright,-1]];
surface('header',100,4,1908,42,['address','online-dot','online','date','clock']);
surface('cpu-label',289,204,192,43,['cpu-label'],'cpu');
surface('memory-label',1542,204,230,43,['memory-label'],'memory');
surface('cpu-readout',276,271,218,123,['cpu-usage'],'cpu');
surface('memory-readout',1548,271,218,158,['memory-usage','memory-detail'],'memory');
surface('cpu-track',154,506,463,117,['cpu-lower-voltage','cpu-lower-track','cpu-lower-ticks'],'cpu');
surface('gpu-track',1426,506,463,117,['gpu-lower-voltage','gpu-voltage-track','memory-lower-ticks'],'memory');
surface('center',842,181,364,387,['center-label','power-value','power-unit','power-source','power-formula']);
surface('power-ring',875,211,298,259,['power-track']);
surface('cpu-details',231,655,500,39,['cpu-frequency','cpu-voltage','cpu-power']);
surface('gpu-details',1367,655,358,39,['gpu-frequency','gpu-voltage','gpu-power']);
surface('cpu-power-details',1855,651,150,58,['cpu-power-secondary','cpu-water-bar']);
surface('navigation',893,608,262,68,['view-label',...Array.from({length:6},(_,i)=>'view-dot-'+i)]);
surface('connection',960,692,128,49,['ready-frame','ready']);
function setAttr(id,name,value){
 const element=nodes[id],prefix=element.ownerSVGElement.dataset.assetPrefix;
 let next=String(value);
 if(prefix)next=next.replace(/url\(#([^)]+)\)/g,(_,ref)=>`url(#${prefix}${ref})`);
 if(element.getAttribute(name)!==next)element.setAttribute(name,next);
}
// Cache the detailed static SVG as pixels. Some older WebKit renderers repaint
// even an unchanged SVG's blur filters when a sibling animates.
const face=document.createElement('canvas');face.className='cluster-svg cluster-face';face.setAttribute('aria-hidden','true');face.hidden=true;shell.append(face);
let faceAssets=null,faceKey='',faceRevision=0;
let faceLayoutWidth=shell.clientWidth;
async function fontData(url){
 const response=await fetch(url);if(!response.ok)throw new Error('Font unavailable');
 const blob=await response.blob();
 return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(blob);});
}
function cacheFace(){
 if(document.hidden)return;
 const width=Math.max(1,Math.min(4096,Math.ceil(faceLayoutWidth*Math.min(devicePixelRatio||1,2)))),height=Math.max(1,Math.round(width*3/8));
 const key=`${width}:${config.cpuWarningPercent}:${config.memoryWarningPercent}`;
 if(key===faceKey)return;faceKey=key;
 const revision=++faceRevision;
 return renderFace(width,height,revision);
}
async function renderFace(width,height,revision){
 try{
  if(!faceAssets)faceAssets=Promise.all([fontData('/fonts/Exo2-Regular.ttf'),fontData('/fonts/Exo2-Italic.ttf')]);
  const [regular,italic]=await faceAssets;
  if(revision!==faceRevision)return;
  if(document.hidden){faceKey='';return;}
  const copy=svg.cloneNode(true);copy.setAttribute('xmlns',SVG_NS);copy.setAttribute('width','2048');copy.setAttribute('height','768');copy.style.display='block';copy.style.filter='none';
  const style=document.createElementNS(SVG_NS,'style');
  style.textContent=[...document.styleSheets].flatMap(sheet=>[...sheet.cssRules].map(rule=>rule.cssText)).join('\n')+
   `\n@font-face{font-family:"Cluster Exo";src:url("${regular}");font-style:normal;font-weight:100 900}\n@font-face{font-family:"Cluster Exo";src:url("${italic}");font-style:italic;font-weight:100 900}`;
  copy.prepend(style);
  const image=new Image();image.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(new XMLSerializer().serializeToString(copy));
  await image.decode();
  if(revision!==faceRevision)return;
  if(document.hidden){faceKey='';return;}
  face.width=width;face.height=height;face.getContext('2d').drawImage(image,0,0,width,height);
  face.hidden=false;svg.style.display='none';
 }catch(error){
  // The vector face remains usable if the browser cannot create a bitmap cache.
  if(revision!==faceRevision)return;
  faceAssets=null;face.hidden=true;svg.style.display='block';console.warn('Static dial cache unavailable',error);
 }
}
new ResizeObserver(()=>{faceLayoutWidth=shell.clientWidth;cacheFace();}).observe(shell);
function stopNeedles(){
 for(const [,needle] of needleEntries){for(const animation of needle.animations)if(animation.playState!=='finished')animation.cancel();needle.animations.length=0;}
}
function moveNeedles(ms){
 stopNeedles();
 for(const [id,needle] of needleEntries){
  const value=target[id],start=dialAngle(animated[id]??value??0),end=dialAngle(value??0);
  const opacity=valid(value)?'1':'0';
  if(needle.layer.style.opacity!==opacity)needle.layer.style.opacity=opacity;
  for(const [element,direction] of needle.parts){
   const transform=`rotate(${direction*end}deg)`;
   if(element.style.transform!==transform)element.style.transform=transform;
   if(ms>0&&valid(value)&&start!==end){
    needle.animations.push(element.animate([{transform:`rotate(${direction*start}deg)`},{transform}],{duration:ms,easing:'cubic-bezier(.333333,1,.666667,1)'}));
   }
  }
 }
}
const trackAnimations=new Map();
const trackIds=['cpu-lower-track','gpu-voltage-track','power-track','cpu-water-bar'];
const trackWrites=new Map();
const trackTargets=Object.create(null),trackStarts=Object.create(null);
function trackValues(values,result={}){
 const center=centerValue(values),max=view<=2?100:config.maxPowerW;
 result['cpu-lower-track']=clamp((values.cpuVoltage??0)/VOLTAGE_MAX*100,0,100);
 result['gpu-voltage-track']=clamp((values.gpuVoltage??0)/VOLTAGE_MAX*100,0,100);
 result['power-track']=view===5?0:clamp((center??0)/max*100,0,100);
 result['cpu-water-bar']=clamp((values.cpuPower??0)/config.cpuPowerMaxW*100,0,100);
 return result;
}
function stopTracks(){for(const animation of trackAnimations.values())if(animation.playState!=='finished')animation.cancel();trackAnimations.clear();}
function moveTracks(ms){
 const values=trackValues(target,trackTargets);
 // Read the current presentation before cancelling, including an interrupted view change.
 const starts=trackStarts;
 for(const id of trackIds){
  starts[id]=undefined;
  const element=nodes[id],previous=trackWrites.get(id),animation=trackAnimations.get(id);
  // A finished, unchanged bar already has its exact endpoint inline. Preserve
  // the computed-style read for every change and interrupted animation.
  if(!previous||previous.value!==values[id]||previous.inline!==element.style.strokeDasharray||
     (animation&&animation.playState!=='finished'))starts[id]=getComputedStyle(element).strokeDasharray;
 }
 stopTracks();
 for(const id of trackIds){
  if(starts[id]===undefined)continue;
  const value=values[id];
  const element=nodes[id],end=`${value} 100`,start=starts[id];
  const previous=trackWrites.get(id);
  if(!previous||previous.value!==value||previous.inline!==element.style.strokeDasharray){
   element.style.strokeDasharray=end;trackWrites.set(id,{value,inline:element.style.strokeDasharray});
  }
  // Computed CSS rounds decimals; do not animate a subpixel rounding difference.
  if(ms>0&&Math.abs(parseFloat(start)-value)>.0001)trackAnimations.set(id,element.animate([{strokeDasharray:start},{strokeDasharray:end}],{duration:ms,easing:'cubic-bezier(.333333,1,.666667,1)'}));
 }
}
let latest=null,view=3,lastMessage=0,connected=false,disconnectedCleared=false;
const views=['cpu','gpu','memory','monitor','power','status'];
const viewNames=['CPU','GPU','Memory','Monitor','Power','Sensors'];
const target={cpu:null,memory:null,gpu:null,power:null,cpuPower:null,cpuFrequency:null,gpuFrequency:null,cpuVoltage:null,gpuVoltage:null,gpuPower:null,memoryUsed:null};
const readingKeys=Object.keys(target),usageIds=['cpu','memory'];
const animated={cpu:null,memory:null},from={...animated};
let animationStart=0,duration=850;
let config={maxPowerW:650,cpuWarningPercent:85,memoryWarningPercent:87.5,cpuPowerMaxW:200,brightness:100,sampleIntervalMs:1000,animationMs:850};
const clamp=(n,lo,hi)=>Math.max(lo,Math.min(hi,n));
const valid=n=>typeof n==='number'&&Number.isFinite(n);
const fmt=(n,digits=0)=>valid(n)?n.toFixed(digits):'—';
// One bounded slot per reading, shared by visible and accessible text. Keep the
// original formatter so rounding, invalid values and signed zero stay identical.
const numberFormats=Object.create(null);
function formattedNumber(key,value,digits=0){
 let previous=numberFormats[key];
 if(previous&&Object.is(previous.value,value)&&previous.digits===digits)return previous.text;
 const next=fmt(value,digits);
 if(previous){previous.value=value;previous.digits=digits;previous.text=next;}
 else numberFormats[key]={value,digits,text:next};
 return next;
}
function centerValue(values=target){
 if(!latest)return null;
 if(view===0)return values.cpu;
 if(view===1)return values.gpu;
 if(view===2)return values.memory;
 if(view===5)return latest.issues.length;
 return values.power;
}
function paint(){
 if(document.hidden)return;
 disconnectedCleared=false;
 for(const id of usageIds){
  const value=target[id];
  // Numeric readings show the latest actual sample; easing affects the needle only.
  setText(id+'-usage',formattedNumber(id+'Usage',valid(value)?latest?.[id]?.usage:null));
 }
 setText('cpu-lower-voltage',`CPU ${formattedNumber('cpuVoltage',target.cpuVoltage,2)} V`);
 setText('gpu-lower-voltage',`GPU ${formattedNumber('gpuVoltage',target.gpuVoltage,2)} V`);
 const center=centerValue();
 setText('power-value',formattedNumber(centerFormatKeys[view],center));
 if(latest){
  const cpuPower=`${formattedNumber('cpuPower',target.cpuPower)} W`;
  setText('cpu-power',cpuPower);setText('cpu-power-secondary',cpuPower);
  setText('cpu-frequency',`${formattedNumber('cpuFrequency',valid(target.cpuFrequency)?target.cpuFrequency/1000:null,2)} GHz`);
  setText('cpu-voltage',`${formattedNumber('cpuVoltage',target.cpuVoltage,2)} V`);
  setText('gpu-frequency',`${formattedNumber('gpuFrequency',target.gpuFrequency)} MHz`);
  setText('gpu-voltage',`${formattedNumber('gpuVoltage',target.gpuVoltage,2)} V`);
  setText('gpu-power',`${formattedNumber('gpuPower',target.gpuPower)} W`);
  setText('memory-detail',`${formattedNumber('memoryUsed',target.memoryUsed,1)} / ${formattedNumber('memoryTotal',latest.memory.totalGb,1)} GB`);
 }
}
function advanceAnimation(now){
 const p=duration===0?1:clamp((now-animationStart)/duration,0,1),ease=1-Math.pow(1-p,3);
 for(const key of usageIds) animated[key]=valid(target[key])?((from[key]??target[key])+(target[key]-(from[key]??target[key]))*ease):null;
 return p;
}
function changeView(delta){
 view=(view+delta+views.length)%views.length;
 for(let i=0;i<6;i++)setAttr('view-dot-'+i,'fill',i===view?'url(#active-dot)':'url(#dot)');
 setText('view-label',viewNames[view]);
 updateCenter();moveTracks(0);paint();
}
const centerLabels=['CPU LOAD','GPU LOAD','MEMORY LOAD','SYSTEM POWER','SYSTEM POWER','SENSOR STATUS'];
const centerFormatKeys=['cpuUsage','gpuUsage','memoryUsage','systemPower','systemPower','issues'];
function updateCenter(){
 disconnectedCleared=false;
 setText('center-label',centerLabels[view]);
 setText('power-unit',(view===0||view===1||view===2)?'%':view===5?'ISSUES':'W');
 if(latest){
  const source=latest.demo?'DEMO':latest.powerSource==='measured'?'MEASURED':latest.powerSource==='wall-estimate'?'AC ESTIMATE':'ESTIMATED';
  setText('power-source',view===5?(latest.issues.length?'CHECK SETTINGS':'ALL AVAILABLE'):view<=2?'LIVE TELEMETRY':source);
  setText('power-formula',view===0?latest.cpu.name:view===1?latest.gpu.name:view===2?`${formattedNumber('memoryUsed',latest.memory.usedGb,1)} / ${formattedNumber('memoryTotal',latest.memory.totalGb,1)} GB`:view===5?'OPEN SETTINGS FOR DETAILS':'PWR');
 }
}
const zoneValues={cpu:null,memory:null};
const zoneFields=[['cpu','cpuWarningPercent'],['memory','memoryWarningPercent']];
function zones(){
 for(const [id,field] of zoneFields){
  const value=config[field];
  if(zoneValues[id]===value)continue;
  zoneValues[id]=value;
  const path=arc(0,0,304,dialAngle(value),DIAL.start+DIAL.sweep);
  setAttr(id+'-zone','d',path);
  setAttr(id+'-zone-shadow','d',arc(0,0,302,dialAngle(value),DIAL.start+DIAL.sweep));
 }
}
function accept(packet){
 if(!packet||!packet.cpu||!packet.gpu||!packet.memory)return;
 // Retarget from the current eased position, even when a packet arrives between frames.
 const now=performance.now();
 // Hidden positions are discarded by visibilitychange before anything is drawn.
 if(!document.hidden){advanceAnimation(now);for(const key of usageIds)from[key]=animated[key];}
 latest=packet;connected=true;lastMessage=Date.now();disconnectedCleared=false;
 Object.assign(config,packet.config);duration=window.matchMedia('(prefers-reduced-motion: reduce)').matches?0:config.animationMs;
 target.cpu=packet.cpu.usage;target.memory=packet.memory.usage;target.gpu=packet.gpu.usage;target.power=packet.systemPowerW;target.cpuPower=packet.cpu.powerW;
 target.cpuFrequency=packet.cpu.frequencyMhz;target.gpuFrequency=packet.gpu.frequencyMhz;target.cpuVoltage=packet.cpu.voltageV;target.gpuVoltage=packet.gpu.voltageV;
 target.gpuPower=packet.gpu.powerW;target.memoryUsed=packet.memory.usedGb;animationStart=now;
 if(!document.hidden){
  refreshSample();moveNeedles(duration);moveTracks(duration);paint();
 }
}
function refreshSample(){
 const filter=config.brightness===100?'none':`brightness(${config.brightness/100})`;
 if(document.documentElement.style.getPropertyValue('--cluster-filter')!==filter)document.documentElement.style.setProperty('--cluster-filter',filter);
 zones();cacheFace();setText('address',latest.address);updateCenter();connectionState();
 const packet=latest;
 setNodeText(accessibleReading,`CPU ${formattedNumber('cpuUsage',packet.cpu.usage)}%，内存 ${formattedNumber('memoryUsage',packet.memory.usage)}%，GPU ${formattedNumber('gpuUsage',packet.gpu.usage)}%，CPU 电压 ${formattedNumber('cpuVoltage',packet.cpu.voltageV,2)} 伏，GPU 电压 ${formattedNumber('gpuVoltage',packet.gpu.voltageV,2)} 伏，整机功率 ${formattedNumber('systemPower',packet.systemPowerW)} 瓦。${packet.demo?'当前为演示数据。':''}`);
}
let connectionPresentation='';
function connectionState(){
 const stale=lastMessage&&Date.now()-lastMessage>Math.max(5000,(config.sampleIntervalMs||1000)*3);
 const online=connected&&!stale;
 const warning=online&&latest&&!latest.demo&&latest.issues.length>0;
 const presentation=online?(latest?.demo?'demo':warning?'warning':'online'):lastMessage?'offline':'connecting';
 if(presentation!==connectionPresentation){
  connectionPresentation=presentation;
  const color=online?(latest?.demo?'#ffc36b':'#19da8c'):'#ff5575';
  setText('online',online?(latest?.demo?'DEMO':'ONLINE'):lastMessage?'OFFLINE':'CONNECTING');
  setAttr('online','fill',color);setAttr('online-dot','fill',color);
  const readyColor=!online?'#ff5575':latest?.demo?'#ffbd68':warning?'#ebc472':'#21c183';
  setText('ready',!online?'WAIT':latest?.demo?'DEMO':warning?'CHECK':'READY');
  setAttr('ready','fill',readyColor);setAttr('ready-frame','stroke',readyColor);
 }
 if(stale&&!disconnectedCleared){
  // A disconnected display must never keep presenting stale numbers as current readings.
  for(const key of readingKeys)target[key]=null;
  for(const key of usageIds)animated[key]=null;
  moveNeedles(0);moveTracks(0);
  for(const id of ['cpu-frequency','cpu-voltage','gpu-frequency','gpu-voltage','gpu-power'])setText(id,'—');
  setText('power-source','DISCONNECTED');paint();setText('memory-detail','— / — GB');
  disconnectedCleared=true;
 }
}
const week=['SUN','MON','TUE','WED','THU','FRI','SAT'],months=['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
let clockYear,clockMonth,clockDay,clockWeekday,clockHour,clockMinute;
function clock(){
 const now=new Date(),year=now.getFullYear(),month=now.getMonth(),day=now.getDate(),weekday=now.getDay(),hour=now.getHours(),minute=now.getMinutes();
 if(year!==clockYear||month!==clockMonth||day!==clockDay||weekday!==clockWeekday){
  clockYear=year;clockMonth=month;clockDay=day;clockWeekday=weekday;
  setText('date',`${week[weekday]}   ${months[month]} ${day}, ${year}`);
 }
 if(hour!==clockHour||minute!==clockMinute){
  clockHour=hour;clockMinute=minute;
  setText('clock',`${String(hour).padStart(2,'0')}:${String(minute).padStart(2,'0')}`);
 }
 connectionState();
}
const demo=new URLSearchParams(location.search).get('demo')==='1';
const events=new EventSource('/api/events'+(demo?'?demo=1':''));
events.onmessage=event=>{try{accept(JSON.parse(event.data));}catch(error){console.error('Telemetry decode error',error);}};
events.onerror=()=>{connected=false;if(!document.hidden)connectionState();};
fetch('/api/telemetry'+(demo?'?demo=1':'')).then(r=>r.json()).then(accept).catch(()=>{});
document.getElementById('previous').addEventListener('click',()=>changeView(-1));
document.getElementById('next').addEventListener('click',()=>changeView(1));
async function fullScreen(){try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch(error){console.warn(error);}}
document.getElementById('fullscreen').addEventListener('click',fullScreen);
document.addEventListener('keydown',e=>{if(document.getElementById('status-dialog').open)return;if(e.key==='ArrowLeft')changeView(-1);if(e.key==='ArrowRight')changeView(1);if(e.key.toLowerCase()==='f')fullScreen();});
const dialog=document.getElementById('status-dialog');
document.getElementById('diagnostics').addEventListener('click',()=>{
 const details=document.getElementById('status-details');details.replaceChildren();
 for(const content of latest?[`CPU：${latest.cpu.name}`,`GPU：${latest.gpu.name}`,`CPU 数据源：${latest.cpu.source}`,`GPU 数据源：${latest.gpu.source}`,...latest.issues]:['等待服务连接…']){
  const p=document.createElement('p');p.textContent=content;details.append(p);
 }
 dialog.showModal();
});
document.getElementById('close-status').addEventListener('click',()=>dialog.close());
dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}});
document.addEventListener('visibilitychange',()=>{
 stopNeedles();stopTracks();
 if(!document.hidden){
  // Resume at the newest sample rather than replaying old, hidden animations.
  faceLayoutWidth=shell.clientWidth;
  for(const key of usageIds)animated[key]=from[key]=target[key];animationStart=performance.now()-duration;
  if(latest)refreshSample();moveNeedles(0);moveTracks(0);paint();clock();
 }
});
moveNeedles(0);moveTracks(0);clock();setInterval(()=>{if(!document.hidden)clock();},1000);paint();
