# Vendored third-party packages

## youtubesearchpython

A vendored, lightly modified copy of [youtube-search-python](https://pypi.org/project/youtube-search-python/)
(MIT licensed — see `youtubesearchpython/LICENSE`).

FastSM's YouTube platform uses this library for search, suggestions, and
InnerTube-based metadata (the parts not covered by the official YouTube Data
API). It is vendored rather than installed from PyPI because the upstream
release is unmaintained and needed fixes to keep working against current
InnerTube responses (updated `clientVersion`, renderer paths, and request
payloads).

It is made importable as the top-level package `youtubesearchpython` by a small
`sys.path` shim in `platforms/youtube/__init__.py`, so existing
`import youtubesearchpython` / `from youtubesearchpython.core...` imports work
unchanged whether or not the PyPI package is installed.

Upstream: https://github.com/alexmercerind/youtube-search-python
