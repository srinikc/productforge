"""
E2E Test Script for Product Factory Ingestion System

Tests the full flow:
1. Send conversation via intake API
2. Verify conversation stored
3. Test compilation endpoint
4. Test ideas/projects endpoints
5. Test change packages

Run: python test_e2e.py
"""

import json
import urllib.request
import urllib.error
import sys
import time

BASE_URL = "http://localhost:8765"
PASSED = 0
FAILED = 0


def test(name, method, path, data=None, expected_status=200):
    """Make API request and verify response."""
    global PASSED, FAILED
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            result = json.loads(resp.read().decode())
            if status == expected_status:
                print(f"  PASS: {name} (status={status})")
                PASSED += 1
                return result
            else:
                print(f"  FAIL: {name} (expected {expected_status}, got {status})")
                FAILED += 1
                return result
    except urllib.error.HTTPError as e:
        print(f"  FAIL: {name} (HTTP {e.code})")
        FAILED += 1
        return None
    except Exception as e:
        print(f"  FAIL: {name} ({e})")
        FAILED += 1
        return None


def run_tests():
    """Run all E2E tests."""
    print("\n=== Product Factory E2E Tests ===\n")

    # Test 1: Health check
    print("[1] Health Check")
    test("GET /api/v1/health", "GET", "/api/v1/health")

    # Test 2: Stats endpoint
    print("\n[2] Stats Endpoint")
    stats = test("GET /api/v1/stats", "GET", "/api/v1/stats")
    if stats:
        print(f"       conversations={stats.get('conversations', 0)}, ideas={stats.get('ideas', 0)}")

    # Test 3: Send conversation (save_idea)
    print("\n[3] Send Conversation (save_idea)")
    conv1 = test("POST /api/v1/intake (save_idea)", "POST", "/api/v1/intake", {
        "source_platform": "manual",
        "intent": "save_idea",
        "title": "Test: Task Management Idea",
        "messages": [
            {"role": "user", "content": "I want to build a task management app with AI prioritization"},
            {"role": "assistant", "content": "Great idea! Let me capture this as a feature idea."}
        ]
    })
    conv1_id = conv1.get("id") if conv1 else None
    if conv1_id:
        print(f"       conversation_id={conv1_id[:8]}...")

    # Test 4: Send conversation (new_project)
    print("\n[4] Send Conversation (new_project)")
    conv2 = test("POST /api/v1/intake (new_project)", "POST", "/api/v1/intake", {
        "source_platform": "chatgpt",
        "intent": "new_project",
        "title": "Test: New Dashboard Project",
        "project_name": "test-dashboard-v1",
        "messages": [
            {"role": "user", "content": "Create a new analytics dashboard project"},
            {"role": "assistant", "content": "I'll help you create a new project for an analytics dashboard."}
        ]
    })

    # Test 5: Send conversation (modify_project)
    print("\n[5] Send Conversation (modify_project)")
    conv3 = test("POST /api/v1/intake (modify_project)", "POST", "/api/v1/intake", {
        "source_platform": "gemini",
        "intent": "modify_project",
        "title": "Test: Add Dark Mode",
        "target_project_name": "myworld",
        "messages": [
            {"role": "user", "content": "Add dark mode support to the existing project"},
            {"role": "assistant", "content": "I'll create a change package for adding dark mode."}
        ]
    })

    # Test 6: List conversations
    print("\n[6] List Conversations")
    convs = test("GET /api/v1/conversations", "GET", "/api/v1/conversations")
    if convs:
        print(f"       total={convs.get('total', 0)}")

    # Test 7: Filter conversations by source
    print("\n[7] Filter Conversations by Source")
    filtered = test("GET /api/v1/conversations?source=chatgpt", "GET", "/api/v1/conversations?source=chatgpt")
    if filtered:
        print(f"       chatgpt conversations={filtered.get('total', 0)}")

    # Test 8: Get single conversation
    if conv1_id:
        print("\n[8] Get Single Conversation")
        detail = test(f"GET /api/v1/intake/{conv1_id}", "GET", f"/api/v1/intake/{conv1_id}")
        if detail:
            print(f"       title={detail.get('title', 'N/A')}")

    # Test 9: List ideas
    print("\n[9] List Ideas")
    ideas = test("GET /api/v1/ideas", "GET", "/api/v1/ideas")
    if ideas:
        print(f"       total ideas={ideas.get('total', 0)}")

    # Test 10: List projects
    print("\n[10] List Projects")
    projects = test("GET /api/v1/projects", "GET", "/api/v1/projects")
    if projects:
        print(f"       total projects={projects.get('total', 0)}")

    # Test 11: List change packages
    print("\n[11] List Change Packages")
    cps = test("GET /api/v1/change-packages", "GET", "/api/v1/change-packages")
    if cps:
        print(f"       total change packages={cps.get('total', 0)}")

    # Test 12: Notifications endpoint
    print("\n[12] Notifications Endpoint")
    notifs = test("GET /api/v1/notifications", "GET", "/api/v1/notifications")
    if notifs:
        print(f"       notifications={len(notifs.get('notifications', []))}")

    # Test 13: Dashboard loads
    print("\n[13] Dashboard HTML")
    test("GET / (dashboard)", "GET", "/")

    # Summary
    print(f"\n{'='*40}")
    print(f"Results: {PASSED} passed, {FAILED} failed")
    print(f"{'='*40}\n")

    return FAILED == 0


if __name__ == "__main__":
    # Wait for server to be ready
    print("Waiting for server at http://localhost:8765...")
    for i in range(10):
        try:
            urllib.request.urlopen(f"{BASE_URL}/api/v1/health", timeout=2)
            print("Server is ready!\n")
            break
        except:
            time.sleep(1)
    else:
        print("Server not available. Start with: python pipeline_dashboard/serve.py")
        sys.exit(1)

    success = run_tests()
    sys.exit(0 if success else 1)
