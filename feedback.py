"""User-written feedback, sent only when Send is clicked."""
import json
import re
from PySide6 import QtCore, QtGui, QtNetwork, QtWidgets as W
from community_links import FEEDBACK_URL
from privacy_viewer import show_privacy

from app_version import VERSION as APP_VERSION


class FeedbackDialog(W.QDialog):
    def __init__(self, parent=None, network=None):
        super().__init__(parent)
        self.setWindowTitle('Report a Bug / Suggest a Fix')
        self.resize(520, 460)
        self.network = network if network is not None else QtNetwork.QNetworkAccessManager(self)
        self.reply = None
        self._timed_out = False
        layout = W.QVBoxLayout(self)
        intro = W.QLabel('Found a problem or have an idea? Send the developer a message. Add your email if you would like a reply.')
        intro.setWordWrap(True);layout.addWidget(intro)
        disclosure=W.QLabel('Clicking Send shares your message, report type, app/version and any name/email you enter with Astrivanta through Formspree. Images and logs are not attached automatically.')
        disclosure.setWordWrap(True);layout.addWidget(disclosure)
        self.privacy_button=W.QPushButton('Read Privacy Policy');self.privacy_button.clicked.connect(self.open_privacy);layout.addWidget(self.privacy_button)

        fields = W.QFormLayout(); layout.addLayout(fields)
        self.kind = W.QComboBox(); self.kind.addItems(['Report a bug', 'Suggest a fix / improvement'])
        self.name = W.QLineEdit(); self.name.setMaxLength(150)
        self.email = W.QLineEdit(); self.email.setMaxLength(254)
        fields.addRow('Type',self.kind);fields.addRow('Name (optional)',self.name);fields.addRow('Email (optional)',self.email)
        layout.addWidget(W.QLabel('Message'))
        self.message = W.QPlainTextEdit();self.message.setPlaceholderText('What happened, what did you expect, and how can we reproduce it?')
        layout.addWidget(self.message,1)
        self.status = W.QLabel('');self.status.setWordWrap(True);self.status.setTextFormat(QtCore.Qt.PlainText);layout.addWidget(self.status)
        self.buttons = W.QDialogButtonBox(W.QDialogButtonBox.Cancel)
        self.send = self.buttons.addButton('Send',W.QDialogButtonBox.AcceptRole)
        self.send.clicked.connect(self.submit);self.buttons.rejected.connect(self.reject);layout.addWidget(self.buttons)
        self.timeout = QtCore.QTimer(self);self.timeout.setSingleShot(True);self.timeout.setInterval(30000);self.timeout.timeout.connect(self.abort_timeout)

    def open_privacy(self):show_privacy(self)

    def submit(self):
        if self.reply is not None:return
        message = self.message.toPlainText().strip();email = self.email.text().strip()
        if not message:
            self.status.setText('Please enter a message.');self.message.setFocus();return
        if len(message)>20000:
            self.status.setText('Please keep the message under 20,000 characters.');return
        if email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):
            self.status.setText('Please check your email address, or leave it blank.');self.email.setFocus();return
        payload = {'message':message,'type':self.kind.currentText(),'app':'Easy Astro Studio','version':APP_VERSION,
                   '_subject':'Easy Astro Studio: '+self.kind.currentText()}
        if self.name.text().strip():payload['name']=self.name.text().strip()
        if email:payload['email']=email
        request = QtNetwork.QNetworkRequest(QtCore.QUrl(FEEDBACK_URL))
        request.setHeader(QtNetwork.QNetworkRequest.ContentTypeHeader,'application/json')
        request.setRawHeader(b'Accept',b'application/json')
        request.setTransferTimeout(30000)
        self._timed_out = False
        self.reply = self.network.post(request,QtCore.QByteArray(json.dumps(payload).encode('utf-8')))
        self.reply.finished.connect(self.complete)
        for widget in (self.kind,self.name,self.email,self.message,self.send):widget.setEnabled(False)
        self.status.setText('Sending…');self.timeout.start()

    def abort_timeout(self):
        if self.reply is not None:
            self._timed_out=True;self.reply.abort()

    def complete(self):
        reply=self.reply
        if reply is None:return
        self.timeout.stop();self.reply=None
        status=reply.attribute(QtNetwork.QNetworkRequest.HttpStatusCodeAttribute)
        try:body=json.loads(bytes(reply.readAll()).decode('utf-8'))
        except (ValueError,UnicodeError):body={}
        success=(reply.error()==QtNetwork.QNetworkReply.NoError and status is not None and 200<=int(status)<300 and isinstance(body,dict) and body.get('ok') is True)
        reply.deleteLater()
        if success:
            self.accept();return
        for widget in (self.kind,self.name,self.email,self.message,self.send):widget.setEnabled(True)
        detail='The request timed out.' if self._timed_out else 'Check your connection and try again.'
        if not self._timed_out and isinstance(body,dict) and isinstance(body.get('errors'),list):
            messages=[item.get('message','') for item in body['errors'] if isinstance(item,dict) and isinstance(item.get('message'),str)]
            if messages:detail=' '.join(messages)[:500]
        elif not self._timed_out and status is not None and int(status)>=400:detail=f'The feedback service returned HTTP {status}. Try again later.'
        self.status.setText('Could not confirm the report was sent. Your message is still here. '+detail)

    def reject(self):
        if self.reply is not None:self.reply.abort()
        super().reject()
