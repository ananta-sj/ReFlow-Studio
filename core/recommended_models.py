"""Curated model catalog, limited to implemented adapters for installation.

Curated, human-picked model recommendations shown in the Marketplace as
suggestions - never installed or connected automatically. Distinct from
core/model_detect.py's find_best_hf_model() (a live download-count ranking
of implemented model repositories): this is a small, hand-maintained list of
specific models worth knowing about, the way a "recommended" section in an
app store works.

Every entry lists a real, currently-existing target for the Marketplace's
existing add-model flows:
  - kind="local_file": a Hugging Face repo URL, added exactly like pasting
    that link into the Local Download tab (verified to exist via the real
    HF API before being hardcoded here - see this session's history).
  - kind="cloud_api": a real API base URL. Ones with a request_preset that
    already exists in core/providers/*/cloud_rest.py connect immediately
    once the user supplies their own API key; the rest use "custom" since
    hand-verifying every vendor's exact request/response shape isn't
    something to guess at - the user fills in the specifics when they add it.
  - kind="reference": not a single downloadable model (a GitHub tool/
    pipeline, or a commercial product with its own installer) - shown as
    informational with a link, not directly installable from here.

local_file entries also carry an optional "approx_vram_gb": a rough,
publicly-known ballpark for that model's typical fp16 local-inference
footprint, used ONLY to compute the Marketplace's "Best For This Device"
hint (see bridge/api.py's _fits_device()) by comparing it against
core/hardware_profile.py's captured hardware snapshot. This is a soft,
approximate hint, not a guarantee and not the same mechanism as the real
ETA/VRAM estimator (bridge/api.py's _model_resource_override(), which uses
the actual downloaded file's size once a model is installed - see
DEVELOPMENT_HISTORY.md's "Generalized Per-Model ETA/VRAM Estimation").
Omitted entirely for models with no reasonably confident public figure,
and never set for cloud_api/reference entries - fit-to-hardware isn't a
meaningful concept for something that doesn't run on this machine at all.

Exactly one entry per stage carries "best": True - an editorial "top pick"
for that stage overall (shown as a "Best" badge in the Marketplace),
independent of approx_vram_gb/best_for_device - unlike that hardware-fit
hint, this can land on a cloud_api or reference entry too, since "best
overall" and "fits your machine" are different questions.

Expanded ~4x per stage (from an earlier, shorter list) so a user has real
choices to compare rather than one or two options - every local_file repo
ID below was independently re-verified against the live HF API before
being added, same standard as the original list.
"""

RECOMMENDED_MODELS = {
    "tts": [
        {
            "name": "Kokoro v1.0", "kind": "local_file",
            "source_url": "https://huggingface.co/hexgrad/Kokoro-82M",
            "note": "Just 82M params - the lightweight go-to for CPU/edge deployments.",
            "tag": "lightweight", "approx_vram_gb": 0.5,
        },
        {
            "name": "Piper", "kind": "local_file",
            "source_url": "https://huggingface.co/rhasspy/piper-voices",
            "note": "Tiny, extremely fast, runs comfortably on a Raspberry Pi - the choice when speed matters most.",
            "tag": "lightweight", "approx_vram_gb": 0.2,
        },
        {
            "name": "SpeechT5 (Microsoft)", "kind": "local_file",
            "source_url": "https://huggingface.co/microsoft/speecht5_tts",
            "note": "Compact, well-documented transformer TTS - a solid lightweight baseline.",
            "tag": "lightweight", "approx_vram_gb": 1,
        },
        {
            "name": "MeloTTS (MyShell)", "kind": "local_file",
            "source_url": "https://huggingface.co/myshell-ai/MeloTTS-English",
            "note": "Real-time-capable CPU inference with genuinely natural prosody.",
            "tag": "lightweight", "approx_vram_gb": 1,
        },
        {
            "name": "Sesame CSM", "kind": "local_file",
            "source_url": "https://huggingface.co/sesame/csm-1b",
            "note": "1B+ params - highly natural, expressive conversational speech.",
            "approx_vram_gb": 3,
        },
        {
            "name": "Bark (Suno)", "kind": "local_file",
            "source_url": "https://huggingface.co/suno/bark",
            "note": "Generates laughter, sighs, and other nonverbal sounds alongside speech - great for expressive narration.",
            "approx_vram_gb": 4,
        },
        {
            "name": "XTTS v2 (Coqui)", "kind": "local_file",
            "source_url": "https://huggingface.co/coqui/XTTS-v2",
            "note": "The established open-source standard for multilingual voice generation.",
            "approx_vram_gb": 4,
        },
        {
            "name": "Parler-TTS Large", "kind": "local_file",
            "source_url": "https://huggingface.co/parler-tts/parler-tts-large-v1",
            "note": "Describe the voice you want in plain English (pace, pitch, accent) instead of picking a preset.",
            "approx_vram_gb": 5,
        },
        {
            "name": "Dia 1.6B (Nari Labs)", "kind": "local_file",
            "source_url": "https://huggingface.co/nari-labs/Dia-1.6B",
            "note": "Multi-speaker dialogue generation in one pass - built for conversational, multi-actor scenes.",
            "approx_vram_gb": 6,
        },
        {
            "name": "Fish Speech 1.5", "kind": "local_file",
            "source_url": "https://huggingface.co/fishaudio/fish-speech-1.5",
            "note": "Strong multilingual quality, actively maintained, popular for real-time voice agents.",
            "approx_vram_gb": 4,
        },
        {
            "name": "Tortoise TTS", "kind": "local_file",
            "source_url": "https://huggingface.co/jbetker/tortoise-tts-v2",
            "note": "Slow but exceptionally high-fidelity, expressive output - quality over speed.",
            "approx_vram_gb": 6,
        },
        {
            "name": "ElevenLabs", "kind": "cloud_api", "best": True,
            "api_base_url": "https://api.elevenlabs.io", "request_preset": "elevenlabs_tts",
            "note": "Industry standard for expressive, high-fidelity speech. Needs your API key.",
        },
        {
            "name": "OpenAI TTS", "kind": "cloud_api",
            "api_base_url": "https://api.openai.com", "request_preset": "openai_tts",
            "note": "Extremely reliable and natural for standard reading tasks. Needs your API key.",
        },
        {
            "name": "Azure AI Speech", "kind": "cloud_api",
            "api_base_url": "https://api.cognitive.microsoft.com", "request_preset": "custom",
            "note": "Huge library of neural voices across languages, enterprise-grade reliability. Needs your Azure key.",
        },
        {
            "name": "Amazon Polly", "kind": "cloud_api",
            "api_base_url": "https://polly.us-east-1.amazonaws.com", "request_preset": "custom",
            "note": "Mature, dependable neural TTS, deeply integrated with AWS pipelines. Needs your AWS credentials.",
        },
        {
            "name": "Cartesia Sonic", "kind": "cloud_api",
            "api_base_url": "https://api.cartesia.ai", "request_preset": "custom",
            "note": "Built for ultra-low-latency real-time generation. Needs your API key.",
        },
    ],
    "stt": [
        {
            "name": "Whisper Large-v3", "kind": "local_file", "best": True,
            "source_url": "https://huggingface.co/openai/whisper-large-v3",
            "note": "OpenAI's open-source weights - the accuracy benchmark across languages.",
            "approx_vram_gb": 10,
        },
        {
            "name": "Faster-Whisper (large-v3)", "kind": "local_file",
            "source_url": "https://huggingface.co/Systran/faster-whisper-large-v3",
            "note": "CTranslate2-optimized Whisper build - same accuracy, much faster on CPU.",
            "tag": "lightweight", "approx_vram_gb": 4,
        },
        {
            "name": "Whisper Large-v3 Turbo", "kind": "local_file",
            "source_url": "https://huggingface.co/openai/whisper-large-v3-turbo",
            "note": "A pruned, distilled large-v3 - dramatically faster with only a small accuracy tradeoff.",
            "tag": "lightweight", "approx_vram_gb": 6,
        },
        {
            "name": "Distil-Whisper (large-v3)", "kind": "local_file",
            "source_url": "https://huggingface.co/distil-whisper/distil-large-v3",
            "note": "Up to 6x faster than large-v3, ~50% smaller, English-focused.",
            "tag": "lightweight", "approx_vram_gb": 3,
        },
        {
            "name": "Whisper Medium", "kind": "local_file",
            "source_url": "https://huggingface.co/openai/whisper-medium",
            "note": "A lighter Whisper size for machines that can't comfortably fit large-v3.",
            "tag": "lightweight", "approx_vram_gb": 5,
        },
        {
            "name": "SeamlessM4T v2 (Meta)", "kind": "local_file",
            "source_url": "https://huggingface.co/facebook/seamless-m4t-v2-large",
            "note": "Excellent multilingual transcription, handles complex audio well.",
            "approx_vram_gb": 9,
        },
        {
            "name": "MMS (Meta)", "kind": "local_file",
            "source_url": "https://huggingface.co/facebook/mms-1b-all",
            "note": "Covers 1,000+ languages - unmatched breadth for low-resource languages.",
            "approx_vram_gb": 4,
        },
        {
            "name": "Canary 1B (NVIDIA)", "kind": "local_file",
            "source_url": "https://huggingface.co/nvidia/canary-1b",
            "note": "Tops several transcription accuracy leaderboards for English/European languages.",
            "approx_vram_gb": 4,
        },
        {
            "name": "Wav2Vec2 Large (Meta)", "kind": "local_file",
            "source_url": "https://huggingface.co/facebook/wav2vec2-large-960h-lv60-self",
            "note": "A classic, extremely well-tested English ASR baseline.",
            "tag": "lightweight", "approx_vram_gb": 2,
        },
        {
            "name": "Deepgram", "kind": "cloud_api",
            "api_base_url": "https://api.deepgram.com", "request_preset": "custom",
            "note": "Fastest, most cost-effective cloud STT - great for real-time streaming. Needs your API key.",
        },
        {
            "name": "AssemblyAI", "kind": "cloud_api",
            "api_base_url": "https://api.assemblyai.com", "request_preset": "custom",
            "note": "Outstanding speaker diarization and audio intelligence. Needs your API key.",
        },
        {
            "name": "Google Cloud Speech-to-Text", "kind": "cloud_api",
            "api_base_url": "https://speech.googleapis.com", "request_preset": "custom",
            "note": "Broad language coverage with strong noisy-audio handling. Needs your API key.",
        },
        {
            "name": "Azure AI Speech", "kind": "cloud_api",
            "api_base_url": "https://api.cognitive.microsoft.com", "request_preset": "custom",
            "note": "Real-time streaming transcription with strong enterprise SLAs. Needs your Azure key.",
        },
        {
            "name": "Rev AI", "kind": "cloud_api",
            "api_base_url": "https://api.rev.ai", "request_preset": "custom",
            "note": "Human-reviewed-grade accuracy option alongside its automated model. Needs your API key.",
        },
    ],
    "translation": [
        {
            "name": "SeamlessM4T v2 (Meta)", "kind": "local_file",
            "source_url": "https://huggingface.co/facebook/seamless-m4t-v2-large",
            "note": "State-of-the-art multimodal translation (text/speech in either direction).",
            "approx_vram_gb": 9,
        },
        {
            "name": "Aya 23 (Cohere)", "kind": "local_file",
            "source_url": "https://huggingface.co/CohereForAI/aya-23-8B",
            "note": "Open-weights model fine-tuned for broad, nuanced multilingual translation.",
            "approx_vram_gb": 16,
        },
        {
            "name": "NLLB-200 (Meta)", "kind": "local_file",
            "source_url": "https://huggingface.co/facebook/nllb-200-distilled-600M",
            "note": "Translates directly between 200+ languages, no forced English intermediary.",
            "tag": "lightweight", "approx_vram_gb": 2,
        },
        {
            "name": "MADLAD-400 (Google)", "kind": "local_file",
            "source_url": "https://huggingface.co/google/madlad400-3b-mt",
            "note": "Trained on 400+ languages including many low-resource ones NLLB doesn't cover as well.",
            "approx_vram_gb": 6,
        },
        {
            "name": "mBART-50", "kind": "local_file",
            "source_url": "https://huggingface.co/facebook/mbart-large-50-many-to-many-mmt",
            "note": "Solid many-to-many baseline across 50 languages, well-tested and lightweight.",
            "tag": "lightweight", "approx_vram_gb": 2.5,
        },
        {
            "name": "TowerInstruct (Unbabel)", "kind": "local_file",
            "source_url": "https://huggingface.co/Unbabel/TowerInstruct-7B-v0.2",
            "note": "An LLM fine-tuned specifically for translation quality - reads more naturally than pure MT models.",
            "approx_vram_gb": 14,
        },
        {
            "name": "Qwen 2.5 Instruct", "kind": "local_file",
            "source_url": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct",
            "note": "Strong general-purpose multilingual LLM, translates well via prompting.",
            "approx_vram_gb": 15,
        },
        {
            "name": "Llama 3.1 8B Instruct", "kind": "local_file",
            "source_url": "https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct",
            "note": "Widely-used general LLM with solid multilingual translation via prompting. Gated (needs HF access approval).",
            "approx_vram_gb": 16,
        },
        {
            "name": "DeepL API", "kind": "cloud_api", "best": True,
            "api_base_url": "https://api-free.deepl.com", "request_preset": "custom",
            "note": "The gold standard for nuanced, natural-sounding text translation. Needs your API key.",
        },
        {
            "name": "Google Cloud Translation", "kind": "cloud_api",
            "api_base_url": "https://translation.googleapis.com", "request_preset": "custom",
            "note": "Unmatched sheer language coverage. Needs your API key.",
        },
        {
            "name": "Microsoft Translator", "kind": "cloud_api",
            "api_base_url": "https://api.cognitive.microsofttranslator.com", "request_preset": "custom",
            "note": "Deep Azure integration and strong document-translation tooling. Needs your Azure key.",
        },
        {
            "name": "OpenAI GPT-4o", "kind": "cloud_api",
            "api_base_url": "https://api.openai.com", "request_preset": "openai_chat",
            "note": "Excellent at preserving tone, idiom, and context vs. literal machine translation. Needs your API key.",
        },
    ],
    "voice": [
        {
            "name": "F5-TTS", "kind": "local_file", "request_preset": "f5tts",
            "source_url": "https://huggingface.co/SWivid/F5-TTS",
            "note": "F5 v1 Base voice cloning (English/Chinese; model weights: CC-BY-NC-4.0). Downloads one pinned checkpoint and vocabulary; "
                    "requires the separate F5 runtime. Vocoder and reference-transcription models "
                    "are downloaded into the project cache on first use. The installed profile uses CPU.",
            "approx_vram_gb": 5,
        },
        {
            "name": "OpenVoice (MyShell)", "kind": "local_file",
            "source_url": "https://huggingface.co/myshell-ai/OpenVoiceV2",
            "note": "Fast cloning with granular control over tone and emotion.",
            "approx_vram_gb": 4,
        },
        {
            "name": "Applio (RVC toolkit)", "kind": "local_file",
            "source_url": "https://huggingface.co/IAHispano/Applio",
            "note": "A modern, actively-maintained RVC-based voice-conversion toolkit - the same family of "
                    "technique this app's own default voice-conversion engine uses.",
            "approx_vram_gb": 3,
        },
        {
            "name": "RVC WebUI (original)", "kind": "local_file",
            "source_url": "https://huggingface.co/lj1995/VoiceConversionWebUI",
            "note": "The original RVC project's own repo - this app's built-in default voice-conversion engine "
                    "is this same technique, connect this to pick a specific alternate checkpoint.",
            "tag": "lightweight", "approx_vram_gb": 2,
        },
        {
            "name": "SpeechT5 Voice Conversion (Microsoft)", "kind": "local_file",
            "source_url": "https://huggingface.co/microsoft/speecht5_vc",
            "note": "A genuine audio-to-audio voice converter (not text-to-speech) from Microsoft's SpeechT5 family.",
            "tag": "lightweight", "approx_vram_gb": 1,
        },
        {
            "name": "ElevenLabs", "kind": "cloud_api", "best": True,
            "api_base_url": "https://api.elevenlabs.io", "request_preset": "elevenlabs_sts",
            "note": "Dominates cloud instant, high-fidelity voice cloning. Needs your API key.",
        },
        {
            "name": "PlayHT", "kind": "cloud_api",
            "api_base_url": "https://api.play.ht", "request_preset": "custom",
            "note": "Strong for maintaining cloned-voice consistency across long-form content. Needs your API key.",
        },
        {
            "name": "Resemble AI", "kind": "cloud_api",
            "api_base_url": "https://app.resemble.ai", "request_preset": "custom",
            "note": "Real-time voice cloning with fine-grained emotion control. Needs your API key.",
        },
        {
            "name": "WellSaid Labs", "kind": "cloud_api",
            "api_base_url": "https://api.wellsaidlabs.com", "request_preset": "custom",
            "note": "Enterprise-focused, especially strong for corporate/e-learning narration voices. Needs your API key.",
        },
    ],
    "enhancer": [
        {
            "name": "Real-ESRGAN", "kind": "local_file",
            "source_url": "https://huggingface.co/ai-forever/Real-ESRGAN",
            "note": "The most widely-used open-source general-purpose upscaler - real photo/video content.",
            "tag": "lightweight", "approx_vram_gb": 2,
        },
        {
            "name": "Real-ESRGAN x4plus (Qualcomm)", "kind": "local_file",
            "source_url": "https://huggingface.co/qualcomm/Real-ESRGAN-x4plus",
            "note": "Optimized weights for efficient on-device inference.",
            "tag": "lightweight", "approx_vram_gb": 1.5,
        },
        {
            "name": "GFPGAN", "kind": "local_file",
            "source_url": "https://huggingface.co/TencentARC/GFPGANv1",
            "note": "The same face-restoration engine this app's own default enhancer already uses - "
                    "connect it explicitly to pick a specific version.",
            "tag": "lightweight", "approx_vram_gb": 2,
        },
        {
            "name": "Swin2SR", "kind": "local_file",
            "source_url": "https://huggingface.co/caidas/swin2SR-classical-sr-x4-64",
            "note": "Transformer-based super-resolution - often sharper fine detail than GAN-based upscalers.",
            "approx_vram_gb": 3,
        },
        {
            "name": "Video2X", "kind": "reference", "best": True,
            "source_url": "https://github.com/k4yt3x/video2x",
            "note": "Best all-in-one local upscaling pipeline (bundles Real-ESRGAN + Waifu2x). "
                    "A tool/pipeline, not a single downloadable model - install it separately, "
                    "then connect its output as a Local Service if you script an endpoint for it.",
        },
        {
            "name": "Anime4K", "kind": "reference",
            "source_url": "https://github.com/bloc97/Anime4K",
            "note": "Fastest open-source real-time upscaler for animated content (shader-based tool).",
        },
        {
            "name": "chaiNNer", "kind": "reference",
            "source_url": "https://github.com/chaiNNer-org/chaiNNer",
            "note": "Node-graph tool for chaining multiple upscaling/restoration models together locally.",
        },
        {
            "name": "Topaz Video AI", "kind": "reference",
            "source_url": "https://www.topazlabs.com/topaz-video-ai",
            "note": "Industry-standard professional upscaling. Commercial product with its own installer.",
        },
    ],
    "filter": [
        {
            "name": "NSFW Image Detection (Falconsai)", "kind": "local_file", "best": True,
            "source_url": "https://huggingface.co/Falconsai/nsfw_image_detection",
            "request_preset": "image_classifier",
            "note": "Lightweight ViT classifier (normal/nsfw) - runs on CPU, no GPU needed. Whole-frame "
                    "blur rather than boxed regions, since a classifier has no localization, unlike NudeNet.",
            "tag": "lightweight", "approx_vram_gb": 1.5,
        },
        {
            "name": "NSFW Image Detector (community ViT)", "kind": "local_file",
            "source_url": "https://huggingface.co/LukeJacob2023/nsfw-image-detector",
            "note": "Another lightweight ViT-based classifier - a second option to compare against Falconsai's.",
            "tag": "lightweight", "approx_vram_gb": 1.5,
        },
        {
            "name": "NSFW Classifier (giacomoarienti)", "kind": "local_file",
            "source_url": "https://huggingface.co/giacomoarienti/nsfw-classifier",
            "note": "Compact ViT classifier, a smaller download than most alternatives.",
            "tag": "lightweight", "approx_vram_gb": 1,
        },
        {
            "name": "Llama Guard 3 Vision", "kind": "local_file",
            "source_url": "https://huggingface.co/meta-llama/Llama-Guard-3-11B-Vision",
            "note": "Meta's multimodal safety model - flags unsafe image content in context. Gated (needs HF access "
                    "approval). 11B params, ~42.6GB download - needs a real GPU with 22GB+ VRAM to run at all.",
            "approx_vram_gb": 22,
        },
        {
            "name": "Hive Moderation", "kind": "cloud_api",
            "api_base_url": "https://api.thehive.ai", "request_preset": "custom",
            "note": "Premier choice for social platforms moderating high volumes of visual content. Needs your API key.",
        },
        {
            "name": "AWS Rekognition", "kind": "cloud_api",
            "api_base_url": "https://rekognition.us-east-1.amazonaws.com", "request_preset": "custom",
            "note": "Enterprise-grade SafeSearch out of the box. Needs your AWS credentials.",
        },
        {
            "name": "Google Cloud Vision", "kind": "cloud_api",
            "api_base_url": "https://vision.googleapis.com", "request_preset": "custom",
            "note": "Robust, enterprise-grade SafeSearch. Needs your API key.",
        },
        {
            "name": "Azure AI Content Safety", "kind": "cloud_api",
            "api_base_url": "https://api.cognitive.microsoft.com", "request_preset": "custom",
            "note": "Configurable severity thresholds across multiple unsafe-content categories. Needs your Azure key.",
        },
        {
            "name": "Sightengine", "kind": "cloud_api",
            "api_base_url": "https://api.sightengine.com", "request_preset": "custom",
            "note": "Fast, purpose-built moderation API with per-frame video scanning. Needs your API key.",
        },
    ],
    "lipsync": [
        {
            "name": "Wav2Lip", "kind": "reference",
            "source_url": "https://github.com/Rudrabha/Wav2Lip",
            "note": "This app's own built-in default lip-sync engine - lightweight enough to run well on CPU-only "
                    "machines, unlike the newer local_file options below which target real-time GPU inference.",
        },
        {
            "name": "MuseTalk", "kind": "local_file",
            "source_url": "https://huggingface.co/TMElyralab/MuseTalk",
            "note": "2025/2026 SOTA real-time lip sync via latent-space inpainting - 30+ FPS on a real GPU, great "
                    "for live avatars. On CPU-only hardware this is dramatically slower than Wav2Lip - only "
                    "worth connecting if you actually have a GPU to run it on.",
            "approx_vram_gb": 6,
        },
        {
            "name": "SadTalker", "kind": "local_file",
            "source_url": "https://huggingface.co/vinthony/SadTalker",
            "note": "Drives a single still photo into a talking-head video from audio alone - useful when there's "
                    "no source video, just a portrait.",
            "approx_vram_gb": 4,
        },
        {
            "name": "LivePortrait", "kind": "local_file",
            "source_url": "https://huggingface.co/KwaiVGI/LivePortrait",
            "note": "Combines lip sync with accurate head movement and facial expression control.",
            "approx_vram_gb": 4,
        },
        {
            "name": "LatentSync (ByteDance)", "kind": "local_file",
            "source_url": "https://huggingface.co/ByteDance/LatentSync",
            "note": "Latent-diffusion lip sync with strong identity preservation - another real GPU-oriented "
                    "alternative to MuseTalk worth comparing.",
            "approx_vram_gb": 8,
        },
        {
            "name": "SyncLabs API", "kind": "cloud_api", "best": True,
            "api_base_url": "https://api.synclabs.so", "request_preset": "custom",
            "note": "Built for developers adding real-time, low-latency lip sync. Needs your API key.",
        },
        {
            "name": "HeyGen API", "kind": "cloud_api",
            "api_base_url": "https://api.heygen.com", "request_preset": "custom",
            "note": "Enterprise-grade avatar generation and synchronization. Needs your API key.",
        },
        {
            "name": "D-ID", "kind": "cloud_api",
            "api_base_url": "https://api.d-id.com", "request_preset": "custom",
            "note": "Well-established API for turning a photo or video into a synced talking presenter. Needs your API key.",
        },
    ],
    "profanity_filter": [
        {
            "name": "XLM-RoBERTa (toxicity fine-tune)", "kind": "local_file",
            "source_url": "https://huggingface.co/textdetox/xlmr-large-toxicity-classifier",
            "note": "Multilingual toxicity/profanity classification across 20+ languages.",
            "approx_vram_gb": 1.5,
        },
        {
            "name": "Toxic-BERT", "kind": "local_file",
            "source_url": "https://huggingface.co/unitary/toxic-bert",
            "note": "Lightweight, widely-used English toxicity classifier - a fast, well-tested baseline.",
            "tag": "lightweight", "approx_vram_gb": 0.5,
        },
        {
            "name": "Multilingual Toxic XLM-RoBERTa (Unitary)", "kind": "local_file",
            "source_url": "https://huggingface.co/unitary/multilingual-toxic-xlm-roberta",
            "note": "A second multilingual option to compare against the textdetox classifier above.",
            "approx_vram_gb": 1.5,
        },
        {
            "name": "RoBERTa Toxicity Classifier (s-nlp)", "kind": "local_file",
            "source_url": "https://huggingface.co/s-nlp/roberta_toxicity_classifier",
            "note": "Compact, fast, English-focused - a good lightweight default.",
            "tag": "lightweight", "approx_vram_gb": 0.5,
        },
        {
            "name": "Perspective API", "kind": "cloud_api",
            "api_base_url": "https://commentanalyzer.googleapis.com", "request_preset": "custom",
            "note": "Free (Google/Jigsaw). Scores text for toxicity across multiple languages. Needs your API key.",
        },
        {
            "name": "OpenAI Moderation API", "kind": "cloud_api", "best": True,
            "api_base_url": "https://api.openai.com", "request_preset": "custom",
            "note": "Free for developers, highly accurate at hate speech/profanity across languages. Needs your API key.",
        },
        {
            "name": "Azure AI Content Safety (Text)", "kind": "cloud_api",
            "api_base_url": "https://api.cognitive.microsoft.com", "request_preset": "custom",
            "note": "Configurable severity thresholds, same service family as the Visual Filter option above. Needs your Azure key.",
        },
        {
            "name": "Amazon Comprehend", "kind": "cloud_api",
            "api_base_url": "https://comprehend.us-east-1.amazonaws.com", "request_preset": "custom",
            "note": "Toxicity detection alongside broader text analysis, deeply integrated with AWS. Needs your AWS credentials.",
        },
    ],
}

# Discoverability is not execution support. Preserve other projects as links,
# but do not offer large downloads that no current provider can execute.
_SUPPORTED_REPOSITORIES = {
    'tts': {'https://huggingface.co/coqui/XTTS-v2'},
    'stt': {'https://huggingface.co/Systran/faster-whisper-large-v3'},
    'translation': {'https://huggingface.co/facebook/nllb-200-distilled-600M'},
    'voice': {'https://huggingface.co/SWivid/F5-TTS'},
    'filter': {'https://huggingface.co/Falconsai/nsfw_image_detection'},
    'profanity_filter': {'https://huggingface.co/s-nlp/roberta_toxicity_classifier'},
}

for _stage, _entries in RECOMMENDED_MODELS.items():
    for _entry in _entries:
        if _entry['kind'] == 'local_file' and _entry.get('source_url') not in _SUPPORTED_REPOSITORIES.get(_stage, set()):
            _entry['kind'] = 'reference'
            _entry.pop('best', None)
            _entry['note'] = 'Reference only: no compatible one-click adapter is implemented for this download. ' + _entry['note']
        elif _entry['kind'] == 'cloud_api' and _entry.get('request_preset') == 'custom':
            _entry.pop('best', None)
            _entry['note'] = 'Requires a verified endpoint/body/response configuration; the API key alone is insufficient. ' + _entry['note']
