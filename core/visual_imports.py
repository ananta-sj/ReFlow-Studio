"""Exact-source BasicSR guards for isolated CPU inference, without package edits."""
import ast,hashlib,importlib,importlib.abc,importlib.machinery,os,sys
from contextlib import contextmanager
from importlib import metadata
HASHES={'basicsr.utils.dist_util':'e6a6d7fced5146ff2e1f16cb0ce1c922171fe7e8b28c011178695ebed4f477b8',
        'basicsr.data.degradations':'b78e36137ff8e4d783779b5ed611fcf80305633c492ac494ee52b213806f2d83'}
LAUNCHERS={'init_dist','_init_dist_pytorch','_init_dist_slurm'}

def guarded_source(name,payload):
    if name not in HASHES or hashlib.sha256(payload).hexdigest()!=HASHES[name]:
        raise RuntimeError('BasicSR guard source changed; review the isolated runtime before use')
    source=payload.decode('utf-8')
    if name=='basicsr.utils.dist_util':
        tree=ast.parse(source);found=set()
        for node in tree.body:
            if isinstance(node,ast.FunctionDef) and node.name in LAUNCHERS:
                node.body=ast.parse("raise RuntimeError('Distributed training is disabled in Reflow visual inference')").body;found.add(node.name)
        if found!=LAUNCHERS:raise RuntimeError('BasicSR distributed launcher layout changed')
        source=ast.unparse(ast.fix_missing_locations(tree))
    else:
        needle='from torchvision.transforms.functional_tensor import rgb_to_grayscale'
        if source.count(needle)!=1:raise RuntimeError('BasicSR vision compatibility import changed')
        source=source.replace(needle,'from torchvision.transforms.functional import rgb_to_grayscale')
    return source+'\n__reflow_visual_guard__ = True\n'

class _Loader(importlib.machinery.SourceFileLoader):
    def get_code(self,fullname):return compile(guarded_source(fullname,self.get_data(self.path)),self.path,'exec',dont_inherit=True)

class _Finder(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname not in HASHES:return None
        spec=importlib.machinery.PathFinder.find_spec(fullname,path)
        if spec is None or not spec.origin or not isinstance(spec.loader,importlib.machinery.SourceFileLoader):raise RuntimeError('BasicSR guard requires installed Python source')
        spec.loader=_Loader(fullname,spec.origin);return spec

@contextmanager
def guarded_imports():
    if metadata.version('basicsr')!='1.4.2':raise RuntimeError('BasicSR guard requires reviewed version 1.4.2')
    if any(name=='basicsr' or name.startswith('basicsr.') for name in sys.modules):
        raise RuntimeError('BasicSR was loaded before the isolated visual guard')
    os.environ['BASICSR_EXT']='False';os.environ['BASICSR_JIT']='False'
    finder=_Finder();sys.meta_path.insert(0,finder)
    try:
        yield
        for name in HASHES:
            if not getattr(sys.modules.get(name),'__reflow_visual_guard__',False):raise RuntimeError('Required BasicSR guard did not activate')
    finally:
        if finder in sys.meta_path:sys.meta_path.remove(finder)
