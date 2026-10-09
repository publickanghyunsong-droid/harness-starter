#!/usr/bin/env python3
"""test_minitoml.py — 폴백 TOML 파서의 **차등 검증(differential test)**.

3.11+ 에서는 표준 `tomllib`가 있으므로, 같은 입력을 둘 다에 먹여 **결과가 같은지**를 잰다.
표준 구현이 참값이니 우리 폴백의 정답을 따로 손으로 적을 필요가 없다.
(3.10 이하에서는 tomllib이 없어 이 비교를 건너뛴다 — 그때는 fail-closed 검사만 돈다.)

사용: python3 tests/test_minitoml.py
종료코드: 0 = 통과 / 1 = 실패
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from harness import minitoml  # noqa: E402

try:
    import tomllib
except ImportError:                     # pragma: no cover
    tomllib = None

SAMPLES = [
    # 배포 설정 자체가 첫 번째 표본이다 — 이게 안 맞으면 다른 게 맞아도 소용없다
    open(os.path.join(ROOT, "harness.toml"), encoding="utf-8").read(),
    # 문법 구석들
    """
title = "a # not comment"      # 진짜 주석
n = 42
f = -1.5e3
yes = true
arr = [1, 2, 3]
multi = [
  "a",     # 배열 안 주석
  "b",
]
nested = [[1, 2], [3]]
lit = 'C:\\raw\\path'
esc = "tab\\there"

[a.b]
k = "v"

[[items]]
name = "one"
[[items]]
name = "two"
""",
]

BAD = [
    ('x = 2026-08-02', "날짜"),
    ('x = {a = 1}', "인라인 테이블"),
    ('x = """여러 줄"""', "여러 줄 문자열"),
    ('[unclosed', "닫히지 않은 테이블"),
    ('novalue', "= 없는 줄"),
    ('a = "x"\na = "y"', "키 중복"),
    ('arr = [1, 2', "닫히지 않은 배열"),
]


def main():
    fails = []
    oks = []
    if tomllib:
        for i, text in enumerate(SAMPLES):
            ref = tomllib.loads(text)
            got = minitoml.loads(text)
            if ref != got:
                fails.append("표본 %d 불일치\n  ref=%r\n  got=%r" % (i, ref, got))
            else:
                print("  ok   표본 %d 는 tomllib 와 일치 (키 %d개)" % (i, len(ref)))
                oks.append(1)
    else:
        print("  --   tomllib 없음(3.10 이하) → 차등 비교 생략")

    # ★fail-closed: 모르는 문법을 조용히 흘리면 게이트가 꺼진 줄 모르고 통과한다
    for text, what in BAD:
        try:
            minitoml.loads(text)
        except minitoml.TomlSubsetError:
            print("  ok   %s 에서 예외가 났다" % what)
            oks.append(1)
        except Exception as e:                      # noqa: BLE001
            fails.append("%s: TomlSubsetError 가 아닌 예외 %r" % (what, e))
        else:
            fails.append("%s: 조용히 통과했다(조용한 무시 = 최악)" % what)

    print()
    if fails:
        print("결과: FAIL %d" % len(fails))
        for f in fails:
            print("  - %s" % f)
        return 1
    # ★수를 찍는다(2026-08-23). 이 절만 숫자 없이 "전부 통과"라 총합을 셀 수 없었고,
    #   에이전트가 그 빈자리를 지어 메우다 총합을 틀렸다(first-reader-log 4회차).
    print("결과: PASS %d · FAIL 0" % len(oks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
