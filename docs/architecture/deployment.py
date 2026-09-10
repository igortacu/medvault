"""D2 — MedVault deployment topology.

One DigitalOcean Droplet, one Docker Compose stack, manual deploys.

Source of truth: MedVault — Technical Requirements Specification v1.1 §2.1
(Docker Compose, Alembic), §2.3 (Database Setup & Migration Strategy), §4
Availability ("single instance per service; no high-availability requirement"),
and §6 R6. No load balancer, no replicas, no CI/CD, no staging environment —
none of those exist in the design.

Three facts the picture has to carry:
  * Caddy is the ONLY process with a port published to the host.
  * Secrets travel .env (chmod 600, never committed) -> container environment.
  * Schema changes reach the database ONLY as a blocking migration step run by
    the `migrator` role before the application starts (§2.3, R6).

Run:  .venv/bin/python deployment.py     ->  deployment.png
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.digitalocean.compute import Droplet
from diagrams.generic.blank import Blank
from diagrams.generic.network import Firewall
from diagrams.generic.storage import Storage
from diagrams.onprem.client import User, Users
from diagrams.onprem.container import Docker
from diagrams.onprem.database import PostgreSQL
from diagrams.onprem.inmemory import Redis
from diagrams.onprem.network import Caddy, Internet
from diagrams.programming.framework import FastAPI, React

GRAPH_ATTR = {
    "fontsize": "20",
    "labelloc": "t",
    "pad": "0.75",
    "nodesep": "0.7",
    "ranksep": "1.5",
    "splines": "spline",
}
NODE_ATTR = {"fontsize": "12"}
EDGE_ATTR = {"fontsize": "10"}

# Same colour vocabulary as D1.
PUBLIC = "#1a7f37"   # traffic that crosses the host boundary
INTERNAL = "#57606a" # traffic that never leaves Docker
SECRET = "#b7410e"   # secret material
ADMIN = "#8250df"    # operator actions
SCHEMA = "#bf8700"   # DDL — migrator role only, never the running app

with Diagram(
    "MedVault — D2: Deployment (single DigitalOcean Droplet)",
    filename="deployment",
    show=False,
    direction="TB",
    graph_attr=GRAPH_ATTR,
    node_attr=NODE_ATTR,
    edge_attr=EDGE_ATTR,
):
    patients = Users("Patients / Caregivers\nbrowser")
    internet = Internet("Internet")
    admin = User("Droplet administrator\n(deploys by hand)")

    with Cluster("DigitalOcean Droplet — Ubuntu, single instance"):

        firewall = Firewall("ufw\nALLOW 22 (SSH, key only)\nALLOW 80, 443\nDENY everything else")

        env_file = Blank("/srv/medvault/.env\nchmod 600, owner root\nNOT in git (.gitignore)")

        with Cluster("Docker Compose stack"):
            compose = Docker("docker compose\ngit pull && up -d --build")

            with Cluster("schema lifecycle — DDL never runs as app_user (§2.3)"):
                bootstrap = Blank(
                    "bootstrap script — ONCE per instance\n"
                    "creates roles, medvault schema, extensions"
                )
                migrate = Blank(
                    "alembic upgrade head — every deploy\n"
                    "blocking, runs as migrator\ncontainer exits if it fails (R6)"
                )

            with Cluster("published to host: 80/443 — the ONLY one"):
                caddy = Caddy("caddy\nTLS via Let's Encrypt\nautomatic issue + renew")

            with Cluster("network medvault_internal — zero ports published on the host"):
                frontend = React("frontend\nnginx, static build")
                backend = FastAPI("backend\nFastAPI")
                institution_mock = FastAPI("institution-mock")
                sms_mock = FastAPI("sms-mock\ncode visible only in\ndocker compose logs")
                postgres = PostgreSQL("postgres")
                redis = Redis("redis")
                minio = Storage("minio")

            with Cluster("named volumes (persistent)"):
                vol_pg = Storage("postgres_data")
                vol_redis = Storage("redis_data")
                vol_minio = Storage("minio_data")
                vol_caddy = Storage("caddy_data\nTLS certs + ACME account")

    # --- Public traffic ------------------------------------------------------
    patients >> Edge(color=PUBLIC) >> internet
    internet >> Edge(color=PUBLIC, label="443 / 80") >> firewall
    firewall >> Edge(color=PUBLIC, label="only 80 + 443\nreach a container") >> caddy

    # --- Schema lifecycle, before any traffic is served ----------------------
    # §2.3 splits these deliberately: bootstrap assumes nothing exists and runs
    # once; migrations assume bootstrap already ran and run on every deploy.
    compose >> Edge(color=SCHEMA, style="dotted", label="first boot only") >> bootstrap
    bootstrap >> Edge(color=SCHEMA, style="dotted", label="CREATE ROLE / SCHEMA / EXTENSION") >> postgres

    # Ordering edge: §2.3 says bootstrap runs once, and from that point on all
    # schema evolution goes through versioned migrations. It also keeps the two
    # zero-width Blank nodes on separate ranks so their labels do not collide.
    bootstrap >> Edge(color=SCHEMA, style="dotted", label="from then on,\nonly migrations") >> migrate
    compose >> Edge(color=SCHEMA, style="bold", label="step 1 — every deploy") >> migrate
    migrate >> Edge(color=SCHEMA, style="bold", label="DDL as migrator\n(owns the schema)") >> postgres
    migrate >> Edge(color=SCHEMA, style="bold", label="step 2 — only if step 1 succeeded\nthen serve traffic as app_user") >> backend

    # --- Inside the stack ----------------------------------------------------
    caddy >> Edge(color=INTERNAL, label="/") >> frontend
    caddy >> Edge(color=INTERNAL, label="/api/*") >> backend
    caddy >> Edge(color=INTERNAL, label="/institution/*") >> institution_mock

    # sms-mock is deliberately NOT behind Caddy: nothing outside the Docker
    # network can reach it, so the verification code cannot leak over HTTP.
    backend >> Edge(color=INTERNAL, style="dashed", label="internal only\nnever routed by Caddy") >> sms_mock

    for store in (postgres, redis, minio):
        backend >> Edge(color=INTERNAL) >> store

    postgres >> Edge(color=INTERNAL, style="dotted") >> vol_pg
    redis >> Edge(color=INTERNAL, style="dotted") >> vol_redis
    minio >> Edge(color=INTERNAL, style="dotted") >> vol_minio
    caddy >> Edge(color=INTERNAL, style="dotted") >> vol_caddy

    # --- Secrets -------------------------------------------------------------
    env_file >> Edge(color=SECRET, style="bold", label="env vars at container start\n(no secret manager — out of scope)") >> compose

    # --- Manual deploy -------------------------------------------------------
    admin >> Edge(color=ADMIN, label="SSH :22 (key)") >> firewall
    admin >> Edge(color=ADMIN, style="dashed", label="git pull &&\ndocker compose up -d --build") >> compose
