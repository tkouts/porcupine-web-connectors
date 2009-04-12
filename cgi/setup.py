# setup.py
"py2exe script for generating executable CGI"
from distutils.core import setup
import py2exe

setup(
    name = 'Porcupine Server CGI Connector',
    version = '0.1.1',
    url = 'http://www.innoscript.org',
    author_email="tkouts@innoscript.org",
    author = 'Tassos Koutsovassilis',
    zipfile = None,
    console = [
        "porcupine.py",
    ],
    options = {
        "py2exe": {
            "optimize": 1,
            "packages": [],
            "includes": [],
            "excludes": []
        }
    },
    data_files = [
        ( "", ["server.ini"] ),
    ]
)
