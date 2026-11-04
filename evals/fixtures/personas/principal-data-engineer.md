# Oluwaseun Adeyemi -- Career Knowledge Base

## Personal Information

| Field    | Value                                    |
|----------|------------------------------------------|
| Name     | Oluwaseun (Seun) Adeyemi                 |
| Email    | seun.adeyemi@example.com                 |
| Phone    | (312) 555-0145                           |
| Location | Emberton, IL                             |
| LinkedIn | https://linkedin.example.com/in/seunadeyemi |
| Website  | https://seunadeyemi.example.com          |

## Languages

- English (native)
- Yoruba (conversational)

## Professional Summary

Principal data engineer with fourteen years of experience building data
platforms, from SSIS packages at a consultancy to a lakehouse that serves an
entire insurance company. Currently the senior technical lead for a data
platform group of 38 engineers in five teams at a $3.1B property and casualty
insurer, without direct reports.

Led the migration of a 640 TB on-premises Teradata warehouse to a Databricks
lakehouse on AWS, retiring Teradata and saving $2.3M a year. Designed the
streaming claims platform that gets first notice of loss events to fraud
models in under two minutes instead of the next day. Introduced data
contracts that cut breaking schema changes reaching production from 11 a
quarter to 1, and rolled out data governance with column-level controls for
personal data.

Known for design documents that settle arguments, for growing senior engineers
into staff engineers, and for treating cost, quality, and reliability as
platform features. Looking for a principal or distinguished engineer role
where the data platform is central to the business.

## Technical Skills -- Master List

### Languages
- Python (12 years): PySpark, pipelines, tooling, and services
- SQL (14 years): Spark SQL, PostgreSQL, Redshift, Teradata, Oracle, and T-SQL
- Scala (3 years, Spark jobs at Parcelwise)
- Java (reading and small changes in Kafka connectors)
- Bash

### Processing and Storage
- Apache Spark (10 years): batch and Structured Streaming, performance tuning, and cluster sizing
- Databricks (5 years): Delta Lake, Unity Catalog, Workflows, cluster policies, and Photon
- Delta Lake and the lakehouse architecture (medallion layers)
- Amazon S3, EMR, Redshift and Redshift Spectrum, Glue Data Catalog
- Teradata (migration source), Oracle, PostgreSQL, SQL Server

### Streaming
- Apache Kafka (9 years) and Amazon MSK
- Kafka Connect and Debezium change data capture
- Schema Registry with Avro and Protobuf
- Spark Structured Streaming

### Orchestration and Transformation
- Apache Airflow (10 years): self-hosted and Amazon MWAA, DAG design standards, and custom operators
- dbt (5 years): project structure, CI with state-based selection, tests, and documentation
- Data contracts: schema checks in CI and contract ownership

### Data Quality, Governance, and Security
- Great Expectations and dbt tests
- Data governance: Unity Catalog, column masking, row filters, and access reviews
- Data lineage and catalog adoption
- Personal data handling under state insurance regulations

### Cloud and Infrastructure
- AWS (12 years): S3, EMR, MSK, MWAA, IAM, Lambda, and Glue
- Terraform for data platform infrastructure
- GitHub Actions and Jenkins
- Datadog and CloudWatch for pipeline monitoring

### Legacy Tools (early career)
- SQL Server Integration Services (SSIS)
- Informatica PowerCenter
- Oracle PL/SQL
- Looker (as a developer at Parcelwise)

### Leadership
- Architecture reviews and design documents
- Technical strategy and multi-year roadmaps
- Mentoring senior engineers toward staff
- Hiring: interviews, rubrics, and debriefs
- Incident command and postmortems

## Career History -- Complete and Detailed

### Lumora Insurance -- Principal Data Engineer
**2022-01 to present** | Emberton, IL (hybrid)

Property and casualty insurer (personal auto, homeowners, and small commercial)
with $3.1B in written premium and about 4,200 employees. Data and analytics
organization of 120 people; the data platform group has 38 engineers in five
teams (ingestion, lakehouse platform, streaming, governance, and analytics
engineering). Reports to the VP of Data Platform. Technical lead across all
five teams with no direct reports.

- Architected and led the migration of the 640 TB on-premises Teradata warehouse to a Databricks lakehouse on AWS with Delta Lake
  - Moved 2,300 tables and 410 downstream reports over 20 months, from 2022-07 to 2024-03
  - Built a "migration factory": automated DDL conversion, parallel runs, and row-count and checksum reconciliation for every table before cutover
  - Decommissioned Teradata in 2024-03, saving $2.3M a year in license, support, and hardware costs
  - Kept every statutory and regulatory report on schedule through the migration
- Designed the streaming claims platform on Kafka (Amazon MSK) and Spark Structured Streaming, writing to Delta tables
  - Processes about 1.8M claims events a day from the claims system
  - First notice of loss (FNOL) events now reach fraud models in under 2 minutes instead of the next morning
  - The special investigations unit attributes about $6M a year in avoided fraudulent payouts to earlier flags
- Introduced data contracts between 60 producer services and the lakehouse
  - Contracts live in the producers' repositories and are checked in CI against Schema Registry
  - Breaking schema changes that reached production fell from 11 a quarter to 1
- Rolled out data governance with Unity Catalog across the lakehouse
  - Column masking and row filters for personal data in about 9,000 columns
  - Self-service access requests cut the average wait for data access from 5 days to 4 hours
  - Produced the lineage reports used in the 2024 state insurance department examination
- Led a Databricks cost program: cluster policies, job right-sizing, autoscaling limits, and chargeback dashboards; compute spend fell 31% (about $1.4M a year) while workload volume grew 40%
- Set dbt standards for 7 analytics teams with about 1,100 models; moved CI to state-based selection, cutting CI runs from 50 minutes to 9 minutes
- Led the migration of 900 Airflow DAGs from self-hosted Airflow 1.10 to Airflow 2 on Amazon MWAA in 2023; failed DAG runs fell from 6% to 1.5%
- Built the data quality framework with Great Expectations and dbt tests, about 4,000 automated checks; data incidents reaching business dashboards fell from 25 a quarter to 10
- Built the hurricane exposure aggregation pipeline actuaries use during storm season; the exposure report went from 3 days to 3 hours during the 2024 season
- Supported the ML platform team with feature tables for pricing and fraud models
- Chairs the monthly data architecture council and wrote 14 design documents for platform changes
- Mentored 6 senior engineers; 3 were promoted to staff engineer
- Interviewed more than 70 candidates and co-wrote the staff and principal data engineering career ladder
- Wrote the 2025 to 2027 data platform strategy, presented it to the CIO and CFO, and secured $4.5M in funding
- Incident commander for a 2023-04 delay in a statutory reporting feed; the postmortem added freshness SLAs and alerting for every regulatory dataset, and the problem has not recurred
- Tech stack: Databricks, Delta Lake, Spark, Kafka, Amazon MSK, Airflow, dbt, Great Expectations, Unity Catalog, Terraform, AWS

### Lumora Insurance -- Staff Data Engineer
**2019-06 to 2021-12** | Emberton, IL

Joined to build the company's first cloud data platform alongside the existing
Teradata warehouse.

- Built the first cloud data lake on Amazon S3 with Spark on EMR for policy and claims data, growing to 140 TB by 2021
- Stood up a self-hosted Airflow 1.10 platform on EC2 and grew it to 300 DAGs by the end of 2021
- Built change data capture from the policy administration system's Oracle databases with Debezium and Kafka Connect
- Designed ingestion for the usage-based auto insurance program: about 40M trip events a day from the mobile app through Kafka into S3, which let the pricing team launch usage-based pricing in 3 states
- Cut the nightly batch window from 7 hours to 2.5 hours by moving the heaviest transformations from Teradata to Spark
- Led the 2021 evaluation of three lakehouse and warehouse options and wrote the decision record that chose Databricks and Delta Lake
- Built Terraform modules for EMR clusters, IAM roles, and S3 buckets used by every data team
- Mentored 4 engineers and ran the data engineering interview loop
- Tech stack: Spark, EMR, S3, Kafka, Debezium, Airflow, Terraform, Teradata, Python

### Parcelwise -- Senior Data Engineer
**2016-03 to 2019-05** | Emberton, IL

Last-mile delivery company that grew from about 180 to 900 employees while
Seun was there. Data team of 12.

- Built the real-time ETA pipeline with Kafka and Spark Streaming, processing about 120M GPS pings a day from driver phones
  - With the data science team, cut median ETA error from 14 minutes to 6 minutes
- Introduced Airflow in 2016 to replace cron jobs and grew it to 150 DAGs
- Moved cold data from Redshift to S3 queried through Redshift Spectrum, cutting warehouse costs by 45%
- Built the experimentation data pipeline: exposure logging, metric tables, and daily experiment readouts for the product team
- Tech lead for a team of 3 data engineers from 2018-01 to 2019-05
- Wrote the company's first data dictionary and on-call runbook for data pipelines
- Wrote Spark jobs in Scala for route optimization features
- Tech stack: Kafka, Spark, Scala, Python, Redshift, S3, Airflow, Looker

### Parcelwise -- Data Engineer
**2014-08 to 2016-02** | Emberton, IL

Second data hire at a Series B startup.

- Built Python ETL from the PostgreSQL application database into Redshift
- Built the driver payroll data feed, removing about 20 hours a week of manual reconciliation for the finance team
- Developed the first Looker models and dashboards for operations
- Set up nightly data validation that caught missing delivery scans before payroll ran
- Tech stack: Python, PostgreSQL, Redshift, Looker

### Granary Analytics -- ETL Developer
**2012-07 to 2014-07** | Emberton, IL

Data warehousing consultancy serving retail and healthcare clients.

- Built about 120 SSIS packages for a regional retailer's sales and inventory data warehouse
- Wrote Oracle PL/SQL procedures for a hospital network's monthly quality reporting
- Maintained Informatica PowerCenter workflows for 3 retail clients
- Cut a client's nightly load from 6 hours to 2 hours by replacing row-by-row logic with set-based SQL
- Tech stack: SSIS, SQL Server, Informatica PowerCenter, Oracle

## Detailed Project Notes

### Teradata to lakehouse migration (Lumora, 2022 to 2024)

- Problem: the Teradata contract renewal in 2024 would have cost more than $2M a year, the platform could not take streaming data, and analysts waited weeks for new tables
- Approach: migrated in 14 waves grouped by business domain, starting with marketing data and ending with statutory reporting; each wave ran in parallel for at least two close cycles before cutover
- Tooling: DDL conversion scripts, a reconciliation service that compared row counts and checksums for every table, and a report-by-report sign-off tracker for business owners
- People: coordinated 5 platform teams, 7 analytics teams, and the actuarial and finance departments; ran a weekly migration review with the VP of Data Platform
- Outcome: Teradata switched off in 2024-03; $2.3M a year saved; analysts now get new tables in days

### Streaming claims platform (Lumora, 2022 to 2023)

- Problem: claims data landed in the warehouse once a night, so fraud models scored claims up to a day after first notice of loss
- Approach: change data capture from the claims system into Kafka, Spark Structured Streaming jobs that write bronze, silver, and gold Delta tables, and a scoring hook for the fraud model
- Reliability: exactly-once writes to Delta, replay from Kafka for 7 days, and freshness alerts in Datadog
- Outcome: FNOL events available to fraud models in under 2 minutes; about 1.8M events a day

### Data contracts program (Lumora, 2023 to present)

- Problem: producer teams changed schemas without warning, breaking downstream pipelines 11 times a quarter
- Approach: contract files in each producer repository, checks in CI against Schema Registry, and a deprecation process with a 30-day notice
- Adoption: started with the 10 highest-traffic producers, then all 60 producer services within a year
- Outcome: breaking schema changes reaching production fell to 1 a quarter

### Cost program (Lumora, 2024 to 2025)

- Cluster policies that cap instance types and require autoscaling
- Job-level cost dashboards and monthly chargeback to the owning teams
- Rewrote the 20 most expensive jobs; the largest dropped from 4 hours to 50 minutes
- Outcome: compute spend down 31% (about $1.4M a year) while workload volume grew 40%

## Key Achievements

- Teradata to Databricks lakehouse migration: 640 TB, 2,300 tables, $2.3M a year saved
- Streaming claims platform: FNOL events to fraud models in under 2 minutes
- Data contracts across 60 producer services: breaking changes from 11 a quarter to 1
- Databricks compute spend down 31% while workloads grew 40%
- Mentored 6 senior engineers, 3 promoted to staff

## Education

### Northgate University -- MS, Computer Science
**2015-01 to 2017-12** | Emberton, IL

- Part-time evening program completed while working at Parcelwise
- Focus on distributed systems and databases
- Project: a benchmark of streaming join strategies in Spark

### Emberton Institute of Technology -- BS, Computer Engineering
**2008-08 to 2012-05** | Emberton, IL

- Minor in mathematics
- Senior project: sensor data collection for a campus energy study

## Certifications

- Databricks Certified Data Engineer Professional, 2022
- AWS Certified Solutions Architect -- Associate, 2019

## Talks and Writing

- "Data contracts that producers actually keep," Midwest Data Engineering Summit, 2025
- "Retiring a warehouse without stopping the business," Midwest Data Engineering Summit, 2023
- Monthly internal tech talk series host at Lumora since 2022
- Guest lecturer on data platforms at Emberton Institute of Technology, 2023 and 2024
- Internal blog posts on Delta Lake table maintenance and Airflow DAG design standards

## Mentoring and Community

- Mentor in a nonprofit program that prepares adults from underrepresented groups for data engineering jobs (2020 to present, 9 mentees)
- Organizer of a local data engineering meetup with about 600 members

## Strengths

- Writes design documents that let five teams move in the same direction
- Comfortable saying no to a popular idea when the numbers do not support it
- Patient mentor who gives people real scope and backs them up
- Keeps the business outcome in view during long migrations

## Passions & Interests

- Amateur astronomy and astrophotography
- Plays bass in a church band
- Cooks West African food for friends most weekends
