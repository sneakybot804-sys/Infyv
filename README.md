# aviveera795-project

## Phase 5A - Highlight Scoring

After analyzing a video (Phase 4A) you can score its scenes into a ranked
highlight report. The scorer is generic and game-agnostic: it uses only the
signals in `analysis.json` (motion, brightness, static score, duration, idle
and black-screen overlap). It does not use Ollama, FFmpeg, audio or OCR.

```bash
python app.py    # choose option 3, then provide the analysis.json path
```

Output: `output/<video_name>_highlight.json` (schema `5a.1`, never
overwritten). Each scene gets a 0-100 `score`, a `rank`, a `classification`
(Excellent / Good / Average / Ignore) and a `components` breakdown.

Scoring is fully configurable via `HighlightScoringConfig`. See `SCORING.md`
for the formula, weighting and thresholds, and `JSON_SCHEMA.md` for the
output schema.

## OCR Setup (Phase 5B)

Phase 5B extracts on-screen HUD text (menu option 5) using OCR. It has two
separate parts you must install:

1. **The Python wrapper** (`pytesseract`) — installed from `requirements.txt`.
2. **The native Tesseract OCR engine** — an external program you install
   yourself. This project does **not** bundle, download, or auto-install it.

OCR only runs on the configured static regions (ROIs) of a few sampled
frames per scene; it never OCRs full frames.

### 1. Install the Python dependencies

```bash
pip install -r requirements.txt
```

This installs `pytesseract` (the Python binding). The binding alone does not
include the OCR engine — continue to step 2.

### 2. Install the native Tesseract binary

- **Windows:** download and run the installer from the UB-Mannheim build
  (`https://github.com/UB-Mannheim/tesseract/wiki`). Note the install
  directory, typically `C:\Program Files\Tesseract-OCR`.
- **macOS:** `brew install tesseract`
- **Linux (Debian/Ubuntu):** `sudo apt-get install tesseract-ocr`

English language data (`eng`) is included by default, which is all Phase 5B
requires.

### 3. Add Tesseract to PATH (Windows)

Add the install directory (e.g. `C:\Program Files\Tesseract-OCR`) to your
system `PATH` so `tesseract.exe` is discoverable:

- Windows Settings → *Edit the system environment variables* → *Environment
  Variables* → select `Path` → *Edit* → *New* → paste the directory → OK.
- Open a **new** terminal afterwards so the updated PATH takes effect.

Alternatively, without editing PATH, point `pytesseract` at the binary in
your own environment/config:

```python
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

### 4. Verify the installation

```bash
tesseract --version        # should print the Tesseract version
python -c "import pytesseract; print(pytesseract.get_tesseract_version())"
```

If both commands print a version, OCR is ready. Run it via:

```bash
python app.py    # choose option 5 (Extract HUD text / OCR)
```

Output: `output/<video_name>_ocr.json` (schema `5b.1`, never overwritten).

### 5. Common Windows troubleshooting

- **`TesseractNotFoundError` / "tesseract is not installed or it's not in
  your PATH":** the native binary isn't on PATH. Re-check step 3, open a new
  terminal, or set `tesseract_cmd` explicitly as shown above.
- **`tesseract --version` works in one terminal but not the app:** the app
  was launched from a terminal opened *before* the PATH change. Close and
  reopen the terminal / IDE.
- **Installed but still not found:** confirm you added the folder that
  contains `tesseract.exe` (not a parent folder), and that the installer
  actually completed.
- **Non-English or missing language data:** Phase 5B only needs `eng`
  (bundled). If you removed it, re-run the installer and keep the English
  language pack.
- **Poor accuracy on stylized HUD fonts:** expected for some games; the
  extractor already applies grayscale/threshold/upscale to ROI crops. Tune
  the ROIs and preprocessing in `OcrConfig`.

The Python dependency (`pytesseract`) and the native executable are
deliberately kept separate: the project declares only the Python binding and
never installs system software on your behalf.

## Getting started

To make it easy for you to get started with GitLab, here's a list of recommended next steps.

Already a pro? Just edit this README.md and make it your own. Want to make it easy? [Use the template at the bottom](#editing-this-readme)!

## Add your files

* [Create](https://docs.gitlab.com/user/project/repository/web_editor/#create-a-file) or [upload](https://docs.gitlab.com/user/project/repository/web_editor/#upload-a-file) files
* [Add files using the command line](https://docs.gitlab.com/topics/git/add_files/#add-files-to-a-git-repository) or push an existing Git repository with the following command:

```
cd existing_repo
git remote add origin https://gitlab.com/aviveera795-group/aviveera795-project.git
git branch -M main
git push -uf origin main
```

## Integrate with your tools

* [Set up project integrations](https://gitlab.com/aviveera795-group/aviveera795-project/-/settings/integrations)

## Collaborate with your team

* [Invite team members and collaborators](https://docs.gitlab.com/user/project/members/)
* [Create a new merge request](https://docs.gitlab.com/user/project/merge_requests/creating_merge_requests/)
* [Automatically close issues from merge requests](https://docs.gitlab.com/user/project/issues/managing_issues/#closing-issues-automatically)
* [Enable merge request approvals](https://docs.gitlab.com/user/project/merge_requests/approvals/)
* [Set auto-merge](https://docs.gitlab.com/user/project/merge_requests/auto_merge/)

## Test and Deploy

Use the built-in continuous integration in GitLab.

* [Get started with GitLab CI/CD](https://docs.gitlab.com/ci/quick_start/)
* [Analyze your code for known vulnerabilities with Static Application Security Testing (SAST)](https://docs.gitlab.com/user/application_security/sast/)
* [Deploy to Kubernetes, Amazon EC2, or Amazon ECS using Auto Deploy](https://docs.gitlab.com/topics/autodevops/requirements/)
* [Use pull-based deployments for improved Kubernetes management](https://docs.gitlab.com/user/clusters/agent/)
* [Set up protected environments](https://docs.gitlab.com/ci/environments/protected_environments/)

***

# Editing this README

When you're ready to make this README your own, just edit this file and use the handy template below (or feel free to structure it however you want - this is just a starting point!). Thanks to [makeareadme.com](https://www.makeareadme.com/) for this template.

## Suggestions for a good README

Every project is different, so consider which of these sections apply to yours. The sections used in the template are suggestions for most open source projects. Also keep in mind that while a README can be too long and detailed, too long is better than too short. If you think your README is too long, consider utilizing another form of documentation rather than cutting out information.

## Name
Choose a self-explaining name for your project.

## Description
Let people know what your project can do specifically. Provide context and add a link to any reference visitors might be unfamiliar with. A list of Features or a Background subsection can also be added here. If there are alternatives to your project, this is a good place to list differentiating factors.

## Badges
On some READMEs, you may see small images that convey metadata, such as whether or not all the tests are passing for the project. You can use Shields to add some to your README. Many services also have instructions for adding a badge.

## Visuals
Depending on what you are making, it can be a good idea to include screenshots or even a video (you'll frequently see GIFs rather than actual videos). Tools like ttygif can help, but check out Asciinema for a more sophisticated method.

## Installation
Within a particular ecosystem, there may be a common way of installing things, such as using Yarn, NuGet, or Homebrew. However, consider the possibility that whoever is reading your README is a novice and would like more guidance. Listing specific steps helps remove ambiguity and gets people to using your project as quickly as possible. If it only runs in a specific context like a particular programming language version or operating system or has dependencies that have to be installed manually, also add a Requirements subsection.

## Usage
Use examples liberally, and show the expected output if you can. It's helpful to have inline the smallest example of usage that you can demonstrate, while providing links to more sophisticated examples if they are too long to reasonably include in the README.

## Support
Tell people where they can go to for help. It can be any combination of an issue tracker, a chat room, an email address, etc.

## Roadmap
If you have ideas for releases in the future, it is a good idea to list them in the README.

## Contributing
State if you are open to contributions and what your requirements are for accepting them.

For people who want to make changes to your project, it's helpful to have some documentation on how to get started. Perhaps there is a script that they should run or some environment variables that they need to set. Make these steps explicit. These instructions could also be useful to your future self.

You can also document commands to lint the code or run tests. These steps help to ensure high code quality and reduce the likelihood that the changes inadvertently break something. Having instructions for running tests is especially helpful if it requires external setup, such as starting a Selenium server for testing in a browser.

## Authors and acknowledgment
Show your appreciation to those who have contributed to the project.

## License
For open source projects, say how it is licensed.

## Project status
If you have run out of energy or time for your project, put a note at the top of the README saying that development has slowed down or stopped completely. Someone may choose to fork your project or volunteer to step in as a maintainer or owner, allowing your project to keep going. You can also make an explicit request for maintainers.
