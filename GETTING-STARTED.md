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

## 2. Configure your LLM provider (1 min)

```bash
cp .env.example .env
```

Open `.env` and choose your provider, model, and API key. For Codex/OpenAI:

```
QAFORGE_LLM_PROVIDER=codex
QAFORGE_MODEL=gpt-5.2-codex
OPENAI_API_KEY=sk-...
```

Other supported providers:

```text
QAFORGE_LLM_PROVIDER=anthropic
QAFORGE_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
```

```text
QAFORGE_LLM_PROVIDER=gemini
QAFORGE_MODEL=gemini-2.5-pro
GEMINI_API_KEY=...
```

Verify the wiring:

```bash
qaforge skills
qaforge ask "where do generated tests live?"
```

If you see `tests/specs/` in the answer, you're ready. If you see a missing-key message, re-check step 2.

For a no-API-key local check, run:

```powershell
.\scripts\verify-local.ps1
```

## 3. Plan your first test (1 min)

```bash
qaforge plan "User login with email and password"
```

QAForge will:
1. Send your description + the `test-design` SKILL to the configured LLM
2. Print a Markdown test plan with TC-001, TC-002, ...
3. Ask: **Approve? [y]es / [n]o / [e]dit**

Type `y` to save it to `test-plans/001-user-login.md`.

> **Tip:** Use `qaforge plan "..." --auto` to skip approval, or `qaforge plan --file requirements.txt` for longer specs.

## 4. Generate runnable code (2 min)

```bash
qaforge generate --plan test-plans/001-user-login.md
```

What happens:
1. The configured LLM reads the plan + the `write-test` SKILL + the gold-standard examples in `tests/`
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
QAForge also writes an HTML report to `test-results/qaforge-report.html` after each run.

## 6. Heal failures automatically

```bash
qaforge heal              # interactive — shows diff before applying
qaforge heal --auto       # unattended; max 3 attempts
qaforge heal --max-attempts 5
```

QAForge picks the first failing test, sends the configured LLM:
- The full spec source
- Every page object the spec imports
- The pytest traceback

The configured LLM emits a JSON patch (using `skills/heal-test/SKILL.md`). You review the diff, type `y` to apply, and it re-runs. Repeats until green or attempts exhausted.

If the failure is a real bug (assertion mismatch on real data), the LLM returns `{"files": []}` and the loop stops — your test caught a regression, fix the app.

## 7. Scaffold a new project

Use this path when you want to point QAForge at your own web app instead of the default Sauce Demo target.

```bash
qaforge init ~/my-app-tests --name my-app-tests
cd ~/my-app-tests
```

The scaffold includes `knowledge.md`, `skills/`, `templates/`, `tests/`, `test-plans/`, `.env.example`, and CI starter files.

### Configure environment variables

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Set:

```text
QAFORGE_LLM_PROVIDER=codex
QAFORGE_MODEL=gpt-5.2-codex
OPENAI_API_KEY=sk-...
BASE_URL=https://your-product.example.com
```

`BASE_URL` is the application under test. Generated tests should navigate with relative paths like `page.goto("/")`, so the same suite can run against local, staging, or production by changing this value.

### Teach QAForge your product

Edit `knowledge.md` before generating tests. Replace the Sauce Demo notes with your product details:

- product URL and main user journeys
- login method, test accounts, and required roles
- pages/screens that matter most
- data setup rules and cleanup expectations
- locator strategy, especially preferred `data-testid` attributes
- behaviors that are out of scope for the first test suite

Keep secrets out of `knowledge.md`. Put credentials in `.env` and reference them from fixtures or generated Page Objects.

### Add or update gold-standard examples

QAForge generates better tests when the examples match your app. Update the files under:

```text
tests/specs/
tests/pages/
templates/
```

Use the existing login examples as the pattern: specs describe behavior, while Page Objects own selectors and page actions.

### Generate a test plan

Describe one product feature in plain English:

```bash
qaforge plan "User can sign in, see the dashboard, and sign out"
```

For longer requirements, put the feature description in a file:

```bash
qaforge plan --file ./requirements/login.md
```

Review the Markdown plan in the terminal. Approve it when it captures the happy path, negative cases, edge cases, and clear expected results. Approved plans are saved in `test-plans/`.

### Generate test code

Use the saved plan path:

```bash
qaforge generate --plan test-plans/001-user-login.md
```

QAForge writes generated specs to `tests/specs/` and Page Objects to `tests/pages/`. It also compile-checks the generated files and can run the new spec once.

If the first run fails because the generated test guessed a selector incorrectly, tighten the guidance in `knowledge.md` or `skills/write-test/SKILL.md`, then regenerate or use healing.

### Run and heal

Run the full suite:

```bash
qaforge run
```

Run one spec:

```bash
qaforge run tests/specs/test_user_login.py
```

Heal locator drift or small timing issues:

```bash
qaforge heal
```

Use `qaforge heal --auto` only after you are comfortable with the diffs it produces.

### Repeat feature by feature

Start with a small, stable workflow such as login or account creation. Then add plans for checkout, onboarding, settings, reports, or other core user journeys. Commit the generated plans, specs, Page Objects, `knowledge.md`, and skill updates so the suite improves over time.

### Recommended first product checklist

- Your app is reachable from the machine running tests.
- `.env` has `QAFORGE_LLM_PROVIDER`, `QAFORGE_MODEL`, the matching API key, and `BASE_URL`.
- Test credentials are available through environment variables or fixtures.
- `knowledge.md` describes your app, users, data, and selector conventions.
- At least one gold-standard spec and Page Object match your app.
- `qaforge plan`, `qaforge generate`, and `qaforge run` complete for one small feature.

## Where to look when things go wrong

| Symptom | First place to look |
|---|---|
| Missing API key | `.env` — see step 2 and configure the key for your selected provider |
| `Executable doesn't exist` (Playwright) | Run `playwright install chromium` |
| No HTML report after `qaforge run` | Check `test-results/qaforge-report.html`; the folder is gitignored |
| Generated test doesn't compile | `skills/write-test/SKILL.md` — add a "NEVER do this" example |
| Generated test compiles but fails on first run | Same SKILL — make the locator pattern more explicit |
| Healer loop won't fix a failure | Check the diff — if the LLM returns `{"files": []}`, it thinks it's a real bug |
| Plans miss edge cases | `skills/test-design/SKILL.md` — the most important file you'll edit |

## What's in MVP vs not

✅ MVP: `plan`, `generate`, `run`, `heal`, `init`, configurable LLM provider, GitHub Actions template
❌ Out of scope (v0.2+): visual regression, npm publish, OpenAPI import, dashboards, mobile, accessibility

See [README.md](README.md) for the full table.
