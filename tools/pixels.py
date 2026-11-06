"""Small, deterministic 1-bit OLED renderer; shared glyphs also drive the web preview."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
GLYPHS = json.loads((ROOT / 'ui/glyphs.json').read_text())


def render(theme='cat', message='HELLO FRIEND', height=64, goodbye=False):
    if theme not in ('cat', 'cloud', 'sprout') or height not in (64, 128):
        raise ValueError('Unsupported screen')
    if len(message) > 18 or any(c not in GLYPHS for c in message):
        raise ValueError('Use at most 18 supported characters')
    pixels = [[0] * 128 for _ in range(height)]
    oy = (height - 64) // 2

    def point(x, y):
        if 0 <= x < 128 and 0 <= y + oy < height:
            pixels[y + oy][x] = 1

    def line(x0, y0, x1, y1):
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            point(x0, y0)
            if (x0, y0) == (x1, y1):
                break
            twice = 2 * err
            if twice >= dy:
                err += dy
                x0 += sx
            if twice <= dx:
                err += dx
                y0 += sy

    def path(points):
        for a, b in zip(points, points[1:]):
            line(*a, *b)

    def text(value, y):
        x = (128 - (len(value) * 6 - 1)) // 2
        for c in value:
            for row, bits in enumerate(GLYPHS[c]):
                for col in range(5):
                    if bits & (1 << (4 - col)):
                        point(x + col, y + row)
            x += 6

    text('COZY HOTSPOT', 1)
    if theme == 'cat':
        path([(48, 39), (46, 25), (47, 15), (56, 20), (72, 20),
              (81, 15), (82, 25), (80, 39), (74, 43), (54, 43), (48, 39)])
        if goodbye:
            line(53, 29, 58, 29)
            line(70, 29, 75, 29)
        else:
            line(55, 27, 55, 29)
            line(73, 27, 73, 29)
        path([(61, 33), (64, 35), (67, 33)])
        line(43, 31, 51, 33)
        line(43, 36, 51, 35)
        line(77, 33, 85, 31)
        line(77, 35, 85, 36)
    elif theme == 'cloud':
        path([(44, 39), (40, 36), (40, 29), (44, 25), (50, 25),
              (50, 20), (56, 15), (65, 15), (71, 19), (73, 24),
              (81, 24), (87, 29), (87, 36), (82, 40), (44, 40)])
        line(55, 29, 55 if not goodbye else 59, 31 if not goodbye else 29)
        line(73, 29, 73 if not goodbye else 77, 31 if not goodbye else 29)
        path([(61, 34), (64, 36), (67, 34)])
    else:
        path([(64, 43), (64, 29), (58, 24), (49, 23), (45, 17),
              (54, 16), (61, 19), (64, 26), (67, 19), (74, 16),
              (83, 17), (79, 23), (70, 24), (64, 29)])
        line(52, 43, 76, 43)
        line(57, 46, 71, 46)
        point(60, 38)
        point(68, 38)
    for x, y in [(30, 22), (96, 33)]:
        line(x - 2, y, x + 2, y)
        line(x, y - 2, x, y + 2)
    text('SWEET DREAMS' if goodbye else message, 55)
    # Huawei's XML uses row-major, most-significant bit first; 1 is background.
    data = bytearray()
    for row in pixels:
        for x in range(0, 128, 8):
            data.append(255 ^ sum(row[x + i] << (7 - i) for i in range(8)))
    return bytes(data)


def xml_frame(data):
    return '\n' + '\n'.join(''.join(f'0x{v:02X},' for v in data[i:i + 16])
                            for i in range(0, len(data), 16)) + '\n'


def patch_animation(text, boot, goodbye):
    import re
    for tag in ('welcome', 'fast_power_up', 'fast_power_down', 'ani_power_off'):
        pattern = rf'(<{tag}>)(.*?)(</{tag}>)'
        def replace(match):
            body = match[2]
            frame = xml_frame(boot if tag in ('welcome', 'fast_power_up') else goodbye)
            body = re.sub(r'(<frame>).*?(</frame>)',
                          lambda m: m[1] + frame + m[2], body, flags=re.S)
            return match[1] + body + match[3]
        text = re.sub(pattern, replace, text, flags=re.S)
    return text
