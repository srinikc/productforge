"""
Tests for New Modules
Validates prompt cache, agent messenger, memory API, and agent card loader.
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
BOLD = '\033[1m'
RESET = '\033[0m'

passed = 0
failed = 0
errors = []

def test(name, func):
    global passed, failed
    try:
        result = func()
        if result:
            passed += 1
            print(f"  {GREEN}✓{RESET} {name}")
        else:
            failed += 1
            errors.append(name)
            print(f"  {RED}✗{RESET} {name}")
    except Exception as e:
        failed += 1
        errors.append(f"{name}: {e}")
        print(f"  {RED}✗{RESET} {name}: {e}")


print(f"\n{BOLD}{'='*70}{RESET}")
print(f"{BOLD}  NEW MODULES TEST - Prompt Cache, Messenger, Memory API, Card Loader{RESET}")
print(f"{BOLD}{'='*70}{RESET}")


# ============================================================================
# SECTION 1: Prompt Cache Tests
# ============================================================================
print(f"\n{CYAN}[1/4] Prompt Cache Tests{RESET}")

def test_prompt_cache_basic():
    from core.prompt_cache import PromptCache
    cache = PromptCache(cache_dir="test_pc_basic")
    cache.set("prompt1", "response1", model="gpt-4")
    result = cache.get("prompt1", model="gpt-4")
    return result == "response1"

def test_prompt_cache_miss():
    from core.prompt_cache import PromptCache
    cache = PromptCache(cache_dir="test_pc_miss")
    result = cache.get("nonexistent", model="gpt-4")
    return result is None

def test_prompt_cache_ttl_expiration():
    from core.prompt_cache import PromptCache
    cache = PromptCache(cache_dir="test_pc_ttl")
    cache.set("prompt", "response", ttl_seconds=1)
    import time
    time.sleep(2)
    result = cache.get("prompt")
    return result is None

def test_prompt_cache_lru_eviction():
    from core.prompt_cache import PromptCache
    cache = PromptCache(cache_dir="test_pc_lru", max_entries=3)
    cache.set("p1", "r1")
    cache.set("p2", "r2")
    cache.set("p3", "r3")
    cache.set("p4", "r4")  # Should evict p1
    return cache.get("p1") is None and cache.get("p4") == "r4"

def test_prompt_cache_stats():
    from core.prompt_cache import PromptCache
    cache = PromptCache(cache_dir="test_pc_stats")
    cache.set("p1", "r1", tokens_input=10, tokens_output=20)
    cache.get("p1")  # hit
    cache.get("nonexistent")  # miss
    stats = cache.get_stats()
    return stats["hits"] == 1 and stats["misses"] == 1 and stats["hit_rate"] == 50.0

def test_prompt_cache_invalid_pattern():
    from core.prompt_cache import PromptCache
    cache = PromptCache(cache_dir="test_pc_pattern")
    cache.set("user_data_prompt", "r1")
    cache.set("system_prompt", "r2")
    count = cache.invalidate_by_pattern("user_data")
    return count == 1

def test_cached_llm_call_wrapper():
    from core.prompt_cache import PromptCache, cached_llm_call
    cache = PromptCache(cache_dir="test_pc_wrapper")

    call_count = [0]
    def fake_llm(prompt, **kwargs):
        call_count[0] += 1
        return f"response to: {prompt}"

    r1 = cached_llm_call(cache, "test", fake_llm, model="gpt-4")
    r2 = cached_llm_call(cache, "test", fake_llm, model="gpt-4")  # Should hit cache

    return r1 == r2 and call_count[0] == 1  # LLM called only once

test("Basic cache get/set", test_prompt_cache_basic)
test("Cache miss returns None", test_prompt_cache_miss)
test("TTL expiration works", test_prompt_cache_ttl_expiration)
test("LRU eviction works", test_prompt_cache_lru_eviction)
test("Cache statistics tracking", test_prompt_cache_stats)
test("Invalidate by pattern", test_prompt_cache_invalid_pattern)
test("cached_llm_call wrapper", test_cached_llm_call_wrapper)


# ============================================================================
# SECTION 2: Agent Messenger Tests
# ============================================================================
print(f"\n{CYAN}[2/4] Agent Messenger Tests{RESET}")

def test_messenger_send_receive():
    from core.agent_messenger import AgentMessenger, MessageType
    m = AgentMessenger(project="test_msg_basic")
    msg_id = m.send("alice", "bob", MessageType.REQUEST, {"task": "review"})
    received = m.receive("bob")
    return len(received) == 1 and received[0].message_id == msg_id

def test_messenger_priority():
    from core.agent_messenger import AgentMessenger, MessageType, MessagePriority
    m = AgentMessenger(project="test_msg_priority")
    m.send("a", "b", MessageType.NOTIFICATION, {"x": 1}, priority=MessagePriority.LOW)
    m.send("a", "b", MessageType.NOTIFICATION, {"x": 2}, priority=MessagePriority.URGENT)
    m.send("a", "b", MessageType.NOTIFICATION, {"x": 3}, priority=MessagePriority.NORMAL)
    received = m.receive("b")
    # URGENT should be first
    return received[0].payload["x"] == 2

def test_messenger_broadcast():
    from core.agent_messenger import AgentMessenger, MessageType
    m = AgentMessenger(project="test_msg_broadcast")
    m.send("alice", "bob", MessageType.NOTIFICATION, {"x": 1})
    m.send("alice", "broadcast", MessageType.BROADCAST, {"msg": "hello"})
    # Bob should have received the broadcast
    bob_msgs = m.receive("bob")
    return any("msg" in msg.payload for msg in bob_msgs)

def test_messenger_pub_sub():
    from core.agent_messenger import AgentMessenger, MessageType
    m = AgentMessenger(project="test_msg_pubsub")
    m.subscribe("subscriber1", "events")
    m.subscribe("subscriber2", "events")
    m.send("publisher", "ignored", MessageType.NOTIFICATION, {"event": "test"}, topic="events")
    s1 = m.receive("subscriber1", topic="events")
    s2 = m.receive("subscriber2", topic="events")
    return len(s1) == 1 and len(s2) == 1

def test_messenger_handlers():
    from core.agent_messenger import AgentMessenger, MessageType
    m = AgentMessenger(project="test_msg_handlers")

    received = []
    def handler(msg):
        received.append(msg)

    m.on("message:request", handler)
    m.send("a", "b", MessageType.REQUEST, {"x": 1})
    return len(received) == 1

def test_messenger_stats():
    from core.agent_messenger import AgentMessenger, MessageType
    m = AgentMessenger(project="test_msg_stats")
    m.send("a", "b", MessageType.REQUEST, {})
    m.send("a", "c", MessageType.NOTIFICATION, {})
    m.send("a", "broadcast", MessageType.BROADCAST, {})
    stats = m.get_stats()
    return stats["total_messages"] >= 3

def test_messenger_clear_queue():
    from core.agent_messenger import AgentMessenger, MessageType
    m = AgentMessenger(project="test_msg_clear")
    m.send("a", "b", MessageType.REQUEST, {})
    m.send("a", "b", MessageType.NOTIFICATION, {})
    count = m.clear_queue("b")
    return count == 2 and len(m.receive("b")) == 0

test("Send and receive messages", test_messenger_send_receive)
test("Priority ordering works", test_messenger_priority)
test("Broadcast to all agents", test_messenger_broadcast)
test("Pub/sub with topic subscriptions", test_messenger_pub_sub)
test("Message handlers triggered", test_messenger_handlers)
test("Messenger statistics", test_messenger_stats)
test("Clear message queue", test_messenger_clear_queue)


# ============================================================================
# SECTION 3: Memory API Tests
# ============================================================================
print(f"\n{CYAN}[3/4] Memory API Tests{RESET}")

def test_memory_api_batch_store():
    from core.memory_api import MemoryAPI
    api = MemoryAPI(products_dir="test_products_api", project=f"test-batch-{datetime.now().strftime('%H%M%S')}")
    result = api.store_batch([
        {"memory_type": "semantic", "content": "item1", "source": "src1"},
        {"memory_type": "episodic", "content": "item2", "source": "src2"},
        {"memory_type": "decision", "content": "item3", "source": "src3"},
    ])
    return result.successful == 3

def test_memory_api_skip_duplicates():
    from core.memory_api import MemoryAPI
    api = MemoryAPI(products_dir="test_products_api", project=f"test-dup-{datetime.now().strftime('%H%M%S')}")
    entries = [{"memory_type": "semantic", "content": "duplicate", "source": "src"}]
    r1 = api.store_batch(entries, skip_duplicates=True)
    r2 = api.store_batch(entries, skip_duplicates=True)
    return r1.successful == 1 and r2.skipped == 1

def test_memory_api_export_all():
    from core.memory_api import MemoryAPI
    api = MemoryAPI(products_dir="test_products_api", project=f"test-export-{datetime.now().strftime('%H%M%S')}")
    api.store_batch([
        {"memory_type": "semantic", "content": "a", "source": "s"},
        {"memory_type": "episodic", "content": "b", "source": "s"},
    ])
    bundle = api.export_all()
    return bundle.entry_count == 2 and len(bundle.entries) == 2

def test_memory_api_save_load():
    from core.memory_api import MemoryAPI
    import tempfile
    api = MemoryAPI(products_dir="test_products_api", project=f"test-saveload-{datetime.now().strftime('%H%M%S')}")
    api.store_batch([{"memory_type": "semantic", "content": "save me", "source": "s"}])
    bundle = api.export_all()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        tmp_path = f.name
    api.save_export(bundle, tmp_path)
    
    api2 = MemoryAPI(products_dir="test_products_api", project=f"test-load-{datetime.now().strftime('%H%M%S')}")
    loaded = api2.load_export(tmp_path)
    os.unlink(tmp_path)
    return loaded.entry_count == 1

def test_memory_api_analytics():
    from core.memory_api import MemoryAPI
    api = MemoryAPI(products_dir="test_products_api", project=f"test-analytics-{datetime.now().strftime('%H%M%S')}")
    api.store_batch([
        {"memory_type": "semantic", "content": "a", "source": "src1", "tags": ["t1"]},
        {"memory_type": "episodic", "content": "b", "source": "src2", "tags": ["t1", "t2"]},
    ])
    analytics = api.get_analytics()
    return (analytics["total_entries"] == 2 and
            analytics["unique_sources"] == 2 and
            len(analytics["top_tags"]) > 0)

def test_memory_api_delete_by_source():
    from core.memory_api import MemoryAPI
    api = MemoryAPI(products_dir="test_products_api", project=f"test-del-{datetime.now().strftime('%H%M%S')}")
    api.store_batch([
        {"memory_type": "semantic", "content": "a", "source": "delete_me"},
        {"memory_type": "semantic", "content": "b", "source": "keep_me"},
    ])
    deleted = api.delete_by_source("delete_me")
    return deleted == 1

def test_memory_api_migrate_legacy():
    from core.memory_api import MemoryAPI
    api = MemoryAPI(products_dir="test_products_api", project=f"test-mig-{datetime.now().strftime('%H%M%S')}")
    legacy_data = [
        {"type": "semantic", "text": "legacy1", "source": "old"},
        {"memory_type": "episodic", "content": "legacy2", "source": "old"},
    ]
    result = api.migrate_from_legacy(legacy_data)
    return result.successful == 2

test("Batch store multiple entries", test_memory_api_batch_store)
test("Skip duplicates in batch", test_memory_api_skip_duplicates)
test("Export all memory", test_memory_api_export_all)
test("Save and load export bundle", test_memory_api_save_load)
test("Memory analytics", test_memory_api_analytics)
test("Delete by source", test_memory_api_delete_by_source)
test("Migrate from legacy format", test_memory_api_migrate_legacy)


# ============================================================================
# SECTION 4: Agent Card Loader Tests
# ============================================================================
print(f"\n{CYAN}[4/4] Agent Card Loader Tests{RESET}")

def test_card_loader_loads_all():
    from core.agent_card_loader import AgentCardLoader
    loader = AgentCardLoader()
    cards = loader.load_all()
    return len(cards) > 0

def test_card_loader_parses_frontmatter():
    from core.agent_card_loader import AgentCardLoader
    loader = AgentCardLoader()
    cards = loader.load_all()
    if not cards:
        return False
    # Check that at least one card has parsed frontmatter
    return any(c.frontmatter for c in cards)

def test_card_loader_parses_sections():
    from core.agent_card_loader import AgentCardLoader
    loader = AgentCardLoader()
    cards = loader.load_all()
    if not cards:
        return False
    # Check that at least one card has parsed sections
    return any(c.sections for c in cards)

def test_card_loader_validates():
    from core.agent_card_loader import AgentCardLoader
    loader = AgentCardLoader()
    cards = loader.load_all()
    if not cards:
        return False
    # Check that validation produces issues
    return any(c.issues for c in cards)

def test_card_loader_report():
    from core.agent_card_loader import AgentCardLoader
    loader = AgentCardLoader()
    report = loader.generate_report()
    return (
        "total_cards" in report and
        "valid_cards" in report and
        "invalid_cards" in report and
        "cards" in report
    )

def test_card_loader_get_by_name():
    from core.agent_card_loader import AgentCardLoader
    loader = AgentCardLoader()
    card = loader.get_card_by_name("design")
    return card is not None

def test_card_loader_filter_valid():
    from core.agent_card_loader import AgentCardLoader
    loader = AgentCardLoader()
    valid = loader.get_valid_cards()
    invalid = loader.get_invalid_cards()
    return len(valid) + len(invalid) == len(loader.load_all())

test("Loads all agent cards", test_card_loader_loads_all)
test("Parses frontmatter", test_card_loader_parses_frontmatter)
test("Parses sections", test_card_loader_parses_sections)
test("Validates cards and produces issues", test_card_loader_validates)
test("Generates validation report", test_card_loader_report)
test("Gets card by name", test_card_loader_get_by_name)
test("Filters valid/invalid cards", test_card_loader_filter_valid)


# ============================================================================
# SUMMARY
# ============================================================================
print(f"\n{BOLD}{'='*70}{RESET}")
print(f"{BOLD}  NEW MODULES TEST RESULTS{RESET}")
print(f"{BOLD}{'='*70}{RESET}")
print(f"  {GREEN}Passed: {passed}{RESET}")
print(f"  {RED}Failed: {failed}{RESET}")
print(f"  Total:  {passed + failed}")
print(f"  Rate:   {passed/(passed+failed)*100:.1f}%")

if errors:
    print(f"\n{RED}  Failed tests:{RESET}")
    for err in errors:
        print(f"    - {err}")

print(f"\n{'='*70}")

if failed == 0:
    print(f"{GREEN}{BOLD}  ✅ ALL TESTS PASSED - All new modules working!{RESET}")
else:
    print(f"{RED}{BOLD}  ❌ SOME TESTS FAILED{RESET}")

print(f"{'='*70}\n")

sys.exit(0 if failed == 0 else 1)
