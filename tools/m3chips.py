"""Draws the README's Material 3 buttons and chips into assets/m3, styled after sc.is-a.dev ("default" palette).

    python tools/m3chips.py            # everything
    python tools/m3chips.py counters   # only the live counter chips (what the scheduled workflow runs)

Needs fonttools. Text is drawn as outlines because a README image cannot load fonts.
Google Sans Flex: SIL OFL 1.1 (tools/m3/fonts/OFL.txt). Material Symbols: Apache 2.0.
"""
import json, os, re, sys, urllib.request
from xml.dom import minidom
from xml.sax.saxutils import escape, quoteattr
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, 'm3')
OUT = os.path.join(HERE, '..', 'assets', 'm3')


class Font:
    def __init__(self, path, key):
        self.f, self.key = TTFont(path), key
        self.upm = self.f['head'].unitsPerEm
        self.cmap, self.gs, self.hmtx = self.f.getBestCmap(), self.f.getGlyphSet(), self.f['hmtx']
        self.pairs = {}
        for lookup in self.f['GPOS'].table.LookupList.Lookup if 'GPOS' in self.f else []:
            for st in lookup.SubTable:
                st = st.ExtSubTable if lookup.LookupType == 9 else st
                if type(st).__name__ != 'PairPos':
                    continue
                cov = st.Coverage.glyphs
                if st.Format == 1:
                    for i, a in enumerate(cov):
                        for r in st.PairSet[i].PairValueRecord:
                            v = getattr(r.Value1, 'XAdvance', 0) if r.Value1 else 0
                            if v:
                                self.pairs.setdefault((a, r.SecondGlyph), v)
                else:
                    by_class = {}
                    for g, c in st.ClassDef2.classDefs.items():
                        by_class.setdefault(c, []).append(g)
                    for a in cov:
                        rec = st.Class1Record[st.ClassDef1.classDefs.get(a, 0)]
                        for c, gl in by_class.items():
                            v1 = rec.Class2Record[c].Value1
                            v = getattr(v1, 'XAdvance', 0) if v1 else 0
                            for b in gl if v else []:
                                self.pairs.setdefault((a, b), v)

    def layout(self, s, size):
        names = [self.cmap[ord(ch)] for ch in s]
        xs, x = [], 0
        for i, n in enumerate(names):
            xs.append(x)
            x += self.hmtx[n][0] + (self.pairs.get((n, names[i + 1]), 0) if i + 1 < len(names) else 0)
        return names, xs, x * size / self.upm

    def path(self, name):
        pen = SVGPathPen(self.gs, ntos=lambda v: str(round(v)))
        self.gs[name].draw(TransformPen(pen, (1, 0, 0, -1, 0, 0)))
        return pen.getCommands()


REG = Font(os.path.join(RES, 'fonts', 'gsf-400.ttf'), 'r')
MED = Font(os.path.join(RES, 'fonts', 'gsf-500.ttf'), 'm')


class Doc:
    def __init__(self, w, h, title):
        self.w, self.h, self.title, self.defs, self.body, self.glyphs = w, h, title, [], [], {}

    def text(self, s, x, y, size, font, fill):
        names, xs, width = font.layout(s, size)
        uses = []
        for n, gx in zip(names, xs):
            if (font.key, n) not in self.glyphs:
                d = font.path(n)
                self.glyphs[font.key, n] = f'{font.key}{len(self.glyphs)}' if d else None
                if d:
                    self.defs.append(f'<path id="{self.glyphs[font.key, n]}" d="{d}"/>')
            if self.glyphs[font.key, n]:
                uses.append(f'<use href="#{self.glyphs[font.key, n]}" x="{round(gx)}"/>')
        self.body.append(f'<g fill="{fill}" transform="translate({x:.1f} {y:.1f}) scale({size / font.upm:.5f})">{"".join(uses)}</g>')
        return width

    def icon(self, name, x, y, size, fill):
        with open(os.path.join(RES, 'icons', f'{name}.svg'), encoding='utf-8') as f:
            d = re.search(r' d="([^"]+)"', f.read()).group(1)
        self.body.append(f'<path fill="{fill}" transform="translate({x:.1f} {y + size:.1f}) scale({size / 960:.5f})" d="{d}"/>')

    def save(self, name, theme):
        w, h = round(self.w), round(self.h)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
               f'aria-label={quoteattr(self.title)}><title>{escape(self.title)}</title><defs>{"".join(self.defs)}</defs>{"".join(self.body)}</svg>\n')
        path = os.path.join(OUT, f'{name}-{theme}.svg')
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(svg)
        minidom.parse(path)  # self-check: a broken image would show as a dead link on the profile


# .btn on the site: 40px pill, 18px icon, 500 14.72px label. (bg, fg) per theme.
BUTTONS = [
    ('btn-profile', 'public', 'sc.is-a.dev', {'dark': ('#ffb4a1', '#561f10'), 'light': ('#8f4b39', '#ffffff')}),
    ('btn-portfolio', 'web', 'swar.is-a.dev', {'dark': ('#3e3a3b', '#e8e1e1'), 'light': ('#e8e1e1', '#1e1b1b')}),
    ('btn-hackathons', 'emoji_events', 'hackathon logbook', {'dark': ('#534519', '#f7e1a6'), 'light': ('#f7e1a6', '#534519')}),
    ('btn-discord', 'forum', 'sc136', {'dark': ('#3f447d', '#aeb4f4'), 'light': ('#b7bcfe', '#444a83')}),
]
# .chip on the site: 32px, 8px radius, outline-variant border, 16px icon in primary.
SETUP = [('desktop_windows', 'windows 11'), ('code', 'vs code'), ('laptop_windows', 'asus laptop'),
         ('smartphone', 'samsung phone'), ('language', 'edge')]
CHIP = {'dark': dict(line='#4d4446', fg='#d0c3c5', accent='#ffb4a1'), 'light': dict(line='#d0c3c5', fg='#4d4446', accent='#8f4b39')}
# counter chips: icon, label, then the live value in primary (like "python 39%" on the site)
COUNTERS = {'visitors': ('visibility', 'visitors'), 'discord': ('forum', 'discord'), 'followers': ('group', 'followers')}
# section headings: the site's shape icon and a lowercase title. (bg, fg) of the shape per theme, brand-tinted like the site.
HEADS = [
    ('head-projects', 'cookie12', 'deployed_code', "what i've made", {'dark': ('#2fa54f', '#00300f'), 'light': ('#008737', '#f7fff2')}),
    ('head-stack', 'sunny8', 'terminal', 'how i code', {'dark': ('#4d8eff', '#001c46'), 'light': ('#2170e4', '#fefcff')}),
    ('head-lately', 'flower8', 'headphones', "what i'm up to", {'dark': ('#d51007', '#ffe7e3'), 'light': ('#d51007', '#ffe7e3')}),
    ('head-stats', 'soft6', 'monitoring', 'github stats', {'dark': ('#ffb4a1', '#561f10'), 'light': ('#8f4b39', '#ffffff')}),
    ('head-hangout', 'clover4', 'forum', 'come hang out', {'dark': ('#5865f2', '#fffdff'), 'light': ('#5865f2', '#fffdff')}),
]
INK = {'dark': '#e8e1e1', 'light': '#1e1b1b'}
VISITS = 'https://visitor-badge.laobi.icu/badge?page_id=SC136'
DISCORD = 'https://img.shields.io/discord/594513706055106560.json'
GITHUB = 'https://api.github.com/users/SC136'


def buttons():
    for name, ic, label, colors in BUTTONS:
        for theme, (bg, fg) in colors.items():
            w = 16 + 18 + 8 + MED.layout(label, 14.72)[2] + 20
            doc = Doc(w, 40, label)
            doc.body.append(f'<rect width="{round(w)}" height="40" rx="20" fill="{bg}"/>')
            doc.icon(ic, 16, 11, 18, fg)
            doc.text(label, 42, 25.2, 14.72, MED, fg)
            doc.save(name, theme)


def headings():
    with open(os.path.join(RES, 'shapes.json'), encoding='utf-8') as f:
        shapes = json.load(f)  # the site's --shape-* polygons, as percentages
    for name, shape, ic, title, colors in HEADS:
        for theme, (bg, fg) in colors.items():
            doc = Doc(52 + MED.layout(title, 24)[2], 40, title)
            pts = 'L'.join(f'{px * .4:.1f} {py * .4:.1f}' for px, py in shapes[shape])
            doc.body.append(f'<path fill="{bg}" d="M{pts}Z"/>')
            doc.icon(ic, 10, 10, 20, fg)
            doc.text(title, 52, 28.5, 24, MED, INK[theme])
            doc.save(name, theme)


def chip(doc, x, c, ic, label, value=''):
    """One outlined chip at x; returns its width."""
    lw = REG.layout(label, 13.76)[2]
    vw = MED.layout(value, 13.76)[2] + 5 if value else 0
    w = 12 + 16 + 6 + lw + vw + 14
    doc.body.append(f'<rect x="{x + .5:.1f}" y=".5" width="{w - 1:.1f}" height="31" rx="8" fill="none" stroke="{c["line"]}"/>')
    doc.icon(ic, x + 12, 8, 16, c['accent'])
    doc.text(label, x + 34, 20.8, 13.76, REG, c['fg'])
    if value:
        doc.text(value, x + 34 + lw + 5, 20.8, 13.76, MED, c['accent'])
    return w


def setup():
    for theme, c in CHIP.items():
        doc, x = Doc(0, 32, 'setup: ' + ', '.join(label for _, label in SETUP)), 0
        for ic, label in SETUP:
            x += chip(doc, x, c, ic, label) + 8
        doc.w = x - 8
        doc.save('setup', theme)


def fetch(url):
    headers = {'User-Agent': 'SC136-readme'}
    if url.startswith('https://api.github.com') and os.environ.get('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
        return r.read().decode()


def live_counts():
    """Current numbers as text. A source that is down is left out, so its chip keeps the last image."""
    sources = {
        'visitors': lambda: format(int(re.findall(r'>(\d+)</text>', fetch(VISITS))[-1]), ','),
        'discord': lambda: re.fullmatch(r'\d+ online', json.loads(fetch(DISCORD))['message']).group(),
        'followers': lambda: format(int(json.loads(fetch(GITHUB))['followers']), ','),
    }
    out = {}
    for key, get in sources.items():
        try:
            out[key] = get()
        except Exception as e:  # network, rate limit, or an answer in a shape we do not trust
            print(f'{key}: skipped ({e})', file=sys.stderr)
    return out


def counters():
    for key, value in live_counts().items():
        ic, label = COUNTERS[key]
        for theme, c in CHIP.items():
            doc = Doc(0, 32, f'{label}: {value}')
            doc.w = chip(doc, 0, c, ic, label, value)
            doc.save(f'stat-{key}', theme)
        print(f'{key}: {value}')


if __name__ == '__main__':
    if sys.argv[1:] != ['counters']:
        buttons()
        setup()
        headings()
    counters()
