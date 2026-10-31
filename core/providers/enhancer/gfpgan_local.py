"""Local GFPGAN face-enhancer provider - thin wrapper around the
existing FaceEnhancer. Called once per video (not per-segment), so
unlike the TTS/RVC providers there's no lazy-cache regression risk here -
matches the original pipeline.py's own one-shot instantiation."""

from core.providers.base import EnhancerProvider


class GFPGANLocalProvider(EnhancerProvider):
    def __init__(self, device=None, upscale=1, model_path=None, runtime='legacy'):
        if runtime not in ('legacy','isolated'):raise ValueError('Unknown face enhancement runtime')
        if runtime=='isolated' and device not in (None,'cpu'):raise ValueError('Isolated face enhancement supports CPU only')
        self.runtime=runtime
        self.device = device
        self.upscale = upscale
        self.model_path = model_path

    def enhance(self, video_path, output_path):
        if self.runtime=='isolated':
            return self._isolated(video_path,output_path)
        from enhancer import FaceEnhancer
        enhancer = FaceEnhancer(device=self.device, upscale=self.upscale, model_path=self.model_path)
        return enhancer.enhance(video_path, output_path)

    def _isolated(self,video_path,output_path):
        import json,os,tempfile
        from pathlib import Path
        from core.visual_runtime import validate,model_contract
        from core.python_runtime import project_root
        from core.render_context import current_job,run_process
        from pipeline import _staged_output
        route=validate();contract=model_contract(self.model_path,verify_weights=True)
        self.runtime_identity=route['identity'];self.worker_interpreter=route['executable'];self.engine_id='gfpgan'
        root=project_root();job=current_job();parent=job.workspace if job else root/'temp'
        with tempfile.TemporaryDirectory(prefix='visual-',dir=parent) as folder,_staged_output(output_path) as pending:
            request=Path(folder)/'request.json';evidence=Path(folder)/'evidence.json'
            request.write_text(json.dumps(dict(**contract,device='cpu',upscale=self.upscale,input_path=str(Path(video_path).resolve()),output_path=str(Path(pending).resolve()),evidence_path=str(evidence))),encoding='utf-8')
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8','REFLOW_OFFLINE':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1',
                 'BASICSR_EXT':'False','BASICSR_JIT':'False','TEMP':folder,'TMP':folder,'TORCH_HOME':folder,'MPLCONFIGDIR':folder,
                 'PATH':str(root/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')}
            log=Path(folder)/'worker.log'
            try:
                with log.open('wb') as stream:run_process([route['executable'],'-B',str(root/'core/run_visual.py'),str(request)],check=True,timeout=3600,stdout=stream,stderr=stream,env=env)
            except Exception as error:
                from core.render_context import RenderCancelled
                if isinstance(error,RenderCancelled):raise
                with log.open('rb') as stream:
                    stream.seek(max(0,log.stat().st_size-6000));detail=stream.read().decode('utf-8',errors='replace')
                raise RuntimeError('Isolated face enhancement failed: '+detail) from error
            self.last_worker_evidence=json.loads(evidence.read_text(encoding='utf-8'))
        return output_path
