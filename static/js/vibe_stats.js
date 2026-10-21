/* Heatmap exploration only: server owns all coordinates, counts and report maths. */
(()=>{
 'use strict';
 if(document.body.dataset.page!=='vibe_stats')return;
 for(const chart of document.querySelectorAll('[data-vibe-chart]')){
  const svg=chart.querySelector('svg'),points=[...chart.querySelectorAll('[data-vibe-point]')],caption=chart.querySelector('.vibe-chart-selection');
  const original=caption.textContent;let index=-1;
  function show(point){
   if(!point)return;
   index=points.indexOf(point);const link=document.createElement('a');link.href=point.getAttribute('href');link.textContent=point.dataset.songTitle;
   caption.replaceChildren(link,document.createTextNode(' · '+point.dataset.songArtist));caption.title=point.dataset.songTitle+' · '+point.dataset.songArtist;
  }
  chart.addEventListener('pointerover',event=>show(event.target.closest('[data-vibe-point]')));
  chart.addEventListener('focusin',event=>show(event.target.closest('[data-vibe-point]')));
  chart.addEventListener('pointerleave',()=>{if(!svg.contains(document.activeElement)){caption.textContent=original;caption.removeAttribute('title')}});
  svg.addEventListener('keydown',event=>{
   if(!points.length)return;
   const directions={ArrowRight:1,ArrowDown:1,ArrowLeft:-1,ArrowUp:-1};
   if(event.key in directions){event.preventDefault();index=index<0?(directions[event.key]>0?0:points.length-1):(index+directions[event.key]+points.length)%points.length;points[index].focus();show(points[index])}
   else if(event.key==='Home'||event.key==='End'){event.preventDefault();index=event.key==='Home'?0:points.length-1;points[index].focus();show(points[index])}
   else if(event.key==='Enter'&&event.target===svg&&index>=0){event.preventDefault();points[index].dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}))}
  });
 }
})();
