// Execute actual transpiled components/hooks with controlled React/DOM boundaries.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), ts = require('typescript')
function harness(file, imports = {}, globals = {}, exposed = []) {
  const states=[], effects=[], memos=[], pending=[]; let cursor=0, writes=0
  const react={
    useState(initial) { const i=cursor++; if (!(i in states)) states[i]=typeof initial==='function'?initial():initial
      return [states[i],value=>{ writes++;states[i]=typeof value==='function'?value(states[i]):value }] },
    useRef(initial) { const i=cursor++;if (!(i in states)) states[i]={current:initial};return states[i] },
    useMemo(fn,deps) { const i=cursor++,old=memos[i];if (!old||!deps||deps.some((x,j)=>x!==old.deps[j])) memos[i]={value:fn(),deps};return memos[i].value },
    useCallback(fn,deps) { return react.useMemo(()=>fn,deps) },
    useEffect(fn,deps) { const i=cursor++,old=effects[i];if (!old||!deps||deps.some((x,j)=>x!==old.deps[j])) {effects[i]={deps,cleanup:old?.cleanup};pending.push(()=>{effects[i].cleanup?.();effects[i].cleanup=fn()})} },
  }
  const filename=path.resolve(__dirname,'../src',file),module={exports:{}}
  const code=ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText
  vm.runInNewContext(code+(exposed.length?'\nmodule.exports.__test={'+exposed.join(',')+'}':''),{
    module,exports:module.exports,setTimeout,clearTimeout,console,...globals,
    require(name) {if(name==='react')return react;if(name in imports)return imports[name]
      if(name==='@/lib/utils')return {cn:(...args)=>args.filter(Boolean).join(' ')}
      if(name.startsWith('@/'))return new Proxy({}, {get:(_,key)=>key})
      return require(name)
    }},{filename})
  return {exports:module.exports,render(name,props){cursor=0;return (module.exports[name]??module.exports.__test?.[name])(props)},
    effects(){let count=0;while(pending.length){if(++count>100)throw Error('Effect loop');pending.shift()()}},
    unmount(){effects.forEach(x=>x?.cleanup?.())},writes:()=>writes}
}
function nodes(tree){if(!tree||typeof tree!=='object')return [];if(Array.isArray(tree))return tree.flatMap(nodes);return [tree,...nodes(tree.props?.children)]}
function text(tree){if(tree==null||typeof tree==='boolean')return '';if(typeof tree!=='object')return String(tree);return Array.isArray(tree)?tree.map(text).join(''):text(tree.props?.children)}
function button(tree,label){return nodes(tree).find(x=>x.props?.onClick&&(x.props['aria-label']===label||text(x)===label))}
const flush=async()=>{for(let i=0;i<40;i++)await Promise.resolve()}
module.exports={harness,nodes,text,button,flush}
