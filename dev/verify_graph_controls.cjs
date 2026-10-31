// Actual frontend module contracts; uses existing TypeScript/Node only.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const assert=require('node:assert/strict'),crypto=require('node:crypto');
const ts=require('../frontend/node_modules/typescript');
const root=path.resolve(__dirname,'..'),hashes={},checks=[];
const noop=()=>{};
const jsx=(type,props)=>({type,props});
const runtime={jsx,jsxs:jsx,Fragment:'Fragment'};
const graphAlerts=[];
const actions=load('frontend/src/lib/graph-actions.ts',{
  './use-confirm':{confirmAction:async options=>{graphAlerts.push(options);return false;}}});
function load(name,bindings={},globals={}) {
  const source=fs.readFileSync(path.join(root,name),'utf8');
  hashes[name]=crypto.createHash('sha256').update(source).digest('hex');
  const exports={};
  vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,
    target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText,
    {exports,require:key=>{if(!(key in bindings))throw Error('Unexpected dependency: '+key);return bindings[key];},console,...globals});
  return exports;
}
function find(tree,type) {
  if(!tree || typeof tree!=='object')return null;
  if(tree.type===type)return tree;
  for(const child of [tree.props?.children].flat(Infinity)){const result=find(child,type);if(result)return result;}
  return null;
}
function textContent(tree) {
  if(typeof tree==='string'||typeof tree==='number')return String(tree);
  if(!tree||typeof tree!=='object')return '';
  return [tree.props?.children].flat(Infinity).map(textContent).join(' ');
}
async function check(name,run){await run();checks.push({name,passed:true});}
async function drain(){for(let i=0;i<20;i++)await Promise.resolve();}
const graph=load('frontend/src/lib/graph-config.ts');
const rendered=[],warnings=[];
const config=load('frontend/src/lib/use-render-config.ts',{
  './preference-storage':{preferenceStorage:{getItem:()=>JSON.stringify({lang:'hi',sourceLanguage:'en',keepBg:false}),setItem:noop}},
  '@/lib/api':{bridge:{setNodeEnabled:async()=>({ok:false,message:'fixture publication rejection'})}},
  react:{useState:value=>[value,next=>rendered.push(next)],useEffect:fn=>fn()}},
  {window:{__reflow:{dispatch:(_event,payload)=>warnings.push(payload.message)}},console:{warn:noop}});
const stageMap=config.STAGE_NODE_MAP;
let cfg={...config.useRenderConfig()};
function project(node,settings=cfg){return graph.projectGraphNode(node,settings,1,[{code:'hi',name:'Hindi'}],
  'C:/fixture/source.mp4',stageMap);}
(async()=>{
  await drain();
  cfg={...rendered.at(-1)};
  await check('All mapped switches follow current render flags after a late saved graph load',()=>{
    for(const [id,key]of Object.entries(stageMap))for(const enabled of [false,true]){
      const original={id,enabled:!enabled,params:[]};
      const result=project(original,{...cfg,[key]:enabled});
      assert.equal(result.enabled,enabled);assert.equal(original.enabled,!enabled);
    }
  });
  await check('Unmapped fixed nodes preserve their own enabled state',()=>{
    assert.equal(project({id:'stt',enabled:true,params:[]}).enabled,true);
  });
  await check('Restored target, source filename and singleton voice remain projected',()=>{
    assert.equal(project({id:'translate',params:[{key:'lang',default:'English (en)'}]}).params[0].default,'Hindi (hi)');
    assert.equal(project({id:'input',params:[{key:'video_name'}]}).params[0].default,'source.mp4');
    assert.equal(project({id:'tts_rvc',params:[{key:'voice',default:'old'}]}).params[0].default,cfg.voice);
  });
  await check('Rejected restore produces a visible warning without losing the render setting',()=>{
    assert.equal(rendered.at(-1).keepBg,false);
    assert.ok(warnings.some(message=>message.includes('fixture publication rejection')));
  });
  await check('Rejected later graph mirror keeps the chosen future-job flag and reports it',async()=>{
    const before=warnings.length;config.updateConfig({keepBg:true});await drain();
    assert.equal(rendered.at(-1).keepBg,true);assert.equal(warnings.length,before+1);
  });
  const thrownWarnings=[];
  const throwing=load('frontend/src/lib/use-render-config.ts',{
    './preference-storage':{preferenceStorage:{getItem:()=>'{"keepBg":false}',setItem:noop}},
    '@/lib/api':{bridge:{setNodeEnabled:async()=>{throw Error('fixture transport failure');}}},
    react:{useState:value=>[value,noop],useEffect:fn=>fn()}},
    {window:{__reflow:{dispatch:(_event,payload)=>thrownWarnings.push(payload.message)}},console:{warn:noop}});
  await check('Transport rejection is caught and reported',async()=>{
    throwing.useRenderConfig();await drain();
    assert.ok(thrownWarnings.some(message=>message.includes('fixture transport failure')));
  });
  const renderState={status:'idle',activeStageId:null,isRunning:false,inputPath:null};
  const rawNodes=[{id:'separate',position:{x:0,y:0},data:{enabled:true,
    def:{id:'separate',enabled:true,params:[]}}},
    {id:'input',position:{x:0,y:0},data:{def:{id:'input',enabled:true,
      params:[{key:'video_name',default:'saved.mp4'}]}}}];
  const bindings={react:{useState:value=>[value,noop],useEffect:noop,useRef:value=>({current:value}),useCallback:fn=>fn},
    'react/jsx-runtime':runtime,'@xyflow/react':{ReactFlow:'ReactFlow',Background:'Background',Controls:'Controls',
      useNodesState:()=>[rawNodes,noop,noop],useEdgesState:()=>[[{id:'fixture',animated:false}],noop,noop]},'@xyflow/react/dist/style.css':{},
    '@/lib/api':{bridge:{}},'@/lib/graph-config':graph,'@/lib/graph-actions':actions,'@/lib/render-params':{buildRenderParams:()=>({})},
    '@/components/panels/StageNode':{StageNode:'StageNode'},'@/lib/use-render':{useRenderJob:()=>renderState},
    '@/lib/use-queue':{useQueue:()=>[{input_path:'C:/fixture/source.mp4'}]},
    '@/lib/use-render-config':{STAGE_NODE_MAP:stageMap,setStageFromNode:noop,updateConfig:noop,useRenderConfig:()=>cfg},
    '@/lib/use-confirm':{confirmAction:async()=>false},'@/lib/gauge-color':{loadGaugeColor:()=>''},
    '@/lib/eta':{formatDuration:()=>'',relativeSpeedPercent:()=>0,projectedLoadPercent:()=>null,jobMemoryBudget:()=>null},
    '@/lib/utils':{cn:()=>''}};
  for(const [module,names]of Object.entries({'ui/button':['Button'],'ui/card':['Card','CardContent'],
    'ui/progress':['Progress'],'ui/select':['Select','SelectContent','SelectItem','SelectTrigger','SelectValue'],
    'panels/RadialGauge':['RadialGauge'],'shared/HelpTooltip':['HelpTooltip']}))
    bindings['@/components/'+module]=Object.fromEntries(names.map(name=>[name,name]));
  await check('Actual Nodes component passes projected switch state to the graph',()=>{
    const nodes=load('frontend/src/pages/Nodes.tsx',bindings);
    const tree=find(nodes.NodesPage(),'ReactFlow');assert.ok(tree);
    assert.equal(tree.props.nodes[0].data.enabled,false);
    assert.equal(tree.props.nodes[0].data.def.enabled,false);
    assert.equal(rawNodes[0].data.enabled,true);
  });
  await check('Late graph definitions reflect current active stage and edge animation',()=>{
    const nodes=load('frontend/src/pages/Nodes.tsx',bindings);
    Object.assign(renderState,{activeStageId:'separate',isRunning:true});
    let tree=find(nodes.NodesPage(),'ReactFlow');
    assert.equal(tree.props.nodes[0].data.active,true);
    assert.equal(tree.props.edges[0].animated,true);
    Object.assign(renderState,{activeStageId:'translate',isRunning:false});
    tree=find(nodes.NodesPage(),'ReactFlow');
    assert.equal(tree.props.nodes[0].data.active,false);
    assert.equal(tree.props.edges[0].animated,false);
    assert.equal(rawNodes[0].data.active,undefined);
  });
  await check('Input node shows the current active file instead of the next pending job',()=>{
    const nodes=load('frontend/src/pages/Nodes.tsx',bindings);
    Object.assign(renderState,{isRunning:true,inputPath:'C:/fixture/active.mp4'});
    let tree=find(nodes.NodesPage(),'ReactFlow');
    assert.equal(tree.props.nodes[1].data.def.params[0].default,'active.mp4');
    Object.assign(renderState,{isRunning:false,inputPath:null});
    tree=find(nodes.NodesPage(),'ReactFlow');
    assert.equal(tree.props.nodes[1].data.def.params[0].default,'source.mp4');
  });
  await check('Progress passes its displayed value to the accessible primitive',()=>{
    const progress=load('frontend/src/components/ui/progress.tsx',{
      react:{},'react/jsx-runtime':runtime,'radix-ui':{Progress:{Root:'ProgressRoot',Indicator:'ProgressIndicator'}},
      '@/lib/utils':{cn:()=>''}});
    for(const value of [0,25,100]) {
      const root=progress.Progress({value});assert.equal(root.props.value,value);
      assert.equal(find(root,'ProgressIndicator').props.style.transform,`translateX(-${100-value}%)`);
    }
  });
  await check('Assets shows pending cancellation rather than the last rendering message',()=>{
    const session={busy:true,paused:true,render:{status:'stopping',statusText:'Stopping; waiting for exit'},
      queue:[{id:'one',input_path:'one.mp4',status:'processing',progress:25,status_text:'Old running message'}]};
    const assets=load('frontend/src/pages/Assets.tsx',{
      'react/jsx-runtime':runtime,'lucide-react':{Store:'Store',AlertTriangle:'AlertTriangle',X:'X'},
      '@/components/ui/button':{Button:'Button'},
      '@/components/ui/card':Object.fromEntries(['Card','CardContent','CardHeader','CardTitle'].map(name=>[name,name])),
      '@/lib/api':{bridge:{}},'@/lib/use-queue':{},'@/lib/use-jobs':{useJobs:()=>session},
      '@/lib/use-confirm':{confirmAction:noop},'@/lib/deletion-preview':{}});
    let text=textContent(assets.AssetsPage({onNavigate:noop}));
    assert.match(text,/Stopping/);assert.match(text,/waiting for exit/);assert.doesNotMatch(text,/Old running message/);
    session.busy=false;session.render.status='idle';session.queue[0].status='cancelled';
    text=textContent(assets.AssetsPage({onNavigate:noop}));assert.match(text,/Cancelled/);
    assert.doesNotMatch(text,/waiting for exit/);
  });
  await check('Graph action failures report rejection or uncertain transport outcome',async()=>{
    assert.equal(await actions.requestGraphChange(async()=>({ok:false,message:'fixture rejected'})),null);
    assert.equal(graphAlerts.at(-1).description,'fixture rejected');
    assert.equal(await actions.requestGraphChange(async()=>{throw Error('fixture disconnected');}),null);
    assert.match(graphAlerts.at(-1).description,/backend may have received/);
    assert.equal(graphAlerts.at(-1).alertOnly,true);
    const result={ok:true,nodeId:'tts_rvc_2'};
    assert.equal(await actions.requestGraphChange(async()=>result),result);
  });
  function harness(bridgeOverrides={},voiceCount=1) {
    const effects=[],updates=[],pending=[],alerts=[];
    let nodeState=Array.from({length:voiceCount},(_,index)=>{
      const id=index===0?'tts_rvc':`tts_rvc_${index+1}`;
      return {id,position:{x:0,y:0},data:{def:{id,enabled:true,
        params:[{key:'voice',default:'actor-a'}]}}};});
    const fakeBridge={listLanguages:async()=>[],getHardwareSnapshot:async()=>({devices:[],default_device_id:'cpu'}),
      estimateJobAllDevices:async()=>({}),getGraphDefinition:()=>new Promise((resolve,reject)=>pending.push({resolve,reject})),
      setNodeEnabled:async()=>{throw Error('toggle disconnected');},setNodeParam:async()=>{throw Error('param disconnected');},
      addNodeInstance:async()=>({ok:true}),removeNodeInstance:async()=>({ok:true}),setNodePosition:async()=>{throw Error('position disconnected');},
      ...bridgeOverrides};
    const localBindings={...bindings,react:{...bindings.react,useEffect:fn=>effects.push(fn)},
      '@xyflow/react':{...bindings['@xyflow/react'],useNodesState:()=>[nodeState,value=>{
        nodeState=typeof value==='function'?value(nodeState):value;},noop]},
      '@/lib/api':{bridge:fakeBridge},
      '@/lib/use-render-config':{...bindings['@/lib/use-render-config'],updateConfig:value=>updates.push(value)},
      '@/lib/use-confirm':{confirmAction:async options=>{alerts.push(options);return false;}}};
    const page=load('frontend/src/pages/Nodes.tsx',localBindings);
    const flow=find(page.NodesPage(),'ReactFlow');
    const cleanups=effects.map(fn=>fn());
    return {flow,pending,updates,alerts,cleanups,nodes:()=>nodeState};
  }
  const definition=voice=>({nodes:[{id:'tts_rvc',enabled:true,x:0,y:0,
    params:[{key:'voice',default:voice}]}],edges:[]});
  await check('Actual node callbacks catch transport errors without changing shared choices',async()=>{
    const h=harness({removeNodeInstance:async()=>{throw Error('remove disconnected');}});
    h.pending[0].resolve(definition('actor-a'));await drain();
    const data=h.nodes()[0].data,before=graphAlerts.length;
    await data.onToggle('subtitles',false);await data.onParamChange('tts_rvc','voice','actor-b');
    await data.onDuplicate('tts_rvc');await data.onRemove('tts_rvc_2');
    assert.equal(graphAlerts.length,before+4);assert.equal(h.updates.length,0);
    assert.equal(h.nodes()[0].data.def.params[0].default,'actor-a');
    await h.flow.props.onNodeDragStop(null,{id:'tts_rvc',position:{x:1,y:1}});
    assert.equal(graphAlerts.at(-1).title,'Layout could not be saved');
    assert.equal(h.pending.length,2);h.pending[1].resolve(definition('actor-a'));await drain();
  });
  await check('Newest graph reload wins and unmounted pending loads are ignored',async()=>{
    const h=harness();h.pending[0].resolve(definition('actor-a'));await drain();
    const data=h.nodes()[0].data;
    await data.onRemove('tts_rvc_2');await data.onRemove('tts_rvc_3');
    h.pending[2].resolve(definition('latest'));await drain();
    h.pending[1].resolve(definition('stale'));await drain();
    assert.equal(h.nodes()[0].data.def.params[0].default,'latest');
    await data.onRemove('tts_rvc_4');
    for(const cleanup of h.cleanups)if(typeof cleanup==='function')cleanup();
    h.pending[3].resolve(definition('after-unmount'));await drain();
    assert.equal(h.nodes()[0].data.def.params[0].default,'latest');
  });
  await check('Current graph load failure is reported while a stale failure is ignored',async()=>{
    const h=harness();h.pending[0].reject(Error('fixture read failed'));await drain();
    assert.equal(h.alerts.length,1);assert.equal(h.alerts[0].title,'Graph could not be loaded');
    const fresh=harness();fresh.pending[0].resolve(definition('actor-a'));await drain();
    const data=fresh.nodes()[0].data;
    await data.onRemove('tts_rvc_2');await data.onRemove('tts_rvc_3');
    fresh.pending[1].reject(Error('stale read failed'));
    fresh.pending[2].resolve(definition('latest'));await drain();
    assert.equal(fresh.alerts.length,0);
  });
  await check('Removing an extra voice returns shared selection to the remaining singleton',async()=>{
    const h=harness({},2);
    const multi=definition('remaining-actor');
    multi.nodes.push({...multi.nodes[0],id:'tts_rvc_2'});
    h.pending[0].resolve(multi);await drain();
    assert.equal(h.updates.length,0);
    await h.nodes()[1].data.onRemove('tts_rvc_2');
    h.pending[1].resolve(definition('remaining-actor'));await drain();
    assert.equal(h.nodes().length,1);assert.equal(h.updates.at(-1).voice,'remaining-actor');
  });
  const mapper=load('frontend/src/lib/render-params.ts',{'@/lib/use-render-config':config});
  await check('Projected optional choices match the actual render parameter mapper',()=>{
    for(const enabled of [false,true]){
      const choice={...cfg,keepBg:enabled,lipsync:enabled,enhance:enabled,includeSubtitles:enabled,contentFilter:enabled};
      const params=mapper.buildRenderParams(choice,'cpu','video','video_dub');
      for(const [node,field]of Object.entries({separate:'keep_bg',lipsync:'lipsync',enhance:'enhance',
        subtitles:'include_subtitles',content_filter:'content_filter'}))
        assert.equal(project({id:node,enabled:!enabled,params:[]},choice).enabled,params[field]);
    }
  });
  const receipt={passed:true,checks,source_sha256:hashes};
  const receiptPath=process.argv[2]??'docs/validation/2026-10-10-graph-controls-frontend-contracts.json';
  fs.writeFileSync(path.join(root,receiptPath),JSON.stringify(receipt,null,2));
  console.log(JSON.stringify(receipt,null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
