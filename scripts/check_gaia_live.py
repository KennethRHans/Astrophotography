"""Read a public M31 catalog region; no user image, credentials or metadata."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gaia_matching import GaiaClient
rows=GaiaClient().query(10.6847,41.2688,.1,18)
assert rows,'Public Gaia cone query returned no sources'
print(f'Gaia DR3 live protocol check passed: {len(rows)} public catalog sources.')
