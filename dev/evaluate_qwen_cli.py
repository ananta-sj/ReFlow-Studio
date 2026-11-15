"""Offline file/pipe evaluation of the approved model; no local server required."""
import argparse,json,os,re,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
from dev.evaluate_qwen_scene import INSTRUCTION,cases,validate_response
from dev.prepare_qwen_dialogue_trial import sha
from dev.completion_evidence import generation_counts,finished_before_cap


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--smoke',action='store_true');parser.add_argument('--case');parser.add_argument('--cpu',action='store_true');parser.add_argument('--native-template',action='store_true');args=parser.parse_args()
    from core.render_context import RenderContext,bind_job,run_process
    runtime=ROOT/'runtime_profiles/dialogue-qwen-evaluation'
    receipt=json.loads((runtime/'profile.json').read_text(encoding='utf-8'))
    for relative,checksum in receipt['files'].items():
        if sha(runtime/relative)!=checksum:raise ValueError('Trial artifact changed: '+relative)
    names=('settings.json','models.json','graph.json','ui_preferences.json','hardware_profile.json')
    before={name:sha(ROOT/name) for name in names}
    destination=ROOT/'docs/validation/qwen-scene-20261114';destination.mkdir(exist_ok=True)
    job=RenderContext(ROOT/'temp'); report=dict(transport='offline-completion',production_route_changed=False,human_quality_accepted=False,
        character_labels_supplied_for_text_trial=True,results=[])
    try:
        with bind_job(job):
            system=job.workspace/'system.txt';system.write_text(INSTRUCTION,encoding='utf-8')
            trials=[dict(name='cli-smoke',cues=[dict(id='a',source='Yes.',speaker_gender='female',available_seconds=2)],source_language='en')] if args.smoke else [c for c in cases() if c['name']==args.case] if args.case else cases()[:3]
            if not trials:raise ValueError('Unknown test case')
            for case in trials:
                prompt=job.workspace/(case['name']+'.txt')
                prompt.write_text('<|im_start|>system\n'+INSTRUCTION+'<|im_end|>\n<|im_start|>user\n'+json.dumps(case,ensure_ascii=False)+
                    '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n',encoding='utf-8')
                schema=job.workspace/'schema.json'
                schema.write_text(json.dumps(dict(type='object',properties={'cues':dict(type='array',items=dict(type='object',properties={
                    'id':dict(type='string',enum=[c['id'] for c in case['cues']]),'text':dict(type='string'),
                    'uncertain':dict(type='boolean'),'reason':dict(type='string')},required=['id','text','uncertain','reason'],additionalProperties=False))},required=['cues'],additionalProperties=False)),encoding='utf-8')
                maximum=256 if args.smoke else 3072
                command=[str(runtime/'bin/llama-completion.exe'),'-m',str(runtime/'model.gguf'),'--device','none' if args.cpu else 'Vulkan1','-ngl','0' if args.cpu else '99',
                    '-c','8192','-n',str(maximum),'-t','4','-f',str(prompt),'--no-conversation','--special',
                    '--no-display-prompt','--color','off','--json-schema-file',str(schema),'--temp','.2','--seed','17']
                if args.native_template:
                    command=[str(runtime/'bin/llama-completion.exe'),'-m',str(runtime/'model.gguf'),'--device','none' if args.cpu else 'Vulkan1','-ngl','0' if args.cpu else '99',
                        '-c','8192','-n',str(maximum),'-t','4','--prompt',json.dumps(case,ensure_ascii=False),'--system-prompt-file',str(system),
                        '--conversation','--single-turn','--jinja','--reasoning','off',
                        '--no-display-prompt','--color','off','--json-schema-file',str(schema),'--temp','.2','--seed','17']
                suffix=('-cpu' if args.cpu else '')+('-native' if args.native_template else '')
                started=time.monotonic();log_path=destination/(case['name']+suffix+'-completion.log')
                output_path=destination/(case['name']+suffix+'-completion-output.txt')
                with log_path.open('wb') as log, output_path.open('wb') as output:
                    result=run_process(command,stdout=output,stderr=log,stdin=subprocess.DEVNULL,
                        check=True,timeout=300,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                stdout=output_path.read_text(encoding='utf-8-sig')
                start=stdout.find('{')
                if start<0:raise ValueError('No generated JSON; inspect CLI output')
                payload,end=json.JSONDecoder().raw_decode(stdout[start:])
                # Keep actual CLI output and completion evidence; a valid JSON
                # fragment alone is not evidence that generation finished.
                log_text=log_path.read_text(encoding='utf-8',errors='replace')
                tail=stdout[start+end:].strip().lower()
                completion=tail.startswith(('[end of text]','[eot]','<|im_end|>'))
                token_counts=generation_counts(log_text)
                completion=finished_before_cap(log_text,maximum)
                rows=validate_response({'choices':[{'finish_reason':'stop' if completion else 'unverified','message':{'content':json.dumps(payload)}}]},[c['id'] for c in case['cues']])
                entry=dict(name=case['name'],seconds=time.monotonic()-started,input=case,output=rows,
                    completion_verified=completion,generated_token_counts=token_counts)
                report['results'].append(entry)
                print(json.dumps(dict(name=case['name'],seconds=entry['seconds'],output=rows),ensure_ascii=True),flush=True)
            report['completed']=True
    except Exception as error:
        report['error']=str(error);raise
    finally:
        job.cleanup();report['configuration_unchanged']=before=={name:sha(ROOT/name) for name in names}
        filename='completion-smoke-report.json' if args.smoke else (args.case+('-cpu' if args.cpu else '')+('-native' if args.native_template else '')+'-report.json') if args.case else 'report.json'
        (destination/filename).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
