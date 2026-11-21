const {test}=require('node:test'),assert=require('node:assert/strict')
const {harness,nodes,text,button}=require('./dev/component-harness.cjs')
function tourFixture({late=false,origin="dashboard",last=false}={}) {
 const handlers=new Map(),timers=new Map();let next=0,ended=0,focused=0,scrolled=0,ready=!late,mutation,active=true,page=origin
 const rect={left:300,top:1392,right:600,bottom:1492,width:300,height:100}
 const target={getBoundingClientRect:()=>rect,scrollIntoView(){scrolled++;rect.top=100;rect.bottom=200}}
 const trigger={focus(){focused++},isConnected:true}
 const window={innerWidth:1200,innerHeight:761,addEventListener(n,f){handlers.set(n,f)},removeEventListener(n,f){if(handlers.get(n)===f)handlers.delete(n)}}
 const document={activeElement:trigger,documentElement:{},querySelector:selector=>selector==='[data-tour="replay-tour"]' ? (page==='settings'?{focus(){focused++}}:null) : ready?target:null,addEventListener:window.addEventListener,removeEventListener:window.removeEventListener}
 const step={target:'dashboard-estimate',title:'Estimate',description:'Fixture'}
 const h=harness('components/onboarding/ProductTour.tsx',{'@/lib/tour-layout':harness('lib/tour-layout.ts').exports,'@/lib/use-tour':{useTour:()=>({active,stepIndex:last?8:3,step,totalSteps:9}),endTour(){ended++;active=false},nextTourStep(){ended++;active=false},prevTourStep(){}}},
  {window,document,MutationObserver:class{constructor(fn){mutation=fn}observe(){}disconnect(){mutation=null}},ResizeObserver:class{observe(){}disconnect(){}},requestAnimationFrame(fn){const n=++next;timers.set(n,fn);return n},cancelAnimationFrame(n){timers.delete(n)},setTimeout(fn){const n=++next;timers.set(n,fn);return n},clearTimeout(n){timers.delete(n)}})
 const navigate=next=>{page=next}
 const render=()=>h.render('ProductTour',{currentPage:page,onNavigate:navigate})
 let tree=render();h.effects();for(const [n,fn] of [...timers]){timers.delete(n);fn()}tree=render()
 return {h,render,tree,handlers,page:()=>page,changePage(next){page=next;trigger.isConnected=false},ended:()=>ended,focused:()=>focused,scrolled:()=>scrolled,showTarget(){ready=true;mutation?.([]);for(const [n,fn]of [...timers]){timers.delete(n);fn()}}}
}
test('offscreen tour target leaves callout controls inside viewport',()=>{
 const f=tourFixture();const callout=nodes(f.tree).find(x=>x.props?.className?.includes('shadow-2xl'))
 assert.ok(callout.props.style.top<=505,`callout top ${callout.props.style.top}`)
 assert.ok(f.scrolled()>0)
})
test('Escape dismisses the tour and returns focus',()=>{
 const f=tourFixture();f.handlers.get('keydown')?.({key:'Escape',preventDefault(){},stopPropagation(){}})
 assert.equal(f.ended(),1);assert.equal(f.focused(),1)
})
test('tour subscribes to scroll and removes listeners on unmount',()=>{
 const f=tourFixture();assert.ok(f.handlers.has('scroll'));f.h.unmount();assert.equal(f.handlers.size,0)
})
const accent=harness('lib/use-accent-color.ts',{'./accent-contrast':harness('lib/accent-contrast.ts').exports,'./preference-storage':{preferenceStorage:{getItem(){return null}}}}).exports
function picker() {const h=harness('components/shared/ColorPicker.tsx',{'@/lib/use-accent-color':accent});let resets=0
 const props={value:'#c8ff4d',onChange(){},onReset(){resets++}}
 return {h,render:()=>h.render('ColorPicker',props),resets:()=>resets}
}
test('reset clears invalid hex even when committed colour is already default',()=>{
 const f=picker();let tree=f.render();nodes(tree).find(x=>x.props?.maxLength===7).props.onChange({target:{value:'#xyz'}})
 tree=f.render();assert.equal(nodes(tree).find(x=>x.props?.maxLength===7).props.value,'#xyz')
 button(tree,'Reset to Default').props.onClick();tree=f.render()
 assert.equal(nodes(tree).find(x=>x.props?.maxLength===7).props.value,'#c8ff4d');assert.equal(f.resets(),1)
})

test('default light theme does not receive the raw bright accent inline',()=>{
 const style=new Map();let writes=0
 const h=harness('lib/use-accent-color.ts',{'./accent-contrast':harness('lib/accent-contrast.ts').exports,'./preference-storage':{preferenceStorage:{getItem(){return null},setItem(){writes++}}}},
  {document:{documentElement:{style:{setProperty(k,v){style.set(k,v)}},classList:{contains:x=>x==='light'}}},getComputedStyle:()=>({getPropertyValue:k=>k==='--card'?'#ffffff':'#f2f3ee'})})
 assert.equal(h.exports.getAccentColor(),'#c8ff4d');assert.notEqual(style.get('--accent-foreground'),'#c8ff4d');assert.equal(writes,0)
})
test('computed accent palette meets numeric contrast in both themes',()=>{
 const {contrastRatio,resolveAccentTokens}=harness('lib/accent-contrast.ts').exports
 assert.equal(contrastRatio('#000000','#ffffff'),21);assert.equal(contrastRatio('#ffffff','#ffffff'),1)
 for(const theme of ['light','dark'])for(const hex of ['#c8ff4d','#3366ff','#000000','#ffffff','#ff0000']){
  const surfaces=theme==='light'?{background:'#f2f3ee',card:'#ffffff'}:{background:'#08090a',card:'#101214'}
  const t=resolveAccentTokens(hex,theme,surfaces)
  for(const surface of Object.values(surfaces)){
   assert.ok(contrastRatio(t.accentForeground,surface)>=4.5,`${theme} ${hex}`)
   assert.ok(contrastRatio(t.ring,surface)>=3)
  }
  assert.ok(contrastRatio(t.primaryForeground,t.primary)>=4.5)
 }
})

test('tour discovers a target mounted after initial measurement',()=>{
 const f=tourFixture({late:true});assert.equal(f.scrolled(),0);f.showTarget();f.render();assert.ok(f.scrolled()>0);f.h.unmount()
})
test('tour geometry bounds narrow, short, missing and zero-size viewports',()=>{
 const {computeTourCallout}=harness('lib/tour-layout.ts').exports
 for(const viewport of [{width:360,height:200},{width:1200,height:761},{width:0,height:0}]) {
  const p=computeTourCallout(null,viewport,{width:320,height:900})
  for(const n of Object.values(p))assert.ok(Number.isFinite(n)&&n>=0)
  assert.ok(p.maxWidth<=viewport.width && p.maxHeight<=viewport.height)
 }
})

test('accent foreground and focus ring cover real light hover surface',()=>{
 const {contrastRatio,resolveAccentTokens}=harness('lib/accent-contrast.ts').exports
 const tokens=resolveAccentTokens('#c8ff4d','light',{background:'#f2f3ee',card:'#ffffff',accent:'#e7e8e2'})
 assert.ok(contrastRatio(tokens.accentForeground,'#e7e8e2')>=4.5)
 const fs=require('node:fs');for(const name of ['button','badge','input','textarea','select','switch','tabs','scroll-area']) assert.doesNotMatch(fs.readFileSync(`src/components/ui/${name}.tsx`,'utf8'),/focus-visible:ring-ring\/50/,name)
})

test('pipeline readable zoom requests actual-size viewport without changing graph data',()=>{
 const zooms=[]
 const h=harness('components/panels/ReadableGraphZoom.tsx',{'@xyflow/react':{Panel:'Panel',useReactFlow:()=>({zoomTo:level=>{zooms.push(level);return Promise.resolve(true)}})}})
 const tree=h.render('ReadableGraphZoom')
 const action=button(tree,'Readable zoom (100%)');assert.ok(action)
 action.props.onClick();assert.deepEqual(zooms,[1]);assert.equal(action.props.type,'button')
 assert.match(action.props.title,/pan/i)
})

for(const action of ['Escape','Skip'])test(`tour ${action} restores Settings and focus after opener unmounts`,()=>{
 const f=tourFixture({origin:'settings'});f.changePage('dashboard');f.render();f.h.effects()
 if(action==='Escape')f.handlers.get('keydown')({key:'Escape',preventDefault(){},stopPropagation(){}})
 else button(f.render(),'Skip').props.onClick()
 f.render();f.h.effects();f.render();f.h.effects()
 assert.equal(f.page(),'settings');assert.equal(f.focused(),1)
 f.h.unmount();assert.equal(f.handlers.size,0)
})

test('finishing a tour restores the remounted opener and focus',()=>{
 const f=tourFixture({origin:'settings',last:true});f.changePage('dashboard');f.render();f.h.effects()
 button(f.render(),'Finish').props.onClick()
 for(let i=0;i<3;i++){f.render();f.h.effects()}
 assert.equal(f.page(),'settings');assert.equal(f.focused(),1);assert.equal(f.ended(),1)
 f.h.unmount()
})
