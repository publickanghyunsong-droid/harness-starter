#!/usr/bin/env python3
"""score_canaries.py — 규약 카나리 **채점기**(2단계).

카나리 = 규약이 *문서에 있다*가 아니라 *실제로 발효됐다*를 재는 테스트 작업.
  총괄 세션이 `canaries.json`의 상황을 **서브에이전트**에 던지고(신선한 컨텍스트라야
  시험이 된다 — 이미 규약을 읽은 자기 자신에게 물으면 시험이 아니라 복창이다),
  받은 답을 파일로 떨어뜨린 뒤 이 스크립트로 채점한다.
  ★사람이 읽고 판정하지 않는다 — 정규식이 먼저다(검증 순서 = 코드 → 기계 → 사람 눈).

사용:
  1) 각 카나리 응답을 <dir>/<카나리ID>.txt 로 저장
  2) python3 -m harness.score_canaries <dir> [--spec canaries.json] [--report <경로>]
종료코드: 0 = 절반 이상 통과 / 1 = 절반 이상 실패(규약이 안 걸리고 있다) / 2 = 명세 없음

★FAIL의 뜻 = *에이전트가 못났다*가 아니라 **그 규약이 부트스트랩만으로는 안 걸린다**.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import config as hconfig   # noqa: E402

# 명세 키는 영문이 정본. 한글 키(기대/금지/규약/프롬프트)도 읽어준다 —
# 기존 자산을 옮겨올 때 파일을 통째로 다시 쓰게 만들지 않으려는 것뿐이다.
_ALIAS = {"expect": "기대", "forbid": "금지", "rule": "규약", "prompt": "프롬프트"}


def field(c, key, default=None):
    if key in c:
        return c[key]
    alias = _ALIAS.get(key)
    if alias and alias in c:
        return c[alias]
    return default


def locate_spec(explicit, cfg):
    for cand in (explicit,
                 cfg.get("canaries.spec") and cfg.path_of(cfg.get("canaries.spec")),
                 os.path.join(cfg.config_dir, "canaries.json"),
                 os.path.join(cfg.root, "canaries.json")):
        if cand and os.path.exists(os.path.expanduser(cand)):
            return os.path.expanduser(cand)
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="카나리 채점(2단계)")
    ap.add_argument("answers_dir", help="카나리 응답 .txt 들이 있는 폴더")
    ap.add_argument("--spec", default=None)
    ap.add_argument("--config", default=None)
    ap.add_argument("--report", default=None)
    args = ap.parse_args(argv)

    try:
        cfg = hconfig.load(args.config)
    except hconfig.ConfigError as e:
        sys.stderr.write("설정 오류: %s\n" % e)
        return 2
    spec = locate_spec(args.spec, cfg)
    if not spec:
        sys.stderr.write("카나리 명세(canaries.json)를 찾지 못했다. --spec 으로 지정하라.\n")
        return 2
    with open(spec, encoding="utf-8") as fh:
        canaries = json.load(fh)["canaries"]

    rows = []
    for c in canaries:
        path = os.path.join(args.answers_dir, c["id"] + ".txt")
        if not os.path.exists(path):
            rows.append((c, "MISS", "응답 파일 없음: %s" % os.path.basename(path), ""))
            continue
        with open(path, encoding="utf-8", errors="replace") as fh:
            out = fh.read()
        missed = [p for p in field(c, "expect", []) if not re.search(p, out, re.I)]
        bad = [p for p in field(c, "forbid", []) if re.search(p, out, re.I)]
        if not missed and not bad:
            rows.append((c, "PASS", "", out))
        else:
            note = ("미검출: " + " / ".join(missed) if missed else "") + \
                   (" · 금지어 등장: " + ", ".join(bad) if bad else "")
            rows.append((c, "FAIL", note, out))

    n_pass = sum(1 for _, v, _, _ in rows if v == "PASS")
    n_fail = sum(1 for _, v, _, _ in rows if v == "FAIL")
    n_miss = sum(1 for _, v, _, _ in rows if v == "MISS")

    lines = [
        "---", "type: report", "date: %s" % datetime.now().strftime("%Y-%m-%d"),
        "status: active", "---", "",
        "# 규약 카나리 — %s" % datetime.now().strftime("%Y-%m-%d %H:%M"), "",
        "> 하네스 점검 루틴 **2단계**. 명세 = `%s`" % os.path.basename(spec), "",
        "**결과: PASS %d · FAIL %d · 미실시 %d**" % (n_pass, n_fail, n_miss), "",
        "| 결과 | 카나리 | 대상 규약 | 비고 |", "|---|---|---|---|",
    ]
    for c, v, note, _ in rows:
        mark = {"PASS": "[PASS]", "FAIL": "[FAIL]", "MISS": "[skip]"}[v]
        lines.append("| %s | `%s` | %s | %s |" % (
            mark, c["id"], str(field(c, "rule", "")).replace("|", "\\|"),
            note.replace("|", "\\|")))
    lines += [
        "", "> ★FAIL은 *에이전트가 못났다*가 아니라 **그 규약이 부트스트랩만으로는 안 걸린다**는 신호다.",
        "> 조치 후보: ①규약을 부트스트랩 문서(항상 읽히는 자리)로 끌어올린다 "
        "②맥락이 아니라 **행위**로 다시 쓴다 ③기대 정규식이 과했는지 본다(위양성).", "",
        "## 응답 원문", "",
    ]
    for c, v, _, out in rows:
        if not out:
            continue
        lines += ["<details><summary>%s (%s)</summary>" % (c["id"], v), "", "```",
                  out.strip()[:3000], "```", "", "</details>", ""]
    report = "\n".join(lines) + "\n"

    if args.report:
        path = cfg.path_of(args.report)
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(report)
    print(report)
    scored = n_pass + n_fail
    return 1 if (scored and n_fail * 2 >= scored) else 0


if __name__ == "__main__":
    sys.exit(main())
