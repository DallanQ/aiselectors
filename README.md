# aiselectors

[![Release](https://img.shields.io/github/v/release/DallanQ/aiselectors)](https://img.shields.io/github/v/release/DallanQ/aiselectors)
[![Build status](https://img.shields.io/github/actions/workflow/status/DallanQ/aiselectors/main.yml?branch=main)](https://github.com/DallanQ/aiselectors/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/DallanQ/aiselectors/branch/main/graph/badge.svg)](https://codecov.io/gh/DallanQ/aiselectors)
[![Commit activity](https://img.shields.io/github/commit-activity/m/DallanQ/aiselectors)](https://img.shields.io/github/commit-activity/m/DallanQ/aiselectors)
[![License](https://img.shields.io/github/license/DallanQ/aiselectors)](https://img.shields.io/github/license/DallanQ/aiselectors)

Human-readable prompts for selecting data from HTML.

- **Github repository**: <https://github.com/DallanQ/aiselectors/>
- **Documentation** <https://DallanQ.github.io/aiselectors/>

## Getting started with your project

First, clone this repository.

Next, set python to version 3.11. If you use rtx, you can `rtx install`

Finally, install the environment and the pre-commit hooks with

```bash
make install
```

And install playwright dependencies with

```bash
playwright install
```

Note that this command may ask you to also install some additional dependencies.

You are now ready to start development on your project!
The CI/CD pipeline will be triggered when you open a pull request, merge to main, or when you create a new release.

To finalize the set-up for publishing to PyPi or Artifactory, see [here](https://fpgmaas.github.io/cookiecutter-poetry/features/publishing/#set-up-for-pypi).
For activating the automatic documentation with MkDocs, see [here](https://fpgmaas.github.io/cookiecutter-poetry/features/mkdocs/#enabling-the-documentation-on-github).
To enable the code coverage reports, see [here](https://fpgmaas.github.io/cookiecutter-poetry/features/codecov/).

## Deactivating and reactivating the environment

`exit` deactivates the virtual environment; `poetry shell` reactivates it.

## Releasing a new version

---

Repository initiated with [fpgmaas/cookiecutter-poetry](https://github.com/fpgmaas/cookiecutter-poetry).
