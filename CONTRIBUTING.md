# Contributing to Mypy

Welcome!  Mypy is a community project that aims to work for a wide
range of Python users and Python codebases.  If you're trying mypy on
your Python code, your experience and what you can contribute are
important to the project's success.

## Code of Conduct

Everyone participating in the Mypy community, and in particular in our
issue tracker, pull requests, and chat, is expected to treat
other people with respect and more generally to follow the guidelines
articulated in the [Python Community Code of Conduct](https://www.python.org/psf/codeofconduct/).


## Getting started with development

### Setup

Run the following:
```
# Clone the mypy repository
git clone https://github.com/python/mypy.git

# Enter the repository
cd mypy

# Create then activate a virtual environment
python3 -m venv venv
source venv/bin/actiate

# Install the test requirements and the project
python3 -m pip install -r test-requirements.txt
python3 -m pip install -e .
hash -r
```

### Running tests

Once setup, you should be able to run tests:
```
python3 runtests.py
```

To use mypy to check mypy's own code, run:
```
python3 runtests.py self
# or equivalently:
python3 -m mypy --config-file mypy_self_check.ini -p mypy
```

You can also use `tox` to run tests, for instance:
```
tox -e py
```

## First time contributors

If you're looking for things to help with, browse our [issue tracker](https://github.com/python/mypy/issues)!

In particular, look for:
- [good first issues](https://github.com/python/mypy/labels/good-first-issue)
- [good second issues](https://github.com/python/mypy/labels/good-second-issue)
- [documentation issues](https://github.com/python/mypy/labels/documentation)

It's also extremely easy to get started contributing to our sister project
[typeshed](https://github.com/python/typeshed/issues) that provides type stubs
for libraries. This is a great way to become familiar with type syntax.

If you need help getting started, don't hesitate to ask on
[gitter](https://gitter.im/python/typing).

To get help fixing a specific issue, it's often best to comment on the issue
itself. The more details you provide about what you've tried and where you've
looked, the easier it will be for you to get help.

Interactive debuggers like `pdb` and `ipdb` are really useful for getting
started with the mypy codebase. This is a
[useful tutorial](https://realpython.com/python-debugging-pdb/).

## Submitting changes

Even more excellent than a good bug report is a fix for a bug, or the
implementation of a much-needed new feature. We'd love to have
your contributions.

We use the usual GitHub pull-request flow, which may be familiar to
you if you've contributed to other projects on GitHub.  For the mechanics,
see [our git and GitHub workflow help page](https://github.com/python/mypy/wiki/Using-Git-And-GitHub),
or [GitHub's own documentation](https://help.github.com/articles/using-pull-requests/).

Anyone interested in Mypy may review your code.  One of the Mypy core
developers will merge your pull request when they think it's ready.

If your change will be a significant amount of work
to write, we highly recommend starting by opening an issue laying out
what you want to do.  That lets a conversation happen early in case
other contributors disagree with what you'd like to do or have ideas
that will help you do it.

The best pull requests are focused, clearly describe what they're for
and why they're correct, and contain tests for whatever changes they
make to the code's behavior.  As a bonus these are easiest for someone
to review, which helps your pull request get merged quickly!  Standard
advice about good pull requests for open-source projects applies; we
have [our own writeup](https://github.com/python/mypy/wiki/Good-Pull-Request)
of this advice.

See also our [coding conventions](https://github.com/python/mypy/wiki/Code-Conventions) --
which consist mainly of a reference to
[PEP 8](https://www.python.org/dev/peps/pep-0008/) -- for the code you
put in the pull request.

Also, do not squash your commits after you have submitted a pull request, as this
erases context during review. We will squash commits when the pull request is merged.

You may also find other pages in the
[Mypy developer guide](https://github.com/python/mypy/wiki/Developer-Guides)
helpful in developing your change.


## Core developer guidelines

Core developers should follow these rules when processing pull requests:

* Always wait for tests to pass before merging PRs.
* Use "[Squash and merge](https://github.com/blog/2141-squash-your-commits)"
  to merge PRs.
* Delete branches for merged PRs (by core devs pushing to the main repo).
* Edit the final commit message before merging to conform to the following
  style (we wish to have a clean `git log` output):
  * When merging a multi-commit PR make sure that the commit message doesn't
    contain the local history from the committer and the review history from
    the PR. Edit the message to only describe the end state of the PR.
  * Make sure there is a *single* newline at the end of the commit message.
    This way there is a single empty line between commits in `git log`
    output.
  * Split lines as needed so that the maximum line length of the commit
    message is under 80 characters, including the subject line.
  * Capitalize the subject and each paragraph.
  * Make sure that the subject of the commit message has no trailing dot.
  * Use the imperative mood in the subject line (e.g. "Fix typo in README").
  * If the PR fixes an issue, make sure something like "Fixes #xxx." occurs
    in the body of the message (not in the subject).
  * Use Markdown for formatting.
