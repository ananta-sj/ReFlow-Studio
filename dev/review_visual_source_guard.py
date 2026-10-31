"""No-install prototype: disable BasicSR training launchers in reviewed source."""
import os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CODE=r'''
import ast,hashlib,json,os,sys,zipfile
from pathlib import Path
from unittest.mock import patch
root=Path(sys.argv[1]);out=root/'docs/validation';report=dict(passed=False,installed_or_integrated=False,upstream_advisory_resolved=False)
try:
    import torch
    torch.set_num_threads(2)
    def offline(event,args):
        if event in {'socket.connect','socket.bind','socket.getaddrinfo','subprocess.Popen','os.system'}:raise RuntimeError('Prototype forbids network or shell execution')
    sys.addaudithook(offline)
    row=next(row for row in json.loads((out/'2026-10-16-visual-helpers/build-receipt.json').read_text())['packages'] if row['name']=='basicsr')
    with zipfile.ZipFile(root/row['wheel']) as archive:source=archive.read('basicsr/utils/dist_util.py')
    tree=ast.parse(source);targets={'init_dist','_init_dist_pytorch','_init_dist_slurm'};found=set()
    for node in tree.body:
        if isinstance(node,ast.FunctionDef) and node.name in targets:
            node.body=ast.parse("raise RuntimeError('Distributed training is disabled in Reflow visual inference')").body;found.add(node.name)
    assert found==targets
    namespace=dict(__name__='reviewed_visual_guard',__file__='reviewed-dist-util.py')
    exec(compile(ast.fix_missing_locations(tree),'reviewed-dist-util.py','exec'),namespace)
    attempts=0
    with patch('subprocess.getoutput',side_effect=AssertionError('Shell execution attempted')) as shell,patch.dict(os.environ,{'SLURM_NODELIST':'untrusted-node-list','SLURM_PROCID':'0','SLURM_NTASKS':'1'}):
        for name,args in [('init_dist',('slurm',)),('_init_dist_slurm',('nccl',)),('_init_dist_pytorch',('nccl',))]:
            try:namespace[name](*args)
            except RuntimeError as error:assert 'Distributed training is disabled' in str(error);attempts+=1
            else:raise AssertionError('Launcher was not blocked')
        assert shell.call_count==0
    assert namespace['get_dist_info']()==(0,1)
    @namespace['master_only']
    def inference_helper():return 'preserved'
    assert inference_helper()=='preserved'
    report.update(passed=True,source_sha256=hashlib.sha256(source).hexdigest(),launchers_blocked=attempts,shell_calls=0,
        nondistributed_helpers_preserved=True,required_production_integration='Exact-source import guard before BasicSR import; fail on drift; prototype alone is not deployment')
except Exception as error:
    import traceback
    report.update(error=repr(error),traceback=traceback.format_exc())
finally:
    (out/'2026-10-16-visual-guard-prototype.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
raise SystemExit(not report['passed'])
'''
if __name__=='__main__':
    raise SystemExit(subprocess.run([str(ROOT/'runtime_profiles/xtts-security-candidate/python.exe'),'-B','-X','utf8','-c',CODE,str(ROOT)],
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8','OMP_NUM_THREADS':'2'},timeout=60).returncode)
