# Reference View standalone test 0.2

NASA SkyView DSS2 Red (grayscale) is now the default after live checks found CDS primary returning 404 and its mirror timing out. The test adds provider selection, request diagnostics and an Open request in browser control. Local images are not uploaded. This isolated branch creates only a standalone HTML download, not an Easy Astro Studio update or installer.

Extract the ZIP and open Reference-View-Test.html in Edge or Chrome. Read START-HERE.txt for supported FITS layouts and limitations. Grayscale references guide structure/framing, not color or predicted final quality.

The workflow checks public services and runs browser regression tests plus a real NASA image load from a file:// page. Check the workflow result before relying on service availability.
