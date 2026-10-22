"""Reusable A7 helpers for all 15 models; no inference on import."""
import math, time, gc
from pathlib import Path
import pandas as pd

SYSTEM=("You are CozyDay, a helpful daily planning assistant. "
        "Use only the information given by the user. "
        "Follow the requested format. Be accurate and concise.")
TRAFFIC={"Prototype":1000,"Early Startup":10000,"Growing Product":100000,
         "Large Platform":1000000,"Mass Consumer App":10000000,"Global Platform":100000000}

def registry(matrix):
    models={int(r['Model No.']):(r['Model Name'],r['Category']) for _,r in matrix.iterrows()}
    assert set(models)==set(range(1,16)), 'Expected models 1–15'
    return models

def load_model(model_id, *, backend='cpu', precision='float32', local_only=False):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    tokenizer=AutoTokenizer.from_pretrained(model_id, local_files_only=local_only, trust_remote_code=False)
    kwargs={'local_files_only':local_only,'trust_remote_code':False}
    if backend=='cuda':
        if not torch.cuda.is_available(): raise RuntimeError('CUDA GPU unavailable')
        kwargs.update(device_map={'':0}, attn_implementation='eager', dtype=torch.float16)
        if precision=='nf4':
            from transformers import BitsAndBytesConfig
            kwargs['quantization_config']=BitsAndBytesConfig(
                load_in_4bit=True,bnb_4bit_quant_type='nf4',
                bnb_4bit_compute_dtype=torch.float16,bnb_4bit_use_double_quant=True)
        elif precision!='fp16': raise ValueError('GPU precision should be fp16 or nf4')
    elif backend=='cpu':
        if precision not in ('float32','bfloat16'): raise ValueError('Invalid CPU precision')
        kwargs['dtype']=torch.float32 if precision=='float32' else torch.bfloat16
    else: raise ValueError('backend must be cpu or cuda')
    model=AutoModelForCausalLM.from_pretrained(model_id,**kwargs)
    model.eval()
    return tokenizer,model

def run_models(numbers, model_matrix, prompts_df, result_dir, *, execute=False,
               backend='cpu',precision='float32',local_only=False):
    """Opt-in benchmark; validates existing records and saves each prompt. Scored files untouched."""
    models=registry(model_matrix)
    if not execute:
        print('Dry run: no model inference. Set execute=True explicitly.')
        return {}
    import torch
    result_dir=Path(result_dir);result_dir.mkdir(parents=True,exist_ok=True)
    reference=prompts_df.set_index('Prompt ID')
    assert len(reference)==25 and reference.index.is_unique
    output={}
    for number in numbers:
        model_id,category=models[number]
        path=result_dir/f'a7_model_{number}_benchmark.csv'
        previous=pd.read_csv(path) if path.exists() else pd.DataFrame()
        if not previous.empty:
            needed={'Prompt ID','Prompt','Prompt Type','Model','Max New Tokens','Response','Latency','Tokens/sec','Precision'}
            if not needed.issubset(previous.columns) or previous['Prompt ID'].duplicated().any():
                raise ValueError(f'Invalid resume file: {path}')
            for _,r in previous.iterrows():
                if r['Prompt ID'] not in reference.index:raise ValueError('Unexpected prompt ID')
                expected=reference.loc[r['Prompt ID']]
                if (r['Prompt']!=expected['Prompt'] or r['Prompt Type']!=expected['Prompt Type']
                    or r['Model']!=model_id or int(r['Max New Tokens'])!=256
                    or str(r['Precision'])!=precision):
                    raise ValueError('Resume configuration mismatch; refusing to mix runs')
        rows=previous.to_dict('records'); completed=set(previous['Prompt ID']) if not previous.empty else set()
        if len(completed)==25:
            output[number]=previous;continue
        tokenizer,model=load_model(model_id,backend=backend,precision=precision,local_only=local_only)
        device=next(model.parameters()).device
        try:
            for _,item in prompts_df.iterrows():
                if item['Prompt ID'] in completed:continue
                opt={'enable_thinking':False} if 'Qwen3' in model_id else {}
                inputs=tokenizer.apply_chat_template(
                    [{'role':'system','content':SYSTEM},{'role':'user','content':item['Prompt']}],
                    tokenize=True,add_generation_prompt=True,return_tensors='pt',return_dict=True,**opt)
                inputs={k:v.to(device) for k,v in inputs.items()}
                if device.type=='cuda':torch.cuda.synchronize()
                start=time.perf_counter()
                with torch.inference_mode():
                    generated=model.generate(**inputs,max_new_tokens=256,do_sample=False,
                                             pad_token_id=tokenizer.eos_token_id)
                if device.type=='cuda':torch.cuda.synchronize()
                elapsed=time.perf_counter()-start
                new=generated[0][inputs['input_ids'].shape[-1]:];n=len(new)
                rows.append({'Model':model_id,'Model Category':category,'Tokens/sec':round(n/elapsed,3),
                    'Latency':round(elapsed,3),'Prompt Type':item['Prompt Type'],'Prompt':item['Prompt'],
                    'Self-Evaluation Score (1-10)':None,'Prompt ID':item['Prompt ID'],
                    'Response':tokenizer.decode(new,skip_special_tokens=True),'Generated Tokens':n,
                    'Reached Token Limit':n>=256,'Backend':'Transformers','Device':str(device),
                    'Precision':precision,'Max New Tokens':256,'Instruction Adherence':None,
                    'Accuracy':None,'Clarity':None,'Structure':None})
                tmp=path.with_suffix('.tmp');pd.DataFrame(rows).to_csv(tmp,index=False);tmp.replace(path)
            output[number]=pd.DataFrame(rows)
        finally:
            del model,tokenizer;gc.collect()
            if torch.cuda.is_available():torch.cuda.empty_cache()
    return output

def calculate_costs(numbers,model_matrix,throughput,api_price_per_million,*,tokens_per_request=500,
                    requests_per_user=1,utilization=.7,machine_hourly=1.006,days=30,
                    gateway_hourly=.05,gateway_rps=100):
    """Return six local and six API scenario rows per model, in USD/month."""
    models=registry(model_matrix);local=[];api=[]
    for number in numbers:
        mid,_=models[number]; tps=throughput[number];price=api_price_per_million[number]
        if min(tps,price,tokens_per_request,requests_per_user)<=0:raise ValueError('Nonpositive assumption')
        for group,dau in TRAFFIC.items():
            requests=dau*requests_per_user;tokens=requests*tokens_per_request
            machines=max(1,math.ceil(tokens/(tps*86400*utilization)))
            gateways=max(1,math.ceil(requests/(86400*gateway_rps)))
            local_month=round(machines*machine_hourly*24*days,2)
            api_month=round(tokens/1e6*price*days,2)
            gateway_month=round(gateways*gateway_hourly*24*days,2)
            local.append({'Model Name':mid,'Daily Traffic Category':group,'Daily Active Users':dau,
                'Avg Tokens per User':tokens_per_request,'Total Daily Token Load':tokens,
                'Per Machine Cost (Cloud)':machine_hourly,'Machines Needed':machines,
                'Total Machine Cost':local_month,'Cloud Throughput Assumption (tokens/sec)':tps,
                'Cost Period':'USD/month'})
            api.append({'Local LLM Model Size':mid,
                'Comparable Paid Model Hosted on Hugging Face':mid+' (hypothetical hosted equivalent)',
                'Cost of Paid API per Token':price/1e6,'Daily Traffic Category':group,
                'Total Token Load':tokens,'Estimated API Cost':api_month,
                'Machines Required (API infrastructure)':gateways,
                'Total Cost':round(api_month+gateway_month,2),'API Gateway Cost':gateway_month,
                'Pricing Status':'Illustrative assumption, not quoted','Cost Period':'USD/month'})
    return pd.DataFrame(local),pd.DataFrame(api)
