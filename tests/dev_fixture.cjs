/* Shared rendered-shell fixture; navigation data comes from the production registry. */
const fs=require('node:fs'),path=require('node:path');
module.exports=function installDevShell(w,view='overview') {
  const d=w.document,context=JSON.parse(fs.readFileSync(path.join(__dirname,'../songranker/developer/navigation.json'),'utf8'));
  context.view=view||'overview';
  d.querySelector('#main').innerHTML='<script id="dev-context" type="application/json"></script><div class="dev-shell"><nav id="dev-section-nav"></nav><div id="dev-unsaved" hidden></div><div id="dev-workspace" class="dev-workspace"><section id="dev-main"><div id="loading"></div></section><aside id="dev-editor-slot"></aside></div></div>';
  d.querySelector('#dev-context').textContent=JSON.stringify(context);
  if(!d.querySelector('#dev-page-menu'))d.body.insertAdjacentHTML('afterbegin','<nav id="dev-page-menu"></nav>');
  w.HTMLDialogElement.prototype.show=function(){this.open=true;};
  w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
};
