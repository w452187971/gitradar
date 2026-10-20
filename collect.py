#!/usr/bin/env python3
"""GitRadar V3 collector: preserve existing snapshots and optionally AI-summarize."""
import datetime as dt, json, os, pathlib, re, time, urllib.parse, urllib.request
P=pathlib.Path(__file__).parent/'data';P.mkdir(exist_ok=True)
TODAY=dt.datetime.now(dt.timezone.utc).date()
def read(name,default):
 try:return json.loads((P/name).read_text(encoding='utf-8'))
 except (OSError,ValueError):return default
def api(url,body=None,token=None):
 headers={'Accept':'application/vnd.github+json','User-Agent':'GitRadar-V3'}
 if token:headers['Authorization']='Bearer '+token
 if body is not None:headers['Content-Type']='application/json'
 req=urllib.request.Request(url,headers=headers,data=json.dumps(body).encode() if body is not None else None)
 with urllib.request.urlopen(req,timeout=35) as resp:return json.load(resp)
token=os.getenv('GH_API_TOKEN'); old=read('projects.json',{});history=read('history.json',{});summaries=read('summaries.json',{})
queries=[
 f'created:>={TODAY-dt.timedelta(days=7)} stars:20..2000',
 f'created:>={TODAY-dt.timedelta(days=30)} stars:50..5000',
 f'created:>={TODAY-dt.timedelta(days=90)} stars:100..10000',
 f'pushed:>={TODAY-dt.timedelta(days=7)} stars:100..3000',
 'topic:android-tv stars:>15','topic:adblock stars:>20','topic:download-manager stars:>20',
 'topic:open-source-apps stars:>20','topic:privacy stars:>50','topic:self-hosted stars:>50',
 'topic:ai-agent stars:>50','topic:productivity stars:>30',
 'android tv remove ads in:description stars:>10','ad blocker in:description stars:>30',
]
repos={};errors=[]
for q in queries:
 try:
  url='https://api.github.com/search/repositories?'+urllib.parse.urlencode({'q':q,'sort':'stars','order':'desc','per_page':100})
  for r in api(url,token=token).get('items',[]):
   if not r.get('fork') and not r.get('archived'):repos[r['full_name']]=r
 except Exception as e:errors.append(q+': '+str(e))
 time.sleep(2.1)
# Preserve previously tracked repositories, even if they disappear from discovery searches.
old_projects=old.get('projects',[])
for r in old_projects:
 name=r['full_name']
 if name in repos:continue
 try:
  rr=api('https://api.github.com/repos/'+urllib.parse.quote(name,safe='/'),token=token)
  if not rr.get('archived'):repos[name]=rr
 except Exception as e:errors.append('refresh '+name+': '+str(e))
 time.sleep(.12)
if not repos:raise RuntimeError('No repositories retrieved; keeping existing data.')
# Classification and scores are heuristics, not verified quality assessments.
RULES=[('影音去广告',r'ad.?block|adguard|android.?tv|smart.?tv|launcher|iptv|youtube|television'),('影音下载',r'download|video|media|music|player|stream|yt.dlp'),('AI 应用',r'agent|llm|chatbot|openai|rag|diffusion|mcp|ai.?tool'),('隐私安全',r'privacy|security|vpn|firewall|password|encrypt'),('效率工具',r'productivity|automation|workflow|note|office|clipboard'),('系统工具',r'desktop|windows|macos|linux|android|ios|browser|extension'),('自托管',r'self.host|homelab|docker|nas|server'),('游戏娱乐',r'game|gaming|emulator')]
def classify(r):
 txt=' '.join([r['full_name'],r.get('description') or '', ' '.join(r.get('topics') or [])]).lower()
 for name,pattern in RULES:
  if re.search(pattern,txt):return name
 return '其他开源'
def change(series,stars,days):
 pts=[(d,s) for d,s in series.items() if d<=str(TODAY-dt.timedelta(days=days))]
 return max(0,stars-max(pts)[1]) if pts else None
items=[]
for r in repos.values():
 name=r['full_name'];stars=r['stargazers_count'];series=history.get(name,{})
 series[str(TODAY)]=stars
 series={d:s for d,s in series.items() if d>=str(TODAY-dt.timedelta(days=45))}
 history[name]=series
 d1=change(series,stars,1);d7=change(series,stars,7)
 created=r.get('created_at','')
 age=max(1,(TODAY-dt.date.fromisoformat(created[:10])).days) if created else 9999
 category=classify(r)
 # If growth is unknown, use modest discovery score instead of claiming growth.
 score=(d7 or 0)*2+(d1 or 0)*3+min(stars,2500)/(age+12)*3+(90 if category!='其他开源' else 0)
 items.append({'full_name':name,'html_url':r['html_url'],'description':r.get('description') or '',
 'stargazers_count':stars,'delta_1d':d1,'delta_7d':d7,'language':r.get('language'),
 'topics':r.get('topics') or [],'created_at':created,'pushed_at':r.get('pushed_at'),
 'category_zh':category,'discovery_score':round(score,1)})
items.sort(key=lambda r:r['discovery_score'],reverse=True)
# AI summaries are optional. Only generated when user configures OPENAI_API_KEY secret.
# Limit to 12 summaries per run to constrain API costs; use description + README excerpt.
key=os.getenv('OPENAI_API_KEY');count=0
if key:
 for r in items[:30]:
  if count>=12:break
  name=r['full_name'];desc=r['description']
  cache=summaries.get(name,{})
  if cache.get('source_description')==desc:continue
  try:
   raw=urllib.request.urlopen(urllib.request.Request('https://raw.githubusercontent.com/'+name+'/HEAD/README.md',headers={'User-Agent':'GitRadar'}),timeout=12).read(12000).decode('utf-8','replace')
  except Exception:raw=''
  prompt='请根据以下仓库资料，用简体中文写一句不超过75字的项目用途介绍。仅基于提供的资料，不要猜测功能、热度、使用难度或安全性。输出纯文本。\n项目：'+name+'\n描述：'+desc+'\nREADME摘录：'+raw[:5500]
  try:
   response=api('https://api.openai.com/v1/chat/completions',{'model':os.getenv('OPENAI_MODEL','gpt-4.1-mini'),'messages':[{'role':'user','content':prompt}],'max_tokens':180},token=key)
   summary=response['choices'][0]['message']['content'].strip()
   if summary:summaries[name]={'source_description':desc,'zh':summary,'updated_at':str(TODAY)};count+=1
  except Exception as e:errors.append('AI '+name+': '+str(e));break
for r in items:r['summary_zh']=summaries.get(r['full_name'],{}).get('zh')
# Persist in stable structure compatible with existing V2 frontend.
(P/'history.json').write_text(json.dumps(history,ensure_ascii=False),encoding='utf-8')
(P/'summaries.json').write_text(json.dumps(summaries,ensure_ascii=False),encoding='utf-8')
(P/'projects.json').write_text(json.dumps({'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'count':len(items),'projects':items,'warnings':errors},ensure_ascii=False),encoding='utf-8')
print('Collected',len(items),'repos; AI summaries generated',count,'warnings',len(errors))
