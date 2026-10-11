# Security policy

## Reporting a problem

Please report security problems **privately**. Do not open a public issue or pull request.

On the repository's [Security tab](https://github.com/rcocetta/school-quiz/security), choose **Report a vulnerability** (GitHub private vulnerability reporting). Say what you found, how to reproduce it (a small quiz file helps), and what you think the impact is. We will reply as soon as we can, and credit you in the fix if you like.

## What is in scope

- The pages `quizgen` generates: for example script injection through quiz text, a weakened Content-Security-Policy, or a page that makes requests to other sites.
- The `quizgen` command: for example reading or writing files outside the chosen folders, or unsafe handling of images and links.
- The GitHub Actions workflows in `.github/workflows/`: for example leaked secrets or permissions that are too broad.

Not in scope: the content of third-party image hosts that a quiz author links to, and problems in forks or other people's quiz sites.

## Maintainer notes

The Claude review workflow needs a `CLAUDE_CODE_OAUTH_TOKEN` repository secret, made with `claude setup-token` and used only for this workflow. If it might have leaked, revoke it and make a new one.

## Supported versions

Only the latest version on the `main` branch is supported. Fixes go there.
