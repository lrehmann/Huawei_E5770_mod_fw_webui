#!/usr/bin/env python3
"""Generate small on-device screen presets and the matching default profile."""
from pathlib import Path
import json
from pixels import ROOT, GLYPHS, render, patch_animation


def generate():
    base = ROOT / 'system/etc/cozy'
    base.mkdir(parents=True, exist_ok=True)
    for theme in ('cat', 'cloud', 'sprout'):
        for height in (64, 128):
            folder = base / 'themes' / theme
            folder.mkdir(parents=True, exist_ok=True)
            for kind in ('boot', 'bye'):
                data = render(theme, height=height, goodbye=(kind == 'bye'))
                (folder / f'{kind}{height}.hex').write_text(data.hex() + '\n')
    profile = {
        'version': '1', 'theme': 'cat', 'label': 'COZY HOTSPOT',
        'message': 'HELLO FRIEND', 'dim_seconds': '10', 'sleep_seconds': '15',
        'poll_seconds': '30', 'boot64': render().hex(),
        'boot128': render(height=128).hex(),
    }
    (base / 'default.profile').write_text(''.join(f'{k}={v}\n' for k, v in profile.items()))
    web = ROOT / 'system/www/cozy'
    web.mkdir(parents=True, exist_ok=True)
    (web / 'glyphs.js').write_text('window.COZY_GLYPHS=' + json.dumps(GLYPHS, separators=(',', ':')) + ';\n')
    for folder, height in [('oled', 128), ('oled_128x64', 64)]:
        p = ROOT / 'web/WebApp/common/config' / folder / 'animation.xml'
        old = p.read_bytes().decode('utf-8')
        p.write_bytes(patch_animation(old, render(height=height), render(height=height, goodbye=True)).encode('utf-8'))


if __name__ == '__main__':
    generate()
