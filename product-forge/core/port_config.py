"""
Dynamic Port Configuration

Ports are NOT hardcoded. They are derived from:
1. Tech stack (framework defaults) - ANY technology
2. Architecture (services needed)
3. Actual implementation (what's actually used)
4. Deployment environment (dev, staging, prod)

The pipeline updates ports at each stage:
- Ideation: Initial defaults from tech stack hints
- Architecture: Refined based on services needed
- Implementation: Actual ports used (after build)
- Deployment: Environment-specific ports

This module:
- Maps ANY tech stack → default ports (comprehensive coverage)
- Detects port conflicts
- Suggests alternatives
- Generates port allocations
- Tracks port history
"""

import json
import re
import socket
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from datetime import datetime


@dataclass
class PortAllocation:
    """Port allocation for a service"""
    service: str
    internal_port: int  # Inside container
    external_port: int  # Outside container (host)
    protocol: str = "tcp"
    reason: str = ""  # Why this port was chosen
    tech_source: str = ""  # Which tech string it was derived from


@dataclass
class PortConfig:
    """Dynamic port configuration"""
    allocations: Dict[str, PortAllocation] = field(default_factory=dict)
    tech_stack: Dict[str, str] = field(default_factory=dict)
    architecture_services: List[str] = field(default_factory=list)
    environment: str = "development"
    updated_at: str = ""
    updated_by: str = ""  # Which stage updated it


# COMPREHENSIVE port mapping for ALL common technologies
# Pattern: "tech_keyword" → default_port
# The matching is fuzzy - it matches if the tech keyword appears in the tech string
TECH_PORT_REGISTRY = {
    # ============ FRONTEND FRAMEWORKS ============
    "next.js": 3000,
    "nextjs": 3000,
    "react": 3000,
    "create-react-app": 3000,
    "vue": 5173,
    "vue.js": 5173,
    "nuxt": 3000,
    "nuxt.js": 3000,
    "svelte": 5173,
    "sveltekit": 5173,
    "angular": 4200,
    "remix": 3000,
    "gatsby": 8000,
    "astro": 4321,
    "solid": 3000,
    "solid.js": 3000,
    "solidjs": 3000,
    "ember": 4200,
    "ember.js": 4200,
    "backbone": 8080,
    "preact": 8080,
    "alpine": 8080,
    "alpine.js": 8080,
    "lit": 8080,
    "lit-element": 8080,
    "stimulus": 8080,
    "hotwired": 8080,
    "qwik": 5173,
    "vanilla-extract": 3000,
    "htmx": 8080,
    "eleventy": 8080,
    "11ty": 8080,
    "hugo": 1313,
    "jekyll": 4000,
    "pelican": 8000,
    "vite": 5173,
    "parcel": 1234,
    "webpack-dev-server": 8080,
    "storybook": 6006,
    "sanity": 3333,
    "strapi": 1337,
    "directus": 8055,
    "ghost": 2368,
    "wordpress": 8000,
    
    # ============ BACKEND FRAMEWORKS ============
    # Python
    "fastapi": 8000,
    "flask": 5000,
    "django": 8000,
    "tornado": 8888,
    "aiohttp": 8080,
    "bottle": 8080,
    "cherrypy": 8080,
    "falcon": 8000,
    "hug": 8000,
    "sanic": 8000,
    "starlette": 8000,
    "uvicorn": 8000,
    "gunicorn": 8000,
    "hypercorn": 8000,
    
    # Node.js
    "express": 3000,
    "express.js": 3000,
    "nestjs": 3000,
    "nest.js": 3000,
    "koa": 3000,
    "koa.js": 3000,
    "hapi": 3000,
    "fastify": 3000,
    "sails": 1337,
    "loopback": 3000,
    "meteor": 3000,
    "adonis": 3333,
    "feathers": 3030,
    "restify": 8080,
    "polka": 8080,
    
    # Java/JVM
    "spring": 8080,
    "spring boot": 8080,
    "springboot": 8080,
    "quarkus": 8080,
    "micronaut": 8080,
    "vertx": 8080,
    "vert.x": 8080,
    "play": 9000,
    "play framework": 9000,
    "spark": 4567,
    "java spark": 4567,
    "javalin": 7000,
    "helidon": 8080,
    "ktor": 8080,
    
    # Ruby
    "rails": 3000,
    "ruby on rails": 3000,
    "sinatra": 4567,
    "hanami": 2300,
    "grape": 9292,
    
    # PHP
    "laravel": 8000,
    "symfony": 8000,
    "codeigniter": 8080,
    "yii": 8080,
    "slim": 8080,
    "lumen": 8000,
    "phalcon": 8080,
    
    # Go
    "gin": 8080,
    "echo": 8080,
    "fiber": 8080,
    "beego": 8080,
    "revel": 9000,
    "chi": 8080,
    "buffalo": 3000,
    "iris": 8080,
    
    # Rust
    "actix": 8080,
    "actix-web": 8080,
    "rocket": 8000,
    "axum": 3000,
    "warp": 3030,
    "tide": 8080,
    "iron": 3000,
    
    # C#/.NET
    "asp.net": 5000,
    "aspnet": 5000,
    ".net": 5000,
    "dotnet": 5000,
    "blazor": 5000,
    "nancy": 5000,
    "service stack": 5000,
    
    # Elixir/Erlang
    "phoenix": 4000,
    "cowboy": 8080,
    
    # Kotlin
    "ktor": 8080,
    "spring kotlin": 8080,
    
    # Scala
    "akka": 8080,
    "akka-http": 8080,
    "http4s": 8080,
    
    # ============ DATABASES ============
    "postgresql": 5432,
    "postgres": 5432,
    "psql": 5432,
    "mysql": 3306,
    "mariadb": 3306,
    "mongodb": 27017,
    "mongo": 27017,
    "cassandra": 9042,
    "scylladb": 9042,
    "scylla": 9042,
    "cockroachdb": 26257,
    "cockroach": 26257,
    "sqlite": 0,  # File-based, no port
    "oracle": 1521,
    "sql server": 1433,
    "mssql": 1433,
    "dynamodb": 8000,  # Local
    "cosmosdb": 8081,  # Local emulator
    "surrealdb": 8000,
    "neo4j": 7687,  # Bolt
    "neo4j http": 7474,
    "arangodb": 8529,
    "janusgraph": 8182,
    "tigergraph": 9000,
    "clickhouse": 8123,  # HTTP
    "clickhouse tcp": 9000,
    "duckdb": 0,  # Embedded
    "influxdb": 8086,
    "timescaledb": 5432,  # PostgreSQL-based
    "questdb": 9000,
    "doris": 9030,
    "starrocks": 9030,
    "tidb": 4000,
    "memcached": 11211,
    "hazelcast": 5701,
    "ignite": 10800,
    "apache ignite": 10800,
    
    # ============ CACHE ============
    "redis": 6379,
    "redis cluster": 6379,
    "keydb": 6379,
    "dragonfly": 6379,
    "varnish": 6082,
    "squid": 3128,
    
    # ============ SEARCH ENGINES ============
    "elasticsearch": 9200,
    "elastic": 9200,
    "opensearch": 9200,
    "meilisearch": 7700,
    "typesense": 8108,
    "algolia": 0,  # SaaS
    "solr": 8983,
    "apache solr": 8983,
    "vespa": 8080,
    "quickwit": 7280,
    "manticoresearch": 9306,
    "manticore": 9306,
    
    # ============ MESSAGE QUEUES / STREAMING ============
    "rabbitmq": 5672,  # AMQP
    "rabbitmq mgmt": 15672,
    "kafka": 9092,
    "apache kafka": 9092,
    "nats": 4222,
    "mqtt": 1883,
    "mosquitto": 1883,
    "emqx": 1883,
    "activemq": 61616,
    "artemis": 61616,
    "pulsar": 6650,
    "apache pulsar": 6650,
    "beanstalkd": 11300,
    "amazon sqs": 0,  # SaaS
    "amazon msk": 9092,  # Kafka
    "aws sqs": 0,
    "google pubsub": 0,  # SaaS
    "azure service bus": 0,  # SaaS
    "redpanda": 9092,
    "kafka rest": 8082,
    
    # ============ OBJECT STORAGE ============
    "minio": 9000,
    "minio console": 9001,
    "seaweedfs": 8333,
    "garage": 3900,
    "s3": 0,  # SaaS
    "gcs": 0,  # SaaS
    "azure blob": 0,  # SaaS
    "rustfs": 9000,
    
    # ============ MONITORING / OBSERVABILITY ============
    "prometheus": 9090,
    "grafana": 3000,  # Conflicts with web - can be changed
    "tempo": 3200,
    "loki": 3100,
    "jaeger": 16686,  # UI
    "jaeger agent": 6831,
    "jaeger collector": 14268,
    "zipkin": 9411,
    "elk": 9200,  # Elasticsearch
    "logstash": 5044,
    "kibana": 5601,
    "filebeat": 0,  # Agent
    "metricbeat": 0,  # Agent
    "fluentd": 24224,
    "fluent-bit": 24224,
    "datadog": 0,  # SaaS
    "newrelic": 0,  # SaaS
    "sentry": 9000,
    "node-exporter": 9100,
    "cadvisor": 8080,
    "alertmanager": 9093,
    "thanos": 10901,
    "cortex": 9009,
    "mimir": 9009,
    "vector": 8686,
    "signoz": 3301,
    
    # ============ API GATEWAY / LOAD BALANCER ============
    "kong": 8000,  # Conflicts with api - can be changed
    "kong admin": 8001,
    "kong proxy": 8000,
    "ambassador": 8080,
    "emissary": 8080,
    "envoy": 9901,  # Admin
    "envoy proxy": 10000,
    "traefik": 8080,
    "nginx": 80,
    "nginx http": 80,
    "nginx https": 443,
    "haproxy": 80,
    "caddy": 2019,  # Admin
    "caddy http": 80,
    "krakend": 8080,
    "apisix": 9080,
    "tyk": 8080,
    
    # ============ CI/CD ============
    "jenkins": 8080,
    "gitlab": 8929,
    "gitlab runner": 0,
    "argocd": 8080,
    "spinnaker": 8084,
    "drone": 80,
    "woodpecker": 8000,
    "concourse": 8080,
    "buildkite": 0,  # SaaS
    "circleci": 0,  # SaaS
    "github actions": 0,  # SaaS
    
    # ============ ML/AI ============
    "mlflow": 5000,
    "kubeflow": 8080,
    "tensorboard": 6006,
    "jupyter": 8888,
    "jupyterhub": 8000,
    "ray": 8265,  # Dashboard
    "ray serve": 8000,
    "triton": 8000,
    "tensorflow serving": 8501,
    "seldon": 8000,
    "bentoml": 3000,
    "streamlit": 8501,
    "gradio": 7860,
    "label studio": 8080,
    "optuna": 8080,
    "dvc": 0,
    "weights and biases": 0,  # SaaS
    "wandb": 0,
    "langchain": 8000,
    "llamaindex": 8000,
    "ollama": 11434,
    "vllm": 8000,
    "text-generation-inference": 8080,
    "tgi": 8080,
    "llamacpp": 8080,
    "localai": 8080,
    "open-webui": 8080,
    "chroma": 8000,
    "qdrant": 6333,
    "weaviate": 8080,
    "pinecone": 0,  # SaaS
    "milvus": 19530,
    "pgvector": 5432,  # PostgreSQL extension
    "faiss": 0,  # Library
    "annoy": 0,  # Library
    "vespa.ai": 8080,
    
    # ============ AUTH / IDENTITY ============
    "keycloak": 8080,
    "keycloak admin": 9990,
    "auth0": 0,  # SaaS
    "okta": 0,  # SaaS
    "ory": 0,  # SaaS (or self-hosted)
    "ory hydra": 4445,
    "ory kratos": 4433,
    "dex": 5556,  # HTTP
    "dex grpc": 5557,
    "hydra": 4445,
    "kratos": 4433,
    "authentik": 9000,
    "zitadel": 8080,
    "casdoor": 8000,
    "logto": 3001,
    "supertokens": 3567,
    
    # ============ REAL-TIME / WEBSOCKET ============
    "socket.io": 3000,  # Same as express
    "centrifugo": 8000,
    "pusher": 0,  # SaaS
    "ably": 0,  # SaaS
    "pubnub": 0,  # SaaS
    "gotify": 8080,
    "ntfy": 80,
    "apprise": 8000,
    
    # ============ CMS / CONTENT ============
    "strapi": 1337,
    "directus": 8055,
    "sanity": 3333,
    "contentful": 0,  # SaaS
    "prismic": 0,  # SaaS
    "ghost": 2368,
    "netlify cms": 8080,
    "decap": 8080,
    "tinacms": 3000,
    "payload": 3000,
    "keystone": 3000,
    
    # ============ MOBILE / DESKTOP ============
    "react native": 8081,  # Metro bundler
    "metro": 8081,
    "expo": 19000,  # Expo dev server
    "expo go": 19000,
    "flutter": 0,  # No web port
    "ionic": 8100,
    "capacitor": 8100,
    "cordova": 8000,
    "electron": 0,  # Desktop
    "tauri": 1420,
    
    # ============ WEB SERVER ============
    "apache": 80,
    "apache httpd": 80,
    "httpd": 80,
    "iis": 80,
    "lighttpd": 80,
    "openlitespeed": 8088,
    "tomcat": 8080,
    "wildfly": 8080,
    "jboss": 8080,
    "glassfish": 8080,
    "weblogic": 7001,
    "websphere": 9080,
    
    # ============ TESTING / QA ============
    "selenium": 4444,
    "selenium grid": 4444,
    "selenium hub": 4444,
    "playwright": 3000,
    "cypress": 0,  # Local
    "allure": 5050,
    "reportportal": 8080,
    "testrail": 0,  # SaaS
    "browserstack": 0,  # SaaS
    "saucelabs": 0,  # SaaS
    "lambdatest": 0,  # SaaS
    
    # ============ DOCUMENTATION ============
    "swagger": 8080,
    "swagger ui": 8080,
    "redoc": 8080,
    "stoplight": 0,
    "gitbook": 0,  # SaaS
    "docusaurus": 3000,
    "mintlify": 3000,
    "readme": 0,  # SaaS
    "notion": 0,  # SaaS
    
    # ============ LOW-CODE / NO-CODE ============
    "appsmith": 80,
    "budibase": 10000,
    "tooljet": 3000,
    "retool": 0,  # SaaS
    "n8n": 5678,
    "airflow": 8080,
    "prefect": 4200,
    "dagster": 3000,
    "mage": 6789,
    "kestra": 8080,
    
    # ============ PROJECT MANAGEMENT / COLLAB ============
    "jira": 0,  # SaaS
    "confluence": 0,  # SaaS
    "asana": 0,  # SaaS
    "trello": 0,  # SaaS
    "notion": 0,  # SaaS
    "slack": 0,  # SaaS
    "discord": 0,  # SaaS
    "mattermost": 8065,
    "rocketchat": 3000,
    "element": 0,  # SaaS
    "matrix": 8008,
    "synapse": 8008,
    "nextcloud": 80,
    "owncloud": 80,
    "seafile": 80,
    "wikijs": 3000,
    "bookstack": 80,
    "dokuwiki": 80,
    "mediawiki": 80,
    "xwiki": 8080,
    "trilium": 8080,
    "joplin server": 22300,
    "hedgedoc": 3000,
    "etherpad": 9001,
    
    # ============ SCHEDULING / WORKFLOW ============
    "temporal": 7233,
    "temporal ui": 8080,
    "temporalite": 7233,
    "cadence": 7933,
    "zeebe": 26500,
    "camunda": 8080,
    "flowable": 8080,
    "airflow": 8080,
    
    # ============ SERVICE MESH ============
    "istio": 15010,  # Pilot
    "linkerd": 4191,  # Web
    "consul": 8500,  # HTTP
    "consul dns": 8600,
    "consul server": 8300,
    "consul rpc": 8300,
    "etcd": 2379,  # Client
    "etcd peer": 2380,
    "zookeeper": 2181,
    "vault": 8200,
    "nomad": 4646,  # HTTP
    "nomad rpc": 4647,
    "consul connect": 8502,
    
    # ============ BACKUP / STORAGE ============
    "velero": 0,  # K8s
    "restic": 0,  # Backup tool
    "borg": 0,  # Backup tool
    "duplicati": 8200,
    "bacula": 9101,
    
    # ============ TICKETING / HELP DESK ============
    "osTicket": 80,
    "zammad": 8080,
    "glpi": 80,
    "freshdesk": 0,  # SaaS
    "zendesk": 0,  # SaaS
    
    # ============ GIT / VCS ============
    "gitea": 3000,
    "gitea ssh": 22,
    "gogs": 3000,
    "gitlab": 8929,
    "gitbucket": 8080,
    "phabricator": 80,
    "rhodecode": 5000,
    "sourcegraph": 7080,
    
    # ============ BPM / WORKFLOW (additional) ============
    "flowable": 8080,
    "activiti": 8080,
    "bonita": 8080,
    "jbpm": 8080,
    "processmaker": 80,
    "n8n": 5678,
    
    # ============ ERP / CRM ============
    "odoo": 8069,
    "erpnext": 8000,
    "vtigercrm": 80,
    "espocrm": 80,
    "sugarcrm": 80,
    "suitecrm": 80,
    "dolibarr": 80,
    "xibo": 80,
    "invoiceninja": 80,
    "yetiforcecrm": 80,
    
    # ============ INVOICING / BILLING ============
    "killbill": 8080,
    "stripe": 0,  # SaaS
    "chargebee": 0,  # SaaS
    
    # ============ BOOKING / SCHEDULING ============
    "calcom": 80,
    "easyappointments": 80,
    "sabai": 80,
    "bookingpress": 0,  # WP plugin
    
    # ============ ECOMMERCE / SHOPS ============
    "magento": 80,
    "woocommerce": 0,  # WP plugin
    "shopware": 80,
    "prestashop": 80,
    "opencart": 80,
    "oscommerce": 80,
    "mediamarkt": 80,
    "sylius": 80,
    "vendure": 3000,
    "saleor": 8000,
    "medusa": 9000,
    
    # ============ LMS / LEARNING ============
    "moodle": 80,
    "canvas": 80,
    "chamilo": 80,
    "opencart": 80,
    "edx": 80,
    "teachable": 0,  # SaaS
    "udemy": 0,  # SaaS
    "coursera": 0,  # SaaS
    "learndash": 0,  # WP plugin
    "tutorlms": 0,
    "sensei": 0,
    
    # ============ HEALTHCARE ============
    "openemr": 80,
    "openmrs": 8080,
    "hapi fhir": 8080,
    "openelis": 80,
    "orthanc": 8042,  # DICOM
    
    # ============ FINANCE / BANKING ============
    "firefly": 80,
    "firefly iii": 80,
    "actual": 5006,
    "splitwise": 0,  # SaaS
    "wallabag": 80,
    
    # ============ IOT ============
    "thingsboard": 8080,
    "kura": 80,
    "mainflux": 80,
    "emqx": 1883,
    "vernemq": 1883,
    "hivemq": 1883,
    "particle": 0,  # SaaS
    
    # ============ GAMING ============
    "minecraft": 25565,
    "minecraft bedrock": 19132,
    "valheim": 2456,
    "terraria": 7777,
    "csgo": 27015,
    "source": 27015,
    "factorio": 34197,
    "rust": 28015,
    "ark": 7777,
    
    # ============ VIDEOCONFERENCING ============
    "jitsi": 80,
    "jitsi meet": 80,
    "jitsi videobridge": 10000,
    "bigbluebutton": 80,
    "nextcloud talk": 80,
    "element call": 0,
    "livekit": 7880,  # HTTP
    "livekit tcp": 7881,
    "mediasoup": 0,  # Library
    "janus": 8088,
    "medooze": 0,
    "ion-sfu": 7000,
    "aws ivs": 0,  # SaaS
    "agora": 0,  # SaaS
    "twilio": 0,  # SaaS
    "vonage": 0,  # SaaS
    
    # ============ MISC / UTILITIES ============
    "mailhog": 1025,  # SMTP
    "mailhog ui": 8025,
    "mailpit": 1025,
    "mailpit ui": 8025,
    "smtp": 25,
    "smtp submission": 587,
    "smtps": 465,
    "imap": 143,
    "imaps": 993,
    "pop3": 110,
    "pop3s": 995,
    "postfix": 25,
    "dovecot": 143,
    "exim": 25,
    "sendmail": 25,
    "mailcow": 80,
    "mailu": 80,
    "mailtrain": 80,
    "listmonk": 9000,
    "maddy": 80,
    "stalwart": 80,
    
    # DNS
    "bind": 53,
    "named": 53,
    "unbound": 53,
    "powerdns": 53,
    "coredns": 53,
    "knot": 53,
    "nsd": 53,
    
    # FTP
    "ftp": 21,
    "ftps": 990,
    "sftp": 22,
    "vsftpd": 21,
    "proftpd": 21,
    "pure-ftpd": 21,
    
    # SSH
    "ssh": 22,
    "openssh": 22,
    
    # VPN
    "wireguard": 51820,
    "openvpn": 1194,
    "ipsec": 500,  # IKE
    "ipsec nat": 4500,
    "tailscale": 0,  # SaaS
    "zerotier": 9993,
    "cloudflare warp": 0,  # SaaS
    
    # TURN/STUN
    "coturn": 3478,
    "turn": 3478,
    "stun": 3478,
    
    # Proxy
    "squid": 3128,
    "tinyproxy": 8888,
    "privoxy": 8118,
    "polipo": 8123,
    
    # WebRTC
    "kurento": 8888,
    "mediasoup": 0,  # Library
    
    # Build tools
    "jenkins": 8080,
    "drone": 80,
    "woodpecker": 8000,
    "buildbot": 8010,
    "gocd": 8153,
    
    # Package registries
    "nexus": 8081,
    "artifactory": 8081,
    "harbor": 80,
    "registry": 5000,  # Docker registry
    "distribution": 5000,  # Docker
    "jfrog": 8081,
    "sonatype": 8081,
    "npm": 0,  # SaaS
    "pypi": 0,  # SaaS
    "maven central": 0,  # SaaS
    
    # Security / Scanning
    "sonarqube": 9000,
    "sonar": 9000,
    "snyk": 0,  # SaaS
    "trivy": 0,  # CLI
    "clair": 6060,
    "anchore": 8228,
    "dependency-track": 8080,
    "defectdojo": 8080,
    "archerysec": 8000,
    "faraday": 80,
    "wazuh": 55000,
    "ossec": 1514,
    "snort": 0,  # NIDS
    "suricata": 0,  # NIDS
    "fail2ban": 0,  # Service
    "crowdsec": 8080,
    
    # Databases (additional)
    "duckdb": 0,
    "polardb": 1521,  # Oracle-compatible
    "oceanbase": 1521,
    "tidb": 4000,
    "oceanbase mysql": 2881,
    
    # Logging
    "syslog": 514,
    "rsyslog": 514,
    "syslog-ng": 514,
    "graylog": 9000,
    "graylog web": 9000,
    "loggly": 0,  # SaaS
    "splunk": 8000,
    "papertrail": 0,  # SaaS
    "logz.io": 0,  # SaaS
    
    # Feature flags
    "unleash": 4242,
    "launchdarkly": 0,  # SaaS
    "flagsmith": 8000,
    "growthbook": 8080,
    "posthog": 8000,
    "flipt": 8080,
    
    # Error tracking
    "sentry": 9000,
    "bugsnag": 0,  # SaaS
    "rollbar": 0,  # SaaS
    "airbrake": 0,  # SaaS
    "raygun": 0,  # SaaS
    "glitchtip": 8000,
    
    # Analytics
    "matomo": 80,
    "plausible": 8000,
    "umami": 3000,
    "ackee": 3000,
    "google analytics": 0,  # SaaS
    "mixpanel": 0,  # SaaS
    "amplitude": 0,  # SaaS
    "heap": 0,  # SaaS
    "segment": 0,  # SaaS
    
    # A/B Testing
    "growthbook": 8080,
    "eppo": 0,  # SaaS
    "statsig": 0,  # SaaS
    "optimizely": 0,  # SaaS
}


def get_default_port(tech: str) -> Optional[int]:
    """Get default port for ANY technology (handles version strings, fuzzy matching)"""
    if not tech:
        return None
    
    tech_lower = tech.lower().strip()
    
    # Direct exact match
    if tech_lower in TECH_PORT_REGISTRY:
        port = TECH_PORT_REGISTRY[tech_lower]
        return port if port > 0 else None
    
    # Try fuzzy matching - check if any known tech is a substring
    # Sort by length (longest first) to prefer more specific matches
    sorted_techs = sorted(TECH_PORT_REGISTRY.keys(), key=len, reverse=True)
    for known_tech in sorted_techs:
        if known_tech in tech_lower:
            port = TECH_PORT_REGISTRY[known_tech]
            return port if port > 0 else None
    
    return None


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is available on the host"""
    if port <= 0:
        return True  # Non-network services always "available"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect((host, port))
            return False  # Port is in use
    except (socket.error, socket.timeout, OSError):
        return True  # Port is available


def find_available_port(start_port: int, max_attempts: int = 100) -> int:
    """Find next available port starting from start_port"""
    for offset in range(max_attempts):
        port = start_port + offset
        if is_port_available(port):
            return port
    raise RuntimeError(f"Could not find available port starting from {start_port}")


def detect_port_conflicts(allocations: Dict[str, PortAllocation]) -> List[str]:
    """Detect port conflicts in allocations"""
    conflicts = []
    port_to_services: Dict[int, List[str]] = {}
    
    for service, allocation in allocations.items():
        if allocation.external_port <= 0:
            continue
        if allocation.external_port not in port_to_services:
            port_to_services[allocation.external_port] = []
        port_to_services[allocation.external_port].append(service)
    
    for port, services in port_to_services.items():
        if len(services) > 1:
            conflicts.append(f"Port {port} used by: {', '.join(services)}")
    
    return conflicts


def _normalize_tech_key(tech: str) -> str:
    """Normalize a tech string to a service key"""
    if not tech:
        return "unknown"
    
    tech_lower = tech.lower().strip()
    
    # Remove version numbers and extra info
    # e.g. "Next.js 15 + React 19 + TypeScript + Tailwind" → "next.js"
    # e.g. "Python 3.12 + FastAPI" → "fastapi" (last/most-specific)
    # e.g. "PostgreSQL 16 + pgvector" → "postgresql"
    
    # Split by common separators
    parts = re.split(r'[+/,;|]', tech_lower)
    
    # Try each part to find a known tech
    sorted_techs = sorted(TECH_PORT_REGISTRY.keys(), key=len, reverse=True)
    for part in parts:
        part = part.strip()
        for known_tech in sorted_techs:
            if known_tech in part:
                return known_tech
    
    return tech_lower.split()[0] if tech_lower else "unknown"


def derive_ports_from_tech_stack(tech_stack: Dict[str, str], 
                                  architecture_services: List[str] = None,
                                  check_available: bool = True) -> Dict[str, PortAllocation]:
    """
    Derive port allocations from tech stack and architecture services.
    
    Handles ANY tech stack. For each technology mentioned:
    1. Detects the technology (fuzzy match against 400+ known technologies)
    2. Gets the default port
    3. Allocates internal (container) and external (host) ports
    4. Detects conflicts
    5. Suggests alternatives
    
    Returns a dict of service → PortAllocation
    """
    allocations: Dict[str, PortAllocation] = {}
    
    # Map from common tech_stack_hints keys to semantic service names
    TECH_HINTS_TO_SERVICE = {
        "frontend_web": "web",
        "frontend": "web",
        "frontend_mobile": "mobile_dev",
        "backend": "api",
        "api": "api",
        "database": "database",
        "db": "database",
        "cache": "cache",
        "caching": "cache",
        "search": "search",
        "queue": "queue",
        "message_queue": "queue",
        "streaming": "queue",
        "object_storage": "object_storage",
        "storage": "object_storage",
        "monitoring": "monitoring",
        "observability": "monitoring",
        "auth": "auth",
        "authentication": "auth",
        "identity": "auth",
        "ml_platform": "ml_platform",
        "ai": "ml_platform",
        "vector_db": "vector_db",
        "embeddings": "vector_db",
        "real_time": "real_time",
        "websocket": "real_time",
        "cms": "cms",
        "content": "cms",
        "mobile": "mobile_dev",
        "api_gateway": "api_gateway",
        "gateway": "api_gateway",
        "service_mesh": "service_mesh",
        "ci_cd": "ci_cd",
        "dns": "dns",
        "vpn": "vpn",
        "load_balancer": "load_balancer",
        "lb": "load_balancer",
        "reverse_proxy": "reverse_proxy",
        "proxy": "reverse_proxy",
        "cdn": "cdn",
        "feature_flags": "feature_flags",
        "analytics": "analytics",
        "error_tracking": "error_tracking",
        "documentation": "documentation",
        "docs": "documentation",
        "package_registry": "package_registry",
        "registry": "package_registry",
        "mail": "mail",
        "email": "mail",
        "videoconferencing": "videoconferencing",
        "video": "videoconferencing",
    }
    
    # Process tech_stack_hints
    for tech_key, tech_value in tech_stack.items():
        service = TECH_HINTS_TO_SERVICE.get(tech_key.lower())
        if not service:
            # Try to determine service from tech_key
            service = tech_key.lower()
        
        # Skip if not a service we care about
        if service in ("tech_stack_hints", "package_manager_web", "package_manager_api", "monorepo", "auth"):
            # auth handled differently
            if service == "auth":
                # Auth tech — try to detect what auth provider
                default_port = get_default_port(tech_value)
                if default_port and default_port > 0:
                    if "auth" not in allocations:
                        external_port = default_port
                        if check_available and not is_port_available(external_port):
                            external_port = find_available_port(external_port + 1)
                        allocations["auth"] = PortAllocation(
                            service="auth",
                            internal_port=default_port,
                            external_port=external_port,
                            reason=f"Default for {tech_value} (auth provider)",
                            tech_source=tech_value
                        )
            continue
        
        # Get the default port for this tech
        default_port = get_default_port(tech_value)
        if default_port is None or default_port <= 0:
            continue
        
        # Determine internal and external ports
        # For databases, cache: external is offset to avoid host conflicts
        internal_port = default_port
        external_port = default_port
        
        if service == "database" and default_port == 5432:
            external_port = 5433  # Avoid conflict with local postgres
        elif service == "database" and default_port == 3306:
            external_port = 3307  # Avoid conflict with local mysql
        elif service == "cache" and default_port == 6379:
            external_port = 6380  # Avoid conflict with local redis
        elif service == "search" and default_port == 9200:
            external_port = 9201  # Avoid conflict with local elasticsearch
        elif service == "queue" and default_port == 5672:
            external_port = 5673  # Avoid conflict with local rabbitmq
        elif service == "queue" and default_port == 9092:
            external_port = 9093  # Avoid conflict with local kafka
        
        # Check if port is available (only for external ports)
        if check_available and external_port > 0 and not is_port_available(external_port):
            external_port = find_available_port(external_port + 1)
        
        allocations[service] = PortAllocation(
            service=service,
            internal_port=internal_port,
            external_port=external_port,
            reason=f"Default for {tech_value}",
            tech_source=tech_value
        )
    
    # Add ports for additional architecture services
    if architecture_services:
        for service in architecture_services:
            if service in allocations:
                continue  # Already allocated
            
            # Get a default port for this service type
            default_port = None
            tech_options = {
                "web": ["nginx", "caddy", "apache"],
                "api": ["kong", "apisix", "tyk"],
                "database": ["postgresql", "mysql", "mongodb"],
                "cache": ["redis", "memcached"],
                "search": ["elasticsearch", "meilisearch"],
                "queue": ["rabbitmq", "kafka", "nats"],
                "monitoring": ["prometheus", "grafana"],
                "auth": ["keycloak", "authentik"],
                "ml_platform": ["mlflow", "jupyter", "ray"],
                "vector_db": ["qdrant", "weaviate", "chroma"],
                "real_time": ["centrifugo", "socket.io"],
                "cms": ["strapi", "directus", "ghost"],
                "mobile_dev": ["metro", "expo"],
                "api_gateway": ["kong", "apisix"],
                "service_mesh": ["consul", "istio"],
                "ci_cd": ["jenkins", "gitlab", "argocd"],
                "vpn": ["wireguard", "openvpn"],
                "mail": ["mailhog", "mailpit", "mailcow"],
                "videoconferencing": ["jitsi", "livekit", "bigbluebutton"],
            }
            
            for tech in tech_options.get(service, []):
                default_port = get_default_port(tech)
                if default_port and default_port > 0:
                    external_port = default_port
                    if check_available and not is_port_available(external_port):
                        external_port = find_available_port(external_port + 1)
                    
                    allocations[service] = PortAllocation(
                        service=service,
                        internal_port=default_port,
                        external_port=external_port,
                        reason=f"Default for {tech} ({service})",
                        tech_source=tech
                    )
                    break
    
    return allocations


def update_ports_from_config(project_config_path: str, 
                              updated_by: str = "system") -> Dict[str, Any]:
    """
    Update port configuration based on current project state.
    
    Called at various stages:
    - After ideation: from tech_stack_hints
    - After architecture: from architecture services
    - After implementation: from actual config
    """
    config_path = Path(project_config_path)
    with open(config_path) as f:
        config = json.load(f)
    
    tech_stack = config.get("tech_stack_hints", {})
    architecture_services = config.get("architecture_services", [])
    
    # Derive ports
    allocations = derive_ports_from_tech_stack(
        tech_stack, 
        architecture_services,
        check_available=True
    )
    
    # Detect conflicts
    conflicts = detect_port_conflicts(allocations)
    
    # Update config
    port_config = {
        "allocations": {k: asdict(v) for k, v in allocations.items()},
        "tech_stack": tech_stack,
        "architecture_services": architecture_services,
        "environment": config.get("environment", "development"),
        "updated_at": datetime.now().isoformat(),
        "updated_by": updated_by,
        "conflicts": conflicts,
    }
    
    config["ports"] = port_config
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    return port_config


def get_port(project_config: Dict[str, Any], service: str, 
             port_type: str = "external") -> Optional[int]:
    """Get a specific port from project config"""
    ports = project_config.get("ports", {})
    
    if isinstance(ports, dict) and "allocations" in ports:
        allocations = ports["allocations"]
    else:
        allocations = ports  # Legacy format
    
    if service not in allocations:
        return None
    
    allocation = allocations[service]
    if isinstance(allocation, dict):
        return allocation.get(f"{port_type}_port")
    else:
        return getattr(allocation, f"{port_type}_port", None)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python port_config.py <project-config.json> [stage]")
        sys.exit(1)
    
    config_path = sys.argv[1]
    stage = sys.argv[2] if len(sys.argv) > 2 else "system"
    
    port_config = update_ports_from_config(config_path, updated_by=stage)
    
    print(f"Port configuration updated by: {stage}")
    print(f"Allocations: {len(port_config['allocations'])}")
    for service, allocation in port_config["allocations"].items():
        print(f"  {service}: {allocation['external_port']} → {allocation['internal_port']} ({allocation['reason']})")
    
    if port_config["conflicts"]:
        print(f"\n⚠️ Conflicts: {port_config['conflicts']}")
    else:
        print("\n✓ No conflicts")
