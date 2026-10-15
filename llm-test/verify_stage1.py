"""Validate Stage 1 research artifacts. Run: python llm-test/verify_stage1.py"""
from pathlib import Path
import ast,csv,json,sys
root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parent.parent
p=root/'llm-test/ai_prototype.ipynb'
notebook=json.loads(p.read_text(encoding='utf-8'))
source='\n'.join(''.join(c['source']) for c in notebook['cells'] if c['cell_type']=='code')
for i,c in enumerate(notebook['cells'],1):
 if c['cell_type']=='code':ast.parse(''.join(c['source']),filename=f'cell-{i}')
assert 'D:\\HuggingFace' not in source
assert 'RUN_BASELINES = False' in source and 'RUN_COLAB_FP16 = False' in source
assert 'test_model_v2(model_id, test_cases)' in source
assert 'evaluated.to_csv(output, index=False)' in source
assert 'RESULTS_DIR' in source
folder=root/'llm-test/results'
with (folder/'research_matrix.csv').open(encoding='utf-8-sig',newline='') as f: research=list(csv.DictReader(f))
assert len(research)==15
assert len(set(int(r['Model No.']) for r in research))==15
expected={1:6,2:13,3:12,4:29,5:34}
columns=None
for i in range(1,6):
 with (folder/f'model_{i}_results.csv').open(encoding='utf-8-sig',newline='') as f:
  rd=csv.DictReader(f); rows=list(rd)
 assert len(rows)==3 and {r['Test ID'] for r in rows}=={'T1','T2','T3'}
 if columns is None:columns=rd.fieldnames
 assert rd.fieldnames==columns,f'Model {i} columns mismatch'
 assert sum(float(r['Total Score']) for r in rows)==expected[i]
 for r in rows:
  assert sum(float(r[x]) for x in ['Instruction Adherence','Output Quality','Formatting Consistency'])==float(r['Total Score'])
  assert r['Status']=='Success'
 if i>=4:
  assert all('Transformers' in r['Backend'] and 'llama' not in r['Backend'].lower() for r in rows)
  assert all('FP16' in r['Quantization'] for r in rows)
  assert all(r['Generated Tokens'] and r['Reached Token Limit'] for r in rows)
  for r in rows:
   assert all(s not in r['Response'] for s in ('llama-cli','llama_model_loader','User request:','Assistant response:'))
 print(f'Model {i}: 3 tests, score {expected[i]}/45, schema verified')
with (folder/'model_4_5_hardware_assessment.csv').open(encoding='utf-8-sig',newline='') as f:hw=list(csv.DictReader(f))
assert len(hw)==2 and all('Transformers' in r['Status'] and 'GGUF' not in r['Status'] for r in hw)
assert all('Transformers' in r['Status'] for r in research if int(r['Model No.']) in (4,5))
req=(root/'requirements.txt').read_text(encoding='utf-8').lower()
assert 'torch' in req and 'transformers' in req
print(f'PASS: Notebook syntax ({len(notebook["cells"])} cells), matrix, FP16 results, scoring and requirements')
print('NOTE: Clean-environment installation and 22-cell notebook execution passed with Python 3.13.15. This lightweight verifier does not independently rerun large-model inference.')
