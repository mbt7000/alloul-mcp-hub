from __future__ import annotations
from typing import Any
import structlog
from fastmcp import FastMCP
from alloul_workspace.settings import Settings
from shared.db import init_pool
from shared.adapter import HTTPBackendAdapter
from shared.envelope import ok, err

log = structlog.get_logger()


def _adapter(product: str, settings: Settings) -> HTTPBackendAdapter:
    url = settings.alloulq_backend_url if product == "alloulq" else settings.handex_backend_url
    return HTTPBackendAdapter(url)


def create_server(settings: Settings) -> FastMCP:
    mcp = FastMCP("product.workspace", version="0.1.0")


    # ── CRM ──────────────────────────────────────────────────

    @mcp.tool()
    async def crm_list_deals(
        tenant_id: str,
        product: str,
        stage: str | None = None,
        assigned_to: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List CRM deals for a tenant. Proxies to product backend."""
        adapter = _adapter(product, settings)
        params: dict[str, Any] = {"tenant_id": tenant_id, "limit": limit}
        if stage:
            params["stage"] = stage
        if assigned_to:
            params["assigned_to"] = assigned_to
        try:
            data = await adapter.get("/api/crm/deals", params=params)
            return ok(data)
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    @mcp.tool()
    async def crm_create_deal(
        tenant_id: str,
        product: str,
        title: str,
        contact_name: str,
        value: float = 0.0,
        stage: str = "lead",
        assigned_to: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new CRM deal."""
        adapter = _adapter(product, settings)
        try:
            data = await adapter.post("/api/crm/deals", {
                "tenant_id": tenant_id, "title": title, "contact_name": contact_name,
                "value": value, "stage": stage, "assigned_to": assigned_to,
                "metadata": metadata or {},
            })
            return ok(data)
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    @mcp.tool()
    async def crm_update_deal(
        tenant_id: str,
        product: str,
        deal_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Update a deal's fields."""
        adapter = _adapter(product, settings)
        try:
            data = await adapter.patch(f"/api/crm/deals/{deal_id}", {"tenant_id": tenant_id, **updates})
            return ok(data)
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    @mcp.tool()
    async def crm_move_deal_stage(
        tenant_id: str,
        product: str,
        deal_id: str,
        new_stage: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Move a deal to a new pipeline stage."""
        adapter = _adapter(product, settings)
        try:
            data = await adapter.post(f"/api/crm/deals/{deal_id}/move", {
                "tenant_id": tenant_id, "stage": new_stage, "note": note,
            })
            return ok(data)
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    @mcp.tool()
    async def crm_log_activity(
        tenant_id: str,
        product: str,
        deal_id: str,
        activity_type: str,
        note: str,
        performed_by: str | None = None,
    ) -> dict[str, Any]:
        """Log an activity (call, email, meeting) on a deal."""
        adapter = _adapter(product, settings)
        try:
            data = await adapter.post(f"/api/crm/deals/{deal_id}/activities", {
                "tenant_id": tenant_id, "type": activity_type,
                "note": note, "performed_by": performed_by,
            })
            return ok(data)
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    @mcp.tool()
    async def crm_contact_timeline(
        tenant_id: str,
        product: str,
        contact_id: str,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Get full activity timeline for a contact."""
        adapter = _adapter(product, settings)
        try:
            data = await adapter.get(f"/api/crm/contacts/{contact_id}/timeline",
                                      params={"tenant_id": tenant_id, "limit": limit})
            return ok(data)
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    # ── Tasks ────────────────────────────────────────────────

    @mcp.tool()
    async def tasks_create(
        tenant_id: str,
        product: str,
        title: str,
        assigned_to: str | None = None,
        project_id: str | None = None,
        due_date: str | None = None,
        priority: str = "medium",
    ) -> dict[str, Any]:
        """Create a new task."""
        adapter = _adapter(product, settings)
        try:
            data = await adapter.post("/api/tasks", {
                "tenant_id": tenant_id, "title": title,
                "assigned_to": assigned_to, "project_id": project_id,
                "due_date": due_date, "priority": priority,
            })
            return ok(data)
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    @mcp.tool()
    async def tasks_list(
        tenant_id: str,
        product: str,
        project_id: str | None = None,
        assigned_to: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List tasks with filters."""
        adapter = _adapter(product, settings)
        params: dict[str, Any] = {"tenant_id": tenant_id, "limit": limit}
        for k, v in [("project_id", project_id), ("assigned_to", assigned_to), ("status", status)]:
            if v:
                params[k] = v
        try:
            return ok(await adapter.get("/api/tasks", params=params))
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    @mcp.tool()
    async def tasks_update_status(
        tenant_id: str,
        product: str,
        task_id: str,
        status: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Update task status (todo/in_progress/done/blocked)."""
        adapter = _adapter(product, settings)
        try:
            data = await adapter.patch(f"/api/tasks/{task_id}", {"tenant_id": tenant_id, "status": status, "note": note})
            return ok(data)
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    @mcp.tool()
    async def tasks_my_today(
        tenant_id: str,
        product: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Get tasks assigned to a user due today."""
        adapter = _adapter(product, settings)
        try:
            data = await adapter.get("/api/tasks/my-today",
                                      params={"tenant_id": tenant_id, "user_id": user_id})
            return ok(data)
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    @mcp.tool()
    async def projects_create(
        tenant_id: str,
        product: str,
        name: str,
        description: str | None = None,
        owner_id: str | None = None,
        due_date: str | None = None,
    ) -> dict[str, Any]:
        """Create a new project."""
        adapter = _adapter(product, settings)
        try:
            data = await adapter.post("/api/projects", {
                "tenant_id": tenant_id, "name": name,
                "description": description, "owner_id": owner_id, "due_date": due_date,
            })
            return ok(data)
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    @mcp.tool()
    async def projects_summary(
        tenant_id: str,
        product: str,
        project_id: str,
    ) -> dict[str, Any]:
        """Get project summary: progress, tasks, team members."""
        adapter = _adapter(product, settings)
        try:
            return ok(await adapter.get(f"/api/projects/{project_id}/summary", params={"tenant_id": tenant_id}))
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    # ── Meetings ──────────────────────────────────────────────

    @mcp.tool()
    async def meetings_schedule(
        tenant_id: str,
        product: str,
        title: str,
        start_at: str,
        end_at: str,
        attendees: list[str],
        location: str | None = None,
        agenda: str | None = None,
    ) -> dict[str, Any]:
        """Schedule a meeting."""
        adapter = _adapter(product, settings)
        try:
            data = await adapter.post("/api/meetings", {
                "tenant_id": tenant_id, "title": title, "start_at": start_at,
                "end_at": end_at, "attendees": attendees,
                "location": location, "agenda": agenda,
            })
            return ok(data)
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    @mcp.tool()
    async def meetings_list_upcoming(
        tenant_id: str,
        product: str,
        user_id: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """List upcoming meetings."""
        adapter = _adapter(product, settings)
        params: dict[str, Any] = {"tenant_id": tenant_id, "limit": limit}
        if user_id:
            params["user_id"] = user_id
        try:
            return ok(await adapter.get("/api/meetings/upcoming", params=params))
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    @mcp.tool()
    async def meetings_cancel(
        tenant_id: str,
        product: str,
        meeting_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Cancel a scheduled meeting."""
        adapter = _adapter(product, settings)
        try:
            data = await adapter.patch(f"/api/meetings/{meeting_id}/cancel",
                                        {"tenant_id": tenant_id, "reason": reason})
            return ok(data)
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    @mcp.tool()
    async def meetings_attach_summary(
        tenant_id: str,
        product: str,
        meeting_id: str,
        summary: str,
        action_items: list[str] | None = None,
    ) -> dict[str, Any]:
        """Attach meeting summary and action items after it concludes."""
        adapter = _adapter(product, settings)
        try:
            data = await adapter.post(f"/api/meetings/{meeting_id}/summary", {
                "tenant_id": tenant_id, "summary": summary, "action_items": action_items or [],
            })
            return ok(data)
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    # ── Handovers ─────────────────────────────────────────────

    @mcp.tool()
    async def handover_create(
        tenant_id: str,
        product: str,
        title: str,
        from_employee_id: str,
        to_employee_id: str,
        due_date: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Create a new handover package."""
        adapter = _adapter(product, settings)
        try:
            data = await adapter.post("/api/handovers", {
                "tenant_id": tenant_id, "title": title,
                "from_employee_id": from_employee_id,
                "to_employee_id": to_employee_id,
                "due_date": due_date, "notes": notes,
            })
            return ok(data)
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    @mcp.tool()
    async def handover_add_item(
        tenant_id: str,
        product: str,
        handover_id: str,
        category: str,
        title: str,
        description: str,
        priority: str = "medium",
        attachments: list[str] | None = None,
    ) -> dict[str, Any]:
        """Add an item to an existing handover."""
        adapter = _adapter(product, settings)
        try:
            data = await adapter.post(f"/api/handovers/{handover_id}/items", {
                "tenant_id": tenant_id, "category": category, "title": title,
                "description": description, "priority": priority,
                "attachments": attachments or [],
            })
            return ok(data)
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    @mcp.tool()
    async def handover_submit(
        tenant_id: str,
        product: str,
        handover_id: str,
        submitted_by: str,
    ) -> dict[str, Any]:
        """Submit a handover for review."""
        adapter = _adapter(product, settings)
        try:
            data = await adapter.post(f"/api/handovers/{handover_id}/submit",
                                       {"tenant_id": tenant_id, "submitted_by": submitted_by})
            return ok(data)
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    @mcp.tool()
    async def handover_review(
        tenant_id: str,
        product: str,
        handover_id: str,
        reviewer_id: str,
        decision: str,
        comments: str | None = None,
    ) -> dict[str, Any]:
        """Approve or reject a handover (decision: approved/rejected)."""
        if decision not in ("approved", "rejected"):
            return err("INVALID_DECISION", "decision must be approved or rejected")
        adapter = _adapter(product, settings)
        try:
            data = await adapter.post(f"/api/handovers/{handover_id}/review", {
                "tenant_id": tenant_id, "reviewer_id": reviewer_id,
                "decision": decision, "comments": comments,
            })
            return ok(data)
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    @mcp.tool()
    async def handover_get(
        tenant_id: str,
        product: str,
        handover_id: str,
    ) -> dict[str, Any]:
        """Get handover details including items and status."""
        adapter = _adapter(product, settings)
        try:
            return ok(await adapter.get(f"/api/handovers/{handover_id}", params={"tenant_id": tenant_id}))
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    @mcp.tool()
    async def handover_list(
        tenant_id: str,
        product: str,
        employee_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """List handovers for a tenant."""
        adapter = _adapter(product, settings)
        params: dict[str, Any] = {"tenant_id": tenant_id, "limit": limit}
        if employee_id:
            params["employee_id"] = employee_id
        if status:
            params["status"] = status
        try:
            return ok(await adapter.get("/api/handovers", params=params))
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    # ── Team ─────────────────────────────────────────────────

    @mcp.tool()
    async def team_list_members(
        tenant_id: str,
        product: str,
        department: str | None = None,
    ) -> dict[str, Any]:
        """List team members for a tenant."""
        adapter = _adapter(product, settings)
        params: dict[str, Any] = {"tenant_id": tenant_id}
        if department:
            params["department"] = department
        try:
            return ok(await adapter.get("/api/team/members", params=params))
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    @mcp.tool()
    async def team_workload(
        tenant_id: str,
        product: str,
        user_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get workload summary per team member."""
        adapter = _adapter(product, settings)
        try:
            params: dict[str, Any] = {"tenant_id": tenant_id}
            if user_ids:
                params["user_ids"] = ",".join(user_ids)
            return ok(await adapter.get("/api/team/workload", params=params))
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    # ── Unified Search ───────────────────────────────────────

    @mcp.tool()
    async def workspace_search(
        tenant_id: str,
        product: str,
        query: str,
        entity_types: list[str] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Unified search across all workspace entities (deals, tasks, meetings, handovers)."""
        adapter = _adapter(product, settings)
        try:
            params: dict[str, Any] = {"tenant_id": tenant_id, "q": query, "limit": limit}
            if entity_types:
                params["types"] = ",".join(entity_types)
            return ok(await adapter.get("/api/search", params=params))
        except Exception as e:
            return err("BACKEND_ERROR", str(e))

    return mcp
