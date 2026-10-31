"""Record exact user-approved examples; not a runtime preset or global quality gate."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / 'docs/validation'


def checked_asset(path):
    path = Path(path).resolve()
    if not path.is_relative_to(VALIDATION.resolve()) or not path.is_file():
        raise ValueError('Accepted example outside retained validation storage')
    return dict(file=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    sujata_path = VALIDATION / '2026-10-04-sujata-reference.json'
    sujata = json.loads(sujata_path.read_text(encoding='utf-8'))
    native = json.loads((VALIDATION / '2026-10-04-native-playback.json').read_text(encoding='utf-8'))
    entries = [
        dict(voice='sujata', **checked_asset(Path(sujata['directory']) / 'candidate.wav'),
             user_feedback='beautiful', scope='Exact 6.049-second cleaned-reference comparison take',
             reference=checked_asset(Path(sujata['directory']) / 'clean-reference.wav'),
             temperature=.90, seed=1234, tempo=1.342, output_sample_rate=24000),
        dict(voice='abhishek', **checked_asset(Path(native['directory']) / 'abhishek-native.wav'),
             user_feedback='beautiful.. but i think the sujata voice has a bit echo',
             scope='Exact native-rate Abhishek comparison take; Sujata caveat does not approve her earlier take',
             temperature=.90, seed=1234, tempo=1.342, output_sample_rate=24000),
    ]
    receipt = dict(acceptance_type='human listening to exact examples', examples=entries,
                   all_text_quality_verified=False, production_preset_promoted=False,
                   automatic_video_pipeline_accepted=False)
    (VALIDATION / '2026-10-04-hindi-accepted-examples.json').write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    sujata.update(human_quality_accepted=True, user_feedback='beautiful',
                  acceptance_scope=entries[0]['scope'], production_preset_promoted=False)
    sujata_path.write_text(json.dumps(sujata, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
