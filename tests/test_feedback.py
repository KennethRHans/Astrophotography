import json
from PySide6 import QtCore,QtGui,QtNetwork,QtWidgets as W
from feedback import FeedbackDialog
from app import Window
import community_links


class Reply(QtCore.QObject):
    finished=QtCore.Signal()
    def __init__(self):
        super().__init__();self.status=200;self.body={'ok':True};self.failed=False
    def attribute(self,key):return self.status
    def error(self):return QtNetwork.QNetworkReply.ConnectionRefusedError if self.failed else QtNetwork.QNetworkReply.NoError
    def readAll(self):return QtCore.QByteArray(json.dumps(self.body).encode())
    def abort(self):self.failed=True;self.finished.emit()


class Network:
    def __init__(self):self.requests=[];self.reply=None
    def post(self,request,data):
        self.requests.append((request.url().toString(),bytes(request.rawHeader('Accept')),json.loads(bytes(data))))
        self.reply=Reply();return self.reply


def test_feedback_validation_retry_and_service_confirmation():
    app=W.QApplication.instance() or W.QApplication([])
    network=Network();dialog=FeedbackDialog(network=network)
    dialog.submit();assert not network.requests
    dialog.message.setPlainText('Stars disappear after cropping. ✨')
    dialog.email.setText('bad email');dialog.submit();assert not network.requests
    dialog.email.setText('observer@example.com');dialog.submit();dialog.submit()
    assert len(network.requests)==1
    url,accept,payload=network.requests[0]
    assert url=='https://formspree.io/f/xzezdzwd' and accept==b'application/json'
    assert payload['email']=='observer@example.com' and payload['message'].endswith('✨')
    assert 'files' not in payload and 'logs' not in payload
    network.reply.status=422;network.reply.body={'errors':[{'message':'Please try again later.'}]};network.reply.finished.emit()
    assert dialog.send.isEnabled() and dialog.message.toPlainText().startswith('Stars')
    assert 'Please try again later.' in dialog.status.text()
    dialog.submit();network.reply.body={'ok':True};network.reply.finished.emit()
    assert dialog.result()==W.QDialog.Accepted
    dialog.close()


def test_timeout_preserves_message_and_footer_links(monkeypatch):
    app=W.QApplication.instance() or W.QApplication([])
    network=Network();dialog=FeedbackDialog(network=network)
    dialog.message.setPlainText('My suggestion');dialog.submit();dialog.abort_timeout()
    assert 'timed out' in dialog.status.text() and dialog.message.toPlainText()=='My suggestion'
    assert dialog.send.isEnabled();dialog.close()
    window=Window(ask_on_close=False);opened=[]
    monkeypatch.setattr(QtGui.QDesktopServices,'openUrl',lambda url: opened.append(url.toString()) or True)
    window.coffee_button.click()
    window.planner_banner.linkActivated.emit(community_links.PLANNER_URL)
    assert opened==['https://cash.app/$KennethRHans','https://planner.astrivanta.com']
    feedback=[];monkeypatch.setattr(FeedbackDialog,'exec',lambda self: feedback.append(self.windowTitle()) or W.QDialog.Rejected)
    window.feedback_button.click();assert feedback==['Report a Bug / Suggest a Fix']
    window.close()


def test_privacy_link_available_before_feedback_submission(monkeypatch):
    app=W.QApplication.instance() or W.QApplication([])
    network=Network();dialog=FeedbackDialog(network=network);opened=[]
    monkeypatch.setattr(QtGui.QDesktopServices,'openUrl',lambda url:opened.append(url.toString()) or True)
    dialog.privacy_button.click()
    assert opened==[community_links.PRIVACY_URL] and not network.requests
    dialog.close()
    window=Window(ask_on_close=False);window.privacy_action.trigger()
    assert opened==[community_links.PRIVACY_URL,community_links.PRIVACY_URL]
    window.close()
