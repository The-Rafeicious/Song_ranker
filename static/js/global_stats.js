/* Global Stats: compact list expansion and browser-local activity times. */
(()=>{
 'use strict';
 const checkbox=document.getElementById('frequent-five');
 const expand=()=>document.querySelectorAll('[data-frequent-extra]').forEach(row=>row.hidden=!checkbox?.checked);
 checkbox?.addEventListener('change',expand);expand();
 for(const node of document.querySelectorAll('time[data-local-time]')){
  const date=new Date(node.dateTime);if(Number.isNaN(date.getTime()))continue;
  node.textContent=date.toLocaleString(undefined,{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
  node.title=date.toLocaleString();
 }
 const activity=document.getElementById('global-activity');
 const modes={standard:['--standard','Standard Vote'],blind:['--blind','Blind Audition'],recognition:['--recognition','Trivia'],tournament:['--tournament','Tournament'],guesser:['--guesser','Elo Guesser'],shelves:['--shelves','Album Shelves']};
 function themeActivity(){
  if(!activity)return;
  const counts={};for(const row of activity.querySelectorAll('[data-activity-kind]')){
   const kind=row.dataset.activityKind;if(Object.prototype.hasOwnProperty.call(modes,kind)&&!row.closest('[hidden]'))counts[kind]=(counts[kind]||0)+1;
  }
  const present=Object.keys(modes).filter(kind=>counts[kind]),total=present.reduce((n,kind)=>n+counts[kind],0);
  let accent='var(--muted)',sum=0,cumulative=0;const stops=[];
  for(const kind of present){
   const color=`var(${modes[kind][0]})`,weight=counts[kind];
   if(!sum)accent=color;else{const left=100*sum/(sum+weight);accent=`color-mix(in srgb, ${accent} ${left.toFixed(4)}%, ${color} ${(100-left).toFixed(4)}%)`}
   const tint=`color-mix(in srgb, ${color} 12%, #202020)`;
   if(!stops.length)stops.push(`${tint} 0%`);
   stops.push(`${tint} ${((cumulative+weight/2)/total*100).toFixed(2)}%`);cumulative+=weight;sum+=weight;
   if(sum===total)stops.push(`${tint} 100%`);
  }
  activity.style.setProperty('--activity-accent',accent);
  activity.style.setProperty('--activity-wash',stops.length?`linear-gradient(135deg, ${stops.join(', ')})`:'linear-gradient(145deg, #252525, #1b1b1b)');
  activity.dataset.currentModes=present.join(',');
  const heading=activity.querySelector('.activity-heading');if(heading)heading.title=present.map(kind=>`${modes[kind][1]}: ${counts[kind]}`).join(' · ')||'No recent mode results';
 }
 themeActivity();
 if(activity)new MutationObserver(themeActivity).observe(activity,{childList:true,subtree:true,attributes:true,attributeFilter:['data-activity-kind','hidden']});
 window.addEventListener('pageshow',()=>{expand();themeActivity()});
})();
