Frame the product as a backend API with infrastructure-as-code. Out of scope: any web UI, mobile apps, customer-facing dashboards. In scope: HTTP endpoints, auth, data model, observability hooks, and the AWS infrastructure that runs the service.

When identifying gaps, pay attention to deployment-relevant questions: expected request volume, data retention requirements, multi-tenancy, region/latency requirements, secrets management, and compliance (PII, PCI, HIPAA) — these all materially shape the Terraform.
