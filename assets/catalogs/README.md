# Bundled object catalog

`objects.json.gz` is a reduced and reformatted derivative catalog, licensed under
[Creative Commons Attribution-ShareAlike 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
The full license is included as `CC-BY-SA-4.0.txt`. The catalog license applies
to this data, independently of the application code.

Sources retrieved November 7, 2026:

* **OpenNGC**, Mattia Verga and contributors:
  https://github.com/mattiaverga/OpenNGC, `database_files/NGC.csv` (master).
  Selected positioned galaxies, star clusters and nebulae. Converted sexagesimal
  J2000 coordinates to degrees and retained NGC/IC, Messier and common names,
  object class and V magnitude (B magnitude where V is unavailable).
* **HYG Stellar Database v4.1**, David Nash / Astronomy Nexus and contributors:
  https://github.com/astronexus/HYG-Database, `hyg/CURRENT/hygdata_v41.csv` (main).
  Selected named/Bayer/Flamsteed stars of magnitude 6.5 or brighter, excluding
  the Sun. Retained J2000 positions, magnitude and proper motions.
  Current upstream: https://codeberg.org/astronexus/hyg.

Changes: selected columns/rows, renamed categories, converted coordinates,
rounded to eight decimal places and serialized as compact JSON. These are
catalog positions, not a claim of image detection, complete sky coverage or
survey-level astrometric accuracy. Proper motions are used for stars when a
valid observation date is available. Deep-sky magnitudes may be absent or
approximate. OpenNGC source acknowledgments: NASA/IPAC Extragalactic Database
(NED), HyperLEDA, SIMBAD (CDS Strasbourg), HEASARC, and Harold Corwin's NGC/IC
positions and notes. Consult the upstream README for per-field provenance.

Source CSV SHA-256 checksums (before reduction):

* OpenNGC NGC.csv: `54abea0b57b0a103831bfc7a8e3a99a23acfbf4bb581fcf3d8af539cbb826c84`
* HYG v4.1 CSV: `d9f69fd86bbf90a4e4d52b4c5c53eacfa6dfc0bfdef85bfd94f095e0bebe4ebd`

## Optional Gaia matching

Gaia is queried online only after separate consent; its full catalog is not
bundled here. The runtime uses ESA Gaia DR3 source parameters from
https://gea.esac.esa.int/archive/documentation/GDR3/ . Credit: ESA mission Gaia
and the Gaia Data Processing and Analysis Consortium (DPAC). DPAC funding is
provided by national institutions, particularly those participating in the
Gaia Multilateral Agreement. Local candidate matching is not an independent
plate solution, source classification or guarantee of identity.
