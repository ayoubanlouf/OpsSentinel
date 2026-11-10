# Operational Runbook: SSL/TLS Certificate Expiration & Renewal Failures

## Service Information
- **Service Name**: Public Ingress & Edge TLS Termination
- **Severity**: P1 / Critical
- **Category**: Security, Networking & Public Endpoints
- **Owning Team**: Edge Network & Security SRE

---

## 1. Overview & Incident Description
Public HTTPS endpoints rely on X.509 SSL/TLS certificates issued by trusted Certificate Authorities (e.g., Let's Encrypt, DigiCert, Cloudflare). When automatic renewal mechanisms (e.g. `cert-manager`, ACME bots) fail silently or automated validation webhooks encounter DNS/firewall blockages, certificates expire. Client browsers and API consumers immediately reject connections with TLS handshake errors, causing total outage for affected domains.

---

## 2. Common Symptoms & Alert Triggers
- **Prometheus Alert**: `SSLCertExpiringSoon` (< 7 days) or `SSLCertExpired` (0 days).
- **Client & Browser Errors**:
  - `NET::ERR_CERT_DATE_INVALID` (Chrome)
  - `SEC_ERROR_EXPIRED_CERTIFICATE` (Firefox)
  - `curl: (60) SSL certificate problem: certificate has expired`
  - `requests.exceptions.SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]`
- **Log Signatures**:
  - `cert-manager controller: Failed to obtain certificate: ACME error: urn:ietf:params:acme:error:connection`

---

## 3. Diagnostic Procedures

### 3.1 Verify Live Certificate Validity via OpenSSL
Test the active TLS handshake directly from your terminal:
```bash
echo | openssl s_client -servername api.opssentinel.io -connect api.opssentinel.io:443 2>/dev/null | openssl x509 -noout -dates -issuer -subject
```

### 3.2 Inspect Kubernetes Cert-Manager Status
Check certificate resources and renewal orders:
```bash
# Check certificate status
kubectl get certificate -A
kubectl describe certificate api-opssentinel-tls -n ingress-nginx

# Check certificate request and order objects
kubectl get certificaterequest -n ingress-nginx
kubectl describe order -n ingress-nginx
```

### 3.3 Check ACME Challenge Pods and Ingress Rules
Verify if the ACME HTTP-01 challenge solver pod or DNS-01 webhook is reachable:
```bash
kubectl get challenges -n ingress-nginx
kubectl logs -n cert-manager -l app=cert-manager --tail=100
```

---

## 4. Immediate Mitigation Steps

### Step 1: Force Cert-Manager Renewal Trigger
Force cert-manager to re-attempt issuance by touching the Certificate custom resource:
```bash
# Using cmctl plugin
cmctl renew api-opssentinel-tls -n ingress-nginx

# Or deleting the active secret to force immediate re-creation
kubectl delete secret api-opssentinel-tls -n ingress-nginx
```

### Step 2: Swap to Emergency Wildcard or Backup Certificate
If the automated ACME flow is blocked by Let's Encrypt rate limits or DNS outages, patch the ingress to use a valid backup wildcard certificate:
```bash
kubectl patch ingress opssentinel-api -n production -p '
{
  "spec": {
    "tls": [
      {
        "hosts": ["api.opssentinel.io"],
        "secretName": "ops-wildcard-backup-tls"
      }
    ]
  }
}'
```

### Step 3: Manual ACME / Let's Encrypt Generation (Certbot Standalone)
If automated cert-manager fails completely:
```bash
certbot certonly --manual --preferred-challenges dns -d api.opssentinel.io
# Create TLS secret manually
kubectl create secret tls api-opssentinel-tls \
  --cert=/etc/letsencrypt/live/api.opssentinel.io/fullchain.pem \
  --key=/etc/letsencrypt/live/api.opssentinel.io/privkey.pem \
  -n ingress-nginx --dry-run=client -o yaml | kubectl apply -f -
```

### Step 4: Reload Ingress Controller
Ensure NGINX / Envoy reloads the new TLS secret:
```bash
kubectl rollout restart deployment/ingress-nginx-controller -n ingress-nginx
```

---

## 5. Long-Term Remediation
1. **Certificate Monitoring**: Configure Blackbox Exporter probe with Prometheus alerting when expiration is <= 30 days.
2. **Dual-Provider Redundancy**: Configure cert-manager with fallback ClusterIssuer (e.g. ZeroSSL or Google Trust Services ACME).
3. **Automated End-to-End Synthetic Health Checks**: Run daily synthetic tests against all public HTTPS endpoints.

---

## 6. Escalation Matrix
- **L1 / On-Call SRE**: Triage immediately upon `SSLCertExpiringSoon` (< 7 days) alert.
- **L2 / Security Engineering**: Escalate if ACME CA account is suspended or blocked.
- **Incident Commander**: Immediate P1 incident if client requests are actively failing.
