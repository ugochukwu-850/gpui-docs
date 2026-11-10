"""Check internal links and #anchors in the built site (dist/). Usage: python3 -I scripts/linkcheck.py dist"""
import os, sys
from html.parser import HTMLParser
root = sys.argv[1]
class P(HTMLParser):
    def __init__(s): super().__init__(); s.links=[]; s.ids=set()
    def handle_starttag(s, tag, attrs):
        d=dict(attrs)
        if 'id' in d: s.ids.add(d['id'])
        if tag=='a' and 'href' in d: s.links.append(d['href'])
pages={}
for dp,_,fs in os.walk(root):
    for f in fs:
        if f.endswith('.html'):
            path=os.path.join(dp,f); p=P(); p.feed(open(path,encoding='utf8').read())
            rel=os.path.relpath(dp,root)
            url='/' if rel=='.' else '/'+rel+'/'
            pages[url]=p
bad=[]
for url,p in pages.items():
    for h in set(p.links):
        if h.startswith(('http','mailto:')): continue
        if h.startswith('#'):
            if h[1:] and h[1:] not in p.ids: bad.append((url,h,'anchor missing on same page'))
            continue
        base,_,frag=h.partition('#')
        t=base if base.endswith('/') else base+'/'
        if t not in pages:
            if os.path.exists(root+base): continue
            bad.append((url,h,'page missing')); continue
        if frag and frag not in pages[t].ids: bad.append((url,h,'anchor missing'))
for b in sorted(bad): print(*b)
print(len(bad),'problems in',len(pages),'pages')
