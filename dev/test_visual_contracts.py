"""Real tiny frame transforms and simulated lip-sync/detector failures."""
from contextlib import ExitStack
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np
from core import video_frames, model_assets, lipsync_handler
from core.providers.lipsync import musetalk_local
from core.vision.vision_handler import VisionHandler
import pipeline


class VisualContracts(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.source = self.root / 'input.mp4'
        self.output = self.root / 'output.mp4'
        self.output.write_bytes(b'prior output')
        pipeline._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=32x16:r=10:d=0.4',
                              '-c:v', 'mpeg4', str(self.source)])

    def test_wav2lip_batches_preserve_every_video_frame(self):
        from core.wav2lip_stream import frame_batches
        batches = list(frame_batches(str(self.source), 3, 25, .4))
        self.assertEqual([len(frames) for _, frames in batches], [3, 1])
        self.assertTrue(all(fps == 10 for fps, _ in batches))

    def test_musetalk_frame_groups_preserve_source_without_whole_video_buffers(self):
        from core.musetalk_stream import frame_indices, frame_groups
        groups = list(frame_groups(frame_indices(9, 8, True), 4))
        self.assertEqual([len(group) for group in groups], [4, 4, 1])
        self.assertEqual([source for group in groups for source, _ in group], list(range(9)))
        self.assertEqual(groups[-1], [(8, 7)])
        with self.assertRaisesRegex(RuntimeError, 'shorter'):
            list(frame_indices(9, 6, True))
        self.assertEqual(list(frame_indices(1, 3, False)), [(0, 0), (0, 1), (0, 2)])

    def test_wav2lip_tail_audio_window_is_padded(self):
        from core.wav2lip_stream import mel_window
        mel = np.arange(80 * 7, dtype=float).reshape(80, 7)
        window = mel_window(mel, 100, 25)
        self.assertEqual(window.shape, (80, 16))
        np.testing.assert_array_equal(window[:, -1], mel[:, -1])
        with self.assertRaises(ValueError):
            mel_window(mel, 0, 0)
        mel[0, -1] = np.nan
        with self.assertRaises(ValueError):
            mel_window(mel, 100, 25)

    def test_wav2lip_rejects_short_audio_and_invalid_batches(self):
        from core.wav2lip_stream import frame_batches
        with self.assertRaisesRegex(RuntimeError, 'shorter'):
            list(frame_batches(str(self.source), 2, 25, .1))
        with self.assertRaises(ValueError):
            list(frame_batches(str(self.source), 0, 25, .4))

    def test_wav2lip_reader_closes_on_early_consumer_exit(self):
        from core.wav2lip_stream import frame_batches
        capture = Mock()
        capture.isOpened.return_value = True
        capture.get.side_effect = [10, 4]
        capture.read.return_value = (True, np.zeros((16, 32, 3), dtype=np.uint8))
        with patch.object(cv2, 'VideoCapture', return_value=capture):
            batches = frame_batches(str(self.source), 1, 25, .4)
            next(batches)
            batches.close()
        capture.release.assert_called_once()

    def test_optional_visual_runtime_real_video(self):
        from core.optional_runtime import interpreter
        from core.providers.filter.nudenet_local import NudeNetLocalProvider
        if not interpreter('vision'):
            self.skipTest('Optional visual runtime is not installed')
        result = NudeNetLocalProvider().scan_and_blur(str(self.source), str(self.output))
        pipeline._validate_media(result, {'video'})
        reader = cv2.VideoCapture(result)
        try:
            self.assertEqual(reader.get(cv2.CAP_PROP_FRAME_COUNT), 4)
        finally:
            reader.release()

    def test_optional_worker_failure_preserves_previous_output(self):
        from core.providers.filter.nudenet_local import NudeNetLocalProvider
        with patch('core.optional_runtime.interpreter', return_value='isolated-python'), \
             patch('core.optional_runtime.run_feature', side_effect=RuntimeError('worker failed')):
            with self.assertRaisesRegex(RuntimeError, 'worker failed'):
                NudeNetLocalProvider().scan_and_blur(str(self.source), str(self.output))
        self.assertEqual(self.output.read_bytes(), b'prior output')
        self.assertEqual(list(self.root.glob('.reflow-*')), [])

    def test_real_frame_transforms_at_one_two_and_four_times_scale(self):
        for scale in (1, 2, 4):
            result = video_frames.transform_video(str(self.source), str(self.output),
                lambda frame, index: cv2.resize(frame, (32 * scale, 16 * scale)), upscale=scale)
            self.assertEqual(result, str(self.output))
            reader = cv2.VideoCapture(result)
            try:
                self.assertEqual(reader.get(cv2.CAP_PROP_FRAME_WIDTH), 32 * scale)
                self.assertEqual(reader.get(cv2.CAP_PROP_FRAME_HEIGHT), 16 * scale)
                self.assertEqual(reader.get(cv2.CAP_PROP_FRAME_COUNT), 4)
            finally:
                reader.release()
            pipeline._validate_media(result, {'video'})

    def test_gfpgan_inference_error_does_not_publish_original_faces_as_success(self):
        from core.enhancer import FaceEnhancer
        enhancer = FaceEnhancer.__new__(FaceEnhancer)
        enhancer.upscale = 1
        enhancer.restorer = Mock(device='cpu')
        enhancer.restorer.face_helper.cropped_faces = [np.zeros((16, 16, 3), dtype=np.uint8)]
        enhancer.restorer.gfpgan.side_effect = RuntimeError('inference ran out of memory')
        with self.assertRaisesRegex(RuntimeError, 'out of memory'):
            enhancer.enhance(str(self.source), str(self.output))
        self.assertEqual(self.output.read_bytes(), b'prior output')
        self.assertEqual(list(self.root.glob('.reflow-*')), [])

    def test_frame_failure_preserves_old_destination(self):
        def transform(frame, index):
            if index == 1:
                raise RuntimeError('enhancement failed on frame 2')
            return frame
        with self.assertRaisesRegex(RuntimeError, 'frame 2'):
            video_frames.transform_video(str(self.source), str(self.output), transform)
        self.assertEqual(self.output.read_bytes(), b'prior output')
        self.assertEqual(list(self.root.glob('.reflow-*')), [])

    def test_wrong_scaled_frame_cannot_be_written(self):
        with self.assertRaisesRegex(RuntimeError, 'dimensions'):
            video_frames.transform_video(str(self.source), str(self.output), lambda frame, index: frame, upscale=2)
        self.assertEqual(self.output.read_bytes(), b'prior output')

    def test_reader_and_writer_open_failures_are_explicit(self):
        reader = Mock()
        reader.isOpened.return_value = False
        with patch.object(cv2, 'VideoCapture', return_value=reader):
            with self.assertRaisesRegex(RuntimeError, 'open video'):
                video_frames.transform_video(str(self.source), str(self.output), lambda frame, index: frame)
        reader.release.assert_called_once()
        writer = Mock()
        writer.isOpened.return_value = False
        with patch.object(cv2, 'VideoWriter', return_value=writer):
            with self.assertRaisesRegex(RuntimeError, 'writer'):
                video_frames.transform_video(str(self.source), str(self.output), lambda frame, index: frame)
        writer.release.assert_called_once()
        self.assertEqual(self.output.read_bytes(), b'prior output')

    def test_cancelled_frame_stage_keeps_old_output(self):
        with patch.object(video_frames, 'check_cancelled', side_effect=RuntimeError('cancelled')):
            with self.assertRaisesRegex(RuntimeError, 'cancelled'):
                video_frames.transform_video(str(self.source), str(self.output), lambda frame, index: frame)
        self.assertEqual(self.output.read_bytes(), b'prior output')

    def test_detector_new_api_labels_and_failures(self):
        scanner = VisionHandler.__new__(VisionHandler)
        scanner.enabled = True
        scanner.detector = Mock()
        scanner.detector.detect.return_value = [{'class': 'FEMALE_BREAST_EXPOSED', 'score': .9, 'box': [1, 2, 3, 4]}]
        frame = object()
        self.assertEqual(scanner.scan_frame(frame), [[1, 2, 4, 6]])
        scanner.detector.detect.assert_called_once_with(frame)
        scanner.detector.detect.side_effect = RuntimeError('detector failed')
        with self.assertRaisesRegex(RuntimeError, 'detection failed'):
            scanner.scan_frame(frame)
        scanner.enabled = False
        with self.assertRaisesRegex(RuntimeError, 'unavailable'):
            scanner.scan_frame(frame)

    def test_missing_detector_does_not_disable_filter_silently(self):
        with patch.dict('sys.modules', {'nudenet': None}):
            with self.assertRaisesRegex(RuntimeError, 'initialization failed'):
                VisionHandler()

    def test_wav2lip_nonzero_exit_cannot_publish(self):
        handler = lipsync_handler.LipSyncHandler.__new__(lipsync_handler.LipSyncHandler)
        handler.model_path = str(self.root / 'checkpoint.pth')
        Path(handler.model_path).write_bytes(b'fixture')
        handler.wav2lip_dir = str(self.root)
        audio = self.root / 'audio.wav'
        audio.write_bytes(b'fixture')
        with patch.object(lipsync_handler.config, 'TEMP_PATH', str(self.root)), \
             patch.object(lipsync_handler, 'run_process', side_effect=subprocess.CalledProcessError(1, ['fixture'])) as process:
            with self.assertRaisesRegex(RuntimeError, 'execution failed'):
                handler.execute(str(self.source), str(audio), str(self.output))
        self.assertTrue(process.call_args.kwargs['check'])
        self.assertEqual(self.output.read_bytes(), b'prior output')

    def test_musetalk_nonzero_exit_and_stale_result_cannot_publish(self):
        self.stack.enter_context(patch('core.optional_runtime.interpreter', return_value=None))
        provider = musetalk_local.MuseTalkLocalProvider()
        provider.unet_model_path = str(self.root / 'checkpoint.pth')
        Path(provider.unet_model_path).write_bytes(b'fixture')
        stale = self.root / 'results/v15/result.mp4'
        stale.parent.mkdir(parents=True)
        stale.write_bytes(b'old result' * 200)
        with patch.object(musetalk_local.config, 'TEMP_PATH', str(self.root)), \
             patch.object(model_assets, 'ensure_assets'), \
             patch.object(musetalk_local, 'run_process', side_effect=subprocess.CalledProcessError(1, ['fixture'])) as process:
            with self.assertRaises(subprocess.CalledProcessError):
                provider.execute(str(self.source), 'unused.wav', str(self.output))
        self.assertTrue(process.call_args.kwargs['check'])
        self.assertEqual(self.output.read_bytes(), b'prior output')
        self.assertTrue(stale.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
