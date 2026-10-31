"""Local toxicity-classifier profanity-filter provider - for a
"local_file" ProfanityFilter Marketplace entry backed by a sequence
classifier (e.g. textdetox/xlmr-large-toxicity-classifier), distinct
from the Ollama default (core/providers/profanity_filter/ollama_local.py),
which never actually loads a Marketplace-connected local_file model -
see core/providers/resolve.py.

A classifier only scores text, it can't rewrite/censor it the way an
instructable LLM can (ProfanityFilterProvider.filter_text's whole
contract) - so "filtering" here means replacing a line the classifier
scores as toxic with a fixed placeholder, the same "bleep the whole
line" tradeoff broadcast media uses when a clean edit isn't available,
rather than pretending word-level rewriting is possible from a model
that was never trained to generate text at all.
"""

from core.providers.label_contract import positive_index
from core.providers.base import ProfanityFilterProvider

_TOXIC_LABEL = "toxic"
# 0.5 (this classifier's own naive midpoint) turned out to be too
# aggressive for anything outside its training distribution (short,
# informal social-media-style toxic/hate speech): a real benign
# documentary-narration line, once translated, scored 0.9028 toxic and
# was silently deleted - most likely because NLLB's translation happened
# to land on a negative/ominous-sounding word ("अशुभ", "inauspicious")
# for "lacklustre", and the classifier over-associates negative sentiment
# with toxicity for prose it wasn't trained on. Genuinely profane content
# from the same real transcript scored 0.9991 - comfortable margin above
# 0.95, so raising the bar here to just above the measured false
# positive (rather than a round 0.8/0.9 guess) trades away only that
# specific low-confidence-for-actual-toxicity band, while the real
# detection keeps ~0.05 of headroom below it.
_DEFAULT_THRESHOLD = 0.95
_PLACEHOLDER = "[line removed by profanity filter]"


class ClassifierProfanityFilterProvider(ProfanityFilterProvider):
    supports_line_removal = True
    def __init__(self, model_path, device=None, threshold=_DEFAULT_THRESHOLD):
        self.model_path = model_path
        self.device = device or "cpu"
        self.threshold = threshold
        self._model = None
        self._tokenizer = None
        # lazy + cached: filter_text() runs once per subtitle segment, but
        # loading the model/tokenizer from disk must happen once per video.

    def _ensure_loaded(self):
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        # local_files_only=True - see core/providers/translation/
        # nllb_local.py's comment on the same line: from_pretrained()
        # attempts a network check even for an already-downloaded local
        # directory unless told not to, observed hanging for 15+ minutes
        # on a slow connection.
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_path, local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(self.model_path, local_files_only=True)
        if self.device.startswith("cuda") and torch.cuda.is_available():
            model = model.to(self.device)
        else:
            self.device = "cpu"
        model.eval()

        # id2label's exact casing/wording varies by checkpoint - resolved
        # once here against the actually-loaded config rather than
        # hardcoding an index, so a differently-labeled classifier
        # (e.g. "TOXIC" vs "toxic", or a 3-class scheme) fails clearly
        # instead of silently scoring the wrong class as "toxic".
        positive = positive_index(model.config.id2label, {'toxic', 'toxicity'}, {'neutral', 'non_toxic', 'not_toxic', 'non_toxicity'})

        self._toxic_index = positive
        self._model = model

    def filter_text(self, text, custom_instructions=""):
        # custom_instructions is accepted for interface compatibility with
        # every other ProfanityFilterProvider, but a fixed classifier has
        # no prompt mechanism to steer - same documented limitation as
        # TranslationProvider's M2M100 fallback.
        if not text or not text.strip():
            return text
        if custom_instructions.strip():
            raise ValueError("A fixed classifier cannot apply custom instructions")
        self._ensure_loaded()

        import torch

        inputs = self._tokenizer(text, return_tensors="pt", truncation=True, max_length=512).to(self.device)
        with torch.no_grad():
            logits = self._model(**inputs).logits
        probs = torch.softmax(logits, dim=-1)[0]
        toxic_score = probs[self._toxic_index].item()

        return "" if toxic_score >= self.threshold else text
