"""minitoml — TOML **부분집합** 파서 (의존성 0, Python 3.6+).

★왜 이게 있나 (지우기 전에 읽을 것)
  설정을 TOML로 쓰기로 한 이유는 **주석이 들어가기 때문**이다(JSON은 못 넣는다).
  이 하네스의 설정 파일은 "왜 이 값인가"를 옆에 적어두는 것이 본체의 절반이라
  주석 없는 포맷은 후보가 아니었다.
  그런데 표준 `tomllib`는 **Python 3.11+**이고, macOS 26.5의 시스템 파이썬은
  아직 3.9.6이다(실측: `/usr/bin/python3 -V` → 3.9.6).
  "빈 프로젝트에서 그대로 돈다"를 약속하려면 3.9에서도 떠야 하므로 폴백을 둔다.

  우선순위: tomllib(표준) → tomli(설치돼 있으면) → **이 파서**.
  즉 3.11+ 사용자는 이 코드를 아예 타지 않는다.

★설계 원칙 = fail-closed
  지원하지 않는 문법을 만나면 **조용히 무시하지 않고 예외를 던진다.**
  설정 파서가 조용히 한 줄을 흘리면 게이트가 꺼진 줄 모르고 통과한다.
  (설정을 못 읽는 것보다 나쁜 것은 "일부만 읽고 다 읽은 척"하는 것이다.)

지원: [table] · [[array of tables]] · 점 표기 테이블명 · 주석 · 문자열("", '')
      · 정수 · 실수 · bool · 배열(중첩·여러 줄)
미지원(=예외): 여러 줄 문자열(삼중따옴표), 날짜/시각, 인라인 테이블({}), 점 표기 *키*
"""
import re

__all__ = ["loads", "load", "TomlSubsetError"]


class TomlSubsetError(ValueError):
    """이 파서가 다루지 않는 문법. 조용히 넘기지 않는다."""


def _scan(s):
    """따옴표 상태를 추적하며 (문자, 문자열안인가) 를 흘린다."""
    quote = None
    esc = False
    for ch in s:
        if quote:
            yield ch, True
            if esc:
                esc = False
            elif ch == "\\" and quote == '"':
                esc = True
            elif ch == quote:
                quote = None
        else:
            if ch in "\"'":
                quote = ch
                yield ch, True
            else:
                yield ch, False


def _strip_comment(line):
    out = []
    for ch, in_str in _scan(line):
        if ch == "#" and not in_str:
            break
        out.append(ch)
    return "".join(out)


def _balance(s):
    depth = 0
    for ch, in_str in _scan(s):
        if in_str:
            continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
    return depth


def _split_top(s, sep=","):
    """최상위 레벨에서만 자른다(따옴표·괄호 안의 구분자는 무시)."""
    parts, buf, depth = [], [], 0
    for ch, in_str in _scan(s):
        if not in_str:
            if ch in "[{":
                depth += 1
            elif ch in "]}":
                depth -= 1
            elif ch == sep and depth == 0:
                parts.append("".join(buf))
                buf = []
                continue
        buf.append(ch)
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


_INT = re.compile(r"^[+-]?\d[\d_]*$")
_FLOAT = re.compile(r"^[+-]?(\d[\d_]*)?\.\d[\d_]*([eE][+-]?\d+)?$|^[+-]?\d[\d_]*[eE][+-]?\d+$")
_ESC = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}


def _parse_string(v):
    body = v[1:-1]
    if v[0] == "'":            # literal string — 이스케이프 없음
        return body
    out, i = [], 0
    while i < len(body):
        ch = body[i]
        if ch == "\\":
            if i + 1 >= len(body):
                raise TomlSubsetError("문자열 끝의 역슬래시: %s" % v)
            nxt = body[i + 1]
            if nxt not in _ESC:
                raise TomlSubsetError("지원하지 않는 이스케이프 \\%s (%s)" % (nxt, v))
            out.append(_ESC[nxt])
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _parse_value(v):
    v = v.strip()
    if not v:
        raise TomlSubsetError("값이 비어 있다")
    if v.startswith('"""') or v.startswith("'''"):
        raise TomlSubsetError("여러 줄 문자열은 지원하지 않는다. 한 줄로 쓰거나 tomllib(3.11+)를 쓸 것")
    if v.startswith("{"):
        raise TomlSubsetError("인라인 테이블 {..} 은 지원하지 않는다. [table] 로 풀어 쓸 것")
    if v[0] in "\"'":
        if len(v) < 2 or v[-1] != v[0]:
            raise TomlSubsetError("따옴표가 닫히지 않았다: %s" % v)
        return _parse_string(v)
    if v.startswith("["):
        if not v.endswith("]"):
            raise TomlSubsetError("배열이 닫히지 않았다: %s" % v)
        return [_parse_value(x) for x in _split_top(v[1:-1])]
    if v in ("true", "false"):
        return v == "true"
    if _INT.match(v):
        return int(v.replace("_", ""))
    if _FLOAT.match(v):
        return float(v.replace("_", ""))
    raise TomlSubsetError("해석할 수 없는 값: %r (날짜·인라인테이블 등은 미지원)" % v)


def _split_key(name):
    parts, buf = [], []
    for ch, in_str in _scan(name):
        if ch == "." and not in_str:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            raise TomlSubsetError("빈 키 조각: %s" % name)
        if p[0] in "\"'":
            p = _parse_string(p)
        out.append(p)
    return out


def _descend(root, path, array_last=False):
    node = root
    for p in path[:-1]:
        node = node.setdefault(p, {})
        if isinstance(node, list):     # [[a]] 뒤의 [a.b] → 마지막 원소로
            node = node[-1]
        if not isinstance(node, dict):
            raise TomlSubsetError("테이블 경로 충돌: %s" % ".".join(path))
    last = path[-1]
    if array_last:
        arr = node.setdefault(last, [])
        if not isinstance(arr, list):
            raise TomlSubsetError("[[%s]] 가 테이블과 충돌" % ".".join(path))
        arr.append({})
        return arr[-1]
    node = node.setdefault(last, {})
    if isinstance(node, list):
        node = node[-1]
    if not isinstance(node, dict):
        raise TomlSubsetError("테이블 경로 충돌: %s" % ".".join(path))
    return node


def loads(text):
    root = {}
    cur = root
    lines = text.splitlines()
    i, n = 0, len(lines)
    while i < n:
        raw = lines[i]
        i += 1
        line = _strip_comment(raw).strip()
        if not line:
            continue
        if line.startswith("[["):
            if not line.endswith("]]"):
                raise TomlSubsetError("%d행: [[..]] 가 닫히지 않았다" % i)
            cur = _descend(root, _split_key(line[2:-2]), array_last=True)
            continue
        if line.startswith("["):
            if not line.endswith("]"):
                raise TomlSubsetError("%d행: [..] 가 닫히지 않았다" % i)
            cur = _descend(root, _split_key(line[1:-1]))
            continue
        if "=" not in line:
            raise TomlSubsetError("%d행: key = value 형태가 아니다: %r" % (i, line))
        k, v = line.split("=", 1)
        # 여러 줄 배열 이어붙이기
        while _balance(v) > 0:
            if i >= n:
                raise TomlSubsetError("배열이 파일 끝까지 닫히지 않았다")
            v += " " + _strip_comment(lines[i]).strip()
            i += 1
        key = _split_key(k)
        if len(key) != 1:
            raise TomlSubsetError("점 표기 *키*는 미지원(테이블명은 가능): %s" % k.strip())
        if key[0] in cur:
            raise TomlSubsetError("키 중복: %s" % key[0])
        cur[key[0]] = _parse_value(v)
    return root


def load(fh):
    data = fh.read()
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return loads(data)
