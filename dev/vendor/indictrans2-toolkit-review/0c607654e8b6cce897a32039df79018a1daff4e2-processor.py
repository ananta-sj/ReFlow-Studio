import re
from tqdm import tqdm
from queue import Queue
from typing import List, Tuple, Union

from indicnlp.tokenize import indic_tokenize, indic_detokenize
from indicnlp.normalize.indic_normalize import IndicNormalizerFactory
from sacremoses import MosesPunctNormalizer, MosesTokenizer, MosesDetokenizer
from indicnlp.transliterate.unicode_transliterate import UnicodeIndicTransliterator


class IndicProcessor:
    def __init__(self, inference=True):
        self.inference = inference

        self._flores_codes = {
            "asm_Beng": "as",
            "awa_Deva": "hi",
            "ben_Beng": "bn",
            "bho_Deva": "hi",
            "brx_Deva": "hi",
            "doi_Deva": "hi",
            "eng_Latn": "en",
            "gom_Deva": "kK",
            "gon_Deva": "hi",
            "guj_Gujr": "gu",
            "hin_Deva": "hi",
            "hne_Deva": "hi",
            "kan_Knda": "kn",
            "kas_Arab": "ur",
            "kas_Deva": "hi",
            "kha_Latn": "en",
            "lus_Latn": "en",
            "mag_Deva": "hi",
            "mai_Deva": "hi",
            "mal_Mlym": "ml",
            "mar_Deva": "mr",
            "mni_Beng": "bn",
            "mni_Mtei": "hi",
            "npi_Deva": "ne",
            "ory_Orya": "or",
            "pan_Guru": "pa",
            "san_Deva": "hi",
            "sat_Olck": "or",
            "snd_Arab": "ur",
            "snd_Deva": "hi",
            "tam_Taml": "ta",
            "tel_Telu": "te",
            "urd_Arab": "ur",
            "unr_Deva": "hi",
        }

        self._indic_num_map = {
            "\u09e6": "0",
            "0": "0",
            "\u0ae6": "0",
            "\u0ce6": "0",
            "\u0966": "0",
            "\u0660": "0",
            "\uabf0": "0",
            "\u0b66": "0",
            "\u0a66": "0",
            "\u1c50": "0",
            "\u06f0": "0",
            "\u09e7": "1",
            "1": "1",
            "\u0ae7": "1",
            "\u0967": "1",
            "\u0ce7": "1",
            "\u06f1": "1",
            "\uabf1": "1",
            "\u0b67": "1",
            "\u0a67": "1",
            "\u1c51": "1",
            "\u0c67": "1",
            "\u09e8": "2",
            "2": "2",
            "\u0ae8": "2",
            "\u0968": "2",
            "\u0ce8": "2",
            "\u06f2": "2",
            "\uabf2": "2",
            "\u0b68": "2",
            "\u0a68": "2",
            "\u1c52": "2",
            "\u0c68": "2",
            "\u09e9": "3",
            "3": "3",
            "\u0ae9": "3",
            "\u0969": "3",
            "\u0ce9": "3",
            "\u06f3": "3",
            "\uabf3": "3",
            "\u0b69": "3",
            "\u0a69": "3",
            "\u1c53": "3",
            "\u0c69": "3",
            "\u09ea": "4",
            "4": "4",
            "\u0aea": "4",
            "\u096a": "4",
            "\u0cea": "4",
            "\u06f4": "4",
            "\uabf4": "4",
            "\u0b6a": "4",
            "\u0a6a": "4",
            "\u1c54": "4",
            "\u0c6a": "4",
            "\u09eb": "5",
            "5": "5",
            "\u0aeb": "5",
            "\u096b": "5",
            "\u0ceb": "5",
            "\u06f5": "5",
            "\uabf5": "5",
            "\u0b6b": "5",
            "\u0a6b": "5",
            "\u1c55": "5",
            "\u0c6b": "5",
            "\u09ec": "6",
            "6": "6",
            "\u0aec": "6",
            "\u096c": "6",
            "\u0cec": "6",
            "\u06f6": "6",
            "\uabf6": "6",
            "\u0b6c": "6",
            "\u0a6c": "6",
            "\u1c56": "6",
            "\u0c6c": "6",
            "\u09ed": "7",
            "7": "7",
            "\u0aed": "7",
            "\u096d": "7",
            "\u0ced": "7",
            "\u06f7": "7",
            "\uabf7": "7",
            "\u0b6d": "7",
            "\u0a6d": "7",
            "\u1c57": "7",
            "\u0c6d": "7",
            "\u09ee": "8",
            "8": "8",
            "\u0aee": "8",
            "\u096e": "8",
            "\u0cee": "8",
            "\u06f8": "8",
            "\uabf8": "8",
            "\u0b6e": "8",
            "\u0a6e": "8",
            "\u1c58": "8",
            "\u0c6e": "8",
            "\u09ef": "9",
            "9": "9",
            "\u0aef": "9",
            "\u096f": "9",
            "\u0cef": "9",
            "\u06f9": "9",
            "\uabf9": "9",
            "\u0b6f": "9",
            "\u0a6f": "9",
            "\u1c59": "9",
            "\u0c6f": "9",
        }

        self._placeholder_entity_maps = Queue()

        self._en_tok = MosesTokenizer(lang="en")
        self._en_normalizer = MosesPunctNormalizer()
        self._en_detok = MosesDetokenizer(lang="en")
        self._xliterator = UnicodeIndicTransliterator()

        self._multispace_regex = re.compile("[ ]{2,}")
        self._digit_space_percent = re.compile(r"(\d) %")
        self._double_quot_punc = re.compile(r"\"([,\.]+)")
        self._digit_nbsp_digit = re.compile(r"(\d) (\d)")
        self._end_bracket_space_punc_regex = re.compile(r"\) ([\.!:?;,])")

        self._URL_PATTERN = r"\b(?<![\w/.])(?:(?:https?|ftp)://)?(?:(?:[\w-]+\.)+(?!\.))(?:[\w/\-?#&=%.]+)+(?!\.\w+)\b"
        self._NUMERAL_PATTERN = r"(~?\d+\.?\d*\s?%?\s?-?\s?~?\d+\.?\d*\s?%|~?\d+%|\d+[-\/.,:']\d+[-\/.,:'+]\d+(?:\.\d+)?|\d+[-\/.:'+]\d+(?:\.\d+)?)"
        self._EMAIL_PATTERN = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}"
        self._OTHER_PATTERN = r"[A-Za-z0-9]*[#|@]\w+"

    def get_batches(self, sentences: List[str], batch_size=8):
        for i in tqdm(range(0, len(sentences), batch_size)):
            yield sentences[i : i + batch_size]

    def _punc_norm(self, text) -> str:
        text = (
            text.replace("\r", "")
            .replace("(", " (")
            .replace(")", ") ")
            .replace("( ", "(")
            .replace(" )", ")")
            .replace(" :", ":")
            .replace(" ;", ";")
            .replace("`", "'")
            .replace("„", '"')
            .replace("“", '"')
            .replace("”", '"')
            .replace("–", "-")
            .replace("—", " - ")
            .replace("´", "'")
            .replace("‘", "'")
            .replace("‚", "'")
            .replace("’", "'")
            .replace("''", '"')
            .replace("´´", '"')
            .replace("…", "...")
            .replace(" « ", ' "')
            .replace("« ", '"')
            .replace("«", '"')
            .replace(" » ", '" ')
            .replace(" »", '"')
            .replace("»", '"')
            .replace(" %", "%")
            .replace("nº ", "nº ")
            .replace(" :", ":")
            .replace(" ºC", " ºC")
            .replace(" cm", " cm")
            .replace(" ?", "?")
            .replace(" !", "!")
            .replace(" ;", ";")
            .replace(", ", ", ")
        )

        text = self._multispace_regex.sub(" ", text)
        text = self._end_bracket_space_punc_regex.sub(r")\1", text)
        text = self._digit_space_percent.sub(r"\1%", text)
        text = self._double_quot_punc.sub(r'\1"', text)
        text = self._digit_nbsp_digit.sub(r"\1.\2", text)
        return text.strip()

    def _normalize_indic_numerals(self, line: str) -> str:
        """
        Normalize the numerals in Indic languages from native script to Roman script (if present).

        Args:
            line (str): an input string with Indic numerals to be normalized.

        Returns:
            str: an input string with the all Indic numerals normalized to Roman script.
        """
        return "".join([self._indic_num_map.get(c, c) for c in line])

    def _wrap_with_placeholders(self, text: str, patterns: list) -> str:
        """
        Wraps substrings with matched patterns in the given text with placeholders and returns
        the modified text along with a mapping of the placeholders to their original value.

        Args:
            text (str): an input string which needs to be wrapped with the placeholders.
            pattern (list): list of patterns to search for in the input string.

        Returns:
            text (str): a modified text.
        """

        serial_no = 1

        placeholder_entity_map = {}

        indic_failure_cases = [
            "آی ڈی ",
            "ꯑꯥꯏꯗꯤ",
            "आईडी",
            "आई . डी . ",
            "आई . डी .",
            "आई. डी. ",
            "आई. डी.",
            "आय. डी. ",
            "आय. डी.",
            "आय . डी . ",
            "आय . डी .",
            "ऐटि",
            "آئی ڈی ",
            "ᱟᱭᱰᱤ ᱾",
            "आयडी",
            "ऐडि",
            "आइडि",
            "ᱟᱭᱰᱤ",
        ]

        for pattern in patterns:
            matches = set(re.findall(pattern, text))

            # wrap common match with placeholder tags
            for match in matches:
                if pattern == self._URL_PATTERN:
                    # Avoids false positive URL matches for names with initials.
                    if len(match.replace(".", "")) < 4:
                        continue
                if pattern == self._NUMERAL_PATTERN:
                    # Short numeral patterns do not need placeholder based handling.
                    if (
                        len(match.replace(" ", "").replace(".", "").replace(":", ""))
                        < 4
                    ):
                        continue

                # Set of Translations of "ID" in all the suppported languages have been collated.
                # This has been added to deal with edge cases where placeholders might get translated.
                base_placeholder = f"<ID{serial_no}>"

                placeholder_entity_map[f"<ID{serial_no}]"] = match
                placeholder_entity_map[f"< ID{serial_no} ]"] = match
                placeholder_entity_map[f"<ID{serial_no}>"] = match
                placeholder_entity_map[f"< ID{serial_no} >"] = match
                placeholder_entity_map[f"[ID{serial_no}]"] = match
                placeholder_entity_map[f"[ID {serial_no}]"] = match
                placeholder_entity_map[f"[ ID{serial_no} ]"] = match

                for i in indic_failure_cases:
                    placeholder_entity_map[f"<{i}{serial_no}>"] = match
                    placeholder_entity_map[f"< {i}{serial_no} >"] = match
                    placeholder_entity_map[f"< {i} {serial_no} >"] = match
                    placeholder_entity_map[f"<{i} {serial_no}]"] = match
                    placeholder_entity_map[f"< {i} {serial_no} ]"] = match
                    placeholder_entity_map[f"[{i}{serial_no}]"] = match
                    placeholder_entity_map[f"[{i} {serial_no}]"] = match
                    placeholder_entity_map[f"[ {i}{serial_no} ]"] = match
                    placeholder_entity_map[f"[ {i} {serial_no} ]"] = match
                    placeholder_entity_map[f"{i} {serial_no}"] = match
                    placeholder_entity_map[f"{i}{serial_no}"] = match

                text = text.replace(match, base_placeholder)
                serial_no += 1

        text = re.sub(r"\s+", " ", text).replace(">/", ">").replace("]/", "]")
        self._placeholder_entity_maps.put(placeholder_entity_map)
        return text

    def _normalize(
        self,
        text: str,
    ) -> Tuple[str, dict]:
        """
        Normalizes and wraps the spans of input string with placeholder tags. It first normalizes
        the Indic numerals in the input string to Roman script. Later, it uses the input string with normalized
        Indic numerals to wrap the spans of text matching the pattern with placeholder tags.

        Args:
            text (str): input string.
            pattern (list): list of patterns to search for in the input string.

        Returns:
            text (str): the modified text
        """
        patterns = [
            self._EMAIL_PATTERN,
            self._URL_PATTERN,
            self._NUMERAL_PATTERN,
            self._OTHER_PATTERN,
        ]

        text = self._normalize_indic_numerals(text.strip())

        if self.inference:
            text = self._wrap_with_placeholders(text, patterns)

        return text

    def _apply_lang_tags(
        self, sent: str, src_lang: str, tgt_lang: str, delimiter=" "
    ) -> str:
        """
        Add special tokens indicating source and target language to the start of the each input sentence.
        Each resulting input sentence will have the format: "`{src_lang} {tgt_lang} {input_sentence}`".

        Args:
            sent (str): input sentence to be translated.
            src_lang (str): flores lang code of the input sentence.
            tgt_lang (str): flores lang code in which the input sentence will be translated.

        Returns:
            List[str]: list of input sentences with the special tokens added to the start.
        """
        return f"{src_lang}{delimiter}{tgt_lang}{delimiter}{sent.strip()}"

    def _preprocess(
        self,
        sent: str,
        lang: str,
        normalizer: Union[MosesPunctNormalizer, IndicNormalizerFactory],
    ) -> str:
        """
        Preprocess an input text sentence by normalizing, tokenization, and possibly transliterating it.

        Args:
            sent (str): input text sentence to preprocess.
            normalizer (Union[MosesPunctNormalizer, IndicNormalizerFactory]): an object that performs normalization on the text.
            lang (str): flores language code of the input text sentence.

        Returns:
            sent (str): a preprocessed input text sentence
        """
        iso_lang = self._flores_codes.get(lang, "hi")
        sent = self._punc_norm(sent)
        sent = self._normalize(sent)

        transliterate = True
        if lang.split("_")[1] in ["Arab", "Aran", "Olck", "Mtei", "Latn"]:
            transliterate = False

        if iso_lang == "en":
            processed_sent = " ".join(
                self._en_tok.tokenize(
                    self._en_normalizer.normalize(sent.strip()), escape=False
                )
            )
        elif transliterate:
            processed_sent = self._xliterator.transliterate(
                " ".join(
                    indic_tokenize.trivial_tokenize(
                        normalizer.normalize(sent.strip()), iso_lang
                    )
                ),
                iso_lang,
                "hi",
            ).replace(" ् ", "्")
        else:
            processed_sent = " ".join(
                indic_tokenize.trivial_tokenize(
                    normalizer.normalize(sent.strip()), iso_lang
                )
            )

        return processed_sent

    def preprocess_batch(
        self,
        batch: List[str],
        src_lang: str,
        tgt_lang: str,
        is_target: bool = False,
    ) -> List[str]:
        """
        Preprocess an array of sentences by normalizing, tokenization, and possibly transliterating it. It also tokenizes the
        normalized text sequences using sentence piece tokenizer and also adds language tags.

        Args:
            batch (List[str]): input list of sentences to preprocess.
            src_lang (str): flores language code of the input text sentences.
            tgt_lang (str): flores language code of the output text sentences.
            is_target (bool): add language tags if false otherwise skip it.

        Returns:
            List[str]: a list of preprocessed input text sentences.
        """
        normalizer = (
            IndicNormalizerFactory().get_normalizer(self._flores_codes.get(src_lang, "hi"))
            if src_lang != "eng_Latn"
            else None
        )

        preprocessed_sents = [
            self._preprocess(sent, src_lang, normalizer) for sent in batch
        ]

        tagged_sents = (
            [
                self._apply_lang_tags(sent, src_lang, tgt_lang)
                for sent in preprocessed_sents
            ]
            if not is_target
            else preprocessed_sents
        )

        return tagged_sents

    def _postprocess(
        self,
        sent: str,
        lang: str = "hin_Deva",
    ):
        """
        Postprocesses a single input sentence after the translation generation.

        Args:
            sent (str): input sentence to postprocess.
            placeholder_entity_map (dict): dictionary mapping placeholders to the original entity values.
            lang (str): flores language code of the input sentence.

        Returns:
            text (str): postprocessed input sentence.
        """
        placeholder_entity_map = self._placeholder_entity_maps.get()

        if isinstance(sent, tuple) or isinstance(sent, list):
            sent = sent[0]

        lang_code, script_code = lang.split("_")
        iso_lang = self._flores_codes.get(lang, "hi")

        # Fixes for Perso-Arabic scripts
        if script_code in ["Arab", "Aran"]:
            sent = (
                sent.replace(" ؟", "؟")
                .replace(" ۔", "۔")
                .replace(" ،", "،")
                .replace("ٮ۪", "ؠ")
            )

        if lang_code == "ory":
            sent = sent.replace("ଯ଼", "ୟ")

        for k, v in placeholder_entity_map.items():
            sent = sent.replace(k, v)

        return (
            self._en_detok.detokenize(sent.split(" "))
            if lang == "eng_Latn"
            else indic_detokenize.trivial_detokenize(
                self._xliterator.transliterate(sent, "hi", iso_lang),
                iso_lang,
            )
        )

    def postprocess_batch(self, sents: List[str], lang: str = "hin_Deva") -> List[str]:
        """
        Postprocesses a batch of input sentences after the translation generations.

        Args:
            sents (List[str]): batch of translated sentences to postprocess.
            placeholder_entity_map (List[dict]): dictionary mapping placeholders to the original entity values.
            lang (str): flores language code of the input sentences.

        Returns:
            List[str]: postprocessed batch of input sentences.
        """

        postprocessed_sents = [self._postprocess(sent, lang) for sent in zip(sents)]

        # for good reason, empty the placeholder entity map after each batch
        self._placeholder_entity_maps.queue.clear()

        return postprocessed_sents
