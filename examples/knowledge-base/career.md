<!-- Example career knowledge base for mkcv.
     This file demonstrates the format mkcv expects for your career history.
     Replace all content with your own information. The more detail you include
     (metrics, technologies, outcomes), the better the AI can tailor your resume.

     Run `mkcv validate --kb career.md` to check for missing sections. -->

# Alex Chen -- Career Knowledge Base

## Personal Information

| Field    | Value                                  |
|----------|----------------------------------------|
| Name     | Alex Chen                              |
| Email    | alex.chen@example.com                  |
| Phone    | (555) 867-5309                         |
| Location | San Francisco, CA                      |
| LinkedIn | linkedin.com/in/alexchen-example       |
| GitHub   | github.com/alexchen-example            |
| Website  | alexchen.example.com                   |

## Languages

- English (native)
- Mandarin (conversational)

## Professional Summary

Senior software engineer with 9 years of experience building high-throughput
distributed systems and data-intensive backend services. Core expertise in
Python and Go with deep knowledge of cloud-native architectures on AWS.

Led platform teams of 4-8 engineers, driving migrations that cut infrastructure
costs by 40% and reduced deploy times from hours to minutes. Track record of
designing APIs serving 50k+ requests per second and mentoring junior engineers
into senior roles.

Passionate about developer experience, observability, and building systems that
are as easy to operate as they are to develop.

## Technical Skills -- Master List

### Programming Languages
- Python (9 years) -- primary language, deep expertise
- Go (4 years) -- high-performance services, CLI tools
- TypeScript (3 years) -- full-stack features, internal tooling
- Rust (1 year) -- exploring for performance-critical components
- SQL (9 years) -- complex queries, query optimization, migrations

### Frontend
- React, Next.js
- Tailwind CSS
- HTML5, CSS3

### Backend Frameworks
- FastAPI, Django, Flask (Python)
- Gin, Echo (Go)
- Express, Nest.js (TypeScript)
- gRPC, Protocol Buffers

### AI / ML / LLM
- OpenAI API, Anthropic API
- LangChain, LlamaIndex
- Retrieval-Augmented Generation (RAG) pipelines
- Vector databases (Pinecone, pgvector)
- Basic PyTorch for fine-tuning

### APIs & Protocols
- REST API design, OpenAPI/Swagger
- GraphQL (Apollo Server)
- gRPC / Protobuf
- WebSockets
- OAuth 2.0, JWT

### Databases & Data Stores
- PostgreSQL (expert -- partitioning, indexing, replication)
- Redis (caching, pub/sub, rate limiting)
- MongoDB
- Elasticsearch
- Apache Kafka
- Amazon DynamoDB

### Data & Pipeline
- Apache Kafka, Kafka Streams
- Apache Airflow
- dbt (data transformations)
- Pandas, NumPy

### Infrastructure & DevOps
- AWS (ECS, EKS, Lambda, S3, RDS, SQS, SNS, CloudFormation, CDK)
- Docker, Docker Compose
- Kubernetes (EKS), Helm
- Terraform
- GitHub Actions, CircleCI
- Datadog, Grafana, Prometheus
- PagerDuty, Opsgenie

## Career History -- Complete and Detailed

### Arcline Systems -- Senior Staff Engineer
**2023-01 to present** | San Francisco, CA (Hybrid)

Led the platform engineering team (6 engineers) responsible for core backend
infrastructure supporting 200+ microservices across the organization.

- Designed and implemented a company-wide API gateway using Go and Envoy Proxy, consolidating 12 legacy ingress configurations and reducing p99 latency from 340ms to 85ms for all customer-facing endpoints
- Architected event-driven order processing pipeline on Kafka and Python, replacing a synchronous monolith and improving throughput from 500 to 8,000 orders per minute during peak traffic
- Built an internal developer platform with self-service deployment tooling (Kubernetes, Terraform, GitHub Actions), reducing average deploy time from 45 minutes to 4 minutes and cutting deployment failures by 72%
- Introduced structured observability standards across all services using OpenTelemetry, Datadog, and custom dashboards, reducing mean time to detection (MTTD) from 22 minutes to 3 minutes
- Mentored 3 mid-level engineers to senior promotions over 18 months through weekly 1:1s, architecture reviews, and stretch assignments on cross-team projects
- Drove adoption of gRPC for internal service communication, migrating 34 REST endpoints and reducing inter-service payload sizes by 60%
- Established an architecture review board and authored 15 ADRs (Architecture Decision Records) to improve cross-team alignment on technical standards
- Tech stack: Go, Python, Kubernetes (EKS), Kafka, Terraform, Datadog, gRPC, PostgreSQL, Redis, GitHub Actions

### Meridian Health Technologies -- Senior Software Engineer
**2020-03 to 2022-12** | Remote

Backend engineering team building a HIPAA-compliant healthcare data platform
serving 400+ clinic locations and processing 2M+ patient records daily.

- Built a real-time patient data synchronization service in Python (FastAPI) and PostgreSQL that processed 2.3M events per day with 99.97% uptime over 18 months
- Designed and implemented a HIPAA-compliant audit logging system using Kafka and Elasticsearch, enabling full request traceability and passing 3 consecutive compliance audits with zero findings
- Led migration of legacy Django monolith to FastAPI microservices, reducing API response times by 65% and enabling the team to ship features 3x faster through independent deployments
- Created a shared Python SDK used by 8 internal teams for authentication, logging, and error handling, reducing onboarding time for new services from 2 weeks to 2 days
- Optimized PostgreSQL query performance for the reporting module, reducing average query time from 12 seconds to 800ms by implementing materialized views, composite indexes, and connection pooling (PgBouncer)
- Implemented automated data pipeline testing with Great Expectations, catching 94% of data quality issues before they reached production
- Collaborated with the ML team to deploy a patient readmission prediction model, building the serving infrastructure (FastAPI + Redis) that handled 50k predictions per day
- Tech stack: Python, FastAPI, Django, PostgreSQL, Kafka, Elasticsearch, Redis, AWS (ECS, RDS, S3), Docker, Terraform, GitHub Actions

### BrightPath Education -- Software Engineer
**2017-06 to 2020-02** | New York, NY

Full-stack engineer on the core learning platform team, building features for
an ed-tech product used by 150,000+ students and 2,000+ instructors.

- Developed a real-time collaborative document editor using WebSockets and React, supporting 50+ concurrent users per session with sub-200ms sync latency
- Built the course recommendation engine backend (Python, scikit-learn) that increased student engagement by 23% as measured by course completion rates
- Designed and implemented a RESTful API layer serving 15,000 requests per second at peak, using Django REST Framework with Redis caching and CDN integration
- Automated the CI/CD pipeline (CircleCI, Docker) reducing build times from 25 minutes to 8 minutes and eliminating manual deployment steps for a team of 12 engineers
- Led the migration from a single PostgreSQL instance to a read-replica architecture, improving read query throughput by 4x and eliminating downtime during traffic spikes
- Contributed to accessibility (WCAG 2.1 AA) compliance across the platform, remediating 200+ issues and enabling the company to serve public school districts
- Tech stack: Python, Django, React, TypeScript, PostgreSQL, Redis, Docker, CircleCI, AWS (EC2, S3, CloudFront, RDS)

### Quantum Pixel Labs -- Junior Software Engineer
**2015-08 to 2017-05** | New York, NY

First engineering role at an early-stage startup building analytics dashboards
for e-commerce businesses.

- Built RESTful APIs in Flask and PostgreSQL powering analytics dashboards used by 300+ e-commerce merchants to track conversion funnels and revenue metrics
- Implemented automated ETL pipelines using Celery and Redis that ingested data from Shopify, Stripe, and Google Analytics APIs, processing 5M+ events daily
- Developed a responsive dashboard frontend in React, reducing customer support tickets related to data visualization by 40%
- Wrote comprehensive test suites (pytest, 85% coverage) and set up the team's first CI pipeline, reducing production bugs by 30% in the first quarter
- Tech stack: Python, Flask, React, PostgreSQL, Redis, Celery, AWS (EC2, S3), Heroku

## Education

### Columbia University -- M.S. Computer Science
**2013 - 2015** | New York, NY
- Focus: Distributed Systems and Machine Learning
- Teaching Assistant for Operating Systems (2 semesters)

### University of California, Berkeley -- B.S. Computer Science
**2009 - 2013** | Berkeley, CA
- Dean's List (6 semesters)
- Senior capstone: distributed key-value store with Raft consensus

## Certifications

- AWS Solutions Architect -- Associate (2021, renewed 2024)
- Certified Kubernetes Administrator (CKA) (2023)

## Key Achievements

- Promoted from engineer to senior staff in 8 years across 4 companies
- Designed systems collectively handling 100k+ requests per second in production
- Reduced infrastructure costs by $1.2M annually through architecture optimizations at Arcline Systems
- Open-source contributor to FastAPI ecosystem (3 merged PRs to core, maintained a popular middleware package with 2k+ GitHub stars)

## Strengths

- Designing systems that balance performance, reliability, and developer ergonomics
- Translating ambiguous product requirements into clear technical designs
- Building consensus across engineering teams through written proposals and ADRs
- Debugging production incidents methodically under pressure
- Mentoring engineers and fostering a culture of code review and knowledge sharing

## Passions & Interests

- Developer tooling and internal platforms that reduce friction
- Observability and the art of making complex systems understandable
- Technical writing -- maintain a blog on distributed systems patterns
- Open source -- active contributor and occasional conference speaker
- Rock climbing, cycling, and fermenting hot sauce
