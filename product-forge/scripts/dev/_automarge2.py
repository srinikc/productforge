import json, os, re, subprocess, sys, time

PROJ = "ProductForge-Dashboard"
SP = f"products/{PROJ}/interactive/prompts.json"
TMP = f"products/{PROJ}/.merged_ans.txt"


def pending():
    try:
        d = json.load(open(SP, encoding="utf-8"))
        return [p for p in d["prompts"] if p.get("status") == "pending"]
    except Exception:
        return []


def merge(p):
    txt = p.get("prompt") or ""
    prev = (p.get("default") or "").strip().lstrip("\ufeff")
    m = re.search(r"recommended answer:\s*(.*?)(?:\n\s*previous answer \(Enter keeps it\):|\Z)", txt, re.S)
    rec = (m.group(1).strip() if m else "")
    if rec and prev and rec.strip() != prev.strip():
        return f"{rec}\n\n{prev}"
    return rec or prev or ""


def main():
    answered = 0
    started = time.time()
    while time.time() - started < 100:
        ps = pending()
        if not ps:
            time.sleep(2)
            continue
        for p in ps:
            ans = merge(p)
            if not ans:
                continue
            open(TMP, "w", encoding="utf-8", newline="\n").write(ans)
            r = subprocess.run([sys.executable, "-m", "core.interactive", "--project", PROJ,
                                "--answer-file", p["id"], TMP], capture_output=True, text=True)
            if "answered" in (r.stdout or r.stderr):
                answered += 1
                print("answered", p["id"])
        time.sleep(2)
    try: os.remove(TMP)
    except Exception: pass
    print("total answered this pass:", answered)


main()
