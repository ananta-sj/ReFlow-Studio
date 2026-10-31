// Execute the actual dialog and App recovery handlers with existing TS/Node.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const assert = require('node:assert/strict'), crypto = require('node:crypto');
const ts = require('../frontend/node_modules/typescript');
const root = path.resolve(__dirname, '..'), hashes = {}, checks = [];
const effects = [];
const react = {useState: value => [value, () => {}], useEffect: fn => effects.push(fn)};
const jsx = (type, props) => ({type, props});
const runtime = {jsx, jsxs:jsx, Fragment:'Fragment'};
function load(name, bindings) {
  const source = fs.readFileSync(path.join(root, name), 'utf8');
  hashes[name] = crypto.createHash('sha256').update(source).digest('hex');
  const exports = {};
  vm.runInNewContext(ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.CommonJS,
    target:ts.ScriptTarget.ES2022, jsx:ts.JsxEmit.ReactJSX}}).outputText,
    {exports, require: name => {
      if (!(name in bindings)) throw Error('Unexpected dependency: '+name);
      return bindings[name];
    }, window:{__reflow:{dispatch:()=>{}}}, setTimeout:()=>{}, console});
  return exports;
}
const dialogs = Object.fromEntries(['Dialog','DialogContent','DialogDescription','DialogFooter',
  'DialogHeader','DialogTitle'].map(name => [name,name]));
const confirmation = load('frontend/src/lib/use-confirm.tsx', {'react':react,
  'react/jsx-runtime':runtime, '@/components/ui/button':{Button:'Button'},
  '@/components/ui/dialog':dialogs});
function button(tree, label) {
  if (!tree || typeof tree !== 'object') return null;
  if (tree.type === 'Button' && tree.props.children === label) return tree;
  for (const child of [tree.props?.children].flat(Infinity)) {
    const result = button(child,label); if (result) return result;
  }
  return null;
}
async function check(name, run) { await run(); checks.push({name, passed:true}); }
async function drain() { for (let i=0;i<20;i++) await Promise.resolve(); }
const record = {input_path:'C:/fixture/source.mp4', params:{voice:'CLONED_USER',lang:'hi'},
  template_id:'video_dub', recovery_token:'original-token'};
async function boot(choice, result={ok:true}, discardThrows=false) {
  effects.length=0;
  const calls=[];
  const bridge={runIntegrityCheck:async()=>({ok:true,message:'fixture'}),
    getSettings:async()=>({values:{onboarding_complete:true}}), captureHardwareProfile:()=>{},
    getInterruptedRender:async()=>record,
    resumeInterruptedRender:async(...args)=>{calls.push({action:'resume',args});return result;},
    discardInterruptedRender:async token=>{calls.push({action:'discard',token});
      if(discardThrows) throw Error('fixture denial'); return result;}};
  const bindings={'react':react,'react/jsx-runtime':runtime,'./lib/events':{},
    '@/lib/api':{bridge}, '@/lib/use-confirm':confirmation,
    '@/lib/use-theme':{useTheme:()=>({theme:'dark',toggle:()=>{}})},
    '@/lib/use-accent-color':{useAccentColor:()=>{}},
    '@/lib/use-tour':{hasTourCompleted:()=>true,startTour:()=>{}},
    '@/lib/use-jobs':{initializeJobs:()=>{},runJobAction:send=>send()},
    '@/lib/use-experience':{useExperienceLevel:()=>({level:'basic',setLevel:()=>{}}),levelAtLeast:()=>false}};
  for (const [module,name] of [['shell/TitleBar','TitleBar'],['shell/PrimaryNav','PrimaryNav'],
    ['shell/IconRail','IconRail'],['shell/BootScreen','BootScreen'],['onboarding/SetupWizard','SetupWizard'],
    ['onboarding/ProductTour','ProductTour'],['panels/HardwareIntelligence','HardwareIntelligence'],
    ['panels/LogConsole','LogConsole']]) bindings['@/components/'+module]={[name]:()=>null};
  for (const name of ['Dashboard','Nodes','Assets','Marketplace','Logs','Settings'])
    bindings['@/pages/'+name]={[name==='Dashboard'?name:name+'Page']:()=>null};
  const app=load('frontend/src/App.tsx',bindings);
  app.default(); effects[0](); await drain();
  const tree=confirmation.ConfirmDialogHost();
  assert.equal(tree.props.open,true);
  if(choice==='dismiss') tree.props.onOpenChange(false);
  else button(tree,choice==='confirm'?'Resume Render':'Discard').props.onClick();
  await drain();
  const final=confirmation.ConfirmDialogHost();
  return {calls,final};
}
(async()=>{
  await check('Dialog distinguishes dismissal from an explicit cancel',async()=>{
    let result=confirmation.confirmChoice({title:'fixture',description:'fixture'});
    confirmation.ConfirmDialogHost().props.onOpenChange(false);
    assert.equal(await result,'dismiss');
    result=confirmation.confirmChoice({title:'fixture',description:'fixture'});
    button(confirmation.ConfirmDialogHost(),'Cancel').props.onClick();
    assert.equal(await result,'cancel');
  });
  await check('Boolean callers still reject cancel/dismiss and accept confirm',async()=>{
    for(const choice of ['dismiss','cancel','confirm']) {
      const result=confirmation.confirmAction({title:'fixture',description:'fixture'});
      const tree=confirmation.ConfirmDialogHost();
      if(choice==='dismiss') tree.props.onOpenChange(false);
      else button(tree,choice==='cancel'?'Cancel':'Confirm').props.onClick();
      assert.equal(await result,choice==='confirm');
    }
  });
  await check('Acknowledgement never permits a proceed action',async()=>{
    const result=confirmation.confirmAction({title:'fixture',description:'fixture',alertOnly:true});
    button(confirmation.ConfirmDialogHost(),'OK').props.onClick(); assert.equal(await result,false);
  });
  await check('App dismissal neither restarts nor deletes recovery',async()=>{
    const {calls}=await boot('dismiss'); assert.equal(calls.length,0);
  });
  await check('Explicit discard uses the originally offered recovery token',async()=>{
    const {calls}=await boot('cancel'); assert.deepEqual(calls,[{action:'discard',token:'original-token'}]);
  });
  await check('Resume uses the offered token without replaying editable client parameters',async()=>{
    const {calls}=await boot('confirm'); assert.deepEqual(calls,[{action:'resume',args:[record.recovery_token]}]);
  });
  await check('Rejected resume presents an alert and does not discard',async()=>{
    const {calls,final}=await boot('confirm',{ok:false,message:'fixture rejection'});
    assert.equal(calls.length,1); assert.equal(final.props.open,true);
    button(final,'OK').props.onClick();
  });
  await check('Stale-token rejection and discard exceptions surface an alert',async()=>{
    for(const throws of [false,true]) {
      const {calls,final}=await boot('cancel',{ok:false,message:'stale token'},throws);
      assert.equal(calls.length,1); assert.equal(final.props.open,true);
      button(final,'OK').props.onClick();
    }
  });
  const receipt={checks,source_sha256:hashes,passed:true};
  fs.writeFileSync(path.resolve(root,process.argv[2] || 'docs/validation/2026-10-10-native-recovery-frontend-contracts.json'),JSON.stringify(receipt,null,2));
  console.log(JSON.stringify(receipt,null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
