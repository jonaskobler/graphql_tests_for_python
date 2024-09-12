import ast
import re
import string
import sys
import traceback
from typing import Match

import pytest


LINENO_AT_START = sys.version_info >= (3, 8)


def nth_line(src: str, lineno: int) -> int:
    """
    Compute the starting index of the n-th line (where n is 1-indexed)

    >>> nth_line("aaa\\nbb\\nc", 2)
    4
    """
    assert lineno >= 1
    pos = 0
    for _ in range(lineno - 1):
        pos = src.find("\n", pos) + 1
    return pos


def nth_eol(src: str, lineno: int) -> int:
    """
    Compute the ending index of the n-th line (before the newline,
    where n is 1-indexed)

    >>> nth_eol("aaa\\nbb\\nc", 2)
    6
    """
    assert lineno >= 1
    pos = -1
    for _ in range(lineno):
        pos = src.find("\n", pos + 1)
        if pos == -1:
            return len(src)
    return pos


def normalize_nl(t: str) -> str:
    return t.replace("\r\n", "\n").replace("\r", "\n")


def escape_trailing_quote(s: str, quote: str) -> str:
    if s and s[-1] == quote:
        return s[:-1] + "\\" + quote
    else:
        return s


class EditHistory:
    state: dict[str, list[tuple[int, int]]]

    def __init__(self) -> None:
        self.state = {}

    def adjust_lineno(self, fn: str, lineno: int) -> int:
        if fn not in self.state:
            return lineno
        for edit_loc, edit_diff in self.state[fn]:
            if lineno > edit_loc:
                lineno += edit_diff
        return lineno

    def seen_file(self, fn: str) -> bool:
        return fn in self.state

    def record_edit(self, fn: str, lineno: int, delta: int) -> None:
        self.state.setdefault(fn, []).append((lineno, delta))


EDIT_HISTORY = EditHistory()


def ok_for_raw_triple_quoted_string(s: str, quote: str) -> bool:
    """
    Is this string representable inside a raw triple-quoted string?
    Due to the fact that backslashes are always treated literally,
    some strings are not representable.

    >>> ok_for_raw_triple_quoted_string("blah", quote="'")
    True
    >>> ok_for_raw_triple_quoted_string("'", quote="'")
    False
    >>> ok_for_raw_triple_quoted_string("a ''' b", quote="'")
    False
    """
    return quote * 3 not in s and (not s or s[-1] not in [quote, "\\"])


RE_EXPECT = re.compile(
    (r"(?P<raw>r?)" r"(?P<quote>'''|" r'""")' r"(?P<body>.*?)" r"(?P=quote)"), re.DOTALL
)


def replace_string_literal(
    src: str, start_lineno: int, end_lineno: int, new_string: str
) -> tuple[str, int]:
    r"""
    Replace a triple quoted string literal with new contents.
    Only handles printable ASCII correctly at the moment.  This
    will preserve the quote style of the original string, and
    makes a best effort to preserve raw-ness (unless it is impossible
    to do so.)

    Returns a tuple of the replaced string, as well as a delta of
    number of lines added/removed.

    >>> replace_string_literal("'''arf'''", 1, 1, "barf")
    ("'''barf'''", 0)
    >>> r = replace_string_literal("  moo = '''arf'''", 1, 1, "'a'\n\\b\n")
    >>> print(r[0])
      moo = '''\
    'a'
    \\b
    '''
    >>> r[1]
    3
    >>> replace_string_literal("  moo = '''\\\narf'''", 1, 2, "'a'\n\\b\n")[1]
    2
    >>> print(replace_string_literal("    f('''\"\"\"''')", 1, 1, "a ''' b")[0])
        f('''a \'\'\' b''')
    """
    # Haven't implemented correct escaping for non-printable characters
    assert all(c in string.printable for c in new_string), repr(new_string)

    new_string = normalize_nl(new_string)

    delta = [new_string.count("\n")]
    if delta[0] > 0:
        delta[0] += 1  # handle the extra \\\n

    assert start_lineno <= end_lineno
    start = nth_line(src, start_lineno)
    end = nth_eol(src, end_lineno)
    assert start <= end

    def replace(m: Match[str]) -> str:
        s = new_string
        raw = m.group("raw") == "r"
        if not raw or not ok_for_raw_triple_quoted_string(s, quote=m.group("quote")[0]):
            raw = False
            s = s.replace("\\", "\\\\")
            if m.group("quote") == "'''":
                s = escape_trailing_quote(s, "'").replace("'''", r"\'\'\'")
            else:
                s = escape_trailing_quote(s, '"').replace('"""', r"\"\"\"")

        new_body = "\\\n" + s if "\n" in s and not raw else s
        delta[0] -= m.group("body").count("\n")
        return "".join(
            [
                "r" if raw else "",
                m.group("quote"),
                new_body,
                m.group("quote"),
            ]
        )

    return (
        src[:start] + RE_EXPECT.sub(replace, src[start:end], count=1) + src[end:],
        delta[0],
    )


def replace_many(rep: dict[str, str], text: str) -> str:
    rep = {re.escape(k): v for k, v in rep.items()}
    pattern = re.compile("|".join(rep.keys()))
    return pattern.sub(lambda m: rep[re.escape(m.group(0))], text)


@pytest.fixture
def expect(capsys):
    def f(expected, debug=False):
        actual, _ = capsys.readouterr()
        if debug:
            if expected != actual:
                tb = traceback.extract_stack(limit=2)
                fn, lineno, _, _ = tb[0]
                with open(fn, "r+") as f:
                    old = f.read()
                    old_ast = ast.parse(old)

                    # NB: it's only the traceback line numbers that are wrong;
                    # we reread the file every time we write to it, so AST's
                    # line numbers are correct
                    lineno = EDIT_HISTORY.adjust_lineno(fn, lineno)

                    # Conservative assumption to start
                    start_lineno = lineno
                    end_lineno = lineno
                    # Try to give a more accurate bounds based on AST
                    # NB: this walk is in no specified order (in practice it's
                    # breadth first)
                    for n in ast.walk(old_ast):
                        if isinstance(n, ast.Expr):
                            if hasattr(n, "end_lineno"):
                                assert LINENO_AT_START
                                if n.lineno == start_lineno:
                                    # type: ignore[attr-defined]
                                    end_lineno = n.end_lineno
                            else:
                                if n.lineno == end_lineno:
                                    start_lineno = n.lineno

                    new, delta = replace_string_literal(
                        old, start_lineno, end_lineno, actual
                    )

                    assert old != new, (
                        f"Failed to substitute string at {fn}:{lineno}; did you use triple quotes?  "
                        "If this is unexpected, please report it "
                        f"with the contents of the source file near {fn}:{lineno}"
                    )

                    f.seek(0)
                    f.truncate(0)

                    f.write(new)

                EDIT_HISTORY.record_edit(fn, lineno, delta)
        else:
            assert expected == actual

    return f
