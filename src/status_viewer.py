
import aiohttp_jinja2
import jinja2


PROJ_ROOT = pathlib.Path(__file__).parent
TEMPLATES_ROOT = pathlib.Path(__file__).parent / 'templates'

print(f"TEMPLATES AT: {TEMPLATES_ROOT} And {PROJ_ROOT}")


def setup_jinja(app):
    loader = jinja2.FileSystemLoader(str(TEMPLATES_ROOT))
    jinja_env = aiohttp_jinja2.setup(app, loader=loader)
    return jinja_env
