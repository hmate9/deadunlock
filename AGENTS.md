# AGENT Guidelines

This repository contains a Windows-only aimbot/ESP for the Deadlock game.
Python modules live in the `deadlock` package and various helper scripts
reside in the project root.

## Coding conventions

- Target **Python 3.11** and keep compatibility with standard libraries only.
- Indent with **4 spaces** and keep line length under **100** characters.
- Provide triple quoted docstrings for all public modules, classes and functions.
- Use type hints for function signatures and dataclasses for simple containers.
- Group imports in the order: standard library, third party, local modules.
- End all files with a trailing newline.

## Commit messages

- Start with a short summary (<=50 chars) in imperative mood.
- Leave a blank line before any detailed description.

Example:
```
Add update check for binary releases

Explain what was changed and why.
```

## Programmatic checks

Before committing any changes run the following from the repo root:

```
python -m py_compile $(git ls-files '*.py')
```

Fix any reported errors so that all Python files compile.

## Pull request text

Every PR description should contain two sections:

```
## Summary
<Describe changes and cite lines as `F:path#Lstart-Lend`>

## Testing
<Show output of the programmatic checks or explain failures>
```

These guidelines apply to all files in this repository.
