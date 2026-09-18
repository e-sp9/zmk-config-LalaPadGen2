#!/usr/bin/env python3
"""Generate README keymap SVGs from this repository's ZMK configuration.

Uses only the Python standard library; --check never modifies files.
Unsupported behaviors retain their source spelling rather than disappearing.
"""

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
START, END = '<!-- keymap:start -->', '<!-- keymap:end -->'
ALIASES = {
    'LCTRL': 'Ctrl', 'LEFT_CONTROL': 'Ctrl', 'LWIN': 'Cmd', 'LGUI': 'Cmd',
    'LEFT_GUI': 'Cmd', 'LEFT_WIN': 'Cmd', 'LEFT_COMMAND': 'Cmd',
    'LEFT_ALT': 'Alt', 'LEFT_SHIFT': 'Shift', 'SPACE': 'Space', 'ENTER': 'Enter',
    'BACKSPACE': 'BS', 'ESCAPE': 'Esc', 'TAB': 'Tab', 'DEL': 'Del',
    'LANGUAGE_1': 'かな', 'LANGUAGE_2': '英数', 'EQUAL': '=', 'MINUS': '−',
    'COMMA': ',', 'PERIOD': '.', 'SLASH': '/', 'BACKSLASH': '\\',
    'EXCLAMATION': '!', 'AT_SIGN': '@', 'HASH': '#', 'DOLLAR': '$',
    'PERCENT': '%', 'CARET': '^', 'AMPERSAND': '&', 'ASTERISK': '*',
    'LEFT_PARENTHESIS': '(', 'RIGHT_PARENTHESIS': ')', 'GRAVE': '`',
    'SQT': "'", 'SEMI': ';', 'LEFT_BRACKET': '[', 'RIGHT_BRACKET': ']',
    'PAGE_UP': 'PgUp', 'PAGE_DOWN': 'PgDn', 'HOME': 'Home', 'END': 'End',
    'UP': '↑', 'UP_ARROW': '↑', 'DOWN': '↓', 'DOWN_ARROW': '↓',
    'LEFT': '←', 'RIGHT': '→', 'PRINTSCREEN': 'PrtSc', 'SCROLLLOCK': 'ScrLk',
    'PAUSE_BREAK': 'Pause', 'KP_NUMLOCK': 'Num Lock', 'KP_PLUS': 'Num +',
    'KP_MINUS': 'Num −', 'KP_ASTERISK': 'Num *', 'KP_DIVIDE': 'Num /',
    'KP_DOT': 'Num .', 'LCLK': '左クリック', 'RCLK': '右クリック',
    'MCLK': '中クリック', 'MB4': '戻る', 'MB5': '進む',
}


def key_label(code):
    modifier = re.fullmatch(r'(LC|LG|LS|LA)\((.*)\)', code)
    if modifier:
        return {'LC': 'Ctrl', 'LG': 'Cmd', 'LS': 'Shift', 'LA': 'Alt'}[modifier[1]] + '+' + key_label(modifier[2])
    if code in ALIASES:
        return ALIASES[code]
    return re.sub(r'^KP_NUMBER_', 'Num ', re.sub(r'^(NUMBER_|N)(?=\d+$)', '', code))


def binding_label(binding):
    behavior, *args = binding.split()
    if behavior in ('&kp', '&mkp'):
        return key_label(args[0]), ''
    if behavior == '&none':
        return '—', ''
    if behavior == '&trans':
        return '▽', ''
    if behavior in ('&lt', '&mt', '&mt2'):
        return key_label(args[1]), 'hold: ' + ('L' + args[0] if behavior == '&lt' else key_label(args[0]))
    if behavior in ('&mo', '&to', '&tog'):
        return {'&mo': 'Hold', '&to': 'To', '&tog': 'Toggle'}[behavior] + ' L' + args[0], ''
    if behavior == '&bt':
        return ({'BT_SEL': 'BT ' + (str(int(args[1]) + 1) if len(args) > 1 else '?'),
                 'BT_CLR': 'BT消去', 'BT_CLR_ALL': 'BT全消去'}.get(args[0], ' '.join(args)), '')
    if behavior == '&out':
        return '出力切替' if args == ['OUT_TOG'] else ' '.join(args), ''
    if behavior in ('&sys_reset', '&bootloader'):
        return ('再起動' if behavior == '&sys_reset' else '書込モード'), ''
    if behavior == '&zip_dyn_scale':
        group = {'ZDS_XY': '移動', 'ZDS_SC': 'スクロール', 'ZDS_ALL': '全倍率'}[args[0]]
        return group + {'ZDS_INC': '+', 'ZDS_DEC': '−', 'ZDS_RST': '初期化'}[args[1]], ''
    return binding, ''


def cells(body, name):
    match = re.search(r'\b' + re.escape(name) + r'\s*=\s*<([^>]*)>;', body, re.S)
    return match[1].split() if match else []


def bindings(body):
    match = re.search(r'\bbindings\s*=\s*<(.*?)>;', body, re.S)
    if not match:
        raise ValueError('Missing bindings')
    return [b.strip() for b in re.findall(r'&[^&]+', match[1])]


def parse_keymap(source):
    source = re.sub(r'/\*.*?\*/|//[^\n]*', '', source, flags=re.S)
    defines = dict(re.findall(r'^#define\s+(\w+)\s+(\d+)\s*$', source, re.M))
    layers = []
    for node, name, body in re.findall(r'(\w+)\s*\{\s*display-name\s*=\s*"([^"]+)";(.*?)\};', source, re.S):
        layers.append((node, name, bindings(body)))
    if not layers:
        raise ValueError('No keymap layers found')
    combos = []
    for body in re.findall(r'\w+\s*\{([^{}]*\bkey-positions\s*=.*?)\};', source, re.S):
        combos.append({
            'positions': [int(n) for n in cells(body, 'key-positions')],
            'binding': bindings(body)[0],
            'layers': [int(defines.get(n, n)) for n in cells(body, 'layers')],
        })
    return layers, combos


def svg_text(x, y, text, size=15, color='#182532', anchor='middle'):
    return f'<text x="{x:g}" y="{y:g}" text-anchor="{anchor}" font-size="{size}" fill="{color}">{html.escape(text)}</text>'


def label_lines(label, width):
    """Wrap by approximate glyph width, including full-width Japanese text."""
    lines, line, used = [], '', 0
    limit = max(2, int((width - 12) / 8))
    for character in label:
        size = 2 if unicodedata.east_asian_width(character) in ('W', 'F') else 1
        if line and used + size > limit:
            lines.append(line.strip())
            line, used = '', 0
        line += character
        used += size
    return lines + [line.strip()]


def render(index, name, layer, positions, combo_labels, digest):
    unit, margin, top = 88, 24, 98
    min_x = min(p['x'] for p in positions)
    min_y = min(p['y'] for p in positions)
    width = max(p['x'] - min_x + p.get('u', 1) for p in positions) * unit + margin * 2
    bottom = max(p['y'] - min_y + p.get('h', 1) for p in positions) * unit + top
    height = bottom + 76 + 24 * len(combo_labels)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:g}" height="{height:g}" viewBox="0 0 {width:g} {height:g}" role="img" aria-labelledby="title desc">',
           f'<title id="title">Layer {index} — {html.escape(name)}</title>',
           '<desc id="desc">全キーの割り当て。hold は長押し、▽ は下位レイヤー、— は未割り当て。</desc>',
           f'<!-- Source SHA256: {digest} -->',
           f'<rect width="{width:g}" height="{height:g}" fill="#f5f7fa"/>',
           '<g font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Noto Sans CJK JP, Hiragino Sans, sans-serif">',
           svg_text(margin, 36, f'Layer {index} · {name}', 24, anchor='start'),
           svg_text(margin, 64, 'hold: 長押し   /   ▽ 下位レイヤー   /   — 未割り当て   /   Num テンキー', 14, '#526171', 'start')]
    for binding, pos in zip(layer, positions):
        x, y = margin + (pos['x'] - min_x) * unit, top + (pos['y'] - min_y) * unit
        w, h = pos.get('u', 1) * unit - 6, pos.get('h', 1) * unit - 6
        label, hold = binding_label(binding)
        fill = '#e3efff' if hold else '#ffffff'
        if binding == '&trans':
            fill = '#edf0f4'
        svg.append(f'<g><title>{html.escape(binding)}</title><rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="7" fill="{fill}" stroke="#bcc8d5"/>')
        # Wrap unknown/long labels rather than silently cropping new behaviors.
        lines = label_lines(label, w)
        center_y = y + h / 2 - (8 if hold else 0)
        for line_index, line in enumerate(lines):
            svg.append(svg_text(x + w / 2, center_y + 5 + (line_index - (len(lines) - 1) / 2) * 17, line))
        if hold:
            svg.append(svg_text(x + w / 2, y + h - 13, hold, 12, '#345d8a'))
        svg.append('</g>')
    svg.append(svg_text(margin, bottom + 23, 'コンボ（通常レイヤー上のキー位置）', 15, anchor='start'))
    for i, label in enumerate(combo_labels):
        svg.append(svg_text(margin, bottom + 49 + i * 24, label, 15, anchor='start'))
    svg.extend(['</g>', '</svg>', ''])
    return '\n'.join(svg)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='fail if generated docs are stale')
    args = parser.parse_args()
    source = (ROOT / 'config/lalapadgen2.keymap').read_text()
    geometry = (ROOT / 'config/lalapadgen2.json').read_text()
    positions = json.loads(geometry)['layouts']['default_layout']['layout']
    layers, combos = parse_keymap(source)
    digest = hashlib.sha256((source + '\n' + geometry).encode()).hexdigest()
    outputs, section = {}, [START, '', '<!-- Generated by scripts/render_keymap.py; do not edit this section. -->', '']
    for i, (node, name, layer) in enumerate(layers):
        if len(layer) != len(positions):
            raise ValueError(f'{node}: {len(layer)} bindings for {len(positions)} positions')
        labels = []
        for combo in combos:
            if combo['layers'] and i not in combo['layers']:
                continue
            keys = ' + '.join(binding_label(layers[0][2][p])[0] for p in combo['positions'])
            labels.append(keys + ' → ' + binding_label(combo['binding'])[0])
        path = f'docs/keymap/layer-{i}.svg'
        outputs[ROOT / path] = render(i, name, layer, positions, labels, digest)
        section.extend([f'### レイヤー {i} — {name}', '', f'![レイヤー {i} のキー配置]({path})', ''])
    section.append(END)
    readme = ROOT / 'README.md'
    existing = readme.read_text()
    if existing.count(START) != 1 or existing.count(END) != 1:
        raise ValueError('README must contain exactly one keymap:start/keymap:end section')
    outputs[readme] = re.sub(re.escape(START) + '.*?' + re.escape(END), lambda _: '\n'.join(section), existing, flags=re.S)
    stale = [path for path, content in outputs.items() if not path.exists() or path.read_text() != content]
    if args.check:
        if stale:
            print('Run python3 scripts/render_keymap.py and commit the updated files:', file=sys.stderr)
            for path in stale:
                print('  ' + str(path.relative_to(ROOT)), file=sys.stderr)
            return 1
        print(f'Keymap documentation is current ({len(layers)} layers, {len(positions)} positions each).')
        return 0
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    print(f'Updated {len(layers)} keymap images and README.md.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
