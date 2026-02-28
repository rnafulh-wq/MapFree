# Contributing to MapFree

## Development setup

```bash
git clone https://github.com/your-org/MapFree.git
cd MapFree
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -e .
pip install flake8
```

## Code style

- Follow **PEP 8**. Run `flake8` before submitting (config in `setup.cfg` and `.flake8`).
- Use the **logging** module instead of `print()` for diagnostic or progress output.
- Type hints are encouraged for public APIs.

## Branch naming

- `feature/<short-name>` — New features (e.g. `feature/3d-viewer`).
- `fix/<short-name>` — Bug fixes (e.g. `fix/colmap-timeout`).
- `refactor/<short-name>` — Code refactors without changing behaviour.
- `docs/<short-name>` — Documentation only (e.g. `docs/readme-badges`).

Base branches: `main` for stable releases, `develop` for integration. Branch from `develop` unless you are fixing a release.

## Pull request workflow

1. Create a branch from `develop` using the naming convention above.
2. Make your changes; ensure `flake8` passes and the app runs (`python -m mapfree.app` or CLI).
3. Push the branch and open a pull request against `develop`.
4. Use a clear title and reference any issue. In the description, summarize the change and how to test.
5. Address review feedback. Maintainers will merge when approved.

## Commit messages (conventional)

Use a short prefix so history is scannable:

- **feat:** New feature (e.g. `feat: add OpenMVS dense engine option`).
- **fix:** Bug fix (e.g. `fix: handle missing COLMAP binary gracefully`).
- **refactor:** Refactor without changing behaviour (e.g. `refactor: extract pipeline stages into helpers`).
- **docs:** Documentation only (e.g. `docs: update README installation steps`).
- **chore:** Build, tooling, or trivial changes (e.g. `chore: bump flake8 in dev deps`).

First line should be imperative and under about 72 characters. Add a blank line and body if more context is needed.

Example:

```
feat: add progress bar to console panel

Emit progress from pipeline; connect to ProgressPanel.update_progress.
```

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
