// Run actual frontend modules with existing TypeScript and Node fixtures.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const assert = require('node:assert/strict'), crypto = require('node:crypto');
const ts = require('../frontend/node_modules/typescript');
const root = path.resolve(__dirname, '..'), hashes = {}, results = [];
function load(name, bindings = {}) {
  const source = fs.readFileSync(path.join(root, name), 'utf8');
  hashes[name] = crypto.createHash('sha256').update(source).digest('hex');
  const exports = {};
  vm.runInNewContext(ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.CommonJS,
    target:ts.ScriptTarget.ES2022}}).outputText, {exports, require:key => {
      if (!(key in bindings)) throw Error('Unexpected dependency: '+key); return bindings[key];
    }, console, ...bindings.globals});
  return exports;
}
async function check(name, run) { await run(); results.push({name,passed:true}); }
(async () => {
  let saved = {'reflow-experience-level':'advanced', 'reflow.renderConfig':'{"lang":"hi"}'}, writes=[];
  const bridge = {getUiPreferences:async()=>({...saved}), updateUiPreferences:async partial=>{
    writes.push(partial); Object.assign(saved,partial); return {...saved};
  }};
  const bindings={'./api':{bridge}, globals:{window:{},localStorage:{getItem:()=>{throw Error('Private cache unavailable');}}}};
  const prefs=load('frontend/src/lib/preference-storage.ts',bindings);
  await check('Private cache absence still restores app-owned preferences',async()=>{
    await prefs.initializePreferences(); assert.equal(prefs.preferenceStorage.getItem('reflow-experience-level'),'advanced');
  });
  await check('Writes retain user order and unrelated saved preferences',async()=>{
    prefs.preferenceStorage.setItem('reflow-theme','light');
    prefs.preferenceStorage.setItem('reflow-theme','dark'); await prefs.flushPreferences();
    assert.equal(saved['reflow-theme'],'dark'); assert.equal(saved['reflow-experience-level'],'advanced'); assert.equal(writes.length,2);
  });
  await check('New module session restores final choice without browser state',async()=>{
    const restarted=load('frontend/src/lib/preference-storage.ts',bindings); await restarted.initializePreferences();
    assert.equal(restarted.preferenceStorage.getItem('reflow-theme'),'dark');
  });
  await check('Unknown storage key cannot enqueue a bridge request',()=>{
    assert.throws(()=>prefs.preferenceStorage.setItem('credentials','secret'),/Unknown/); assert.equal(writes.length,2);
  });
  const updates=[];
  const config=load('frontend/src/lib/use-render-config.ts',{
    './preference-storage':prefs, '@/lib/api':{bridge:{setNodeEnabled:async()=>({ok:true})}},
    react:{useState:initial=>[initial,next=>updates.push(next)],useEffect:effect=>effect()},
  });
  await check('Restored render config reaches subscriber on first mount',()=>{
    config.useRenderConfig(); assert.equal(updates.at(-1).lang,'hi');
  });
  const {projectGraphNode}=load('frontend/src/lib/graph-config.ts');
  const languages=[{code:'hi',name:'Hindi'}], cfg={lang:'hi',voice:'chosen'};
  const voice={id:'tts_rvc',params:[{key:'voice',default:'old'}]};
  await check('Singleton voice display follows actual Dashboard render choice',()=>{
    assert.equal(projectGraphNode(voice,cfg,1,languages,null).params[0].default,'chosen');
    assert.equal(voice.params[0].default,'old');
  });
  await check('Multiple voice nodes retain independent choices',()=>{
    assert.equal(projectGraphNode(voice,cfg,2,languages,null).params[0].default,'old');
    assert.equal(projectGraphNode({...voice,id:'tts_rvc_2'},cfg,2,languages,null).params[0].default,'old');
  });
  await check('Language and source labels follow current render selection',()=>{
    const node={id:'translate',params:[{key:'lang',default:'English (en)'}]};
    assert.equal(projectGraphNode(node,cfg,1,languages,null).params[0].default,'Hindi (hi)');
    assert.match(projectGraphNode(node,{...cfg,lang:'source'},1,languages,null).params[0].default,/no translation/);
    assert.equal(projectGraphNode({id:'input',params:[{key:'video_name'}]},cfg,1,languages,'C:\\source\\clip.mp4').params[0].default,'clip.mp4');
  });
  await prefs.flushPreferences();
  const receipt={passed:true,checks:results,source_sha256:hashes};
  fs.writeFileSync(path.join(root,'docs/validation/2026-10-10-preference-graph-frontend-contracts.json'),JSON.stringify(receipt,null,2));
  console.log(JSON.stringify(receipt,null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
