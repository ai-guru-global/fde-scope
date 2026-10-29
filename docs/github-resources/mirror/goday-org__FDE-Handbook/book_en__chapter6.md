<!-- fde-scope mirror · repo: goday-org/FDE-Handbook · license: MIT · commit: 229db7b57e3362f3a66c3b757b1cb0c264e69535
     upstream path: book_en/chapter6.md · retrieved: 2026-10-06 · verbatim; report issues upstream. -->

# Chapter 6: High-Security Perimeters and Compliance (VPC SC)

In the enterprise world, identity access management (IAM) is not considered a sufficient security control on its own. If a compromised credential or misconfigured IAM policy allows access, sensitive data can still be exfiltrated to unauthorized locations on the public internet. For high-security environments, such as banking or healthcare, organizations implement physical and logical service boundaries.

In Google Cloud, this is achieved using **VPC Service Controls (VPC SC)**. VPC SC establishes a security perimeter around sensitive APIs (like Cloud Storage, BigQuery, and Vertex AI) to prevent data from crossing the network boundary, even if a user has full admin credentials.

This chapter dissects the mechanics of VPC SC, provides a complete Terraform manifest to establish a security perimeter, and outlines troubleshooting playbooks for resolving boundary violations.

---

## 1. VPC Service Controls: Security Perimeters

VPC SC acts as an API-level firewall. When an API is protected by a perimeter, calls to that API are blocked unless the request originates from within the perimeter or is explicitly permitted by an ingress policy.


<svg viewBox="0 0 750 250" width="100%" height="auto" style="background-color: #fafafa; border: 1px solid #e1e1e8; border-radius: 4px; margin: 20px 0; display: block;">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#333" />
    </marker>
  </defs>

  <!-- Outside (Public Web / Attacker) -->
  <rect x="20" y="70" width="160" height="110" fill="#ffebee" stroke="#c62828" stroke-width="2" rx="6" />
  <text x="100" y="95" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="12" fill="#c62828">OUTSIDE INTERNET</text>
  <text x="100" y="125" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#333">Compromised Key or</text>
  <text x="100" y="140" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#333">Public API Request</text>

  <!-- Block Arrow -->
  <line x1="180" y1="125" x2="280" y2="125" stroke="#c62828" stroke-width="2.5" marker-end="url(#arrow)" />
  <text x="230" y="115" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#c62828" font-weight="bold">BLOCKED by VPC-SC</text>

  <!-- VPC Service Controls Perimeter -->
  <rect x="290" y="30" width="440" height="190" fill="#e8f5e9" stroke="#2e7d32" stroke-width="3" stroke-dasharray="6" rx="8" />
  <text x="510" y="55" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="13" fill="#2e7d32">VPC SERVICE CONTROLS PERIMETER</text>

  <!-- Inside Project -->
  <rect x="310" y="80" width="180" height="120" fill="#fff" stroke="#666" rx="4" />
  <text x="400" y="105" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="11" fill="#111">Service Project</text>
  <text x="400" y="130" text-anchor="middle" font-family="monospace" font-size="9" fill="#555">Private GKE Cluster</text>
  <text x="400" y="150" text-anchor="middle" font-family="monospace" font-size="9" fill="#555">Authorized VM nodes</text>

  <!-- Protected APIs -->
  <rect x="520" y="80" width="190" height="120" fill="#e3f2fd" stroke="#1a73e8" rx="4" />
  <text x="615" y="105" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="11" fill="#1a73e8">Protected Google APIs</text>
  <text x="615" y="135" text-anchor="middle" font-family="monospace" font-size="9" fill="#333">bigquery.googleapis.com</text>
  <text x="615" y="155" text-anchor="middle" font-family="monospace" font-size="9" fill="#333">storage.googleapis.com</text>
  <text x="615" y="175" text-anchor="middle" font-family="monospace" font-size="9" fill="#333">vertexai.googleapis.com</text>
</svg>

### Core Mechanisms of VPC SC
1. **Restricted Services**: The list of Google Cloud APIs (like `bigquery.googleapis.com`) that are protected by the perimeter. Once added, calls to these services from outside the perimeter are blocked by default.
2. **Access Levels**: Define conditions (such as client source IPs or corporate device states) under which requests originating outside the perimeter are allowed.
3. **Ingress and Egress Rules**: Explicit rules governing communication across the perimeter boundary. Ingress rules define who can access resources inside the perimeter from outside, while Egress rules define what data can be sent outside the perimeter.

---

## 2. Infrastructure as Code: Terraform Security Perimeter Manifests

Establishing a VPC Service Controls perimeter requires configure Access Context Manager resources. Because VPC SC configuration errors can block API access across an entire organization, these settings should be managed using Terraform.

### Terraform Perimeter Configuration
Below is a complete manifest establishing an Access Context Manager policy, access level, and service perimeter protecting BigQuery, Cloud Storage, and Vertex AI.

```hcl
# vpc_service_controls.tf

# Access Context Manager Policy (Organization Level)
resource "google_access_context_manager_access_policy" "org_policy" {
  parent = "organizations/${var.org_id}"
  title  = "fde-security-policy"
}

# Access Level permitting entry from secure client CIDRs
resource "google_access_context_manager_access_level" "corporate_ips" {
  parent = google_access_context_manager_access_policy.org_policy.name
  name   = "accessPolicies/${google_access_context_manager_access_policy.org_policy.name}/accessLevels/corporate_ips"
  title  = "Corporate IP Range Access"

  basic {
    conditions {
      ip_subnetworks = ["192.168.100.0/24", "10.0.10.0/24"]
    }
  }
}

# The Service Perimeter protecting BigQuery, Cloud Storage, and Vertex AI
resource "google_access_context_manager_service_perimeter" "security_perimeter" {
  parent = google_access_context_manager_access_policy.org_policy.name
  name   = "accessPolicies/${google_access_context_manager_access_policy.org_policy.name}/servicePerimeters/fde_secure_perimeter"
  title  = "FDE High-Security Perimeter"

  status {
    # Service projects enclosed within the perimeter
    resources = ["projects/${var.service_project_number}"]

    # Services protected by the perimeter
    restricted_services = [
      "bigquery.googleapis.com",
      "storage.googleapis.com",
      "vertexai.googleapis.com"
    ]

    # Ingress policy permitting read access from the Access Level
    ingress_policies {
      ingress_from {
        identity_type = "ANY_IDENTITY"
        sources {
          access_level = google_access_context_manager_access_level.corporate_ips.name
        }
      }
      ingress_to {
        resources = ["*"]
        operations {
          service_name = "storage.googleapis.com"
          method_selectors {
            method = "google.storage.objects.get"
          }
        }
      }
    }
  }
}
```

---

## 3. Perimeter Troubleshooting & Dry-Run Diagnoses

When a request violates a VPC SC boundary, the cloud provider blocks the API call and returns a generic `403 Forbidden` error. This can block applications and disrupt operations. FDEs use a structured troubleshooting playbook to diagnose and resolve these violations.

### 1. Active vs. Dry-Run Mode
When deploying a perimeter, FDEs configure it in **Dry-Run Mode** first. In dry-run mode, violations are logged in Cloud Logging but the API calls are not blocked, allowing the FDE to test and refine the configuration before enforcing the boundary.

### 2. Querying Audit Logs for VPC SC Violations
When an API call is blocked, the FDE queries Cloud Logging inside the Host Project using a specific filter to isolate the violation metadata.

```sql
-- Cloud Logging filter to isolate VPC-SC violations
resource.type="audited_resource"
protoPayload.status.code=7
protoPayload.metadata."@type"="type.googleapis.com/google.cloud.audit.VpcServiceControlsAuditMetadata"
```

#### Reading the Violation Metadata payload:
* `callerIp`: The IP address from which the blocked request was made.
* `serviceName`: The targeted Google API (e.g., `bigquery.googleapis.com`).
* `violationReason`: Explains why the call was blocked (such as `NO_MATCHING_ACCESS_LEVEL` or `RESOURCES_NOT_IN_SAME_SERVICE_PERIMETER`).
* `egressViolationInfo`: If the block was caused by an egress policy violation, this section identifies the target project to which the data was being sent.

Using this metadata, the FDE updates the perimeter's ingress or egress policies to permit the required traffic before enforcing the boundary.

---

## Summary

VPC Service Controls are essential for securing enterprise data workloads. By configuring security perimeters, defining precise ingress/egress rules, and analyzing Cloud Logging metadata to troubleshoot violations in dry-run mode, FDEs build secure cloud architectures that comply with enterprise security requirements.
