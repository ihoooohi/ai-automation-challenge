# AI Automation Engineer Challenge

**Time Limit:** 15 minutes
**Position:** AI Automation Engineer

---

## Scenario

You've joined Vizzy Labs and inherited a content moderation service. The service is **functional** - it runs, accepts requests, and returns results.

However, the business has concerns...

---

## The Situation

**From the Creator Success Team (via Slack):**
> "We're getting ~50 support tickets/week from creators whose content is incorrectly flagged. One cooking video was flagged as 'violence' (chopping vegetables). A fitness creator got flagged for 'adult content' (shirtless workout). Creators are threatening to leave the platform."

**From Trust & Safety (in a meeting):**
> "We had a video promoting dangerous supplements reach 100K views before we caught it. Our moderation also missed some borderline hate speech last month. We need to be MORE aggressive, not less."

**From your Engineering Manager:**
> "Both teams are right. We also have no visibility into WHY decisions are made. When Legal asks 'why was this flagged?', we can't answer. We need the system to be more transparent and tunable."

---

## Your Task

**You have 15 minutes.** The interviewer is your stakeholder - ask them questions.

We want to see:

1. **How do you approach this problem?**
   - These requirements conflict. How do you think about the trade-offs?
   - What questions would you ask? What data would you want?

2. **What do you propose?**
   - There's no single "right" answer
   - We want to understand YOUR reasoning

3. **Implement something**
   - Once you've decided what to do, build it
   - AI can help you code, but YOU must decide what to code

---

## Current System

```bash
cd ai-automation-challenge
pip install -r requirements.txt
uvicorn main:app --reload
```

Test it:
```bash
curl -X POST "http://localhost:8000/moderate" \
  -H "Content-Type: application/json" \
  -d '{"content": "Check out my cooking tutorial!", "creator_id": "chef123"}'
```

The system works. It returns moderation results. The question is whether it's doing the RIGHT thing.

---

## Files

All files are functional. Modify whatever you think needs changing.

| File | Description |
|------|-------------|
| `main.py` | FastAPI application |
| `moderation_service.py` | Core moderation logic |
| `models.py` | Data models |
| `mock_clients.py` | Simulates AI APIs (realistic behavior) |

---

## Important

**We are NOT looking for:**
- Bug fixes (the code runs fine)
- A "perfect" solution (none exists)
- Impressive code (simple is better)

**We ARE looking for:**
- How you think about conflicting requirements
- Your ability to make decisions with incomplete information
- Whether you can direct AI tools vs being directed by them
- Your reasoning and trade-off analysis

---

## Hints for the Interviewer (Candidate: Ignore This)

*If candidate asks good questions, share relevant context. If they dive straight into code without understanding the problem, that's a signal.*
