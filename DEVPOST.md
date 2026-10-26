# Covered: Devpost submission

**Elevator pitch:** Older adults in Ontario miss care and benefits they qualify for. Covered screens 10 programs in a few taps, reads a tax slip, routes home care and prepares the forms.

## Inspiration

We built Covered for people like Maria, a benefits caseworker who knows every program her clients are owed but can't get most of them there. Getting there means forms, offices and proof, and there is only one of her.

The research said the same thing. In a peer-reviewed study of Ontario caregivers, one put it plainly: "If you don't go online and do your research, you have no clue." Under 40% of eligible people claim the Disability Tax Credit, about a third have an RDSP, and only 12% of caregivers have ever claimed the Canada Caregiver Credit.

## What it does

- **Screens 10 federal and Ontario programs** from a few questions. People can tap Yes/No, type, or speak, or upload a photo of their CRA Notice of Assessment so income is read for them. The SIN is never read or stored.
- **Routes home care**: Direct Funding (the person hires and directs their own attendants, using the real Reg 367/94 criteria) or Ontario Health atHome (care arranged for them). It estimates the Direct Funding budget from CILT's published formula; CILT sets the final amount.
- **Prepares applications**: it pre-fills what it safely can and names what is still needed. A person confirms and submits. Nothing is ever filed automatically.
- **Connects the care team**: a caregiver gets access only with consent, and a clinician completes the medical part of the DTC.
- **Plugs into organizations**: an agency console screens a whole caseload (a simulated CRM through Era) with a co-pilot that answers from exact counts, and partners can embed a widget or call one API.
- **Shows only numbers it can calculate.** Coverage programs such as dental are labelled as coverage, not given invented dollar amounts.

## How we built it

- **FastAPI and Python, in Docker.** A deterministic rules engine makes every eligibility decision. The language model (through OpenRouter) only writes the plain-language explanation.
- **A drift checker built on Cohere** re-reads canada.ca and ontario.ca. One agent finds the figure and a verbatim quote; a second agent independently verifies it. Anything it isn't confident about goes to a human. Today it re-checks 11 of the 15 figures automatically.
- **SurrealDB** with two layers of row-level security (it runs embedded when no server is available). SurrealDB Agent Memory keeps each confirmed figure with its source, date and quote, so a changed value supersedes the old one instead of erasing it.
- **A vision model** reads the Notice of Assessment. Natural voice comes from ElevenLabs, with a browser fallback.
- **99 automated tests in CI**, covering the engine, the API, full user journeys, privacy and row-level security.

The Direct Funding estimate follows CILT's formula:

$$B = (1 + c)\,\big(h \cdot w \cdot (1 + m) + a\big)$$

where h is monthly attendant hours (capped at 212.2), w = 22 per hour, m = 0.21 for employer costs, a = 215 for admin, and c = 0.05 for contingency. Thirty hours a week gives about 3,857 a month.

## Challenges we ran into

- **Breadth was hiding the product.** A general benefits screener had no clear user. Focusing on older adults setting up home care made the path obvious.
- **Adding AI without losing trust.** The model does language and discovery; the deterministic engine decides. The drift checker flagged a live mismatch in the Canada Disability Benefit threshold between our figure and a canada.ca page, and sent it to a human instead of changing the rule.
- **Keeping our own numbers honest.** We removed a placeholder dental value and stopped calling our regression suite "100% accurate", because passing cases we wrote ourselves proves consistency, not correctness.
- **Infrastructure.** A database server and client that had drifted to different versions broke persistence. We pinned them and made the database run embedded, so the demo works anywhere.

## Accomplishments that we're proud of

- **Real forms, not mock-ups**: the actual Direct Funding criteria and CILT's budget formula.
- **Honest by construction**: every figure links to its source and date, and a person always confirms.
- **Built for busy people**: large text, tap-to-answer, voice, and upload instead of typing.

## What we learned

The person with the problem often can't pay. The value goes to whoever captures it, and only one saving can be proven with arithmetic today: disability insurers reduce long-term disability payments dollar for dollar by any CPP Disability benefit a claimant is approved for, so a better-prepared application is directly measurable. Hospitals freeing beds and employers keeping caregivers at work are strong hypotheses we still need to test with a pilot.

## What's next

- Model tax owed, so non-refundable credits are valued for each household's real situation.
- Read PDF Notices of Assessment, not only photos.
- Turn on real sign-in, and host in a Canadian region for privacy.
- Add provinces one by one.
- Run a first pilot with a payer, measuring the savings it captures.

## Built with

Python, FastAPI, SurrealDB, SurrealDB Agent Memory, OpenRouter, Cohere, ElevenLabs, Clerk, Eon / Era, Docker, pytest.

## Links

- Live demo: (deployed URL)
- Repo: https://github.com/Saltef/COVERED
- Demo video: [demo/covered-demo.mp4](demo/covered-demo.mp4) in the repo (upload to YouTube or Vimeo for the Devpost link)
- Logo and thumbnail: [brand/](brand/)
