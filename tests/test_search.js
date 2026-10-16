/* node tests/test_search.js — isolated read-only presentation fixtures. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
let count=0;const check=(value,label)=>{assert.ok(value,label);count++;};
const events={};
let document;
const makeNode=(id='',dataset={})=>({id,dataset,innerHTML:'',textContent:'',hidden:false,value:'',attrs:{},classes:new Set(),
 setAttribute(key,value){this.attrs[key]=value},getAttribute(key){return this.attrs[key]},
 classList:{remove(){},toggle(){}},focus(){document.activeElement=this},getBoundingClientRect:()=>({top:100,bottom:148,height:156}),
 closest(selector){return selector==='#search-sort-control'&&(id.startsWith('search-sort')||dataset.searchSort)?nodes['search-sort-control']:selector==='button'?this:null}
});
const nodes=Object.fromEntries(['catalog-results','result-count','search-more','search-tag-filter','catalog-query','search-sort','search-sort-control','search-sort-menu','search-sort-value'].map(id=>[id,makeNode(id)]));
const options=['score','name','random'].map((value,i)=>Object.assign(makeNode('',{searchSort:value}),{textContent:['Highest rating','Name A–Z','Random'][i]}));
nodes['search-sort-control'].contains=node=>!!node&&(node.id?.startsWith('search-sort')||options.includes(node));
const categories=['songs','artists','albums','tags'],buttons=categories.map(type=>({dataset:{searchType:type},classList:{toggle(){}},setAttribute(){},querySelector(){return this.counter??={textContent:''}}}));
const body={classList:{add(){}},dataset:{}};
document={body,querySelector:s=>nodes[s.slice(1)]||null,querySelectorAll:s=>s.includes('[data-search-type]')?buttons:s.includes('[role="option"]')?options:[],addEventListener:(e,f)=>(events[e]??=[]).push(f)};
const c={Math:Object.assign(Object.create(Math),{random:()=>0}),URLSearchParams,window:{innerHeight:800,addEventListener(){}},document,location:{search:''},history:{replaceState(_a,_b,url){c.url=url}},getComputedStyle:()=>({columnGap:'8'})};vm.createContext(c);
for(const file of ['ui','search'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/js/'+file+'.js'),'utf8'),c);
const S=c.window.SearchPage;
const full={championships:2,runner_ups:5,third_places:4,correct:3,available_points:3,guess_correct:2,guess_attempts:2,shelf_order_right:6,shelf_order_pairs:6,voting:{standard_wins:5,standard_losses:0,blind_wins:9,blind_losses:1}};
let b=S.achievementCandidates([full]);
check(b.length===6,'all six achievement modes');check(b[0].text.includes('2 titles'),'championship highest priority');check(b.filter(x=>x.mode==='tournament').length===1,'one podium badge');
check(S.achievementCandidates([{}]).length===0,'no activity no badge');
check(S.achievementCandidates([{correct:1,available_points:1,guess_correct:1,guess_attempts:1,shelf_order_right:5,shelf_order_pairs:5}]).length===0,'sample minimums');
check(S.achievementCandidates([{correct:9,available_points:10}])[0].text==='Trivia 90%','Trivia threshold inclusive');
check(S.achievementCandidates([{guess_correct:9,guess_attempts:10}])[0].text==='Guesser 90%','Guesser threshold inclusive');
check(S.achievementCandidates([{shelf_order_right:18,shelf_order_pairs:20}])[0].text==='Track order 90%','Shelves threshold inclusive');
check(S.achievementCandidates([{correct:9,available_points:10},{correct:0,available_points:10}]).length===0,'pooled rates, not best track');
check(S.achievementCandidates([{third_places:1}])[0].text.includes('third'),'bronze included');
check(S.achievementCandidates([{runner_ups:1,third_places:2}])[0].text.includes('runner-up'),'silver replaces bronze');
check(S.achievementCandidates([{voting:{standard_wins:3,standard_losses:2}}]).length===0,'ordinary voting omitted');
check(S.achievementCandidates([{guess_correct:8,guess_attempts:9,shelf_order_right:17,shelf_order_pairs:20,voting:{standard_wins:8,standard_losses:1,blind_wins:8,blind_losses:1}}]).length===0,'sub-90 percentages omitted');
check(S.achievementCandidates([{voting:{standard_wins:9,standard_losses:1,blind_wins:9,blind_losses:1}}]).length===2,'both voting badges at 90 percent');
const row={clientWidth:250,children:[120,100,80,50].map(width=>({hidden:false,getBoundingClientRect:()=>({width})}))};
S.fitBadgeRow(row);check(row.children.map(x=>x.hidden).join()==='false,false,true,true','whole badges in one row');
row.clientWidth=150;S.fitBadgeRow(row);check(row.children.filter(x=>!x.hidden).length===1,'phone shows highest badge');
row.clientWidth=600;S.fitBadgeRow(row);check(row.children.filter(x=>!x.hidden).length===3,'resize restores up to three');
const songs=Array.from({length:50},(_,i)=>({...full,id:i+1,name:(i===0?'Zed':'Track '+i)+' <test>',title:'Track',artist_ids:[1],album_id:1,tag_ids:[1],score:1500-i}));
const data={songs,artists:[{id:1,name:'Artist, Name',song_ids:songs.map(s=>s.id),score:1400}],albums:[{id:1,title:'Proper',name:'Proper',score:1500},{id:2,name:'Hidden single',single:true,score:1200}],tags:[{id:1,name:'Rock <&>',description:'Tag <description>',score:1500}]};
const U={main:{innerHTML:''},records:t=>data[t],related:q=>Object.fromEntries(categories.map(t=>[t,q==='absent'?[]:data[t]])),linkedSongs:(t,r)=>t==='songs'?[r]:songs,properAlbum:r=>!!r&&!r.single,rankingMetadata:()=>({html:'<a class="artist" href="/artist/Name">Artist, Name</a>',text:'Artist, Name'}),artwork:(_r,t)=>`<span class="art-wrap ${t==='artists'?'circle':''}"></span>`,urlFor:(t,r)=>'/'+t+'/'+r.id,pageTone:t=>body.dataset.tone=t};
const trigger=(event,target)=>events[event]?.forEach(fn=>fn({target,preventDefault(){}}));
const choose=value=>trigger('click',options.find(option=>option.dataset.searchSort===value));
const songIds=()=>[...nodes['catalog-results'].innerHTML.matchAll(/href="\/songs\/(\d+)"/g)].map(m=>Number(m[1]));
S.init(U);const randomFirst=songIds();check(nodes['search-sort-value'].textContent==='Random','empty search defaults random');check(randomFirst[0]!==1,'shuffle differs from highest rating with fixed random source');check(U.main.innerHTML.indexOf('id="result-count"')<U.main.innerHTML.indexOf('class="search-sort"'),'count before dropdown');
check((nodes['catalog-results'].innerHTML.match(/<article/g)||[]).length===40,'initial forty');check(!nodes['search-more'].hidden,'more available');check(U.main.innerHTML.includes('role="search"'),'labelled search form');
trigger('click',{closest:()=>({dataset:{},hasAttribute:k=>k==='data-search-more'})});check((nodes['catalog-results'].innerHTML.match(/<article/g)||[]).length===50,'load more');check(nodes['search-more'].hidden,'more ends');check(songIds().slice(0,40).join()===randomFirst.join(),'random prefix stable through load more');check(new Set(songIds()).size===50,'random load more no duplicates or omissions');
trigger('input',{id:'catalog-query',value:'test'});check(nodes['search-sort-value'].textContent==='Highest rating'&&songIds()[0]===1,'typing selects highest rating');
trigger('input',{id:'catalog-query',value:''});check(nodes['search-sort-value'].textContent==='Random'&&songIds().join()===randomFirst.join(),'clearing query restores stable random browsing');
for(const type of categories){
 trigger('click',{closest:()=>({dataset:{searchType:type},hasAttribute:()=>false})});
 const html=nodes['catalog-results'].innerHTML;check(html.includes('class="result-card'),'all categories card grid');check(!html.includes('<a class="result-card'),'card not nested link');check(html.includes('search-achievements'),'all categories achievements');check(html.includes('&lt;')||type!=='songs','escape entity names');check(body.dataset.tone===c.window.SongRankerUI.entityColour(type),'entity page tone');
 if(type==='albums')check(!html.includes('Hidden single'),'proper album only');
 if(type==='tags')check(html.includes('Tag &lt;description&gt;'),'tag description escaped');
}
trigger('click',{closest:()=>({dataset:{searchType:'songs'},hasAttribute:()=>false})});check(songIds().join()===randomFirst.join(),'category round trip preserves random ordering');
c.location.search='?q=test';S.init(U);check(nodes['search-sort-value'].textContent==='Highest rating'&&songIds()[0]===1,'query deep link defaults highest rating');
c.location.search='?sort=score';S.init(U);check(nodes['search-sort-value'].textContent==='Highest rating'&&songIds()[0]===1,'explicit empty-search rating sort retained');
c.location.search='?type=songs&tag=1&sort=name&q=test';S.init(U);check(c.url.includes('tag=1')&&c.url.includes('sort=name'),'deep link state');check(!nodes['search-tag-filter'].hidden,'tag filter preserved');
check(nodes['catalog-results'].innerHTML.match(/href="([^"]+)/)[1]==='/songs/2','name sort order');
choose('score');check(nodes['catalog-results'].innerHTML.indexOf('/songs/1"')<nodes['catalog-results'].innerHTML.indexOf('/songs/2'),'rating sort order');
trigger('click',{closest:()=>({dataset:{},hasAttribute:k=>k==='data-search-clear-tag'})});check(nodes['search-tag-filter'].hidden&&!c.url.includes('tag='),'clear tag scope');
let submitted=false;nodes['catalog-query'].value='absent';events.submit[0]({target:{id:'catalog-search'},preventDefault(){submitted=true}});check(submitted&&nodes['catalog-results'].innerHTML.includes('No songs found'),'keyboard submit');
trigger('input',{id:'catalog-query',value:'absent'});check(nodes['catalog-results'].innerHTML.includes('No songs found'),'helpful empty state');check(nodes['search-more'].hidden,'empty pagination');
// Exercise actual dropdown handlers with focus/ARIA fixtures.
const key=(target,value)=>{let prevented=false;events.keydown.forEach(fn=>fn({target,key:value,preventDefault(){prevented=true}}));return prevented;};
trigger('click',nodes['search-sort']);check(!nodes['search-sort-menu'].hidden&&nodes['search-sort'].attrs['aria-expanded']==='true','trigger opens styled menu');
check(document.activeElement===options[0],'selected option receives focus');
key(options[0],'ArrowDown');check(document.activeElement===options[1],'ArrowDown moves focus');
key(options[1],'End');check(document.activeElement===options[2],'End focuses last');
key(options[2],'Home');check(document.activeElement===options[0],'Home focuses first');
key(options[0],'r');check(document.activeElement===options[2],'letter navigation');
key(options[2],'Enter');check(nodes['search-sort-menu'].hidden&&document.activeElement===nodes['search-sort'],'selection closes and restores focus');
check(nodes['search-sort-value'].textContent==='Random'&&options[2].attrs['aria-selected']==='true','selection updates label and ARIA');
key(nodes['search-sort'],'ArrowDown');check(!nodes['search-sort-menu'].hidden,'arrow opens trigger');
check(key(options[2],'Escape')&&nodes['search-sort-menu'].hidden&&document.activeElement===nodes['search-sort'],'Escape returns to trigger');
trigger('click',nodes['search-sort']);trigger('click',{closest:()=>null});check(nodes['search-sort-menu'].hidden,'outside click dismisses');
trigger('click',nodes['search-sort']);key(options[2],'Tab');check(nodes['search-sort-menu'].hidden&&document.activeElement===nodes['search-sort'],'Tab prepares natural focus exit');
trigger('click',nodes['search-sort']);events.focusout[0]({target:options[2],relatedTarget:nodes['catalog-query']});check(nodes['search-sort-menu'].hidden,'moving focus outside dismisses');
trigger('click',nodes['search-sort']);key(options[2],'ArrowUp');check(document.activeElement===options[1],'ArrowUp moves focus');
key(options[1],' ');check(nodes['search-sort-value'].textContent==='Name A–Z'&&nodes['search-sort-menu'].hidden,'Space selects');
const classes=new Set();nodes['search-sort-control'].classList={remove:name=>classes.delete(name),toggle:(name,on)=>on?classes.add(name):classes.delete(name)};
nodes['search-sort'].getBoundingClientRect=()=>({top:400,bottom:448});c.window.innerHeight=500;
trigger('click',nodes['search-sort']);check(classes.has('opens-up'),'menu opens above when space below is tight');
key(options[1],'Escape');check(!classes.has('opens-up'),'closing clears upward position');
check(!U.main.innerHTML.includes('<select')&&U.main.innerHTML.includes('role="listbox"'),'custom listbox replaces native popup');
console.log(count+' search assertions passed');
