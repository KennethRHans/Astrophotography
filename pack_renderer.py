"""Embed or replace the unmodified renderer module in the portable HTML.

Usage: python pack_renderer.py Reference-View-Test.html path/to/aladin.js
Use a modified replacement module at your discretion; preserve upstream license
notices and provide corresponding source when redistributing it.
"""
import base64,hashlib,re,sys
from pathlib import Path
html=Path(sys.argv[1]);module=Path(sys.argv[2]);source=html.read_text();data=module.read_bytes()
pattern=r'(<script id="aladinModule" type="application/octet-stream">).*?(</script>)'
source,count=re.subn(pattern,lambda m:m[1]+base64.b64encode(data).decode()+m[2],source,flags=re.S)
if count!=1:raise ValueError('Expected one renderer placeholder')
html.write_text(source);print('Embedded renderer:',len(data),'bytes; SHA256',hashlib.sha256(data).hexdigest())
