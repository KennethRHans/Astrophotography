"""Public M77 service diagnostics; no user files, headers or credentials."""
import concurrent.futures,io,json,urllib.request,urllib.parse
from PIL import Image
params=dict(hips='CDS/P/DSS2/color',width=256,height=256,fov=.5,projection='TAN',coordsys='icrs',ra=40.6696,dec=-.0133,format='jpg')
cases=[('CDS primary','https://alasky.cds.unistra.fr/hips-image-services/hips2fits?'+urllib.parse.urlencode(params)),('CDS mirror','https://alaskybis.cds.unistra.fr/hips-image-services/hips2fits?'+urllib.parse.urlencode(params))]
for survey in ['DSS2 Red','DSS']:
    p=dict(Position='40.6696,-0.0133',Survey=survey,Return='JPEG',Pixels=256,Size=.5,Projection='Tan',Coordinates='J2000',Scaling='Log')
    cases.append(('NASA SkyView '+survey,'https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?'+urllib.parse.urlencode(p)))
def check(case):
    name,url=case
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'EasyAstroStudio-ReferencePrototype/0.2 public service check'})
        with urllib.request.urlopen(request,timeout=25) as r:
            data=r.read(6*1024*1024);content_type=r.headers.get('Content-Type','');status=r.status
        try:
            image=Image.open(io.BytesIO(data));image.load()
            result=dict(name=name,status=status,content_type=content_type,image=True,size=image.size)
        except Exception:
            result=dict(name=name,status=status,content_type=content_type,image=False,preview=data[:120].decode('utf-8',errors='replace'))
    except Exception as exc:result=dict(name=name,error=str(exc))
    print('PROBE_RESULT '+json.dumps(result),flush=True)
    return result
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(check,cases))
with open('service-check.json','w') as f:json.dump(results,f,indent=2)
