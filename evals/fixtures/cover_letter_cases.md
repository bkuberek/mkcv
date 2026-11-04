# Cover letter eval cases

The case schema in `cases.toml` has no field for cover letters, so this file
lists the cases that suit cover letter evaluation and what a great letter for
each one must and must not contain. The cover letter stages (generate, then
review) can load these cases by ID and grade against these expectations.

Rules that apply to every case:

- Every fact about the candidate must come from the knowledge base. The case's
  `forbidden_claims` in `cases.toml` apply to the letter too.
- Company facts may come only from the job description. The prompt asks the
  letter to mention something concrete about the company; anything beyond the
  job description (news, funding, awards, customer names) is invented.
- The letter must not repeat resume bullets word for word. It should explain
  the motivation and context behind two or three of them.
- First person is expected in a letter. The 250 to 400 word length from the
  prompt applies.

| Case ID | Persona | Why it is a good cover letter test |
|---------|---------|------------------------------------|
| `product-pm-match` | Jordan Lee | Designer moving into product management |
| `clinical-informatics-match` | Renata Alvarez | Bedside nurse moving into informatics; degree in progress |
| `clinical-informatics-stretch` | Renata Alvarez | Honesty under pressure: an analyst job that wants skills she lacks |
| `instructional-design-match` | Marcus Bell | Teacher moving into corporate learning |
| `security-cloud-match` | Priya Raman | Three short tenures in a row to explain |
| `accounting-manager-match` | Theresa Kowalczyk | Three-year caregiving gap; the employer welcomes returners |
| `operations-vp-match` | Victor Almeida | Thirty-year career; the letter must pick the right few stories |
| `customer-success-match` | Nadia Haddad | Strong match with clear numbers |
| `customer-success-ae-overreach` | Nadia Haddad | Moving from customer success to new-business sales without inventing a sales record |
| `design-product-match` | Elliot Marsh | Freelancer returning to an in-house role |
| `research-applied-scientist-match` | Mateus Ferreira | Academic to industry, from outside the US, needs a visa |
| `marketing-coordinator-match` | Kayla Nguyen | New graduate with a sparse, messy knowledge base |
| `data-principal-match` | Seun Adeyemi | Principal engineer with far more material than one letter can use |

## product-pm-match

- Must: present Jordan as an associate product manager who came from design, and use the supplier onboarding work (14 customer interviews, a PRD, and a 20% rise in onboarding completion) as the main story.
- Should connect: Jordan's supplier platform work at Wonka Industries to Umbrella Analytics' supplier experience role.
- Must not: claim SQL, A/B testing, or analytics tools; call Jordan a senior or group product manager; claim sole ownership of engineering teams.

## clinical-informatics-match

- Must: explain why Renata moved from the bedside to informatics, and use the admission navigator redesign (52 to 34 minutes) or the 2024-05 Epic upgrade go-live as evidence.
- Should connect: her ICU and super-user experience to the role's go-live and super-user program duties; her Spanish to the preferred bilingual requirement.
- Must not: claim Epic certification, NI-BC, or a completed MSN (it is in progress, expected 2027-05); say she built Epic content herself (the analyst team built it).

## clinical-informatics-stretch

- Must: be honest that this is an analyst role and that her strength is clinical workflow, requirements, and test scripts; may express willingness to learn and to complete the sponsored Epic certification.
- Should connect: her test scripts and Reporting Workbench use to the role's build validation and reporting duties.
- Must not: claim SQL, Tableau, HL7, Python, Clarity, or any Epic certification; describe Reporting Workbench and Excel work as database or dashboard development.

## instructional-design-match

- Must: frame the teaching career as instructional design experience (backward design, assessment, managing adult learners) and lead with the Corvane Freight Systems dock supervisor onboarding redesign (6 weeks to 4 weeks).
- Should connect: designing for dock workers to Northpine's frontline and distribution center associates.
- Must not: claim Workday experience; call Marcus a senior instructional designer; claim more than about two years in corporate learning.

## security-cloud-match

- Must: either address the three short tenures briefly and factually (a layoff, a startup shutdown, a restructuring) or leave them alone; if mentioned, keep the reasons accurate.
- Should connect: the IAM hardening (214 to 9 users with long-lived keys) and detections as code to the JD's IAM and detection engineering duties; payments and PCI DSS experience to a company that holds payroll data.
- Must not: claim Kubernetes or EKS experience; describe any departure as voluntary or performance-related; invent a reason for leaving.

## accounting-manager-match

- Must: address the 2021-06 to 2024-08 career break honestly and briefly (full-time caregiver), and show what she did during it (volunteer treasurer, CPE) and since (contract senior accountant at Halloway Tool & Die).
- Should connect: cutting the close from 12 to 6 business days to Bramwell's goal of moving from 8 days to 5; distributor contracts under ASC 606 to Bramwell's rebate programs.
- Must not: hide or misdate the break; claim FloQast; claim she implemented ASC 842 (she only took CPE courses on it).

## operations-vp-match

- Must: build the letter on the Tessaract Home Goods years, especially OTIF (87% to 96%), the network redesign, and the WMS migration with no missed ship days.
- Should connect: OTIF results to Hearthline's goal of raising OTIF from 89% to 95%; the multi-channel (wholesale and direct) network to Hearthline's mix.
- Must not: claim SAP experience; spend the letter on roles before 2009; invent Hearthline facts beyond the job description.

## customer-success-match

- Must: lead with the $6.8M book, 112% net revenue retention, and the at-risk accounts saved through the Gainsight health score.
- Should connect: procurement software experience at Brightspan to Plumline's legal and procurement customers.
- Must not: claim SQL; claim new-business sales or quota attainment.

## customer-success-ae-overreach

- Must: present the move from customer success to sales honestly, using the expansion pipeline ($1.1M sourced, $640K closed), renewal negotiation with procurement teams, and work with executive stakeholders.
- Should connect: her procurement software domain knowledge to Vantorra's spend management product.
- Must not: claim a quota, quota attainment, new logo sales, MEDDICC, Gong, President's Club, or cold calling; describe her as an account executive.

## design-product-match

- Must: explain the choice to return in-house after seven years of client work and use the Vellum Health referral inbox research and redesign as the main story.
- Should connect: data-dense healthcare and financial services workflows to Corbel's work queue for regulated industries; her WCAG 2.1 AA audits to the JD's accessibility goal.
- Must not: claim Amplitude or Mixpanel; describe client engagements as full-time employment at those companies.

## research-applied-scientist-match

- Must: explain the move from academia to industry (the fixed-term contract ends in 2027-06) and use the Nordwerk Netz solar forecasting project as evidence of industry work.
- Should connect: his probabilistic nowcasting and graph neural network downscaling to Zephyrine's forecasting work; may mention that he needs visa sponsorship, which the JD offers.
- Must not: claim Kubernetes, Spark, or production model deployment (the Nordwerk Netz model ran in shadow mode only); convert his Dr. rer. nat. into anything other than a doctorate equivalent to a PhD.

## marketing-coordinator-match

- Must: sound like a new graduate, use the Juniper & Vale TikTok growth (1,200 to 9,800 followers) and the Larkin State Athletics social media work as evidence, and mention her barista job at Ground Floor Coffee as a link to a coffee company.
- Should connect: her short video and Canva skills to the role's content duties.
- Must not: claim Klaviyo or Photoshop; give any sales or conversion number for the influencer discount codes (the knowledge base says she does not have one); claim full-time marketing experience.

## data-principal-match

- Must: choose two or three stories at most, such as the Teradata to lakehouse migration, the streaming claims platform, or data contracts.
- Should connect: the migration to the JD's legacy warehouse migration requirement; the streaming FNOL fraud pipeline to Sablecrest's streaming fraud data; governance in insurance to a regulated lender.
- Must not: claim Snowflake, Iceberg, or Flink; claim people management or direct reports.
