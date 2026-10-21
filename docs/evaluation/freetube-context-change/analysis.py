import json,pathlib,hashlib,difflib,sys
root=pathlib.Path('/Users/mac/.codex/worktrees/gitradar-v4/gitradar');sys.path.insert(0,str(root))
from gitradar.sources import visibleSourceText
from gitradar.evidence import mergeEvidence
from gitradar.content import deriveFacts,resolveContent,eligibleForRecommendation
archive=pathlib.Path('/tmp/gitradar-license-live-renewal-xpq6zrtb');out=pathlib.Path('/tmp/gitradar-freetube-context-analysis');out.mkdir(exist_ok=True)
sha=lambda value:hashlib.sha256(value).hexdigest()
a=json.load(open(archive/'before.json'))['FreeTubeApp/FreeTube'];b=json.load(open(archive/'after.json'))['FreeTubeApp/FreeTube']
url='https://github.com/FreeTubeApp/FreeTube/releases'
def whole(bundle):return next(r for r in bundle['refs'] if r['url']==url and r['id'].startswith('official_site:source:'))
def path(bundle):return next(r for r in bundle['refs'] if r['id']=='path')
afull,bfull=whole(a),whole(b)
assert sha(afull['text'].encode())==afull['content_hash']==path(a)['source_hash']
assert sha(bfull['text'].encode())==bfull['content_hash']==path(b)['source_hash']
raw=(archive/'responses/03.body').read_bytes();assert visibleSourceText(raw,'')==bfull['text']
old,new=afull['text'].splitlines(),bfull['text'].splitlines();assert len(old)==len(new)
changed=[{'line':i+1,'before':x,'after':y} for i,(x,y) in enumerate(zip(old,new)) if x!=y]
assert changed==[{'line':100,'before':'Pull requests11\xa0(11)','after':'Pull requests12\xa0(12)'}]
assert path(a)['text']==path(b)['text'] and path(a)['text'] in bfull['text']
# Exact real-source input reproduces the existing conservative guard without a network request.
fetched={'full_name':a['full_name'],'node_id':a['node_id'],'refs':[bfull],'critical_unknowns':[],'status':'success'}
replayed=mergeEvidence(a,fetched);assert path(replayed)['context_changed'] is True
curation=json.load(open(root/'data/curation.json'))['projects']['FreeTubeApp/FreeTube'];asOf='2026-10-21T01:23:06.724896Z'
oldEligibility=eligibleForRecommendation(resolveContent(deriveFacts(a),curation,asOf),asOf=asOf)
newEligibility=eligibleForRecommendation(resolveContent(deriveFacts(replayed),curation,asOf),asOf=asOf)
assert oldEligibility['eligible'] and not newEligibility['eligible'] and 'context_changed:path' in newEligibility['reasons']
diff=''.join(difflib.unified_diff(afull['text'].splitlines(True),bfull['text'].splitlines(True),fromfile='old-normalized-text',tofile='new-normalized-text'))
(out/'diff.txt').write_text(diff)
result={'before_file_sha256':sha((archive/'before.json').read_bytes()),'after_file_sha256':sha((archive/'after.json').read_bytes()),'new_http_body_sha256':sha(raw),'old_source_hash':afull['content_hash'],'new_source_hash':bfull['content_hash'],'old_checked_at':afull['checked_at'],'new_checked_at':bfull['checked_at'],'chars':[len(afull['text']),len(bfull['text'])],'lines':[len(old),len(new)],'changed_lines':changed,'before_eligibility':oldEligibility,'replayed_eligibility':newEligibility,'curation_claims':{k:v for k,v in curation['claims'].items() if 'path' in v},'curation_prerequisites':curation['prerequisites'],'limits':['Old source is complete normalized text, not an old raw HTML response.','URL/HTML attributes absent from normalized text cannot be compared.','No sticky flags changed; no production writes or network.']}
(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2));print('result_sha256',sha((out/'result.json').read_bytes()))
