import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, rm, writeFile, readFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { PACKAGES, MARKER, releaseBody, collectAssets, findPreviewRelease, hash, publish, validateExistingRelease } from '../publish_development_preview.mjs'
const SHA='a'.repeat(40), OTHER='b'.repeat(40)
async function fixture(run) {
  const folder=await mkdtemp(path.join(os.tmpdir(),'reflow-preview-'))
  try {
    for(const name of Object.values(PACKAGES)) {
      const file=path.join(folder,name);await writeFile(file,`fixture package ${name}`)
      await writeFile(`${file}.sha256`,`${await hash(file)}  ${name}\n`)
    }
    await run(folder)
  } finally {await rm(folder,{recursive:true,force:true})}
}
function server({staleAt=Infinity,failUpload=Infinity,failPromotion=false,lostPromotionResponse=false,conflictingTag=false,unknownPromotion=false,lostUploadResponse=false}={}) {
  const calls=[], releases=[{id:9,tag_name:'development-preview',body:MARKER,draft:false,immutable:true}]
  const tags=new Map([['development-preview',OTHER]]), assetsByRelease=new Map()
  let heads=0,uploads=0,nextId=1
  const api=async(route,options={})=>{
    calls.push({route,...options})
    if(route==='/git/ref/heads/main')return {object:{sha:++heads>=staleAt?OTHER:SHA}}
    if(route==='/releases?per_page=100&page=1')return releases.map(r=>({...r}))
    if(route==='/tags?per_page=100&page=1')return [...tags.keys()].map(name=>({name}))
    if(route==='/releases'&&options.method==='POST') {
      const release={id:nextId++,...options.body};release.upload_url=`https://uploads.github.com/release/${release.id}/assets{?name,label}`
      releases.push(release);return {...release}
    }
    const assets=route.match(/^\/releases\/(\d+)\/assets\?per_page=100&page=1$/)
    if(assets){assert.notEqual(Number(assets[1]),9,'old release assets must never be accessed');return (assetsByRelease.get(Number(assets[1]))||[]).map(a=>({...a}))}
    if(route.startsWith('https://uploads.github.com/')) {
      if(++uploads===failUpload)throw new Error('Upload failed')
      const id=Number(route.match(/release\/(\d+)\//)[1])
      const asset={id:100+uploads,name:new URL(route).searchParams.get('name'),state:'uploaded',size:4,digest:'sha256:'+'c'.repeat(64)}
      if(!assetsByRelease.has(id))assetsByRelease.set(id,[])
      assetsByRelease.get(id).push(asset)
      if(lostUploadResponse&&uploads===1)throw new Error('Lost upload response')
      return {...asset}
    }
    const tag=route.match(/^\/git\/ref\/tags\/(.+)$/)
    if(tag){if(conflictingTag)return{object:{type:'commit',sha:OTHER}}
      if(!tags.has(tag[1]))throw Object.assign(new Error('Missing'),{status:404})
      return{object:{type:'commit',sha:tags.get(tag[1])}}}
    if(route==='/git/refs'&&options.method==='POST'){tags.set(options.body.ref.replace('refs/tags/',''),options.body.sha);return{}}
    const ref=route.match(/^\/git\/refs\/tags\/(.+)$/)
    if(ref&&options.method==='DELETE'){tags.delete(ref[1]);return null}
    const match=route.match(/^\/releases\/(\d+)$/)
    if(match){const release=releases.find(r=>r.id===Number(match[1]));assert.notEqual(release.id,9)
      if(options.method==='PATCH'){
        if(failPromotion)throw new Error('Metadata failed')
        Object.assign(release,options.body)
        if(lostPromotionResponse||unknownPromotion)throw new Error('Lost response')
      }else if(unknownPromotion)throw new Error('Cannot reconcile')
      return{...release}}
    if(options.method==='DELETE'&&route.startsWith('/releases/assets/')){
      const id=Number(route.split('/').at(-1))
      for(const [release,rows] of assetsByRelease)assetsByRelease.set(release,rows.filter(a=>a.id!==id))
      return null
    }
    throw new Error(`Unexpected request ${route}`)
  }
  const assets=[1,2].map(n=>({name:`ReflowStudio-dev-new${n}.zip`,file:'/fixture',bytes:4,sha256:'c'.repeat(64)}))
  return{api,calls,assets,releases,tags,assetsByRelease}
}
async function execute(state,overrides={}){return publish({...state,repository:'owner/repo',sha:SHA,runId:'123',attempt:'1',...overrides})}

test('complete packages require four platforms, source and matching checksums',()=>fixture(async folder=>{
  const assets=await collectAssets(folder,SHA,'123','1');assert.equal(assets.length,5)
  assert.ok(assets.every(r=>r.name.includes('aaaaaaaaaaaa-r123-a1')))
  await rm(path.join(folder,PACKAGES['macos-arm64']));await assert.rejects(collectAssets(folder,SHA,'123','1'),/exactly four/)
}))
test('tampered package and unexpected private files block publication',()=>fixture(async folder=>{
  await writeFile(path.join(folder,PACKAGES.source),'changed');await assert.rejects(collectAssets(folder,SHA,'123','1'),/Checksum mismatch/)
  await writeFile(path.join(folder,'settings.json'),'{}');await assert.rejects(collectAssets(folder,SHA,'123','1'),/exactly four/)
}))
test('unowned and immutable draft releases cannot be replaced',()=>{
  for(const release of [{body:'user release'},{body:MARKER,immutable:true}])assert.throws(()=>validateExistingRelease(release),/Refusing/)
})
test('outdated build skips before changing any release',async()=>{
  const state=server({staleAt:1});assert.equal((await execute(state)).skipped,true);assert.equal(state.calls.length,1)
})
test('failed upload cleans only this build uploads and leaves previous releases intact',async()=>{
  const s=server({failUpload:2});await assert.rejects(execute(s),/Upload failed/)
  assert.deepEqual(s.calls.filter(r=>r.method==='DELETE').map(r=>r.route),['/releases/assets/101'])
  assert.ok(!s.calls.some(r=>r.method==='PATCH'));assert.equal(s.releases[0].tag_name,'development-preview')
})
test('new versioned preview is a regular latest release and never replaces legacy release',async()=>{
  const s=server(),result=await execute(s);assert.equal(result.tag,'v0.7.1-desktop-preview')
  const i=s.calls.findIndex(r=>r.route==='/releases/1'&&r.method==='PATCH')
  assert.ok(i>s.calls.findLastIndex(r=>r.route.startsWith('https://uploads.github.com/')))
  assert.equal(s.calls[i].body.make_latest,'true');assert.equal(s.calls[i].body.prerelease,false)
  assert.match(s.calls[i].body.name,/v0.7.1.*Desktop Preview/)
  assert.equal(s.calls.filter(r=>r.method==='DELETE').length,0)
  assert.equal(s.tags.get('development-preview'),OTHER)
})
test('successive builds create v0.7.1 then v0.7.2 and retain both download sets',async()=>{
  const s=server();await execute(s);const old=JSON.stringify(s.releases.find(r=>r.id===1))
  assert.equal((await execute(s,{runId:'124'})).tag,'v0.7.2-desktop-preview')
  assert.equal(JSON.stringify(s.releases.find(r=>r.id===1)),old)
  assert.ok(s.tags.has('v0.7.1-desktop-preview'));assert.ok(s.tags.has('v0.7.2-desktop-preview'))
})
test('push arriving during upload never promotes stale build',async()=>{
  const s=server({staleAt:2});assert.equal((await execute(s)).skipped,true)
  assert.equal(s.calls.filter(r=>r.method==='DELETE').length,2);assert.ok(!s.calls.some(r=>r.method==='PATCH'))
})
test('failed promotion removes only newly created version tag and uploads',async()=>{
  const s=server({failPromotion:true});await assert.rejects(execute(s),/Metadata failed/)
  assert.ok(!s.tags.has('v0.7.1-desktop-preview'));assert.equal(s.tags.get('development-preview'),OTHER)
  assert.ok(!s.calls.some(r=>r.method==='PATCH'&&r.route.startsWith('/git/')))
})
test('conflicting existing version tag is never moved or deleted',async()=>{
  const s=server({conflictingTag:true});await assert.rejects(execute(s),/refusing to move/)
  assert.ok(!s.calls.some(r=>r.route.startsWith('/git/refs/')&&['PATCH','DELETE'].includes(r.method)))
})
test('lost successful response is reconciled without rolling back published artifacts',async()=>{
  const s=server({lostPromotionResponse:true});assert.equal((await execute(s)).skipped,false)
  assert.equal(s.calls.filter(r=>r.method==='DELETE').length,0)
})
test('uncertain publication preserves version tag and artifacts for inspection',async()=>{
  const s=server({unknownPromotion:true});await assert.rejects(execute(s),/Lost response/)
  assert.ok(s.tags.has('v0.7.1-desktop-preview'));assert.equal(s.calls.filter(r=>r.method==='DELETE').length,0)
})
test('matching interrupted draft is reused and other builds drafts are ignored',async()=>{
  const identity=`<!-- reflow-preview-build:123:1:${SHA} -->`
  const draft={id:5,tag_name:'v0.7.1-desktop-preview',draft:true,body:`${MARKER}\n${identity}`}
  assert.equal(findPreviewRelease([draft], '123','1',SHA).id,5)
  assert.equal(findPreviewRelease([draft], '124','1',SHA),undefined)
  const s=server();await execute(s);s.releases[1].draft=true;s.calls.length=0
  await execute(s);assert.ok(!s.calls.some(r=>r.route==='/releases'&&r.method==='POST'))
})
test('published same build is idempotent even when immutable',async()=>{
  const s=server();await execute(s);s.releases[1].immutable=true;s.calls.length=0
  assert.equal((await execute(s)).alreadyPublished,true)
  assert.ok(s.calls.every(r=>!r.method||r.method==='GET'))
})
test('first preview stays draft until all uploads verify',async()=>{
  const s=server();await execute(s)
  const draft=s.calls.find(r=>r.route==='/releases'&&r.method==='POST')
  assert.equal(draft.body.draft,true);assert.equal(draft.body.prerelease,false);assert.ok(!('make_latest' in draft.body))
  const tag=s.calls.findIndex(r=>r.route==='/git/refs'&&r.method==='POST')
  assert.ok(tag>s.calls.findLastIndex(r=>r.route.startsWith('https://uploads.github.com/')))
})
test('workflow gates publication on four builds, main and a job-local write token',async()=>{
  const w=await readFile(new URL('../../.github/workflows/build.yml',import.meta.url),'utf8')
  for(const regex of [/branches: \[main\]/,/needs: \[source, build\]/,/build:\s+needs: source/,/run: npm ci --dry-run --ignore-scripts --no-audit --no-fund/,/if: github\.ref == 'refs\/heads\/main'/,/cancel-in-progress: false/,/pattern: ReflowStudio-\*/])assert.match(w,regex)
  assert.equal((w.match(/contents: write/g)||[]).length,1)
  for(const target of ['windows-x64','linux-x64','macos-arm64','macos-x64'])assert.ok(w.includes(`target: ${target}`))
})
test('notes retain preview warnings, supplied changes and previous release history',()=>{
  const body=releaseBody('owner/repo',SHA,'123','## Recent changes\n- Fix recovery')
  assert.match(body,/regular GitHub release/);assert.match(body,/Fix recovery/)
  assert.match(body,/Earlier preview releases and their downloads are preserved/)
})

test('numbering includes release and tag history beyond the first page',async()=>{
  const s=server(),base=s.api
  s.api=async(route,options={})=>{
    if(route==='/releases?per_page=100&page=1')return Array.from({length:100},(_,i)=>({id:200+i,tag_name:`archive-${i}`,body:'archive'}))
    if(route==='/releases?per_page=100&page=2')return s.releases.map(r=>({...r}))
    if(route==='/tags?per_page=100&page=1')return Array.from({length:100},(_,i)=>({name:`archive-${i}`}))
    if(route==='/tags?per_page=100&page=2')return [{name:'v0.7.8-desktop-preview'}]
    return base(route,options)
  }
  assert.equal((await execute(s)).tag,'v0.7.9-desktop-preview')
})

test('interrupted own draft reuses previously verified uploaded assets',async()=>{
  const s=server();await execute(s);s.releases[1].draft=true;s.calls.length=0
  assert.equal(s.assetsByRelease.get(1).length,2)
  await execute(s)
  assert.ok(!s.calls.some(r=>r.route.startsWith('https://uploads.github.com/')))
  assert.ok(!s.calls.some(r=>r.method==='DELETE'))
})
test('unverifiable or mismatched asset is replaced only on its owned unpublished draft',async()=>{
  for(const digest of [undefined,'sha256:'+'d'.repeat(64)]){
    const s=server();await execute(s);s.releases[1].draft=true;s.calls.length=0
    s.assetsByRelease.get(1)[0].digest=digest
    await execute(s)
    assert.deepEqual(s.calls.filter(r=>r.method==='DELETE').map(r=>r.route),['/releases/assets/101'])
    assert.ok(s.assetsByRelease.get(1).some(a=>a.id===102))
    assert.equal(s.assetsByRelease.get(1).length,2)
  }
})
test('upload accepted with a lost response is recovered on the next invocation',async()=>{
  const s=server({lostUploadResponse:true});await assert.rejects(execute(s),/Lost upload response/)
  assert.equal(s.assetsByRelease.get(1).length,1)
  assert.equal((await execute(s)).tag,'v0.7.1-desktop-preview')
  assert.equal(s.assetsByRelease.get(1).length,2)
  assert.ok(s.assetsByRelease.get(1).some(a=>a.id===101))
})
