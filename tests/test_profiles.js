/* node tests/test_profiles.js — read-only profile rendering and mount fixtures. */
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
let count=0;const check=(value,label)=>{assert.ok(value,label);count++;};
const nodes={},main={innerHTML:'',classList:{add(){},remove(){}}},calls=[];
const document={body:{dataset:{entity:'1'},classList:{add(){}}},querySelector:s=>nodes[s]||null,querySelectorAll:()=>[],addEventListener(){},createElement:()=>({dataset:{},isConnected:true})};
const c={window:{addEventListener(){}},document,URLSearchParams,location:{search:''},console};vm.createContext(c);
for(const name of ['ui','profiles','overall'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/js/'+name+'.js'),'utf8'),c);
const source=fs.readFileSync(path.join(__dirname,'../static/js/site.js'),'utf8');
for(const [start,end] of [['function renderSong(){','function renderSongHistory()'],['function renderProfile(){','function renderProfileTracks()']])vm.runInContext(source.slice(source.indexOf(start),source.indexOf(end,source.indexOf(start))),c);
const track={id:1,name:'Track <one>',title:'Track <one>',artist_ids:[1],tag_ids:[1],album_id:1,audio_url:'preview',elo_score:1400,highest_elo:1500,matches_played:10,attempts:2,new_attempts:2,album_attempts:2,title_correct:2,artist_correct:1,album_correct:2,correct:5,available_points:6,championships:1,runner_ups:0,third_places:0,podiums:1,tournament_points:3.5,tournament_wins:3,tournament_losses:1,guess_attempts:4,guess_correct:3,shelf_attempts:2,shelf_album_correct:1,shelf_order_right:6,shelf_order_pairs:8,shelf_points:5.5,shelf_available:6,voting:{standard_wins:6,standard_losses:2,blind_wins:1,blind_losses:1},artist:'Artist, Joint'};
const artist={id:1,name:'Artist, Joint',title:'Artist, Joint',song_ids:[1],score:1400,impact_score:1400,avg_elo:1400},album={id:1,name:'Album <one>',title:'Album <one>',song_ids:[1],score:1400,impact_score:1400,avg_elo:1400},tag={id:1,name:'Tag <one>',title:'Tag <one>',description:'Description <safe>',song_ids:[1],score:1400,impact_score:1400,avg_elo:1400};
const data={songs:[track],artists:[artist],albums:[album],tags:[tag],tournaments:[{id:10,size:8,status:'completed',champion_id:1,scope_type:'artist',completed_at:'2026-01-01'}],tournament_entries:[{song_id:1,tournament_id:10}],tournament_matches:[{tournament_id:10,song1_id:1,song2_id:2,status:'completed',winner_id:1,loser_id:2,points_awarded:3.5}]};
const esc=c.window.SongRankerUI.esc,available=s=>Number(s.available_points||0);
const aggregateVotes=tracks=>{const v={};for(const p of ['standard_','blind_']){for(const key of ['wins','losses'])v[p+key]=tracks.reduce((n,s)=>n+Number(s.voting?.[p+key]||0),0);v[p+'matches']=v[p+'wins']+v[p+'losses'];}v.wins=v.standard_wins+v.blind_wins;v.losses=v.standard_losses+v.blind_losses;v.matches=v.wins+v.losses;return v;};
const urlFor=(type,row)=>'/'+type+'/'+encodeURIComponent(row.name||row.title),stat=(label,value,tone)=>`<div class="stat ${tone}"><span>${label}</span><b>${value}</b></div>`;
c.window.ProfileUI.bindUI({stat,available,aggregateVotes,urlFor,data:()=>data});
for(const type of ['songs','artists','albums','tags']){
 const html=c.window.ProfileUI.stats([track],type);
 check((html.match(/data-profile-panel=/g)||[]).length===5,'five concise mode panels');
 check(html.includes('3.50')&&html.includes('Points'),'saved tournament points');check(html.includes('75%'),'saved Guesser/order accuracy');
 check(html.includes('entity='+type),'correct entity rankings');check(html.includes('/tournament?tournament=10'),'bracket link opens game');
 check(!html.includes('<details')&&html.includes('Field breakdown'),'mode data visible without disclosure');check(!html.includes('NaN')&&!html.includes('undefined'),'valid figures');
 const empty=c.window.ProfileUI.stats([],type);check(empty.includes('No results yet')&&!empty.includes('NaN'),'empty rates unavailable');
}
const before=JSON.stringify(data);c.window.ProfileUI.stats([track],'tags');check(JSON.stringify(data)===before,'rendering does not mutate data');
const info=c.window.ProfileUI.queueInfo([track],0);check(info.includes('1 / 1')&&!info.includes('10s')&&!info.includes('Artist, Joint'),'preview only name and order');check(info.includes('Track &lt;one&gt;'),'preview title escaped');check(c.window.ProfileUI.queueInfo([])===''&&c.window.ProfileUI.queueInfo([track])==='','no preview caption before playback');
Object.assign(c,{$:c.window.SongRankerUI.$,main,songs:data.songs,artists:data.artists,albums:data.albums,tags:data.tags,DB:data,byId:(rows,id)=>rows.find(r=>Number(r.id)===Number(id)),normal:s=>String(s).toLowerCase(),records:type=>data[type],linkedSongs:(_type,item)=>data.songs.filter(s=>item.song_ids.includes(s.id)),properAlbum:a=>!!a&&!a.single,colour:c.window.SongRankerUI.entityColour,esc,urlFor,stat,available,metadata:()=>'<a class="artist">Artist</a>',tagLinks:()=>'',profileTags:()=>'',mediaButton:()=>'<button data-audio="song-audio"></button>',compactArt:()=>'<span class="small-art"></span>',artwork:()=>'<span class="art-wrap"></span>',renderSongHistory:()=>calls.push('history'),attachPlayers:()=>calls.push('players'),renderProfileTracks:()=>calls.push('tracks'),bindAlbumAudio:()=>calls.push('album-audio'),trackOrder:(a,b)=>a.id-b.id});
c.renderSong();check(main.innerHTML.indexOf('profile-key-stats')<main.innerHTML.indexOf('song-sections'),'key stats above modes');check(calls.includes('players')&&calls.includes('history'),'song audio/history bindings preserved');check(!main.innerHTML.includes('profile-preview-note')&&!main.innerHTML.includes('<details'),'song caption removed and history visible');check(!main.innerHTML.includes('profile-tag-list'),'song tags remain unrestricted');
for(const [type,item] of [['artists',artist],['albums',album],['tags',tag]]){
 nodes['#profile-data']={textContent:JSON.stringify({kind:type,name:item.name})};c.renderProfile();const html=main.innerHTML;
 check(/class="profile-copy"><h1/.test(html),'entity name inside metadata column');check((html.match(/<h1/g)||[]).length===1,'one profile heading');check(!html.includes('<details'),'collection data and albums visible');check(html.indexOf('id="album-player-info"')<html.indexOf('<audio id="album-audio"'),'preview caption inside cover player');
 check(html.includes('aria-label="Previous '+(type==='artists'?'artist':type==='albums'?'album':'tag')+' preview"'),'labelled skip controls');
 check(c.albumPlayer.queue.length===1&&c.albumPlayer.index===-1,'queue remains unstarted');
 check(html.includes('profile-tag-list')===(type!=='tags'),'only artist/album tags use two-row list');
 if(type==='albums')check(html.includes('Artist, Joint'),'whole collaborator name retained');
 if(type==='tags')check(html.includes('# Tag &lt;one&gt;')&&html.includes('Description &lt;safe&gt;'),'tag title and description inside hero');
}
const tagRows=[{id:1,tag_ids:[2,2,1]},{id:2,tag_ids:[2,3]},{id:3,tag_ids:[2]}];
const tagHTML=c.window.ProfileUI.tags([...tagRows,tagRows[0]],[{id:1,name:'Alpha'},{id:2,name:'Zulu'},{id:3,name:'Beta'}]);
check(tagHTML.indexOf('# Zulu')<tagHTML.indexOf('# Alpha')&&tagHTML.indexOf('# Alpha')<tagHTML.indexOf('# Beta'),'tags ranked by matching songs then name');
check(tagHTML.includes('Zulu · 3 matching songs')&&tagHTML.includes('Alpha · 1 matching songs'),'tag counts deduplicate songs and repeated tag IDs');
const chips={clientWidth:400,children:[0,0,44,44,88].map(offsetTop=>({offsetTop,hidden:false}))};
c.window.ProfileUI.fitTagRows(chips);check(chips.children.map(x=>x.hidden).join() === 'false,false,false,false,true','only two tag rows');
chips.children.forEach((chip,index)=>chip.offsetTop=index<3?0:44);c.window.ProfileUI.fitTagRows(chips);check(chips.children.every(x=>!x.hidden),'wider tag area restores relevant tags');
// Overall inserts after the four-stat group, including loading/error paths.
let insertion='';nodes['.profile-key-stats']={after(node){insertion='stats';nodes.placeholder=node}};
nodes['.song-profile']={after(){insertion='hero'}};
const row={id:1,name:'Track',score:60,evidence:50,mode_count:2,contributions:[]};
c.window.Overall.bindUI({records:type=>data[type],profile:()=>({type:'tags',item:tag}),api:async()=>({entities:{songs:[row],artists:[row],albums:[row],tags:[row]}})});
(async()=>{
 for(const page of ['song','artist','album','tag']){await c.window.Overall.mount(page);check(insertion==='stats','Overall mounts below key stats for '+page);check(nodes.placeholder.outerHTML.includes('id="overall-profile"'),'Overall details card mounted');check(nodes.placeholder.outerHTML.includes('Mode balance'),'Overall dropdown preserved');}
 c.window.Overall.bindUI({api:async()=>{throw Error('Temporary error')},records:type=>data[type]});await c.window.Overall.mount('song');check(insertion==='stats'&&nodes.placeholder.innerHTML.includes('Retry'),'Overall error/retry remains below stats');
 console.log(count+' profile assertions passed');
})().catch(error=>{console.error(error);process.exitCode=1});
