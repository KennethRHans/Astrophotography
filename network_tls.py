"""Verified HTTPS roots bundled with the app, including sandboxed macOS builds."""
import ssl
import certifi


def https_context():
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    return context
