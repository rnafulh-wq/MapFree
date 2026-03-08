# Contributing to MapFree

Thank you for your interest in contributing to MapFree!
This document explains how to set up, develop, test, and submit contributions.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Testing](#testing)
- [Branch Naming](#branch-naming)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)
- [License](#license)

---

## Code of Conduct

- Be respectful and constructive in all interactions
- Welcome newcomers and help them get started
- Focus on what is best for the project and community
- Show empathy towards other contributors

---

## Getting Started

1. Check [Issues](https://github.com/rnafulh-wq/MapFree/issues) to see if the
   bug or feature is already being tracked
2. For major changes, open an issue first to discuss your proposal
3. Fork the repository and clone it locally
4. Follow the Development Setup below

---

## Development Setup

### Prerequisites

- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) (required)
- [COLMAP 3.13+](https://github.com/colmap/colmap/releases) on PATH
- Git

> **Important:** MapFree requires conda because GDAL and PDAL cannot be
> reliably installed via pip alone on Windows.
> Do NOT use `python -m venv` — it will not work for geospatial dependencies.

### Setup Steps

```powershell
# 1. Clone your fork
git clone https://github.com/YOUR-USERNAME/MapFree.git
cd MapFree

# 2. Add upstream remote
git remote add upstream https://github.com/rnafulh-wq/MapFree.git

# 3. Create conda environment
conda env create -f environment.yml

# 4. Activate environment
conda activate mapfree_engine

# 5. Install MapFree in editable mode
pip install -e .

# 6. Verify everything works
python -c "import mapfree; print('MapFree OK')"
gdalinfo --version
pdal --version
where.exe colmap
```

### Run in Development Mode

```powershell
conda activate mapfree_engine
python -m mapfree
```

Optionally set environment variables for more verbose output:

```powershell
$env:MAPFREE_LOG_LEVEL = "DEBUG"
python -m mapfree
```

### Development Tools

```powershell
# Linting
flake8 mapfree/

# Tests
pytest tests/ -v

# Tests with coverage
pytest tests/ --cov=mapfree --cov-report=html
```

---

## Development Workflow

1. **Sync with upstream** before starting:
   ```powershell
   git checkout develop
   git fetch upstream
   git merge upstream/develop
   ```

2. **Create a feature branch** from `develop`:
   ```powershell
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes** — follow code style guidelines below

4. **Test your changes:**
   ```powershell
   flake8 mapfree/
   pytest tests/ -v
   python -m mapfree   # verify GUI starts without error
   ```

5. **Commit** using conventional commit format

6. **Push and open a pull request** against `develop`

---

## Code Style

We follow **PEP 8** with flake8 enforcement (see `.flake8` and `setup.cfg`).

### Key Rules

- Max line length: **88 characters**
- Indentation: **4 spaces** (no tabs)
- Imports: standard library → third-party → local, each group separated by blank line

### Use Logging, Not Print

```python
# ❌ Avoid
print("Processing image...")

# ✅ Prefer
import logging
logger = logging.getLogger(__name__)
logger.info("Processing image...")
logger.error("Failed: %s", error_message)
```

### Type Hints

Encouraged for public APIs:

```python
from pathlib import Path

def find_colmap(search_dirs: list[Path]) -> Path | None:
    """Find COLMAP executable in given directories.

    Args:
        search_dirs: List of directories to search.

    Returns:
        Path to colmap.exe, or None if not found.
    """
    ...
```

### Docstrings

Use Google-style docstrings for all public functions:

```python
def extract_gps(image_path: Path) -> dict | None:
    """Extract GPS coordinates from image EXIF data.

    Args:
        image_path: Path to the image file.

    Returns:
        Dict with keys 'lat', 'lon', 'alt', or None if no GPS found.

    Raises:
        FileNotFoundError: If image_path does not exist.
    """
    ...
```

---

## Testing

### Running Tests

```powershell
conda activate mapfree_engine

# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=mapfree --cov-report=html

# Specific test file
pytest tests/test_pipeline.py -v

# Specific test
pytest tests/test_pipeline.py::test_colmap_integration -v
```

### Writing Tests

Place tests in `tests/` with naming `test_*.py`:

```python
import pytest
from pathlib import Path
from mapfree.geospatial.georef import get_utm_epsg_from_gps

def test_utm_epsg_south():
    """Lewoleba (lat=-8.37, lon=123.40) should be EPSG:32751."""
    epsg = get_utm_epsg_from_gps(lat=-8.37, lon=123.40)
    assert epsg == 32751

def test_utm_epsg_north():
    """Northern hemisphere should return 326xx."""
    epsg = get_utm_epsg_from_gps(lat=3.5, lon=98.6)
    assert 32600 <= epsg <= 32660
```

### Real-world Testing

For PRs that touch the pipeline (core/, engines/, geospatial/):

1. Test with at least **10 drone photos with GPS**
2. Confirm Sparse Reconstruction produces >80% registered images
3. Confirm Geospatial stage produces non-empty `dsm.tif` and `dtm.tif`
4. Attach `mapfree.log` to the PR description

---

## Branch Naming

Always branch from `develop` (not `main`):

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feature/` | New features | `feature/3d-viewer` |
| `fix/` | Bug fixes | `fix/colmap-argparse` |
| `perf/` | Performance improvements | `perf/direct-pipeline-mode` |
| `refactor/` | Code refactoring | `refactor/engine-abstraction` |
| `docs/` | Documentation only | `docs/update-readme` |
| `test/` | Adding/updating tests | `test/geospatial-coverage` |
| `chore/` | Maintenance, dependencies | `chore/update-pyside6` |

### Base Branches

- **`main`** — stable releases only, never commit directly
- **`develop`** — integration branch, all PRs target here

---

## Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>        ← optional, explain what and why
<footer>      ← optional, issue references
```

### Types

| Type | Use for |
|------|---------|
| `feat` | New feature |
| `fix` | Bug fix |
| `perf` | Performance improvement |
| `refactor` | Refactoring without feature/fix |
| `docs` | Documentation only |
| `test` | Adding or updating tests |
| `chore` | Build, tooling, dependencies |
| `style` | Formatting, no logic change |

### Examples

```
fix(engine): remove unsupported --SiftExtraction.num_threads arg

feat(geospatial): use pdal info to read binary PLY bounds

perf(pipeline): direct mode without chunking for ≤500 photos

fix(legal): replace MIT with AGPL v3 license
```

### Guidelines

- Use imperative mood: "add" not "added", "fix" not "fixed"
- Keep subject line under 72 characters
- No period at end of subject
- Body explains *what* and *why*, not *how*

---

## Pull Request Process

### Before Submitting

- [ ] All tests pass: `pytest tests/ -v`
- [ ] Linting clean: `flake8 mapfree/`
- [ ] GUI starts without error: `python -m mapfree`
- [ ] For pipeline changes: real-world test with drone photos
- [ ] Commits follow conventional format
- [ ] Rebased on latest `develop`

### PR Title

Use conventional commit format:

```
fix(geospatial): fix DTM ground filter using filters.range
feat(gui): real-time COLMAP output in console panel
perf(pipeline): remove photo copy overhead for ≤500 photos
```

### Review Process

- Maintainers will review within a few days
- Address feedback by pushing new commits to the same branch
- Do not force-push after review has started
- Maintainer will merge once approved

---

## Issue Reporting

### Bug Reports

Please include:

| Field | Example |
|-------|---------|
| OS | Windows 11 64-bit |
| COLMAP version | `colmap feature_extractor --help \| head -1` |
| GPU | NVIDIA MX150, 2GB VRAM |
| Photo count | 335 photos, ~5.9MB each |
| mapfree.log | Attach from `your_project/logs/mapfree.log` |
| Steps to reproduce | Numbered steps |
| Expected vs actual | What should happen vs what happened |

### Feature Requests

- **Use case**: Why is this needed?
- **Proposed solution**: How should it work?
- **Alternatives**: Other approaches considered
- **Examples**: Similar feature in Metashape, WebODM, ODM, etc.

---

## Getting Help

- **Questions**: [GitHub Discussions](https://github.com/rnafulh-wq/MapFree/discussions)
- **Bugs**: [GitHub Issues](https://github.com/rnafulh-wq/MapFree/issues)
- **Docs**: [docs/](docs/) folder

---

## License

By contributing to MapFree, you agree that your contributions will be
licensed under the **GNU Affero General Public License v3.0 (AGPL v3)**
that covers this project.

See [LICENSE](LICENSE) for full text.

---

**Thank you for contributing to MapFree! 🎉**
