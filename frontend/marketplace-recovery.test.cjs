const {test}=require('node:test'),assert=require('node:assert/strict')
const {harness,text}=require('./dev/component-harness.cjs')
const failure={code:'network_error',message:'The transfer could not reach the server. Check the connection and retry.'}
function card(meta={}) {const h=harness('pages/Marketplace.tsx',{'@/lib/download-failure':harness('lib/download-failure.ts').exports}, {},['ModelCard']);return h.render('ModelCard',{model:{id:'one',kind:'local_file',stage_type:'stt',display_name:'Fixture',status:'error',meta},isActive:false,mp:{progress:{}}})}
test('model card renders a persisted safe failure after refresh',()=>{
 assert.match(text(card({download_error:failure})),/Check the connection/)
})
test('legacy or malformed model failure stays actionable',()=>{
 assert.match(text(card({download_error:'bad'})),/transfer did not finish/)
})

const {nodes,button,flush}=require('./dev/component-harness.cjs')
function dialogFixture() {
 let calls=0,reject=false
 const operation=async()=>{calls++;if(reject)throw Error('SENTINEL_SECRET');return {ok:false,message:'SENTINEL_SECRET'}}
 const mp={addLocal:operation,addCloud:operation,addLocalApi:operation,refresh:async()=>{}}
 const h=harness('pages/Marketplace.tsx',{'@/lib/api':{bridge:{addAirllmModel:operation}}},{},['AddModelDialog'])
 return {render:()=>h.render('AddModelDialog',{stageType:'translation',mp,open:true,onOpenChange(){}}),calls:()=>calls,reject(){reject=true}}
}
test('all category Add Model tabs report blank required fields without bridge calls',async()=>{
 for(const label of ['Download & Install','Add Cloud Model','Add Local Service','Add AirLLM Model']) {
  const f=dialogFixture();let tree=f.render();await button(tree,label).props.onClick();tree=f.render()
  assert.match(text(tree),/Enter a display name/);assert.equal(f.calls(),0)
  assert.ok(nodes(tree).some(n=>n.props?.['aria-invalid']===true))
 }
})
test('rejected local submission clears busy and never renders exception text',async()=>{
 const f=dialogFixture();let tree=f.render()
 nodes(tree).find(n=>n.props?.placeholder==='Display name').props.onChange({target:{value:'Fixture'}})
 nodes(tree).find(n=>n.props?.placeholder?.startsWith('Model URL')).props.onChange({target:{value:'https://example.test/model'}})
 tree=f.render();f.reject();try {await button(tree,'Download & Install').props.onClick()}catch{}
 await flush();tree=f.render();assert.equal(button(tree,'Download & Install')?.props.disabled,false)
 assert.match(text(tree),/Failed to start download/);assert.doesNotMatch(text(tree),/SENTINEL_SECRET/)
})

test('failed local card offers retry without changing its identity',()=>{
 const h=harness('pages/Marketplace.tsx',{'@/lib/download-failure':harness('lib/download-failure.ts').exports},{},['ModelCard']);let id
 const tree=h.render('ModelCard',{model:{id:'one',kind:'local_file',stage_type:'stt',display_name:'Fixture',status:'error',meta:{}},isActive:false,mp:{progress:{},retry: x=>{id=x}}})
 assert.ok(button(tree,'Retry download'));button(tree,'Retry download').props.onClick();assert.equal(id,'one')
})
function hookFixture(){
 const events=new Map();let rows=[{id:'one',status:'downloading',meta:{download_attempt_id:'new'}}],starts=0
 const bridge={listModels:async()=>rows,getActiveModels:async()=>({}),retryModelDownload:async()=>{starts++;return {ok:true}}}
 const h=harness('lib/use-marketplace.ts',{'@/lib/api':{bridge},'@/lib/events':{subscribe(n,fn){events.set(n,fn);return()=>events.delete(n)}},'./use-confirm':{confirmAction:async()=>true},'./deletion-preview':{}})
 return {h,events,render:()=>h.render('useMarketplace','stt'),starts:()=>starts,setRows(value){rows=value}}
}
test('stale attempt progress cannot update a retried model',async()=>{
 const f=hookFixture();f.render();f.h.effects();await flush();f.render()
 f.events.get('model_download_progress')({modelId:'one',attemptId:'old',percent:99})
 assert.equal(f.render().progress.one,undefined)
 f.events.get('model_download_progress')({modelId:'one',attemptId:'new',percent:20})
 assert.equal(f.render().progress.one.percent,20)
 f.h.unmount();assert.equal(f.events.size,0)
})
test('two immediate UI retries call the bridge once',async()=>{
 const f=hookFixture();let hook=f.render();f.h.effects();await flush();hook=f.render()
 assert.equal(typeof hook.retry,'function')
 await Promise.all([hook.retry('one'),hook.retry('one')]);assert.equal(f.starts(),1)
 f.h.unmount()
})

test('resolved submission failure hides unexpected provider details',async()=>{
 const f=dialogFixture();let tree=f.render()
 nodes(tree).find(n=>n.props?.placeholder==='Display name').props.onChange({target:{value:'Fixture'}})
 nodes(tree).find(n=>n.props?.placeholder?.startsWith('Model URL')).props.onChange({target:{value:'https://example.test/model'}})
 await button(f.render(),'Download & Install').props.onClick()
 assert.doesNotMatch(text(f.render()),/SENTINEL_SECRET/)
})

test('retry terminal during initial refresh reconciles persisted result',async()=>{
 const events=new Map();let rows=[{id:'one',status:'error',meta:{download_attempt_id:'A'}}],gate=null
 const bridge={listModels:async()=>rows.map(x=>({...x})),getActiveModels:()=>gate?new Promise(resolve=>{gate.push(resolve)}):Promise.resolve({}),retryModelDownload:async()=>{rows=[{id:'one',status:'downloading',meta:{download_attempt_id:'B'}}];return {ok:true,model:rows[0]}}}
 const h=harness('lib/use-marketplace.ts',{'@/lib/api':{bridge},'@/lib/events':{subscribe(n,fn){events.set(n,fn);return()=>{}}},'./use-confirm':{confirmAction:async()=>true},'./deletion-preview':{}})
 let hook=h.render('useMarketplace','stt');h.effects();await flush();hook=h.render('useMarketplace','stt')
 gate=[];const running=hook.retry('one');await flush()
 rows=[{id:'one',status:'error',meta:{download_attempt_id:'B'}}];events.get('model_download_error')({modelId:'one',attemptId:'B'});await flush()
 const waiting=gate;gate=null;waiting.forEach(resolve=>resolve({}));await running;await flush()
 assert.equal(h.render('useMarketplace','stt').models[0].status,'error');h.unmount()
})

test('invalid service JSON opens and focuses the configuration field',async()=>{
 const f=dialogFixture();let tree=f.render()
 for(const [label,value] of [['Display name','Fixture'],['Service base URL','https://example.test']]){
  const tab=nodes(tree).find(n=>n.type==='TabsContent' && n.props?.value==='localapi');const input=nodes(tab).find(n=>n.props?.['aria-label']===label);assert.ok(input,label);input.props.onChange({target:{value}})
 }
 let focused=0;const textarea=nodes(tree).find(n=>n.props?.['aria-label']==='Local service configuration')
 textarea.props.onChange({target:{value:'[]'}});if(textarea.props.ref)textarea.props.ref({focus(){focused++},closest(){return {open:false}}})
 await button(f.render(),'Add Local Service').props.onClick();tree=f.render()
 assert.equal(nodes(tree).find(n=>n.props?.['aria-label']==='Local service configuration').props['aria-invalid'],true)
 assert.equal(focused,1);assert.ok(nodes(tree).some(n=>n.type==='details'&&n.props.open));assert.equal(f.calls(),0)
})

function quickFixture(){
 let calls=0,reject=false
 const operation=async()=>{calls++;if(reject)throw Error('SENTINEL');return {ok:false,message:'SENTINEL'}}
 const h=harness('pages/Marketplace.tsx',{'@/lib/api':{bridge:{addLocalModel:operation,addCloudModel:operation,addLocalApiModel:operation,detectModelType:async()=>{throw Error('SENTINEL')}}}},{},['QuickAddDialog'])
 const render=()=>h.render('QuickAddDialog')
 return {h,render,calls:()=>calls,reject(){reject=true},source(value){nodes(render()).find(n=>n.type==='Tabs').props.onValueChange(value)},fill(placeholder,value){nodes(render()).find(n=>n.props?.placeholder===placeholder).props.onChange({target:{value}})}}
}
test('actual auto-detect Quick Add validates each required-field boundary',async()=>{
 for(const source of ['local','cloud','localapi']){
  const f=quickFixture();f.source(source);await button(f.render(),'Add Model').props.onClick()
  assert.match(text(f.render()),/Enter a display name/)
  f.fill('Display name','Fixture');await button(f.render(),'Add Model').props.onClick()
  assert.match(text(f.render()),source==='local'?/Enter a model URL/:/Enter an API base URL/)
  assert.equal(f.calls(),0)
 }
})
test('actual Quick Add invalid JSON opens and focuses configuration',async()=>{
 for(const invalid of ['[]','{']){
  const f=quickFixture();f.source('localapi');f.fill('Display name','Fixture');f.fill('Base URL (e.g. http://localhost:11434)','http://localhost:11434')
  let tree=f.render(),focus=0;const input=nodes(tree).find(n=>n.props?.['aria-label']==='Quick Add service configuration')
  input.props.onChange({target:{value:invalid}});input.props.ref?.({focus(){focus++},closest(){return {open:false}}})
  await button(f.render(),'Add Model').props.onClick();tree=f.render()
  assert.equal(nodes(tree).find(n=>n.props?.['aria-label']==='Quick Add service configuration').props['aria-invalid'],true)
  assert.ok(nodes(tree).some(n=>n.type==='details'&&n.props.open));assert.equal(focus,1);assert.equal(f.calls(),0)
 }
})
test('actual Quick Add rejected request clears busy and hides provider details',async()=>{
 const f=quickFixture();f.fill('Display name','Fixture');f.fill('Model URL (Hugging Face link, .zip, .pth, etc.)','https://example.test/model');f.reject()
 try{await button(f.render(),'Add Model').props.onClick()}catch{}
 assert.equal(button(f.render(),'Add Model')?.props.disabled,false);assert.match(text(f.render()),/could not be added/);assert.doesNotMatch(text(f.render()),/SENTINEL/)
})

test('actual Quick Add detection rejection releases Detect button',async()=>{
 const f=quickFixture();f.fill('Model URL (Hugging Face link, .zip, .pth, etc.)','https://example.test/model')
 try{await button(f.render(),'Detect').props.onClick()}catch{}
 assert.equal(button(f.render(),'Detect')?.props.disabled,false);assert.match(text(f.render()),/choose the stage manually/);assert.doesNotMatch(text(f.render()),/SENTINEL/)
})

test('interrupted transfer card explains restart and offers retry',()=>{
 const tree=card({download_error:{code:'interrupted'}})
 assert.match(text(tree),/interrupted/);assert.ok(button(tree,'Retry download'))
})
