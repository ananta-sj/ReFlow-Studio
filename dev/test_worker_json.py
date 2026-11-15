import unittest,os,tempfile,threading
from pathlib import Path
from unittest.mock import Mock,patch
from core.worker_json import read_json,replace,retire
from core.cuda_worker import stopping_criteria_base

class WorkerJsonTests(unittest.TestCase):
    @unittest.skipUnless(os.name=='nt','Windows sharing semantics')
    def test_real_windows_exclusive_file_lock_recovers(self):
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,
            ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        kernel.CreateFileW.restype=wintypes.HANDLE
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'request.json';path.write_text('{"ok":true}',encoding='utf-8')
            handle=kernel.CreateFileW(str(path),0x80000000,0,None,3,0x80,None)
            self.assertNotEqual(handle,ctypes.c_void_p(-1).value)
            lock=threading.Lock();closed=[]
            def close():
                with lock:
                    if not closed:kernel.CloseHandle(handle);closed.append(True)
            timer=threading.Timer(.15,close);timer.start()
            try:self.assertEqual(read_json(path),{'ok':True})
            finally:timer.cancel();timer.join();close()

    def test_temporary_read_lock_is_retried_without_repeating_inference(self):
        path=Mock();path.read_text.side_effect=[PermissionError('scanner lock'),'{"ok":true}']
        check=Mock()
        with patch('core.worker_json.time.sleep'):
            self.assertEqual(read_json(path,check),{'ok':True})
        self.assertEqual(path.read_text.call_count,2);self.assertEqual(check.call_count,2)

    def test_persistent_denial_is_bounded_and_invalid_json_is_not_accepted(self):
        path=Mock();path.read_text.side_effect=PermissionError('denied')
        with patch('core.worker_json.time.sleep'),self.assertRaises(PermissionError):read_json(path)
        self.assertEqual(path.read_text.call_count,5)
        path.read_text.side_effect=None;path.read_text.return_value='partial'
        with self.assertRaises(ValueError):read_json(path)

    def test_cancel_interrupts_lock_retries_and_response_publish_is_bounded(self):
        path=Mock();path.read_text.side_effect=PermissionError('lock')
        with patch('core.worker_json.time.sleep'),self.assertRaisesRegex(RuntimeError,'cancelled'):
            read_json(path,Mock(side_effect=[None,RuntimeError('cancelled')]))
        pending=Mock();pending.replace.side_effect=[PermissionError('lock'),None]
        with patch('core.worker_json.time.sleep'):replace(pending,'result')
        self.assertEqual(pending.replace.call_count,2)

    def test_consumed_sidecar_cleanup_never_discards_successful_response(self):
        path=Mock();path.unlink.side_effect=PermissionError('lock')
        with patch('core.worker_json.time.sleep'):retire(path)
        self.assertEqual(path.unlink.call_count,5)

    def test_separation_and_recognition_do_not_load_transformers(self):
        import builtins
        original=builtins.__import__
        def guarded(name,*args,**kwargs):
            if name=='transformers':raise AssertionError('Unnecessary translation library import')
            return original(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=guarded):
            self.assertIs(stopping_criteria_base('separate'),object)
            self.assertIs(stopping_criteria_base('recognition'),object)

if __name__=='__main__':unittest.main()
