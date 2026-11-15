# Versioning and deprecation

WikibaseIntegrator follows [semantic versioning](https://semver.org/) from version 1.0: a version number
`MAJOR.MINOR.PATCH` changes its

- **major** number when the public API changes in a way that can break the code using it,
- **minor** number when features are added without breaking the public API,
- **patch** number for bug fixes that don't change the public API.

Before 1.0, a minor release (e.g. 0.14 to 0.15) can break the public API. Every such change is listed in the
[upgrading guide](upgrading.md), with the code to change. To stay on a minor version, pin it with `~=`, e.g.
`wikibaseintegrator~=0.15.0`. From 1.0, `wikibaseintegrator~=1.0` gets every release without a breaking change.

## The public API

The public API is what semantic versioning covers:

- the names exported by the `__all__` of the package and of its subpackages: `wikibaseintegrator`,
  `wikibaseintegrator.datatypes`, `wikibaseintegrator.datatypes.extra`, `wikibaseintegrator.entities` and
  `wikibaseintegrator.models`;
- the `wbi_*` modules (`wbi_config`, `wbi_enums`, `wbi_exceptions`, `wbi_fastrun`, `wbi_helpers`, `wbi_login`...) and
  the names they define, documented in the [API reference](../api/index.rst);
- the keys of `wbi_config.config` and their default values;
- the parameters, return types and documented behavior of all of these.

Names starting with an underscore (`_`), in any module, are private: they can change or disappear in any release,
without a deprecation period. So can the attributes that are not documented, the text of the log messages and of the
exceptions, and the `repr()` of the objects.

## What isn't covered yet

Some parts of the library are marked as **experimental** or **beta**. They can change in a minor release, without a
deprecation period:

- **experimental**: `format2wbi()` and its helpers. Calling `format2wbi()` emits a `UserWarning`.
- **beta**: the support of Structured Data on Commons (`MediaInfoEntity`, `wbi.mediainfo`), because the MediaInfo API
  has no stable interface policy and can change without notice (see [Structured Data on Commons](mediainfo.md)).

A new experimental or beta API is marked as such in its documentation, and in its docstring. An experimental function
also warns when it's called. It becomes stable when the documentation stops marking it, which the
[changelog](../changelog.rst) announces.

## Deprecation

A public API is never removed or changed in a breaking way without warning:

1. It is **deprecated** in a minor release: it keeps working, emits a `DeprecationWarning` saying what to use
   instead and in which version it will be removed, and the [upgrading guide](upgrading.md) lists it. Its docstring
   gets a `deprecated` note.
2. It stays deprecated for **at least one minor release**.
3. It is **removed in a major release** only (before 1.0: in a later minor release), with an entry in the breaking
   changes of the upgrading guide.

Python shows a `DeprecationWarning` only when it is triggered by the code of the `__main__` module. To see the
ones triggered elsewhere, e.g. in the modules of your bot, run Python with `-W default::DeprecationWarning`, or
turn them into errors in your tests (`-W error::DeprecationWarning`, or the `filterwarnings` option of pytest).

When a change can't go through a deprecation period, like a different result of `len()`, it waits for a major
release.

## What counts as a breaking change

Besides removing or renaming a public name or a parameter, these changes are breaking, and wait for a major
release:

- changing the **default value** of a parameter or of a key of `wbi_config.config`, when the result changes;
- changing the **type of the value returned**, or of the **exception raised** in a given case. Raising a subclass of
  the exception raised before isn't breaking;
- changing the **retries**: what is retried, how many times, and how long the library waits;
- changing the **data sent to the Wikibase instance** for the same calls, e.g. writing fields that weren't written,
  or removing claims that were kept.

These changes aren't breaking, and can come in a minor release:

- adding a function, a class, a method, a keyword parameter with a default value, or a key of `wbi_config.config`;
- raising an exception where the library used to fail later in an unrelated way (e.g. an `AttributeError`), or
  sent invalid data that the instance rejected;
- fixing a bug, when the previous behavior contradicted the documentation. A fix that callers can notice is
  listed in the changelog.

## Python versions

WikibaseIntegrator supports the Python versions that the [CI](https://github.com/LeMyst/WikibaseIntegrator/actions)
tests, listed in the `python` requirement and the classifiers of the package: Python 3.11 to 3.15 today.

- A new Python version is supported in a minor or patch release, once the CI passes on it.
- Support for a Python version that has reached its [end of life](https://devguide.python.org/versions/) can be
  dropped in a **minor** release. The upgrading guide announces it, and the `Requires-Python` metadata of the
  package changes, so pip keeps installing the last compatible release on the older Python.
- A Python version that is still supported upstream is only dropped in a major release.
