/* Reusable SVG radar: semantic spoke order comes from Python, absent values stay gaps. */
(()=>{
 'use strict';
 const esc=value=>window.SongRankerUI.esc(value);
 function radar(data,label='Song vibe'){
  const spokes=data.spokes, n=spokes.length,cx=220,cy=205,r=128;
  const at=(i,radius)=>{const a=i*2*Math.PI/n-Math.PI/2;return [cx+Math.cos(a)*r*radius,cy+Math.sin(a)*r*radius]};
  const pair=p=>p.map(v=>v.toFixed(2)).join(',');
  const rings=[.25,.5,.75,1].map(radius=>`<polygon class="radar-ring ${radius===.5?'radar-neutral':''}" points="${spokes.map((_,i)=>pair(at(i,radius))).join(' ')}"/>`).join('');
  const axes=spokes.map((s,i)=>{const [x,y]=at(i,1),[tx,ty]=at(i,1.16);return `<line class="radar-axis" x1="${cx}" y1="${cy}" x2="${x}" y2="${y}"/><text x="${tx}" y="${ty}" text-anchor="${Math.abs(tx-cx)<1?'middle':tx<cx?'end':'start'}" dominant-baseline="middle">${esc(s.label||s.high)}</text>`}).join('');
  const valid=s=>Number.isFinite(s.radius);
  let shape='';
  if(spokes.every(valid))shape=`<polygon class="radar-shape" points="${spokes.map((s,i)=>pair(at(i,s.radius))).join(' ')}"/>`;
  else shape=spokes.map((s,i)=>{const next=(i+1)%n;if(!valid(s)||!valid(spokes[next]))return '';return `<polyline class="radar-shape" fill="none" points="${pair(at(i,s.radius))} ${pair(at(next,spokes[next].radius))}"/>`}).join('');
  const points=spokes.map((s,i)=>{if(!valid(s))return '';const [x,y]=at(i,s.radius);return `<circle class="radar-point" cx="${x}" cy="${y}" r="4"><title>${esc(s.low)} → ${esc(s.high)}</title></circle>`}).join('');
  return `<svg class="vibe-radar" viewBox="0 0 440 410" role="img" aria-label="${esc(label)}"><desc>Eight bipolar axes. The dashed ring is neutral. Missing maps leave gaps.</desc>${rings}${axes}${shape}${points}</svg>`;
 }
 window.VibeCharts=Object.freeze({radar});
})();
