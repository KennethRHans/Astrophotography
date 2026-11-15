"""Offline packaged-browser verification (never requests a survey)."""
import json
import time
from PySide6 import QtCore

def wait_for(app,predicate,timeout=25):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        app.processEvents()
        if predicate():return
        time.sleep(.01)
    raise AssertionError('Reference viewer timed out')

def javascript(panel,app,source):
    result=[]
    panel.page.runJavaScript('JSON.stringify('+source+')',lambda value:result.append(value))
    wait_for(app,lambda:bool(result))
    return json.loads(result[0])

def smoke_reference(window,app):
    window.toggle_reference();panel=window.reference_panel
    wait_for(app,lambda:panel.ready)
    assert not panel.guard.enabled,'Reference requested network access without consent'
    panel.set_context(dict(name='Public test field',ra=40.6696,dec=-.0133,fov=.5,hint='Offline packaging test'))
    wait_for(app,lambda:javascript(panel,app,"$('ra').value")=='40.6696')
    assert javascript(panel,app,"$('consent').checked") is False
    assert javascript(panel,app,"$('loadReference').disabled") is True
    # Isolated synthetic cached reference: do not change the user's saved cache.
    result=javascript(panel,app,"""(()=>{
      const original=localStorage.getItem(referenceCacheKey);
      try {
       const canvas=document.createElement('canvas');canvas.width=32;canvas.height=32;
       canvas.getContext('2d').fillRect(0,0,32,32);const data=canvas.toDataURL();
       localStorage.setItem(referenceCacheKey,JSON.stringify([{key:cacheField('DSS2/color',40.6696,-.0133,.5),data,caption:'Synthetic offline test',survey:'DSS2/color',stored:'2026-11-15'}]));
       $('loadSaved').click();return !$('referenceImage').hidden&&$('referenceCaption').textContent.includes('Synthetic offline test');
      } finally {
       if(original===null)localStorage.removeItem(referenceCacheKey);else localStorage.setItem(referenceCacheKey,original);
      }
    })()""")
    assert result,'Saved reference did not load offline'
    assert not panel.guard.enabled
    panel.set_theme(dict(bg='#fff',fg='#000',panel='#eee',button='#ddd',border='#888',muted='#444',link='#00f',base='#fff',light=True))
    panel.cancel();window.reference_dock.hide()
