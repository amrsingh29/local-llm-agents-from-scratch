# Gemma Local AI — Documentation Guide

This project uses **MkDocs** (specifically the `mkdocs-material` theme) to generate the static site documentation. This guide explains how the system was originally configured from scratch, how the architecture works, and how to maintain or expand it.

---

## 1. Initial Setup from Scratch

If you ever need to rebuild this system from scratch:

1. **Install Dependencies:**
   ```bash
   pip install mkdocs-material pymdown-extensions
   ```
2. **Configuration (`mkdocs.yml`):**
   The project root contains `mkdocs.yml`. The critical pieces in this configuration:
   - `docs_dir: docs` — Tells MkDocs to look in the `docs/` folder for content.
   - `markdown_extensions` > `pymdownx.snippets` — Enables dynamic code injection directly from `.py` files.
3. **Exclusions (`.gitignore`):**
   MkDocs outputs the generated static HTML to a folder named `site/`. This is ignored via `.gitignore` to keep the repository clean.

---

## 2. The Architecture (Symlinks)

The core requirement of this project was to generate documentation **without** fundamentally changing the underlying directory structure. 

MkDocs strictly requires all markdown files to live under a designated "docs" directory (which we named `docs/`). However, all lesson resources (`01-installation`, `02-llm-fundamentals`) were stored directly at the repository root.

**The Solution:**
Instead of physically moving those root folders into a nested `docs/` directory, we created **Symbolic Links (symlinks)**. 
- Inside the `docs/` folder, `01-installation` is actually a shortcut pointing back to `../01-installation`.
- This allows you to work exactly how you always have (editing files in the root folder structure), while MkDocs perfectly discovers them via the symlink mirror.

---

## 3. How to Update Content

Because MkDocs relies on "auto-discovery," adding content is nearly entirely automated. You do not need to update `mkdocs.yml` when writing new lessons.

### Adding completely new files to existing folders
If you create a new file or move a `.md` file inside an existing structure (e.g., inside `02-llm-fundamentals/notes/`), **you do nothing.**
- The `docs/02-llm-fundamentals` symlink will automatically catch it.
- MkDocs will immediately generate the page and place it into the left sidebar.

### Creating a brand new top-level folder
If you create a completely new phase for the curriculum, you *must* explicitly symlink it so MkDocs knows it exists.
1. Create your new directory: `mkdir 08-advanced-agents`
2. Create the symlink inside `docs/`:
   ```bash
   ln -s ../08-advanced-agents docs/08-advanced-agents
   ```
From that point forward, anything placed in `08-advanced-agents` is auto-discovered natively!

---

## 4. Embedding Live Code (Snippets)

We use the `pymdownx.snippets` extension to prevent copy-pasting Python code into Markdown files — which easily falls out of sync.

Whenever you want to display the contents of a Python file directly inside your markdown documentation, insert this exact block syntax into your `.md` file:

```markdown
```python title="Your Target File Title.py"
--8<-- "01-installation/code/my_script.py"
```
```

**Important rules for Snippets:**
- The path provided (e.g., `01-installation/code/my_script.py`) must correspond to its path **relative to the root of the repository**, regardless of what sub-folder the Markdown file lives in!
- You can change `python` to any language identifier (e.g., `bash`, `json`), and `title="..."` is optional but highly recommended.

---

## 5. Local Server & Deployment

### Starting the Server
To view the live site locally while editing, open your terminal and run:
```bash
source .venv/bin/activate
mkdocs serve
```
By default, this will run at `http://127.0.0.1:8000`. If port 8000 is already occupied by a FastAPI app (which often happens in this project), you can manually specify a free port:
```bash
mkdocs serve -a 127.0.0.1:8123
```

### Restarting the Server
The `mkdocs serve` command uses **LiveReload**, so it automatically updates and refreshes your browser when you modify or add files. 

However, if you physically **move** files between directories (breaking macOS symlink watchers), or if you make major structural changes to `mkdocs.yml`, the watcher may fail to pick it up. 
To manually restart the server:
1. Go to your terminal running `mkdocs serve`.
2. Press `Ctrl+C` to terminate the process.
3. Press `Up Arrow` and hit `Enter` to run the command again.

### GitHub Pages Deployment
In `.github/workflows/pages.yml`, there is a workflow that triggers every time code is pushed to the `main` branch. 

**How the cloud build works:**
1. GitHub spins up a temporary server and installs Python, MkDocs, and the Material theme.
2. It runs `mkdocs gh-deploy --force`.
3. This command builds the HTML site internally and silently pushes the compiled site into a hidden branch on your repository called `gh-pages` (keeping your `main` branch clean).

**What you need to do on GitHub (First time only):**
To make the site public initially, you must tell GitHub to serve the `gh-pages` branch:
1. Go to your repository on **GitHub.com**.
2. Click the **Settings** tab.
3. In the left sidebar, click **Pages**.
4. Under the "Source" drop-down, select **Deploy from a branch**.
5. Under the "Branch" drop-down, select **`gh-pages`** (and leave the folder as `/ (root)`), then click **Save**.

Once saved, GitHub will generate your live URL. From then on, every time you push code to `main`, the public site will update automatically!
