import pathlib,json,hashlib,base64,subprocess,sys,datetime
R=pathlib.Path(__file__).parent; root=pathlib.Path(sys.argv[1]); commit=sys.argv[2]
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==commit
assert not subprocess.check_output(['git','diff','--name-only','HEAD','--','gitradar','web','collect.py','.github/workflows/update.yml'],cwd=root,text=True).strip()
manifest=json.loads((R/'manifest.json').read_text())
for name,digest in manifest['files'].items():assert hashlib.sha256((R/name).read_bytes()).hexdigest()==digest
sys.path.insert(0,str(root))
from gitradar.github_client import GitHubClient
from gitradar.content import deriveFacts,resolveContent
now=datetime.datetime.now(datetime.timezone.utc).isoformat();client=GitHubClient(now=lambda:now)
xs=json.loads((R/'inputs.json').read_text());labels=json.loads((R/'labels.json').read_text());results=[]
for x,label in zip(xs,labels):
 name=x['full_name'];meta=x['authenticated_metadata'];body=meta.get('body') or {};canonical=body.get('full_name') or name
 repo={'full_name':canonical,'node_id':body.get('node_id')};refs=[]
 if meta.get('status')==200:refs.extend(client.evidenceRefs(body,'repository',repo))
 readmes=[d for d in x['documents'] if d.get('status')==200 and 'readme' in d['url'].lower()]
 if readmes:
  doc=readmes[0]; filename=doc['url'].rsplit('/',1)[-1]
  payload={'encoding':'base64','content':base64.b64encode(doc['body'].encode()).decode(),'html_url':'https://github.com/'+canonical+'/blob/'+body.get('default_branch','HEAD')+'/'+filename,'sha':doc['sha256']}
  refs.extend(client.evidenceRefs(payload,'readme',repo))
 bundle={**repo,'refs':refs,'official_urls':[]}; facts=deriveFacts(bundle);out=resolveContent(facts,asOf=now)
 results.append({'sample_name':name,'canonical_name':canonical,'source_available':label['source_available'],'expected_scene':label['actual_scene'],'purpose_source_informative':bool(label['purpose']['value']),'purpose':out.get('purpose'),'platforms':out.get('platforms'),'usage_paths':out.get('usage_paths'),'prerequisites':out.get('prerequisites'),'form':out.get('form'),'effective_status':out.get('effective_status'),'eligibility':out.get('eligibility'),'claims':out.get('claims'),'output':out})
summary={'implementation_commit':commit,'first_scored_at':now,'input_sha256':manifest['files']['inputs.json'],'labels_sha256':manifest['files']['labels.json'],'sample_count':40,'source_available_count':sum(r['source_available'] for r in results),'purpose_assertion_count':sum(bool(r['purpose']) for r in results),'platform_assertion_count':sum(bool(r['platforms']) for r in results),'entry_assertion_count':sum(bool(r['usage_paths']) for r in results),'eligible_count':sum(r['eligibility']['eligible'] for r in results),'all_domain_unknown_count':sum(not r['purpose'] for r in results),'scope_informative_count':sum(r['expected_scene']!='范围外' and r['purpose_source_informative'] for r in results),'scope_informative_unknown_count':sum(r['expected_scene']!='范围外' and r['purpose_source_informative'] and not r['purpose'] for r in results),'outside_count':sum(r['expected_scene']=='范围外' for r in results),'outside_unknown_count':sum(r['expected_scene']=='范围外' and not r['purpose'] for r in results),'notes':['Only repository metadata and the default README are passed through production evidence parsing; no hand-crafted normalized description and no seed curation.','Releases are unavailable in this offline snapshot and are not fabricated. Official supplementary docs retained for labels, not injected as structured facts.','Accuracy is unverified when output assertion count is below 30. No assertions is not 100 percent accuracy.']}
(R/'first-results.json').write_text(json.dumps({'summary':summary,'results':results},ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
