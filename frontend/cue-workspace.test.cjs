const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript')
function harness(file,imports={}) {
  const states=[],effects=[],pending=[];let cursor=0
  const react={
    useState(initial){const i=cursor++;if(!(i in states))states[i]=typeof initial==='function'?initial():initial
      return[states[i],v=>{states[i]=typeof v==='function'?v(states[i]):v}]},
    useRef(initial){const i=cursor++;if(!(i in states))states[i]={current:initial};return states[i]},
    useId(){return `test-${cursor++}`},
    useEffect(callback,deps){const i=cursor++,old=effects[i]
      if(!old||deps.some((v,j)=>v!==old.deps[j])){effects[i]={deps,cleanup:old?.cleanup}
        pending.push(()=>{effects[i].cleanup?.();effects[i].cleanup=callback()})}},
  }
  const filename=path.resolve(__dirname,'src',file),module={exports:{}}
  const code=ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText
  vm.runInNewContext(code,{module,exports:module.exports,setTimeout,clearTimeout,
    require(name){if(name==='react')return react;if(name in imports)return imports[name]
      if(name.startsWith('@/')||name.startsWith('./'))return new Proxy({},{get:(_,key)=>key})
      return require(name)}},{filename})
  return{render(props){cursor=0;return Object.values(module.exports)[0](props)},
    effects(){while(pending.length)pending.shift()()},unmount(){effects.forEach(e=>e?.cleanup?.())}}
}
function nodes(t){if(t==null||typeof t!=='object')return[];if(Array.isArray(t))return t.flatMap(nodes);return[t,...nodes(t.props?.children)]}
function text(t){if(t==null||typeof t==='boolean')return'';if(typeof t!=='object')return String(t);return Array.isArray(t)?t.map(text).join(''):text(t.props?.children)}
function button(t,label){return nodes(t).find(n=>n.props?.onClick&&(n.props['aria-label']===label||text(n)===label))}
const flush=async()=>{for(let i=0;i<30;i++)await Promise.resolve()}
const cue=(n,overrides={})=>({cue_id:`cue-${n}`,start:n,end:n+1,available_seconds:1,source_text:`Original ${n}`,text:`Target ${n}`,candidate:null,accepted:null,...overrides})
const review={id:'review-a',name:'Scene',revision:1,duration:4,target_lang:'hi',cues:[cue(0,{accepted:{seconds:.8,fits:true}}),cue(1,{speaker:'Daughter'}),cue(2),cue(3)]}
function fixture(overrides={}){const h=harness('components/shared/CueTranscript.tsx'),selected=[]
  return{...h,selected,props:{review,selectedIndex:0,disabled:false,showAccepted:false,onlyUnassigned:false,onSelect:i=>selected.push(i),...overrides}}}
function search(f,q){const t=f.render(f.props);nodes(t).find(n=>n.props?.type==='search').props.onChange({target:{value:q}});return f.render(f.props)}
test('search finds original, target or character and preserves selected cue',()=>{
  for(const q of ['original 2','target 2','daughter']){const f=fixture(),t=search(f,q)
    assert.ok(text(t).includes(q==='daughter'?'Target 1':'Target 2'));assert.ok(!text(t).includes('Target 3'))
    assert.ok(text(t).includes('Target 0'));assert.deepEqual(f.selected,[]);assert.ok(nodes(t).some(n=>n.type==='table'))}})
test('next unresolved wraps and respects search and character filters',()=>{
  const f=fixture({selectedIndex:3});button(f.render(f.props),'Next unresolved line').props.onClick();assert.deepEqual(f.selected,[1])
  const g=fixture({selectedIndex:3});button(search(g,'target 2'),'Next unresolved line').props.onClick();assert.deepEqual(g.selected,[2])
  const k=fixture({review:{...review,speaker_references:['Daughter']},onlyUnassigned:true})
  button(k.render(k.props),'Next unresolved line').props.onClick();assert.deepEqual(k.selected,[2])})
test('busy or dirty state blocks navigation; empty search is explained',()=>{
  const f=fixture({disabled:true}),t=f.render(f.props);assert.equal(button(t,'Next unresolved line').props.disabled,true)
  assert.ok(nodes(t).filter(n=>n.props?.['data-cue-index']!==undefined).every(n=>n.props.disabled))
  const empty=search(fixture(),'absent wording');assert.match(text(empty),/No lines match/);assert.equal(button(empty,'Next unresolved line').props.disabled,true)})
test('accepted take and missing character reference are distinct statuses',()=>{
  const f=fixture({review:{...review,speaker_matching:true,speaker_references:[],cues:[cue(0,{accepted:{seconds:.8,fits:true}}),cue(1,{candidate:{seconds:2,fits:false}})]}})
  const t=f.render(f.props);assert.match(text(t),/Needs character reference/);assert.match(text(t),/Accepted take saved/)})
async function panelFixture(overrides={}) {
  const calls=[]
  const jobs={busy:false}
  const bridge={getDialogueReadiness:async()=>({ready:false,message:'No engine configured'}),
    listCueReviews:async()=>({ok:true,reviews:[{id:review.id,name:'Scene',created_at:1}]}),
    getCueReview:async()=>({ok:true,review:{...review,cues:[cue(0,{candidate:{seconds:.8,fits:true},accepted:{seconds:.8,fits:true}})]}}),
    getReviewSourceAudio:async(...args)=>{calls.push(['original',...args]);return{ok:true,audio:'data:audio/wav;base64,AAAA'}},
    getReviewAudio:async(...args)=>{calls.push([args[2]?'accepted':'candidate',...args]);return{ok:true,audio:'data:audio/wav;base64,BBBB'}},
    ...overrides}
  const h=harness('components/shared/CueReviewPanel.tsx',{'@/lib/api':{bridge},'@/lib/use-jobs':{useJobs:()=>jobs,runJobAction:async f=>f()}})
  const props={inputPath:null,params:{}}
  for(let i=0;i<4;i++){h.render(props);h.effects();await flush()}
  return{...h,props,calls,jobs}
}
test('audition labels and player identity distinguish original, candidate and accepted takes',async()=>{
  const f=await panelFixture();const identities=[]
  for(const [buttonLabel,audioLabel] of [['Listen to original line','Original line 1'],['Listen to new take','Candidate take for line 1'],['Listen to accepted take','Accepted take for line 1']]){
    button(f.render(f.props),buttonLabel).props.onClick();await flush()
    const player=nodes(f.render(f.props)).find(n=>n.type==='CueAudioPlayer')
    assert.equal(player?.props.label,audioLabel);identities.push(player.key)
  }
  assert.equal(new Set(identities).size,3,'equal-sized auditions must not share player identity')
  assert.deepEqual(f.calls.map(c=>c[0]),['original','candidate','accepted'])
})
test('unsaved wording disables transcript navigation and removes obsolete audition',async()=>{
  const f=await panelFixture();button(f.render(f.props),'Listen to original line').props.onClick();await flush()
  let tree=f.render(f.props);const field=nodes(tree).find(n=>n.type==='textarea')
  field.props.onChange({target:{value:'Corrected original'}});tree=f.render(f.props)
  assert.ok(!nodes(tree).some(n=>n.type==='CueAudioPlayer'))
  const transcript=nodes(tree).find(n=>n.type==='CueTranscript');assert.equal(transcript?.props.disabled,true)
})
test('panel filters keep the selected accepted or assigned line in the inspector',async()=>{
  const saved={...review,speaker_matching:true,speaker_references:['Daughter'],cues:[
    cue(0,{speaker:'Daughter',speaker_match:'confirmed',accepted:{seconds:.8,fits:true}}),cue(1),cue(2)]}
  const f=await panelFixture({getCueReview:async()=>({ok:true,review:saved})})
  const checkbox=label=>{
    const wrapper=nodes(f.render(f.props)).find(n=>n.type==='label'&&text(n).includes(label))
    return nodes(wrapper).find(n=>n.type==='input')
  }
  checkbox('Show accepted lines').props.onChange({target:{checked:true}})
  f.render(f.props);f.effects();await flush()
  nodes(f.render(f.props)).find(n=>n.type==='CueTranscript').props.onSelect(0)
  f.render(f.props);f.effects();await flush()
  checkbox('Show accepted lines').props.onChange({target:{checked:false}})
  f.render(f.props);f.effects();await flush()
  assert.equal(nodes(f.render(f.props)).find(n=>n.type==='CueTranscript').props.selectedIndex,0)
  checkbox('Only unresolved characters').props.onChange({target:{checked:true}})
  f.render(f.props);f.effects();await flush()
  assert.equal(nodes(f.render(f.props)).find(n=>n.type==='CueTranscript').props.selectedIndex,0)
})
test('selected transcript cue is brought into view after explicit navigation',()=>{
  const f=fixture(),calls=[];let tree=f.render(f.props)
  let selected=nodes(tree).find(n=>n.props?.['aria-current']==='true')
  assert.ok(selected.props.ref,'selected row has a scroll target')
  const ref=selected.props.ref;ref.current={scrollIntoView:options=>calls.push(options.block)}
  f.effects();assert.deepEqual(calls,[], 'opening a review should not scroll the page')
  f.props={...f.props,selectedIndex:2};tree=f.render(f.props)
  selected=nodes(tree).find(n=>n.props?.['aria-current']==='true')
  ;selected.props.ref.current={scrollIntoView:options=>calls.push(options.block)}
  f.effects();assert.deepEqual(calls,['nearest'])
})
