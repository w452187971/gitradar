import json,os,urllib.request,urllib.parse,datetime,time
from pathlib import Path
p=Path(__file__).parent/'data'; p.mkdir(exist_ok=True)
today=datetime.datetime.now(datetime.timezone.utc).date(); day=str(today)
def read(name,default):
 try:return json.loads((p/name).read_text())
 except (ValueError,OSError):return default
history=read('history.json',{}); old=read('projects.json',{}).get('projects',[])
queries=[f'created:>={today-datetime.timedelta(days=30)} stars:>20',f'pushed:>={today-datetime.timedelta(days=7)} stars:>300','topic:android-tv stars:>20','topic:adblock stars:>30','topic:self-hosted stars:>100']
repos={}; errors=[]
def fetch(url):
 h={'Accept':'application/vnd.github+json','User-Agent':'GitRadar'}
 if os.getenv('GH_API_TOKEN'):h['Authorization']='Bearer '+os.environ['GH_API_TOKEN']
 with urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=30) as response:return json.load(response)
for q in queries:
 try:
  url='https://api.github.com/search/repositories?'+urllib.parse.urlencode({'q':q,'sort':'stars','order':'desc','per_page':100})
  for r in fetch(url)['items']:
   if not r['fork'] and not r['archived']:repos[r['full_name']]=r
 except Exception as e:errors.append(str(e))
 time.sleep(2)
if not repos:raise RuntimeError('All searches failed: '+repr(errors))
for r in old:
 if r['full_name'] not in repos:
  try:repos[r['full_name']]=fetch('https://api.github.com/repos/'+r['full_name']);time.sleep(.1)
  except Exception:pass
items=[]
for r in repos.values():
 name=r['full_name'];stars=r['stargazers_count'];series=history.get(name,{})
 series[day]=stars;series={k:v for k,v in series.items() if k>=str(today-datetime.timedelta(days=45))};history[name]=series
 def delta(days):
  points=[(k,v) for k,v in series.items() if k<=str(today-datetime.timedelta(days=days))]
  return max(0,stars-max(points)[1]) if points else None
 items.append({'full_name':name,'html_url':r['html_url'],'description':r.get('description') or '', 'stargazers_count':stars,'delta_1d':delta(1),'delta_7d':delta(7),'language':r.get('language'),'topics':r.get('topics',[]),'created_at':r['created_at'],'pushed_at':r['pushed_at']})
(p/'history.json').write_text(json.dumps(history,ensure_ascii=False))
(p/'projects.json').write_text(json.dumps({'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'projects':items,'warnings':errors},ensure_ascii=False))
print('Saved',len(items),'projects')
