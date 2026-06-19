# Contributing

Thank you for wanting to contribute to PyShock! I really appreciate it.

## Setup

```sh
git clone https://github.com/jwinpbe/pyshock
cd pyshock
just install
```

That creates a virtual environment and installs everything, including dev tools.

## Making changes

Create a branch with a descriptive name.

```sh
git switch --create fix/signin-issue
```

Write tests for what you change. If you fix a bug, add a test that would have caught it. If you add a feature, test it works.

## Before you submit

Two commands must pass:

```sh
just lint
just test
```

`just lint` formats your code, checks for issues, and runs the type checker. `just test` runs the full test suite with coverage.

If you changed CLI behavior, test with `--json` output too.

## Opening a pull request

Push your branch and open a PR. Use the pull request template. Link the issue your change addresses with `closes #XXXX`.

Your PR will be reviewed, I may ask you to make changes!

## Questions

Open an issue with the bug report template.
