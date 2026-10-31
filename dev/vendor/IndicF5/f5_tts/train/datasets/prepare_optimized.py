import os
import sys
import json
import argparse
from pathlib import Path
from multiprocessing import Pool
from datasets.arrow_writer import ArrowWriter
from f5_tts.model.utils import convert_char_to_pinyin
from tqdm import tqdm

sys.path.append(os.getcwd())

# Increase CSV field size limit
import csv
csv.field_size_limit(sys.maxsize)


# def get_audio_duration(audio_path):
#     """Use SoX for instant audio duration retrieval"""
#     result = os.popen(f"soxi -D {audio_path}").read().strip()
#     return float(result) if result else 0

import subprocess

def get_audio_duration(audio_path):
    """Use ffprobe for accurate duration retrieval without header issues."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", 
             "default=noprint_wrappers=1:nokey=1", audio_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return float(result.stdout.strip()) if result.stdout.strip() else 0
    except Exception as e:
        print(f"Error processing {audio_path}: {e}")
        return 0



def read_audio_text_pairs(csv_file_path):
    """Use AWK to quickly process CSV"""
    awk_cmd = f"awk -F '|' 'NR > 1 {{ print $1, $2 }}' {csv_file_path}"
    output = os.popen(awk_cmd).read().strip().split("\n")

    parent = Path(csv_file_path).parent
    return [(str(parent / line.split(" ")[0]), " ".join(line.split(" ")[1:])) for line in output if len(line.split(" ")) >= 2]


def process_audio(audio_path_text):
    """Processes an audio file: checks existence, computes duration, and converts text to Pinyin"""
    audio_path, text = audio_path_text
    if not Path(audio_path).exists():
        return None

    duration = get_audio_duration(audio_path)
    if duration < 0.1 or duration > 30:
        return None

    text = convert_char_to_pinyin([text], polyphone=True)[0]
    return {"audio_path": audio_path, "text": text, "duration": duration}, duration


def prepare_csv_wavs_dir(input_dir, num_processes=32):
    """Parallelized processing of audio-text pairs using multiprocessing"""
    input_dir = Path(input_dir)
    metadata_path = input_dir / "metadata.csv"
    audio_path_text_pairs = read_audio_text_pairs(metadata_path.as_posix())

    with Pool(num_processes) as pool:
        results = list(tqdm(pool.imap(process_audio, audio_path_text_pairs), total=len(audio_path_text_pairs), desc="Processing audio files"))

    sub_result, durations, vocab_set = [], [], set()
    for result in results:
        if result:
            sub_result.append(result[0])
            durations.append(result[1])
            vocab_set.update(list(result[0]['text']))

    return sub_result, durations, vocab_set


def save_prepped_dataset(out_dir, result, duration_list, text_vocab_set):
    """Writes the processed dataset to disk efficiently"""
    out_dir = Path(out_dir)
    out_dir.mkdir(exist_ok=True, parents=True)
    print(f"\nSaving to {out_dir} ...")

    raw_arrow_path = out_dir / "raw.arrow"
    with ArrowWriter(path=raw_arrow_path.as_posix(), writer_batch_size=1) as writer:
        for line in tqdm(result, desc="Writing to raw.arrow"):
            writer.write(line)  # Stream data directly to Arrow file

    dur_json_path = out_dir / "duration.json"
    with open(dur_json_path.as_posix(), "w", encoding="utf-8") as f:
        json.dump({"duration": duration_list}, f, ensure_ascii=False)

    voca_out_path = out_dir / "new_vocab.txt"
    with open(voca_out_path.as_posix(), "w") as f:
        f.writelines(f"{vocab}\n" for vocab in sorted(text_vocab_set))

    dataset_name = out_dir.stem
    print(f"\nFor {dataset_name}, sample count: {len(result)}")
    print(f"For {dataset_name}, total {sum(duration_list)/3600:.2f} hours")


def prepare_and_save_set(inp_dir, out_dir):
    """Runs the dataset preparation pipeline"""
    sub_result, durations, vocab_set = prepare_csv_wavs_dir(inp_dir)
    save_prepped_dataset(out_dir, sub_result, durations, vocab_set)


def cli():
    """Command-line interface for the script"""
    parser = argparse.ArgumentParser(description="Prepare and save dataset.")
    parser.add_argument("inp_dir", type=str, help="Input directory containing the data.")
    parser.add_argument("out_dir", type=str, help="Output directory to save the prepared data.")

    args = parser.parse_args()
    prepare_and_save_set(args.inp_dir, args.out_dir)


if __name__ == "__main__":
    cli()
