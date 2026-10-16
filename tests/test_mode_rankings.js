/* Run with node tests/test_mode_rankings.js. No database or browser writes. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.resolve(__dirname,'..');
let assertions=0;function check(value,message){assert.ok(value,message);assertions++;}
const main={innerHTML:''},listeners={},body={dataset:{},classList:{add(){}},style:{setProperty(){}}};
const document={body,querySelector:()=>null,querySelectorAll:()=>[],addEventListener:(type,fn)=>(listeners[type]??=[]).push(fn)};
const context={window:{addEventListener(){}},document,location:{search:''},history:{replaceState(_a,_b,url){context.lastURL=url}},URLSearchParams,console,setTimeout,clearTimeout};
vm.createContext(context);for(const name of ['ui','special_modes','overall'])vm.runInContext(fs.readFileSync(path.join(root,'static/js/'+name+'.js'),'utf8'),context);
const records={songs:[],artists:[{id:1,name:'Artist, with comma',song_count:25}],albums:[{id:1,name:'Album',title:'Album',song_count:25},{id:2,name:'Single',title:'Single',single:true}],tags:[{id:1,name:'Tag',song_count:25}]};
for(let i=1;i<=25;i++)records.songs.push({id:i,name:'Song '+i,artist_ids:[1],tag_ids:[1],album_id:1,guess_attempts:i,guess_correct:i%2?i:0,shelf_attempts:i,shelf_order_right:i%2?i:0,shelf_order_pairs:i,correct:i%2?i:0,available_points:i,tournament_appearances:i,tournament_points:i/4,championships:i%3,podiums:i,tournament_wins:i,runner_ups:0,third_places:0});
const U={main,records:type=>records[type],properAlbum:r=>!r.single,colour:context.window.SongRankerUI.entityColour,urlFor:(type,r)=>'/'+type+'/'+r.id,artwork:()=>'<span class="art-wrap"></span>',rankGlow:(_i,_b,tone)=>'--glow-color:var(--'+tone+')',pageTone(){},rankingMetadata:(r,type)=>({html:'<a class="artist" href="/artists/1">Linked artist</a>',text:'Linked artist'}),api:async()=>({entities:Object.fromEntries(['songs','artists','albums','tags'].map(type=>[type,records[type].map((r,i)=>({...r,score:80-i,evidence:50,mode_count:3,eligible:!r.single,tested_tracks:3,track_count:25,group_confidence:50}))]))})};
context.window.SpecialModes.bindUI(U);context.window.Overall.bindUI(U);
async function click(data){for(const fn of listeners.click)await fn({target:{closest:()=>({dataset:data,hasAttribute:()=>false})}});}
(async()=>{
for(const mode of ['trivia','tournament','guesser','shelves'])for(const entity of ['songs','artists','albums','tags'])for(const bottom of [false,true]){
 context.location.search=`?entity=${entity}&view=${bottom?'bottom':'top'}&metric=points`;
 context.window.SpecialModes.renderModeRanking(mode,true);
 const html=main.innerHTML;
 check(html.includes('class="rank-links"'),'standard category navigation');check(!html.includes('data-special-metric'),'no metric tabs');
 check(html.includes(`aria-pressed="true"`),'range announced');check(!context.lastURL.includes('metric='),'old metric normalised');
 check(html.includes('entity=tags'),'Tags category present');
 check(html.includes('--category-color:var(--tag)'),'category glow uses tag colour');
 if(mode==='tournament'&&entity==='tags')check(html.includes('81.25')&&html.includes('<small>Points</small>'),'tag points pool linked tracks');
 if(mode==='tournament'&&entity==='songs')check(html.includes(bottom?'0.25':'6.25')&&html.includes('<small>Points</small>'),'saved points order and decimal score');
 check(!html.includes('NaN')&&!html.includes('undefined'),'valid values');check((html.match(/<article/g)||[]).length===(entity==='songs'?20:1),'twenty rows and proper-album filter');
 check(html.includes('leader-votes'),'compact context');
 if(entity==='songs')check(html.includes('Linked artist'),'metadata delegated');
 await click({specialView:bottom?'top':'bottom'});check(context.lastURL.endsWith('view='+(bottom?'top':'bottom')),'range click updates URL');
}
for(const entity of ['songs','artists','albums','tags']){
 context.location.search=`?entity=${entity}`;await context.window.Overall.renderRankings(true);
 check(main.innerHTML.includes('href="/overall_rankings?entity=tags'),'Overall tag board preserved');check(!main.innerHTML.includes('undefined'),'Overall sparse records supported');
 if(entity==='songs'){check(main.innerHTML.includes('Linked artist'),'Overall uses catalogue metadata');check(main.innerHTML.includes('80.00%'),'Overall saved score');}
}
records.songs=[];records.artists=[];records.albums=[];records.tags=[];
for(const mode of ['trivia','tournament','guesser','shelves']){context.location.search='';context.window.SpecialModes.renderModeRanking(mode,true);check(main.innerHTML.includes('No results'),'empty state');}
await context.window.Overall.renderRankings(true);check(main.innerHTML.includes('No tested records'),'Overall empty state');
console.log(assertions+' ranking assertions passed');
})().catch(error=>{console.error(error);process.exitCode=1});
