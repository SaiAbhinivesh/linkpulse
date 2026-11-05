# Interview prep

Material for talking about LinkPulse in technical interviews: a pitch, a question bank, a system design walkthrough, and code to explain. If you build the project yourself, use your own numbers.

| File | Use it for |
| --- | --- |
| [pitch.md](pitch.md) | "Tell me about a project": 30 s, 2 min and 5 min versions |
| [question-bank.md](question-bank.md) | Technical questions by topic, answered with examples from this project |
| [system-design.md](system-design.md) | "Design a URL shortener" |
| [code-to-explain.md](code-to-explain.md) | Snippets to walk through line by line |
| [glossary.md](glossary.md) | Quick review of every term, the night before |

## How to prepare (about 2 hours)

1. Say the 2-minute pitch out loud three times, until it doesn't sound read.
2. Pick three problems from [../troubleshooting.md](../troubleshooting.md) and practice telling each in STAR form (situation, task, action, result), under 2 minutes each.
3. Draw the architecture from memory on paper, then check it against [../architecture.md](../architecture.md).
4. Go through the question bank for the topics in the job description. Cover the answer, answer aloud, then check.
5. Skim the glossary just before the interview.

## Numbers worth remembering

| What | Number |
| --- | --- |
| Redirect, cache miss (Postgres) | about 25 ms |
| Redirect, cache hit (Redis) | about 2-3 ms |
| Redis outage | redirects still work, about 25 ms |
| Rate limit | 10 link creations per IP per minute |
| Short code space | 62^7, about 3.5 trillion |
| Kafka topic | 3 partitions, so up to 3 parallel workers |
| Replay test | 8 events replayed, 0 double-counted |
| API replicas | 2, rolling update with maxUnavailable 0 |
| Merge request pipeline | about 1 minute (lint + 16 tests) |
| Instance that failed | t3.micro: 908 MB RAM, load average above 5 |
| Instance that works | m7i-flex.large: 2 vCPU, 8 GB |
