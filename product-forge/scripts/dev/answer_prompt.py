"""Answer the current pending discovery prompt. Usage: python scripts/dev/answer_prompt.py <mode>
mode = rec | keep | merge | list
"""
import json, os, re, subprocess, sys

PROJ = "ProductForge-Dashboard"
mode = sys.argv[1] if len(sys.argv) > 1 else "list"
SP = f"products/{PROJ}/interactive/prompts.json"
d = json.load(open(SP, encoding="utf-8"))
pend = [p for p in d["prompts"] if p.get("status") == "pending"]

if mode == "list" or not pend:
    for p in pend:
        q = (p.get("prompt") or "").split("]")[-1].split("recommended answer:")[0].strip()
        print(p["id"], "|", q[:90])
    sys.exit(0)

p = pend[0]
txt = p.get("prompt") or ""
prev = (p.get("default") or "").strip().lstrip("\ufeff")
m = re.search(r"recommended answer:\s*(.*?)(?:\n\s*previous answer \(Enter keeps it\):|\Z)", txt, re.S)
rec = (m.group(1).strip() if m else "")
if mode == "rec":
    ans = rec or prev
elif mode == "keep":
    ans = prev or rec
elif mode == "merge":
    ans = (rec + "\n\n" + prev) if (rec and prev and rec != prev) else (rec or prev)
else:
    ans = prev or rec

tmp = f"products/{PROJ}/.ans_tmp.txt"
open(tmp, "w", encoding="utf-8", newline="\n").write(ans)
r = subprocess.run([sys.executable, "-m", "core.interactive", "--project", PROJ,
                    "--answer-file", p["id"], tmp], capture_output=True, text=True)
print(p["id"], "->", (r.stdout or r.stderr).strip()[:80], "| mode", mode)
try: os.remove(tmp)
except Exception: pass
