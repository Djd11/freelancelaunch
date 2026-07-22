# Course Curation & Contract Landing Strategy
> End-to-end plan: Topic selection → Skill curriculum → Platform strategy → Contract win

## Core Insight
A freelancer needs TWO things to succeed:
1. **Skill competence** — can they DO the work? (technical curriculum)
2. **Platform competence** — can they SELL the work? (application curriculum)

Our existing platform teaches #1 well. The research proves #2 is what determines success.

---

## Phase 1: Topic Selection & Demand Validation

### 1.1 User Picks a Topic
- User searches or browses curated topics
- Search shows live platform demand (Upwork jobs, Fiverr gigs, Contra projects)
- User sees: job count, avg rate, demand score, time-to-first-gig estimate

### 1.2 Demand Validation Gate
Before generating a curriculum, the system validates:
```
Demand Score = (Upwork jobs × 0.4) + (Fiverr gigs × 0.3) + (Contra projects × 0.3)

If Score > 30: ✅ Proceed with full curriculum
If Score < 30: ⚠️ Show "Low demand" warning + suggest alternatives
If Score = 0:  ❌ "No demand found" + topic suggestions
```

### 1.3 Topic Categorization
Each topic gets tagged with:
- **Platform fit**: Which platform(s) have the most demand for this skill?
- **Difficulty level**: Beginner / Intermediate / Advanced
- **Estimated time to first gig**: Based on demand + competition data
- **Competition level**: Low / Medium / High (based on freelancer count)

---

## Phase 2: Curriculum Generation (Dual-Track)

### Track A: Technical Skill Training (Days 1-30)
The core skill curriculum — already implemented via LLM generator.
Example for "Web Scraping with Python":
```
Day 1:  HTTP Requests & HTML Fundamentals
Day 2:  BeautifulSoup for Beginners
Day 3:  CSS Selectors & Advanced Parsing
...
Day 30: Job Preparation
```

### Track B: Platform Application Training (Days +7-14)

This is **NEW** — inserted after the technical curriculum based on which platforms the user linked:

#### If User Linked Upwork (7 days added)
```
Day 31: Profile Optimization for Upwork Search
Day 32: Writing Proposals That Convert (with exercises)
Day 33: Pricing Strategy for New Upwork Freelancers
Day 34: Portfolio Presentation (Upwork-specific)
Day 35: Handling Interviews & Client Communication
Day 36: Common Upwork Mistakes & How to Avoid Them
Day 37: Building JSS & Getting Repeat Clients
```

#### If User Linked Fiverr (7 days added)
```
Day 31: Fiverr Gig Creation & SEO
Day 32: Pricing Packages (Basic/Standard/Premium)
Day 33: Buyer Request Mastery
Day 34: First 5 Reviews Strategy
Day 35: Delivery Excellence & Review Generation
Day 36: Handling Revisions & Disputes
Day 37: Scaling from 1 Gig to 5 Gigs
```

#### If User Linked Contra (5 days added)
```
Day 31: Portfolio Creation (Contra-Specific)
Day 32: Profile Optimization & Skills Targeting
Day 33: Pricing on a Commission-Free Platform
Day 34: Client Communication & Negotiation
Day 35: Building Long-Term Client Relationships
```

#### Multi-Platform Ordering
If user links multiple platforms, they get ALL platform modules:
```
Upwork (highest demand) → Fiverr (second) → Contra (last)
Priority determined by: job count for their specific skill on each platform
```

---

## Phase 3: Daily Lesson Structure (Application Days)

Each platform application day follows this format:

```
┌─────────────────────────────────────────────────────────────┐
│  LESSON: Writing Proposals That Convert (Day 32)            │
├─────────────────────────────────────────────────────────────┤
│  1. LEARNING (15 min)                                       │
│     Video: "The First 2 Lines Decide Everything"            │
│     → Bad: "I'm a skilled developer with 5 years exp..."    │
│     → Good: "I see your project needs X because of Y..."   │
│                                                             │
│  2. PRACTICE (25 min)                                       │
│     Exercise: Write a proposal for this real Upwork job:    │
│     [Embedded link to real Upwork job posting]              │
│     → Open with their problem (not your skills)             │
│     → Show you read the description                         │
│     → Include relevant sample                               │
│     → Call to action                                        │
│                                                             │
│  3. APPLY (10 min)                                          │
│     → Submit your proposal draft for feedback               │
│     → OR: Go to Upwork and submit a real proposal           │
│     → Log it in your Pipeline tracker                       │
│                                                             │
│  4. CHECKLIST ITEM                                          │
│     ☐ Completed proposal writing exercise                   │
│     ☐ Submitted at least 1 real proposal this week          │
├─────────────────────────────────────────────────────────────┤
│  PRO TIP (from research):                                   │
│  "Don't use AI to write proposals — clients detect it       │
│   immediately and ignore them. Write from scratch.          │
│   First 2 lines are about THEM, not you."                   │
│  — r/Upwork $300K earner                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 4: Progress Tracking & Pipeline Integration

### Platform Application Tracker
The existing freelance pipeline (Funnel 2) gets enhanced:

```
YOUR UPWORK PROGRESS
┌─────────────────────────────────────────────────────────────┐
│  📋 Profile Checklist                             3/7 done │
│  ☑️ Profile photo added                                      │
│  ☑️ Title matches niche                                      │
│  ☑️ Overview written (Problem → Solution → Proof)           │
│  ☐ Portfolio items added (need 3+)                          │
│  ☐ Skills tags set                                           │
│  ☐ Intro video recorded                                      │
│  ☐ Hourly rate set                                           │
└─────────────────────────────────────────────────────────────┘

📊 PROPOSAL STATS (This Week)
  Target: 5 proposals
  Sent:   2
  Views:  1
  Replies: 0
  ━━━━━━━░░░░░░░ 28%
```

### Smart Proposal Tracking
When user logs a proposal, the system asks:
1. What platform? (Upwork/Fiverr/Contra)
2. Did you use the proposal template? (Y/N)
3. Client responded? (Y/N) — closed-loop feedback

---

## Phase 5: Learning Plan Visualization

### User Dashboard — Updated
```
30-DAY CURRICULUM: Web Scraping with Python
████████████░░░░░░░░░░░░░░░░░ 12/30 days done

UPCOMING PLATFORM TRAINING (starts Day 31)
Based on your linked platforms:
  🟢 Upwork   → ✅ Linked (7 days of proposal training)
  🟡 Fiverr   → ⏳ Not linked (link to add 7 more days)
  ⚪ Contra   → ❌ Not linked

TOTAL CURRICULUM: 37 days (30 skill + 7 Upwork)
```

### Platform Completion Badges
Each platform module awards a badge:
- 🥇 **Upwork Ready** — Completed all 7 Upwork application days
- 🥇 **Fiverr Ready** — Completed all 7 Fiverr application days  
- 🥇 **Contra Ready** — Completed all 5 Contra application days

---

## Implementation Plan

### Phase A: Curriculum Generator Enhancement
- [ ] Modify LLM prompt to accept `platforms` parameter
- [ ] Add platform-specific day templates to curriculum generator
- [ ] Platform module content (pre-written, not LLM-generated for consistency)

### Phase B: Dashboard Integration
- [ ] Add platform progress section to dashboard
- [ ] Show "Upcoming Platform Training" based on linked platforms
- [ ] Add proposal tracking stats per platform

### Phase C: Pipeline Enhancement
- [ ] Add platform-specific proposal tracking
- [ ] Add profile checklist per platform
- [ ] Add "Proposal Quality" self-assessment before submission

### Phase D: BDD Tests
- [ ] Curriculum includes platform days when platforms linked
- [ ] Platform training order matches demand priority
- [ ] Proposal writing exercise loads real Upwork job
- [ ] Profile checklists track completion per platform
