/* Bounded, read-only opponent exploration; no audio or rating ownership. */
window.MatchNetwork = (() => {
  "use strict";
  const {esc} = window.SongRankerUI, controllers = new Map();
  let serial = 0;
  const num = value => Number.isFinite(value) ? value.toLocaleString(undefined,{maximumFractionDigits:1}) : "—";
  const date = value => value && Number.isFinite(new Date(value).getTime()) ? new Date(value).toLocaleString() : "Date unavailable";
  const precise = value => Number.isFinite(value) ? value.toLocaleString(undefined,{maximumFractionDigits:2}) : "—";
  const sign = value => (value > 0 ? "+" : value < 0 ? "-" : "") + (Math.abs(value)>0 && Math.abs(value)<.01 ? "<0.01" : precise(Math.abs(value)));
  const nodeName = song => `<a class="song" href="/song/${song.id}" title="${esc(song.title)}">${esc(song.title)}</a>`;
  function identity(song) {
    return `<div class="network-identity">${song.cover_url ? `<img src="${esc(song.cover_url)}" alt="" loading="lazy">` : '<span class="network-art" aria-hidden="true">♫</span>'}<div>${nodeName(song)}<div class="network-meta">${song.artist_links.map(a=>`<a class="artist" href="/artist/${encodeURIComponent(a.name)}">${esc(a.name)}</a>`).join(", ")}${song.album_link ? ` · <a class="album" href="/album/${encodeURIComponent(song.album_link.title)}">${esc(song.album_link.title)}</a>` : ""}</div><small>Current Elo ${num(song.elo)} · Rank ${song.rank == null ? "—" : "#"+song.rank}</small></div></div>`;
  }
  function panel(id) {
    return `<section class="panel dashboard-surface voting network-embedded"><div class="section-head"><h2 class="voting">Match network</h2><a class="voting" href="/match-network?song_id=${id}">Open large map ↗</a></div><div data-match-network data-song-id="${id}"><p>Explore four layers of opponents, with four branches from each song.</p><button class="btn voting" data-network-start>Explore matches</button></div></section>`;
  }
  function layout(nodes, edges, focus) {
    const points = new Map(nodes.map(n=>[n.id,{...n,x:0,y:0}]));
    if (focus != null) {
      const layers = new Map();
      for (const n of points.values()) { const list=layers.get(n.level)||[];list.push(n);layers.set(n.level,list); }
      let radius=0;
      for (const level of [...layers.keys()].sort((a,b)=>a-b)) {
        const list=layers.get(level); if (!level) continue;
        radius=Math.max(radius+200,list.length*105/(2*Math.PI));
        list.forEach((n,i)=>{const angle=2*Math.PI*i/list.length- Math.PI/2+level*.3;n.x=Math.cos(angle)*radius;n.y=Math.sin(angle)*radius;});
      }
      return points;
    }
    const adjacent = new Map(nodes.map(n=>[n.id,[]]));
    edges.forEach(e=>{adjacent.get(e.a)?.push(e.b);adjacent.get(e.b)?.push(e.a);});
    const seen = new Set(), groups=[];
    for (const n of nodes) if (!seen.has(n.id)) {
      const group=[],queue=[n.id];seen.add(n.id);
      for(let i=0;i<queue.length;i++){const id=queue[i];group.push(points.get(id));for(const other of adjacent.get(id)){if(!seen.has(other)){seen.add(other);queue.push(other);}}}
      groups.push(group);
    }
    groups.sort((a,b)=>b.length-a.length);
    let x=0,y=0,rowHeight=0;const width=Math.max(3200,Math.sqrt(nodes.length)*260);
    for(const group of groups){
      const radius=Math.max(180,Math.sqrt(group.length)*125),size=radius*2+240;
      if(x && x+size>width){x=0;y+=rowHeight;rowHeight=0;}
      group.forEach((n,i)=>{const angle=i*2.3999632297,r=88*Math.sqrt(i);n.x=x+size/2+Math.cos(angle)*r;n.y=y+size/2+Math.sin(angle)*r;n.cx=x+size/2;n.cy=y+size/2;});
      x+=size;rowHeight=Math.max(rowHeight,size);
    }
    // Spatial repulsion keeps each pass proportional to local density, not N².
    for(let iteration=0;iteration<60;iteration++){
      const grid=new Map();
      for(const n of points.values()){n.dx=0;n.dy=0;const key=`${Math.floor(n.x/220)},${Math.floor(n.y/220)}`;const bucket=grid.get(key)||[];bucket.push(n);grid.set(key,bucket);}
      for(const n of points.values()){
        const gx=Math.floor(n.x/220),gy=Math.floor(n.y/220);
        for(let i=-1;i<=1;i++)for(let j=-1;j<=1;j++)for(const other of grid.get(`${gx+i},${gy+j}`)||[]){
          if(n.id===other.id)continue;const dx=n.x-other.x,dy=n.y-other.y,d=Math.max(1,Math.hypot(dx,dy));
          if(d<200){const push=(200-d)*.14/d;n.dx+=dx*push;n.dy+=dy*push;}
        }
        n.dx+=(n.cx-n.x)*.002;n.dy+=(n.cy-n.y)*.002;
      }
      for(const e of edges){const a=points.get(e.a),b=points.get(e.b);if(!a||!b)continue;const dx=b.x-a.x,dy=b.y-a.y,d=Math.max(1,Math.hypot(dx,dy)),force=(d-270)*.012/d;a.dx+=dx*force;a.dy+=dy*force;b.dx-=dx*force;b.dy-=dy*force;}
      for(const n of points.values()){n.x+=Math.max(-15,Math.min(15,n.dx));n.y+=Math.max(-15,Math.min(15,n.dy));}
    }
    // Reserve cover/label-sized cells after the force pass. Crowded hubs cannot
    // pull labels back onto one another, including across component boundaries.
    const occupied=new Set();
    for(const n of points.values()){
      const col=Math.round(n.x/240),row=Math.round(n.y/160);let cell=null;
      for(let ring=0;!cell;ring++){
        let distance=Infinity;
        for(let y=-ring;y<=ring;y++)for(let x=-ring;x<=ring;x++){
          if(Math.max(Math.abs(x),Math.abs(y))!==ring)continue;
          const c=col+x,r=row+y,key=`${c},${r}`;
          if(occupied.has(key))continue;
          const d=(c*240-n.x)**2+(r*160-n.y)**2;
          if(d<distance){distance=d;cell={c,r,key};}
        }
      }
      occupied.add(cell.key);n.x=cell.c*240+(n.id%13-6);n.y=cell.r*160+(n.id%11-5);
    }
    return points;
  }
  function directions(edge){
    const result=[];
    if(edge.a_wins>0)result.push({from:edge.b,to:edge.a,wins:edge.a_wins});
    if(edge.b_wins>0)result.push({from:edge.a,to:edge.b,wins:edge.b_wins});
    return result;
  }
  function mount(root) {
    if(controllers.has(root))return controllers.get(root);
    const full=root.hasAttribute("data-network-full"),instance=++serial;
    let focus=Number(root.dataset.songId)||null,data=null,points=new Map(),loadingGraph=false,disposed=false,request,inspection,searchRequest,queryTimer,timelineTimer;
    let selected=null,selectedPair=null,pairPage=1,listLimit=50,searchRows=[];
    let camera={x:0,y:0,k:1},pointerStart=null,dragged=false,pinch=null;const pointers=new Map(),images=new Map(),timeouts=new Set();
    let viewport,canvas,ctx,details,status,range,clock,mode,source,local,depth,branches,results,search,lastWidth=0,lastHeight=0;
    function controls() {
      const select=(key,label,options,value)=>window.GameplayUI.select(`network-${instance}-${key}`,label,options.map(([value,label])=>({value,label})),value);
      root.innerHTML=`<div class="network-controls"><div class="network-search" role="search"><label for="network-${instance}-search">Find a song</label><input id="network-${instance}-search" type="search" autocomplete="off" placeholder="Song or artist…" maxlength="100"><ul class="network-search-results" hidden></ul></div>${select('mode','Visibility',[['all','Both modes'],['standard','Non-blind'],['blind','Blind']],'all')}${select('source','Matches',[['all','All matches'],['voting','Voting'],['first_round','Tournament first rounds'],['tournament','Later tournament rounds']],'all')}${select('depth','Layers',[['1','1 layer'],['2','2 layers'],['3','3 layers'],['4','4 layers'],['5','5 layers']],'4')}${select('branches','Branches per song',[['3','3 branches'],['4','4 branches'],['5','5 branches']],'4')}<label class="network-local"><input type="checkbox" data-network-local> Include local artist/album tournaments</label><button class="btn" data-network-action="all">Whole network</button></div>
        <div class="network-toolbar"><p>Drag to pan · Ctrl/⌘ + wheel or +/− to zoom · Arrow keys to pan · Home to fit</p><div><button class="btn" data-network-action="in" aria-label="Zoom in">+</button><button class="btn" data-network-action="out" aria-label="Zoom out">−</button><button class="btn" data-network-action="fit">Fit map</button><button class="btn" data-network-action="fullscreen">Full screen</button></div></div>
        <p class="network-status" role="status" aria-live="polite"></p><div class="network-timeline"><label for="network-${instance}-through">Matches through <time data-network-time>All saved matches</time></label><input type="range" id="network-${instance}-through" min="0" max="0" value="0" disabled aria-label="Matches through this point"><button class="btn" data-network-action="latest">Latest</button></div>
        <div class="network-legend"><span class="standard">● Non-blind</span><span class="blind">● Blind</span><span class="voting">● Mixed visibility</span><span class="tournament">Pink rim: tournament evidence</span><span>Arrows point loser → winner. Heads at both ends mean both songs have wins. Select a connection for its record. Layout shows connections, not Elo rank.</span></div>
        <div class="network-layout"><div class="network-viewport" tabindex="0" aria-label="Interactive match network. Use the song search or visible-song list to select songs with a keyboard."><canvas role="img" aria-label="Opponent network"></canvas><p class="network-empty" hidden>No matches in this view.</p></div><aside class="network-details" tabindex="-1" aria-label="Selected song or connection" hidden></aside></div>
        <details class="network-song-list"><summary>Visible songs</summary><div data-network-list></div><button class="btn" data-network-action="more">Show more songs</button></details><p class="network-note">Current collection and current Elo. Whole maps start at a readable zoom; Fit map shows the overview. Timeline filters saved matches, not historical rankings. Points-only rounds have no Elo change. Songs without matching connections are still searchable. Local tournaments are separate from competition.</p>`;
      const $=s=>root.querySelector(s);
      viewport=$('.network-viewport');canvas=$('canvas');ctx=canvas.getContext('2d');details=$('.network-details');status=$('.network-status');range=$('input[type=range]');clock=$('[data-network-time]');search=$('input[type=search]');results=$('.network-search-results');
      mode=$(`#network-${instance}-mode`);source=$(`#network-${instance}-source`);depth=$(`#network-${instance}-depth`);branches=$(`#network-${instance}-branches`);local=$('[data-network-local]');
      [mode,source,local].forEach(node=>node.addEventListener('change',()=>{titles();load(null);}));
      [depth,branches].forEach(node=>node.addEventListener('change',()=>{titles();load(data?.timeline.position??null);}));titles();
      range.addEventListener('input',()=>{clearTimeout(timelineTimer);clock.textContent=`Match ${range.value} · release to load`;});
      range.addEventListener('change',()=>{clearTimeout(timelineTimer);const point=Number(range.value);request?.abort();timelineTimer=setTimeout(()=>load(point),120);});
      search.addEventListener('input',()=>{clearTimeout(queryTimer);searchRequest?.abort();queryTimer=setTimeout(find,180);});
      search.addEventListener('keydown',e=>{if(e.key==='ArrowDown'){e.preventDefault();results.querySelector('button')?.focus();}if(e.key==='Enter' && searchRows.length){e.preventDefault();choose(searchRows[0].id);}if(e.key==='Escape')results.hidden=true;});
      root.addEventListener('click',click);
      viewport.addEventListener('pointerdown',down);viewport.addEventListener('pointermove',move);viewport.addEventListener('pointerup',up);viewport.addEventListener('pointercancel',cancelPointer);
      viewport.addEventListener('wheel',wheel,{passive:false});viewport.addEventListener('keydown',key);
      viewport.addEventListener('lostpointercapture',e=>pointers.delete(e.pointerId));
      if(!root.requestFullscreen)$('[data-network-action=fullscreen]').hidden=true;
      resize();
    }
    function params(through=data?.timeline.position) {
      const p=new URLSearchParams({mode:mode.value,source:source.value,local:local.checked?'1':'0',depth:depth.value,branches:branches.value});
      if(focus!=null)p.set('song_id',focus);if(through!=null)p.set('through',through);return p;
    }
    function titles(){for(const node of [mode,source,depth,branches])node.closest('.game-select').querySelector('.game-select-trigger').title=node.selectedOptions[0].textContent;}
    async function read(url,own,timeout=20000){
      const timer=setTimeout(()=>own.abort('network-timeout'),timeout);timeouts.add(timer);
      try{const response=await fetch(url,{signal:own.signal,cache:'no-store'});if(!response.ok)throw Error('Request failed.');const payload=await response.json();if(own.signal.aborted)throw new DOMException('Canceled','AbortError');return payload;}
      catch(error){if(own.signal.reason==='network-timeout')throw Error('Request timed out.');throw error;}
      finally{clearTimeout(timer);timeouts.delete(timer);}
    }
    async function load(through=null) {
      request?.abort();inspection?.abort();request=new AbortController();const own=request;loadingGraph=true;
      root.setAttribute('aria-busy','true');status.textContent='Loading saved match connections…';close(false);
      try{
        const payload=await read('/api/match-network?'+params(through),own);
        if(disposed||own!==request||own.signal.aborted||!root.isConnected)return;
        if(!Array.isArray(payload.nodes)||!Array.isArray(payload.edges))throw Error('Invalid network response.');
        depth.closest(".game-select").hidden=focus==null;branches.closest(".game-select").hidden=focus==null;
        data=payload;points=layout(data.nodes,data.edges,data.focus_id);listLimit=50;
        range.max=data.timeline.total;range.value=data.timeline.position;range.disabled=!data.timeline.total;
        clock.textContent=`${data.timeline.position} / ${data.timeline.total} matches · ${data.timeline.time ? date(data.timeline.time) : 'Date unavailable'}`;
        range.setAttribute('aria-valuetext',clock.textContent);
        status.textContent=`${data.nodes.length} songs · ${data.edges.length} connections · ${data.totals.shown_matches??data.edges.reduce((n,e)=>n+e.count,0)} matches shown · ${data.totals.matches} in filtered history${focus ? ` · ${data.depth} layers, up to ${data.branches} new branches per song` : ` · ${data.totals.connected} connected songs in the collection`}${data.limits.limited||data.limits.edges_limited?' · Drawing limit reached; focus a song or narrow the filters.':''}${data.omitted?` · ${data.omitted} results have unavailable participants.`:''}`;
        root.querySelector('.network-empty').textContent='No matches in this view.';root.querySelector('.network-empty').hidden=data.nodes.length>0;
        if(focus!=null && points.has(focus)){const centre=points.get(focus),ring=Math.max(0,...[...points.values()].filter(n=>n.level===1).map(n=>Math.hypot(n.x-centre.x,n.y-centre.y))),k=ring?Math.max(.06,Math.min(1,viewport.clientWidth/(2*(ring+70)),viewport.clientHeight/(2*(ring+70)))):1;camera={x:viewport.clientWidth/2-centre.x*k,y:viewport.clientHeight/2-centre.y*k,k};}else{fit();if(camera.k<.85&&points.size){const hub=[...points.values()].sort((a,b)=>b.opponents-a.opponents||b.matches-a.matches||a.id-b.id)[0];camera={x:viewport.clientWidth/2-hub.x,y:viewport.clientHeight/2-hub.y,k:1};}}
        list();draw();if(focus!=null && points.has(focus))inspectNode(focus,false);
      }catch(error){if(disposed||own!==request||error.name==='AbortError')return;status.textContent='Network could not load. ';const retry=document.createElement('button');retry.className='btn';retry.textContent='Retry network';retry.dataset.networkAction='retry';status.append(retry);data=null;points.clear();root.querySelector('[data-network-list]').replaceChildren();range.disabled=true;clock.textContent='Network unavailable';root.querySelector('.network-empty').textContent='Network unavailable. Retry above.';root.querySelector('.network-empty').hidden=false;draw();}
      finally{if(own===request){loadingGraph=false;root.removeAttribute('aria-busy');}}
    }
    async function find(){
      searchRequest?.abort();const query=search.value.trim();if(!query){results.hidden=true;searchRows=[];return;}
      const own=new AbortController();searchRequest=own;results.hidden=false;results.innerHTML='<li>Searching…</li>';
      try{const payload=await read('/api/match-network?search='+encodeURIComponent(query),own,10000);if(disposed||own!==searchRequest||own.signal.aborted||!root.isConnected)return;searchRows=payload.songs;results.innerHTML=searchRows.map(s=>`<li><button type="button" data-network-find="${s.id}">${esc(s.title)}<small>${esc(s.artist_links.map(a=>a.name).join(', '))} · ${num(s.elo)} Elo</small></button></li>`).join('')||'<li>No matching songs.</li>';}catch(e){if(e.name!=='AbortError' && own===searchRequest && !disposed && root.isConnected)results.innerHTML='<li>Search could not load. Type again to retry.</li>';}
    }
    function choose(id){focus=Number(id);results.hidden=true;search.value='';load(data?.timeline.position??null);}
    function fit(){if(!points.size)return;const values=[...points.values()],xs=values.map(n=>n.x),ys=values.map(n=>n.y),minX=Math.min(...xs)-90,maxX=Math.max(...xs)+90,minY=Math.min(...ys)-90,maxY=Math.max(...ys)+90;const k=Math.max(.01,Math.min(1.25,(viewport.clientWidth||640)/(maxX-minX),(viewport.clientHeight||500)/(maxY-minY)));camera={k,x:(viewport.clientWidth||640)/2-(minX+maxX)*k/2,y:(viewport.clientHeight||500)/2-(minY+maxY)*k/2};draw();}
    function resize(){if(!canvas)return;const ratio=Math.min(2,window.devicePixelRatio||1),width=viewport.clientWidth||640,height=viewport.clientHeight||500;if(data&&lastWidth){camera.x+=(width-lastWidth)/2;camera.y+=(height-lastHeight)/2;}lastWidth=width;lastHeight=height;canvas.width=width*ratio;canvas.height=height*ratio;draw();}
    function draw(){
      if(!ctx||!canvas||disposed)return;const ratio=Math.min(2,window.devicePixelRatio||1),w=canvas.width/ratio,h=canvas.height/ratio;
      ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,w,h);if(!data)return;
      const css=getComputedStyle(root),colour=key=>css.getPropertyValue('--'+key).trim()||({blind:'#55d6c2',standard:'#f0a35b',tournament:'#ff78a6',voting:'#9cdb91',song:'#1db954'})[key];
      ctx.save();ctx.translate(camera.x,camera.y);ctx.scale(camera.k,camera.k);
      for(const edge of data.edges){const a=points.get(edge.a),b=points.get(edge.b);if(!a||!b)continue;const ax=a.x*camera.k+camera.x,bx=b.x*camera.k+camera.x,ay=a.y*camera.k+camera.y,by=b.y*camera.k+camera.y;if(Math.max(ax,bx)<-30||Math.min(ax,bx)>w+30||Math.max(ay,by)<-30||Math.min(ay,by)>h+30)continue;const active=selectedPair===edge.id,near=selected===edge.a||selected===edge.b;ctx.globalAlpha=selected!=null&&!near&&!active ? .14 : .55;ctx.setLineDash(edge.modes.blind&&!edge.modes.standard?[7,5]:[]);const path=()=>{ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();};if(edge.sources.first_round||edge.sources.tournament){ctx.strokeStyle=colour('tournament');ctx.lineWidth=(active?7:4)/Math.max(.5,camera.k);path();}ctx.strokeStyle=active?colour('song'):edge.modes.blind&&edge.modes.standard?colour('voting'):colour(edge.modes.blind?'blind':'standard');ctx.lineWidth=(active?3:1.3)/Math.max(.5,camera.k);path();
        // Each endpoint gets a head only if that song has recorded a win.
        ctx.setLineDash([]);
        for(const direction of directions(edge)){
          const loser=points.get(direction.from),winner=points.get(direction.to),dx=winner.x-loser.x,dy=winner.y-loser.y,d=Math.hypot(dx,dy);
          if(!d)continue;const ux=dx/d,uy=dy/d,radius=camera.k<.3?10:25,gap=Math.min(radius+4/camera.k,d*.3),length=Math.min(12/camera.k,d*.18),half=length*.5;
          if(d<2*radius+length)continue;
          const x=winner.x-ux*gap,y=winner.y-uy*gap;
          ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x-ux*length-uy*half,y-uy*length+ux*half);ctx.lineTo(x-ux*length+uy*half,y-uy*length-ux*half);ctx.closePath();ctx.fillStyle=ctx.strokeStyle;ctx.fill();
          if(edge.sources.first_round||edge.sources.tournament){const core=ctx.strokeStyle;ctx.strokeStyle=colour('tournament');ctx.lineWidth=1/Math.max(.5,camera.k);ctx.stroke();ctx.strokeStyle=core;}
        }
      }
      ctx.setLineDash([]);ctx.globalAlpha=1;const coverBudget=new Set();
      for(const n of points.values()){
        const sx=n.x*camera.k+camera.x,sy=n.y*camera.k+camera.y;if(sx<-100||sy<-90||sx>w+100||sy>h+100)continue;
        const radius=camera.k<.3?10:25;ctx.beginPath();ctx.arc(n.x,n.y,radius,0,Math.PI*2);ctx.fillStyle=n.id===selected?'#263d2e':'#242424';ctx.fill();
        if(camera.k>=.45 && n.cover_url && (coverBudget.has(n.cover_url)||coverBudget.size<96)){coverBudget.add(n.cover_url);let img=images.get(n.cover_url);if(!img){if(images.size>=96){const first=[...images.keys()].find(key=>!coverBudget.has(key));if(first!=null){images.get(first).onload=null;images.delete(first);}}img=new Image();images.set(n.cover_url,img);img.onload=()=>{if(!disposed&&images.get(n.cover_url)===img)draw();};img.src=n.cover_url;}if(img.complete&&img.naturalWidth){ctx.save();ctx.beginPath();ctx.arc(n.x,n.y,23,0,Math.PI*2);ctx.clip();ctx.drawImage(img,n.x-23,n.y-23,46,46);ctx.restore();}}
        ctx.beginPath();ctx.arc(n.x,n.y,radius,0,Math.PI*2);ctx.strokeStyle=colour(n.id===selected||n.id===data.focus_id?'song':'voting');ctx.lineWidth=n.id===selected?4:1.5;ctx.stroke();
        if(camera.k>=.42){ctx.fillStyle='#f4f4f4';ctx.font='bold 13px Arial';ctx.textAlign='center';let title=n.title.slice(0,40);while(title.length>1&&((ctx.measureText(title+(title.length<n.title.length?'…':''))?.width)??title.length*7)>180)title=title.slice(0,-1);if(title.length<n.title.length)title+='…';ctx.fillText(title,n.x,n.y+43);ctx.fillStyle='#bbb';ctx.font='12px Arial';ctx.fillText(num(n.elo)+' Elo'+(n.level!=null?' · layer '+n.level:''),n.x,n.y+60);}
      }
      ctx.restore();
      canvas.setAttribute('aria-label',`${data.nodes.length} songs and ${data.edges.length} opponent connections with loser-to-winner arrows. Current Elo; use the visible-song list for keyboard selection.`);
    }
    function zoom(factor,x=viewport.clientWidth/2,y=viewport.clientHeight/2){const k=Math.max(.01,Math.min(3,camera.k*factor)),scale=k/camera.k;camera={k,x:x-(x-camera.x)*scale,y:y-(y-camera.y)*scale};draw();}
    function list(){if(!data)return;const rows=[...data.nodes].sort((a,b)=>b.matches-a.matches||a.title.localeCompare(b.title));root.querySelector('[data-network-list]').innerHTML=rows.slice(0,listLimit).map(n=>`<button class="network-list-song" data-network-node="${n.id}">${esc(n.title)}<small>${num(n.elo)} current Elo · ${n.opponents} opponents</small></button>`).join('');root.querySelector('.network-song-list summary').textContent=`Visible songs · ${rows.length}`;root.querySelector('[data-network-action=more]').hidden=listLimit>=rows.length;}
    function open(){details.hidden=false;root.classList.add('has-network-details');}
    function close(focusBack=true){inspection?.abort();inspection=null;selected=null;selectedPair=null;if(details)details.hidden=true;root.classList.remove('has-network-details');draw();if(focusBack)viewport?.focus({preventScroll:true});}
    function inspectNode(id,focusPanel=true){
      inspection?.abort();inspection=null;const n=points.get(Number(id));if(!n)return;selected=n.id;selectedPair=null;open();
      const edges=data.edges.filter(e=>e.a===n.id||e.b===n.id).sort((a,b)=>b.count-a.count||a.id.localeCompare(b.id));
      details.innerHTML=`<div class="network-detail-head"><h3>Song connections</h3><button class="btn" data-network-action="close">Close</button></div>${identity(n)}<p>${n.matches} filtered matches · ${n.opponents} opponents in this history.</p><button class="btn voting" data-network-focus="${n.id}">Focus map here</button><h4>Visible opponents · ${edges.length}</h4><ul class="network-opponents">${edges.map(e=>{const other=points.get(e.a===n.id?e.b:e.a),wins=e.a===n.id?e.a_wins:e.b_wins;return `<li><button data-network-pair="${e.id}">${esc(other.title)}<small>${wins} wins · ${e.count-wins} losses · ${num(other.elo)} current Elo</small></button></li>`;}).join('')||'<li>No matching opponents. Try other filters or a later point.</li>'}</ul><p class="network-note">Focus here to explore this song’s branches beyond the visible map.</p>`;
      if(focusPanel)details.focus({preventScroll:true});draw();
    }
    async function inspectPair(id,page=1){
      const ids=id.split('-').map(Number);if(ids.length!==2||ids.some(n=>!Number.isSafeInteger(n)))return;
      inspection?.abort();const own=new AbortController();inspection=own;selectedPair=id;pairPage=page;open();details.innerHTML='<p role="status">Loading saved matches…</p>';draw();
      const p=params();p.set('pair',ids.join(','));p.set('page',page);
      try{const d=await read('/api/match-network?'+p,own);if(disposed||inspection!==own||own.signal.aborted||!root.isConnected)return;
        const a=d.songs[ids[0]],b=d.songs[ids[1]];
        details.innerHTML=`<div class="network-detail-head"><h3>Match connection</h3><button class="btn" data-network-action="close">Close</button></div>${identity(a)}${identity(b)}<p>${d.total} matches through the selected point. Each result below names its winner.</p><ol class="network-match-list">${d.history.map(r=>{const winner=d.songs[r.winner_id],loser=d.songs[r.loser_id];const changes=r.winner_before!=null&&r.winner_after!=null;return `<li><strong class="song">Won: ${esc(winner.title)}</strong><span class="network-loss">Lost: ${esc(loser.title)}</span><span class="${r.mode}">${r.mode==='blind'?'Blind':'Non-blind'}</span><small>${esc(date(r.time))}</small>${r.tournament_id ? `<a class="tournament" href="/tournament/${r.tournament_id}/bracket">${esc(r.stage)} · ${esc(({global:'Library',tag:'Tag',artist:'Local artist',album:'Local album'})[r.scope]||'Tournament')} #${r.tournament_id} ↗</a>`:'<span>Voting</span>'}${changes?`<p>${esc(winner.title)}: ${precise(r.winner_before)} → ${precise(r.winner_after)} <b class="song">(${esc(sign(r.winner_after-r.winner_before))})</b><br>${esc(loser.title)}: ${precise(r.loser_before)} → ${precise(r.loser_after)} <b class="network-loss">(${esc(sign(r.loser_after-r.loser_before))})</b></p>`:`<p>${r.source==='voting'?'Elo snapshot unavailable':'Points-only / Elo snapshot unavailable'}${r.points!=null?' · '+precise(r.points)+' points to winner':''}</p>`}</li>`;}).join('')||'<li>No matches under these filters.</li>'}</ol><div class="network-history-pages"><button class="btn" data-network-action="newer" ${d.page<=1?'disabled':''}>← Newer</button><span>${d.page} / ${d.pages}</span><button class="btn" data-network-action="older" ${d.page>=d.pages?'disabled':''}>Older →</button></div>`;details.focus({preventScroll:true});
      }catch(e){if(e.name!=='AbortError'&&inspection===own&&!disposed)details.innerHTML='<p role="alert">Match details could not load.</p><button class="btn" data-network-action="pair-retry">Retry details</button><button class="btn" data-network-action="close">Close</button>';}
    }
    function click(e){if(!root.querySelector('.network-search')?.contains(e.target))results.hidden=true;const button=e.target.closest('button');if(!button||!root.contains(button))return;
      if(button.hasAttribute('data-network-find'))return choose(button.dataset.networkFind);
      if(button.hasAttribute('data-network-node')&&loadingGraph)return;
      if(button.hasAttribute('data-network-pair')&&loadingGraph)return;
      if(button.hasAttribute('data-network-node'))return inspectNode(button.dataset.networkNode);
      if(button.hasAttribute('data-network-focus'))return choose(button.dataset.networkFocus);
      if(button.hasAttribute('data-network-pair'))return inspectPair(button.dataset.networkPair);
      const action=button.dataset.networkAction;if(action==='close')close();else if(action==='in')zoom(1.3);else if(action==='out')zoom(1/1.3);else if(action==='fit')fit();else if(action==='all'){focus=null;load(data?.timeline.position??null);}else if(action==='latest'||action==='retry')load(null);else if(action==='more'){listLimit+=50;list();}else if(action==='older')inspectPair(selectedPair,pairPage+1);else if(action==='newer')inspectPair(selectedPair,pairPage-1);else if(action==='pair-retry')inspectPair(selectedPair,pairPage);else if(action==='fullscreen')Promise.resolve(root.requestFullscreen?.()).catch(()=>{});
    }
    function coordinates(e){const r=viewport.getBoundingClientRect();return {x:e.clientX-r.left,y:e.clientY-r.top};}
    function down(e){if(e.button && e.pointerType!=='touch')return;pointers.set(e.pointerId,coordinates(e));viewport.setPointerCapture?.(e.pointerId);pointerStart={...coordinates(e),camera:{...camera}};dragged=false;if(pointers.size===2){const [a,b]=[...pointers.values()];pinch={distance:Math.hypot(a.x-b.x,a.y-b.y),k:camera.k};dragged=true;}}
    function move(e){if(!pointers.has(e.pointerId))return;const p=coordinates(e);pointers.set(e.pointerId,p);if(pointers.size>=2){const [a,b]=[...pointers.values()],distance=Math.hypot(a.x-b.x,a.y-b.y);if(pinch&&pinch.distance)zoom(pinch.k*distance/pinch.distance/camera.k,(a.x+b.x)/2,(a.y+b.y)/2);dragged=true;return;}if(!pointerStart)return;const dx=p.x-pointerStart.x,dy=p.y-pointerStart.y;if(Math.hypot(dx,dy)>5)dragged=true;if(dragged){camera.x=pointerStart.camera.x+dx;camera.y=pointerStart.camera.y+dy;draw();}}
    function up(e){const p=coordinates(e),wasDrag=dragged;pointers.delete(e.pointerId);pinch=null;pointerStart=null;viewport.releasePointerCapture?.(e.pointerId);if(wasDrag||loadingGraph||!data)return;const world={x:(p.x-camera.x)/camera.k,y:(p.y-camera.y)/camera.k};const node=[...points.values()].map(n=>({n,d:Math.hypot(n.x-world.x,n.y-world.y)})).filter(item=>item.d<Math.max(28,12/camera.k)).sort((a,b)=>a.d-b.d)[0]?.n;if(node)return inspectNode(node.id);let closest=null,distance=9/camera.k;for(const edge of data.edges){const a=points.get(edge.a),b=points.get(edge.b),dx=b.x-a.x,dy=b.y-a.y,t=Math.max(0,Math.min(1,((world.x-a.x)*dx+(world.y-a.y)*dy)/(dx*dx+dy*dy||1))),d=Math.hypot(world.x-a.x-t*dx,world.y-a.y-t*dy);if(d<distance){closest=edge;distance=d;}}if(closest)inspectPair(closest.id);}
    function cancelPointer(){pointers.clear();pinch=null;pointerStart=null;dragged=true;}
    function wheel(e){if(e.ctrlKey||e.metaKey){e.preventDefault();const p=coordinates(e);zoom(Math.exp(-e.deltaY*.002),p.x,p.y);}}
    function key(e){if(e.key==='Escape'){e.preventDefault();close();}else if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','=','-','Home'].includes(e.key)){e.preventDefault();if(e.key==='Home')fit();else if(['+','=','-'].includes(e.key))zoom(e.key==='-'?1/1.2:1.2);else{camera.x+=e.key==='ArrowLeft'?80:e.key==='ArrowRight'?-80:0;camera.y+=e.key==='ArrowUp'?80:e.key==='ArrowDown'?-80:0;draw();}}}
    root.addEventListener('keydown',e=>{if(e.key==='Escape'&&e.target!==viewport){results&&(results.hidden=true);if(details&&!details.hidden)close();}});
    let observer;
    function start(){controls();observer=typeof ResizeObserver!=='undefined'?new ResizeObserver(resize):null;observer?.observe(viewport);load(null);}
    const controller={destroy(){disposed=true;request?.abort();inspection?.abort();searchRequest?.abort();clearTimeout(queryTimer);clearTimeout(timelineTimer);for(const timer of timeouts)clearTimeout(timer);timeouts.clear();observer?.disconnect();for(const img of images.values())img.onload=null;images.clear();controllers.delete(root);}};
    controllers.set(root,controller);
    if(full)start();else root.querySelector('[data-network-start]')?.addEventListener('click',start,{once:true});
    return controller;
  }
  function mountAll(container=document){for(const [root,controller] of controllers)if(!root.isConnected)controller.destroy();container.querySelectorAll('[data-match-network]').forEach(mount);}
  document.addEventListener('DOMContentLoaded',()=>mountAll());
  window.addEventListener('pagehide',()=>{for(const controller of [...controllers.values()])controller.destroy();});
  return Object.freeze({panel,mount,mountAll,layout,directions});
})();
