import time
import numpy as np
from astropy.io import fits
from PySide6 import QtCore, QtWidgets
import app as application
from app import Window
import engine
from project_store import save_project


def settings_at(tmp_path):
    return QtCore.QSettings(str(tmp_path / 'preferences.ini'), QtCore.QSettings.IniFormat)


def test_fits_folder_persists_across_windows_and_cancel(tmp_path, monkeypatch):
    qt = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    # Exercise the Qt path on any host without presenting native panels.
    monkeypatch.setattr(application.sys, 'platform', 'linux')
    chosen = str(tmp_path / 'Lights' / 'light.fit')
    monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileNames', lambda *args: ([chosen], ''))
    first = Window(ask_on_close=False, settings=settings_at(tmp_path))
    first.add_files()
    first.close()
    second = Window(ask_on_close=False, settings=settings_at(tmp_path))
    seen = []
    def cancel(parent, title, folder, filters):
        seen.append(folder)
        return '', ''
    monkeypatch.setattr(QtWidgets.QFileDialog, 'getOpenFileName', cancel)
    assert second.choose_fits() == []
    assert seen == [str(tmp_path / 'Lights')]
    assert second.settings_store.value('files/last_fits_directory') == seen[0]
    second.close()


def test_gpu_choice_survives_restart_and_unavailable_device(tmp_path, monkeypatch):
    import gpu
    qt = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    class Device:
        name = 'Test GPU'
        disabled = False
        last_error = None
    monkeypatch.setattr(gpu, 'create_gpu_processor', lambda: Device())
    first = Window(ask_on_close=False, settings=settings_at(tmp_path))
    first.use_gpu.setChecked(True)
    first.close()
    second = Window(ask_on_close=False, settings=settings_at(tmp_path))
    assert second.use_gpu.isChecked() and isinstance(second.gpu, Device)
    second.close()
    def unavailable(): raise RuntimeError('Device unavailable')
    monkeypatch.setattr(gpu, 'create_gpu_processor', unavailable)
    fallback = Window(ask_on_close=False, settings=settings_at(tmp_path))
    assert fallback.gpu is None and not fallback.use_gpu.isChecked()
    assert fallback.settings_store.value('processing/use_gpu', type=bool)
    fallback.close()
    monkeypatch.setattr(gpu, 'create_gpu_processor', lambda: Device())
    recovered = Window(ask_on_close=False, settings=settings_at(tmp_path))
    assert recovered.use_gpu.isChecked()
    recovered.use_gpu.setChecked(False)
    recovered.close()
    final = Window(ask_on_close=False, settings=settings_at(tmp_path))
    assert not final.use_gpu.isChecked()
    final.close()


def test_old_project_adds_neutral_sky_to_edits_and_undo_history(tmp_path):
    qt = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = Window(ask_on_close=False, settings=settings_at(tmp_path))
    pixels = np.ones((30, 40, 3), dtype='float32') * 100
    window.loaded(pixels, fits.Header())
    metadata = window.project_manifest()
    metadata['state']['sliders'].pop('Sky brightness (stops ×100)')
    for state in metadata['history']['states']:
        state['sliders'].pop('Sky brightness (stops ×100)')
    path = tmp_path / 'older.astro'
    save_project(path, pixels, fits.Header(), metadata)
    window.sliders['Sky brightness (stops ×100)'].setValue(100)
    window.open_project_path(path)
    deadline = time.monotonic() + 15
    while window.project_worker is not None and time.monotonic() < deadline:
        qt.processEvents()
        time.sleep(.01)
    assert window.project_worker is None and window._project_io_ok
    assert window.sliders['Sky brightness (stops ×100)'].value() == 0
    assert all(state['sliders']['Sky brightness (stops ×100)'] == 0 for state in window.history.states)
    window.close()


def test_sky_tone_is_neutral_by_default_and_weights_shadows():
    pixels = np.array([[[.1, .1, .1], [.9, .9, .9], [1, 1, 1]]], dtype='float32')
    before = pixels.copy()
    np.testing.assert_array_equal(engine.adjust_sky(pixels), pixels)
    dark = engine.adjust_sky(pixels, -1)
    light = engine.adjust_sky(pixels, 1)
    assert dark[0,0,0] < pixels[0,0,0] < light[0,0,0]
    assert light[0,0,0] - pixels[0,0,0] > light[0,1,0] - pixels[0,1,0]
    np.testing.assert_array_equal(light[0,2], pixels[0,2])
    np.testing.assert_array_equal(pixels, before)


def test_sky_preserves_uncovered_borders_and_gpu_failure_result():
    image = np.random.default_rng(5).uniform(100, 1000, (30,40,3)).astype('float32')
    image[0] = 0
    class FailedGPU:
        disabled = False
        last_error = None
        def process(self, *args): raise RuntimeError('Unavailable')
    expected = engine.render(image, sky=.8)
    actual = engine.render(image, sky=.8, gpu=FailedGPU())
    np.testing.assert_array_equal(actual, expected)
    assert not actual[0].any()


def test_project_gpu_view_does_not_override_app_preference(tmp_path, monkeypatch):
    import gpu
    qt = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    class Device:
        name = 'Test adjustments GPU'
        disabled = False
        last_error = None
        def process(self, image, *args): return image.copy()
    monkeypatch.setattr(gpu, 'create_gpu_processor', lambda: Device())
    store = settings_at(tmp_path)
    store.setValue('processing/use_gpu', True)
    window = Window(ask_on_close=False, settings=store)
    pixels = np.ones((30, 40, 3), dtype='float32') * 100
    header = fits.Header()
    window.loaded(pixels, header)
    metadata = window.project_manifest()
    metadata['view']['gpu'] = False
    window._project_io_path = str(tmp_path / 'project.astro')
    window._project_opened((pixels, header, metadata))
    assert window._project_io_ok
    assert window.use_gpu.isChecked()
    assert store.value('processing/use_gpu', type=bool)
    window.close()
