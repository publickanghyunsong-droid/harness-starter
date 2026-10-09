#!/usr/bin/env python3
"""검토 화면(HTML)이 참조하는 그림을 파일 안으로 집어넣어 한 파일로 완결시킨다.

★왜 필요한가
검토 화면의 규칙 하나가 "파일 하나로 완결되게 짠다"는 것이다. 인터넷이 끊긴
자리에서도, 몇 년 뒤에도 열려야 검토라는 행위가 죽지 않기 때문이다. 그런데
초판 대시보드는 외부 CDN은 안 쓰면서도 그림만은 `figures/*.png` 상대경로로
참조했다. HTML 하나만 복사해 가면 그림이 전부 깨진다. 규칙은 적혀 있는데
산출물이 그 규칙을 안 지키고 있던 자리다(2026-08-23 실측).

이 스크립트는 `<img src="...png">` 와 그것을 감싼 `<a href="...png">` 를
data URI 로 바꿔 그 간극을 없앤다.

★원본 경로는 `data-src` 에 남긴다
그림을 한 번 내장하면 `src` 에는 더 이상 파일 경로가 없다. 초판 스크립트는
그래서 그림을 새로 그린 뒤 다시 돌려도 "바꿀 것이 없다"로 끝났고, 화면에는
옛 그림이 그대로 남았다. 지금은 `<img>`·`<a>` 에 `data-src="figures/…png"`
속성을 두고, 돌릴 때마다 그 경로의 파일에서 다시 내장한다. 같은 그림이면
결과가 바이트 단위로 같고, 그림 파일이 바뀌면 화면도 바뀐다. 상대경로
참조를 처음 내장할 때는 이 속성을 스스로 붙인다.

그림을 다른 이름으로 저장했다면(예: `figures/fig1_v2_mine.png`) 해당 카드의
`data-src` 두 곳(`<a>`·`<img>`)을 새 경로로 고친 뒤 다시 돌린다.

사용법
    python3 scripts/inline_figures.py dashboard.html
    python3 scripts/inline_figures.py --check dashboard.html   # 고치지 않고 검사만
    python3 scripts/inline_figures.py loop-history/dashboard-v2-reviewed.html

`--check` 는 ①남아 있는 외부 파일 참조 ②`data-src` 파일과 내장된 그림이
다른 자리(다시 담지 않아 옛 그림이 남은 곳)를 세어 하나라도 있으면 exit 1 이다.
게이트에 걸어 두면 다음 사람이 그림을 다시 바깥으로 빼거나, 새로 그리고
다시 담지 않은 것을 잡는다.
"""
import argparse
import base64
import mimetypes
import pathlib
import re
import sys

IMG_EXT = r"\.(?:png|jpg|jpeg|gif|svg|webp)"
# 그림을 담는 태그. 속성 안에 '>' 가 들어가지 않는다고 본다(base64 에는 없다).
TAG = re.compile(r"<(?P<name>img|a)\b(?P<attrs>[^>]*)>", re.IGNORECASE)
# data-src 의 'src' 를 잡지 않도록 앞이 '-'·글자가 아닌 경우만 본다.
ATTR = r'(?<![-\w])%s\s*=\s*"(?P<val>[^"]*)"'
DATA_SRC = re.compile(r'(?<![-\w])data-src\s*=\s*"(?P<val>[^"]*)"')
# 외부 파일 참조: src/href 값이 data:·http(s):·# 가 아닌 이미지 파일.
EXTERNAL = re.compile(r'(?<![-\w])(?:src|href)\s*=\s*"(?!data:|https?:|#)[^"]+%s"' % IMG_EXT,
                      re.IGNORECASE)


def _target_attr(name):
    return "src" if name.lower() == "img" else "href"


def _data_uri(path: pathlib.Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return "data:%s;base64,%s" % (mime, base64.b64encode(path.read_bytes()).decode("ascii"))


def _get(attrs, attr):
    m = re.search(ATTR % attr, attrs)
    return m.group("val") if m else None


def _set(attrs, attr, value):
    pat = re.compile(ATTR % attr)
    if pat.search(attrs):
        return pat.sub(lambda m: '%s="%s"' % (attr, value), attrs, count=1)
    return ' %s="%s"' % (attr, value) + attrs


def inline(html_path: pathlib.Path, check_only: bool = False) -> int:
    base = html_path.parent
    text = html_path.read_text(encoding="utf-8")

    # ★검사 모드는 치환을 돌리기 전에 원문에서 센다.
    #   초판은 REF.sub() 로 다 바꿔 놓고 그 결과를 세어, 고치기 전에도
    #   늘 "0건 통과"가 나왔다. 항상 통과하는 게이트는 없는 게이트보다 나쁘다
    #   (8장). 자기 검사기에서 같은 함정을 그대로 밟은 자리다(2026-08-23).
    if check_only:
        remaining = len(EXTERNAL.findall(text))
        stale, missing = [], []
        for m in TAG.finditer(text):
            attrs = m.group("attrs")
            rel = _get(attrs, "data-src")
            if not rel:
                continue
            target = (base / rel).resolve()
            if not target.is_file():
                missing.append(rel)
            elif _get(attrs, _target_attr(m.group("name"))) != _data_uri(target):
                stale.append(rel)
        rc = 0
        if remaining:
            print("%s: 바깥 파일 참조 %d건 남음 (한 파일로 완결되지 않았다)"
                  % (html_path.name, remaining), file=sys.stderr)
            rc = 1
        if missing:
            print("%s: data-src 파일이 없다 %d건: %s"
                  % (html_path.name, len(missing), ", ".join(sorted(set(missing)))), file=sys.stderr)
            rc = 1
        if stale:
            print("%s: 그림 파일과 화면 속 그림이 다르다 %d건(다시 담아야 한다): %s"
                  % (html_path.name, len(stale), ", ".join(sorted(set(stale)))), file=sys.stderr)
            rc = 1
        if rc == 0:
            print("%s: 바깥 파일 참조 0건, 내장된 그림이 원본 파일과 같다" % html_path.name)
        return rc

    misses, done, changed = [], [], []

    def repl(m):
        name, attrs = m.group("name"), m.group("attrs")
        attr = _target_attr(name)
        rel = _get(attrs, "data-src")
        if not rel:
            cur = _get(attrs, attr)
            if not cur or not re.search(IMG_EXT + "$", cur, re.IGNORECASE) \
                    or re.match(r"(?:data:|https?:|#)", cur):
                return m.group(0)
            rel = cur  # 처음 내장하는 상대경로 참조: 경로를 data-src 로 옮겨 둔다
            attrs = _set(attrs, "data-src", rel)
        target = (base / rel).resolve()
        if not target.is_file():
            misses.append(rel)
            return m.group(0)
        uri = _data_uri(target)
        if _get(attrs, attr) != uri:
            changed.append(rel)
        done.append(rel)
        return "<%s%s>" % (name, _set(attrs, attr, uri))

    new = TAG.sub(repl, text)

    if misses:
        # ★찾지 못한 참조를 조용히 넘기지 않는다. 그대로 두면 "한 파일로
        #   완결됐다"고 믿는 채로 깨진 화면이 나간다.
        print("파일이 없어 깨진 참조 %d건:" % len(misses), file=sys.stderr)
        for m in sorted(set(misses)):
            print("   %s" % m, file=sys.stderr)
        return 1

    if not done:
        print("%s: 담을 그림이 없다(data-src 도, 상대경로 그림 참조도 없다)" % html_path.name)
        return 0

    if new == text:
        print("%s: 그림 %d개 다시 내장 · 원본 파일과 이미 같아 바뀐 것 없음"
              % (html_path.name, len(set(done))))
        return 0

    before = len(text.encode("utf-8"))
    html_path.write_text(new, encoding="utf-8")
    after = len(new.encode("utf-8"))
    print("%s: 그림 %d개 다시 내장, 그중 %d개가 바뀜 (참조 %d곳) · %.1f KB → %.1f KB"
          % (html_path.name, len(set(done)), len(set(changed)), len(done), before / 1024, after / 1024))
    return 0


def main():
    ap = argparse.ArgumentParser(description="검토 화면의 그림을 파일 안으로 내장한다")
    ap.add_argument("html", nargs="+", help="대상 HTML")
    ap.add_argument("--check", action="store_true", help="고치지 않고 검사만 한다")
    args = ap.parse_args()
    rc = 0
    for p in args.html:
        rc |= inline(pathlib.Path(p), check_only=args.check)
    return rc


if __name__ == "__main__":
    sys.exit(main())
