"""No-install Python 3.13 helper checks; not full GFPGAN runtime acceptance."""
import os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CODE=r'''
import json,sys,zipfile,hashlib,os
from pathlib import Path
root=Path(sys.argv[1]);out=root/'docs/validation'
report=dict(passed=False,checks={},full_basicsr_import_tested=False,gfpgan_inference_tested=False,runtime_installed=False)
def check(name,value):
    report['checks'][name]=bool(value)
    if not value:raise AssertionError(name)
try:
    check('python_3_13_16',sys.version_info[:3]==(3,13,16))
    import torch,numpy as np
    torch.set_num_threads(2)
    def offline(event,args):
        if event in {'socket.connect','socket.bind','socket.getaddrinfo','subprocess.Popen','os.system'}:raise RuntimeError('No helper smoke network or compiler execution')
    sys.addaudithook(offline);os.environ['BASICSR_JIT']='False'
    builds=json.loads((out/'2026-10-16-visual-helpers/build-receipt.json').read_text());count=0;paths={}
    for row in builds['packages']:
        wheel=root/row['wheel'];paths[row['name']]=str(wheel)
        check('hash_'+row['name'],hashlib.sha256(wheel.read_bytes()).hexdigest()==row['wheel_sha256'])
        with zipfile.ZipFile(wheel) as archive:
            for filename in archive.namelist():
                if filename.endswith('.py'):compile(archive.read(filename),str(wheel)+'/'+filename,'exec');count+=1
    check('129_sources_compile',count==129)
    sys.path.insert(0,paths['filterpy'])
    import filterpy
    from filterpy.kalman import KalmanFilter
    check('filterpy_wheel_origin',str(filterpy.__file__).startswith(paths['filterpy']))
    f=KalmanFilter(dim_x=2,dim_z=1);f.x=np.array([[0.],[1.]])
    f.F=np.array([[1.,1.],[0.,1.]]);f.H=np.array([[1.,0.]])
    f.predict();f.update(np.array([[1.2]]))
    check('real_filter_update',np.isfinite(f.x).all() and 1.0<float(f.x[0,0])<1.2)
    with zipfile.ZipFile(paths['basicsr']) as archive:
        # Load this unchanged operator source alone; package imports need the future visual closure.
        filename='basicsr/ops/upfirdn2d/upfirdn2d.py'
        scope=dict(__name__='reviewed_operator',__package__='',__file__=paths['basicsr']+'/'+filename)
        exec(compile(archive.read(filename),scope['__file__'],'exec'),scope)
        signal=torch.arange(16,dtype=torch.float32).reshape(1,1,4,4)
        value=scope['upfirdn2d'](signal,torch.ones(1,1))
        check('unchanged_basicsr_cpu_operator',torch.equal(signal,value))
    report.update(passed=True,compiled_sources=count,torch_version=torch.__version__)
except Exception as error:
    import traceback
    report.update(error=repr(error),traceback=traceback.format_exc())
finally:
    (out/'2026-10-16-visual-helpers-smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
raise SystemExit(not report['passed'])
'''
if __name__=='__main__':
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8','OMP_NUM_THREADS':'2'}
    raise SystemExit(subprocess.run([str(ROOT/'runtime_profiles/xtts-security-candidate/python.exe'),'-B','-X','utf8','-c',CODE,str(ROOT)],env=env,timeout=90).returncode)
