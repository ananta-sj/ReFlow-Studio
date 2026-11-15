"""Translation-specialist acceptance checks using the publisher's prompt format."""
import argparse,json,os,re,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
from dev.prepare_qwen_dialogue_trial import sha
from dev.completion_evidence import generation_counts,finished_before_cap


def cases():
    data=json.loads((ROOT/'docs/diagnostics/overnight-20261114-metadata/identity-evaluation/inputs.json').read_text(encoding='utf-8'))['cues']
    result=[]
    for name,indices,speaker in [('departure',[25],'mother'),('leaving-father',[27,28],'mother'),
            ('father-last-words',[29,30],'daughter'),('as-soon-as-possible',[31],'daughter'),
            ('yes-he-did',[32],'mother'),('grandfather-location',[33,34,35,36],'daughter'),('first-europe-trip',[37,38],'mother')]:
        result.append(dict(name=name,source=' '.join(data[i]['text'] for i in indices),source_language='ja',
            source_indices=indices,speaker=speaker,available_seconds=data[indices[-1]]['end']-data[indices[0]]['start']))
    result.extend([
        dict(name='held-negation',source='父はまだ死んでいない。',source_language='ja'),
        dict(name='held-refusal',source='私は行かないと言ったの。',source_language='ja'),
        dict(name='held-quantity',source='2人で3時に駅に来てください。',source_language='ja'),
        dict(name='held-relationship',source='おじいさんじゃなくて、お父さんに聞いて。',source_language='ja'),
        dict(name='english-father-control',source='But Father told us before he died, remember?',source_language='en',speaker='daughter'),
        dict(name='english-mother-control',source='I cannot bring myself to leave this village.',source_language='en',speaker='mother')])
    return result


def prompt_for(case,contextual):
    if case.get('rewrite_draft'):
        return ("Rewrite the Hindi film dialogue below as concise, natural spoken Hindi. Return ONLY the revised Hindi dialogue. "
            f"Use at most {case['dialogue_budget_words']} whitespace-separated words for {case['available_seconds']:.2f} seconds of speech. "
            'Keep every fact and relationship from the English meaning; do not add facts. '
            'The speaker is a female '+case['speaker']+'. Both mother and daughter are female; the mother addresses her daughter with तुम. '
            'Use correct first-person agreement and natural conversational grammar.\n'
            'English meaning: '+case['source']+'\nHindi draft: '+case['rewrite_draft'])
    if not contextual or not case.get('speaker'):
        return 'Translate the following segment into Hindi, without additional explanation.\n\n'+case['source']
    context=('Context only: a mother and her daughter are speaking. Both speakers are female. '
        'The father has died. They are discussing leaving the village and visiting the paternal grandfather in France. '
        'The current speaker is the '+case['speaker']+'.')
    if case.get('preceding_dialogue'):
        context+='\nPrevious dialogue (context only):\n'+case['preceding_dialogue']
    if case.get('fact_constraints'):
        context+='\nTerminology constraints for the segment:\n'+case['fact_constraints']
    if case.get('dialogue_budget_words'):
        context+=('\nThis translation will be spoken as a film dub. Use concise, natural conversational Hindi, '
            'not literary wording. Preserve every fact, relationship, negation and emotion. '
            'Use feminine first-person agreement for these female speakers. '
            'The mother addresses her daughter with तुम, not आप. '
            f"The speech window is {case['available_seconds']:.2f} seconds; aim for no more than {case['dialogue_budget_words']} whitespace-separated words. "
            'Translate only the segment, with no explanation.')
    # Publisher's contextual-translation template. It explicitly excludes
    # translating the context itself. Ground-truth roles are fixture data.
    return context+'\n参考上面的信息，把下面的文本翻译成Hindi，注意不需要翻译上文，也不要额外解释：\n'+case['source']


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--contextual',action='store_true')
    parser.add_argument('--case')
    parser.add_argument('--cpu',action='store_true')
    parser.add_argument('--english-captions',action='store_true')
    parser.add_argument('--fact-constraints',action='store_true')
    parser.add_argument('--larger-model',action='store_true')
    parser.add_argument('--spoken-dialogue',action='store_true')
    parser.add_argument('--rewrite-draft',action='store_true')
    parser.add_argument('--temperature',type=float,default=.7)
    args=parser.parse_args()
    if not 0<=args.temperature<=1:raise ValueError('Trial temperature must be between zero and one')
    from core.render_context import RenderContext,bind_job,run_process
    from core.dialogue_integrity import repetition
    runtime=ROOT/'runtime_profiles'/('dialogue-hymt7b-evaluation' if args.larger_model else 'dialogue-hymt-evaluation');profile=json.loads((runtime/'profile.json').read_text(encoding='utf-8'))
    if sha(runtime/'model.gguf')!=profile['model']['sha256']:raise ValueError('Specialist model changed')
    runner=Path(profile['runner_profile'])
    for key,value in profile['runner_files'].items():
        if sha(runner/key)!=value:raise ValueError('Verified runner changed')
    names=('settings.json','models.json','graph.json','ui_preferences.json','hardware_profile.json')
    before={name:sha(ROOT/name) for name in names}
    destination=ROOT/'docs/validation'/('hymt7b-trial-20261115' if args.larger_model else 'hymt-trial-20261114');destination.mkdir(exist_ok=True)
    report=dict(production_route_changed=False,human_quality_accepted=False,
        contextual=args.contextual,model_sha256=profile['model']['sha256'],character_groupings_are_test_ground_truth=True,results=[])
    trials=cases()
    if args.english_captions:
        from core.translation_caption_alignment import align
        source=json.loads((ROOT/'docs/diagnostics/overnight-20261114-metadata/identity-evaluation/inputs.json').read_text(encoding='utf-8'))['cues']
        english=json.loads((ROOT/'docs/validation/2026-11-14-scene-english-captions.json').read_text(encoding='utf-8'))
        trials=[case for case in trials if case.get('source_indices')]
        windows=[dict(start=source[c['source_indices'][0]]['start'],end=source[c['source_indices'][-1]]['end'],text=c['source']) for c in trials]
        aligned,issues=align(windows,english)
        if issues:raise ValueError('Unaligned caption evidence: '+str(issues))
        for index,case in enumerate(trials):
            case['original_japanese']=case['source'];case['source']=aligned[index]['text'];case['source_language']='en';case['caption_evidence']=aligned[index]
    if args.contextual:
        preceding=[]
        for case in trials:
            case['preceding_dialogue']='\n'.join(preceding[-4:]) if case.get('source_indices') else ''
            if case.get('source_indices'):
                preceding.append(case.get('speaker','speaker')+': '+case['source'])
    if args.fact_constraints:
        if not args.contextual or not args.english_captions:raise ValueError('Fact constraints require contextual English evidence')
        for case in trials:
            terms=[]
            source=case['source'].casefold()
            for word,target in [('north','उत्तर'),('south','दक्षिण'),('east','पूर्व'),('west','पश्चिम')]:
                if re.search(r'\b'+word+r'\s+of\b',source):terms.append(word+' = '+target+' (preserve this direction)')
            if re.search(r'\b(?:we|us)\b[^.!?]*\bhis father\b',source):
                terms.append('his father = उनके पिता (the father of him, not the father of we/us)')
            case['fact_constraints']='\n'.join(terms)
    if args.smoke:trials=[next(c for c in trials if c['name']=='english-father-control')]
    if args.case:trials=[c for c in trials if c['name']==args.case]
    if not trials:raise ValueError('Unknown test case')
    if args.spoken_dialogue:
        if not args.contextual:raise ValueError('Spoken-dialogue trial requires scene context')
        for case in trials:
            if case.get('available_seconds'):case['dialogue_budget_words']=max(3,round(case['available_seconds']*3))
    if args.rewrite_draft:
        if not args.larger_model or not args.english_captions or not args.spoken_dialogue:raise ValueError('Draft rewrite requires larger English scene trial with speech budget')
        baseline=json.loads((destination/'full-contextual-english-captions-history-facts-report.json').read_text(encoding='utf-8'))
        for case in trials:case['rewrite_draft']=next(row['translation'] for row in baseline['results'] if row['name']==case['name'])
    suffix=('-contextual' if args.contextual else '')+('-english-captions' if args.english_captions else '')+('-history' if args.contextual else '')+('-facts' if args.fact_constraints else '')+('-spoken' if args.spoken_dialogue else '')+('-rewrite' if args.rewrite_draft else '')+('-temp'+str(args.temperature).replace('.','') if args.temperature!=.7 else '')+('-cpu' if args.cpu else '')
    job=RenderContext(ROOT/'temp')
    try:
        with bind_job(job):
            for case in trials:
                text=prompt_for(case,args.contextual);path=job.workspace/'prompt.txt'
                path.write_text('<｜hy_begin▁of▁sentence｜><｜hy_User｜>'+text+'<｜hy_Assistant｜>',encoding='utf-8')
                output_path=destination/(case['name']+suffix+'.txt');log_path=destination/(case['name']+suffix+'.log')
                maximum=768;started=time.monotonic()
                command=[str(runner/'bin/llama-completion.exe'),'-m',str(runtime/'model.gguf'),
                    '--device','none' if args.cpu else 'Vulkan1','-ngl','0' if args.cpu else '99','-c','4096','-n',str(maximum),'-t','4',
                    '--prompt',text,'--conversation','--single-turn','--jinja','--no-display-prompt','--color','off',
                    '--temp',str(args.temperature),'--top-k','20','--top-p','.6','--repeat-penalty','1.05','--seed','17']
                with output_path.open('wb') as output,log_path.open('wb') as log:
                    run_process(command,stdout=output,stderr=log,stdin=subprocess.DEVNULL,check=True,timeout=180,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                raw=output_path.read_text(encoding='utf-8-sig')
                log=log_path.read_text(encoding='utf-8',errors='replace')
                token_counts=generation_counts(log)
                if not finished_before_cap(log,maximum):raise ValueError('No verified natural completion')
                text=re.split(r'<｜hy_[^>]+｜>|\[end of text\]',raw,maxsplit=1)[0].strip()
                if not text or len(text)>4000 or repetition(text) or not any('\u0900'<=c<='\u097f' for c in text):raise ValueError('Invalid Hindi translation')
                row=dict(**case,translation=text,seconds=time.monotonic()-started,generated_tokens=token_counts[-1])
                from core.dialogue_integrity import require_explicit_facts,DialogueIntegrityReviewRequired
                row['fact_alarms']=[]
                try:require_explicit_facts(case['source'],text,case['source_language'],'hi')
                except DialogueIntegrityReviewRequired as error:row['fact_alarms'].append(str(error))
                report['results'].append(row);print(json.dumps(row,ensure_ascii=True),flush=True)
            report['completed']=True
    except Exception as error:
        report['error']=str(error);raise
    finally:
        job.cleanup();report['configuration_unchanged']=before=={name:sha(ROOT/name) for name in names}
        name=('smoke' if args.smoke else args.case or 'full')+suffix+'-report.json'
        (destination/name).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
