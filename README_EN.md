<div align="center">

# Image to CSS Art

[![release](https://img.shields.io/github/v/release/AvroraCL/image-to-css-art?style=flat-square&logo=github)](https://github.com/AvroraCL/image-to-css-art/releases)
[![checks](https://img.shields.io/github/actions/workflow/status/AvroraCL/image-to-css-art/ci.yml?style=flat-square&label=checks)](https://github.com/AvroraCL/image-to-css-art/actions)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![HTML + CSS](https://img.shields.io/badge/output-HTML%20%2B%20CSS-21B6AD?style=flat-square)](#output-constraints)
[![MIT](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

**Trace a reference image into a standalone, open-anywhere pure HTML + CSS illustration.**

[GitHub](https://github.com/AvroraCL/image-to-css-art) · [GitCode](https://gitcode.com/HelenaSG/image-to-css-art) · [Download](https://github.com/AvroraCL/image-to-css-art/releases) · [中文](README.md)

</div>

Image to CSS Art is an AI Agent skill with a standalone command-line tool. Any AI coding assistant that can load Agent Skills and run local commands (Codex, Claude Code, etc.) can use it, and it also works from the plain command line without any agent. It performs color segmentation, contour extraction and gradient fitting locally, turning a reference image into a large set of HTML elements and CSS polygons. The finished file needs no Python, no image assets and no network connection to open.

This is an independent community tool. Conversion is lossy automatic contour tracing, and the generated layers are organized by color and outline; it does not automatically split characters into semantically editable hair, eye or clothing components.

## For users

### What it does

- Converts illustrations, flat-color artwork and other static bitmaps into a single-file HTML document.
- Preserves the original aspect ratio and draws contours, holes and thin lines with CSS `clip-path`.
- Fits gradients inside larger color regions and adds an underpainting layer to reduce seams at small display sizes.
- Offers `preview`, `balanced` and `faithful` quality presets plus an output size budget.
- Handles non-ASCII paths, EXIF orientation, alpha compositing onto a matte, and JSON conversion reports.
- Automatically checks the structural constraints of the generated HTML/CSS.

### Example

<div align="center">
<img src="docs/contour-study.png" alt="Self-made input test image: teal rings, a coral sphere, holes and thin lines" width="300">
</div>

The image above is a repository-made **input test image**; the [matching pure CSS output](docs/contour-study.html) can be downloaded and opened directly. It contains 326 contours, 48 underpainting shapes and 98 gradients; the HTML is about 463 kB. The image in this README is for illustration only — the generated HTML never references it.

### Download v0.1.1

| File | Description |
| --- | --- |
| [image-to-css-art-0.1.1-plugin.zip](https://github.com/AvroraCL/image-to-css-art/releases/download/v0.1.1/image-to-css-art-0.1.1-plugin.zip) | Full plugin source package: manifest, skill, CLI, docs, example and tests |
| [image-to-css-art-0.1.1-skill.zip](https://github.com/AvroraCL/image-to-css-art/releases/download/v0.1.1/image-to-css-art-0.1.1-skill.zip) | Standalone installable skill, including the conversion scripts and license |
| [SHA256SUMS.txt](https://github.com/AvroraCL/image-to-css-art/releases/download/v0.1.1/SHA256SUMS.txt) | SHA-256 checksums for both archives |

Source code is also mirrored on [GitCode](https://gitcode.com/HelenaSG/image-to-css-art). The archives do not bundle Python or third-party dependencies.

### Requirements

- Generating: Python 3.10+ with NumPy, Pillow and OpenCV; installing dependencies needs network access once.
- Viewing: a browser with evenodd CSS polygon fills, gradients and `aspect-ratio` support.
- Development happens mainly on Windows + Python 3.12 + Chromium; CI covers Windows/Linux and Python 3.10/3.12.

### Using with AI agents

Any AI coding assistant that supports the Agent Skills format can load this skill: download and unpack the skill package, put the whole `image-to-css-art` directory into your personal `~/.agents/skills/` or the project's `.agents/skills/`, then simply ask your agent in natural language. Codex users can also have `$skill-installer` install from this repository's `skills/image-to-css-art`; see [OpenAI's skill documentation](https://learn.chatgpt.com/docs/build-skills) for loading details.

After installing, provide a reference image and prompt:

```text
$image-to-css-art Recreate this reference image as faithfully as possible
in a single pure HTML + CSS file. No img, SVG, Canvas, JavaScript, base64
or external resources. Use the faithful preset, check desktop and narrow
viewports, then deliver the HTML.
```

The full plugin manifest lives at `.codex-plugin/plugin.json`. To install into the Codex plugin list, unpack the plugin package and have `$plugin-creator` register the directory in your personal local marketplace, then install from there and test in a fresh task. The workflow is described in [OpenAI's plugin documentation](https://learn.chatgpt.com/docs/build-plugins). This repository publishes the plugin source package; it is not submitted to any public OpenAI plugin directory.

### Command-line usage

Run these PowerShell commands from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r skills/image-to-css-art/requirements.txt
.\.venv\Scripts\python.exe skills/image-to-css-art/scripts/image_to_css.py convert "reference.png" -o "art.html" --preset faithful
.\.venv\Scripts\python.exe skills/image-to-css-art/scripts/image_to_css.py audit "art.html"
```

On Linux/macOS use `.venv/bin/python`. When conversion finishes, open the HTML in a browser.

Common options:

| Option | Purpose |
| --- | --- |
| `--preset preview/balanced/faithful` | Trade-off between speed, size and detail; defaults to faithful |
| `--max-width 1200` | Caps the tracing width; the longest edge is also capped at twice this value |
| `--colors 160` | Quantization palette size, 2–256 |
| `--background '#faf8f2'` | Page matte and compositing color for transparent areas |
| `--title "Scene description"` | Sets the title and accessible description, escaped as plain text |
| `--max-output-mb 32` | HTML size budget in MiB, defaults to 64 |
| `--fit 20` | Target size in MiB: automatically steps down width/colors until the HTML fits |
| `--report .work/report.json` | Writes contour count, gradient count, dependency versions and SHA-256 |
| `--no-gradients` / `--no-underpainting` | Disable local gradients / the anti-seam underpainting |
| `--score` | Rasterize the shapes offline and report MAE against the reference |
| `--force` | Explicitly overwrite existing output and report |

### Output constraints

The output consists of `main`, `div` layers, inline styles and the minimal document metadata. Every visible mark comes from CSS polygons and gradients — no `<img>`, SVG, Canvas, JavaScript, external links, font assets or base64. Python is only used for offline authoring.

### Known limitations

Faithful outputs can reach tens of megabytes and tens of thousands of elements, which is expensive to render on low-memory devices. Photographs, textures and noise produce larger files than flat-color illustrations. Transparent backgrounds are composited onto the chosen matte; animated and multi-page images must be exported to a single frame first. Wide-gamut or CMYK sources are best converted to sRGB beforehand.

The automatic audit verifies structure only; it cannot prove visual similarity. Always compare thin lines, contours, gradients and multiple display sizes against the reference. See [tuning.md](skills/image-to-css-art/references/tuning.md) for the full algorithm and tuning notes.

---

## For developers

### Design principles

The conversion algorithm is separated from the model: the skill chooses parameters, runs tools and inspects results visually, while Python performs reproducible image processing. Identical input, parameters and dependency environment produce identical HTML; the report additionally records timing. All runtime resources live inside the skill, so copying the skill alone keeps it working.

### Repository layout

```text
.codex-plugin/plugin.json              # Codex plugin manifest
skills/image-to-css-art/
├── SKILL.md                           # Workflow and trigger conditions
├── agents/openai.yaml                 # Codex display metadata
├── requirements.txt                   # Authoring-time dependencies
├── scripts/image_to_css.py            # CLI entry point
├── scripts/css_art/                   # Segmentation, geometry, gradients, output, audit
└── references/tuning.md               # Tuning parameters and limits
scripts/                              # Checks, packaging, original test-image generator
tests/                                # Regression tests
docs/                                 # Public sample input and HTML output
.github/workflows/ci.yml               # Cross-platform checks
```

### Checks and packaging

```powershell
.\.venv\Scripts\python.exe scripts/check.py
.\.venv\Scripts\python.exe scripts/package.py
```

Archives are written to `dist/` and include only explicitly listed source and documentation directories, with fixed ZIP metadata for reproducible builds. `.venv/`, `.work/` and user inputs are never packaged. Do not commit private reference images, generated results or local paths to the repository.

### Verification scenarios

| Scenario | What is checked |
| --- | --- |
| Tiny input and flat colors | 1×1 and blank backgrounds do not crash; valid output opens |
| Transparency and orientation | Matte compositing is correct; EXIF rotation keeps the aspect ratio |
| Holes and separate islands | Evenodd polygon bridges preserve the filled areas |
| Thin lines and gradients | Dark isolated details survive; smooth bands produce local gradients |
| File writing | Input/output conflicts rejected, overwrite refused by default, no partial file over budget |
| Output constraints | Scripts, images, resource URLs and event attributes are rejected |
| Reproducibility and distribution | Identical HTML/ZIP in the same environment; standalone skill package runs |

Visual inspection additionally covers the original width and a narrow viewport around 390 px; the regression scripts do not pretend to be visual similarity tests.

### Related projects

The community already has [css-video](https://github.com/kevinjycui/css-video) for CSS polygon conversion and [img2css](https://github.com/javierbyte/img2css) for the CSS pixel-shadow route. These are related precedents; this repository neither copies nor bundles their code. The current implementation focuses on standalone single files, local gradients, detail preservation, a skill-driven workflow and automatic constraint checks.

### Contributing and license

Issues with publicly shareable minimal reproduction images, commands, dependency versions and browser details are welcome. Algorithm changes should come with matching regression coverage and a before/after comparison of the generated output.

The code and the repository-made test images use the [MIT](LICENSE) license, Copyright (c) 2026 AvroraCL. Third-party dependencies keep their own licenses; rights to input images and derived content are not changed by using this tool.
