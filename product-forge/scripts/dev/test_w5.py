from core.run_breaker import RunBreaker

# tiny budget to force decisions quickly
spec = {"soft_cost": 0.001, "hard_cost": 0.002, "variance_percent": 10,
        "rate_limit_tokens_per_min": 1000}
b = RunBreaker("test-pipeline", "products", spec, rate_window_s=60)

print("== feed usage under soft ==")
print(b.add_usage(200, 0.0002).action)     # 20% -> continue
print("== approach soft ==")
print(b.add_usage(500, 0.0006).action)     # 80% -> warn
print("== beyond soft+variance ==")
print(b.add_usage(200, 0.0005).action)     # >0.0011 -> throttle
print("== hard ==")
print(b.add_usage(100, 0.0010).action)     # >=0.002 -> stop (or rate)
print("status:", b.status()["total_cost"], "stopped:", b.status()["stopped"])
print("alerts:", [a["level"] + ":" + a["metric"] for a in b.get_alerts()])

print("\n== rate loop test ==")
spec2 = {"rate_limit_tokens_per_min": 500}
b2 = RunBreaker("test-pipeline", "products", spec2, rate_window_s=60)
r = [b2.add_usage(300, 0.0).action for _ in range(3)]
print("actions:", r)
