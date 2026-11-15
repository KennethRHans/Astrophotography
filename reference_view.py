"""Optional local survey-reference viewer; the processing image never enters it."""
import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit
from PySide6 import QtCore, QtGui, QtWidgets as W

# Required before QApplication for a lazily created WebEngine view.
QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)

SURVEY_PATHS={
 'stpubdata.s3.us-east-1.amazonaws.com':'/mast/skybackgrounds/DSSColor/',
 'casda.csiro.au':'/hips/DSS2/color/',
 'hips.china-vo.org':'/m/CDS_P_DSS2_color/',
 'skies.esac.esa.int':'/DSSColor/',
 'cdn.skies.esac.esa.int':'/DSSColor/',
 'skyview.gsfc.nasa.gov':'/current/cgi/runquery.pl',
}

def allowed_remote(url):
    parsed=urlsplit(url)
    prefix=SURVEY_PATHS.get(parsed.hostname)
    return bool(parsed.scheme=='https' and not parsed.username and not parsed.password
                and parsed.port in (None,443) and prefix and parsed.path.startswith(prefix))


def reference_context(header=None,shape=None,solution=None):
    """Return only public pointing information, never the complete FITS header."""
    from object_identification import celestial_wcs,catalog
    from astropy.wcs.utils import proj_plane_pixel_scales
    name=str(header.get('OBJECT','')).strip() if header is not None else ''
    if shape is not None:
        try:
            wcs=celestial_wcs(solution if solution is not None else header,shape)
            height,width=shape[:2]
            ra,dec=wcs.pixel_to_world_values((width-1)/2,(height-1)/2)
            scales=proj_plane_pixel_scales(wcs)
            fov=max(float(scales[0])*width,float(scales[1])*height)
            if all(math.isfinite(float(x)) for x in (ra,dec,fov)) and fov>0:
                return dict(name=name or 'Current image field',ra=float(ra)%360,dec=float(dec),
                    fov=round(min(10,max(.05,fov)),5),
                    hint='Suggested from the current image’s sky solution. Check the field before loading. The reference is a square view, not registered to your image.')
        except (ValueError,TypeError,AttributeError):
            pass
    key=re.sub(r'[^A-Z0-9]','',name.upper())
    key={'C56':'NGC246'}.get(key,key)
    def canonical(value):
        value=re.sub(r'[^A-Z0-9]','',value.upper())
        return re.sub(r'^(NGC|IC|M|C)0+(?=\d)',r'\1',value)
    if key:
        for row in catalog():
            if canonical(key) in [canonical(alias) for alias in row['name'].split('/')]:
                return dict(name=name,ra=row['ra'],dec=row['dec'],fov=.5,
                    hint='Suggested from the object name in the bundled catalog. No complete sky solution was available. Set the field width and check the target before loading.')
    return dict(name=name or 'Custom sky coordinates',ra=None,dec=None,fov=.5,
        hint='No reliable sky position found. Select a listed object or enter RA and Dec in degrees. No request has been made.')


class ReferenceBridge(QtCore.QObject):
    readySignal=QtCore.Signal()
    def __init__(self,guard,parent=None):
        super().__init__(parent);self.guard=guard
    @QtCore.Slot(bool,result=bool)
    def setPermission(self,enabled):
        self.guard.enabled=bool(enabled)
        return self.guard.enabled
    @QtCore.Slot()
    def ready(self):self.readySignal.emit()
    @QtCore.Slot(str)
    def openExternal(self,url):
        parsed=urlsplit(url)
        docs={'github.com','skyview.gsfc.nasa.gov','aladin.cds.unistra.fr','alasky.cds.unistra.fr'}
        if (allowed_remote(url) and self.guard.enabled) or (parsed.scheme=='https' and parsed.hostname in docs and not parsed.username and not parsed.password):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))


class ReferencePanel(W.QWidget):
    contextRequested=QtCore.Signal()
    def __init__(self,parent=None,storage_path=None):
        super().__init__(parent)
        # Static imports let PyInstaller bundle the browser helper/resources;
        # the helper process starts only when this optional panel is opened.
        from PySide6.QtWebEngineCore import QWebEngineProfile,QWebEnginePage,QWebEngineSettings,QWebEngineUrlRequestInterceptor,QWebEngineScript
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtWebChannel import QWebChannel
        root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'assets'/'reference'
        class Guard(QWebEngineUrlRequestInterceptor):
            enabled=False
            def interceptRequest(guard,info):
                url=info.requestUrl();scheme=url.scheme()
                if scheme=='https':
                    info.block(not guard.enabled or bytes(info.requestMethod()) not in (b'GET',b'HEAD',b'OPTIONS') or not allowed_remote(url.toString()))
                elif scheme=='file':
                    info.block(Path(url.toLocalFile()).resolve()!= (root/'reference.html').resolve())
                elif scheme not in ('data','blob','qrc','about'):info.block(True)
        class Page(QWebEnginePage):
            def acceptNavigationRequest(page,url,kind,is_main):
                if is_main:return url==QtCore.QUrl.fromLocalFile(str(root/'reference.html')) or url.toString()=='about:blank'
                return url.scheme() in ('about','blob','data')
            def createWindow(page,kind):return None
        self.ready=False;self._context=reference_context();self._theme=None
        layout=W.QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        self.refresh=W.QPushButton('Use current image’s object / sky position');layout.addWidget(self.refresh)
        self.refresh.clicked.connect(self.contextRequested)
        self.view=QWebEngineView(self);layout.addWidget(self.view,1)
        location=Path(storage_path or QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.AppLocalDataLocation))/'object-reference'
        location.mkdir(parents=True,exist_ok=True)
        self.profile=QWebEngineProfile('ObjectReference',self)
        self.profile.setPersistentStoragePath(str(location));self.profile.setHttpCacheType(QWebEngineProfile.MemoryHttpCache)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)
        self.guard=Guard(self.profile);self.profile.setUrlRequestInterceptor(self.guard)
        self.profile.downloadRequested.connect(lambda download:download.cancel())
        self.page=Page(self.profile,self.view);self.view.setPage(self.page)
        channel_file=QtCore.QFile(':/qtwebchannel/qwebchannel.js')
        if not channel_file.open(QtCore.QIODevice.ReadOnly):raise RuntimeError('Qt WebChannel resource is missing')
        script=QWebEngineScript();script.setName('Local reference bridge')
        script.setSourceCode(bytes(channel_file.readAll()).decode('utf-8'));channel_file.close()
        script.setInjectionPoint(QWebEngineScript.DocumentCreation);script.setWorldId(QWebEngineScript.MainWorld)
        script.setRunsOnSubFrames(False);self.page.scripts().insert(script)
        settings=self.page.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls,True)
        settings.setAttribute(QWebEngineSettings.DnsPrefetchEnabled,False)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls,False)
        settings.setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture,True)
        self.page.featurePermissionRequested.connect(lambda origin,feature:self.page.setFeaturePermission(origin,feature,QWebEnginePage.PermissionDeniedByUser))
        self.bridge=ReferenceBridge(self.guard,self)
        self.channel=QWebChannel(self.page);self.channel.registerObject('referenceBridge',self.bridge);self.page.setWebChannel(self.channel)
        self.bridge.readySignal.connect(self._became_ready)
        if (root/'reference.html').is_file():self.view.load(QtCore.QUrl.fromLocalFile(str(root/'reference.html')))
        else:layout.addWidget(W.QLabel('Reference renderer is missing. Run scripts/prepare_reference_assets.py before building.'))
        self.setMinimumWidth(360)
    def _became_ready(self):
        self.ready=True;self.set_context(self._context)
        if self._theme:self.set_theme(self._theme)
    def set_context(self,context):
        self._context=context;self.guard.enabled=False
        if self.ready:self.page.runJavaScript('window.setReferenceContext('+json.dumps(context)+');')
    def set_theme(self,theme):
        self._theme=theme
        if self.ready:self.page.runJavaScript('window.setReferenceTheme('+json.dumps(theme)+');')
    def cancel(self):
        self.guard.enabled=False
        if self.ready:self.page.runJavaScript('revokeReferenceConsent();')
    def shutdown(self):
        self.cancel();self.view.stop()
        # Destroy the page before its profile (required by Qt WebEngine).
        import shiboken6
        shiboken6.delete(self.view)
        self.ready=False
        shiboken6.delete(self.profile)
