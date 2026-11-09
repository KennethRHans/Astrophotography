"""Rebuild the CC BY-SA derivative catalog from downloaded upstream CSV files.

Usage: python scripts/build_object_catalog.py NGC.csv hygdata_v41.csv
Run from the repository root. The bundled license and attribution are preserved.
"""
import sys
import csv,json,hashlib
from pathlib import Path
rows=[]
def ra(s):
    h,m,v=map(float,s.split(':'));return (h+m/60+v/3600)*15
def dec(s):
    d,m,v=map(float,s.lstrip('+-').split(':'));return (-1 if s.startswith('-') else 1)*(d+m/60+v/3600)
for r in csv.DictReader(Path(sys.argv[1]).open(),delimiter=';'):
    typ=r['Type'];category='Galaxies' if typ in ('G','GPair','GTrpl','GGroup') else 'Clusters' if typ in ('OCl','GCl','Cl+N','Cl*','*Ass') else 'Nebulae' if typ in ('Neb','EmN','RfN','HII','PN','SNR','DrkN') else None
    if not category or not r['RA'] or not r['Dec']:continue
    ident=r['Name'];display=('M '+str(int(r['M']))+' / ' if r['M'] else '')+ident
    common=r['Common names'].split(',')[0].strip()
    if common:display+=' ('+common+')'
    mag=r['V-Mag'] or r['B-Mag']
    rows.append(dict(id='OpenNGC:'+ident,name=display[:200],category=category,ra=round(ra(r['RA']),8),dec=round(dec(r['Dec']),8),mag=float(mag) if mag else None,priority=0 if r['M'] else 1))
for r in csv.DictReader(Path(sys.argv[2]).open()):
    if r['id']=='0' or not r['mag']:continue
    mag=float(r['mag'])
    if mag>6.5 or not(r['proper'] or r['bf']):continue
    ident=r['hip'] or r['id'];name=r['proper'] or r['bf'].strip()
    rows.append(dict(id='HYG:'+ident,name=name[:200],category='Stars',ra=round(float(r['ra'])*15,8),dec=round(float(r['dec']),8),mag=mag,priority=1,pmra=float(r['pmra'] or 0),pmdec=float(r['pmdec'] or 0)))
import gzip
Path('assets/catalogs/objects.json.gz').write_bytes(gzip.compress((json.dumps(rows,separators=(',',':'))+'\n').encode(),mtime=0))
print(f'Wrote {len(rows)} catalog entries.')
