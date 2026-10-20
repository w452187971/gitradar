import sys,json,pathlib,copy,datetime,tempfile,hashlib
root=pathlib.Path(sys.argv[1]);sys.path[:0]=[str(root),str(root/'tests')]
from test_v4_content import sampleContent,NOW
from gitradar.content import resolveContent
from gitradar.github_client import GitHubClient,HttpResponse
from gitradar.models import Budget
from gitradar.observations import applyObservations
from gitradar.recommendations import selectRecommendations
from gitradar.evidence import mergeEvidence,refreshPaths
from gitradar.site import _disabled
from gitradar.validation import _historyErrors
facts,editor=sampleContent();content=resolveContent(facts,editor,NOW)
p={'full_name':'demo/search','node_id':'N1','created_at':'2020-01-01T00:00:00Z','stargazers_count':10,'content':content,'archived':False,'fork':False}
previous={'projects':[p],'history':{'demo/search':{'2026-10-19':10}}}
client=GitHubClient(transport=lambda *args:HttpResponse(404,{},{}),now=lambda:NOW)
batch=client.fetchRestObservations([{'full_name':p['full_name'],'node_id':'N1'}],Budget());out=applyObservations(previous,batch,'2026-10-20');blocked=out['projects'][0]
checks={}
checks['rest404_recommendation_revoked']=selectRecommendations(out['projects'],{},NOW)['selected_count']==0
checks['rest404_static_path_disabled']=_disabled(blocked)
success={'full_name':'demo/search','node_id':'N1','status':'success','created_at':p['created_at'],'observed_at':NOW,'stargazers_count':11,'archived':False,'fork':False}
recovered=applyObservations(out,[success],'2026-10-20');checks['recovery_clears_404']=selectRecommendations(recovered['projects'],{},NOW)['selected_count']==1
checks['historical_day_unchanged']=recovered['history']['demo/search']['2026-10-19']==10
old={'full_name':'demo/search','refs':[{'id':'intro','source_kind':'readme','url':'https://github.com/demo/search/blob/main/README.md','text':'Official purpose.','content_hash':'fragment','source_hash':'old-full','checked_at':NOW}]}
new={'refs':[{'id':'readme:new','source_kind':'readme','url':old['refs'][0]['url'],'text':'Official purpose.\nRequires a paid account.','content_hash':'new-full','checked_at':NOW}]}
merged=mergeEvidence(old,new);checks['new_requirement_requires_review']=bool(merged['refs'][0].get('context_changed'))
new['refs'][0]['url']='https://github.com/demo/search/blob/main/COPYING';other=mergeEvidence(old,new);checks['separate_documents_not_mixed']=other['refs'][0]['source_hash']=='old-full'
pr={'full_name':'demo/search','content':{'usage_paths':[{'url':'https://github.com/demo/search/releases'},{'url':'https://github.com/demo/search/wiki/Install'}],'claims':{'usage_paths':['intro']}}}
statuses=[200,404];client=GitHubClient(transport=lambda *args:HttpResponse(statuses.pop(0),{},None),now=lambda:NOW)
paths=refreshPaths([pr],{'projects':{'demo/search':old}},client,Budget(),NOW)['projects']['demo/search']['refs'][0]
checks['all_paths_checked']=client.usage.path_requests==2 and paths.get('path_status')==404
client=GitHubClient(now=lambda:NOW);partial=client.parseBatch([{'full_name':'demo/search','node_id':'N1'}],{'data':{'r0':{'id':'N1','nameWithOwner':'demo/search','createdAt':p['created_at'],'stargazerCount':12,'isArchived':None,'isFork':False}},'errors':[{'path':['r0','isArchived']}]})
checks['critical_partial_node_not_success']=partial[0]['status']!='success'
checks['rollback_cannot_overwrite_new_history']=bool(_historyErrors({'history':{'demo/search':{'2026-10-19':10,'2026-10-20':11}}},{'projects':[],'history':{'demo/search':{'2026-10-19':10}}},'2026-10-20'))
checks['prior_input_not_mutated']=previous['history']=={'demo/search':{'2026-10-19':10}}
print(json.dumps({'checks':checks,'all_passed':all(checks.values())},ensure_ascii=False,indent=2))
