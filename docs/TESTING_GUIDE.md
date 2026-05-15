# UBIS Testing Guide

Comprehensive guide for testing the Unidentified Body Identification System.

**Primary Functions:**
- Unidentified Body Identification
- Face Recognition for Proclaimed Offenders

For **police-led UAT, sign-off, and hosting handover**, use [UAT & Police Sign-Off](UAT_AND_POLICE_SIGNOFF.md).

---

## Table of Contents

1. [Testing Overview](#1-testing-overview)
2. [Test Environment Setup](#2-test-environment-setup)
3. [Backend Tests (pytest)](#3-backend-tests-pytest)
4. [E2E Tests (Playwright)](#4-e2e-tests-playwright)
5. [Test Data Management](#5-test-data-management)
6. [Writing New Tests](#6-writing-new-tests)
7. [CI/CD Integration](#7-cicd-integration)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Testing Overview

UBIS uses a two-tier testing strategy:

| Layer | Framework | Purpose | Location |
|-------|-----------|---------|----------|
| **Backend** | pytest | API unit/integration tests | `backend/tests/` |
| **E2E** | Playwright | Full user journey tests | `tests/` |

### Test Coverage Summary

| Feature | Backend | E2E |
|---------|:-------:|:---:|
| Authentication | ✓ | ✓ |
| Dashboard | ✓ | ✓ |
| Case Submissions | ✓ | ✓ |
| Search (Photo/Text/Voice) | ✓ | ✓ |
| Face Matching | ✓ | ✓ |
| Proclaimed Offenders | ✓ | ✓ |
| User Management | ✓ | ✓ |
| Audit Logging | ✓ | ✓ |
| Geographic Data | ✓ | - |

---

## 2. Test Environment Setup

### 2.1 Prerequisites

```bash
# Backend testing
cd backend
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-cov httpx  # Test dependencies

# E2E testing
npm install
npx playwright install chromium
```

### 2.2 Seed Test Users

Before running E2E tests, seed the test users:

```bash
cd backend
python -m scripts.seed_test_users
```

This creates the following test accounts:

| Username | Password | Role |
|----------|----------|------|
| `admin` | `changeme` | admin |
| `adminUser` | `adminPass123` | admin |
| `regularUser` | `userPass123` | investigator |
| `userA` | `userAPassword` | investigator |
| `userB` | `userBPassword` | investigator |

### 2.3 Seed Demo Data (Optional)

For matching tests, seed reference photos:

```bash
# Copy sample images
cp ../sample_test_images/*.jpeg reference_photos/

# Seed to database and Qdrant
python -m scripts.seed_demo_repository
```

---

## 3. Backend Tests (pytest)

### 3.1 Running All Backend Tests

```bash
cd backend
source .venv/bin/activate

# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=app --cov-report=html --cov-report=term-missing

# Run specific test file
pytest tests/test_auth.py -v

# Run specific test function
pytest tests/test_auth.py::test_login_success -v
```

### 3.2 Backend Test Files

| File | Description |
|------|-------------|
| `test_auth.py` | Login, token validation, password hashing |
| `test_submissions.py` | Case creation, listing, retrieval |
| `test_search.py` | Multi-modal search functionality |
| `test_match.py` | Face matching against references |
| `test_criminals.py` | Proclaimed offenders CRUD *(out of Phase 1 scope; tests retained for the underlying endpoints)* |
| `test_dashboard.py` | Dashboard statistics |
| `test_audit.py` | Audit log creation and retrieval |
| `test_geo_mapping.py` | Districts and police stations |
| `test_feedback.py` | Match feedback submission |
| `test_health.py` | Health check endpoint |
| `test_matching_e2e.py` | Full matching pipeline |

### 3.3 Test Configuration

Tests use a shared configuration in `conftest.py`:

```python
# backend/tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db

@pytest.fixture(scope="session")
def client():
    init_db()
    return TestClient(app)

@pytest.fixture
def auth_headers(client):
    """Get auth headers for admin user."""
    response = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "changeme"
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

### 3.4 Example Backend Test

```python
# backend/tests/test_submissions.py
import pytest
from pathlib import Path

def test_create_submission(client, auth_headers):
    """Test creating a new submission with an image."""
    test_image = Path(__file__).parent / "fixtures" / "sample.png"
    
    with open(test_image, "rb") as f:
        response = client.post(
            "/api/submissions",
            headers=auth_headers,
            files={"files": ("test.jpg", f, "image/jpeg")},
            data={
                "image_types": '["face_frontal"]',
                "face_condition": "normal"
            }
        )
    
    assert response.status_code == 200
    data = response.json()
    assert "submission_id" in data
    assert data["status"] == "captured"

def test_list_submissions(client, auth_headers):
    """Test listing all submissions."""
    response = client.get("/api/submissions", headers=auth_headers)
    
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

---

## 4. E2E Tests (Playwright)

### 4.1 Running E2E Tests

```bash
# From project root

# Run all E2E tests (frontend auto-starts)
npx playwright test

# Run specific test file
npx playwright test tests/dashboard.spec.cjs

# Run in headed mode (visible browser)
npx playwright test --headed

# Run with UI mode (interactive)
npx playwright test --ui

# Run with trace recording
npx playwright test --trace on

# Generate HTML report
npx playwright show-report
```

### 4.2 E2E Test Files

| File | Description |
|------|-------------|
| `dashboard.spec.cjs` | Dashboard access and display |
| `admin.spec.cjs` | User management (admin only) |
| `new-case.spec.cjs` | Case creation workflow |
| `criminal-records.spec.cjs` | Proclaimed offenders management *(out of Phase 1 scope; may be skipped)* |
| `matching.spec.cjs` | Search and matching tests |

### 4.3 Playwright Configuration

```javascript
// playwright.config.cjs
module.exports = defineConfig({
  testDir: "./tests",
  testMatch: "**/*.spec.cjs",
  fullyParallel: true,
  workers: 1,
  reporter: "html",
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } }
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: true,
  },
});
```

### 4.4 Example E2E Test

```javascript
// tests/dashboard.spec.cjs
const { test, expect } = require('@playwright/test');

test.describe('Dashboard Usability and Functionality', () => {
    test('Admin user can access all features', async ({ page }) => {
        // Navigate to app
        await page.goto('/');
        
        // Wait for login form
        await expect(page.locator('[data-testid="login-form"]')).toBeVisible();
        
        // Fill login credentials
        await page.fill('[data-testid="login-username"]', 'adminUser');
        await page.fill('[data-testid="login-password"]', 'adminPass123');
        await page.click('[data-testid="login-submit"]');
        
        // Verify dashboard loads
        await expect(page.locator('[data-testid="dashboard-page"]')).toBeVisible({ timeout: 10000 });
        await expect(page.locator('[data-testid="dashboard-get-started"]')).toBeVisible();
        await expect(page.locator('[data-testid^="dashboard-stat-"]')).toHaveCount(2);
    });

    test('Login shows error for invalid credentials', async ({ page }) => {
        await page.goto('/');
        await expect(page.locator('[data-testid="login-form"]')).toBeVisible();
        
        await page.fill('[data-testid="login-username"]', 'invalidUser');
        await page.fill('[data-testid="login-password"]', 'wrongPassword');
        await page.click('[data-testid="login-submit"]');
        
        await expect(page.locator('[data-testid="login-error"]')).toBeVisible({ timeout: 5000 });
    });
});
```

### 4.5 Using data-testid Selectors

The UI uses `data-testid` attributes for stable test selectors:

| Element | data-testid |
|---------|-------------|
| Login form | `login-form` |
| Username input | `login-username` |
| Password input | `login-password` |
| Submit button | `login-submit` |
| Login error | `login-error` |
| Dashboard page | `dashboard-page` |
| Get started banner | `dashboard-get-started` |
| Dashboard stats | `dashboard-stat-*` |
| Recent cases table | `dashboard-recent-cases` |
| Case row | `dashboard-case-row-{index}` |
| Admin users table | `admin-users-table` |
| Admin user row | `admin-user-row-{index}` |
| Audit log table | `audit-log-table` |
| Audit log row | `audit-log-row-{index}` |

### 4.6 Test Fixtures

Test data is stored in `tests/fixtures/`:

```
tests/fixtures/
├── test-users.json    # Test user credentials
└── sample.png         # Test image for uploads
```

**test-users.json:**
```json
{
  "admin": {
    "username": "adminUser",
    "password": "adminPass123",
    "role": "admin"
  },
  "regular": {
    "username": "regularUser",
    "password": "userPass123",
    "role": "field_officer"
  }
}
```

---

## 5. Test Data Management

### 5.1 Database Reset

```bash
cd backend

# Backup current database
cp ubis.db ubis.db.backup

# Remove and reinitialize
rm ubis.db

# Reinitialize
python -m scripts.seed_admin
python -m scripts.seed_test_users
```

### 5.2 Qdrant Reset

```bash
cd backend

# Remove Qdrant data
rm -rf qdrant_data/

# Will be recreated on next backend start
```

### 5.3 Test Isolation

Each E2E test should:
1. Login fresh (not rely on previous session)
2. Use unique test data where possible
3. Clean up created resources when practical

---

## 6. Writing New Tests

### 6.1 Backend Test Template

```python
# backend/tests/test_new_feature.py
import pytest

def test_feature_success(client, auth_headers):
    """Test successful feature operation."""
    response = client.post(
        "/api/new-feature",
        headers=auth_headers,
        json={"key": "value"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "expected_field" in data

def test_feature_unauthorized(client):
    """Test feature requires authentication."""
    response = client.post("/api/new-feature", json={"key": "value"})
    assert response.status_code == 401

def test_feature_validation(client, auth_headers):
    """Test feature input validation."""
    response = client.post(
        "/api/new-feature",
        headers=auth_headers,
        json={}  # Missing required field
    )
    assert response.status_code == 422
```

### 6.2 E2E Test Template

```javascript
// tests/new-feature.spec.cjs
const { test, expect } = require('@playwright/test');

test.describe('New Feature', () => {
    test.beforeEach(async ({ page }) => {
        // Login before each test
        await page.goto('/');
        await expect(page.locator('[data-testid="login-form"]')).toBeVisible();
        await page.fill('[data-testid="login-username"]', 'regularUser');
        await page.fill('[data-testid="login-password"]', 'userPass123');
        await page.click('[data-testid="login-submit"]');
        await expect(page.locator('[data-testid="dashboard-page"]')).toBeVisible({ timeout: 10000 });
    });

    test('User can access new feature', async ({ page }) => {
        // Navigate to feature
        await page.click('button:has-text("New Feature")');
        
        // Verify feature loaded
        await expect(page.getByText('New Feature Title')).toBeVisible();
    });

    test('User can perform action in new feature', async ({ page }) => {
        await page.click('button:has-text("New Feature")');
        
        // Fill form
        await page.fill('[data-testid="feature-input"]', 'test value');
        await page.click('[data-testid="feature-submit"]');
        
        // Verify success
        await expect(page.getByText('Success')).toBeVisible();
    });
});
```

### 6.3 Adding data-testid to UI

When adding new UI elements, include `data-testid` for testability:

```jsx
// In ubis-pwa.jsx
<button 
  data-testid="new-feature-button"
  onClick={handleClick}
>
  New Feature
</button>

<input 
  data-testid="new-feature-input"
  type="text"
  value={value}
  onChange={onChange}
/>

<table data-testid="new-feature-table">
  {rows.map((row, i) => (
    <tr key={row.id} data-testid={`new-feature-row-${i}`}>
      ...
    </tr>
  ))}
</table>
```

---

## 7. CI/CD Integration

### 7.1 GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install pytest pytest-cov
      
      - name: Run tests
        run: |
          cd backend
          pytest tests/ -v --cov=app

  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Install Playwright
        run: npx playwright install chromium
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install backend dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      
      - name: Seed test data
        run: |
          cd backend
          python -m scripts.seed_admin
          python -m scripts.seed_test_users
      
      - name: Start backend
        run: |
          cd backend
          uvicorn app.main:app --port 8000 &
          sleep 5
      
      - name: Run E2E tests
        run: npx playwright test
      
      - name: Upload report
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: playwright-report
          path: playwright-report/
```

---

## 8. Troubleshooting

### 8.1 Backend Tests Failing

**Database not initialized:**
```bash
cd backend
python -c "from app.database import init_db; init_db()"
```

**Missing test users:**
```bash
python -m scripts.seed_admin
python -m scripts.seed_test_users
```

**Import errors:**
```bash
pip install -r requirements.txt --force-reinstall
```

### 8.2 E2E Tests Failing

**Playwright not installed:**
```bash
npx playwright install chromium
```

**Backend not running:**
```bash
# Start backend manually
cd backend && uvicorn app.main:app --port 8000 &
```

**Test users not seeded:**
```bash
cd backend
python -m scripts.seed_test_users
```

**Selector not found:**
- Check that `data-testid` exists in the UI
- Use Playwright UI mode to inspect: `npx playwright test --ui`
- Increase timeout: `{ timeout: 10000 }`

### 8.3 Flaky Tests

For flaky tests, consider:
1. Adding explicit waits: `await expect(...).toBeVisible({ timeout: 10000 })`
2. Using `test.slow()` for slow operations
3. Adding retry logic in Playwright config: `retries: 2`

### 8.4 Viewing Test Reports

**Playwright HTML report:**
```bash
npx playwright show-report
```

**pytest coverage report:**
```bash
cd backend
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html
```

---

## Quick Reference

### Run All Tests
```bash
# Backend
cd backend && pytest tests/ -v

# E2E
npx playwright test
```

### Run Specific Test
```bash
# Backend
pytest tests/test_auth.py::test_login_success -v

# E2E
npx playwright test tests/dashboard.spec.cjs
```

### Debug Mode
```bash
# Backend with verbose output
pytest tests/ -v -s

# E2E with visible browser
npx playwright test --headed --debug
```

### Generate Reports
```bash
# Backend coverage
pytest tests/ --cov=app --cov-report=html

# E2E report
npx playwright show-report
```

---

*Last updated: March 2026*
