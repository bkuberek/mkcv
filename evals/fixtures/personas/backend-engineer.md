# Alex Rivera -- Career Knowledge Base

## Personal Information

| Field    | Value                           |
|----------|---------------------------------|
| Name     | Alex Rivera                     |
| Email    | alex.rivera@example.com         |
| Phone    | (512) 555-0142                  |
| Location | Austin, TX                      |
| Website  | https://alexrivera.example.com  |

## Languages

- English (native)
- Spanish (conversational)

## Professional Summary

Backend and platform engineer with ten years of experience building and
operating services that run at scale. Most recently led the move of 42
services onto Kubernetes at Initech and built the observability stack that
cut incident detection from 25 minutes to 4 minutes.

Strongest in Go, PostgreSQL, and infrastructure as code with Terraform. Has
carried the pager for teams of up to nine engineers and writes the runbooks
and postmortems that make on-call sustainable.

Enjoys the unglamorous work that keeps systems cheap and boring: capacity
planning, schema migrations, build pipelines, and cost reviews. Prefers small,
reversible changes and measuring before and after.

## Technical Skills -- Master List

### Programming Languages
- Go (7 years) -- services, CLIs, and Kubernetes tooling
- Python (9 years) -- automation, data tooling, and internal APIs
- Java (4 years) -- billing and invoicing services at Hooli
- SQL (10 years) -- PostgreSQL and MySQL
- Bash

### Infrastructure & DevOps
- Kubernetes (5 years) -- cluster operations, Helm charts, operators
- Terraform (5 years) -- shared modules, state management, policy checks
- Docker
- Helm
- GitHub Actions and Jenkins -- CI pipelines and release automation
- AWS (EC2, S3, RDS, IAM, EKS)

### Databases & Data Stores
- PostgreSQL (8 years) -- partitioning, replication, query tuning
- Redis -- caching and rate limiting
- Kafka -- event ingestion
- MySQL
- DynamoDB

### Observability & Operations
- OpenTelemetry
- Prometheus
- Grafana
- PagerDuty
- Incident response, runbooks, and blameless postmortems
- Capacity planning and cloud cost reviews

### Practices
- API design (REST and gRPC)
- Contract testing
- Code review and mentoring
- Technical design documents

## Career History -- Complete and Detailed

### Initech -- Senior Software Engineer, Platform
**2021-03 to present** | Austin, TX

Platform team of 9 engineers that owns deployment, runtime, and observability
for the company's product services.

- Led the migration of 42 services from VM-based deploys to Kubernetes, cutting deploy time from 45 minutes to 6 minutes
  - The VM fleet had grown by hand over six years and each service had its own deploy script
  - Moved services in waves, starting with the lowest-traffic ones, with a rollback plan for each wave
- Reduced p99 latency of the order API by 40% by adding read replicas and a Redis cache layer
- Designed the observability stack (OpenTelemetry, Prometheus, Grafana) covering 120 services, cutting mean time to detect incidents from 25 minutes to 4 minutes
  - Wrote the service onboarding guide and a template dashboard so teams could adopt it without help
- Wrote shared Terraform modules adopted by 14 teams, saving an estimated $310K per year in duplicated infrastructure work
- Ran the on-call rotation for a team of 9 and introduced incident response runbooks, lowering pages per week from 31 to 12
- Mentored 5 engineers, two of whom were promoted to senior
- Tech stack: Go, Kubernetes, Terraform, PostgreSQL, Redis, OpenTelemetry, Prometheus, Grafana

### Globex -- Software Engineer II
**2018-06 to 2021-02** | Austin, TX

Data platform group responsible for event ingestion and reporting databases.

- Built a Go ingestion service handling 85,000 events per second at 99.95% availability
- Migrated a 3 TB PostgreSQL database to a partitioned schema with zero downtime, making report queries 8x faster
  - Used logical replication and a dual-write period of two weeks before cutting over
- Cut cloud spend by $1.2M per year by right-sizing instances and moving batch jobs to spot capacity
- Reduced CI build times from 22 minutes to 7 minutes by caching dependencies and parallelizing test suites
- Introduced contract tests between 6 services, which prevented an estimated 15 production regressions in the first year
- Tech stack: Go, PostgreSQL, Kafka, AWS, Jenkins

### Hooli -- Software Engineer
**2016-07 to 2018-05** | Palo Alto, CA

Billing platform team supporting invoicing for the company's paid products.

- Developed REST APIs in Java serving 2 million requests per day for the billing platform
- Rewrote the nightly invoice generation job, reducing its runtime from 5 hours to 50 minutes
- Added idempotency keys to the payment API, eliminating roughly 200 duplicate charges per month
- Shipped a self-service report builder used by 30 finance analysts, replacing a weekly manual export
- Took part in a 12-person on-call rotation and wrote 9 runbooks for the billing services
- Tech stack: Java, MySQL, REST, Jenkins

### Pied Piper -- Junior Developer
**2014-09 to 2016-06** | Portland, OR

Small startup building a file-sync product for teams.

- Built internal tools in Python that automated the weekly customer data export, saving about 6 hours of manual work per week
- Fixed 120 bugs in the file-sync client during the first year, mostly in the retry and conflict-resolution code
- Wrote the first automated test suite for the sync service, reaching 70% line coverage
- Helped migrate the team's source control to Git and set up code review for 8 developers
- Tech stack: Python, SQLite, Git

## Key Achievements

- Kubernetes migration at Initech: 42 services, deploys from 45 minutes to 6 minutes
- Observability stack for 120 services: mean time to detect from 25 minutes to 4 minutes
- Cloud cost reduction at Globex: $1.2M per year
- Zero-downtime migration of a 3 TB PostgreSQL database with 8x faster reports
- Shared Terraform modules used by 14 teams, an estimated $310K per year saved

## Education

### State University -- BS, Computer Science
**2010-09 to 2014-06** | Austin, TX

- Coursework: operating systems, databases, distributed systems, computer networks
- Teaching assistant for the data structures course for two semesters

## Talks and Writing

- Internal talk "Reading a flame graph", given twice to about 80 engineers in total
- Wrote the Initech runbook template that most platform teams now copy
- Maintains a personal blog with notes on PostgreSQL partitioning and Kubernetes upgrades

## Strengths

- Turns vague reliability complaints into measurable targets and fixes the biggest contributor first
- Writes design documents that other teams can implement without a meeting
- Calm during incidents and careful about follow-through afterward
- Comfortable across the stack, from schema design to Kubernetes manifests

## Passions & Interests

- Home-lab Kubernetes cluster built from refurbished mini PCs
- Long-distance cycling and the occasional gravel race
- Teaching newer engineers how production systems fail
