"""Preview speaker groups and reference clips from a vocal WAV and timed cues.

This experimental command expects mostly single-speaker cues. It assigns
anonymous speaker labels and does not change the render's selected voices.
"""

import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]


def group_speakers(vectors, minimum_similarity):
    import numpy as np
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform

    normalized = np.asarray(vectors)
    norms = np.linalg.norm(normalized, axis=1)
    if not np.isfinite(normalized).all() or np.any(norms <= 0):
        raise ValueError('Speaker encoder returned an invalid embedding')
    normalized = normalized / norms[:, None]
    similarities = np.clip(normalized @ normalized.T, -1, 1)
    distances = 1 - similarities
    np.fill_diagonal(distances, 0)
    if len(vectors) == 1:
        return [1], similarities
    # Complete linkage avoids joining two dissimilar voices through a chain
    # of borderline matches to other turns.
    clusters = linkage(squareform(distances, checks=False), method='complete')
    labels = fcluster(clusters, 1 - minimum_similarity, criterion='distance')
    return labels.tolist(), similarities


def preview(vocal_path, cues_path, output, minimum_similarity):
    from pydub import AudioSegment
    from pydub.silence import detect_nonsilent
    from TTS.tts.models.xtts import load_audio
    import torch
    from core.transcription import normalize_transcription, require_media_bounds
    from core.tts.tts_handler import TTSHandler

    audio = AudioSegment.from_wav(vocal_path).set_channels(1)
    cues = normalize_transcription(json.loads(cues_path.read_text(encoding='utf-8-sig')))
    require_media_bounds(cues, len(audio)/1000)
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for index, cue in enumerate(cues):
        rows.append(dict(index=index, start=cue['start'], end=cue['end'], status='needs_review'))
    torch.set_num_threads(min(torch.get_num_threads(), 5))
    model = TTSHandler(device='cpu', model_path=str(ROOT/'models/xtts/default')).tts.synthesizer.tts_model
    vectors, extracted = [], []
    for row in rows:
        start, end = row['start'], row['end']
        if any(other is not row and min(end, other['end']) - max(start, other['start']) > .08 for other in rows):
            row['reason'] = 'Overlapping cue windows'
            continue
        clip = audio[round(start*1000):round(min(end,start+6)*1000)]
        if len(clip) < 800 or not math.isfinite(clip.dBFS) or clip.dBFS < -45:
            row['reason'] = 'Too short or quiet to match'
            continue
        ranges = detect_nonsilent(clip, min_silence_len=200, silence_thresh=max(-48, clip.dBFS-18))
        if not ranges or sum(right-left for left,right in ranges) < 650:
            row['reason'] = 'Too little audible material'
            continue
        clip = clip[max(0,ranges[0][0]-30):min(len(clip),ranges[-1][1]+40)]
        path = output/f'turn-{row["index"]:04d}.wav'
        clip.export(path, format='wav').close()
        with torch.inference_mode():
            embedding = model.get_speaker_embedding(load_audio(str(path), 16000), 16000)
        vectors.append(embedding.flatten().cpu().numpy())
        extracted.append((row, path, len(clip)))
    if not vectors:
        raise ValueError('No usable source turns')
    labels, similarities = group_speakers(vectors, minimum_similarity)
    groups = {}
    for index, label in enumerate(labels):
        groups.setdefault(label, []).append(index)
    speakers = []
    for members in groups.values():
        if len(members) < 2:
            extracted[members[0]][0]['reason'] = 'No second matching turn'
            continue
        alternatives = [index for index in range(len(labels)) if index not in members]
        for index in members:
            own = min(float(similarities[index,j]) for j in members if j != index)
            other = max((float(similarities[index,j]) for j in alternatives), default=-1)
            if own-other < .10:
                extracted[index][0]['reason'] = 'Similar match to another group'
        confident = [index for index in members if 'reason' not in extracted[index][0]]
        reference_candidates = [index for index in confident if extracted[index][2] >= 2000]
        if len(confident) < 2 or not reference_candidates:
            for index in confident:
                extracted[index][0]['reason'] = 'Group lacks enough evidence or a usable reference'
            continue
        reference = max(reference_candidates, key=lambda index: extracted[index][2])
        speaker_id = f'Speaker {len(speakers)+1}'
        speakers.append(dict(id=speaker_id, reference=extracted[reference][1].name,
                             reference_seconds=extracted[reference][2]/1000))
        for index in confident:
            extracted[index][0].update(status='suggested', speaker=speaker_id)
    result = dict(status='review_required', minimum_similarity=minimum_similarity,
                  speakers=speakers, cues=rows)
    path = output/'speaker-cast.json'
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('vocal_wav', type=Path)
    parser.add_argument('timed_cues_json', type=Path)
    parser.add_argument('new_output_folder', type=Path)
    parser.add_argument('--minimum-similarity', type=float, default=.55)
    args = parser.parse_args()
    if not .1 <= args.minimum_similarity <= .99:
        parser.error('minimum similarity must be between .1 and .99')
    print(preview(args.vocal_wav,args.timed_cues_json,args.new_output_folder,args.minimum_similarity))
