# six 1.17.0 — Complete API Reference

> Python 2/3 compatibility layer. Single-file package (`six.py`, 1003 lines,
> 34,703 bytes). Author: Benjamin Peterson. Status for this app: **purely
> transitive, never imported by app code, inert on Python 3.14 — zero action.**

## Files

Install layout (site-packages root — note: there is **no** `six/` directory):

| Path (under `.venv/Lib/site-packages/`) | Size | Notes |
|---|---|---|
| `six.py` | 34,703 bytes, 1003 lines | The entire package. One module, stdlib-only imports (`functools`, `itertools`, `operator`, `sys`, `types` + late `struct`/`io`) |
| `six-1.17.0.dist-info/METADATA` | 1,658 bytes | Version, license, classifiers, `Requires-Python` |
| `six-1.17.0.dist-info/RECORD` | 603 bytes | 8 entries (see below) |
| `six-1.17.0.dist-info/LICENSE` | 1,066 bytes | MIT text, `Copyright (c) 2010-2024 Benjamin Peterson` |
| `six-1.17.0.dist-info/WHEEL` | 109 bytes | `Root-Is-Purelib: true`, tags `py2-none-any` / `py3-none-any` |
| `six-1.17.0.dist-info/INSTALLER` | 2 bytes | `uv` |
| `six-1.17.0.dist-info/REQUESTED` | **0 bytes (empty)** | Proof six is **not a direct dependency** — pulled in transitively |
| `six-1.17.0.dist-info/top_level.txt` | 4 bytes | `six` |

There is no `six/types.py` — on this interpreter the module self-registers the
virtual `six.moves` package via a PEP 302/451 meta-path importer
(`_SixMetaPathImporter`, appended to `sys.meta_path` at import time).

RECORD entries (8): `INSTALLER`, `LICENSE`, `METADATA`, `RECORD`,
`REQUESTED`, `WHEEL`, `top_level.txt`, `six.py` (sha256
`xRyR9wPT1LNpbJI8tf7CE-BeddkhU5O--sfy-mo5BN8`).

## Metadata

From `six-1.17.0.dist-info/METADATA`:

- **Name / Version:** `six` / `1.17.0` (`__version__ = "1.17.0"` in-module).
- **Summary:** "Python 2 and 3 compatibility utilities".
- **License:** MIT (`License: MIT`, classifier `License :: OSI Approved :: MIT License`).
- **Requires-Python:** `>=2.7, !=3.0.*, !=3.1.*, !=3.2.*` — supports Py2.7 and
  Py3.3+. Trivially satisfied by our 3.14.
- **Requires-Dist:** none — six has **zero runtime dependencies** (pins: none).
- **Classifiers:** `Development Status :: 5 - Production/Stable`; `Python :: 2`,
  `Python :: 3`; `Topic :: Software Development :: Libraries`.
- Upstream: https://github.com/benjaminp/six, docs at https://six.readthedocs.io/.

## API surface

Design: every name is a version-conditional alias so one codebase runs on
Py2 and Py3. On Python 3.14 the `PY3` branch is always taken; every `else`
(Py2) branch below is **dead code at runtime** here. `PY2 = sys.version_info[0] == 2`,
`PY3 = sys.version_info[0] == 3`, `PY34 = version >= (3, 4)`.

### Version flags and type aliases

| Name | Py3 value (live) | Py2 value (dead) | Why it exists |
|---|---|---|---|
| `PY2` / `PY3` / `PY34` | `False`/`True`/`True` | coarse version switches | coarse `if PY2:` branching in user code |
| `string_types` | `(str,)` | `(basestring,)` | `isinstance(x, six.string_types)` works for str on both |
| `text_type` | `str` | `unicode` | the "text" scalar |
| `binary_type` | `bytes` | `str` | the "bytes" scalar |
| `integer_types` | `(int,)` | `(int, long)` | Py2's `long` no longer exists |
| `class_types` | `(type,)` | `(type, types.ClassType)` | Py2 old-style classes |
| `MAXSIZE` | `sys.maxsize` | probed 32/64-bit incl. Jython path | `sys.maxint` replacement |
| `unichr` | `chr` | `unichr` | Py2 `unichr()` builtin |

### Constructors / coercion helpers

- `b(s)` — Py3: `s.encode("latin-1")`; Py2: identity. Byte literal for code
  that must run on both. Example: `six.b("hello") == b"hello"` on Py3.
- `u(s)` — Py3: identity; Py2: `unicode(s, "unicode_escape")` with a
  backslash workaround. Text literal. Example: `six.u("héllo")`.
- `ensure_binary(s, encoding='utf-8', errors='strict')` — coerce to
  `binary_type`: bytes pass through, str is encoded, anything else raises
  `TypeError`. Example: `ensure_binary("x") == b"x"`.
- `ensure_text(s, encoding='utf-8', errors='strict')` — coerce to `text_type`:
  bytes are decoded, str passes through, else `TypeError`.
- `ensure_str(s, encoding='utf-8', errors='strict')` — coerce to native `str`:
  fast-path `type(s) is str`; on Py3 decodes bytes. (On Py2 encoded unicode.)
- `byte2int(bs)` — Py3: `operator.itemgetter(0)` (indexing bytes already gives
  int); Py2: `ord(bs[0])`. `int2byte(i)` — Py3: `struct.Struct(">B").pack`;
  Py2: `chr`. `indexbytes(buf, i)` — Py3: `operator.getitem`; Py2:
  `ord(buf[i])`. `iterbytes(buf)` — Py3: `iter`; Py2:
  `functools.partial(itertools.imap, ord)`. These exist because `buf[i]`
  returns `int` on Py3 but 1-char `str` on Py2.
- `StringIO` → `io.StringIO`; `BytesIO` → `io.BytesIO` (Py2: both were
  `StringIO.StringIO`).

### Dict iteration / views

- `iterkeys(d, **kw)` → `iter(d.keys())`; `itervalues` → `iter(d.values())`;
  `iteritems` → `iter(d.items())`; `iterlists` → `iter(d.lists())` (Py2: the
  `d.iter*` methods). Py2's `d.keys()` materialized a list; these give a
  lazy iterator on both. Example: `for k, v in six.iteritems(d): ...`.
- `viewkeys` / `viewvalues` / `viewitems` = `operator.methodcaller("keys" /
  "values" / "items")` (Py2: `"viewkeys"` etc.). Return live dict views.

### Metaclasses and `__str__`/`__unicode__`

- `with_metaclass(meta, *bases)` — `class Foo(six.with_metaclass(Meta, Base)):`.
  Builds a temporary `metaclass` subclass of `type` (with `__new__` delegating
  to `meta`, `__prepare__` forwarding, and a PEP 560 `types.resolve_bases`
  path on 3.7+) so one declaration works under Py2 (`__metaclass__`) and Py3
  (`metaclass=` keyword) syntax.
- `add_metaclass(metaclass)` — class decorator variant: copies `cls.__dict__`
  (dropping `__dict__`/`__weakref__`/slot names, preserving `__qualname__`)
  and rebuilds via `metaclass(name, bases, orig_vars)`.
  Example: `@six.add_metaclass(Meta)\nclass Foo: ...`.
- `python_2_unicode_compatible(klass)` — on Py3: no-op returning the class.
  On Py2: required `__str__` returning text, aliased it to `__unicode__`, and
  replaced `__str__` with a utf-8-encoding wrapper. Rationale: Py2 `str()` must
  return bytes while Py3 `str()` returns text; writing `__str__` once covers both.

### `six.moves` — the renamed-stdlib table (`add_move` / `remove_move`)

`MovedAttribute(name, old_mod, new_mod, old_attr=None, new_attr=None)` and
`MovedModule(name, old, new=None)` descriptors resolve lazily (cached on first
`__get__`) to the Py3 location, or the Py2 location under Py2. `add_move(move)`
registers a new entry; `remove_move(name)` unregisters (raises
`AttributeError("no such move, ...")` if absent). Both halves of the `urllib`
sub-namespace (`six.moves.urllib.parse`, `.error`, `.request`, `.response`,
`.robotparser`) are virtual modules served by the meta-path importer, plus a
`six.moves.urllib` namespace object exposing `parse/error/request/response/robotparser`.

Categories in `_moved_attributes` (≈70 entries):

- **builtins/functions:** `filter` (itertools.ifilter→builtins.filter),
  `map` (imap→map), `zip` (izip→zip), `range`/`xrange` (xrange→range),
  `zip_longest` (izip_longest→zip_longest), `filterfalse`
  (ifilterfalse→filterfalse), `reduce` (__builtin__→functools),
  `reload_module` (builtin reload→importlib.reload on 3.4+), `intern`
  (__builtin__→sys.intern), `input` (raw_input→input), `getcwd`/`getcwdb`
  (getcwdu/getcwd→os.getcwd/getcwdb).
- **io/strings:** `StringIO` (StringIO→io), `cStringIO`
  (cStringIO.StringIO→io.StringIO), `UserDict`/`UserList`/`UserString`
  (UserDict/UserList/UserString→collections; note: `collections`, not
  `collections.abc` — `UserDict` still lives in `collections` on Py3),
  `shlex_quote` (pipes.quote→shlex.quote).
- **config/persistence:** `configparser` (ConfigParser→configparser),
  `copyreg` (copy_reg→copyreg), `cPickle` (cPickle→pickle), `reprlib`
  (repr→reprlib), `dbm_gnu` (gdbm→dbm.gnu), `dbm_ndbm` (dbm→dbm.ndbm),
  `builtins` (__builtin__→builtins).
- **collections/threading:** `collections_abc`
  (collections→collections.abc on 3.3+), `_thread` (thread→_thread),
  `_dummy_thread` (dummy_thread→_dummy_thread, or `_thread` on 3.9+ where the
  former was removed).
- **HTTP/network/email:** `http_client` (httplib→http.client),
  `http_cookiejar` (cookielib→http.cookiejar), `http_cookies`
  (Cookie→http.cookies), `html_parser` (HTMLParser→html.parser),
  `html_entities` (htmlentitydefs→html.entities), `email_mime_*` (5 entries,
  email.MIME*→email.mime.*), `BaseHTTPServer`/`CGIHTTPServer`/
  `SimpleHTTPServer` (all→http.server), `socketserver`
  (SocketServer→socketserver), `queue` (Queue→queue), `getoutput`
  (commands→subprocess), `xmlrpc_client`/`xmlrpc_server`,
  `urllib_robotparser` (robotparser→urllib.robotparser), win32-only `winreg`
  (_winreg→winreg).
- **tkinter (14 entries):** `tkinter` (Tkinter→tkinter), dialog/filedialog/
  scrolledtext/simpledialog/tix/ttk/constants/dnd/colorchooser/commondialog/
  tkfiledialog/font/messagebox/tksimpledialog with their `tk*` Py2 names.
- **urllib sub-tables:** `urllib_parse` (~25 attrs: urlparse/urlsplit/urljoin/
  quote/quote_plus/unquote/urlencode/... from `urlparse`+`urllib`→`urllib.parse`),
  `urllib_error` (URLError/HTTPError/ContentTooShortError→urllib.error),
  `urllib_request` (~30 attrs incl. urlopen/Request/handlers from
  urllib2+urllib→urllib.request; legacy `URLopener`/`FancyURLopener` only
  registered on `<3.14` since stdlib removed them in 3.14),
  `urllib_response` (addbase/addclosehook/addinfo/addinfourl→urllib.response),
  `urllib_robotparser` (RobotFileParser).

Example: `from six.moves.urllib.parse import urlparse, urlencode` resolves to
`urllib.parse` on Py3, `urlparse`+`urllib` on Py2.

### Exceptions, exec, print, misc shims

- `reraise(tp, value, tb=None)` — Py3: `raise value.with_traceback(tb)`
  (instantiating `tp()` if value is None). Exists because Py2's
  `raise tp, value, tb` is a syntax error on Py3.
- `raise_from(value, from_value)` — Py3: `raise value from from_value`
  (explicit chaining); older Pythons: plain `raise value`. dateutil uses this
  (`six.raise_from(ParserError(...), e)` in `parser/_parser.py`).
- `exec_(_code_, _globs_=None, _locs_=None)` — Py3: builtin `exec`; Py2: an
  `exec ... in ...` statement wrapper (a statement on Py2, a function on Py3).
- `print_(*args, **kwargs)` — Py3: builtin `print`; carries a full Py2.4/2.5
  backport (unicode-aware `sep`/`end`/`file` handling) plus a `<3.3`
  `flush=` wrapper.
- `next` = builtin `next` (Py2 fallback: `it.next()`); `advance_iterator`
  alias. `callable` = builtin (Py2 fallback inspects `__call__` in the MRO).
- `Iterator` — Py3: plain `object`; Py2: mixin mapping `next()` →
  `__next__()`. `get_unbound_function`, `create_bound_method`,
  `create_unbound_method`, `get_method_function`/`get_method_self`
  (`__func__`/`__self__` vs `im_func`/`im_self`), `get_function_closure/code/
  defaults/globals` — paper over Py2/3 introspection renames.
- `assertCountEqual` / `assertRaisesRegex` / `assertRegex` / `assertNotRegex` —
  dispatch to the version-correct `unittest` method name
  (`assertItemsEqual`/`assertRaisesRegexp`/... on Py2).
- `wraps` = `functools.wraps` (with a `<3.4` backport tolerant of missing
  attributes). `__path__ = []` + `__package__` turn the module into a package
  so `six.moves.*` imports resolve through the meta-path hook.

## App usage & correctness

- **Direct app usage: none.** `grep -rn "six" src tests tools --include="*.py"`
  returns zero hits. No `import six` / `from six` anywhere in app code. No
  misuse possible — the package is never touched by first-party code.
- **Transitive chains (both verified in dist METADATA and `uv.lock`):**
  1. `flet 1.0.0` → `repath>=0.9.0` (flet METADATA) → `six>=1.9.0`
     (`repath-0.9.0.dist-info/METADATA` line 20). `repath.py` actively uses it:
     `import six`, `from six.moves.urllib import parse as urllib`,
     `isinstance(token, six.string_types)`, `six.text_type(val)` (routing/
     URL templating consumed by flet). This is the **runtime** chain.
  2. `flet-cli` (dev group) → `cookiecutter` → `arrow` → `python-dateutil
     2.9.0.post0` → `six>=1.5` (`python-dateutil` METADATA line 35). dateutil
     uses it in 8 files (`rrule.py`, `tz/*`, `relativedelta.py`,
     `parser/*`), e.g. `six.raise_from(...)` in `parser/_parser.py`. This is a
     **dev-only** chain (scaffolding/templating tooling).
  (`arrow` itself no longer depends on six; dateutil is its carrier.)
- **Correctness of the vendored copy:** `six.__version__` reports `1.17.0`,
  matching the dist-info; `top_level.txt` = `six`; wheel tags cover py2+py3.
  Nothing to fix.

## Considerations for v1

- This app pins `requires-python = ">=3.14"` (`pyproject.toml` line 6); six's
  entire reason for existing (Py2 compatibility) cannot apply. On 3.14 every
  `PY3` branch is taken and every Py2 fallback is unreachable-but-harmless.
  six is **inert weight**: ~35 KB, zero dependencies, no native code, no
  version conflicts (both dependents' floors — `>=1.5`, `>=1.9.0` — are
  satisfied by 1.17.0).
- **Do not add six to `dependencies`.** `REQUESTED` is empty (transitive-only);
  keep it that way. App code must never `import six` — write native Py3
  (`str`/`bytes`, `urllib.parse`, `raise ... from ...`, `metaclass=`).
- **Do not "clean up" six either.** Removing or constraining it would break
  `repath` (runtime, breaks flet routing) and `python-dateutil` (dev,
  breaks cookiecutter/arrow). Upstream keeps it alive for legacy Py2-support
  promises, not for anything this app needs.
- **Recommendation: zero action.** Leave the pin floating to the resolver;
  revisit only if an upstream (dateutil/repath) drops its six requirement, at
  which point it vanishes from the lockfile on its own.

## Gotchas

1. `six.py` is a module, not a package — don't look for a `six/` directory.
2. `import six.moves.urllib_parse` works but there is no such file; it's served
   by the `sys.meta_path` importer, so static file-finders won't see it.
3. `ensure_str`/`ensure_binary` default to utf-8; `b()` uses latin-1 — don't
   mix them on non-ASCII data.
4. `six.string_types` is a 1-tuple `(str,)` — always use with `isinstance`,
   never `type(x) is`.
5. `python_2_unicode_compatible` is a no-op on Py3; applying it is harmless
   but pointless — don't copy the pattern into new code.
6. ` moves.reload_module` points at `importlib` (3.4+); `moves.collections_abc`
   vs `collections` matters — `UserDict` is under `collections`, not
   `collections.abc`.
7. The `<3.14` guard on `URLopener`/`FancyURLopener` shows six tracks stdlib
   removals; on 3.14 those moves are gone (matching stdlib, which removed them).
