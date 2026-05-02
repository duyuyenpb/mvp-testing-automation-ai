# Getting Started with QAForge

Zero → first healed test in ~10 minutes.

## 1. Install (2 min)

Install Python 3.10+ first. On Windows, install Python from https://www.python.org/downloads/windows/ and check **Add python.exe to PATH**.

macOS / Linux:

```bash
git clone https://github.com/duyuyenpb/mvp-testing-automation-ai.git
cd mvp-testing-automation-ai
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[test]'
playwright install chromium
```

Windows PowerShell:

```powershell
git clone https://github.com/duyuyenpb/mvp-testing-automation-ai.git
cd mvp-testing-automation-ai
.\scripts\setup-local.ps1
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks the script, run this once in the repo shell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup-local.ps1
```

## 2. Add your Claude API key (1 min)

```bash
cp .env.example .env
```

Open `.env` and paste your key (get one at https://console.anthropic.com/settings/keys):

```
ANTHROPIC_API_KEY=sk-ant-...
```

Verify the wiring:

```bash
qaforge skills
qaforge ask "where do generated tests live?"
```

If you see `tests/specs/` in the answer, you're ready. If you see `ANTHROPIC_API_KEY is missing`, re-check step 2.

For a no-API-key local check, run:

```powershell
.\scripts\verify-local.ps1
```

## 3. Plan your first test (1 min)

```bash
qaforge plan "User login with email and password"
```

QAForge will:
1. Send your description + the `test-design` SKILL to Claude
2. Print a Markdown test plan with TC-001, TC-002, ...
3. Ask: **Approve? [y]es / [n]o / [e]dit**

Type `y` to save it to `test-plans/001-user-login.md`.

> **Tip:** Use `qaforge plan "..." --auto` to skip approval, or `qaforge plan --file requirements.txt` for longer specs.

## 4. Generate runnable code (2 min)

```bash
qaforge generate --plan test-plans/001-user-login.md
```

What happens:
1. Claude reads the plan + the `write-test` SKILL + the gold-standard examples in `tests/`
2. Emits one spec at `tests/specs/test_user_login.py` and any new page objects under `tests/pages/`
3. Runs `python -m py_compile` on every file (1 retry on syntax errors)
4. Runs `pytest --collect-only` then `pytest <spec>` once
5. Reports pass/fail

If compile fails twice, you'll see the errors. Most fixes go into `skills/write-test/SKILL.md` — make the rule more specific, regenerate.

## 5. Run the suite

```bash
qaforge run                            # all of tests/specs/
qaforge run tests/specs/test_user_login.py  # one file
```

You'll get a summary like `3 passed, 1 failed in 12.4s` and a brief per-failure dump.

## 6. Heal failures automatically

```bash
qaforge heal              # interactive — shows diff before applying
qaforge heal --auto       # unattended; max 3 attempts
qaforge heal --max-attempts 5
```

QAForge picks the first failing test, sends Claude:
- The full spec source
- Every page object the spec imports
- The pytest traceback

Claude emits a JSON patch (using `skills/heal-test/SKILL.md`). You review the diff, type `y` to apply, and it re-runs. Repeats until green or attempts exhausted.

If the failure is a real bug (assertion mismatch on real data), Claude returns `{"files": []}` and the loop stops — your test caught a regression, fix the app.

## 7. Scaffold a new project

Want to use QAForge for a different app?

```bash
qaforge init ~/my-app-tests --name my-app-tests
cd ~/my-app-tests
# Edit knowledge.md with YOUR app's URL, conventions, locator strategy
# Edit skills/write-test/SKILL.md to reference YOUR gold-standard tests
qaforge plan "..."
```

## Where to look when things go wrong

| Symptom | First place to look |
|---|---|
| `ANTHROPIC_API_KEY is missing` | `.env` — see step 2 |
| `Executable doesn't exist` (Playwright) | Run `playwright install chromium` |
| Generated test doesn't compile | `skills/write-test/SKILL.md` — add a "NEVER do this" example |
| Generated test compiles but fails on first run | Same SKILL — make the locator pattern more explicit |
| Healer loop won't fix a failure | Check the diff — if Claude returns `{"files": []}`, it thinks it's a real bug |
| Plans miss edge cases | `skills/test-design/SKILL.md` — the most important file you'll edit |

## What's in MVP vs not

✅ MVP: `plan`, `generate`, `run`, `heal`, `init`, GitHub Actions template
❌ Out of scope (v0.2+): visual regression, multi-LLM, npm publish, OpenAPI import, dashboards, mobile, accessibility

See [README.md](README.md) for the full table.
