"""Reference outputs from the shipped Windows 1.5 and previous Mac engines.

Fixtures were generated from Windows source 133591e and Mac source 7721e1f,
using numpy seed 2026. Changes must preserve the baseline Windows rendering
and saved Mac sky-exposure edits when all other new controls are neutral.
"""
from pathlib import Path
import numpy as np
import engine
from network_tls import https_context
import ssl


def test_windows_15_render_parity_and_previous_mac_sky():
    with np.load(Path(__file__).parent/'fixtures/render_15_parity.npz') as fixture:
        image=fixture['image']
        for key,options in [
            ('windows_neutral',{}),
            ('windows_adjusted',dict(sky=-.25,midtones=.35,star_denoise=.4,star_protection=.8,curve=(0,350,650,820,1000))),
            ('mac_sky',dict(legacy_sky=.7)),
        ]:
            np.testing.assert_allclose(engine.render(image,**options),fixture[key],atol=3e-5,rtol=3e-5)


def test_online_clients_keep_tls_verification_and_bundled_roots():
    context=https_context()
    assert context.check_hostname and context.verify_mode==ssl.CERT_REQUIRED
    assert context.cert_store_stats()['x509_ca']>0
