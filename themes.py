"""Application-only appearance; image rendering stays independent of themes."""
from PySide6 import QtGui

DARK=dict(bg='#000000',fg='#f1f6fd',base='#071321',alt='#102640',panel='#0b2545',title='#12395e',border='#3a6c9e',edge='#74b9e9',accent='#247eb6',button='#123252',hover='#1b466d',pressed='#235a86',disabled='#0a192b',muted='#91a5bf',groove='#254668',handle='#def2ff',link='#7bceff',warning='#ffce7a')
THEMES={
    'Dark':DARK,
    'Light':dict(DARK,bg='#f4f6fa',fg='#182b40',base='#ffffff',alt='#e9eef5',panel='#e7edf6',title='#24669e',border='#6985a5',edge='#2974a8',accent='#24669e',button='#dae6f3',hover='#c6dced',pressed='#b1cbe3',disabled='#e5e9ef',muted='#5b6d80',groove='#c6d2df',handle='#ffffff',link='#005da8',warning='#925000'),
    'Midnight Purple':dict(DARK,bg='#100b18',base='#191122',alt='#271a35',panel='#281a3b',title='#402659',border='#8362a7',edge='#bd98e5',accent='#8050b0',button='#39234f',hover='#50316c',pressed='#654187',disabled='#1c1426',groove='#4b335f',link='#d9b6ff'),
    'Forest Green':dict(DARK,bg='#08120e',base='#0d1e16',alt='#173025',panel='#183627',title='#214b37',border='#55886b',edge='#94cfac',accent='#28764e',button='#20452f',hover='#2e6043',pressed='#397452',disabled='#11231a',groove='#305740',link='#9ee4b9'),
    'Slate':dict(DARK,bg='#161c24',base='#202934',alt='#303c4a',panel='#2a3543',title='#394b60',border='#73879e',edge='#b0c5dd',accent='#426e9b',button='#35465a',hover='#465b73',pressed='#54708d',disabled='#242d39',groove='#4e6075',link='#b0d7ff'),
    'Warm Copper':dict(DARK,bg='#18100c',base='#241911',alt='#36251a',panel='#3b281d',title='#593921',border='#a47955',edge='#e6b388',accent='#985022',button='#51331f',hover='#69452a',pressed='#805536',disabled='#291c15',groove='#65462f',link='#ffd0a5'),
}

BASE_CSS = '''

            QMainWindow, QWidget#appCanvas, QWidget#controlPanel, QScrollArea { background: #000000; color: #f1f6fd; }
            QScrollArea { border: none; }
            QToolBar { background: #000000; border-bottom: 1px solid #3a6c9e; spacing: 6px; }
            QFrame#histogramPanel { background: #0b2545; border: 1px solid #3a6c9e; border-radius: 5px; }
            QGroupBox#stepEquipment, QGroupBox#stepLoad, QGroupBox#stepStack, QGroupBox#stepAdjust, QGroupBox#stepExport {
                border: 2px solid #3a6c9e; border-radius: 8px;
                margin-top: 4px; padding-top: 4px; background: #0b2545;
            }
            QLabel#sectionTitle {
                color: #ffffff; font-size: 20px; font-weight: bold;
                background: #12395e; border: 1px solid #74b9e9;
                border-radius: 5px; padding: 8px 10px; margin-bottom: 6px;
            }
            QLabel#sectionTitle:disabled { color: #c3d5e9; background: #102b49; border-color: #466888; }
            QFrame#gpuPanel { background: #0b2545; border: 2px solid #3a6c9e; border-radius: 8px; }
            QCheckBox#gpuSwitch::indicator { width: 20px; height: 20px; }
            QFrame#previewPanel { background: #000000; border: 2px solid #3a6c9e; border-radius: 8px; }
            QLabel#sliderValue { color: #def2ff; font-weight: bold; }
            QCheckBox#gpuSwitch { background: transparent; color: #f1f6fd; font-size: 12px; }
            QGroupBox { color: #f1f6fd; }
            QLabel { color: #f1f6fd; background: transparent; }
            QLabel:disabled { color: #91a5bf; }
            QCheckBox { color: #f1f6fd; spacing: 7px; }
            QCheckBox:disabled { color: #91a5bf; }
            QPushButton, QToolButton {
                background: #123252; color: #f1f6fd; border: 1px solid #476b95;
                border-radius: 4px; padding: 5px 8px;
            }
            QPushButton:hover, QToolButton:hover { background: #1b466d; border-color: #74c8ff; }
            QPushButton:pressed, QToolButton:pressed { background: #235a86; }
            QPushButton:disabled, QToolButton:disabled { background: #0a192b; color: #91a5bf; border-color: #28415f; }
            QComboBox, QSpinBox, QLineEdit, QListWidget, QPlainTextEdit {
                background: #071321; color: #f1f6fd; border: 1px solid #3a5e86;
                border-radius: 3px; padding: 3px; selection-background-color: #247eb6;
                selection-color: #ffffff;
            }
            QComboBox QAbstractItemView { background: #102640; color: #f1f6fd; selection-background-color: #247eb6; }
            QProgressBar { background: #071321; color: #ffffff; border: 1px solid #3a5e86; border-radius: 3px; text-align: center; }
            QProgressBar::chunk { background: #247eb6; }
            QSlider::groove:horizontal { height: 8px; background: #254668; border-radius: 4px; }
            QSlider::sub-page:horizontal { background: #379cc3; border-radius: 4px; }
            QSlider::handle:horizontal { width: 24px; margin: -8px 0; background: #def2ff;
                border: 2px solid #5ec9ff; border-radius: 8px; }
            QSlider::handle:horizontal:hover { background: #91d6ff; }
            QSlider::handle:horizontal:pressed { background: #57bbef; }
        '''


def apply_theme(app,name):
    if not isinstance(name,str) or name not in THEMES:name='Dark'
    c=THEMES[name]
    palette=QtGui.QPalette()
    roles={'Window':'bg','WindowText':'fg','Base':'base','AlternateBase':'alt','Text':'fg','Button':'button','ButtonText':'fg','Highlight':'accent','ToolTipBase':'panel','ToolTipText':'fg','Link':'link','Mid':'border','Light':'edge','Dark':'disabled','PlaceholderText':'muted'}
    for role,key in roles.items():palette.setColor(getattr(QtGui.QPalette,role),QtGui.QColor(c[key]))
    palette.setColor(QtGui.QPalette.HighlightedText,QtGui.QColor('#ffffff'))
    for role in (QtGui.QPalette.WindowText,QtGui.QPalette.Text,QtGui.QPalette.ButtonText):palette.setColor(QtGui.QPalette.Disabled,role,QtGui.QColor(c['muted']))
    app.setPalette(palette)
    mapping={'#000000':'bg','#f1f6fd':'fg','#071321':'base','#102640':'alt','#0b2545':'panel','#12395e':'title','#3a6c9e':'border','#74b9e9':'edge','#c3d5e9':'muted','#102b49':'disabled','#466888':'border','#91a5bf':'muted','#123252':'button','#476b95':'border','#1b466d':'hover','#74c8ff':'edge','#235a86':'pressed','#0a192b':'disabled','#28415f':'border','#3a5e86':'border','#247eb6':'accent','#254668':'groove','#379cc3':'accent','#def2ff':'handle','#5ec9ff':'edge','#91d6ff':'edge','#57bbef':'accent'}
    # Replace original literals once, without remapping a newly inserted color.
    import re
    css=re.sub(r'#[0-9a-fA-F]{6}',lambda match:c[mapping[match.group()]] if match.group() in mapping else match.group(),BASE_CSS)
    css+='''
        QDialog, QMenuBar, QMenu, QStatusBar { background: BG; color: FG; }
        QMenuBar::item:selected, QMenu::item:selected { background: ACCENT; color:white; }
        QHeaderView::section { background: TITLE; color:white; border:1px solid BORDER; padding:4px; }
        QTableWidget { background: BASE; color: FG; gridline-color: BORDER; selection-background-color: ACCENT; selection-color:white; }
        QFrame#communityPanel { background: BG; border:1px solid BORDER; border-radius:6px; }
        QLabel#byline { font-size:12px; color: MUTED; }
        QLabel#bayerHelp { color: FG; padding:6px; border:1px solid BORDER; }
        QLabel#sliderValue { color: FG; }
        QFrame#previewPanel, QGraphicsView { background:#000000; }
    '''
    for token,key in [('BG','bg'),('FG','fg'),('ACCENT','accent'),('TITLE','title'),('BORDER','border'),('BASE','base'),('MUTED','muted')]:css=css.replace(token,c[key])
    app.setStyleSheet(css)
    return name
