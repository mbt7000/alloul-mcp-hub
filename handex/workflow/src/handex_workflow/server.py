from __future__ import annotations
import json
from datetime import datetime, timedelta
from typing import Any
import structlog
from fastmcp import FastMCP

from handex_workflow.settings import Settings
from handex_workflow.engine import StateMachineEngine
from shared.db import init_pool, get_pool
from shared.envelope import ok, err

log = structlog.get_logger()


def create_server(settings: Settings) -> FastMCP:
    mcp = FastMCP("handex.workflow", version="0.1.0")


    @mcp.tool()
    async def workflow_define(
        tenant_id: str,
        name: str,
        definition: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Define a workflow state machine for a tenant.
        definition: {states, initial, transitions, terminal_states, sla_hours}
        """
        required = {"states", "initial", "transitions"}
        if not required.issubset(definition.keys()):
            return err("INVALID_DEFINITION", f"Missing required keys: {required - set(definition.keys())}")
        if definition["initial"] not in definition["states"]:
            return err("INVALID_DEFINITION", "initial state not in states list")

        pool = await get_pool()
        row = await pool.fetchrow(
            """
            INSERT INTO handex.workflow_definitions (tenant_id, name, definition)
            VALUES ($1,$2,$3)
            ON CONFLICT (tenant_id, name) DO UPDATE SET definition=EXCLUDED.definition, version=handex.workflow_definitions.version+1
            RETURNING id, name, version, created_at
            """,
            tenant_id, name, json.dumps(definition),
        )
        return ok(dict(row))

    @mcp.tool()
    async def workflow_start(
        tenant_id: str,
        workflow_name: str,
        started_by: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Start a new workflow instance."""
        pool = await get_pool()
        defn_row = await pool.fetchrow(
            "SELECT id, definition FROM handex.workflow_definitions WHERE tenant_id=$1 AND name=$2",
            tenant_id, workflow_name,
        )
        if not defn_row:
            return err("NOT_FOUND", f"Workflow '{workflow_name}' not found")

        definition = json.loads(defn_row["definition"])
        engine = StateMachineEngine(definition)
        initial = engine.initial_state()

        instance = await pool.fetchrow(
            """
            INSERT INTO handex.workflow_instances (tenant_id, definition_id, current_state, context, started_by, status)
            VALUES ($1,$2,$3,$4,$5,'active')
            RETURNING id, current_state, status, created_at
            """,
            tenant_id, str(defn_row["id"]),
            initial, json.dumps(context or {}), started_by,
        )

        # Create initial task if sla defined
        sla_hours = definition.get("sla_hours", {}).get(initial)
        if sla_hours:
            due = datetime.utcnow() + timedelta(hours=sla_hours)
            await pool.execute(
                """
                INSERT INTO handex.workflow_tasks (instance_id, tenant_id, title, due_at, status)
                VALUES ($1,$2,$3,$4,'pending')
                """,
                str(instance["id"]), tenant_id,
                f"Complete: {initial}", due,
            )

        return ok({
            "instance_id": str(instance["id"]),
            "workflow": workflow_name,
            "current_state": initial,
            "available_triggers": engine.available_triggers(initial),
        })

    @mcp.tool()
    async def workflow_list_tasks_for_user(
        tenant_id: str,
        user_id: str,
        status: str = "pending",
    ) -> dict[str, Any]:
        """List workflow tasks assigned to a user."""
        pool = await get_pool()
        rows = await pool.fetch(
            """
            SELECT wt.id, wt.title, wt.due_at, wt.status, wt.created_at,
                   wi.current_state, wi.id AS instance_id
            FROM handex.workflow_tasks wt
            JOIN handex.workflow_instances wi ON wi.id = wt.instance_id
            WHERE wt.tenant_id=$1 AND wt.assignee_id=$2 AND wt.status=$3
            ORDER BY wt.due_at ASC NULLS LAST
            """,
            tenant_id, user_id, status,
        )
        return ok({"tasks": [dict(r) for r in rows], "count": len(rows)})

    @mcp.tool()
    async def workflow_complete_task(
        tenant_id: str,
        instance_id: str,
        trigger: str,
        completed_by: str,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Advance a workflow instance by firing a trigger (completing a task)."""
        pool = await get_pool()
        instance = await pool.fetchrow(
            """
            SELECT wi.id, wi.current_state, wi.definition_id
            FROM handex.workflow_instances wi
            WHERE wi.id=$1 AND wi.tenant_id=$2 AND wi.status='active'
            """,
            instance_id, tenant_id,
        )
        if not instance:
            return err("NOT_FOUND", "Active workflow instance not found")

        defn_row = await pool.fetchrow(
            "SELECT definition FROM handex.workflow_definitions WHERE id=$1",
            str(instance["definition_id"]),
        )
        engine = StateMachineEngine(json.loads(defn_row["definition"]))
        current = instance["current_state"]
        next_state = engine.next_state(current, trigger)

        if not next_state:
            return err("INVALID_TRIGGER", f"Trigger '{trigger}' not valid in state '{current}'. Available: {engine.available_triggers(current)}")

        await pool.execute(
            "UPDATE handex.workflow_instances SET current_state=$1, updated_at=now(), status=$2 WHERE id=$3",
            next_state,
            "completed" if engine.is_terminal(next_state) else "active",
            instance_id,
        )
        await pool.execute(
            "UPDATE handex.workflow_tasks SET status='completed', completed_at=now() WHERE instance_id=$1 AND status='pending'",
            instance_id,
        )

        # Create next task if not terminal
        if not engine.is_terminal(next_state):
            definition_data = json.loads(defn_row["definition"])
            sla_hours = definition_data.get("sla_hours", {}).get(next_state)
            due = datetime.utcnow() + timedelta(hours=sla_hours) if sla_hours else None
            await pool.execute(
                "INSERT INTO handex.workflow_tasks (instance_id, tenant_id, title, due_at, status) VALUES ($1,$2,$3,$4,'pending')",
                instance_id, tenant_id, f"Complete: {next_state}", due,
            )

        return ok({
            "instance_id": instance_id,
            "previous_state": current,
            "current_state": next_state,
            "is_complete": engine.is_terminal(next_state),
            "available_triggers": engine.available_triggers(next_state) if not engine.is_terminal(next_state) else [],
        })

    @mcp.tool()
    async def workflow_cancel(
        tenant_id: str,
        instance_id: str,
        cancelled_by: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Cancel an active workflow instance."""
        pool = await get_pool()
        row = await pool.fetchrow(
            "UPDATE handex.workflow_instances SET status='cancelled', updated_at=now() WHERE id=$1 AND tenant_id=$2 AND status='active' RETURNING id",
            instance_id, tenant_id,
        )
        if not row:
            return err("NOT_FOUND", "Active instance not found")
        await pool.execute(
            "UPDATE handex.workflow_tasks SET status='cancelled' WHERE instance_id=$1 AND status='pending'",
            instance_id,
        )
        log.info("workflow_cancelled", instance_id=instance_id, by=cancelled_by, reason=reason)
        return ok({"cancelled": True, "instance_id": instance_id})

    @mcp.tool()
    async def workflow_get_instance(
        tenant_id: str,
        instance_id: str,
    ) -> dict[str, Any]:
        """Get workflow instance state, history, and pending tasks."""
        pool = await get_pool()
        instance = await pool.fetchrow(
            """
            SELECT wi.id, wi.current_state, wi.status, wi.context, wi.started_by, wi.created_at, wi.updated_at,
                   wd.name AS workflow_name
            FROM handex.workflow_instances wi
            JOIN handex.workflow_definitions wd ON wd.id=wi.definition_id
            WHERE wi.id=$1 AND wi.tenant_id=$2
            """,
            instance_id, tenant_id,
        )
        if not instance:
            return err("NOT_FOUND", "Instance not found")

        tasks = await pool.fetch(
            "SELECT id, title, assignee_id, due_at, status, completed_at FROM handex.workflow_tasks WHERE instance_id=$1 ORDER BY created_at",
            instance_id,
        )

        data = dict(instance)
        data["context"] = json.loads(data["context"])
        data["tasks"] = [dict(t) for t in tasks]
        return ok(data)

    @mcp.tool()
    async def workflow_set_escalation_rule(
        tenant_id: str,
        workflow_name: str,
        state: str,
        escalate_after_hours: int,
        escalate_to_user_id: str,
        notification_message: str | None = None,
    ) -> dict[str, Any]:
        """Set escalation rule: if a workflow stays in a state too long, escalate."""
        pool = await get_pool()
        defn = await pool.fetchrow(
            "SELECT id, definition FROM handex.workflow_definitions WHERE tenant_id=$1 AND name=$2",
            tenant_id, workflow_name,
        )
        if not defn:
            return err("NOT_FOUND", f"Workflow '{workflow_name}' not found")

        definition = json.loads(defn["definition"])
        if state not in definition["states"]:
            return err("INVALID_STATE", f"State '{state}' not in workflow states")

        # Store escalation rule in the SLA hours section
        definition.setdefault("escalation_rules", {})[state] = {
            "after_hours": escalate_after_hours,
            "escalate_to": escalate_to_user_id,
            "message": notification_message,
        }
        await pool.execute(
            "UPDATE handex.workflow_definitions SET definition=$1 WHERE id=$2",
            json.dumps(definition), str(defn["id"]),
        )
        return ok({
            "workflow": workflow_name,
            "state": state,
            "escalate_after_hours": escalate_after_hours,
            "escalate_to": escalate_to_user_id,
        })

    return mcp
