<!-- fde-scope mirror · repo: goday-org/FDE-Handbook · license: MIT · commit: 229db7b57e3362f3a66c3b757b1cb0c264e69535
     upstream path: book_en/chapter5.md · retrieved: 2026-10-06 · verbatim; report issues upstream. -->

# Chapter 5: Hybrid Cloud Networking and Landing Zones (GCP)

Deploying enterprise data platforms inside client infrastructure requires a deep understanding of network security and cloud landing zones. Large organizations rarely allow external software to run on public endpoints or connect directly to their databases over open channels. Instead, they require deployments to run within private subnets, connect to legacy systems via secure tunnels, and restrict cloud resource access using least-privilege identity mappings.

This chapter details the GCP landing zone architecture—specifically Shared VPC topologies and GKE private clustering—and provides complete Terraform manifests for provisioning these secure cloud infrastructures.

---

## 1. Landing Zone Topology: Shared VPC

In enterprise setups, network administration is separated from application deployments. Network resources (VPCs, subnets, firewall rules) are managed in a central **Host Project**, while applications run in separate **Service Projects** that access the shared networks.


<svg viewBox="0 0 750 240" width="100%" height="auto" style="background-color: #fafafa; border: 1px solid #e1e1e8; border-radius: 4px; margin: 20px 0; display: block;">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#333" />
    </marker>
  </defs>

  <!-- Host Project Boundary -->
  <rect x="20" y="30" width="310" height="180" fill="#f4f4f6" stroke="#333" stroke-width="2" rx="6" />
  <text x="175" y="50" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="12" fill="#111">HOST PROJECT (Network Admin)</text>
  
  <rect x="40" y="70" width="270" height="120" fill="#fff" stroke="#666" stroke-dasharray="3" rx="4" />
  <text x="175" y="90" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="10" fill="#333">Shared VPC (10.0.0.0/16)</text>
  
  <rect x="60" y="110" width="105" height="60" fill="#e8f0fe" stroke="#1a73e8" rx="3" />
  <text x="112" y="130" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="9" fill="#1a73e8">GKE Subnet</text>
  <text x="112" y="145" text-anchor="middle" font-family="monospace" font-size="8" fill="#555">10.100.0.0/20</text>

  <rect x="185" y="110" width="105" height="60" fill="#e8f0fe" stroke="#1a73e8" rx="3" />
  <text x="237" y="130" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="9" fill="#1a73e8">Services Subnet</text>
  <text x="237" y="145" text-anchor="middle" font-family="monospace" font-size="8" fill="#555">10.200.0.0/20</text>

  <!-- Share Action -->
  <line x1="330" y1="120" x2="410" y2="120" stroke="#1a73e8" stroke-width="2" marker-end="url(#arrow)" />
  <text x="370" y="110" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#1a73e8" font-weight="bold">Share Subnets</text>

  <!-- Service Project Boundary -->
  <rect x="420" y="30" width="310" height="180" fill="#e3f2fd" stroke="#1a73e8" stroke-width="2" rx="6" />
  <text x="575" y="50" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="12" fill="#1a73e8">SERVICE PROJECT (App Deployment)</text>

  <rect x="450" y="80" width="250" height="110" fill="#fff" stroke="#1a73e8" rx="4" />
  <text x="575" y="105" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="11" fill="#111">Private GKE Cluster</text>
  <text x="575" y="125" text-anchor="middle" font-family="monospace" font-size="9" fill="#666">Nodes bound to Host Subnets</text>
  <text x="575" y="140" text-anchor="middle" font-family="monospace" font-size="9" fill="#666">Control Plane on Private IP</text>
</svg>

### Shared VPC Benefits
1. **Network Auditing**: Centralizes firewall management inside the Host Project, allowing the client's network security team to audit traffic without blocking application development in the Service Project.
2. **Access Control**: Isolates GKE clusters and databases from the public internet. External incoming connections are directed through managed landing zones like Cloud Interconnect or Private Service Connect (PSC).

---

## 2. Infrastructure as Code: Provisioning Secure Environments

To ensure landing zones are consistent and reproducible, FDEs declare all configurations in Infrastructure as Code (IaC) using Terraform.

### 1. Host Project Network Configuration
Below is the configuration for establishing a Shared VPC and subnets in the Host Project.

```hcl
# host_network.tf
provider "google" {
  project = var.host_project_id
  region  = var.region
}

resource "google_compute_network" "shared_vpc" {
  name                    = "shared-vpc-network"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "gke_subnet" {
  name          = "gke-private-subnet"
  ip_cidr_range = "10.100.0.0/20"
  network       = google_compute_network.shared_vpc.id
  region        = var.region

  private_ip_google_access = true

  secondary_ip_range {
    range_name    = "gke-pods-range"
    ip_cidr_range = "172.16.0.0/16"
  }

  secondary_ip_range {
    range_name    = "gke-services-range"
    ip_cidr_range = "172.17.0.0/20"
  }
}
```

### 2. Private GKE Cluster Configuration
Below is the configuration for provisioning the GKE private cluster in the Service Project, binding it to the Host Project's shared subnets.

```hcl
# service_gke.tf
provider "google" {
  project = var.service_project_id
  region  = var.region
}

resource "google_container_cluster" "private_cluster" {
  name     = "fde-private-gke-cluster"
  location = var.region

  # Bind cluster to the Host Project's Shared Subnet
  network    = "projects/${var.host_project_id}/global/networks/${google_compute_network.shared_vpc.name}"
  subnetwork = "projects/${var.host_project_id}/regions/${var.region}/subnetworks/${google_compute_subnetwork.gke_subnet.name}"

  # Enable private nodes and private control plane endpoint
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = true
    master_ipv4_cidr_block  = "172.18.0.0/28"
  }

  ip_allocation_policy {
    cluster_secondary_range_name  = "gke-pods-range"
    services_secondary_range_name = "gke-services-range"
  }

  # Enable Workload Identity for secure token mappings
  workload_identity_config {
    workload_pool = "${var.service_project_id}.svc.id.goog"
  }

  node_config {
    machine_type = "e2-standard-4"
    metadata = {
      disable-legacy-endpoints = "true"
    }
  }
}
```

---

## 3. Secure Identity Mapping: Workload Identity

Inside client environments, static credential files (like JSON service account keys) represent a significant security vulnerability. If a key file is committed to a git repository or leaked, unauthorized users gain access to client cloud resources.

FDEs avoid key files by implementing GCP **Workload Identity**. This feature maps Kubernetes service accounts (KSAs) inside GKE directly to Google Cloud service accounts (GSAs), authorizing pods to access cloud APIs (like BigQuery or Vertex AI) using short-lived access tokens.

```hcl
# workload_identity.tf
resource "google_service_account" "platform_gsa" {
  project      = var.service_project_id
  account_id   = "fde-data-processor-gsa"
  display_name = "GSA for data processor app"
}

# Allow Kubernetes service account to impersonate GSA
resource "google_service_account_iam_member" "workload_identity_binding" {
  service_account_id = google_service_account.platform_gsa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.service_project_id}.svc.id.goog[fde-namespace/data-processor-ksa]"
}
```

### Kubernetes Service Account Mapping Manifest
Inside the GKE cluster, the FDE configures the Kubernetes Service Account manifest to reference the GSA.

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: data-processor-ksa
  namespace: fde-namespace
  annotations:
    # Map Kubernetes service account directly to GSA
    iam.gke.io/gcp-service-account: "fde-data-processor-gsa@service-project-id.iam.gserviceaccount.com"
```

Any pod running under the `data-processor-ksa` account can call Google Cloud APIs without requiring static credentials or JSON key files.

---

## Summary

Establishing a secure landing zone is key to deploying applications in enterprise environments. By configuring Shared VPC networks, deploying private GKE clusters, and mapping credentials using Workload Identity, FDEs build secure cloud architectures that comply with enterprise security requirements.
