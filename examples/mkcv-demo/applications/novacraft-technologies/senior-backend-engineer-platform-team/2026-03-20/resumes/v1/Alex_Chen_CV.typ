// Import the rendercv function and all the refactored components
#import "@preview/rendercv:0.2.0": *

// Apply the rendercv template with custom configuration
#show: rendercv.with(
  name: "Alex Chen",
  title: "Alex Chen - CV",
  footer: context { [#emph[Alex Chen -- #str(here().page())\/#str(counter(page).final().first())]] },
  top-note: [ #emph[Last updated in Mar 2026] ],
  locale-catalog-language: "en",
  text-direction: ltr,
  page-size: "us-letter",
  page-top-margin: 0.7in,
  page-bottom-margin: 0.7in,
  page-left-margin: 0.7in,
  page-right-margin: 0.7in,
  page-show-footer: true,
  page-show-top-note: true,
  colors-body: rgb(0, 0, 0),
  colors-name: rgb(0, 0, 0),
  colors-headline: rgb(0, 0, 0),
  colors-connections: rgb(0, 0, 0),
  colors-section-titles: rgb(0, 0, 0),
  colors-links: rgb(0, 0, 0),
  colors-footer: rgb(128, 128, 128),
  colors-top-note: rgb(128, 128, 128),
  typography-line-spacing: 0.6em,
  typography-alignment: "justified",
  typography-date-and-location-column-alignment: right,
  typography-font-family-body: "New Computer Modern",
  typography-font-family-name: "New Computer Modern",
  typography-font-family-headline: "New Computer Modern",
  typography-font-family-connections: "New Computer Modern",
  typography-font-family-section-titles: "New Computer Modern",
  typography-font-size-body: 10pt,
  typography-font-size-name: 30pt,
  typography-font-size-headline: 10pt,
  typography-font-size-connections: 10pt,
  typography-font-size-section-titles: 1.4em,
  typography-small-caps-name: false,
  typography-small-caps-headline: false,
  typography-small-caps-connections: false,
  typography-small-caps-section-titles: false,
  typography-bold-name: true,
  typography-bold-headline: false,
  typography-bold-connections: false,
  typography-bold-section-titles: true,
  links-underline: true,
  links-show-external-link-icon: false,
  header-alignment: center,
  header-photo-width: 3.5cm,
  header-space-below-name: 0.7cm,
  header-space-below-headline: 0.7cm,
  header-space-below-connections: 0.7cm,
  header-connections-hyperlink: true,
  header-connections-show-icons: false,
  header-connections-display-urls-instead-of-usernames: true,
  header-connections-separator: "•",
  header-connections-space-between-connections: 0.5cm,
  section-titles-type: "with_full_line",
  section-titles-line-thickness: 0.5pt,
  section-titles-space-above: 0.5cm,
  section-titles-space-below: 0.3cm,
  sections-allow-page-break: true,
  sections-space-between-text-based-entries: 0.3em,
  sections-space-between-regular-entries: 1.2em,
  entries-date-and-location-width: 4.15cm,
  entries-side-space: 0.2cm,
  entries-space-between-columns: 0.1cm,
  entries-allow-page-break: false,
  entries-short-second-row: false,
  entries-degree-width: 1cm,
  entries-summary-space-left: 0cm,
  entries-summary-space-above: 0cm,
  entries-highlights-bullet:  "◦" ,
  entries-highlights-nested-bullet:  "◦" ,
  entries-highlights-space-left: 0.15cm,
  entries-highlights-space-above: 0cm,
  entries-highlights-space-between-items: 0cm,
  entries-highlights-space-between-bullet-and-text: 0.5em,
  date: datetime(
    year: 2026,
    month: 3,
    day: 20,
  ),
)


= Alex Chen

  #headline([Senior platform engineer with 9 years building high-throughput distributed systems, specializing in event-driven architectures and developer platform acceleration.])

#connections(
  [San Francisco, CA],
  [#link("mailto:alex.chen@example.com", icon: false, if-underline: false, if-color: false)[alex.chen\@example.com]],
  [#link("tel:+1-415-555-0100", icon: false, if-underline: false, if-color: false)[(415) 555-0100]],
  [#link("https://alexchen.example.com/", icon: false, if-underline: false, if-color: false)[alexchen.example.com]],
  [#link("https://linkedin.com/in/alexchen-example", icon: false, if-underline: false, if-color: false)[linkedin.com\/in\/alexchen-example]],
  [#link("https://github.com/alexchen-example", icon: false, if-underline: false, if-color: false)[github.com\/alexchen-example]],
)


== Experience

#regular-entry(
  [
    #strong[Senior Staff Engineer]

    #emph[Arcline Systems]

  ],
  [
    #emph[San Francisco, CA (Hybrid)]

    #emph[Jan 2023 – present]

  ],
  main-column-second-row: [
    - Designed and implemented company-wide API Gateway using Go and Envoy Proxy, consolidating 12 legacy ingress configurations and reducing p99 latency from 340ms to 85ms for all customer-facing endpoints serving 200+ microservices

    - Architected event-driven order processing pipeline on Apache Kafka and Python, replacing synchronous monolith and improving throughput from 500 to 8,000 orders per minute during peak traffic, demonstrating ability to scale high-throughput systems for transaction processing

    - Built internal developer platform with self-service deployment tooling using Kubernetes (EKS), Terraform, and Infrastructure as Code practices, reducing average deploy time from 45 minutes to 4 minutes and cutting deployment failures by 72\% across 6-engineer Platform Team

    - Mentored 3 mid-level engineers to senior promotions over 18 months through weekly 1:1s, System Design reviews, and stretch assignments on cross-team projects, demonstrating Technical Leadership in platform team context

    - Drove adoption of gRPC and Protocol Buffers for internal service communication across distributed systems, migrating 34 REST endpoints and reducing inter-service payload sizes by 60\% while improving type safety

  ],
)

#regular-entry(
  [
    #strong[Senior Software Engineer]

    #emph[Meridian Health Technologies]

  ],
  [
    #emph[Remote]

    #emph[Mar 2020 – Dec 2022]

  ],
  main-column-second-row: [
    - Built real-time data synchronization service in Python (FastAPI) and PostgreSQL processing 2.3M events per day with 99.97\% uptime over 18 months, demonstrating high-throughput systems expertise critical for payment processing platforms

    - Designed and implemented HIPAA-compliant audit logging system using Apache Kafka and Elasticsearch for event streaming, enabling full request traceability and passing 3 consecutive compliance audits with zero findings — demonstrating regulatory compliance expertise applicable to PCI-DSS and SOC 2 requirements

    - Optimized PostgreSQL query performance for reporting module, reducing average query time from 12 seconds to 800ms by implementing materialized views, composite indexes, and connection pooling — critical skills for fintech transaction databases

  ],
)

#regular-entry(
  [
    #strong[Software Engineer]

    #emph[BrightPath Education]

  ],
  [
    #emph[New York, NY]

    #emph[June 2017 – Feb 2020]

  ],
  main-column-second-row: [
    - Designed and implemented RESTful API layer serving 15,000 requests per second at peak using Python (Django) with Redis caching, demonstrating ability to build high-throughput systems approaching the scale requirements for payment platforms

    - Led migration from single PostgreSQL instance to read-replica architecture, improving read query throughput by 4x and eliminating downtime during traffic spikes — essential for maintaining payment system availability

  ],
)

== Skills

#strong[Languages & Frameworks:] Python, Go, PostgreSQL, FastAPI, Django, gRPC, Protocol Buffers

#strong[Platform & Infrastructure:] Kubernetes, AWS (EKS, ECS, Lambda), Docker, Terraform, Infrastructure as Code, API Gateway (Envoy), Service Mesh

#strong[Data & Streaming:] Apache Kafka, Event Streaming, Redis, Elasticsearch, High-throughput systems

#strong[Architecture & Leadership:] Microservices, Distributed Systems, System Design, Technical Leadership, Mentoring

== Education

#education-entry(
  [
    #strong[Columbia University]

  ],
  [
    #emph[Sept 2013 – May 2015]

  ],
  main-column-second-row: [
    #emph[M.S.] #emph[in] #emph[Computer Science]

    - Focus: Distributed Systems and Machine Learning

    - Teaching Assistant for Operating Systems (2 semesters)

  ],
)

#education-entry(
  [
    #strong[University of California, Berkeley]

  ],
  [
    #emph[Sept 2009 – May 2013]

  ],
  main-column-second-row: [
    #emph[B.S.] #emph[in] #emph[Computer Science]

    - Dean's List (6 semesters)

    - Senior capstone: distributed key-value store with Raft consensus

  ],
)

== Languages

#strong[English:] Native

#strong[Mandarin:] Conversational
