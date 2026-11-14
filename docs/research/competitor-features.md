# Competitor feature research: ScoilMate

Date checked: **2026-11-14**. Scope: Irish Junior Cycle (English, Gaeilge, History) revision app; roles admin + student.

**How this was checked:** I used web search snippets and fetched official pages. Several official pages blocked automated fetches (Studyclix home and pricing pages returned no content, Educake and Quizlet returned 403/captcha), and the search provider started failing partway through. Cells marked **†** come from general product knowledge and were **not re-verified** on 2026-11-14. Check them before quoting them anywhere. Pricing changes often, so treat it as indicative only.

## 1. Feature table

| Tool | Audience / region | Key student features | Teacher / admin features | Progress / reporting | Pricing (brief) | Source (checked 2026-11-14) |
|---|---|---|---|---|---|---|
| **Studyclix** | IE: Junior Cycle + Leaving Cert (also AU/ZA) | Every state + mock exam question sorted **by topic**, with solutions/answer guidance; expert notes; video tutorials; sample essay answers; "Collections" to group questions; printable JC flashcards built from 10 years of papers | School-wide licences give all teachers and students Plus/Premium; tutor plan | "Progress tracker so you can see where you're strong and where to focus" | Freemium; paid student plan "until July 1st"; discounted school licences | studyclix.ie; studyclix.ie/account/pricing; studyclix.ie/blog/introducing-junior-cycle-flashcards-for-students |
| **SimpleStudy (IE)** | IE: Junior Cert / LC | Teacher-written notes per topic; exam papers + marking schemes; exam questions with sample answers; topic quizzes; flashcards | † Limited/none surfaced | Quiz page: "track progress" by topic | Freemium † | simplestudy.com/ie/junior-cert/irish; /quizzes |
| **Exams.ie** | IE: JC / LC | Past papers; free JC subject quizzes (incl. Irish); bookmark subjects/papers | None surfaced | Account-based bookmarks; guest mode | Free (account needed for some features) | exams.ie/quizzes/junior-cycle/irish/ |
| **MY FOLENS Library** (was FolensHIVE) | IE: primary + post-primary, tied to Folens textbooks | eBooks redeemed by students | Teachers get presentations, audio, video and ready-to-use classroom resources | None surfaced (resource delivery, not assessment) | Bundled with textbook adoption | folens.ie/pages/folenshive; folens.ie/pages/my-folens-library |
| **Edco Learning** | IE: Edco textbooks (incl. Gaeilge titles) | eBooks on iPad/Windows/Android/web; **exam audio** (aural tracks) | Teacher resource books/transcripts | None surfaced | Bundled with textbooks | edcolearning.ie; edcolearning.ie/examaudio; /OurProducts |
| **CJ Fallon (MyCJ)** | IE: CJ Fallon textbooks | eBooks; student resources (audio, interactive, video, web links) | Teacher login to interactive teaching tools; a new platform is "coming soon" | None surfaced | Bundled with textbooks | my.cjfallon.ie; cjfallon.ie |
| **BBC Bitesize** | UK (KS1–GCSE; NI/Scotland variants) | Topic study guides; quizzes; games; "Study support" (revision tips, exam stress, bullying) | † Separate "Teach" resources | † Minimal (no class reporting) | Free, public-service | bbc.co.uk/bitesize; bbc.co.uk/bitesize/study-support |
| **Seneca Learning** | UK KS2–A Level (30 subjects) | Adaptive courses (two students get different questions on the same topic); instant feedback; multiple learning modes; **gamification**; exam questions | Classes and assignments; set personalised homework from past performance; AI-generated quizzes from own resources; shared resource hub | Real-time homework completion; "data insights to fill gaps"; custom reports; **reports shareable with parents** | Free core; paid School Premium | senecalearning.com/en-gb/teachers/; help.senecalearning.com |
| **Educake** | UK KS3/GCSE (science-led) | Auto-marked quiz questions; low-stakes quizzing | Set and review quizzes; give feedback; see late completions; bulk-download student reports | Automatic per-student, per-subject progress report once a student has answered more than 20 questions | School subscription † | educake.co.uk; help.educake.co.uk (search snippets) |
| **Save My Exams** | UK/Intl: GCSE, IGCSE, A Level, IB, AP | Revision notes; topic exam questions; flashcards; **Target Tests**; **Mock Exams**; past papers + mark schemes; AI study tools | † Teacher/school plans | † Progress tracking of question attempts | Subscription (freemium) | savemyexams.com; savemyexams.com/learning-hub/sme-articles/save-my-exams-for-students/ |
| **Up Learn** | UK A Level + GCSE | Short video lessons; practice questions after every topic; adaptive learning path; interactive exam-paper walkthroughs; 24/7 tutor chat | † School partnerships | Tracks progress per concept/topic and shows "what you should do next"; AI diagnostic fills gaps | Paid (Core/Master tiers) with an A*/A money-back guarantee | uplearn.co.uk/a-level; uplearn.co.uk/guarantee |
| **Quizlet** | Global, any subject | Flashcards; Learn mode; **spaced repetition** (rate your recall, it schedules the next review); † match/test games | Classes; Quizlet Teacher | Class-level most-missed to least-missed terms, filterable by time period | Freemium (Plus subscription) | quizlet.com/gb/features/spaced-repetition; help.quizlet.com; quizlet.com/features/teacher-class-progress (search snippet) |
| **Khan Academy** | Global (US-led) | Mastery-levelled practice; † hints and step-by-step explanations; videos | Assign units; Course/Unit **Mastery Goals**; Teacher Dashboard | Mastery % at course and unit level; assignment and unassigned-activity reports | Free (non-profit); district licences | khanacademy.org (educator articles); support.khanacademy.org/…360031129891 |
| **Kahoot!** | Global | Live game quizzes; **student-paced challenges**; Learn + Flashcards practice; "Your learning" hub | Host live games or assign challenges as homework | Per-session reports; challenge result analysis | Freemium | kahoot.com/blog/2020/02/06/what-is-student-paced-challenge/; support.kahoot.com |
| **Anki** | Global, self-study | Flashcards with an SRS scheduler (**FSRS**, open algorithm); † card stats | None (self-directed) | † Review stats and retention graphs | Free/open source (paid iOS app †) | docs.ankiweb.net/faqs/what-spaced-repetition-algorithm |
| **Memrise** | Global languages | Native-speaker video clips; "Hear it / Learn it / Copy it"; record yourself and compare pronunciation; † review of difficult words | None | † Streaks/words learned | Freemium | memrise.com |
| **Duolingo** | Global languages (incl. Irish course †) | Bite-size lessons; **streaks**, XP, leagues/leaderboards, hearts (from third-party analyses) | † Duolingo for Schools (classroom) | † XP, streak, lesson progress | Freemium, **ad-supported** free tier † | trophy.so/blog/duolingo-gamification-case-study (secondary source) |
| **Google Classroom (Forms quizzes / Practice sets)** | Global schools | Quiz assignments; practice sets with **hints**, suggested resources and in-the-moment support | Create quizzes from Forms; import questions from PDF/Forms; share sets with other teachers | "Insights" on practice sets; grades | Free with Workspace for Education (some features paid tiers †) | support.google.com/edu/classroom/answer/9095575; workspaceupdates.googleblog.com/2024/01/… |

## 2. Common features (ranked by frequency across 18 tools)

These counts are approximate and include † items.

| Rank | Feature | Count /18 | Tools |
|---|---|---|---|
| 1 | Topic-organised practice questions / quizzes with instant marking or feedback | 15 | all except Folens, Edco, CJ Fallon |
| 2 | Student-facing progress tracking (by topic, mastery, or stats) | 12 | Studyclix, SimpleStudy, Seneca, Educake, SME, Up Learn, Quizlet, Khan, Kahoot, Anki, Memrise, Duolingo |
| 3 | Topic notes / study guides / eBook content | 10 | Studyclix, SimpleStudy, Folens, Edco, CJ Fallon, Bitesize, Seneca, SME, Up Learn, Khan |
| 4 | Teacher assigns work and sees class/student reports | 9 | Studyclix (schools), Seneca, Educake, SME†, Quizlet, Khan, Kahoot, Google, Duolingo Schools† |
| 5 | Flashcards | 8 | Studyclix, SimpleStudy, SME, Quizlet, Kahoot, Anki, Memrise, Duolingo† |
| 6 | Past papers / exam-style questions / marking schemes | 7 | Studyclix, SimpleStudy, Exams.ie, Edco (exam audio), Seneca, SME, Up Learn |
| 6 | Hints, worked solutions, sample answers, mark-scheme guidance | 7 | Studyclix, SimpleStudy, SME, Up Learn, Khan, Google, Seneca |
| 6 | Spaced repetition / adaptive revisiting | 7 | Seneca, Quizlet, Anki, Memrise, Duolingo, Up Learn, Khan |
| 6 | Gamification (points, badges, games, streaks) | 7 | Seneca, Kahoot, Duolingo, Quizlet†, Khan†, Bitesize, Memrise† |
| 10 | Mistake / weak-area review ("most missed", "fill gaps") | 6 | Quizlet, Seneca, Up Learn, Duolingo†, Anki (lapses), Khan |
| 10 | Video lessons | 6 | Studyclix, Up Learn, Khan, Memrise, Folens, CJ Fallon |
| 12 | Audio / listening and speaking practice (relevant to the Gaeilge aural) | 5 | Edco, Folens, CJ Fallon, Memrise, Duolingo |
| 13 | AI marking / AI tutor / AI-generated content | 4 | Seneca, SME, Up Learn (+ human tutor chat), Google |
| 13 | Timed / mock-exam mode | 4 | SME (Mock Exams, Target Tests), Kahoot (timed questions), Up Learn (practice papers), Google† |
| 15 | Public leaderboards / leagues / social competition | 3 | Kahoot, Duolingo, Quizlet† |
| 16 | Bookmarks / collections | 2 | Studyclix, Exams.ie |
| 17 | Parent-shareable reports | 1 | Seneca |
| 17 | Wellbeing / exam-stress support | 1 | Bitesize |
| — | Study planner / revision timetable | 0 found on official pages checked | Rarely prominent; not verified for any tool |

## 3. Recommended for ScoilMate

ScoilMate's constraints are: minors aged 13–15, invite-only, no ads, no public social features or messaging, no AI tutor for now, privacy-first, and a server-rendered FastAPI + SQLite app.

### MVP (must-have)
- **Topic-tagged question bank with instant marking (MCQ, short answer, cloze)**: this is the most common feature (15/18) and the core revision loop. It is easy to build server-side.
- **Topic notes per subject/strand** (English, Gaeilge, History): 10/18 tools have them, and they give context for practice. Store them as admin-authored Markdown.
- **Explanations shown after each answer** (why it's right, plus a sample answer for long questions): 7/18 tools do this, and it turns practice into learning without needing AI.
- **Student progress page** (per-topic accuracy, last practised, weak topics): 12/18 tools have one. Compute it with plain SQL aggregates.
- **Admin progress reports** (per-student and per-class topic accuracy, activity/completion, most-missed questions on the Quizlet model): 9/18 tools have this, and it is the main value of the admin role.
- **Mistake review ("redo my wrong answers")**: 6/18 tools have it. It is cheap to build (filter attempts where the answer was wrong) and gives high value.
- **Exam-style practice tagged to Junior Cycle paper sections**: Irish competitors all centre on past or exam-style questions. Use SEC papers only within their reuse terms, or write original exam-style items to avoid copyright risk.

### Next
- **Spaced repetition revisit queue**: 7/18 tools have one. Start with simple Leitner boxes or SM-2 over questions/cards (a few SQLite columns); FSRS can come later.
- **Flashcards** (Gaeilge vocab, History key terms/dates, English literary terms): 8/18 tools have them, and they fit the SRS engine.
- **Timed practice / mini-mock mode**: only 4/18 tools have it, but it prepares students for exam conditions. A server-side deadline with a client countdown is enough.
- **Admin assignments** (set topic X by date Y, then see completion): 9/18 tools have them, and assignments complete the reporting loop.
- **Gaeilge audio**: 5/18 tools have audio, and the aural is part of the exam. Store admin-uploaded clips locally and avoid third-party embeds that track users.

### Later
- **Light, private gamification**: a personal streak or a "days studied this week" count, plus topic-mastery badges. 7/18 tools gamify. Only use versions that are **private and non-punitive**: no leaderboards, no streak-loss shaming, no notifications at night. ⚠️ Duolingo/Kahoot-style leagues and leaderboards **conflict** with the "no public social features" rule and the minors constraint.
- **Study planner** (exam date, then a suggested weekly topic plan driven by weak areas): no tool I checked made this prominent, but it is useful near exams. Build it from progress data.
- **Bookmarks/collections**: 2/18 tools have them. Low effort, nice to have.
- **Printable/exportable progress report**: Seneca's parent-shareable report is similar. Prefer an admin-generated PDF/HTML export over parent accounts, which would be a new role with new privacy scope.
- **Wellbeing / exam-stress page** (as Bitesize does): static content with links to Irish supports such as Jigsaw and Spunout. Easy to add, and appropriate for this age group.

### Flagged conflicts (not silently dropped)
| Common feature | Count | Conflict | Suggested handling |
|---|---|---|---|
| Public leaderboards / leagues / live competitive games | 3 | No public social features; minors | Leave it out. If wanted, use an admin-only class aggregate with no names. |
| AI marking / AI tutor / AI-generated content | 4 | No AI tutor for now; privacy-first (student answers would go to third parties) | Leave it out. Use rule-based marking and admin-written explanations instead. Revisit later with a DPIA. |
| Ad-supported free tier | (Duolingo, others) | No ads | Leave it out. |
| Parent accounts / shared reports | 1 | Invite-only with only admin and student roles; widens data sharing | Defer. Use admin exports instead. |
| Human tutor chat / messaging | 1 (Up Learn) | No messaging; safeguarding of minors | Leave it out. |
| Aggressive streaks / push notifications | (Duolingo-style) | Wellbeing of 13–15-year-olds; no tracking | Only allow a private, gentle streak with no penalties and no push or email nags. |
| Third-party video embeds (YouTube etc.) | 6 have video | Privacy (tracking cookies on minors) | Self-host the videos, or use privacy-enhanced embeds with consent. Defer. |
| Reusing SEC past papers verbatim | 7 | Copyright/licensing, not privacy | Check the SEC reuse terms. Otherwise write original exam-style questions and link out to examinations.ie. |
