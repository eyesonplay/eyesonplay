# Contributing to EyesOnPlay

Thanks for helping. A few things to know before you open a pull request.

## Licensing of contributions

EyesOnPlay is dual-licensed: the public code is under the GNU AGPL-3.0, and the
maintainers also offer it under commercial licences. To keep that possible,
every contribution must be licensed to the project on terms that allow both.

By submitting a contribution (code, documentation, models, data or anything
else) you confirm that:

1. you wrote it, or otherwise have the right to submit it; and
2. you grant the EyesOnPlay maintainers a perpetual, worldwide, non-exclusive,
   royalty-free, irrevocable licence to use, modify, distribute and sublicense
   it, including under licences other than the AGPL-3.0 (such as commercial
   licences).

You keep the copyright to your contribution. Pull requests may be asked to
sign a formal Contributor Licence Agreement before they are merged.

Do not submit third-party code, model weights or datasets unless their licence
allows this; list anything third-party in [docs/third-party.md](docs/third-party.md).

## Development

See the [README](README.md) for running the stack and the tests. Before opening a
pull request:

- event engine: `cd event-engine && pytest`
- worker: `cd inference-worker && pytest`
- api: `cd backend && pytest`
- frontend: `cd frontend && pnpm typecheck && pnpm lint && pnpm test`

New behaviour comes with tests. Never invent data the video does not support:
if a position, identity or event cannot be measured, the system says so rather
than guessing.

## Security

Please report security issues privately (GitHub security advisories on
[eyesonplay/eyesonplay](https://github.com/eyesonplay/eyesonplay)), not in public issues.
