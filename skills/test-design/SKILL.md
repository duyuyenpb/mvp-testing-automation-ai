# SKILL: test-design

> Loaded by `qaforge plan`. Read `knowledge.md` first; this skill never overrides it.

## Purpose

Convert a plain-English feature description into a complete, reviewable Markdown test plan that another QAForge skill can later turn into Playwright + Python code.

## When you are invoked

Input you will receive:
- A free-form feature description (one sentence to several paragraphs).
- The `BASE_URL` of the target app (assume saucedemo.com for MVP).
- Optional context (existing test plans, page structure).

Output you must produce:
- **A single Markdown document** in the exact format below.
- Nothing else — no preamble, no closing remarks, no code fences around the whole thing.

## Process — follow in order

1. **Restate the feature** in your own words in 1–3 sentences. If the description is ambiguous, list assumptions explicitly under "Preconditions".
2. **Identify the user journey:** Who is the actor? What screen do they start on? What's the success state?
3. **Derive at minimum 3 test cases:** one happy path, one negative case, one edge case. Add more (priority P0/P1) if the feature naturally has them.
4. **Classify each test case** as `UI`, `API`, or `Hybrid`:
   - `UI`: only browser interactions
   - `API`: only HTTP calls
   - `Hybrid`: API setup (e.g., create user) + UI verification
5. **Make every step observable.** "User logs in" is not a step. "Click the Login button" is.
6. **Make every expected result verifiable.** "User sees the products page" → "URL contains `/inventory.html` AND a heading with text 'Products' is visible".
7. **Call out what's NOT covered** under "Out of Scope" — this prevents scope creep at generation time.

## Output format — required, exact

Use this structure verbatim. Replace `<...>` with content. Do not add or remove sections.

````markdown
# Test Plan: <feature name>

## Feature Summary
<1–3 sentences restating the feature.>

## Preconditions
- <env, accounts, data, assumptions>

## Test Cases

### TC-001: <happy path title>
- **Type:** UI
- **Priority:** P0
- **Preconditions:** <test-case-specific setup, or "none">
- **Steps:**
  1. <action>
  2. <action>
- **Expected Result:** <observable outcome, web-first verifiable>

### TC-002: <negative case title>
- **Type:** UI
- **Priority:** P1
- **Preconditions:** <...>
- **Steps:**
  1. <...>
- **Expected Result:** <...>

### TC-003: <edge case title>
- **Type:** UI | API | Hybrid
- **Priority:** P1 | P2
- **Preconditions:** <...>
- **Steps:**
  1. <...>
- **Expected Result:** <...>

## Out of Scope
- <thing not covered>
- <thing not covered>
````

## Quality bar — self-check before returning

- [ ] At least 3 test cases (happy / negative / edge).
- [ ] Each TC has Type, Priority, Steps, Expected Result.
- [ ] Every step is a concrete action, not a goal.
- [ ] Every expected result references a verifiable signal (URL, visible text, status code, element state).
- [ ] No mention of frameworks, locators, or code — those belong to the `write-test` skill.
- [ ] No tests for visual regression, performance, or accessibility (out of MVP scope).

## Common mistakes — NEVER do these

| ❌ Don't | ✅ Do |
|---|---|
| "User can log in successfully" (vague step) | "1. Enter `standard_user` in the username field. 2. Enter `secret_sauce` in the password field. 3. Click Login." |
| "User sees the dashboard" (unverifiable) | "URL ends with `/inventory.html` and the heading `Products` is visible." |
| Only one test case | Always at least one happy + one negative + one edge case |
| Mentioning `get_by_role`, CSS selectors, `expect(...)` | Plans are framework-free. Save selectors for the writer skill. |
| Saying "verify the page works" | Pick a specific signal: a heading, a URL, an element count |
| Wrapping the whole document in ```` ``` ```` fences | Output raw Markdown only |

## Worked example (saucedemo login)

Input: `User login with email and password`

Output:

````markdown
# Test Plan: User login

## Feature Summary
A registered user enters their username and password on the login page and is taken to the products inventory page on success. Invalid credentials show an inline error and keep the user on the login page.

## Preconditions
- Target app is https://www.saucedemo.com.
- Demo accounts exist: `standard_user / secret_sauce`, `locked_out_user / secret_sauce`.

## Test Cases

### TC-001: Standard user logs in with valid credentials
- **Type:** UI
- **Priority:** P0
- **Preconditions:** none
- **Steps:**
  1. Navigate to `/`.
  2. Enter `standard_user` in the Username field.
  3. Enter `secret_sauce` in the Password field.
  4. Click the Login button.
- **Expected Result:** URL ends with `/inventory.html` and the page title `Products` is visible.

### TC-002: Login fails with invalid password
- **Type:** UI
- **Priority:** P1
- **Preconditions:** none
- **Steps:**
  1. Navigate to `/`.
  2. Enter `standard_user` in the Username field.
  3. Enter `wrong_password` in the Password field.
  4. Click the Login button.
- **Expected Result:** An error message containing `Username and password do not match` is visible, and the URL is still `/`.

### TC-003: Locked-out user is rejected
- **Type:** UI
- **Priority:** P1
- **Preconditions:** none
- **Steps:**
  1. Navigate to `/`.
  2. Enter `locked_out_user` in the Username field.
  3. Enter `secret_sauce` in the Password field.
  4. Click the Login button.
- **Expected Result:** An error message containing `Sorry, this user has been locked out` is visible.

## Out of Scope
- Password reset flow.
- Session timeout / remember-me behavior.
- Visual regression of the login page.
````
