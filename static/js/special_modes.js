/* Independent V3.3 games and their shared stats/profile projections. */
window.SpecialModes=(()=>{
 'use strict';
 let U,guess=null,guessBusy=false,guessRequest=0,shelf=null,shelfBusy=false,dragged=null,loopRequested=false,playingSlot=null,selectedSlot=null,previewTimer=null,previewGeneration=0;
 const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const pct=(right,total)=>total?Number((100*right/total).toFixed(1))+'%':'—',num=n=>Number(n||0).toFixed(2);
 const metricKeys=['guess_attempts','guess_correct','shelf_attempts','shelf_album_correct','shelf_order_right','shelf_order_pairs','shelf_points','shelf_available'];
 function totals(tracks){return Object.fromEntries(metricKeys.map(key=>[key,tracks.reduce((sum,s)=>sum+Number(s[key]||0),0)]));}

 const reveal={generation:0,timers:new Map(),audio:null,clip:0,closed:false};
 function cancelReveal(){
   reveal.generation++;for(const [timer,resolve] of reveal.timers){clearTimeout(timer);resolve(false);}reveal.timers.clear();
   reveal.audio?.pause();reveal.audio?.remove();reveal.audio=null;cancelShelfClips();
 }
 function revealDelay(ms,generation){return new Promise(resolve=>{
   if(generation!==reveal.generation||reveal.closed){resolve(false);return;}
   const timer=setTimeout(()=>{reveal.timers.delete(timer);resolve(generation===reveal.generation&&!reveal.closed);},ms);reveal.timers.set(timer,resolve);
 });}
 function snippet(song,ms,generation){
   reveal.audio?.pause();reveal.audio?.remove();reveal.audio=null;
   if(!song?.audio_url||generation!==reveal.generation||reveal.closed||window.PreviewPlayback?.blocked())return;
   const audio=document.createElement('audio');audio.id='answer-snippet';audio.preload='none';audio.dataset.song=String(song.id);audio.volume=Number($('#volume-range')?.value??.5);
   audio.src=window.PreviewPlayback?.source(song.id,song.audio_url)||song.audio_url;U.main.append(audio);reveal.audio=audio;let timer=null;
   const pause=()=>{clearTimeout(timer);audio.pause();};
   audio.addEventListener('playing',()=>{clearTimeout(timer);timer=setTimeout(pause,ms);});
   audio.addEventListener('timeupdate',()=>{if(audio.currentTime>=ms/1000)pause();});
   audio.addEventListener('pause',()=>clearTimeout(timer));
   const playing=window.PreviewPlayback?window.PreviewPlayback.play(audio):audio.play();
   playing.then(()=>{if(generation!==reveal.generation||reveal.closed||!audio.isConnected)pause();}).catch(error=>{
     pause();if(generation!==reveal.generation||!audio.isConnected)return;
     const note=$('#reveal-audio-note');if(note)note.textContent=error.name==='PreviewBlockedError'?'Audio paused by preview limits':'Preview unavailable';
   });
 }
 // One buffered answer ahead; playback starts only when its card is revealed.
 const shelfClips={current:null,next:null,outgoing:new Set()};
 function discardClip(audio){if(!audio)return;audio.pause();audio.removeAttribute('src');audio.load();audio.remove();}
 function cancelShelfClips(){discardClip(shelfClips.current);discardClip(shelfClips.next);shelfClips.outgoing.forEach(discardClip);shelfClips.current=null;shelfClips.next=null;shelfClips.outgoing.clear();}
 function answerAudio(song,buffered=false){
   const audio=document.createElement('audio');audio.id=buffered?'shelf-buffered-snippet':'answer-snippet';audio.preload=buffered?'auto':'none';audio.dataset.song=String(song.id);audio.volume=0;
   audio.src=window.PreviewPlayback?.source(song.id,song.audio_url)||song.audio_url;U.main.append(audio);window.PreviewPlayback?.bind(audio);return audio;
 }
 function fadeClip(audio,incoming,generation){
   if(!audio)return;const started=performance.now(),initial=audio.volume;
   function step(now){
     if(generation!==reveal.generation||reveal.closed||!audio.isConnected)return;
     const t=Math.min(1,(now-started)/180),volume=Number($('#volume-range')?.value??.5);audio.volume=incoming?volume*t:initial*(1-t);
     if(t<1)requestAnimationFrame(step);else if(!incoming){discardClip(audio);shelfClips.outgoing.delete(audio);}
   }
   requestAnimationFrame(step);
 }
 function retireShelfClip(generation){const previous=shelfClips.current;shelfClips.current=null;if(previous){previous.id='outgoing-snippet';shelfClips.outgoing.add(previous);fadeClip(previous,false,generation);}}
 async function shelfAnswerAudio(song,nextSong,generation){
   if(generation!==reveal.generation||reveal.closed)return;
   if(!song?.audio_url||window.PreviewPlayback?.blocked()){discardClip(shelfClips.next);shelfClips.next=null;retireShelfClip(generation);return;}
   let audio=shelfClips.next?.dataset.song===String(song.id)?shelfClips.next:answerAudio(song);if(shelfClips.next&&shelfClips.next!==audio)discardClip(shelfClips.next);shelfClips.next=null;
   const previous=shelfClips.current;if(previous)previous.id='outgoing-snippet';audio.id='answer-snippet';audio.volume=0;shelfClips.current=audio;
   if(previous)shelfClips.outgoing.add(previous);
   try{
     if(audio.error)throw Error('Buffered preview unavailable');
     const playing=Promise.resolve(window.PreviewPlayback?window.PreviewPlayback.play(audio):audio.play());
     playing.then(()=>{if(generation!==reveal.generation||reveal.closed||!audio.isConnected)audio.pause();}).catch(()=>{});
     const ready=await Promise.race([playing.then(()=>true),revealDelay(3000,generation).then(()=>false)]);
     if(!ready||generation!==reveal.generation||reveal.closed||!audio.isConnected){if(!ready&&generation===reveal.generation&&!reveal.closed){window.PreviewPlayback?.problem(audio).catch(()=>{});const note=$('#reveal-audio-note');if(note)note.textContent='Preview unavailable';}if(shelfClips.current===audio)shelfClips.current=null;discardClip(audio);fadeClip(previous,false,generation);return;}
     fadeClip(audio,true,generation);fadeClip(previous,false,generation);
     // Space admissions above the preview gate's minimum gap; no retries or extra lookups.
     if(nextSong?.audio_url)revealDelay(650,generation).then(active=>{
       if(!active||shelfClips.current!==audio||window.PreviewPlayback?.blocked())return;
       const buffered=answerAudio(nextSong,true);shelfClips.next=buffered;buffered.load();
     });
   }catch(error){
     if(shelfClips.current===audio)shelfClips.current=null;discardClip(audio);fadeClip(previous,false,generation);
     if(generation===reveal.generation&&!reveal.closed){const note=$('#reveal-audio-note');if(note)note.textContent=error.name==='PreviewBlockedError'?'Audio paused by preview limits':'Preview unavailable';}
   }
 }
 function percentageStat(label,right,total,mode){
   const value=total?100*right/total:null;
   return `<div class="stat ${mode} percentage-stat"><span class="stat-label">${label}</span><strong class="stat-value">${pct(right,total)}</strong>${value===null?'<small>Not tested yet</small>':`<div class="progress" role="progressbar" aria-label="${esc(label)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Number(value.toFixed(1))}"><span style="width:${Math.min(100,value)}%"></span></div><small>${num(right).replace(/\.00$/,'')} / ${num(total).replace(/\.00$/,'')}</small>`}</div>`;
 }

 const guessLink='/mode_rankings/guesser',shelfLink='/mode_rankings/shelves';
 function panels(tracks,type='songs'){
   const t=totals(tracks);
   return `<div class="special-profile-panels"><section class="panel special-panel guesser"><div class="section-head"><h2 class="guesser">Elo Guesser</h2><a class="guesser" href="${guessLink}?entity=${['songs','artists','albums'].includes(type)?type:'songs'}">Rankings ↗</a></div><div class="mini-stats"><div><b class="guesser">${pct(t.guess_correct,t.guess_attempts)}</b><small>Correct picks</small></div><div><b class="guesser">${t.guess_correct} / ${t.guess_attempts}</b><small>Track appearances</small></div></div></section><section class="panel special-panel shelves"><div class="section-head"><h2 class="shelves">Album Shelves</h2><a class="shelves" href="${shelfLink}?entity=${['songs','artists','albums'].includes(type)?type:'songs'}">Rankings ↗</a></div><div class="mini-stats"><div><b class="shelves">${pct(t.shelf_points,t.shelf_available)}</b><small>Points earned</small></div><div><b class="shelves">${pct(t.shelf_order_right,t.shelf_order_pairs)}</b><small>Track order</small></div></div></section></div>`;
 }
 function homeSummary(){const s=U.data().special_modes||{},g=s.guesser||{},a=s.shelves||{};return `<section class="panel special-panel guesser"><div class="section-head"><h2 class="guesser">Elo Guesser</h2><a class="guesser" href="/elo_guesser_stats">Stats ↗</a></div><div class="mini-stats"><div><b class="guesser">${g.correct||0}</b><small>Correct picks</small></div><div><b class="guesser">${g.best_streak||0} 🔥</b><small>Best streak</small></div><div><b class="guesser">${pct(g.correct,g.rounds)}</b><small>Accuracy</small></div></div></section><section class="panel special-panel shelves"><div class="section-head"><h2 class="shelves">Album Shelves</h2><a class="shelves" href="/album_shelves_stats">Stats ↗</a></div><div class="mini-stats"><div><b class="shelves">${a.rounds||0}</b><small>Rounds</small></div><div><b class="shelves">${pct(a.points,a.available)}</b><small>Points earned</small></div><div><b class="shelves">${a.perfect||0}</b><small>Perfect shelves</small></div></div></section>`;}
 function homeBanners(){
   const songs=U.records('songs'),guesses=songs.filter(s=>s.guess_attempts>0).sort((a,b)=>b.guess_correct/b.guess_attempts-a.guess_correct/a.guess_attempts||b.guess_attempts-a.guess_attempts||a.title.localeCompare(b.title)).slice(0,20);
   const albums=U.records('albums').filter(U.properAlbum).map(a=>({...a,...totals(songs.filter(s=>s.album_id===a.id))})).filter(a=>a.shelf_order_pairs>0).sort((a,b)=>b.shelf_order_right/b.shelf_order_pairs-a.shelf_order_right/a.shelf_order_pairs||b.shelf_order_pairs-a.shelf_order_pairs||a.title.localeCompare(b.title)).slice(0,20);
   const head=(title,key,path)=>`<div class="section-head"><h2>${title}</h2><div class="shelf-controls"><a href="${path}">Stats ↗</a><button class="icon-btn" data-scroll="${key}" data-dir="-1" aria-label="Scroll ${title} left">‹</button><button class="icon-btn" data-scroll="${key}" data-dir="1" aria-label="Scroll ${title} right">›</button></div></div>`;
   const banner=(rows,key,title,type)=>`<section class="shelf-section ${key} home-records" id="home-${key}">${head(title,key,key==='guesser'?'/elo_guesser_stats':'/album_shelves_stats')}<div class="scroller" id="shelf-${key}" tabindex="0" aria-label="${title}">${rows.map((r,i)=>`<a class="shelf-card ${key}" data-home-record="${key}" href="${U.urlFor(type,r)}"><span class="shelf-rank">${i+1}</span><div class="shelf-art">${U.artwork(r,type)}</div><div class="shelf-info"><h3 class="${type==='songs'?'song':'album'}" title="${esc(r.name)}">${esc(r.name)}</h3><p class="artist" title="${esc(r.artist)}">${esc(r.artist)}</p><strong class="${key}">${key==='guesser'?pct(r.guess_correct,r.guess_attempts)+' correct':pct(r.shelf_order_right,r.shelf_order_pairs)+' track order'}</strong><small>${key==='guesser'?r.guess_correct+' / '+r.guess_attempts+' guesses':r.shelf_attempts+' track appearances'}</small></div></a>`).join('')||`<div class="empty">${key==='guesser'?'No Elo guesses yet':'No shelf placements yet'}</div>`}</div></section>`;
   return banner(guesses,'guesser','Elo Guesser','songs')+banner(albums,'shelves','Album Shelves','albums');
 }
 function gameTabs(){return '<div class="game-head"><h1 class="guesser">Elo Guesser</h1></div>';}
 function guessCounters(records){return `<div class="stats guess-records">${U.stat('Correct picks',records.correct||0,'guesser')}${U.stat('Accuracy',pct(records.correct,records.rounds),'guesser')}${U.stat('Current streak',(records.streak||0)+' 🔥','guesser')}${U.stat('Best streak',(records.best_streak||0)+' 🔥','guesser')}</div>`;}
 function artistLinks(s){return (s.artists||[]).map(a=>`<a class="artist" href="/artist/${encodeURIComponent(a.name)}" title="${esc(a.name)}">${esc(a.name)}</a>`).join('<span class="muted">, </span>');}
 async function loadGuess(){
   cancelReveal();reveal.closed=false;const requestId=++guessRequest;guessBusy=true;guess=null;U.cancelTransition();U.stopAudio();U.pageTone('guesser');document.body.classList.add('game-page');const release=U.holdHeight();
   U.main.innerHTML=gameTabs()+'<div class="empty" role="status">Loading pair…</div>';
   try{const result=await U.api('/api/elo-guesser/round',{});if(requestId!==guessRequest||document.body.dataset.tone!=='guesser')return;guess={...result,answered:false};renderGuess();}
   catch(error){if(requestId===guessRequest&&document.body.dataset.tone==='guesser')U.main.innerHTML=gameTabs()+`<div class="empty error" role="alert">${esc(error.message)}</div><div class="next-area"><button class="btn" data-guess-next>Retry</button></div>`;}
   finally{if(requestId===guessRequest)guessBusy=false;release();}
 }
 function renderGuess(){
   const release=U.holdHeight();U.main.innerHTML=gameTabs()+guessCounters(guess.records)+`<div class="matchup">${guess.songs.map((song,i)=>{
     const high=guess.answered&&guess.result.ratings[i]>guess.result.ratings[1-i],chosen=guess.chosen===song.id;
     const overlay=guess.answered?`<div class="score-reveal guess-elo ${high?'score-win':'score-loss'}"><small>${high?'Higher Elo':'Lower Elo'}</small><strong>${Math.round(guess.result.ratings[i])}</strong><b>${high?'✓ Correct answer':chosen?'✕ Your pick':''}</b></div>`:'';
     const cover=U.mediaButton({...song,name:song.title,artist:song.artists.map(a=>a.name).join(', ')},'guess-audio-'+i,false,!guess.answered);
     return `${i?'<span class="vs-circle">VS</span>':''}<article class="game-card ${guess.answered?(high?'guess-right-card':'guess-wrong-card'):''}"><div class="match-cover">${cover}${overlay}</div><h2><a class="song" title="${esc(song.title)}" href="/song/${song.id}">${esc(song.title)}</a></h2><div class="game-meta"><div class="game-artists">${artistLinks(song)}</div>${song.album&&!/\s-\s*single\s*$/i.test(song.album)?`<a class="album" title="${esc(song.album)}" href="/album/${encodeURIComponent(song.album)}">${esc(song.album)}</a>`:''}</div><button class="btn primary vote-btn" data-guess-pick="${song.id}" ${guess.answered?'disabled':''}>${guess.answered?(chosen?guess.result.correct?'✓ Correct · +1':'✕ Wrong pick':high?'✓ Correct answer':'Lower Elo'):'Higher Elo'}</button></article>`;
   }).join('')}</div>${guess.answered?`<section class="panel guess-feedback ${guess.result.correct?'guess-success':'guess-failure'}" role="status"><strong>${guess.result.correct?'✓ Correct · +1 point':'✕ Incorrect · +0 points · streak reset'}</strong><span>Next pair automatically…</span><small id="reveal-audio-note"></small></section>`:''}`;
   U.attachPlayers();if(guess.answered)$$('.match-cover .cover-button').forEach(b=>b.disabled=true);release();
 }

 async function answerGuess(id){
   if(guessBusy||!guess||guess.answered)return;guessBusy=true;$$('[data-guess-pick]').forEach(b=>b.disabled=true);
   let saved=false;
   try{
     const result=await U.api('/api/elo-guesser/answer',{token:guess.token,song_id:id});saved=true;U.stopAudio();cancelReveal();
     guess.answered=true;guess.chosen=id;guess.result=result;guess.records=result.records;renderGuess();
     const generation=reveal.generation,correct=guess.songs[result.ratings[0]>result.ratings[1]?0:1];snippet(correct,2800,generation);
     U.refreshData().catch(()=>U.toast('Answer saved; collection refresh unavailable'));
     if(await revealDelay(4500,generation))loadGuess();
   }catch(error){U.toast(error.message);if(!saved)$$('[data-guess-pick]').forEach(b=>b.disabled=false);}
   finally{guessBusy=false;}
 }

 function stopShelf(){previewGeneration++;loopRequested=false;playingSlot=null;clearTimeout(previewTimer);const a=$('#shelf-preview-audio');if(a)a.pause();markPlayback();}
 function markPlayback(){
   $$('[data-shelf-slot]').forEach(row=>{row.classList.toggle('selected',Number(row.dataset.shelfSlot)===selectedSlot);row.classList.toggle('is-playing',Number(row.dataset.shelfSlot)===playingSlot&&loopRequested);});
   const button=$('[data-shelf-play]');if(button){button.textContent=loopRequested?'Ⅱ Pause previews':'▶ Play previews';button.setAttribute('aria-pressed',String(loopRequested));}
 }
 async function playShelf(slot){
   if(!shelf)return;const available=shelf.songs.filter(s=>s.audio_url);if(!available.length)return;
   let s=available.find(s=>s.slot===slot)||available[0];const a=$('#shelf-preview-audio');if(!a)return;
   const generation=++previewGeneration;clearTimeout(previewTimer);a.pause();a.currentTime=0;selectedSlot=s.slot;playingSlot=s.slot;loopRequested=true;
   a.src=window.PreviewPlayback?.source(s.id,s.audio_url)||s.audio_url;a.volume=Number($('#volume-range')?.value??.5);markPlayback();
   $('#shelf-preview-info').textContent=s.title;
   try{await (window.PreviewPlayback?window.PreviewPlayback.play(a):a.play());}
   catch(error){if(generation!==previewGeneration)return;stopShelf();U.toast(error.name==='PreviewBlockedError'?error.message:'Preview unavailable. Choose another track.');}
 }
 function advanceShelf(){
   if(!loopRequested||!shelf)return;clearTimeout(previewTimer);const available=shelf.songs.filter(s=>s.audio_url),at=available.findIndex(s=>s.slot===playingSlot);
   if(available.length)playShelf(available[(at+1)%available.length].slot);
 }
 function bindShelfAudio(){
   const a=$('#shelf-preview-audio');
   a.addEventListener('playing',()=>{clearTimeout(previewTimer);if(loopRequested)previewTimer=setTimeout(advanceShelf,Math.max(0,10-a.currentTime)*1000);markPlayback();});
   a.addEventListener('timeupdate',()=>{if(loopRequested&&a.currentTime>=10)advanceShelf();});
   a.addEventListener('ended',advanceShelf);
   a.addEventListener('waiting',()=>clearTimeout(previewTimer));
   a.addEventListener('pause',()=>{clearTimeout(previewTimer);if(a.paused)$$('[data-shelf-slot]').forEach(row=>row.classList.remove('is-playing'));});
   a.addEventListener('error',()=>{if(loopRequested){stopShelf();U.toast('Preview unavailable. Try another track.');}});
 }
 async function loadShelf(fresh=false){
   if(shelfBusy)return;shelfBusy=true;cancelReveal();reveal.closed=false;stopShelf();U.stopAudio();shelf=null;selectedSlot=null;U.pageTone('shelves');document.body.classList.remove('game-page');
   const generation=reveal.generation,release=U.holdHeight();U.main.innerHTML='<div class="page-head"><h1 class="shelves">Album Shelves</h1></div><div id="shelf-content"><div class="empty" role="status">Loading shelves…</div></div>';
   try{const result=await U.api('/api/album-shelves/round',{album_count:0,fresh});if(generation!==reveal.generation||reveal.closed)return;
     shelf={...result,placements:Object.fromEntries(result.albums.map(a=>[String(a.slot),[]])),pool:result.songs.map(s=>s.slot),answered:false,revealed:new Set()};
     $('#shelf-content').innerHTML=`<div class="shelf-actions"><button class="btn primary" data-shelf-check>Check shelves</button><button class="btn primary shelf-next" data-shelf-next hidden>Next round →</button><div id="shelf-order-score" class="shelf-order-score" hidden role="status"></div><span id="shelf-reveal-progress" class="sr-only" role="status"></span><small id="reveal-audio-note"></small></div><div class="shelf-audio-bar panel"><span class="shelf-preview-duration">10-second samples</span><button class="btn primary" data-shelf-play aria-pressed="false" ${shelf.songs.some(s=>s.audio_url)?'':'disabled'}>▶ Play previews</button><span id="shelf-preview-info" role="status">${shelf.songs.filter(s=>s.audio_url).length} / 10 previews</span><audio id="shelf-preview-audio" preload="none"></audio></div><div id="shelf-board"></div>`;renderShelfBoard();bindShelfAudio();
   }catch(error){if(generation===reveal.generation&&!reveal.closed)$('#shelf-content').innerHTML=`<div class="empty error" role="alert">${esc(error.message)}</div><div class="next-area"><button class="btn" data-shelf-retry>Retry loading</button></div>`;}
   finally{shelfBusy=false;release();}
 }


 function shelfPicker(song,where){
   const chosen=shelf.albums.find(a=>String(a.slot)===where),title=chosen?.title||'Unsorted';
   const option=(target,title,art)=>`<button type="button" role="menuitemradio" aria-checked="${where===target}" data-shelf-pick="${song.slot}" data-shelf-target="${target}"><span class="shelf-option-art">${art||'⠿'}</span><span>${esc(title)}</span><b aria-hidden="true">${where===target?'✓':''}</b></button>`;
   return `<details class="shelf-picker"><summary aria-label="Album for ${esc(song.title)}" aria-haspopup="menu" title="${esc(title)}"><span>${esc(title)}</span><b aria-hidden="true">⌄</b></summary><div class="shelf-picker-options" role="menu" aria-label="Choose album for ${esc(song.title)}">${option('pool','Unsorted','')}${shelf.albums.map(a=>option(String(a.slot),a.title,U.artwork({name:a.title,cover_url:a.cover_url},'albums'))).join('')}</div></details>`;
 }
 function shelfTrack(slot,where,index,length){
   const song=shelf.songs.find(s=>s.slot===slot),answer=shelf.result?.items.find(i=>i.item_slot===slot),revealed=shelf.revealed.has(slot);
   const full=answer&&answer.album_correct&&(!answer.order_pairs||answer.order_right===answer.order_pairs),truth=shelf.result?.answers.find(a=>a.slot===slot);
   const status=full?'✓ Correct':!answer?.album_correct?'✕ Wrong album':'✕ Order error';
   const submittedAlbum=answer&&shelf.albums.find(a=>a.slot===answer.answer_slot),corrected=revealed&&!full;
   const positionLabel=corrected?`Your shelf position ${answer.answer_position} on ${submittedAlbum?.title||'another album'}; correct album track ${truth.track_number}`:revealed?`Album track ${truth.track_number}`:'Shelf position';
   const position=corrected?`<del title="Your submitted shelf position">${answer.answer_position}</del><span title="Correct album track">${truth.track_number}</span>`:revealed?truth.track_number:where==='pool'?'⠿':index+1;
   const feedback=revealed?`<div class="shelf-revealed-answer"><strong class="${full?'answer-correct':'answer-wrong'}">${status}</strong><span>${answer.order_pairs?`${answer.order_right} / ${answer.order_pairs} order comparisons`: 'No order comparisons'}</span><b class="shelves">${num(answer.points)} / ${answer.available} points</b></div>`:'';
   return `<div class="shelf-track ${shelf.answered?'reveal-track':''} ${revealed?(full?'answer-correct':'answer-wrong'):'reveal-pending'}" data-shelf-slot="${slot}" ${revealed?`data-correct-track="${truth.track_number}"`:''} tabindex="0" draggable="${!shelf.answered}"><div class="shelf-track-title"><span class="shelf-position ${corrected?'shelf-position-corrected':''}" aria-label="${esc(positionLabel)}">${position}</span>${revealed?`<a class="song" title="${esc(song.title)}" href="/song/${song.id}">${esc(song.title)}</a>`:`<b class="song" title="${esc(song.title)}">${esc(song.title)}</b>`}<button class="preview-track" data-shelf-preview="${slot}" aria-label="Play ${esc(song.title)}" ${song.audio_url&&(!shelf.answered||shelf.revealComplete)?'':'disabled'}>▶</button></div>${feedback}${shelf.answered?'':`<div class="shelf-track-controls">${shelfPicker(song,where)}${where==='pool'?'':`<button class="shelf-arrow" data-shelf-shift="${slot}" data-direction="-1" aria-label="Move ${esc(song.title)} up" ${index===0?'disabled':''}>↑</button><button class="shelf-arrow" data-shelf-shift="${slot}" data-direction="1" aria-label="Move ${esc(song.title)} down" ${index===length-1?'disabled':''}>↓</button>`}</div>`}</div>`;
 }
 function shelfAlbumScore(album){
   const answers=shelf.result.answers.filter(a=>a.album_slot===album.slot),items=answers.map(a=>shelf.result.items.find(i=>i.item_slot===a.slot));
   const available=items.reduce((total,item)=>total+item.available,0),points=items.reduce((total,item)=>total+(shelf.revealed.has(item.item_slot)?item.points:0),0);
   return `<div class="shelf-cover-score"><small>Points</small><strong id="shelf-album-score-${album.slot}">${num(points)}</strong><span>/ ${available}</span></div>`;
 }
 function renderShelfBoard(){
   if(!shelf)return;
   $('#shelf-board').innerHTML=`<div class="shelf-columns ${shelf.albums.length===2?'two':''}">${shelf.albums.map(a=>`<section class="panel shelf-column"><div class="shelf-column-head"><div class="shelf-album-art">${U.artwork({name:a.title,cover_url:a.cover_url},'albums')}${shelf.answered?shelfAlbumScore(a):''}</div><h2 class="album" title="${esc(a.title)}">${esc(a.title)}</h2></div><div class="shelf-drop" data-shelf-drop="${a.slot}">${shelf.placements[a.slot].length?shelf.placements[a.slot].map((slot,i,list)=>shelfTrack(slot,String(a.slot),i,list.length)).join(''):'<div class="shelf-empty">Drop tracks here</div>'}</div></section>`).join('')}</div>${shelf.answered?'':`<section class="panel shelf-pool"><div class="section-head"><h2>Unsorted</h2><b class="shelves">${shelf.pool.length} / 10</b></div><div class="shelf-pool-grid" data-shelf-drop="pool">${shelf.pool.map((slot,i,list)=>shelfTrack(slot,'pool',i,list.length)).join('')||'<p>All ten tracks placed</p>'}</div></section>`}`;
   $('[data-shelf-check]').disabled=!!shelf.pool.length||shelf.answered;markPlayback();
 }

 function moveShelf(slot,where,before=null){
   if(!shelf||shelf.answered||!shelf.songs.some(s=>s.slot===slot)||where!=='pool'&&!Object.hasOwn(shelf.placements,where))return;
   shelf.pool=shelf.pool.filter(s=>s!==slot);Object.keys(shelf.placements).forEach(k=>shelf.placements[k]=shelf.placements[k].filter(s=>s!==slot));
   const list=where==='pool'?shelf.pool:shelf.placements[where],at=list.indexOf(before);list.splice(at<0?list.length:at,0,slot);selectedSlot=slot;renderShelfBoard();
 }
 function shiftShelf(slot,direction){
   if(!shelf||shelf.answered)return;const list=Object.values(shelf.placements).find(ids=>ids.includes(slot));if(!list)return;
   const at=list.indexOf(slot),to=at+direction;if(to<0||to>=list.length)return;[list[at],list[to]]=[list[to],list[at]];selectedSlot=slot;renderShelfBoard();$(`[data-shelf-slot="${slot}"]`)?.focus();
 }
 async function revealShelfRound(){
   const current=shelf,generation=reveal.generation,answers=[...current.result.answers].sort((a,b)=>a.album_slot-b.album_slot||a.track_number-b.track_number);let points=0;
   const albumPoints=Object.fromEntries(current.albums.map(a=>[a.slot,0])),button=$('[data-shelf-check]');button.classList.add('shelf-score-counter');button.innerHTML=`<span>Points</span><strong id="shelf-running-score">0.00</strong><small>/ ${current.result.available}</small>`;
   for(let index=0;index<answers.length;index++){
     if(generation!==reveal.generation||reveal.closed)return;const truth=answers[index],slot=truth.slot,item=current.result.items.find(i=>i.item_slot===slot),old=$(`[data-shelf-slot="${slot}"]`);
     old.classList.add('reveal-closing');if(!await revealDelay(420,generation))return;
     current.revealed.add(slot);
     const destination=$(`[data-shelf-drop="${truth.album_slot}"]`);destination.querySelector('.shelf-empty')?.remove();
     const holder=document.createElement('div');holder.innerHTML=shelfTrack(slot,String(truth.album_slot),index,answers.length);const row=holder.firstElementChild;
     old.remove();destination.insertBefore(row,destination.querySelector('.shelf-track:not([data-correct-track])'));row.classList.add('reveal-opening');
     const previous=points;points+=item.points;const previousAlbum=albumPoints[truth.album_slot];albumPoints[truth.album_slot]+=item.points;
     button.innerHTML=`<span>Points</span><strong id="shelf-running-score">${num(points)}</strong><small>/ ${current.result.available}</small>`;U.animateScore($('#shelf-running-score'),previous,points,2);
     U.animateScore($('#shelf-album-score-'+truth.album_slot),previousAlbum,albumPoints[truth.album_slot],2);
     $('#shelf-reveal-progress').textContent=`Track ${index+1} / 10 revealed`;
     const next=answers[index+1];await shelfAnswerAudio(current.songs.find(s=>s.slot===slot),next&&current.songs.find(s=>s.slot===next.slot),generation);
     if(!await revealDelay(2600,generation))return;row.classList.remove('reveal-opening');
   }
   current.placements=Object.fromEntries(current.albums.map(a=>[String(a.slot),answers.filter(t=>t.album_slot===a.slot).map(t=>t.slot)]));
   current.revealComplete=true;renderShelfBoard();$('#shelf-running-score').textContent=num(current.result.points);
   retireShelfClip(generation);const order=$('#shelf-order-score');order.innerHTML=`<small>Track order</small><strong>${pct(current.result.order_right,current.result.order_pairs)}</strong>`;order.hidden=false;$('.shelf-actions').classList.add('shelf-results-ready');$('#shelf-reveal-progress').textContent='10 / 10 tracks revealed';
   $('[data-shelf-next]').hidden=false;$('[data-shelf-play]').disabled=!current.songs.some(s=>s.audio_url);shelfBusy=false;
 }

 async function checkShelf(){
   if(shelfBusy||!shelf||shelf.answered||shelf.pool.length)return;const current=shelf,generation=reveal.generation;shelfBusy=true;$('[data-shelf-check]').disabled=true;let saved=false;
   try{const result=await U.api('/api/album-shelves/answer',{token:current.token,placements:current.placements});saved=true;current.answered=true;current.result=result;if(shelf!==current||generation!==reveal.generation||reveal.closed)return;stopShelf();U.stopAudio();cancelReveal();renderShelfBoard();$('[data-shelf-play]').disabled=true;
     U.refreshData().catch(()=>U.toast('Round saved; collection refresh unavailable'));await revealShelfRound();
   }catch(error){U.toast(error.message);if(!saved&&$('[data-shelf-check]'))$('[data-shelf-check]').disabled=false;}
   finally{if(!saved)shelfBusy=false;}
 }

 function metrics(mode){return mode==='guesser'?[['accuracy','Accuracy','guess_correct','guess_attempts','percentage'],['correct','Correct picks','guess_correct',null,'number'],['attempts','Appearances','guess_attempts',null,'number']]:mode==='shelves'?[['order','Track order','shelf_order_right','shelf_order_pairs','percentage'],['points','Points','shelf_points',null,'decimal'],['accuracy','Points earned','shelf_points','shelf_available','percentage'],['album','Correct albums','shelf_album_correct','shelf_attempts','percentage']]:mode==='trivia'?[['recognition','Recognisability','recognition_correct','recognition_score','trivia']]:[['championships','First place','championships',null,'number'],['runner_ups','Second place','runner_ups',null,'number'],['third_places','Third place','third_places',null,'number'],['podiums','Podiums','podiums',null,'number'],['wins','Match wins','tournament_wins',null,'number'],['points','Points','tournament_points',null,'decimal']];}
 function entityRows(mode,type){
   const songs=U.records('songs');return U.records(type).filter(r=>type!=='albums'||U.properAlbum(r)).map(r=>{
     const tracks=type==='songs'?[r]:songs.filter(s=>type==='artists'?s.artist_ids.includes(r.id):s.album_id===r.id);
     const t=totals(tracks),recognitionAvailable=tracks.reduce((n,s)=>n+Number(s.available_points||0),0);
     return {...r,...t,recognition_correct:tracks.reduce((n,s)=>n+Number(s.correct||0),0),recognition_score:recognitionAvailable,
       tournament_appearances:tracks.reduce((n,s)=>n+Number(s.tournament_appearances||0),0),
       ...Object.fromEntries(['championships','runner_ups','third_places','podiums','tournament_wins','tournament_points'].map(key=>[key,tracks.reduce((n,s)=>n+Number(s[key]||0),0)]))};
   });
 }
 function rankingValue(row,m){return m[4]==='percentage'||m[4]==='trivia'?(row[m[3]]?100*row[m[2]]/row[m[3]]:null):Number(row[m[2]]||0);}
 let rankingState=null,devRecordMode='guesser';
 function renderModeRanking(mode,init=false){
   if(init){const p=new URLSearchParams(location.search),context=$('#mode-ranking-context')?JSON.parse($('#mode-ranking-context').textContent):{};rankingState={mode,type:context.entity||(['songs','artists','albums'].includes(p.get('entity'))?p.get('entity'):'songs'),metric:p.get('metric')||metrics(mode)[0][0],bottom:p.get('view')==='bottom'};}
   const r=rankingState,list=metrics(mode),m=list.find(m=>m[0]===r.metric)||list[0];r.metric=m[0];const tone=mode==='trivia'?'recognition':mode;U.pageTone(tone);document.body.classList.add('rankings-page','performance-page');
   const eligible=entityRows(mode,r.type).filter(row=>mode==='guesser'?row.guess_attempts:mode==='shelves'?row.shelf_attempts:mode==='trivia'?row.recognition_score:row.tournament_appearances).filter(row=>rankingValue(row,m)!==null);
   eligible.sort((a,b)=>rankingValue(b,m)-rankingValue(a,m)||(b.guess_attempts||b.shelf_attempts||b.tournament_appearances||0)-(a.guess_attempts||a.shelf_attempts||a.tournament_appearances||0)||a.name.localeCompare(b.name));
   const rows=(r.bottom?[...eligible].reverse():eligible).slice(0,20),titles={guesser:'Elo Guesser',shelves:'Album Shelves',trivia:'Recognisability',tournament:'Tournament'};
   U.main.innerHTML=`<div class="page-head"><h1 class="${tone}">${titles[mode]} Rankings</h1></div><div class="pill-nav special-rank-tabs">${['songs','artists','albums'].map(type=>`<button class="pill ${r.type===type?'active':''}" data-special-entity="${type}" aria-pressed="${r.type===type}">${type[0].toUpperCase()+type.slice(1)}</button>`).join('')}</div><div class="pill-nav performance-metrics">${list.map(metric=>`<button class="pill ${r.metric===metric[0]?'active':''}" data-special-metric="${metric[0]}" aria-pressed="${r.metric===metric[0]}">${metric[1]}</button>`).join('')}</div><div class="ranking-switch pill-nav"><button class="pill ${r.bottom?'':'active'}" data-special-view="top">Top twenty</button><button class="pill ${r.bottom?'active':''}" data-special-view="bottom">Bottom twenty</button></div><div class="leaderboard">${rows.map((row,i)=>`<article class="leader-row" style="${U.rankGlow(i,r.bottom,tone)}"><span class="leader-rank">${r.bottom?eligible.length-i:['🥇','🥈','🥉'][i]||i+1}</span><a href="${U.urlFor(r.type,row)}" aria-label="${esc(row.name)}">${U.artwork(row,r.type)}</a><div class="special-rank-copy"><a class="leader-title ${U.colour(r.type)}" href="${U.urlFor(r.type,row)}" title="${esc(row.name)}">${esc(row.name)}</a><div class="leader-meta">${mode==='guesser'?`${row.guess_correct} / ${row.guess_attempts} correct appearances`:mode==='shelves'?`${row.shelf_attempts} appearances · ${pct(row.shelf_order_right,row.shelf_order_pairs)} track order`:mode==='trivia'?`${row.recognition_correct} / ${row.recognition_score} recognised fields`:`${row.championships} first · ${row.runner_ups} second · ${row.third_places} third`}</div></div><div class="leader-score ${tone}">${m[4]==='percentage'||m[4]==='trivia'?Number(rankingValue(row,m).toFixed(1))+'%':m[4]==='decimal'?num(rankingValue(row,m)):rankingValue(row,m)}<small>${m[1]}</small></div></article>`).join('')||'<div class="empty">No results for this category yet</div>'}</div>`;
   history.replaceState({},'',`/mode_rankings/${mode}?entity=${r.type}&metric=${r.metric}&view=${r.bottom?'bottom':'top'}`);
 }
 async function renderStats(mode){
   U.pageTone(mode);let data;
   try{data=await U.api('/api/special-modes/stats');}catch(error){U.main.innerHTML=`<div class="empty error">${esc(error.message)}</div>`;return;}
   const g=mode==='guesser',record=data.summary[mode],title=g?'Elo Guesser':'Album Shelves';
   const summary=g?U.stat('Correct picks',record.correct,'guesser')+percentageStat('Accuracy',record.correct,record.rounds,'guesser')+U.stat('Best streak',record.best_streak+' 🔥','guesser')+U.stat('Questions',record.rounds,'guesser'):U.stat('Rounds',record.rounds,'shelves')+U.stat('Points',num(record.points),'shelves')+U.stat('Perfect rounds',record.perfect,'shelves')+U.stat('Best round points',num(record.best_points),'shelves');
   const eligible=entityRows(mode,'songs').filter(row=>g?row.guess_attempts:row.shelf_order_pairs),metric=metrics(mode).find(m=>m[0]===(g?'accuracy':'order'));eligible.sort((a,b)=>rankingValue(b,metric)-rankingValue(a,metric)||a.name.localeCompare(b.name));
   const rows=list=>list.slice(0,10).map(row=>`<div class="compact-track">${U.compactArt(row)}<div class="compact-copy"><a class="song" title="${esc(row.title)}" href="/song/${row.id}">${esc(row.title)}</a><small>${g?row.guess_attempts:row.shelf_attempts} appearances</small></div><div class="compact-score ${mode}"><b>${Number(rankingValue(row,metric).toFixed(1))}%</b></div></div>`).join('')||'<div class="empty">No answers yet</div>';
   const history=g?data.guess_history:data.shelf_history,trackName=id=>U.records('songs').find(s=>s.id===id);
   const albums=(data.participating_albums||[]).map(a=>`<article class="participating-album panel"><a href="/album/${encodeURIComponent(a.title)}">${U.artwork({name:a.title,cover_url:a.cover_url},'albums')}</a><div><a class="album" title="${esc(a.title)}" href="/album/${encodeURIComponent(a.title)}">${esc(a.title)}</a><small>${a.rounds} rounds · ${a.attempts} tracks tested</small><strong class="shelves">${pct(a.order_right,a.order_pairs)} track order</strong><div class="progress" role="progressbar" aria-label="Track order for ${esc(a.title)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${a.order_pairs?100*a.order_right/a.order_pairs:0}"><span style="width:${a.order_pairs?100*a.order_right/a.order_pairs:0}%"></span></div></div></article>`).join('');
   U.main.innerHTML=`<div class="page-head"><h1 class="${mode}">${title} Stats</h1><div class="pill-nav"><a class="btn" href="${g?'/elo_guesser':'/album_shelves'}">Play →</a><a class="btn" href="/mode_rankings/${mode}">Rankings →</a></div></div><section class="special-stats-overview"><div class="stats">${summary}</div></section>${g?'':`<section class="special-stats-accuracy"><div class="section-head"><h2 class="shelves">Track Ordering</h2><small>${record.tracks} track appearances</small></div><div class="stats">${percentageStat('Track order',record.order_right,record.order_pairs,'shelves')}${percentageStat('Points earned',record.points,record.available,'shelves')}</div></section><section class="special-album-participation"><div class="section-head"><h2 class="shelves">Albums Played</h2><small>${data.participating_albums?.length||0} albums</small></div><div class="participating-albums">${albums||'<div class="empty">No albums tested yet</div>'}</div></section><details class="shelf-membership-details"><summary>Album placement breakdown</summary>${percentageStat('Correct albums',record.album_correct,record.tracks,'shelves')}</details>`}<div class="stats-columns special-track-stats"><section class="panel special-panel ${mode}"><div class="section-head"><h2 class="${mode}">Top Tracks</h2><a class="${mode}" href="/mode_rankings/${mode}">All rankings ↗</a></div>${rows(eligible)}</section><section class="panel special-panel ${mode}"><div class="section-head"><h2 class="${mode}">Tracks to Practise</h2><small>Up to ten</small></div>${rows([...eligible].reverse())}</section></div><section class="panel special-panel ${mode} special-recent-stats"><div class="section-head"><h2 class="${mode}">Recent Rounds</h2><small>Latest 30</small></div><div class="special-history">${history.map(row=>`<div class="special-history-row"><time>${new Date(row.completed_at*1000).toLocaleString()}</time><div>${g?[row.song1_id,row.song2_id].map(id=>{const track=trackName(id);return track?`<a class="song" href="/song/${track.id}">${esc(track.title)}</a>`:'<span class="muted">Deleted track</span>';}).join('<span class="muted"> vs </span>'):`${pct(row.order_right,row.order_pairs)} track order`}</div><strong class="${g&&!row.correct?'loss':mode}">${g?row.correct?'✓ +1':'✕ +0':num(row.points)+' / '+row.available}</strong>${g?`<small>${row.streak} 🔥</small>`:''}</div>`).join('')||'<div class="empty">No completed rounds</div>'}</div></section>`;
 }
 async function renderDevRecords(mode='guesser'){
   devRecordMode=mode;
   const node=$('#dev-main');if(!node)return;node.innerHTML='<div class="empty" data-mode-record-loader="'+mode+'">Loading records…</div>';
   try{
     const d=await U.api('/api/special-modes/stats');if(!node.isConnected||node.querySelector('[data-mode-record-loader]')?.dataset.modeRecordLoader!==mode)return;
     const section=(mode,rows)=>`<section class="panel special-panel ${mode} mode-records"><div class="section-head"><h2 class="${mode}">${mode==='guesser'?'Elo Guesser':'Album Shelves'}</h2><button class="btn small danger" data-tool="Reset ${mode==='guesser'?'Elo Guesser':'Album Shelves'} history">Reset history</button></div><div class="mode-record-search"><input type="search" data-mode-history-search="${mode}" placeholder="Find round ID or song…" aria-label="Find ${mode} round"></div><div class="data-scroll"><table class="mode-record-table"><thead><tr><th>Round</th><th>Completed</th><th>Result / tracks</th><th>Actions</th></tr></thead><tbody>${rows.map(r=>{
       const labels=mode==='guesser'?[r.song1_id,r.song2_id].map(id=>U.records('songs').find(s=>s.id===id)?.title||'Deleted track').join(' vs '):(r.song_ids||[]).map(id=>U.records('songs').find(s=>s.id===id)?.title||'Deleted track').join(', ');
       return `<tr data-special-history="${mode}" data-history-query="${esc((r.id+' '+labels).toLowerCase())}"><td>#${r.id}</td><td><small>${new Date(r.completed_at*1000).toLocaleString()}</small></td><td><b class="${mode}">${mode==='guesser'?r.correct?'Correct +1':'Incorrect +0':num(r.points)+' / '+r.available}</b><small class="record-track-names" title="${esc(labels)}">${esc(labels)}</small></td><td><button class="btn small danger" data-remove-special="${mode}" data-round="${r.id}">Delete round</button></td></tr>`;
     }).join('')||'<tr><td colspan="4">No completed rounds</td></tr>'}</tbody></table></div></section>`;
     node.innerHTML=`<div class="page-head"><h2 class="${mode}">${mode==='guesser'?'Elo Guesser':'Album Shelves'} Records</h2><small>Latest 30</small></div>`+section(mode,mode==='guesser'?d.guess_history:d.shelf_history);
   }catch(error){node.innerHTML=`<div class="empty error">${esc(error.message)}</div>`;}
 }
 document.addEventListener('click',async e=>{
   $$('.shelf-picker[open]').forEach(picker=>{if(!picker.contains(e.target))picker.open=false;});
   if(!U)return;const b=e.target.closest('button');if(!b||b.disabled)return;
   if(b.dataset.guessPick)await answerGuess(Number(b.dataset.guessPick));
   if(b.hasAttribute('data-guess-next'))await loadGuess();
   if(b.hasAttribute('data-shelf-play')){if(loopRequested)stopShelf();else playShelf(selectedSlot);}
   if(b.dataset.shelfPreview){const slot=Number(b.dataset.shelfPreview);if(loopRequested&&playingSlot===slot)stopShelf();else playShelf(slot);}
   if(b.dataset.shelfPick){const slot=Number(b.dataset.shelfPick);moveShelf(slot,b.dataset.shelfTarget);$(`[data-shelf-slot="${slot}"] .shelf-picker summary`)?.focus();}
   if(b.dataset.shelfShift)shiftShelf(Number(b.dataset.shelfShift),Number(b.dataset.direction));
   if(b.hasAttribute('data-shelf-check'))await checkShelf();
   if(b.hasAttribute('data-shelf-retry'))await loadShelf();
   if(b.hasAttribute('data-shelf-next')&&shelf?.revealComplete)await loadShelf(true);
   if(b.dataset.specialEntity){rankingState.type=b.dataset.specialEntity;renderModeRanking(rankingState.mode);}
   if(b.dataset.specialMetric){rankingState.metric=b.dataset.specialMetric;renderModeRanking(rankingState.mode);}
   if(b.dataset.specialView){rankingState.bottom=b.dataset.specialView==='bottom';renderModeRanking(rankingState.mode);}
   if(b.dataset.removeSpecial){if(!confirm('Delete this saved round? A database backup will be created.'))return;try{await U.api('/api/dev/special-round/'+b.dataset.removeSpecial+'/'+b.dataset.round,{});await U.refreshData();await renderDevRecords(devRecordMode);U.toast('Round deleted');}catch(error){U.toast(error.message);}}
 });
 document.addEventListener('input',e=>{if(e.target.dataset.modeHistorySearch){const mode=e.target.dataset.modeHistorySearch,q=e.target.value.toLowerCase().trim();$$(`[data-special-history="${mode}"]`).forEach(r=>r.hidden=!r.dataset.historyQuery.includes(q));}});
 document.addEventListener('focusout',e=>{const picker=e.target.closest('.shelf-picker');if(picker&&!picker.contains(e.relatedTarget))picker.open=false;});
 document.addEventListener('dragstart',e=>{const row=e.target.closest('[data-shelf-slot]');if(row&&shelf&&!shelf.answered){dragged=Number(row.dataset.shelfSlot);e.dataTransfer?.setData('text/plain',String(dragged));row.classList.add('dragging');}});
 document.addEventListener('dragover',e=>{const zone=e.target.closest('[data-shelf-drop]');if(zone&&shelf&&!shelf.answered){e.preventDefault();zone.classList.add('dragover');}});
 document.addEventListener('dragleave',e=>{const zone=e.target.closest('[data-shelf-drop]');if(zone&&!zone.contains(e.relatedTarget))zone.classList.remove('dragover');});
 document.addEventListener('drop',e=>{const zone=e.target.closest('[data-shelf-drop]');if(!zone||dragged===null||!shelf||shelf.answered)return;e.preventDefault();const row=e.target.closest('[data-shelf-slot]'),before=row?Number(row.dataset.shelfSlot):null;if(before!==dragged)moveShelf(dragged,zone.dataset.shelfDrop,before);dragged=null;});
 document.addEventListener('dragend',()=>{dragged=null;$$('.dragover,.dragging').forEach(e=>e.classList.remove('dragover','dragging'));});
 document.addEventListener('keydown',e=>{
   const picker=e.target.closest('.shelf-picker');
   if(picker){const options=[...picker.querySelectorAll('[data-shelf-pick]')];
     if(e.key==='Escape'){e.preventDefault();picker.open=false;picker.querySelector('summary').focus();return;}
     if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){
       e.preventDefault();picker.open=true;const at=options.indexOf(e.target),direction=e.key==='ArrowUp'?-1:1;
       const target=e.key==='Home'?0:e.key==='End'?options.length-1:at<0?Math.max(0,options.findIndex(b=>b.getAttribute('aria-checked')==='true')):(at+direction+options.length)%options.length;
       options[target]?.focus();return;
     }
   }
   const row=e.target.closest('[data-shelf-slot]');if(row&&e.target===row&&['ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();shiftShelf(Number(row.dataset.shelfSlot),e.key==='ArrowUp'?-1:1);}
 });
 window.addEventListener('pagehide',()=>{reveal.closed=true;cancelReveal();stopShelf();});
 window.addEventListener('pageshow',e=>{if(e.persisted&&U){reveal.closed=false;guessBusy=false;shelfBusy=false;if(document.body.dataset.page==='guesser')loadGuess();if(document.body.dataset.page==='shelves'){if(shelf?.answered){if(!shelf.revealComplete){shelf.revealed.clear();renderShelfBoard();shelfBusy=true;revealShelfRound().catch(error=>U.toast(error.message));}}else loadShelf();}}});
 return {bindUI:ui=>U=ui,panels,homeSummary,homeBanners,loadGuess,loadShelf,renderStats,renderModeRanking,renderDevRecords,cancelGuess:()=>{guessRequest++;guessBusy=false;},totals};
})();
