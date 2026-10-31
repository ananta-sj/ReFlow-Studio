// Render the actual Dashboard with controlled job state, using installed TS/Node.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const assert = require('node:assert/strict'), crypto = require('node:crypto');
const ts = require('../frontend/node_modules/typescript');
const root = path.resolve(__dirname, '..');
const name = 'frontend/src/pages/Dashboard.tsx';
const source = fs.readFileSync(path.join(root, name), 'utf8');
const jsx = (type, props) => ({type, props});
const noop = () => {};
let job = {status:'idle', isRunning:false, isStopping:false, inputPath:null};
let pending = [{id:'next', input_path:'C:\\fixture\\NEXT.mp4'}];
let slot = 0, inputKind = 'video';
const added = [];
const bindings = {
  react: {useEffect:noop, useRef:value=>({current:value}), useState:value=>[
    slot++ === 1 ? {video_dub:{input_kind:inputKind,label:'Video dubbing'}} : value, noop]},
  'react/jsx-runtime': {jsx,jsxs:jsx},
  'lucide-react': {Upload:'Upload'},
  '@/lib/api': {bridge:{browseVideo:async()=>['C:/fixture/ADDED.mp4']}},
  '@/lib/use-render': {useRenderJob:()=>job},
  '@/lib/use-queue': {useQueue:()=>pending,addToQueue:async files=>added.push(files)},
  '@/lib/use-render-config': {useRenderConfig:()=>({template:'video_dub',taskPriority:75}),
    updateConfig:noop,QUALITY_STEPS:[1,2]},
  '@/lib/render-params': {buildRenderParams:()=>({})},
  '@/lib/use-experience': {levelAtLeast:(level,minimum)=>['basic','advanced','expert'].indexOf(level)>=['basic','advanced','expert'].indexOf(minimum)},
  '@/lib/use-confirm': {confirmAction:async()=>false},
  '@/lib/gauge-color': {loadGaugeColor:()=>''},
  '@/lib/eta': {formatDuration:()=>'',relativeSpeedPercent:()=>0,projectedLoadPercent:()=>null,jobMemoryBudget:()=>null},
  '@/lib/utils': {cn:()=>''},
};
for (const [module,names] of Object.entries({
  'ui/button':['Button'], 'ui/card':['Card','CardContent','CardHeader','CardTitle'],
  'ui/switch':['Switch'], 'ui/slider':['Slider'], 'ui/progress':['Progress'],
  'ui/select':['Select','SelectContent','SelectItem','SelectTrigger','SelectValue'],
  'panels/CornerFrame':['CornerFrame'], 'panels/RadialGauge':['RadialGauge'],
  'shared/HelpTooltip':['HelpTooltip'], 'shared/SourceLanguageReport':['SourceLanguageReport'],
  'shared/CueReviewPanel':['CueReviewPanel'],
})) bindings['@/components/'+module] = Object.fromEntries(names.map(name=>[name,name]));
const exportsObject = {};
vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,
  target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText,
  {exports:exportsObject,require:key=>{assert.ok(key in bindings,key);return bindings[key];}});
function render(level='expert') {
  slot = 0;
  return exportsObject.Dashboard({selectedDeviceId:'cpu',level,onNavigate:noop});
}
function text(node) {
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  return node && typeof node === 'object' ? [node.props?.children].flat(Infinity).map(text).join(' ') : '';
}
function nodes(node) {
  return node && typeof node === 'object' ? [node,...[node.props?.children].flat(Infinity).flatMap(nodes)] : [];
}
const checks = [];
async function check(name, run) {await run();checks.push({name,passed:true});}
(async()=>{
  await check('Running view separates original active source from next pending input and its estimate',()=>{
    job = {status:'running',isRunning:true,isStopping:false,inputPath:'C:/fixture/ACTIVE.mp4',percent:25};
    const output = text(render());
    assert.match(output,/Currently rendering ACTIVE\.mp4/);
    assert.match(output,/Next pending video/);
    assert.match(output,/Estimate for selected input:\s+NEXT\.mp4/);
    assert.match(output,/Active input\s*:\s+ACTIVE\.mp4/);
    assert.match(output,/Accepted batch jobs retain their saved settings/);
  });
  await check('Stopping with no pending jobs retains active identity in Basic mode',()=>{
    pending=[];job={...job,status:'stopping',isStopping:true};
    const output=text(render('basic'));
    assert.match(output,/Stopping render ACTIVE\.mp4/);
    assert.match(output,/Click to select video file/);
    assert.doesNotMatch(output,/Estimate for selected input/);
  });
  await check('Finished state identifies historical source without showing it as running',()=>{
    pending=[{id:'next',input_path:'C:/fixture/NEXT.mp4'}];
    job={...job,status:'finished',isRunning:false,isStopping:false};
    const output=text(render());
    assert.match(output,/Last render input\s*:\s+ACTIVE\.mp4/);
    assert.match(output,/Selected input/);
    assert.doesNotMatch(output,/Currently rendering|Next pending video/);
  });
  await check('Browsing while active adds drafts without replacing active source',async()=>{
    job={...job,status:'running',isRunning:true};
    const browse=nodes(render()).find(node=>node.type==='button' && text(node).includes('NEXT.mp4'));
    assert.ok(browse);await browse.props.onClick();
    assert.equal(added.length,1);assert.equal(added[0][0],'C:/fixture/ADDED.mp4');
    assert.equal(job.inputPath,'C:/fixture/ACTIVE.mp4');
  });
  await check('Video review receives the selected pending video, not the active render input',()=>{
    const review=nodes(render()).find(node=>node.type==='CueReviewPanel');
    assert.ok(review);assert.equal(review.props.inputPath,'C:/fixture/NEXT.mp4');
    assert.notEqual(review.props.inputPath,job.inputPath);
  });
  await check('Audio review stays available and subtitle input does not expose dubbing review',()=>{
    inputKind='audio';assert.ok(nodes(render()).some(node=>node.type==='CueReviewPanel'));
    inputKind='subtitle';assert.ok(!nodes(render()).some(node=>node.type==='CueReviewPanel'));
    inputKind='video';
  });
  const receipt={passed:true,checks,source_sha256:{[name]:crypto.createHash('sha256').update(source).digest('hex')},
    native_walkthrough:false,live_model_calls:false};
  fs.writeFileSync(path.join(root,'docs/validation/2026-10-12-dashboard-input-contracts.json'),JSON.stringify(receipt,null,2));
  console.log(JSON.stringify(receipt,null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
