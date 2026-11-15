import json,os,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import psutil
from core.cache_maintenance import bytecode,abandoned_jobs
from core.render_context import RenderContext,run_process

class CacheMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def write(self,name,value=b'cache'):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value);return path

    def test_only_disposable_source_bytecode_is_removed(self):
        disposable=self.write('core/__pycache__/module.cpython-310.pyc')
        keep=[self.write(name) for name in ('core/__pycache__/note.txt','runtime_profiles/x/__pycache__/runtime.pyc',
            'models/__pycache__/model.pyc','outputs/checkpoints/voice.wav','outputs/reviews/review.json',
            'temp/jobs/job-live/module.pyc','.git/__pycache__/metadata.pyc','Models/__pycache__/keep.pyc')]
        result=bytecode(self.root)
        self.assertEqual(result['files'],1);self.assertFalse(disposable.exists())
        self.assertTrue(all(path.exists() for path in keep))

    def owner(self,name='job-owned'):
        folder=self.root/'temp/jobs'/name;folder.mkdir(parents=True)
        owner=dict(schema='reflow.workspace-owner.v1',workspace=name,pid=123456,
            process_created=10,created_at=time.time()-200000)
        marker=folder/'workspace-owner.json';marker.write_text(json.dumps(owner),encoding='utf-8')
        os.utime(marker,(time.time()-200000,)*2)
        return folder

    def test_old_dead_owned_jobs_are_removed_but_unknown_or_active_jobs_stay(self):
        dead=self.owner();unknown=self.write('temp/jobs/job-unknown/input.wav')
        with patch('psutil.Process',side_effect=psutil.NoSuchProcess(123456)):
            self.assertEqual(abandoned_jobs(self.root)['jobs'],1)
        self.assertFalse(dead.exists());self.assertTrue(unknown.exists())
        active=self.owner('job-active')
        with patch('psutil.Process',return_value=Mock(create_time=lambda:10)):
            self.assertEqual(abandoned_jobs(self.root)['jobs'],0)
        self.assertTrue(active.exists())

    def test_recent_activity_and_unknown_owner_are_preserved(self):
        recent=self.owner();self.write('temp/jobs/job-owned/working.wav')
        with patch('psutil.Process',side_effect=psutil.NoSuchProcess(123456)):
            self.assertEqual(abandoned_jobs(self.root)['jobs'],0)
        self.assertTrue(recent.exists())

    def test_render_context_has_pid_reuse_safe_owner_and_python_workers_get_no_bytecode_flag(self):
        context=RenderContext(self.root/'temp')
        try:
            owner=json.loads((context.workspace/'workspace-owner.json').read_text())
            self.assertEqual(owner['pid'],os.getpid())
            self.assertAlmostEqual(owner['process_created'],psutil.Process().create_time())
            with patch('subprocess.run') as run:
                run_process(['python.exe','-c','pass'])
                self.assertEqual(run.call_args.args[0],['python.exe','-B','-c','pass'])
                run_process(['ffmpeg','-version'])
                self.assertEqual(run.call_args.args[0],['ffmpeg','-version'])
        finally:context.cleanup()

    def test_cleanup_rejects_a_link_to_external_bytecode(self):
        outside=self.root/'outside';outside.mkdir();protected=outside/'keep.pyc';protected.write_bytes(b'keep')
        project=self.root/'project';project.mkdir()
        try:(project/'__pycache__').symlink_to(outside,target_is_directory=True)
        except OSError:self.skipTest('Symlink creation not permitted')
        bytecode(project);self.assertTrue(protected.exists())

if __name__=='__main__':unittest.main()
