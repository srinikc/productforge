#!/usr/bin/env python3
"""Generate model_registry.json from the mymoney llm-catalog.ts source of truth."""
import json
from datetime import datetime

def make_model(name, provider, tier, cost_in, cost_out, ctx, quality, speed, caps, strengths, weaknesses, use_cases, rpm=0):
    return {
        "name": name,
        "provider": provider,
        "tier": tier,
        "cost_per_1k_input": cost_in,
        "cost_per_1k_output": cost_out,
        "context_window": ctx,
        "quality_score": quality,
        "speed_score": speed,
        "capabilities": caps,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "use_cases": use_cases,
        "enabled": True,
        "rate_limit_rpm": rpm,
        "rate_limit_tpm": 0
    }

models = []

# === OPENAI (28 models) ===
openai_models = [
    ("gpt-5.6-sol", "premium", 0.03, 0.09, 256000, 0.98, 0.6, ["code","analysis","reasoning","vision","long_context"], ["Latest flagship","Highest quality","Multimodal"], ["Most expensive"], ["Complex reasoning","Architecture","Critical analysis"]),
    ("gpt-5.6-terra", "premium", 0.025, 0.075, 256000, 0.97, 0.65, ["code","analysis","reasoning","vision","long_context"], ["High quality","Long context"], ["Expensive"], ["Code generation","Analysis"]),
    ("gpt-5.6-luna", "premium", 0.02, 0.06, 256000, 0.96, 0.7, ["code","analysis","reasoning","vision"], ["Good balance","Fast for tier"], ["Expensive"], ["General tasks","Code"]),
    ("gpt-5.5", "premium", 0.015, 0.045, 200000, 0.95, 0.72, ["code","analysis","reasoning","vision"], ["Fast","High quality"], ["Expensive"], ["Code","Analysis"]),
    ("gpt-5.5-pro", "premium", 0.02, 0.06, 200000, 0.96, 0.68, ["code","analysis","reasoning","vision"], ["Enhanced reasoning","High quality"], ["Most expensive"], ["Complex reasoning","Architecture"]),
    ("gpt-5.4", "recommended", 0.01, 0.03, 128000, 0.93, 0.8, ["code","analysis","reasoning","vision"], ["Fast","High quality","Multimodal"], ["Cost"], ["Code generation","Analysis"]),
    ("gpt-5.4-pro", "recommended", 0.012, 0.036, 128000, 0.94, 0.78, ["code","analysis","reasoning","vision"], ["Enhanced reasoning"], ["Cost"], ["Complex code","Architecture"]),
    ("gpt-5.4-mini", "cheap", 0.002, 0.006, 128000, 0.88, 0.92, ["code","analysis","reasoning","vision"], ["Fast","Cheap","Multimodal"], ["Lower than 5.4"], ["High volume","Quick tasks"]),
    ("gpt-5.4-nano", "cheap", 0.001, 0.003, 128000, 0.82, 0.95, ["code","analysis"], ["Very fast","Very cheap"], ["Lower quality"], ["Simple tasks","Validation"]),
    ("gpt-5.3-codex-spark", "recommended", 0.008, 0.024, 128000, 0.92, 0.82, ["code","analysis"], ["Specialized code","Fast"], ["Code only"], ["Code generation","Refactoring"]),
    ("gpt-5.3-codex", "recommended", 0.007, 0.021, 128000, 0.91, 0.83, ["code","analysis"], ["Specialized code"], ["Code only"], ["Code generation"]),
    ("gpt-5.2", "recommended", 0.008, 0.024, 128000, 0.9, 0.85, ["code","analysis","reasoning","vision"], ["Fast","Good quality"], ["Older"], ["General tasks"]),
    ("gpt-5.2-codex", "recommended", 0.007, 0.021, 128000, 0.89, 0.86, ["code","analysis"], ["Code specialized"], ["Code only"], ["Code generation"]),
    ("gpt-5.1", "recommended", 0.006, 0.018, 128000, 0.88, 0.87, ["code","analysis","reasoning"], ["Fast","Good quality"], ["Older"], ["General tasks"]),
    ("gpt-5.1-codex-max", "recommended", 0.01, 0.03, 128000, 0.9, 0.82, ["code","analysis"], ["Max code quality"], ["Expensive"], ["Complex code","Large refactors"]),
    ("gpt-5.1-codex", "recommended", 0.006, 0.018, 128000, 0.87, 0.87, ["code","analysis"], ["Code specialized"], ["Code only"], ["Code generation"]),
    ("gpt-5.1-codex-mini", "cheap", 0.003, 0.009, 128000, 0.82, 0.92, ["code","analysis"], ["Fast code","Cheap"], ["Lower quality"], ["Quick code tasks"]),
    ("gpt-5", "recommended", 0.005, 0.015, 128000, 0.87, 0.88, ["code","analysis","reasoning"], ["Good balance"], ["Older"], ["General tasks"]),
    ("gpt-5-codex", "recommended", 0.005, 0.015, 128000, 0.86, 0.88, ["code","analysis"], ["Code specialized"], ["Code only"], ["Code generation"]),
    ("gpt-5-nano", "cheap", 0.001, 0.003, 128000, 0.78, 0.95, ["code","analysis"], ["Very fast","Very cheap"], ["Lower quality"], ["Simple tasks"]),
    ("gpt-4.1", "recommended", 0.004, 0.012, 128000, 0.88, 0.88, ["code","analysis","reasoning"], ["Reliable","Fast"], ["Older"], ["General tasks"]),
    ("gpt-4.1-mini", "cheap", 0.001, 0.003, 128000, 0.82, 0.93, ["code","analysis"], ["Fast","Cheap"], ["Lower quality"], ["High volume"]),
    ("gpt-4.1-nano", "cheap", 0.0005, 0.0015, 128000, 0.75, 0.96, ["code","analysis"], ["Very fast","Very cheap"], ["Lowest quality"], ["Simple tasks"]),
    ("gpt-4o", "recommended", 0.005, 0.015, 128000, 0.9, 0.85, ["code","analysis","reasoning","vision"], ["Fast","High quality","Multimodal"], ["Older"], ["Code generation","Analysis"]),
    ("gpt-4o-mini", "cheap", 0.00015, 0.0006, 128000, 0.82, 0.93, ["code","analysis","vision"], ["Very fast","Very cheap"], ["Lower quality"], ["High volume","Validation"]),
    ("o3", "premium", 0.02, 0.06, 200000, 0.96, 0.6, ["code","analysis","reasoning","math"], ["Deep reasoning","Math","Code"], ["Slow","Expensive"], ["Complex reasoning","Math"]),
    ("o3-mini", "recommended", 0.005, 0.015, 200000, 0.92, 0.75, ["code","analysis","reasoning","math"], ["Good reasoning","Fast for reasoning"], ["Reasoning only"], ["Reasoning tasks"]),
    ("o4-mini", "recommended", 0.004, 0.012, 200000, 0.93, 0.78, ["code","analysis","reasoning","math"], ["Improved reasoning","Fast"], ["Reasoning only"], ["Reasoning tasks"]),
]
for m in openai_models:
    models.append(make_model(m[0], "openai", m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[10]))

# === ANTHROPIC (11 models) ===
claude_models = [
    ("claude-fable-5", "premium", 0.03, 0.15, 200000, 0.98, 0.55, ["code","analysis","reasoning","writing","long_context"], ["Highest quality","Best writing","Longest context"], ["Most expensive","Slow"], ["Critical analysis","Architecture","Writing"]),
    ("claude-opus-5", "premium", 0.025, 0.125, 200000, 0.97, 0.58, ["code","analysis","reasoning","writing","long_context"], ["Excellent reasoning","Long context"], ["Expensive","Slow"], ["Architecture","Complex reasoning"]),
    ("claude-opus-4-8", "premium", 0.02, 0.1, 200000, 0.96, 0.6, ["code","analysis","reasoning","writing","long_context"], ["High quality","Long context"], ["Expensive"], ["Architecture","Analysis"]),
    ("claude-opus-4-7", "premium", 0.018, 0.09, 200000, 0.95, 0.62, ["code","analysis","reasoning","writing","long_context"], ["Good reasoning","Long context"], ["Expensive"], ["Analysis","Writing"]),
    ("claude-opus-4-6", "recommended", 0.015, 0.075, 200000, 0.94, 0.65, ["code","analysis","reasoning","writing","long_context"], ["Good balance","Long context"], ["Cost"], ["Code review","Analysis"]),
    ("claude-opus-4-5", "recommended", 0.015, 0.075, 200000, 0.93, 0.65, ["code","analysis","reasoning","writing","long_context"], ["Reliable","Long context"], ["Cost"], ["General reasoning"]),
    ("claude-sonnet-5", "recommended", 0.008, 0.04, 200000, 0.92, 0.75, ["code","analysis","reasoning","writing","long_context"], ["Fast for quality","Long context"], ["Cost"], ["Code review","Documentation"]),
    ("claude-sonnet-4-6", "recommended", 0.006, 0.03, 200000, 0.9, 0.78, ["code","analysis","reasoning","writing","long_context"], ["Good code","Fast"], ["Cost"], ["Code generation","Analysis"]),
    ("claude-sonnet-4-5", "recommended", 0.003, 0.015, 200000, 0.88, 0.8, ["code","analysis","reasoning","writing","long_context"], ["Good balance","Long context"], ["Cost"], ["Code review","Documentation"]),
    ("claude-sonnet-4", "cheap", 0.003, 0.015, 200000, 0.87, 0.82, ["code","analysis","reasoning","writing","long_context"], ["Fast","Cheap"], ["Lower quality"], ["General tasks","High volume"]),
    ("claude-haiku-4-5", "cheap", 0.0008, 0.004, 200000, 0.8, 0.92, ["code","analysis","chat","long_context"], ["Very fast","Cheap","Long context"], ["Lower quality"], ["High volume","Validation","Quick analysis"]),
]
for m in claude_models:
    models.append(make_model(m[0], "anthropic", m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[10]))

# === GOOGLE GEMINI (12 models) ===
gemini_models = [
    ("gemini-3.7-flash", "recommended", 0.001, 0.003, 1000000, 0.88, 0.9, ["code","analysis","vision","long_context"], ["Very fast","1M context","Multimodal"], ["Lower quality"], ["Quick analysis","Vision tasks"]),
    ("gemini-3.6-flash", "cheap", 0.00075, 0.002, 1000000, 0.85, 0.92, ["code","analysis","vision"], ["Fast","Cheap"], ["Lower quality"], ["High volume"]),
    ("gemini-3.5-flash", "cheap", 0.0005, 0.0015, 1000000, 0.83, 0.93, ["code","analysis","vision"], ["Very fast","Very cheap"], ["Lower quality"], ["Simple tasks"]),
    ("gemini-3.5-flash-lite", "cheap", 0.00025, 0.00075, 1000000, 0.78, 0.95, ["code","analysis"], ["Ultra fast","Ultra cheap"], ["Lowest quality"], ["Validation"]),
    ("gemini-3.1-pro", "recommended", 0.003, 0.009, 200000, 0.9, 0.82, ["code","analysis","reasoning","vision"], ["Good quality","Fast"], ["Cost"], ["Analysis","Code"]),
    ("gemini-3-flash", "cheap", 0.0005, 0.0015, 1000000, 0.82, 0.93, ["code","analysis","vision"], ["Fast","1M context"], ["Lower quality"], ["Quick tasks"]),
    ("gemini-2.5-pro", "recommended", 0.0025, 0.0075, 1000000, 0.88, 0.85, ["code","analysis","reasoning","vision","long_context"], ["1M context","Good quality"], ["Older"], ["Long document analysis"]),
    ("gemini-2.5-flash", "cheap", 0.0005, 0.0015, 1000000, 0.83, 0.93, ["code","analysis","vision"], ["Fast","1M context"], ["Lower quality"], ["Quick tasks"]),
    ("gemini-2.5-flash-lite", "cheap", 0.00025, 0.00075, 1000000, 0.78, 0.95, ["code","analysis"], ["Ultra fast"], ["Lowest quality"], ["Validation"]),
    ("gemini-2.0-flash", "cheap", 0.0005, 0.0015, 1000000, 0.8, 0.94, ["code","analysis","vision"], ["Fast","1M context"], ["Older"], ["Quick tasks"]),
    ("gemini-1.5-pro", "cheap", 0.00125, 0.005, 2000000, 0.85, 0.8, ["code","analysis","reasoning","vision","long_context"], ["2M context","Long context"], ["Older","Slower"], ["Long document analysis"]),
    ("gemini-1.5-flash", "cheap", 0.000075, 0.0003, 1000000, 0.78, 0.92, ["code","analysis","vision"], ["Very cheap","Fast"], ["Older","Lower quality"], ["Simple tasks"]),
]
for m in gemini_models:
    models.append(make_model(m[0], "google", m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[10]))

# === GROQ (12 models) ===
groq_models = [
    ("llama-3.3-70b-versatile", "cheap", 0.0005, 0.001, 128000, 0.85, 0.95, ["code","analysis"], ["Ultra fast","Very cheap"], ["Lower quality"], ["High volume","Quick tasks"]),
    ("llama-3.1-8b-instant", "cheap", 0.0001, 0.0002, 128000, 0.72, 0.98, ["code","analysis"], ["Fastest","Cheapest"], ["Lowest quality"], ["Simple tasks"]),
    ("llama-3.1-70b-versatile", "cheap", 0.0005, 0.001, 128000, 0.84, 0.94, ["code","analysis"], ["Fast","Cheap"], ["Older"], ["High volume"]),
    ("llama-4-scout-17b-16e-instruct", "cheap", 0.0002, 0.0004, 128000, 0.8, 0.96, ["code","analysis"], ["Fast","Very cheap"], ["Smaller"], ["Quick tasks"]),
    ("llama-4-maverick-17b-128e-instruct", "cheap", 0.0003, 0.0006, 128000, 0.82, 0.95, ["code","analysis"], ["Fast","Cheap"], ["Smaller"], ["Quick tasks"]),
    ("openai/gpt-oss-20b", "cheap", 0.0002, 0.0004, 128000, 0.78, 0.96, ["code","analysis"], ["Fast","Cheap"], ["Smaller"], ["Simple tasks"]),
    ("openai/gpt-oss-120b", "recommended", 0.0008, 0.0016, 128000, 0.88, 0.92, ["code","analysis"], ["Large","Good quality"], ["Cost"], ["Code generation"]),
    ("qwen-3-32b", "cheap", 0.0003, 0.0006, 128000, 0.82, 0.95, ["code","analysis"], ["Fast","Cheap"], ["Lower quality"], ["High volume"]),
    ("qwen-3-8b", "cheap", 0.0001, 0.0002, 128000, 0.75, 0.97, ["code","analysis"], ["Very fast","Very cheap"], ["Smaller"], ["Simple tasks"]),
    ("gemma-2-27b", "cheap", 0.0002, 0.0004, 8192, 0.8, 0.95, ["code","analysis"], ["Fast","Cheap"], ["Short context"], ["Quick tasks"]),
    ("gemma-2-9b", "cheap", 0.0001, 0.0002, 8192, 0.73, 0.97, ["code","analysis"], ["Very fast","Very cheap"], ["Smaller"], ["Simple tasks"]),
    ("deepseek-r1-distill-llama-70b", "cheap", 0.0005, 0.001, 128000, 0.84, 0.93, ["code","analysis","reasoning"], ["Reasoning capable","Fast"], ["Distilled"], ["Reasoning tasks"]),
]
for m in groq_models:
    models.append(make_model(m[0], "groq", m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[10], rpm=20))

# === CEREBRAS (7 models) ===
cerebras_models = [
    ("gpt-oss-120b", "recommended", 0.001, 0.002, 128000, 0.88, 0.96, ["code","analysis"], ["Highest throughput","Fast"], ["Cost"], ["High volume","Code"]),
    ("gpt-oss-20b", "cheap", 0.0002, 0.0004, 128000, 0.78, 0.98, ["code","analysis"], ["Ultra fast","Cheap"], ["Smaller"], ["Simple tasks"]),
    ("llama-3.3-70b", "cheap", 0.0005, 0.001, 128000, 0.85, 0.95, ["code","analysis"], ["Fast","Good quality"], ["Cost"], ["High volume"]),
    ("llama-3.1-70b", "cheap", 0.0005, 0.001, 128000, 0.84, 0.95, ["code","analysis"], ["Fast","Cheap"], ["Older"], ["High volume"]),
    ("llama-3.1-8b", "cheap", 0.0001, 0.0002, 128000, 0.72, 0.98, ["code","analysis"], ["Fastest","Cheapest"], ["Smaller"], ["Simple tasks"]),
    ("qwen-3-32b", "cheap", 0.0003, 0.0006, 128000, 0.82, 0.96, ["code","analysis"], ["Fast","Cheap"], ["Lower quality"], ["High volume"]),
    ("qwen-3-8b", "cheap", 0.0001, 0.0002, 128000, 0.75, 0.98, ["code","analysis"], ["Very fast","Very cheap"], ["Smaller"], ["Simple tasks"]),
]
for m in cerebras_models:
    models.append(make_model(m[0], "cerebras", m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[10], rpm=30))

# === DEEPSEEK (8 models) ===
ds_models = [
    ("deepseek-chat", "cheap", 0.00014, 0.00028, 64000, 0.88, 0.9, ["code","analysis","reasoning"], ["Ultra cheap","Good quality"], ["Smaller context"], ["Code generation","Analysis"]),
    ("deepseek-reasoner", "recommended", 0.00055, 0.0022, 64000, 0.92, 0.7, ["code","analysis","reasoning","math"], ["Deep reasoning","Math"], ["Slow"], ["Complex reasoning","Math"]),
    ("deepseek-v4-pro", "recommended", 0.0005, 0.001, 128000, 0.9, 0.85, ["code","analysis","reasoning"], ["Good quality","Affordable"], ["Cost"], ["Code","Analysis"]),
    ("deepseek-v4-flash", "cheap", 0.0001, 0.0002, 128000, 0.82, 0.95, ["code","analysis"], ["Ultra cheap","Fast"], ["Lower quality"], ["High volume"]),
    ("deepseek-coder", "cheap", 0.00014, 0.00028, 64000, 0.85, 0.92, ["code","analysis"], ["Code specialized","Ultra cheap"], ["Code only"], ["Code generation"]),
    ("deepseek-r1-0528", "recommended", 0.00055, 0.0022, 64000, 0.91, 0.72, ["code","analysis","reasoning","math"], ["Reasoning","Math"], ["Slow"], ["Complex reasoning"]),
    ("deepseek-v3.1", "cheap", 0.00014, 0.00028, 128000, 0.87, 0.92, ["code","analysis","reasoning"], ["Affordable","Good quality"], ["Cost"], ["Code","Analysis"]),
    ("deepseek-v3-0324", "cheap", 0.00014, 0.00028, 64000, 0.85, 0.93, ["code","analysis"], ["Ultra cheap"], ["Older"], ["High volume"]),
]
for m in ds_models:
    models.append(make_model(m[0], "deepseek", m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[10]))

# === MISTRAL (11 models) ===
mistral_models = [
    ("mistral-large-latest", "recommended", 0.002, 0.006, 128000, 0.9, 0.8, ["code","analysis","reasoning","writing"], ["Good quality","EU hosted"], ["Cost"], ["Code","Analysis"]),
    ("mistral-medium-latest", "cheap", 0.0008, 0.0024, 32000, 0.85, 0.88, ["code","analysis"], ["Fast","Cheap"], ["Shorter context"], ["High volume"]),
    ("mistral-small-latest", "cheap", 0.0002, 0.0006, 32000, 0.8, 0.92, ["code","analysis"], ["Fast","Very cheap"], ["Shorter context"], ["Quick tasks"]),
    ("mistral-nemo", "cheap", 0.00003, 0.00003, 128000, 0.72, 0.95, ["code","analysis"], ["Ultra cheap","Long context"], ["Lower quality"], ["Simple tasks"]),
    ("ministral-3b", "cheap", 0.00002, 0.00002, 32000, 0.65, 0.97, ["code","analysis"], ["Ultra cheap","Ultra fast"], ["Smallest"], ["Simple tasks"]),
    ("ministral-8b", "cheap", 0.0001, 0.0001, 32000, 0.75, 0.95, ["code","analysis"], ["Cheap","Fast"], ["Smaller"], ["Quick tasks"]),
    ("codestral-latest", "cheap", 0.0003, 0.0009, 32000, 0.82, 0.9, ["code","analysis"], ["Code specialized","Fast"], ["Code only"], ["Code generation"]),
    ("pixtral-large-latest", "recommended", 0.002, 0.006, 128000, 0.88, 0.82, ["code","analysis","vision"], ["Multimodal","Good quality"], ["Cost"], ["Vision tasks"]),
    ("pixtral-12b", "cheap", 0.0002, 0.0006, 128000, 0.78, 0.92, ["code","analysis","vision"], ["Multimodal","Cheap"], ["Smaller"], ["Quick vision tasks"]),
    ("open-mistral-nemo", "cheap", 0.00003, 0.00003, 128000, 0.72, 0.95, ["code","analysis"], ["Ultra cheap"], ["Lower quality"], ["Simple tasks"]),
    ("open-mixtral-8x22b", "cheap", 0.0006, 0.0018, 65536, 0.82, 0.88, ["code","analysis"], ["Good value"], ["Older"], ["High volume"]),
]
for m in mistral_models:
    models.append(make_model(m[0], "mistral", m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[10]))

# === DEEPINFRA (10 models) ===
di_models = [
    ("meta-llama/Llama-3.3-70B-Instruct", "cheap", 0.00023, 0.0004, 128000, 0.85, 0.94, ["code","analysis"], ["Fast","Cheap"], ["Lower quality"], ["High volume"]),
    ("meta-llama/Llama-4-Maverick", "cheap", 0.0002, 0.0004, 128000, 0.83, 0.95, ["code","analysis"], ["Fast","Cheap"], ["Smaller"], ["Quick tasks"]),
    ("meta-llama/Llama-4-Scout", "cheap", 0.00015, 0.0003, 128000, 0.8, 0.96, ["code","analysis"], ["Very cheap","Fast"], ["Smaller"], ["Simple tasks"]),
    ("meta-llama/Llama-3.1-405B-Instruct", "recommended", 0.001, 0.002, 128000, 0.9, 0.85, ["code","analysis","reasoning"], ["Largest","High quality"], ["Cost"], ["Complex tasks"]),
    ("Qwen/Qwen2.5-72B-Instruct", "cheap", 0.00025, 0.0004, 128000, 0.84, 0.93, ["code","analysis"], ["Fast","Cheap"], ["Lower quality"], ["High volume"]),
    ("Qwen/Qwen3-32B", "cheap", 0.0002, 0.0004, 128000, 0.82, 0.94, ["code","analysis"], ["Fast","Cheap"], ["Lower quality"], ["High volume"]),
    ("deepseek-ai/DeepSeek-V3", "cheap", 0.00014, 0.00028, 64000, 0.87, 0.92, ["code","analysis","reasoning"], ["Affordable","Good quality"], ["Cost"], ["Code","Analysis"]),
    ("deepseek-ai/DeepSeek-R1", "recommended", 0.00055, 0.0022, 64000, 0.91, 0.72, ["code","analysis","reasoning","math"], ["Reasoning","Math"], ["Slow"], ["Complex reasoning"]),
    ("google/gemma-2-27b-it", "cheap", 0.0002, 0.0003, 8192, 0.8, 0.95, ["code","analysis"], ["Fast","Cheap"], ["Short context"], ["Quick tasks"]),
    ("mistralai/Mixtral-8x22B-Instruct-v0.1", "cheap", 0.0006, 0.0018, 65536, 0.82, 0.88, ["code","analysis"], ["Good value"], ["Older"], ["High volume"]),
]
for m in di_models:
    models.append(make_model(m[0], "deepinfra", m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[10]))

# === TOGETHER AI (10 models) ===
together_models = [
    ("meta-llama/Meta-Llama-3.3-70B-Instruct-Turbo", "cheap", 0.00027, 0.00048, 128000, 0.85, 0.94, ["code","analysis"], ["Fast","Affordable"], ["Lower quality"], ["High volume"]),
    ("meta-llama/Llama-4-Maverick", "cheap", 0.0002, 0.0004, 128000, 0.83, 0.95, ["code","analysis"], ["Fast","Cheap"], ["Smaller"], ["Quick tasks"]),
    ("meta-llama/Llama-4-Scout", "cheap", 0.00015, 0.0003, 128000, 0.8, 0.96, ["code","analysis"], ["Very cheap","Fast"], ["Smaller"], ["Simple tasks"]),
    ("meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo", "recommended", 0.001, 0.002, 128000, 0.9, 0.85, ["code","analysis","reasoning"], ["Largest","High quality"], ["Cost"], ["Complex tasks"]),
    ("deepseek-ai/DeepSeek-V3", "cheap", 0.00014, 0.00028, 64000, 0.87, 0.92, ["code","analysis","reasoning"], ["Affordable","Good quality"], ["Cost"], ["Code","Analysis"]),
    ("deepseek-ai/DeepSeek-R1", "recommended", 0.00055, 0.0022, 64000, 0.91, 0.72, ["code","analysis","reasoning","math"], ["Reasoning","Math"], ["Slow"], ["Complex reasoning"]),
    ("Qwen/Qwen2.5-72B-Instruct", "cheap", 0.00025, 0.0004, 128000, 0.84, 0.93, ["code","analysis"], ["Fast","Cheap"], ["Lower quality"], ["High volume"]),
    ("Qwen/Qwen3-32B", "cheap", 0.0002, 0.0004, 128000, 0.82, 0.94, ["code","analysis"], ["Fast","Cheap"], ["Lower quality"], ["High volume"]),
    ("google/gemma-2-27b-it", "cheap", 0.0002, 0.0003, 8192, 0.8, 0.95, ["code","analysis"], ["Fast","Cheap"], ["Short context"], ["Quick tasks"]),
    ("mistralai/Mixtral-8x22B-Instruct-v0.1", "cheap", 0.0006, 0.0018, 65536, 0.82, 0.88, ["code","analysis"], ["Good value"], ["Older"], ["High volume"]),
]
for m in together_models:
    models.append(make_model(m[0], "together", m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[10]))

# === XAI GROK (10 models) ===
xai_models = [
    ("grok-4.6", "premium", 0.01, 0.03, 128000, 0.93, 0.8, ["code","analysis","reasoning","vision"], ["Latest Grok","Fast"], ["Cost"], ["Code","Analysis"]),
    ("grok-4.5", "recommended", 0.008, 0.024, 128000, 0.92, 0.82, ["code","analysis","reasoning","vision"], ["Good quality","Fast"], ["Cost"], ["General tasks"]),
    ("grok-4", "recommended", 0.005, 0.015, 128000, 0.9, 0.85, ["code","analysis","reasoning","vision"], ["Good balance"], ["Cost"], ["General tasks"]),
    ("grok-4-fast", "cheap", 0.002, 0.006, 128000, 0.85, 0.92, ["code","analysis","vision"], ["Very fast","Affordable"], ["Lower quality"], ["Quick tasks"]),
    ("grok-4-mini", "cheap", 0.001, 0.003, 128000, 0.8, 0.95, ["code","analysis"], ["Fast","Cheap"], ["Lower quality"], ["Simple tasks"]),
    ("grok-3", "recommended", 0.005, 0.015, 128000, 0.88, 0.85, ["code","analysis","reasoning"], ["Good quality"], ["Older"], ["General tasks"]),
    ("grok-3-fast", "cheap", 0.002, 0.006, 128000, 0.83, 0.92, ["code","analysis"], ["Fast","Affordable"], ["Lower quality"], ["Quick tasks"]),
    ("grok-3-mini", "cheap", 0.001, 0.003, 128000, 0.78, 0.95, ["code","analysis"], ["Fast","Cheap"], ["Lower quality"], ["Simple tasks"]),
    ("grok-2", "cheap", 0.002, 0.006, 128000, 0.82, 0.88, ["code","analysis"], ["Affordable"], ["Older"], ["General tasks"]),
    ("grok-build-0.1", "cheap", 0.001, 0.003, 128000, 0.75, 0.9, ["code","analysis"], ["Cheap","Fast"], ["Early version"], ["Testing"]),
]
for m in xai_models:
    models.append(make_model(m[0], "xai", m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[10]))

# === OPENCODE ZEN (46+ models) - deduplicate, keep unique ===
opencode_models = [
    ("gpt-5.6-sol", "premium", 0.03, 0.09, 256000, 0.98, 0.6, ["code","analysis","reasoning","vision","long_context"], ["Latest flagship","Highest quality"], ["Most expensive"], ["Complex reasoning","Architecture"]),
    ("gpt-5.6-terra", "premium", 0.025, 0.075, 256000, 0.97, 0.65, ["code","analysis","reasoning","vision","long_context"], ["High quality"], ["Expensive"], ["Code generation","Analysis"]),
    ("gpt-5.6-luna", "premium", 0.02, 0.06, 256000, 0.96, 0.7, ["code","analysis","reasoning","vision"], ["Good balance"], ["Expensive"], ["General tasks"]),
    ("gpt-5.5", "premium", 0.015, 0.045, 200000, 0.95, 0.72, ["code","analysis","reasoning","vision"], ["Fast","High quality"], ["Expensive"], ["Code","Analysis"]),
    ("gpt-5.5-pro", "premium", 0.02, 0.06, 200000, 0.96, 0.68, ["code","analysis","reasoning","vision"], ["Enhanced reasoning"], ["Most expensive"], ["Complex reasoning"]),
    ("gpt-5.4", "recommended", 0.01, 0.03, 128000, 0.93, 0.8, ["code","analysis","reasoning","vision"], ["Fast","High quality"], ["Cost"], ["Code generation","Analysis"]),
    ("gpt-5.4-pro", "recommended", 0.012, 0.036, 128000, 0.94, 0.78, ["code","analysis","reasoning","vision"], ["Enhanced reasoning"], ["Cost"], ["Complex code"]),
    ("gpt-5.4-mini", "cheap", 0.002, 0.006, 128000, 0.88, 0.92, ["code","analysis","reasoning","vision"], ["Fast","Cheap"], ["Lower than 5.4"], ["High volume"]),
    ("gpt-5.4-nano", "cheap", 0.001, 0.003, 128000, 0.82, 0.95, ["code","analysis"], ["Very fast","Very cheap"], ["Lower quality"], ["Simple tasks"]),
    ("gpt-5.3-codex-spark", "recommended", 0.008, 0.024, 128000, 0.92, 0.82, ["code","analysis"], ["Specialized code","Fast"], ["Code only"], ["Code generation"]),
    ("gpt-5.3-codex", "recommended", 0.007, 0.021, 128000, 0.91, 0.83, ["code","analysis"], ["Specialized code"], ["Code only"], ["Code generation"]),
    ("gpt-5.2", "recommended", 0.008, 0.024, 128000, 0.9, 0.85, ["code","analysis","reasoning","vision"], ["Good quality"], ["Older"], ["General tasks"]),
    ("gpt-5.2-codex", "recommended", 0.007, 0.021, 128000, 0.89, 0.86, ["code","analysis"], ["Code specialized"], ["Code only"], ["Code generation"]),
    ("gpt-5.1", "recommended", 0.006, 0.018, 128000, 0.88, 0.87, ["code","analysis","reasoning"], ["Fast"], ["Older"], ["General tasks"]),
    ("gpt-5.1-codex-max", "recommended", 0.01, 0.03, 128000, 0.9, 0.82, ["code","analysis"], ["Max code quality"], ["Expensive"], ["Complex code"]),
    ("gpt-5.1-codex", "recommended", 0.006, 0.018, 128000, 0.87, 0.87, ["code","analysis"], ["Code specialized"], ["Code only"], ["Code generation"]),
    ("gpt-5.1-codex-mini", "cheap", 0.003, 0.009, 128000, 0.82, 0.92, ["code","analysis"], ["Fast code","Cheap"], ["Lower quality"], ["Quick code tasks"]),
    ("gpt-5", "recommended", 0.005, 0.015, 128000, 0.87, 0.88, ["code","analysis","reasoning"], ["Good balance"], ["Older"], ["General tasks"]),
    ("gpt-5-codex", "recommended", 0.005, 0.015, 128000, 0.86, 0.88, ["code","analysis"], ["Code specialized"], ["Code only"], ["Code generation"]),
    ("gpt-5-nano", "cheap", 0.001, 0.003, 128000, 0.78, 0.95, ["code","analysis"], ["Very cheap"], ["Lower quality"], ["Simple tasks"]),
    ("claude-fable-5", "premium", 0.03, 0.15, 200000, 0.98, 0.55, ["code","analysis","reasoning","writing","long_context"], ["Highest quality"], ["Most expensive"], ["Critical analysis"]),
    ("claude-opus-5", "premium", 0.025, 0.125, 200000, 0.97, 0.58, ["code","analysis","reasoning","writing","long_context"], ["Excellent reasoning"], ["Expensive"], ["Architecture"]),
    ("claude-opus-4-8", "premium", 0.02, 0.1, 200000, 0.96, 0.6, ["code","analysis","reasoning","writing","long_context"], ["High quality"], ["Expensive"], ["Analysis"]),
    ("claude-opus-4-7", "premium", 0.018, 0.09, 200000, 0.95, 0.62, ["code","analysis","reasoning","writing","long_context"], ["Good reasoning"], ["Expensive"], ["Analysis"]),
    ("claude-opus-4-6", "recommended", 0.015, 0.075, 200000, 0.94, 0.65, ["code","analysis","reasoning","writing","long_context"], ["Good balance"], ["Cost"], ["Code review"]),
    ("claude-opus-4-5", "recommended", 0.015, 0.075, 200000, 0.93, 0.65, ["code","analysis","reasoning","writing","long_context"], ["Reliable"], ["Cost"], ["General reasoning"]),
    ("claude-sonnet-5", "recommended", 0.008, 0.04, 200000, 0.92, 0.75, ["code","analysis","reasoning","writing","long_context"], ["Fast for quality"], ["Cost"], ["Code review"]),
    ("claude-sonnet-4-6", "recommended", 0.006, 0.03, 200000, 0.9, 0.78, ["code","analysis","reasoning","writing","long_context"], ["Good code","Fast"], ["Cost"], ["Code generation"]),
    ("claude-sonnet-4-5", "recommended", 0.003, 0.015, 200000, 0.88, 0.8, ["code","analysis","reasoning","writing","long_context"], ["Good balance"], ["Cost"], ["Code review"]),
    ("claude-sonnet-4", "cheap", 0.003, 0.015, 200000, 0.87, 0.82, ["code","analysis","reasoning","writing","long_context"], ["Fast","Cheap"], ["Lower quality"], ["General tasks"]),
    ("claude-haiku-4-5", "cheap", 0.0008, 0.004, 200000, 0.8, 0.92, ["code","analysis","chat","long_context"], ["Very fast","Cheap"], ["Lower quality"], ["High volume"]),
    ("gemini-3.7-flash", "recommended", 0.001, 0.003, 1000000, 0.88, 0.9, ["code","analysis","vision","long_context"], ["Very fast","1M context"], ["Lower quality"], ["Quick analysis"]),
    ("gemini-3.6-flash", "cheap", 0.00075, 0.002, 1000000, 0.85, 0.92, ["code","analysis","vision"], ["Fast","Cheap"], ["Lower quality"], ["High volume"]),
    ("gemini-3.5-flash", "cheap", 0.0005, 0.0015, 1000000, 0.83, 0.93, ["code","analysis","vision"], ["Very fast"], ["Lower quality"], ["Simple tasks"]),
    ("gemini-3.5-flash-lite", "cheap", 0.00025, 0.00075, 1000000, 0.78, 0.95, ["code","analysis"], ["Ultra fast"], ["Lowest quality"], ["Validation"]),
    ("gemini-3.1-pro", "recommended", 0.003, 0.009, 200000, 0.9, 0.82, ["code","analysis","reasoning","vision"], ["Good quality"], ["Cost"], ["Analysis"]),
    ("gemini-3-flash", "cheap", 0.0005, 0.0015, 1000000, 0.82, 0.93, ["code","analysis","vision"], ["Fast","1M context"], ["Lower quality"], ["Quick tasks"]),
    ("deepseek-v4-pro", "recommended", 0.0005, 0.001, 128000, 0.9, 0.85, ["code","analysis","reasoning"], ["Good quality"], ["Cost"], ["Code","Analysis"]),
    ("deepseek-v4-flash", "cheap", 0.0001, 0.0002, 128000, 0.82, 0.95, ["code","analysis"], ["Ultra cheap","Fast"], ["Lower quality"], ["High volume"]),
    ("glm-5.2", "recommended", 0.003, 0.009, 128000, 0.85, 0.85, ["code","analysis"], ["Good quality"], ["Cost"], ["General tasks"]),
    ("glm-5.1", "cheap", 0.002, 0.006, 128000, 0.82, 0.88, ["code","analysis"], ["Fast","Affordable"], ["Cost"], ["General tasks"]),
    ("glm-5", "cheap", 0.001, 0.003, 128000, 0.8, 0.9, ["code","analysis"], ["Cheap","Fast"], ["Lower quality"], ["High volume"]),
    ("minimax-m3", "recommended", 0.002, 0.006, 128000, 0.85, 0.85, ["code","analysis"], ["Good quality"], ["Cost"], ["General tasks"]),
    ("minimax-m2.7", "cheap", 0.001, 0.003, 128000, 0.8, 0.9, ["code","analysis"], ["Fast","Affordable"], ["Cost"], ["General tasks"]),
    ("minimax-m2.5", "cheap", 0.0005, 0.0015, 128000, 0.78, 0.92, ["code","analysis"], ["Cheap","Fast"], ["Lower quality"], ["High volume"]),
    ("kimi-k3", "recommended", 0.003, 0.009, 128000, 0.88, 0.85, ["code","analysis","reasoning"], ["Good quality"], ["Cost"], ["Code","Analysis"]),
    ("kimi-k2.7-code", "recommended", 0.002, 0.006, 128000, 0.87, 0.87, ["code","analysis"], ["Code specialized"], ["Code only"], ["Code generation"]),
    ("kimi-k2.6", "cheap", 0.001, 0.003, 128000, 0.82, 0.9, ["code","analysis"], ["Fast","Affordable"], ["Cost"], ["General tasks"]),
    ("kimi-k2.5", "cheap", 0.0008, 0.0024, 128000, 0.8, 0.92, ["code","analysis"], ["Cheap","Fast"], ["Lower quality"], ["High volume"]),
    ("qwen3.6-plus", "recommended", 0.002, 0.006, 128000, 0.88, 0.87, ["code","analysis","reasoning"], ["Good quality"], ["Cost"], ["Code","Analysis"]),
    ("qwen3.5-plus", "cheap", 0.001, 0.003, 128000, 0.85, 0.9, ["code","analysis"], ["Fast","Affordable"], ["Cost"], ["General tasks"]),
    ("big-pickle", "free", 0, 0, 32000, 0.75, 0.85, ["code","analysis"], ["Free","Decent quality"], ["Rate limited"], ["Free tier","Testing"]),
    ("grok-4.6", "premium", 0.01, 0.03, 128000, 0.93, 0.8, ["code","analysis","reasoning","vision"], ["Latest Grok"], ["Cost"], ["Code","Analysis"]),
    ("grok-4.5", "recommended", 0.008, 0.024, 128000, 0.92, 0.82, ["code","analysis","reasoning","vision"], ["Good quality"], ["Cost"], ["General tasks"]),
    ("grok-build-0.1", "cheap", 0.001, 0.003, 128000, 0.75, 0.9, ["code","analysis"], ["Cheap"], ["Early version"], ["Testing"]),
    ("muse-spark-1.2", "free", 0, 0, 32000, 0.7, 0.85, ["code","analysis"], ["Free"], ["Rate limited"], ["Free tier"]),
    ("deepseek-v4-flash-free", "free", 0, 0, 128000, 0.82, 0.9, ["code","analysis"], ["Free","Fast"], ["Rate limited"], ["Free tier","Testing"]),
    ("mimo-v2.5-free", "free", 0, 0, 32000, 0.7, 0.85, ["code","chat","analysis"], ["Free","Fast"], ["Rate limited"], ["Free tier","Testing"]),
    ("hy3-free", "free", 0, 0, 32000, 0.68, 0.87, ["code","analysis"], ["Free"], ["Rate limited"], ["Free tier"]),
    ("nemotron-3-ultra-free", "free", 0, 0, 32000, 0.72, 0.85, ["code","analysis"], ["Free"], ["Rate limited"], ["Free tier"]),
    ("nemotron-3.5-lightning-free", "free", 0, 0, 32000, 0.75, 0.88, ["code","analysis"], ["Free","Fast"], ["Rate limited"], ["Free tier"]),
    ("laguna-s-2.1-free", "free", 0, 0, 32000, 0.68, 0.87, ["code","analysis"], ["Free"], ["Rate limited"], ["Free tier"]),
]
# Deduplicate opencode models by name
seen_oc = set()
for m in opencode_models:
    if m[0] not in seen_oc:
        seen_oc.add(m[0])
        models.append(make_model(m[0], "opencode-zen", m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[10], rpm=60))

# === LOCAL (14 models) ===
local_models = [
    ("llama3.1", "cheap", 0, 0, 128000, 0.8, 0.85, ["code","analysis"], ["Free","Local"], ["Requires hardware"], ["Local inference"]),
    ("llama3.2", "cheap", 0, 0, 128000, 0.82, 0.85, ["code","analysis"], ["Free","Local"], ["Requires hardware"], ["Local inference"]),
    ("llama3", "cheap", 0, 0, 8192, 0.75, 0.88, ["code","analysis"], ["Free","Local"], ["Short context"], ["Local inference"]),
    ("llama2", "cheap", 0, 0, 4096, 0.65, 0.9, ["code","analysis"], ["Free","Local"], ["Short context","Older"], ["Local inference"]),
    ("mistral", "cheap", 0, 0, 32768, 0.75, 0.88, ["code","analysis"], ["Free","Local"], ["Requires hardware"], ["Local inference"]),
    ("qwen2.5", "cheap", 0, 0, 32768, 0.8, 0.85, ["code","analysis"], ["Free","Local","Good quality"], ["Requires hardware"], ["Local inference"]),
    ("qwen2.5-coder", "cheap", 0, 0, 32768, 0.82, 0.85, ["code","analysis"], ["Free","Local","Code specialized"], ["Code only"], ["Local code generation"]),
    ("gemma2", "cheap", 0, 0, 8192, 0.75, 0.88, ["code","analysis"], ["Free","Local"], ["Short context"], ["Local inference"]),
    ("gemma3", "cheap", 0, 0, 32768, 0.78, 0.87, ["code","analysis"], ["Free","Local"], ["Requires hardware"], ["Local inference"]),
    ("phi4", "cheap", 0, 0, 16384, 0.78, 0.9, ["code","analysis"], ["Free","Local","Fast"], ["Smaller"], ["Local inference"]),
    ("deepseek-r1", "cheap", 0, 0, 64000, 0.85, 0.8, ["code","analysis","reasoning","math"], ["Free","Local","Reasoning"], ["Slow"], ["Local reasoning"]),
    ("deepseek-v3", "cheap", 0, 0, 64000, 0.82, 0.85, ["code","analysis"], ["Free","Local"], ["Requires hardware"], ["Local inference"]),
    ("codellama", "cheap", 0, 0, 16384, 0.72, 0.9, ["code","analysis"], ["Free","Local","Code specialized"], ["Code only"], ["Local code generation"]),
    ("starcoder2", "cheap", 0, 0, 16384, 0.7, 0.9, ["code","analysis"], ["Free","Local","Code specialized"], ["Code only"], ["Local code generation"]),
]
for m in local_models:
    models.append(make_model(m[0], "local", m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[10]))

# Build registry
registry = {
    "models": models,
    "fallback_chains": {
        "code": ["gpt-5.6-sol", "claude-opus-5", "gpt-5.5", "claude-sonnet-5", "gpt-5.4", "claude-sonnet-4-5", "deepseek-chat", "llama-3.3-70b-versatile"],
        "architecture": ["claude-fable-5", "claude-opus-5", "gpt-5.6-sol", "claude-opus-4-8", "gpt-5.5-pro"],
        "reasoning": ["o3", "claude-fable-5", "deepseek-reasoner", "o3-mini", "o4-mini"],
        "review": ["gpt-5.5", "claude-opus-5", "gpt-5.4", "claude-sonnet-5"],
        "validation": ["gpt-5.4-mini", "claude-haiku-4-5", "gemini-3.7-flash", "llama-3.3-70b-versatile"],
        "documentation": ["claude-sonnet-5", "gpt-5.4", "gpt-5.4-mini", "claude-sonnet-4-5"],
        "analysis": ["claude-opus-5", "gpt-5.5", "claude-sonnet-5", "gpt-5.4"],
        "long_context": ["claude-fable-5", "claude-opus-5", "gemini-2.5-pro", "gemini-1.5-pro", "gpt-5.6-sol"],
        "free": ["mimo-v2.5-free", "deepseek-v4-flash-free", "big-pickle", "nemotron-3.5-lightning-free"],
        "code_free": ["mimo-v2.5-free", "deepseek-v4-flash-free", "hy3-free"],
    },
    "tiers": {
        "premium": {"label": "Premium", "description": "Latest flagship models, highest quality", "color": "#FFD700"},
        "recommended": {"label": "Recommended", "description": "Best balance of quality and cost", "color": "#4CAF50"},
        "cheap": {"label": "Budget", "description": "Cost-effective models for high volume", "color": "#2196F3"},
        "free": {"label": "Free Tier", "description": "Free models with rate limits", "color": "#9C27B0"},
    },
    "created_at": datetime.now().isoformat(),
    "updated_at": datetime.now().isoformat(),
    "source": "mymoney/llm-catalog.ts (200+ models from 13 providers)"
}

print(f"Total models: {len(models)}")
print(f"Providers: {len(set(m['provider'] for m in models))}")

with open("products/.pipeline/model_registry.json", "w", encoding="utf-8") as f:
    json.dump(registry, f, indent=2)
print("Written to products/.pipeline/model_registry.json")
