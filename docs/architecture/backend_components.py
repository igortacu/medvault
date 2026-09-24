"""D1 — MedVault backend components (C4 level 3).

The inside of the FastAPI container: modules, their boundaries, and which store
each one touches.

Source of truth: MedVault — Technical Requirements Specification v1.1, §2.2
(ADR-01..ADR-05), §2.3 (roles: migrator owns DDL, app_user runs the app under
RLS; tables live in the dedicated `medvault` schema) and §4 Maintainability
("modular internal separation within the monolith"). Nothing appears here that
the spec does not call for.

The invariant the picture exists to make obvious: no feature module reaches
PostgreSQL on its own. Every data path goes through `authorization`, which opens
the transaction and sets `app.current_user_id` with SET LOCAL (ADR-02). A
feature module with its own arrow into PostgreSQL would be a design error.

Run:  .venv/bin/python backend_components.py     ->  backend_components.png
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.generic.storage import Storage
from diagrams.onprem.database import PostgreSQL
from diagrams.onprem.inmemory import Redis
from diagrams.programming.framework import FastAPI
from diagrams.programming.language import Python

GRAPH_ATTR = {
    "fontsize": "20",
    "labelloc": "t",
    "pad": "0.75",
    "nodesep": "0.9",
    "ranksep": "2.0 equally",
    "splines": "spline",
    "compound": "true",
}
NODE_ATTR = {"fontsize": "12"}
# Edge labels are the main source of clutter in Graphviz; keep them short and
# small, and put the full explanation in README.md instead.
EDGE_ATTR = {"fontsize": "10"}

# One colour per meaning, used consistently in D1 and D2.
AUTHZ = "#b7410e"    # carries the RLS context
SESSION = "#1f6feb"  # session / opaque cookie traffic
OAUTH = "#8250df"    # OAuth2 + JWT — institution-mock only
PLAIN = "#57606a"

with Diagram(
    "MedVault — D1: Backend Components (C4 L3)",
    filename="backend_components",
    show=False,
    direction="TB",
    graph_attr=GRAPH_ATTR,
    node_attr=NODE_ATTR,
    edge_attr=EDGE_ATTR,
):
    with Cluster("FastAPI container — backend (modular monolith)"):

        with Cluster("feature modules"):
            auth = Python("auth\nsignup · login · SMS verify\nsession lifecycle")
            caregiver = Python("caregiver\ninvite · permissions\nrevoke")
            institutions = Python("institutions\nOAuth2 client\nlive FHIR fetch")
            documents = Python("documents\nself-upload\nmanual categorisation")
            audit = Python("audit\nappend-only log\nactor + subject patient")

        # Its own cluster because it is a tier, not a peer: everything above
        # depends on it and nothing bypasses it.
        with Cluster("cross-cutting — the only path to patient data"):
            authorization = FastAPI(
                "authorization\nFastAPI dependency\nBEGIN + SET LOCAL\napp.current_user_id"
            )

    with Cluster("data stores — network medvault_data"):
        postgres = PostgreSQL(
            "PostgreSQL — schema: medvault\nconnect as app_user\nNOBYPASSRLS · no DDL"
        )
        redis = Redis("Redis\nserver-side sessions\nADR-01")
        minio = Storage("MinIO (S3-compatible)\nserver-side encryption\nopaque objects")

    with Cluster("mock services"):
        institution_mock = FastAPI("institution-mock\nSMART on FHIR subset\nADR-03")
        sms_mock = FastAPI("sms-mock\ncode -> container log\nADR-05")

    # Every feature module depends on authorization. These five arrows are the
    # point of the diagram — a missing one means that module can query without
    # an RLS context.
    for module in (auth, caregiver, institutions, documents, audit):
        module >> Edge(color=AUTHZ, style="bold") >> authorization

    # ...and authorization is the only thing that talks to PostgreSQL.
    (
        authorization
        >> Edge(
            color=AUTHZ,
            style="bold",
            label="query as app_user, in txn\nRLS filters rows\nno context => 0 rows",
        )
        >> postgres
    )
    authorization >> Edge(color=SESSION, label="GET session:{id}\n-> user_id") >> redis

    # Module-specific side effects. None of these touch a patient row.
    auth >> Edge(color=SESSION, label="SETEX session:{id}\nopaque id · TTL") >> redis
    auth >> Edge(color=PLAIN, style="dashed", label="deliver code\nnever in a response") >> sms_mock
    documents >> Edge(color=PLAIN, label="put/get object\nstored, never parsed\nADR-04") >> minio
    (
        institutions
        >> Edge(color=OAUTH, label="/par · /authorize · /token\nlive FHIR reads\nJWT only here — ADR-01")
        >> institution_mock
    )

    # The one deliberate pre-session path. Login must resolve a phone to a user
    # id before a session exists, so no RLS context can exist yet. It runs
    # through a narrow SECURITY DEFINER function returning a single id — not a
    # general read path into the table.
    (
        auth
        >> Edge(
            color=AUTHZ,
            style="dotted",
            label="pre-session only\nSECURITY DEFINER fn -> 1 id\nargon2id verify (FR1/FR2)",
        )
        >> postgres
    )
