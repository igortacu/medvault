"""MedVault AWS data architecture and retention boundaries.

This is the target AWS topology derived from the application schema and the
Master Test Plan. Institutional medical data is read live and is never copied
into MedVault storage; only self-uploaded files are kept by MedVault.

Run:  .venv/bin/python aws_data_architecture.py
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import ECS
from diagrams.aws.database import Dynamodb, ElastiCache, RDS
from diagrams.aws.management import Cloudwatch
from diagrams.aws.network import CloudFront, ELB, Route53
from diagrams.aws.security import KMS, SecretsManager, WAF
from diagrams.aws.storage import S3
from diagrams.onprem.client import Users

GRAPH_ATTR = {
    "bgcolor": "white",
    "fontsize": "22",
    "labelloc": "t",
    "pad": "0.6",
    "nodesep": "0.65",
    "ranksep": "1.05",
    "splines": "spline",
}
NODE_ATTR = {"fontsize": "11"}
EDGE_ATTR = {"fontsize": "9"}

PUBLIC = "#1a7f37"
APP = "#1f6feb"
LIVE_FHIR = "#8250df"
DATA = "#b7410e"
SECURITY = "#cf222e"
OBSERVABILITY = "#57606a"

with Diagram(
    "MedVault — AWS data flow, storage and retention",
    filename="aws_data_architecture",
    show=False,
    direction="LR",
    graph_attr=GRAPH_ATTR,
    node_attr=NODE_ATTR,
    edge_attr=EDGE_ATTR,
):
    users = Users("Patients / Caregivers\nweb browser")

    with Cluster("Public edge"):
        dns = Route53("Route 53\nmedvault.example")
        cdn = CloudFront("CloudFront\nTLS + Cache-Control")
        waf = WAF("AWS WAF\nrate / request rules")

    with Cluster("AWS account — MedVault VPC"):
        with Cluster("Public entry; workloads remain private"):
            frontend = S3("S3 frontend\nstatic React build\nno patient data")
            alb = ELB("Application Load Balancer\nHTTPS /api/*")

        with Cluster("Private application subnets"):
            api = ECS("ECS Fargate — FastAPI\nauth · RLS context · validation")

        with Cluster("Private data subnets / private S3 access"):
            postgres = RDS(
                "RDS PostgreSQL\nmedvault schema + RLS\naccounts, permissions, metadata, audit\nretention: policy-dependent"
            )
            redis = ElastiCache(
                "ElastiCache Redis\nsessions: idle TTL TBD\nSMS: 5 min · OAuth state: 10 min"
            )
            documents = S3(
                "S3 medvault-documents\nself-uploaded PDF/JPEG/PNG only\nuntil patient deletion"
            )
            exports = S3(
                "S3 medvault-exports\ngenerated PDF/JSON\nshort expiry: exact TTL TBD"
            )

        with Cluster("Security and operations"):
            kms = KMS("AWS KMS\nRDS · Redis · S3 · DynamoDB · logs")
            secrets = SecretsManager("Secrets Manager\nDB/OAuth secrets")
            logs = Cloudwatch("CloudWatch Logs\nno PHI, IDNP or tokens\nretention: 30 days proposed")

    with Cluster("Synthetic institution — separate trust boundary"):
        institution = ECS("ECS Fargate\ninstitution-mock\nSMART on FHIR subset")
        fixtures = S3(
            "S3 mock-fixtures\nFHIR JSON · Binary inline base64\nseeded per environment"
        )
        mock_runtime = Dynamodb(
            "DynamoDB mock-runtime\nPAR <= 90 s · code <= 60 s\ntokens/revocation + access log"
        )

    users >> Edge(color=PUBLIC, label="HTTPS TLS 1.2+") >> dns >> cdn
    waf >> Edge(color=SECURITY, style="dotted", label="attached rules") >> cdn
    cdn >> Edge(color=PUBLIC, label="GET static app") >> frontend
    cdn >> Edge(color=APP, label="HTTPS /api/*") >> alb >> api

    api >> Edge(color=DATA, label="TLS 5432\ntransaction + SET LOCAL") >> postgres
    api >> Edge(color=DATA, label="TLS 6379\nephemeral only") >> redis
    api >> Edge(color=DATA, label="HTTPS SigV4\nvalidated upload") >> documents
    api >> Edge(color=DATA, label="HTTPS SigV4\ncreate / cleanup") >> exports

    api >> Edge(color=LIVE_FHIR, label="HTTPS OAuth2 + FHIR\nlive read; no local copy") >> institution
    institution >> Edge(color=LIVE_FHIR, label="read-only FHIR JSON\nBinary is inline base64") >> fixtures
    institution >> Edge(color=LIVE_FHIR, label="conditional writes + TTL") >> mock_runtime
    secrets >> Edge(color=SECURITY, style="dashed", label="runtime secrets") >> api

    api >> Edge(color=OBSERVABILITY, style="dashed", label="sanitized operational logs") >> logs
    institution >> Edge(color=OBSERVABILITY, style="dashed") >> logs

    api >> Edge(
        color=APP,
        style="dashed",
        label="authorize + issue signed GET\nURL valid <= 5 min",
    ) >> documents
