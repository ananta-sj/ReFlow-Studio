import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


class VideoExportCopyTests(unittest.TestCase):
    def test_h264_frames_are_preserved_while_audio_and_subtitles_are_replaced(self):
        from core.pipeline import ReflowPipeline
        import core.pipeline as pipeline
        import numpy as np
        root = Path(__file__).resolve().parents[1]
        ffmpeg, ffprobe = root/'ffmpeg/bin/ffmpeg.exe', root/'ffmpeg/bin/ffprobe.exe'
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source, voice, result = folder/'source.mp4', folder/'voice.wav', folder/'result.mp4'
            subtitle = folder/'words.srt'
            subtitle.write_text('1\n00:00:00,000 --> 00:00:01,500\nHello\n', encoding='utf-8')
            subprocess.run([str(ffmpeg), '-v', 'error', '-y', '-f', 'lavfi', '-i',
                'testsrc=size=96x64:rate=10', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=8000',
                '-t', '2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(source)], check=True)
            subprocess.run([str(ffmpeg), '-v', 'error', '-y', '-f', 'lavfi', '-i',
                'sine=frequency=220:sample_rate=8000', '-t', '2', str(voice)], check=True)
            with patch.dict(os.environ, PATH=str(ffmpeg.parent)+os.pathsep+os.environ.get('PATH', '')), patch('core.pipeline._run_ffmpeg', wraps=pipeline._run_ffmpeg) as commands:
                ReflowPipeline.__new__(ReflowPipeline).merge_av(str(source), str(voice), str(subtitle),
                    str(result), ffmpeg_preset='veryslow', subtitle_language='hin')
            self.assertEqual(commands.call_args_list[0].args[0][commands.call_args_list[0].args[0].index('-c:v')+1], 'copy')
            def frames(path):
                output = subprocess.check_output([str(ffmpeg), '-v', 'error', '-i', str(path), '-an', '-f', 'framemd5', '-'])
                return [line.split(b',')[-1].strip() for line in output.splitlines() if line and not line.startswith(b'#')]
            self.assertEqual(frames(source), frames(result))
            raw = subprocess.check_output([str(ffmpeg), '-v', 'error', '-i', str(result), '-vn', '-f', 's16le', '-ac', '1', '-ar', '8000', '-'])
            samples = np.frombuffer(raw, dtype=np.int16)
            frequency = np.argmax(abs(np.fft.rfft(samples)))*8000/len(samples)
            self.assertAlmostEqual(frequency, 220, delta=5)
            media = json.loads(subprocess.check_output([str(ffprobe), '-v', 'error', '-show_streams', '-of', 'json', str(result)]))
            self.assertEqual({stream['codec_type'] for stream in media['streams']}, {'video', 'audio', 'subtitle'})
