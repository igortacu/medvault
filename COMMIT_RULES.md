# Commit Rules & Guidelines

This document outlines the commit conventions used in this project. We follow the **Conventional Commits** specification to ensure clear, consistent, and organized commit history.

## Commit Message Format

Each commit message must follow this structure:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Components

#### Type (Required)
The type of change being made. Must be one of:

- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Changes that don't affect code meaning (formatting, missing semicolons, etc.)
- **refactor**: Code changes that neither fix bugs nor add features
- **perf**: Code changes that improve performance
- **test**: Adding or updating tests
- **chore**: Changes to build process, dependencies, or tooling
- **ci**: Changes to CI/CD configuration

#### Scope (Optional)
The area of the codebase affected by the change. Use lowercase.

Examples: `auth`, `database`, `ui`, `api`, `homepage`

#### Subject (Required)
A concise description of the change:
- Use the imperative mood ("add" not "added" or "adds")
- Don't capitalize the first letter
- No period (.) at the end
- Maximum 50 characters

#### Body (Optional)
Provide additional context and explain **why** the change was made:
- Use the imperative mood
- Include motivation for the change
- Separate from subject with a blank line
- Wrap at 72 characters
- Explain what and why, not how

#### Footer (Optional)
Reference issues and breaking changes:
- Format: `Closes #123` or `Fixes #456`
- For breaking changes: `BREAKING CHANGE: description`

## Examples

### Simple Feature
```
feat(auth): add password reset functionality
```

### Feature with Body
```
feat(ui): add dark mode toggle

Add a toggle switch in the settings menu to allow users to switch between
light and dark themes. The preference is saved to localStorage and persists
across sessions.

Closes #42
```

### Bug Fix
```
fix(database): resolve connection timeout issue

Increase the connection pool size and add retry logic with exponential
backoff. This prevents timeouts during peak usage periods.

Fixes #89
```

### Documentation Update
```
docs: update installation instructions

Clarify prerequisites and add troubleshooting section for common setup issues.
```

### Refactor
```
refactor(api): restructure request validation

Move validation logic into a separate middleware module for better
reusability and maintainability.
```

### Performance Improvement
```
perf(search): optimize database queries

Add indexes on frequently searched columns and implement query caching
to reduce average search time by 40%.

Closes #156
```

## Best Practices

✅ **Do:**
- Write clear, descriptive commit messages
- Keep commits focused on a single concern
- Use present tense and imperative mood
- Explain the "why" behind changes
- Reference related issues
- Break large changes into logical, smaller commits

❌ **Don't:**
- Use vague messages like "fix stuff" or "updates"
- Mix unrelated changes in a single commit
- Write messages longer than necessary without formatting
- Capitalize the subject line
- Add a period at the end of the subject
- Commit directly to `main` without a pull request (follow the PR review process)

## Committing Guidelines

1. **Before committing**: Ensure your code is tested and follows project standards
2. **Create a feature branch**: Use descriptive branch names (e.g., `feat/dark-mode`, `fix/auth-bug`)
3. **Keep commits atomic**: Each commit should represent one logical unit of work
4. **Write meaningful messages**: Your future self will thank you
5. **Review before pushing**: Double-check your commit message and changes
6. **Use pull requests**: Submit a PR for review rather than pushing directly to `main`

## Tools & Automation

To help enforce these conventions, consider using:
- **Commitlint**: Validates commit messages against the Conventional Commits standard
- **Husky**: Git hooks to run checks before committing
- **Commitizen**: Interactive CLI to guide commit message creation

---

**Questions?** Refer to [Conventional Commits](https://www.conventionalcommits.org/) for more details.
