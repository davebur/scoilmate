# ScoilMate — Learning Design Guidance (evidence-based)

Scope: Junior Cycle (age 12–15) revision app — English, Gaeilge, History. Lessons, MCQs with hints/explanations, progress reports, thumbs up/down content ratings. No AI tutor.
Sources checked: 2026-11-14. Some publisher pages (EEF, Khan Academy) block automated fetching; where a claim comes from a search-result snippet of the official page rather than a full read, it is marked *(snippet)*.

## 1. Sources

| Source | Key claims used | URL | Checked |
|---|---|---|---|
| Khan Academy Help Centre — "How do Khan Academy's Mastery levels work?" | Levels: Not started → Attempted (<70% on exercise) → Familiar (70–99%) → Proficient (100%) → Mastered (only via correct answers on a **mixed-skill assessment** while already Proficient). Levels also go **down** when questions are missed in mixed assessments. | https://support.khanacademy.org/hc/en-us/articles/5548760867853 | 2026-11-14 (full read) |
| Khan Academy — "What are Course and Unit Mastery?" | Mastery % = share of skills at Proficient or Mastered; after quizzes/unit tests/course challenges a summary shows skills levelled up/down/unchanged. *(snippet)* | https://support.khanacademy.org/hc/en-us/articles/115002552631 | 2026-11-14 |
| Khan for Educators — "Mastery Learning on Khan Academy" | Familiar ≈ 70%+ (50 pts), Proficient = 100% (80 pts); Mastered needs Proficient + correct in unit test / course / mastery challenge. *(snippet)* | https://www.khanacademy.org/khan-for-educators (Mastery learning article) | 2026-11-14 |
| The Learning Scientists — "Six Strategies for Effective Learning" (Smith & Weinstein) | Spacing, retrieval practice, elaboration, interleaving, concrete examples, dual coding. Retrieval and spacing have the most evidence; elaboration has more limitations. Materials can't predict grades. | https://www.learningscientists.org/blog/2016/8/18-1 ; https://www.learningscientists.org/downloadable-materials | 2026-11-14 (full read) |
| Dunlosky et al. (2013), *Psychological Science in the Public Interest* 14(1) | 10 techniques rated. **High utility:** practice testing, distributed practice. **Moderate:** elaborative interrogation, self-explanation, interleaved practice. **Low:** summarisation, highlighting/underlining, keyword mnemonic, imagery for text, rereading. | https://journals.sagepub.com/doi/abs/10.1177/1529100612453266 ; APS summary https://www.psychologicalscience.org/publications/journals/pspi/learning-techniques.html | 2026-11-14 (APS summary read; ratings for moderate tier from the paper, known) |
| EEF Teaching & Learning Toolkit — Metacognition & self-regulation | Average impact ≈ +8 months; most effective when applied to challenging tasks within normal curriculum content. Self-regulated learners set goals, monitor, reflect, review. *(snippet)* | https://educationendowmentfoundation.org.uk/education-evidence/teaching-learning-toolkit/metacognition-and-self-regulation | 2026-11-14 |
| EEF guidance report — Metacognition & Self-Regulated Learning (2nd ed.) | 7 recommendations; plan → monitor → evaluate cycle; independent practice helps when tasks are challenging, build on secure knowledge, and are guided. *(snippet)* | https://educationendowmentfoundation.org.uk/education-evidence/guidance-reports/metacognition | 2026-11-14 |
| EEF guidance report — Teacher Feedback to Improve Pupil Learning | Feedback works best when focused on the **task, subject, and self-regulation strategies**, not the person; principles over delivery method. *(snippet)* | https://educationendowmentfoundation.org.uk/education-evidence/guidance-reports/feedback | 2026-11-14 |
| EEF Toolkit — Homework | Positive effect, larger at secondary; works best when linked to class learning with feedback, not volume. *(page blocked; widely-cited summary, treat as moderate confidence)* | https://educationendowmentfoundation.org.uk/education-evidence/teaching-learning-toolkit/homework | 2026-11-14 |
| NCCA / Curriculum Online — Junior Cycle Key Skills | Eight key skills incl. **Managing Myself** and **Staying Well**; key skills support "learning how to learn" and taking responsibility for one's learning. | https://curriculumonline.ie/junior-cycle/key-skills/ ; https://ncca.ie/en/resources/jc-key-skills-poster/ | 2026-11-14 |
| Dept of Education (gov.ie) — Wellbeing support for exam students | Stress is normal; some helps, too much harms sleep, concentration, appetite. Advises activity, food, staying connected, relaxing, talking to trusted adults/guidance counsellor; signposts support services. | https://www.gov.ie/en/department-of-education/publications/wellbeing-support-for-exam-students-parents-and-school-staff/ | 2026-11-14 (full read) |
| Dept of Education — Wellbeing Policy Statement & Framework for Practice (2018/2019) | Whole-school wellbeing framework; context for minors' wellbeing. | https://oide.ie/wp-content/uploads/2024/11/Wellbeing-Policy-Statement-and-Framework-for-Practice-2019.pdf | 2026-11-14 (not read in full) |

Not verified this session: Khan Academy hint-scoring rules and Duolingo/Anki scheduling internals — rules below are ScoilMate's own, inspired by the general spacing evidence, not copied.

## 2. Principles

| # | Principle | Evidence strength | Source |
|---|---|---|---|
| P1 | Retrieval practice (self-testing) beats re-study for long-term retention | High | Dunlosky 2013; Learning Scientists |
| P2 | Spread practice over days/weeks; revisit with growing gaps | High | Dunlosky 2013; Learning Scientists |
| P3 | Metacognition (plan → monitor → evaluate) materially improves attainment | High (EEF ≈ +8 months) | EEF |
| P4 | Feedback should be specific to the task/strategy, actionable, not about the person | High-moderate | EEF feedback report |
| P5 | Mix related topics in review (interleaving) to help discrimination between similar ideas | Moderate | Dunlosky 2013; Rohrer via Learning Scientists |
| P6 | Ask "why/how" questions and self-explanations | Moderate | Dunlosky 2013 (elaborative interrogation, self-explanation) |
| P7 | Concrete examples and worked examples aid understanding of abstract concepts | Moderate | Learning Scientists |
| P8 | Combine words with visuals (timelines, diagrams) — not "learning styles" | Moderate | Learning Scientists (dual coding) |
| P9 | Mastery = demonstrated repeatedly, including in mixed assessments; can decay | Practice model (not an RCT claim) | Khan Academy |
| P10 | Rereading, highlighting, summarising are low-utility as primary methods | High (that they're weak) | Dunlosky 2013 |
| P11 | Exam stress is normal but excess harms; signpost support, encourage balance | Official guidance | gov.ie; NCCA "Staying Well" |

## 3. ScoilMate design rules

### 3.1 Mastery levels per topic (simple, explainable)
Track per **topic** (e.g. "History › Revolutionary Ireland › 1916 Rising"). Show the student the rule in plain words.

| Level | Rule (last practice set of ≥5 Qs on this topic, first-attempt scoring) |
|---|---|
| Not started | No attempts |
| Attempted | Scored < 70% |
| Familiar | Scored 70–99%, **or** was Proficient and missed a question on this topic in a mixed review |
| Proficient | Scored 100% on first attempts (no hint, or ≤1 hint-assisted correct counted as half) |
| Mastered | Already Proficient **and** answered this topic correctly in a mixed review taken **≥ 3 days later** |

Rules for hints and retries:
- A question answered correctly **without hints on the first try** = full credit (1.0).
- Correct after **hint 1** = 0.5; after hint 2+ or after a wrong attempt = 0 for mastery (still counts as "practised"). Hints are never penalised in tone — the UI says "Hints help you learn; they just mean we'll check this again soon."
- Levels can drop by **one** step at a time (never straight to Attempted from Mastered) — makes decay visible but not punishing.
- Topic mastery % for a subject = share of topics at Proficient or Mastered (same as Khan's course mastery definition).

### 3.2 Retrieval-first quiz design
- Each lesson ends with a short quiz (5–8 MCQs); offer "Try the quiz first" before the lesson for revision visits (pre-testing).
- Lessons themselves embed 1–2 "check yourself" questions mid-way, not just at the end.
- MCQ distractors should be plausible common misconceptions (author note field per distractor explains why it's wrong).
- Where possible add one non-MCQ recall item per set (type a key word/date/Irish word; exact/near-match) — free recall is stronger than recognition. Mark optional for MVP.
- Show the explanation **after** the student commits to an answer; never reveal the answer in hint 1.

### 3.3 Spaced revisit schedule (explainable, fixed ladder)
- After a practice set, schedule the topic's next review by level: Attempted → **1 day**, Familiar → **3 days**, Proficient → **7 days**, Mastered → **21 days**, then 45 days.
- A failed review moves the topic back one rung (shorter interval). No hidden algorithm; the student sees "Due for review: Thursday".
- "Today's review" queue caps at ~15 questions / ~15 minutes; overdue items don't pile up guiltily — show "a few topics are ready to revisit", never a red backlog count.
- If an exam date is set, compress intervals so every studied topic gets ≥2 reviews before it.

### 3.4 Interleaved mixed reviews
- "Mixed review" draws 10–15 questions across 3–5 due topics **within one subject** (e.g. Gaeilge grammar + vocabulary + poetry), shuffled.
- Mixed reviews are the only route to Mastered (mirrors Khan's mixed-skill rule).
- Don't interleave across subjects in one set (English/Gaeilge/History share little structure; low benefit, more confusion).

### 3.5 Worked examples & hint ladder
Each question supports up to 3 authored hints:
1. **Nudge** — points to the relevant idea ("Think about who led the Volunteers in the GPO").
2. **Strategy / worked parallel** — a similar solved example or the rule ("In the Modh Coinníollach, add -fadh…").
3. **Narrowing** — eliminate one wrong option and explain why.
Then the **explanation** (shown after answering): why the right answer is right + why the chosen distractor is wrong.
- Lessons for skill topics (essay paragraph structure, Irish grammar, source analysis in History) open with a worked example, then a faded example (student completes the last step), then independent questions.
- Use concrete examples (a real 1913 Lockout photo/source; a sample PEE paragraph) and pair text with a simple visual (timeline, table) where it helps — dual coding, not style-matching.

### 3.6 Feedback wording
- Specific and task-focused: "You mixed up the Treaty and the Proclamation — the Treaty was 1921." Not "Wrong!" or "You're bad at History."
- Point to the next action: "Look at hint 2's rule, then try the next one."
- Praise strategy/effort-in-process, not ability: "Using the hint and then getting the next one right is exactly how this works." Avoid "You're a genius".
- **Never predict grades** or Junior Cycle descriptors (Distinction/Higher Merit…). Levels describe practice on ScoilMate only — say so in the UI.
- Neutral colours for wrong answers (amber, not alarm red); no sounds/animations that shame.

### 3.7 Metacognition prompts (lightweight, skippable)
- **Before** a practice set: "How confident are you on this topic?" (1–4 scale: not yet / a bit / mostly / very).
- **After**: show confidence vs. result ("You felt 'mostly' and got 4/6") — calibration helps students judge what to revise. Never shown to others as a judgement.
- **End of session**: "What will I do next?" with 3 tap options (revisit this topic / try a mixed review / move to a new topic) + optional short note.
- Weekly reflection card: "What went well / what's still tricky" — optional, private by default.

### 3.8 Study plan & goals
- Student picks subjects + optional exam/test date + realistic weekly time (e.g. 3 × 20 min).
- Plan = list of due reviews + 1 new topic per session; goals phrased as process ("do 3 review sessions this week"), not outcome ("get 90%").
- Allow reschedule without penalty; plan adapts rather than nags.
- Link to Junior Cycle "Managing Myself" key skill in copy for teachers/admins.

### 3.9 Wellbeing guardrails (minors)
- **No streaks**, loss-aversion mechanics, countdown pressure, leaderboards, or "you'll lose progress" messaging. Use a gentle "This week: 3 sessions" tally that resets weekly without fanfare.
- No push/email nudges to students by default; any reminders opt-in, daytime only, max 1/day.
- Session length suggestion (~20–25 min) with a "take a break" prompt after ~45 min continuous use; nothing after ~22:00 except a soft "Time to rest — sleep helps memory."
- Exam-period copy acknowledges stress is normal and links to gov.ie exam wellbeing page and school guidance counsellor / support services (per Dept of Education page).
- Free-text fields (notes, reflections) are private; if admins get content flags, they never see reflection text.

### 3.10 Progress reports
**Student report shows:** topic levels with the rule that produced them; what's due and when; recent sessions (time, questions); confidence-vs-result trend; hint use framed neutrally; "next suggested step".
**Admin/teacher report shows:** per student and per class: topics practised, level distribution, topics most often missed (to re-teach), overdue reviews count, last active date; question-level stats (% correct, most-chosen distractor, hint usage); content ratings (thumbs up/down with counts, flagged items) to improve content.
**Do NOT show:** predicted grades or descriptors; rankings/leaderboards or comparisons between named students; student private reflections/confidence notes; time-of-day surveillance detail (e.g. "studied at 01:30") beyond aggregate; anything labelled "lazy/behind". Reports to students must not show class averages that let them rank themselves.

## 4. Do not do
- **Learning styles** (visual/auditory/kinesthetic matching) — not supported by evidence; use dual coding for everyone instead.
- **Rereading, highlighting, summarising** as the primary revision method (Dunlosky: low utility) — lessons are a starting point; quizzes are the core.
- **Massed cramming** flows ("finish the whole unit tonight").
- **Grade predictions**, Junior Cycle descriptor estimates, or "you're on track for an A".
- **Streaks, leaderboards, badges for time spent**, dark-pattern notifications.
- **Hints that give the answer away** or that silently tank a score — penalties must be explained.
- **Mastery from a single lucky set** — require a delayed mixed review.
- **Opaque algorithms** for scheduling or levels — every number must be explainable to a 13-year-old.
- **Person-focused feedback** ("you're smart"/"you're bad at this").
