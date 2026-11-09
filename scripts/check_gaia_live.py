"""Read a public M31 catalog region; no user image, credentials or metadata."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gaia_matching import GaiaClient
for radius,magnitude in [(.1,18),(1.7,16)]:
    rows=GaiaClient().query(10.6847,41.2688,radius,magnitude)
    assert rows,'Public Gaia cone query returned no sources'
    print(f'Gaia DR3 live protocol check passed: radius {radius} deg, G {magnitude}, {len(rows)} public catalog sources.')
