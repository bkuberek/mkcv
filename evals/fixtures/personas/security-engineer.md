# Priya Raman -- Career Knowledge Base

## Personal Information

| Field    | Value                                  |
|----------|----------------------------------------|
| Name     | Priya Raman                            |
| Email    | priya.raman@example.com                |
| Phone    | (360) 555-0153                         |
| Location | Kestrel Bay, WA                        |
| GitHub   | https://code.example.com/priyaraman    |

## Languages

- English (native)
- Tamil (conversational)

## Professional Summary

Senior security engineer with twelve years in security operations and cloud
security, the last seven focused on AWS. Builds detection engineering programs,
hardens IAM, and runs incident response, and has stood up a security program
from nothing at an early-stage startup.

The last three roles lasted between nine months and two years, for reasons
outside her control: a layoff, a startup that shut down, and a company-wide
restructuring. Each one shipped
durable results: SOC 2 Type II at a 45-person health startup, Okta single
sign-on across 38 applications, and an IAM and detection overhaul at a payments
company that passed its PCI DSS assessment.

Writes Python and Terraform daily and prefers guardrails that engineers do not
have to think about over policies they have to remember.

## Technical Skills -- Master List

### Cloud Security
- AWS (7 years): IAM, Organizations and SCPs, GuardDuty, Security Hub, CloudTrail, Config, KMS, VPC design
- IAM hardening: least-privilege roles, IAM Identity Center (SSO), access reviews, removing long-lived keys
- Terraform (6 years): security guardrails, account baselines, and policy-as-code checks with OPA and Conftest
- Container security for Amazon ECS: image scanning with Trivy and runtime logging

### Detection and Response
- Detection engineering: detections as code in Sigma, tested in CI and deployed to Splunk
- Splunk (12 years): searches, dashboards, and correlation rules
- Incident response: playbooks, incident command, forensics triage, and blameless postmortems
- Tabletop exercises for engineering and executive audiences
- Phishing analysis and response automation

### Application and Product Security
- Threat modeling with STRIDE for new services and major changes
- Static analysis in CI with Semgrep, including custom rules
- Security champions programs and secure code review guidelines
- Coordinating third-party penetration tests and tracking remediation

### Governance and Compliance
- SOC 2 Type I and Type II readiness and audits
- PCI DSS 4.0 scoping, segmentation testing, and evidence collection
- HIPAA security risk assessments and business associate agreements
- Vulnerability management programs and remediation SLAs

### Identity and Endpoint
- Okta: SSO, SCIM provisioning, and MFA policies
- CrowdStrike Falcon endpoint detection and response
- Device management for macOS laptops

### Programming
- Python (10 years): automation, Lambda functions, detection tooling
- Go (2 years, reading and small tools)
- Bash and SQL for log analysis

## Certifications

- CISSP, 2020
- AWS Certified Security -- Specialty, 2022
- GIAC Certified Incident Handler (GCIH), 2016

## Career History -- Complete and Detailed

### Fernhill Payments -- Senior Security Engineer
**2024-09 to 2026-08** | Kestrel Bay, WA

Payment processing company with about 600 employees and 62 AWS accounts.
Security team of seven. Position eliminated in a company-wide restructuring
that cut 30% of staff in 2026-08.

- Led an IAM hardening program that replaced long-lived access keys with SSO and role-based access, reducing IAM users with active keys from 214 to 9
- Built the detection engineering pipeline: detections written in Sigma, unit-tested in CI, and deployed to Splunk; wrote 65 detections and cut the alert false-positive rate from 70% to 22%
- Incident commander for 4 high-severity incidents, including a leaked third-party API key that was contained within 40 minutes; wrote the incident response playbooks used by the on-call rotation
- Ran 6 tabletop exercises, two of them for the executive team
- Owned AWS guardrails in Terraform: SCPs, Config rules, and Conftest checks in CI that block public S3 buckets and unencrypted databases before deploy
- Scoped the cardholder data environment and led segmentation testing for the 2025 PCI DSS 4.0 assessment, which closed with zero open findings
- Ran STRIDE threat modeling sessions for 11 new services with their engineering teams
- Started a security champions program of 14 engineers across 8 teams and mentored 2 junior security engineers
- Tools: AWS, Terraform, Splunk, Sigma, Python, Okta, CrowdStrike

### Quillon Health -- Senior Security Engineer
**2023-08 to 2024-07** | Remote

Digital health startup with 45 employees. First security hire, reporting to
the CTO. The company wound down operations in 2024-07 after it could not raise
its next funding round.

- Built the security program from scratch: policies, risk register, vendor reviews, and an incident response plan
- Led the company to a SOC 2 Type I report in 5 months and a SOC 2 Type II report in 11 months
- Completed the HIPAA security risk assessment and set up business associate agreements with 12 vendors
- Rolled out Okta SSO with MFA and device management for all 45 laptops
- Added Semgrep and dependency scanning to CI for the 3 product repositories, with a weekly triage of findings
- Tools: AWS, Terraform, Okta, Semgrep, Python

### Brightloom Analytics -- Senior Security Engineer
**2022-10 to 2023-06** | Kestrel Bay, WA

Business analytics software company with about 300 employees. Laid off in an
18% reduction in force in 2023-06.

- Rolled out Okta SSO and SCIM provisioning to 38 SaaS applications, cutting offboarding from 3 days to same day
- Integrated Trivy container image scanning into CI for 60 ECS services and set remediation SLAs with engineering managers
- Wrote 9 custom Semgrep rules for the company's most common injection and authorization mistakes
- Coordinated the annual third-party penetration test and tracked all high findings to closure within 30 days
- Tools: AWS, Okta, Trivy, Semgrep, Splunk

### Coldharbor Telecom -- Security Engineer
**2017-09 to 2022-09** | Kestrel Bay, WA

Regional telecommunications provider with about 4,000 employees. Promoted from
the security operations center to the security engineering team.

- Secured the company's move of 140 internal applications to AWS between 2019 and 2022: account baseline in Terraform, centralized CloudTrail logging, and GuardDuty in every account
- Cut the median time to remediate critical vulnerabilities from 41 days to 12 days by assigning owners automatically and reporting weekly to directors
- Deployed CrowdStrike Falcon to 5,200 endpoints and retired the legacy antivirus product
- Wrote Python automation for phishing triage that saved the security operations center about 15 hours a week
- Coordinated annual third-party penetration tests and verified each remediation
- Tools: AWS, Terraform, Splunk, CrowdStrike, Python

### Coldharbor Telecom -- Security Analyst
**2014-07 to 2017-08** | Kestrel Bay, WA

Security operations center analyst on a team of eight, working a rotating
shift schedule.

- Triaged about 120 alerts per shift in Splunk and escalated confirmed incidents
- Wrote 30 runbooks for the most common alert types
- Handled phishing reports and led the response to a 2016 credential phishing campaign that targeted 600 employees
- Tools: Splunk, Python, Wireshark

## Key Achievements

- IAM users with long-lived keys reduced from 214 to 9 at Fernhill Payments
- 65 detections as code; alert false-positive rate cut from 70% to 22%
- SOC 2 Type II in 11 months as the first security hire at Quillon Health
- Median time to remediate critical vulnerabilities from 41 days to 12 days at Coldharbor Telecom

## Education

### Ridgeway Polytechnic -- BS, Computer Science
**2010-09 to 2014-05** | Ridgeway, WA

- Concentration in networks and security
- President of the student cybersecurity club; competed in collegiate capture-the-flag events

## Employment Notes

- 2023-06 to 2023-08: two months between Brightloom and Quillon after the layoff
- 2026-08 to present: looking for a senior or staff cloud security role after the Fernhill restructuring
- References from the Fernhill CISO and the Quillon CTO are available

## Strengths

- Calm incident commander who writes things down as they happen
- Builds guardrails engineers barely notice instead of review queues
- Explains risk to executives in money and time, not acronyms
- Gets a security program working quickly in a new environment

## Passions & Interests

- Mentors women entering security through a regional meetup
- Sea kayaking
- Builds a home lab to test new detections
