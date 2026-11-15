"""Public mirror probes only; no user image or metadata."""
import concurrent.futures,urllib.request,json,io
from PIL import Image
bases=[('ESA','https://skies.esac.esa.int/DSSColor'),('MAST','https://stpubdata.s3.us-east-1.amazonaws.com/mast/skybackgrounds/DSSColor'),('CSIRO','https://casda.csiro.au/hips/DSS2/color'),('China-VO','https://hips.china-vo.org/m/CDS_P_DSS2_color')]
def check(item):
 name,base=item;result=dict(name=name)
 for suffix in ['/properties','/Norder3/Dir0/Npix0.jpg']:
  try:
   req=urllib.request.Request(base+suffix,headers={'User-Agent':'EasyAstroStudio-ReferenceTest/0.3','Origin':'null'})
   with urllib.request.urlopen(req,timeout=15) as r:data=r.read(2*1024*1024);status=r.status;cors=r.headers.get('Access-Control-Allow-Origin');final=r.url
   entry=dict(status=status,cors=cors,final=final)
   if suffix=='/properties':
    props=dict(line.split('=',1) for line in data.decode().splitlines() if '=' in line and not line.startswith('#'))
    entry['properties']={k.strip():v.strip() for k,v in props.items() if k.strip() in ['hips_order','hips_tile_width','hips_frame','hips_tile_format','obs_title','hips_copyright']}
   else:
    image=Image.open(io.BytesIO(data));image.load();entry['image']=image.size
   result[suffix]=entry
  except Exception as exc:result[suffix]=dict(error=str(exc))
 print('MIRROR_RESULT '+json.dumps(result),flush=True);return result
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(check,bases))
with open('mirror-check.json','w') as f:json.dump(results,f,indent=2)
