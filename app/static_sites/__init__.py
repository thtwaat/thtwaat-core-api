"""THTWAAT Deploy — static HTML/ZIP website hosting.

A sibling to app/studio/ (the AI-generated-product deploy engine), not a
replacement for it. Reuses app/domains/ + app/ssl/ for hostname/SSL, and the
same versioned-deployment/rollback/audit/SSE conventions as
StudioProjectDeployment, without touching that table or its FK-constrained
project_id relationship.
"""
