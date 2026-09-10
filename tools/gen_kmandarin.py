#!/usr/bin/env python3
"""Generate kMandarin.dict.yaml: tone-marked readings for reverse lookup.

Source: Unicode Unihan (Unihan_Readings.txt), field priority per character:
  1. kTGHZ2013  - 通用规范汉字字典(2013) readings, all of them (polyphones kept)
  2. kMandarin  - most customary reading(s) (first = zh-Hans, second = zh-Hant)
Usage: python tools/gen_kmandarin.py [path/to/Unihan_Readings.txt]
       (downloads Unihan.zip from unicode.org when the file is absent)
"""
import io, os, re, sys, zipfile, urllib.request, datetime

UNIHAN_URL = 'https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'kMandarin.dict.yaml')


def load_readings(path):
    if path and os.path.exists(path):
        return io.open(path, encoding='utf-8').read().splitlines()
    tmp = os.path.join(os.environ.get('TEMP') or '/tmp', 'Unihan.zip')
    if not os.path.exists(tmp):
        urllib.request.urlretrieve(UNIHAN_URL, tmp)
    with zipfile.ZipFile(tmp) as z:
        return z.read('Unihan_Readings.txt').decode('utf-8').splitlines()


def main():
    lines = load_readings(sys.argv[1] if len(sys.argv) > 1 else None)
    tghz, mandarin, version = {}, {}, ''
    for ln in lines:
        if ln.startswith('#'):
            m = re.match(r'#\s*Unihan_Readings-([0-9.]+)\.txt', ln)
            if m:
                version = m.group(1)
            continue
        parts = ln.split('\t')
        if len(parts) != 3:
            continue
        cp, field, value = parts
        ch = chr(int(cp[2:], 16))
        if field == 'kTGHZ2013':
            # "482.140:zhòu 220.750:hào" -> readings in dictionary order, dedup
            rs = []
            for tok in value.split():
                r = tok.split(':', 1)[-1]
                if r not in rs:
                    rs.append(r)
            tghz[ch] = rs
        elif field == 'kMandarin':
            rs = []
            for r in value.split():
                if r not in rs:
                    rs.append(r)
            mandarin[ch] = rs
    entries = []
    for ch in sorted(set(tghz) | set(mandarin)):
        for r in (tghz.get(ch) or mandarin[ch]):
            entries.append((ch, r))
    today = datetime.date.today().isoformat()
    head = (
        '# Rime dictionary\n'
        '# encoding: utf-8\n'
        '#\n'
        '# 汉字带声调注音，仅供反查注音（radical_reverse_lookup）使用，不参与输入。\n'
        '# 数据来源：Unicode Unihan Database' + (' ' + version if version else '') + '（Unicode License）\n'
        '#   kTGHZ2013 优先（《通用规范汉字字典》读音，多音字全部保留），其余取 kMandarin。\n'
        '# 由 tools/gen_kmandarin.py 生成，请勿手改。\n'
        '\n---\nname: kMandarin\nversion: "' + today + '"\nsort: original\n'
        'columns:\n  - text\n  - code\n...\n\n'
    )
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(head)
        for ch, r in entries:
            f.write(ch + '\t' + r + '\n')
    print('chars: %d (kTGHZ2013 %d, kMandarin-only %d), entries: %d -> %s' % (
        len(set(tghz) | set(mandarin)), len(tghz), len(set(mandarin) - set(tghz)), len(entries), OUT))


if __name__ == '__main__':
    main()
