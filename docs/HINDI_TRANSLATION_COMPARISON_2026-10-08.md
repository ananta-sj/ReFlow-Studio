# Hindi translation comparison — 8 October 2026

Both engines ran offline on the same 19 inputs. Production defaults are unchanged. These are generated candidates for human review; no automatic semantic winner or release approval is claimed.

IndicTrans2 revision: `89cd0007fd7b9e0693a2fd4404d187e07dac79fd`. Transformers 4.51.3; FP16 CUDA, eager attention, five beams, deterministic decoding.

IndicTrans2 peak allocated GPU memory: 2.234 GiB. Model load: 7.656 seconds. Full evaluation: 56.656 seconds.

The historical pure-Python toolkit and its Indic NLP wheel substitution remain evaluation-only. Synthetic preprocessing revealed phone-number spacing changes. Check every quantity, negation, name, idiom and film term below before using these translations in a dub.

| Case | Source | NLLB | IndicTrans2 |
| --- | --- | --- | --- |
| video-1 | Before long, a standard news report visual language established itself, one that's immediately recognisable to anyone. | जल्द ही, एक मानक समाचार रिपोर्ट दृश्य भाषा स्थापित हो गई, जो किसी को भी तुरंत पहचानने योग्य है। | जल्द ही, एक मानक समाचार रिपोर्ट दृश्य भाषा ने खुद को स्थापित कर लिया, जिसे कोई भी तुरंत पहचान सकता है। |
| video-2 | Me has this report. | मेरे पास यह रिपोर्ट है। | मेरे पास यह रिपोर्ट है। |
| video-3 | It starts here, with a lacklustre establishing shot of a significant location. | यह यहाँ से शुरू होता है, एक महत्वपूर्ण स्थान की एक अस्पष्ट स्थापित तस्वीर के साथ। | यह यहाँ से शुरू होता है, एक महत्वपूर्ण स्थान की एक नीरस स्थापना शॉट के साथ। |
| video-4 | Next, a walkie-talkie preamble from the auteur, pacing steadily towards the lens, punctuating every other sentence with a hand gesture and ignoring all the pricks milling around him like he's gliding through the fucking matrix, before coming to a halt and posing a question. | इसके बाद, लेखक से एक वॉकी-टॉकी प्रस्तावना, लेंस की ओर लगातार कदम, एक हाथ के इशारे के साथ प्रत्येक दूसरे वाक्य को अंकित करना और उन सभी कुतियाओं को अनदेखा करना जो उसके चारों ओर मिल रहे हैं जैसे कि वह गंदगी मैट्रिक्स के माध्यम से स्लाइड कर रहा है, रुकने से पहले और एक सवाल पूछने से पहले। | इसके बाद, ऑटूर की ओर से एक वॉकी-टॉकी प्रस्तावना, लेंस की ओर लगातार गति करती है, एक हाथ के इशारे के साथ हर दूसरे वाक्य को विराम देती है और उसके चारों ओर घूमते हुए सभी चुभनों को अनदेखा करती है जैसे कि वह कमबख्त मैट्रिक्स के माध्यम से ग्लाइडिंग कर रहा है, रुकने से पहले और एक सवाल पूछने से पहले। |
| video-5 | What comes next? | इसके बाद क्या होगा? | आगे क्या होगा? |
| video-6 | Often something like this, a filler shot designed to give your eyes something to look at while my voice babbles on about facts. | अक्सर कुछ इस तरह की, एक फिलर शॉट जो आपकी आंखों को देखने के लिए कुछ देने के लिए डिज़ाइन किया गया है जबकि मेरी आवाज तथ्यों के बारे में बकवास करती है। | अक्सर कुछ इस तरह, एक भराव शॉट आपकी आँखों को देखने के लिए कुछ देने के लिए डिज़ाइन किया गया है जबकि मेरी आवाज़ तथ्यों के बारे में बतखाती है। |
| video-7 | Sometimes it'll slow down to a halt, turn monochrome and some of those facts will appear one by one on the screen. | कभी-कभी यह धीमा हो जाता है, मोनोक्रोम हो जाता है और कुछ तथ्य स्क्रीन पर एक के बाद एक दिखाई देंगे। | कभी-कभी यह रुक जाता है, मोनोक्रोम हो जाता है और उनमें से कुछ तथ्य स्क्रीन पर एक-एक करके दिखाई देंगे। |
| video-8 | This is followed by the obligatory shots of overweight people with their faces subtly framed out, after which the report is padded out with a selection of lazy and pointless Vox Pops. | इसके बाद अधिक वजन वाले लोगों के अनिवार्य शॉट होते हैं जिनके चेहरे सूक्ष्म रूप से तैयार होते हैं, जिसके बाद रिपोर्ट को आलसी और निरर्थक Vox Pops के चयन से भरा जाता है। | इसके बाद अधिक वजन वाले लोगों के अनिवार्य शॉट्स होते हैं जिनके चेहरे सूक्ष्म रूप से तैयार किए जाते हैं, जिसके बाद रिपोर्ट को आलसी और व्यर्थ वॉक्स पॉप्स के चयन के साथ तैयार किया जाता है। |
| morning-is-not-afternoon | Good morning. | सुप्रभात. | शुभ प्रभात। |
| greeting-with-context | Good morning. This is a short test. | सुप्रभात, यह एक छोटी सी परीक्षा है। | सुप्रभात। यह एक छोटी सी परीक्षा है। |
| negation | I do not want to cancel the order. | मैं आदेश को रद्द नहीं करना चाहता। | मैं आदेश को रद्द नहीं करना चाहता। |
| time-and-date | The meeting is at 9:30 tomorrow morning. | बैठक कल सुबह 9:30 बजे है। | बैठक कल सुबह 9.30 बजे होगी। |
| numbers-and-negation | The price is 1,250 rupees, not 250 rupees. | कीमत 1,250 रुपये है, 250 रुपये नहीं। | कीमत 1,250 रुपये है, 250 रुपये नहीं। |
| question | Could you speak more slowly, please? | क्या आप धीरे-धीरे बात कर सकते हैं, कृपया? | क्या आप धीरे-धीरे बोल सकते हैं? |
| brand-and-action | ReFlow Studio keeps the original background music. | रिफ्लो स्टूडियो मूल पृष्ठभूमि संगीत रखता है। | रीफ्लो स्टूडियो मूल पार्श्व संगीत रखता है। |
| multi-sentence-reference | Some call me nature. Others call me Mother Nature. | कुछ मुझे प्रकृति कहते हैं, अन्य मुझे माँ प्रकृति कहते हैं। | कुछ लोग मुझे प्रकृति कहते हैं। कुछ लोग मुझे प्रकृति माता कहते हैं। |
| held-out-apology | I'm sorry, I didn't mean to interrupt you. Please go on. | मुझे खेद है, मैं आपको बाधित करने का इरादा नहीं था. कृपया जारी रखें. | क्षमा करें, मैं आपको बाधित नहीं करना चाहता था। कृपया आगे बढ़ें। |
| held-out-reassurance | Don't worry. We still have enough time to fix this. | चिंता मत करो, हमारे पास अभी भी इसे ठीक करने के लिए पर्याप्त समय है। | चिंता मत करो। हमारे पास अभी भी इसे ठीक करने के लिए पर्याप्त समय है। |
| held-out-phone | Call +91-9876543210 at 10:30. | 10:30 बजे +91-9876543210 पर कॉल करें। | 10:30 पर + 91-9876543210 पर कॉल करें। |

## Evidence

- `docs/validation/2026-10-08-indictrans2-download-weights.json`: pinned size and remote SHA256 verification.
- `docs/validation/2026-10-08-indictrans2-comparison.json`: tokens, completion guards, timing and GPU memory.
- `docs/validation/2026-10-08-nllb-comparison-baseline.json`: existing provider outputs and workspace cleanup.
- `docs/INDICTRANS2_EVALUATION_2026-10-08.md`: preparation, packages, failures, limitations and provenance.

Next: human Hindi meaning/style review, then a controlled dubbed-video comparison if accepted.
