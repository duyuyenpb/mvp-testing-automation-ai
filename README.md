# QAForge

> AI-driven test automation framework. **Plan → Generate → Run → Heal.**

QAForge turns plain-English feature descriptions into runnable Playwright + Python tests, runs them, and auto-heals broken locators using Claude.

> **Status:** pre-alpha (Week 4 of 6 — `plan` and `generate` shipped; `run`, `heal` are stubs).

## What's in MVP

| Command | What it does |
|---|---|
| `qaforge plan "<feature>"` | Generates a Markdown test plan and asks for approval |
| `qaforge generate --plan <file>` | Generates `test_*.py` + page objects, py_compile-checks (1 retry), runs pytest once |
| `qaforge run` | Runs Pytest + Playwright, captures structured results *(week 5)* |
| `qaforge heal` | Reads failures, asks Claude for fixes, re-runs *(week 5)* |

Locked-in tech: **Playwright + Python (pytest-playwright)**, **Claude (Sonnet 4.6)**, target app **https://www.saucedemo.com**.

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[test]'
playwright install chromium
cp .env.example .env  # then put your ANTHROPIC_API_KEY in .env

# Smoke checks
qaforge skills                                       # list available skills
qaforge context test-design                          # print resolved system prompt
qaforge ask "where do generated tests live?"        # week 1 — Claude with project context
pytest -m smoke                                      # offline Playwright smoke

# Week 2 — generate a test plan
qaforge plan "User login with email and password"
qaforge plan --file ./requirements.txt
qaforge plan "Add product to cart" --auto            # skip approval prompt

# Week 3-4 — generate test code from a plan
qaforge generate --plan test-plans/001-user-login.md
qaforge generate --plan test-plans/001-user-login.md --no-run    # skip first-run check
qaforge generate --plan test-plans/001-user-login.md --no-retry  # don't retry compile failures
```

You should see Claude answer with **awareness of QAForge's folder structure** (i.e., it mentions `tests/specs/` and `tests/pages/`).

## Repo layout

```
qaforge/                              ← Python package (CLI + library)
│   ├── cli.py                        click CLI entry point
│   ├── llm.py                        Claude API client
│   ├── context.py                    loads knowledge + skills
│   ├── planner.py                    feature → test plan markdown
│   └── integration.py                week 1 smoke
│
├── knowledge.md                      AI global rules (project-wide)
├── skills/
│   ├── test-design/SKILL.md          how to plan tests
│   └── write-test/SKILL.md           how to write Playwright code
├── templates/
│   ├── spec_template.py              reference test for the LLM
│   └── page_template.py              reference POM for the LLM
├── tests/
│   ├── pages/                        generated POMs land here
│   └── specs/                        generated specs land here
├── test-plans/                       generated plans land here
├── conftest.py                       pytest config (baseURL, fixtures)
├── pyproject.toml                    deps + scripts
└── .github/workflows/test.yml        CI template (week 6)
```

## License

MIT
