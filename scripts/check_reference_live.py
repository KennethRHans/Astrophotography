"""Explicit public M77 integration test. Never reads a user's capture."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reference_view import ReferencePanel
from reference_smoke import wait_for,javascript
from PySide6 import QtWidgets as W
app=W.QApplication([])
panel=ReferencePanel();panel.resize(520,920);panel.show()
try:
    wait_for(app,lambda:panel.ready)
    assert not panel.guard.enabled
    panel.set_context(dict(name='M77 (public integration test)',ra=40.6696,dec=-.0133,fov=.5,hint='Explicit public test'))
    javascript(panel,app,"(()=>{$('grayFallback').checked=false;$('saveReference').checked=false;$('consent').checked=true;$('consent').onchange();return true})()")
    wait_for(app,lambda:javascript(panel,app,"!$('loadReference').disabled"))
    javascript(panel,app,"(()=>{$('loadReference').click();return true})()")
    wait_for(app,lambda:javascript(panel,app,"Boolean(window.lastColorRender)||$('referenceStatus').textContent.startsWith('Color reference unavailable')"),140)
    result=javascript(panel,app,"({result:window.lastColorRender||null,status:$('referenceStatus').textContent,diagnostics:window.colorDiagnostics})")
    print(json.dumps(result))
    assert result['result'] and result['result']['variance']>1,'Live color reference failed'
finally:
    panel.shutdown();panel.close();app.processEvents()
