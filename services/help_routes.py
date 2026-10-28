"""Serve only the bundled offline manual, without exposing workspace files."""
from pathlib import Path
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

def manual_url(language):
    return '/help/help.html' if str(language).upper() == 'IT' else '/help/help.en.html'

def manual_routes():
    directory = Path(__file__).resolve().parents[1] / 'help'
    return [Mount('/help', app=StaticFiles(directory=str(directory), html=True))]
