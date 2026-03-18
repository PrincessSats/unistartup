"""
AI generation pipeline test script — real-time output.
Run from backend/ directory:
    python test_ai_generate.py
"""
import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))
BASE_URL = "http://localhost:8000"

# ── Colors ────────────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
GRAY   = "\033[90m"
BLUE   = "\033[94m"

def ok(msg):    print(f"{GREEN}✔ {msg}{RESET}", flush=True)
def fail(msg):  print(f"{RED}✘ {msg}{RESET}", flush=True)
def info(msg):  print(f"{CYAN}→ {msg}{RESET}", flush=True)
def warn(msg):  print(f"{YELLOW}⚠ {msg}{RESET}", flush=True)
def step(msg):  print(f"\n{BOLD}{BLUE}{'─'*50}\n  {msg}\n{'─'*50}{RESET}", flush=True)
def dim(msg):   print(f"{GRAY}{msg}{RESET}", flush=True)


def fmt_score(score):
    if score is None:
        return f"{GRAY}n/a{RESET}"
    if score >= 0.8:
        return f"{GREEN}{score:.3f}{RESET}"
    if score >= 0.5:
        return f"{YELLOW}{score:.3f}{RESET}"
    return f"{RED}{score:.3f}{RESET}"


def fmt_passed(passed):
    return f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"


async def main():
    try:
        import httpx
    except ImportError:
        print("Installing httpx...")
        os.system(f"{sys.executable} -m pip install httpx -q")
        import httpx

    # ── Step 1: Login ──────────────────────────────────────────────────────────
    step("STEP 1 — Login")
    email = input(f"  Admin email [{CYAN}admin@hacknet.ru{RESET}]: ").strip() or "admin@hacknet.ru"
    password = input("  Password: ").strip()

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60) as client:

        info(f"POST /auth/login  ({email})")
        r = await client.post("/auth/login", json={"email": email, "password": password})
        if r.status_code != 200:
            fail(f"Login failed {r.status_code}: {r.text}")
            return
        token = r.json()["access_token"]
        ok(f"Token obtained: {token[:40]}...")
        headers = {"X-Auth-Token": token, "Content-Type": "application/json"}

        # ── Step 2: Start generation ───────────────────────────────────────────
        step("STEP 2 — Start generation batch")
        payload = {
            "task_type": "crypto_text_web",
            "difficulty": "intermediate",
            "num_variants": 3,
        }
        info(f"POST /ai-generate/  payload={payload}")
        r = await client.post("/ai-generate/", headers=headers, json=payload)
        print(f"  HTTP {r.status_code}", flush=True)

        if r.status_code not in (200, 201, 202):
            fail(f"Error: {r.text}")
            return

        data = r.json()
        batch_id = data["batch_id"]
        ok(f"Batch created: {batch_id}")
        info(f"RAG context used: {data.get('rag_context_used', 0)}")

        # ── Step 3: Poll ───────────────────────────────────────────────────────
        step("STEP 3 — Polling (updates every 3s)")
        info("Waiting for pipeline to start...\n")

        prev_status = None
        prev_variant_count = 0
        start_time = time.monotonic()

        for i in range(200):  # up to ~10 minutes
            await asyncio.sleep(3)
            elapsed = int(time.monotonic() - start_time)

            r = await client.get(f"/ai-generate/batch/{batch_id}", headers=headers)
            if r.status_code != 200:
                fail(f"Poll error {r.status_code}: {r.text}")
                break
            data = r.json()
            status   = data["status"]
            attempt  = data.get("attempt", 1)
            variants = data.get("variants", [])

            # Print status change
            if status != prev_status:
                if status == "generating":
                    ok(f"[{elapsed}s] Pipeline started  (attempt {attempt})")
                    if data.get("rag_query_text"):
                        info(f"  RAG query: {data['rag_query_text']}")
                    if data.get("rag_context_ids"):
                        info(f"  RAG CVE IDs: {data['rag_context_ids']}")
                elif status == "completed":
                    ok(f"[{elapsed}s] Pipeline COMPLETED")
                elif status == "failed":
                    fail(f"[{elapsed}s] Pipeline FAILED")
                elif status == "pending":
                    dim(f"[{elapsed}s] Waiting for worker...")
                prev_status = status

            # Print new variants as they appear
            if len(variants) > prev_variant_count:
                for v in variants[prev_variant_count:]:
                    checks = {c["type"]: c["score"] for c in (v.get("reward_checks") or [])}
                    reward_str = fmt_score(v.get("reward_total"))
                    passed_str = fmt_passed(v.get("passed_all_binary", False))
                    print(
                        f"  {BOLD}Variant #{v['variant_number']}{RESET}"
                        f"  reward={reward_str}"
                        f"  {passed_str}",
                        flush=True
                    )
                    for check_type, score in checks.items():
                        bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
                        print(f"    {check_type:<20} {bar} {fmt_score(score)}", flush=True)
                    if v.get("failure_reason"):
                        warn(f"    failure: {v['failure_reason']}")
                    print()
                prev_variant_count = len(variants)

            if status in ("completed", "failed"):
                break

        # ── Step 4: Final summary ──────────────────────────────────────────────
        step("STEP 4 — Final results")

        status = data["status"]
        if status == "completed":
            ok(f"Status: {status}")
        else:
            fail(f"Status: {status}")

        print(f"  Attempt:       {data.get('attempt')}", flush=True)
        print(f"  Pass rate:     {data.get('pass_rate', 'n/a')}", flush=True)
        print(f"  Mean reward:   {fmt_score(data.get('group_mean_reward'))}", flush=True)
        print(f"  Std reward:    {fmt_score(data.get('group_std_reward'))}", flush=True)
        print(f"  RAG query:     {data.get('rag_query_text') or 'none'}", flush=True)
        print(f"  RAG CVE IDs:   {data.get('rag_context_ids') or 'none'}", flush=True)
        selected = data.get("selected_variant_id")
        if selected:
            ok(f"Selected variant: {selected}")
        else:
            warn("No variant selected")

        variants = data.get("variants", [])
        if variants:
            print(f"\n  {BOLD}All variants:{RESET}", flush=True)
            for v in variants:
                checks = {c["type"]: c["score"] for c in (v.get("reward_checks") or [])}
                is_winner = str(v["id"]) == str(selected)
                marker = f"{GREEN}★ SELECTED{RESET}" if is_winner else ""
                print(
                    f"  #{v['variant_number']}"
                    f"  reward={fmt_score(v.get('reward_total'))}"
                    f"  quality={fmt_score(v.get('quality_score'))}"
                    f"  advantage={fmt_score(v.get('advantage'))}"
                    f"  rank={v.get('rank_in_group', '-')}"
                    f"  {marker}",
                    flush=True
                )

        elapsed_total = int(time.monotonic() - start_time)
        print(f"\n{GRAY}Total time: {elapsed_total}s{RESET}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
