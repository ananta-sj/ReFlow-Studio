import argparse
import os
import shutil
import torch

from cached_path import cached_path
from f5_tts.model import CFM, UNetT, DiT, Trainer
from f5_tts.model.utils import get_tokenizer
from f5_tts.model.dataset import load_dataset
from importlib.resources import files

from accelerate import Accelerator

accelerator = Accelerator()
print(f"Using mixed precision: {accelerator.mixed_precision}")

# -------------------------- Dataset Settings --------------------------- #
target_sample_rate = 24000
n_mel_channels = 100
hop_length = 256
win_length = 1024
n_fft = 1024
mel_spec_type = "vocos"  # 'vocos' or 'bigvgan'


# -------------------------- Argument Parsing --------------------------- #
def parse_args():
    # batch_size_per_gpu = 1000 settting for gpu 8GB
    # batch_size_per_gpu = 1600 settting for gpu 12GB
    # batch_size_per_gpu = 2000 settting for gpu 16GB
    # batch_size_per_gpu = 3200 settting for gpu 24GB

    # num_warmup_updates = 300 for 5000 sample about 10 hours

    # change save_per_updates , last_per_steps change this value what you need  ,

    parser = argparse.ArgumentParser(description="Train CFM Model")

    parser.add_argument(
        "--exp_name", type=str, default="F5TTS_Base", choices=["F5TTS_Base", "E2TTS_Base"], help="Experiment name"
    )
    parser.add_argument("--dataset_name", type=str, default="Emilia_ZH_EN", help="Name of the dataset to use")
    parser.add_argument("--learning_rate", type=float, default=1e-5, help="Learning rate for training")
    parser.add_argument("--batch_size_per_gpu", type=int, default=3200, help="Batch size per GPU")
    parser.add_argument(
        "--batch_size_type", type=str, default="frame", choices=["frame", "sample"], help="Batch size type"
    )
    parser.add_argument("--max_samples", type=int, default=64, help="Max sequences per batch")
    parser.add_argument("--grad_accumulation_steps", type=int, default=1, help="Gradient accumulation steps")
    parser.add_argument("--max_grad_norm", type=float, default=1.0, help="Max gradient norm for clipping")
    parser.add_argument("--epochs", type=int, default=700, help="Number of training epochs")
    parser.add_argument("--num_warmup_updates", type=int, default=1500, help="Warmup steps")
    parser.add_argument("--save_per_updates", type=int, default=4000, help="Save checkpoint every X steps")
    parser.add_argument("--last_per_steps", type=int, default=40000, help="Save last checkpoint every X steps")
    parser.add_argument("--finetune", type=bool, default=True, help="Use Finetune")
    parser.add_argument("--pretrain", type=str, default=None, help="the path to the checkpoint")
    parser.add_argument(
        "--tokenizer", type=str, default="pinyin", choices=["pinyin", "char", "custom"], help="Tokenizer type"
    )
    parser.add_argument(
        "--tokenizer_path",
        type=str,
        default=None,
        help="Path to custom tokenizer vocab file (only used if tokenizer = 'custom')",
    )
    parser.add_argument(
        "--log_samples",
        type=bool,
        default=False,
        help="Log inferenced samples per ckpt save steps",
    )
    parser.add_argument("--logger", type=str, default=None, choices=["wandb", "tensorboard"], help="logger")
    parser.add_argument(
        "--bnb_optimizer",
        type=bool,
        default=False,
        help="Use 8-bit Adam optimizer from bitsandbytes",
    )
    parser.add_argument("--ckpt_dir", required=True, type=str)
    parser.add_argument("--data_dir", required=True, type=str)
    parser.add_argument("--wandb_resume_id", type=str, default=None)
    parser.add_argument("--resume", type=bool, default=False, help="Resume Finetune")

    return parser.parse_args()


# -------------------------- Training Settings -------------------------- #


def main():
    args = parse_args()

    # checkpoint_path = str(files("f5_tts").joinpath(f"../../ckpts/{args.dataset_name}"))
    checkpoint_path = args.ckpt_dir

    # Model parameters based on experiment name
    if args.exp_name == "F5TTS_Base":
        wandb_resume_id = args.wandb_resume_id
        print("wandb resume id is: ", wandb_resume_id)
        model_cls = DiT
        model_cfg = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)
        # ckpt_path = "/home/tts/ttsteam/repos/F5-TTS/runs/indic_langs_11_1hr/ckpt/model_1200000.pt"
        # if args.finetune:
        #     if args.pretrain is None:
        #         ckpt_path = str(cached_path("hf://SWivid/F5-TTS/F5TTS_Base/model_1200000.pt"))
        #     else:
        #         ckpt_path = args.pretrain
    # elif args.exp_name == "E2TTS_Base":
    #     wandb_resume_id = None
    #     model_cls = UNetT
    #     model_cfg = dict(dim=1024, depth=24, heads=16, ff_mult=4)
    #     if args.finetune:
    #         if args.pretrain is None:
    #             ckpt_path = str(cached_path("hf://SWivid/E2-TTS/E2TTS_Base/model_1200000.pt"))
    #         else:
    #             ckpt_path = args.pretrain

    if args.finetune and not args.resume:
        if not os.path.isdir(checkpoint_path):
            os.makedirs(checkpoint_path, exist_ok=True)

        file_checkpoint = os.path.join(checkpoint_path, 'model_last.pt')
        
        # if not os.path.isfile(file_checkpoint): ## UNRELIABLE, if too slow on Multinode, can lead to some nodes training from scratch
        #     # shutil.copy2(load_from, file_checkpoint)
        #     ckpt = torch.load(args.load_from, weights_only=True, map_location="cpu")
        #     del ckpt['step']
        #     torch.save(ckpt, file_checkpoint)
        #     del ckpt
        #     print("copy checkpoint for finetune", load_from, file_checkpoint)

    # Use the tokenizer and tokenizer_path provided in the command line arguments
    tokenizer = args.tokenizer
    if tokenizer == "custom":
        if not args.tokenizer_path:
            raise ValueError("Custom tokenizer selected, but no tokenizer_path provided.")
        tokenizer_path = args.tokenizer_path
    else:
        tokenizer_path = args.dataset_name

    vocab_char_map, vocab_size = get_tokenizer(tokenizer_path, tokenizer)

    print("\nvocab : ", vocab_size)
    print("\nvocoder : ", mel_spec_type)

    mel_spec_kwargs = dict(
        n_fft=n_fft,
        hop_length=hop_length,
        win_length=win_length,
        n_mel_channels=n_mel_channels,
        target_sample_rate=target_sample_rate,
        mel_spec_type=mel_spec_type,
    )

    model = CFM(
        transformer=model_cls(**model_cfg, text_num_embeds=vocab_size, mel_dim=n_mel_channels),
        mel_spec_kwargs=mel_spec_kwargs,
        vocab_char_map=vocab_char_map,
    )

    trainer = Trainer(
        model,
        args.epochs,
        args.learning_rate,
        num_warmup_updates=args.num_warmup_updates,
        save_per_updates=args.save_per_updates,
        checkpoint_path=checkpoint_path,
        batch_size=args.batch_size_per_gpu,
        batch_size_type=args.batch_size_type,
        max_samples=args.max_samples,
        grad_accumulation_steps=args.grad_accumulation_steps,
        max_grad_norm=args.max_grad_norm,
        logger=args.logger,
        wandb_project=args.dataset_name,
        wandb_run_name=args.exp_name,
        wandb_resume_id=wandb_resume_id,
        log_samples=args.log_samples,
        last_per_steps=args.last_per_steps,
        bnb_optimizer=args.bnb_optimizer,
    )

    train_dataset = load_dataset(args.dataset_name, tokenizer, mel_spec_kwargs=mel_spec_kwargs, data_dir=args.data_dir)

    trainer.train(
        train_dataset,
        resumable_with_seed=666,  # seed for shuffling dataset
        num_workers=16
    )


if __name__ == "__main__":
    main()
