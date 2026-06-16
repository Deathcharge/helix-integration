from apps.backend.helix_proprietary.integrations import HelixNetClientSession

"""
Zapier Agent Executor
Executes agent tasks through Zapier workflows with coordination-level routing
"""

import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, ClassVar

import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PerformanceScore(Enum):
    """Coordination levels for agent routing (1-10)"""

    MINIMAL = 1
    BASIC = 2
    AWARE = 3
    RESPONSIVE = 4
    ADAPTIVE = 5
    INTELLIGENT = 6
    STRATEGIC = 7
    AUTONOMOUS = 8
    PEAK = 9
    OMNISCIENT = 10


@dataclass
class AgentTask:
    """Represents a task to be executed by an agent"""

    id: str
    agent_id: str
    task_type: str
    performance_score: int
    payload: dict[str, Any]
    priority: int = 5  # 1-10, higher = more urgent
    timeout_seconds: int = 30
    retry_count: int = 0
    max_retries: int = 3
    created_at: str | None = None

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(UTC).isoformat()


@dataclass
class AgentResult:
    """Result from agent execution"""

    task_id: str
    agent_id: str
    status: str  # success, failed, timeout, error
    result: dict[str, Any]
    error: str | None = None
    execution_time_ms: int = 0
    timestamp: str | None = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()


class ZapierAgentExecutor:
    """Execute agent tasks through Zapier workflows"""

    # Agent capabilities by coordination level
    AGENT_CAPABILITIES: ClassVar[dict] = {
        1: ["basic_query", "simple_lookup"],
        2: ["data_retrieval", "pattern_matching"],
        3: ["analysis", "comparison"],
        4: ["decision_making", "routing"],
        5: ["optimization", "learning"],
        6: ["strategy_planning", "coordination"],
        7: ["autonomous_execution", "adaptation"],
        8: ["self_improvement", "innovation"],
        9: ["cross_domain_synthesis", "prediction"],
        10: ["omniscient_analysis", "universal_coordination"],
    }

    # Agent roster (24 agents)
    AGENT_ROSTER: ClassVar[dict] = {
        "research-agent": {
            "name": "Research Agent",
            "capabilities": ["data_retrieval", "analysis", "pattern_matching"],
            "performance_score": 6,
            "specialization": "Information gathering and analysis",
        },
        "analysis-agent": {
            "name": "Analysis Agent",
            "capabilities": ["analysis", "comparison", "optimization"],
            "performance_score": 6,
            "specialization": "Data analysis and insights",
        },
        "synthesis-agent": {
            "name": "Synthesis Agent",
            "capabilities": ["strategy_planning", "coordination", "optimization"],
            "performance_score": 7,
            "specialization": "Combining insights into actionable plans",
        },
        "validation-agent": {
            "name": "Validation Agent",
            "capabilities": ["pattern_matching", "decision_making", "analysis"],
            "performance_score": 5,
            "specialization": "Quality assurance and validation",
        },
        "orchestration-agent": {
            "name": "Orchestration Agent",
            "capabilities": ["coordination", "routing", "autonomous_execution"],
            "performance_score": 7,
            "specialization": "Coordinating multi-agent workflows",
        },
        "monitoring-agent": {
            "name": "Monitoring Agent",
            "capabilities": ["data_retrieval", "pattern_matching", "decision_making"],
            "performance_score": 5,
            "specialization": "System health monitoring",
        },
        "escalation-agent": {
            "name": "Escalation Agent",
            "capabilities": ["decision_making", "routing", "strategy_planning"],
            "performance_score": 6,
            "specialization": "Issue escalation and prioritization",
        },
        "documentation-agent": {
            "name": "Documentation Agent",
            "capabilities": ["data_retrieval", "analysis", "optimization"],
            "performance_score": 4,
            "specialization": "Documentation generation and maintenance",
        },
        "optimization-agent": {
            "name": "Optimization Agent",
            "capabilities": ["optimization", "learning", "strategy_planning"],
            "performance_score": 7,
            "specialization": "Performance optimization",
        },
        "integration-agent": {
            "name": "Integration Agent",
            "capabilities": ["coordination", "routing", "autonomous_execution"],
            "performance_score": 6,
            "specialization": "External system integration",
        },
        "security-agent": {
            "name": "Security Agent",
            "capabilities": ["pattern_matching", "decision_making", "analysis"],
            "performance_score": 7,
            "specialization": "Security monitoring and threat detection",
        },
        "performance-agent": {
            "name": "Performance Agent",
            "capabilities": ["analysis", "optimization", "learning"],
            "performance_score": 6,
            "specialization": "Performance metrics and optimization",
        },
        "learning-agent": {
            "name": "Learning Agent",
            "capabilities": ["learning", "optimization", "self_improvement"],
            "performance_score": 8,
            "specialization": "Continuous learning and adaptation",
        },
        "coordination-agent": {
            "name": "Coordination Agent",
            "capabilities": ["coordination", "routing", "strategy_planning"],
            "performance_score": 7,
            "specialization": "Cross-instance coordination",
        },
    }

    def __init__(self, zapier_webhook_url: str, instance_id: str, performance_score: int = 5):
        """Initialize executor"""
        self.zapier_webhook_url = zapier_webhook_url
        self.instance_id = instance_id
        self.performance_score = performance_score
        self.session: aiohttp.ClientSession | None = None
        self.task_history: list[dict[str, Any]] = []
        self.result_callbacks: dict[str, list[Callable]] = {}

    async def __aenter__(self):
        """
        Enter the context by initializing and storing a HelixNetClientSession and return the executor instance.

        Returns:
            The executor instance with an initialized HelixNetClientSession.
        """
        self.session = HelixNetClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Close the internal HTTP session when exiting the asynchronous context manager.

        If a HelixNetClientSession is active, awaits its close method to release network resources.
        """
        if self.session:
            await self.session.close()

    def get_agent_info(self, agent_id: str) -> dict[str, Any] | None:
        """Get information about an agent"""
        return self.AGENT_ROSTER.get(agent_id)

    def list_agents(self) -> list[dict[str, Any]]:
        """List all available agents"""
        return list(self.AGENT_ROSTER.values())

    def get_agent_capabilities(self, agent_id: str) -> list[str]:
        """Get capabilities of an agent"""
        agent = self.get_agent_info(agent_id)
        if agent:
            return agent.get("capabilities", [])
        return []

    def can_execute_task(self, agent_id: str, task_type: str) -> bool:
        """Check if agent can execute task type"""
        capabilities = self.get_agent_capabilities(agent_id)
        return task_type in capabilities

    def route_task(self, task: AgentTask) -> str:
        """Route task to appropriate agent based on coordination level"""

        # Filter agents by coordination level
        suitable_agents = [
            agent_id
            for agent_id, info in self.AGENT_ROSTER.items()
            if info["performance_score"] >= task.performance_score
        ]

        if not suitable_agents:
            logger.warning("No agents suitable for coordination level %s", task.performance_score)
            return None

        # Filter by capability
        capable_agents = [agent_id for agent_id in suitable_agents if self.can_execute_task(agent_id, task.task_type)]

        if not capable_agents:
            logger.warning("No agents capable of task type %s", task.task_type)
            return suitable_agents[0]  # Return highest coordination agent as fallback

        # Return first capable agent (could implement load balancing here)
        return capable_agents[0]

    async def execute_task(self, task: AgentTask, agent_id: str | None = None) -> AgentResult:
        """
        Execute the given AgentTask by sending it to the configured Zapier webhook and return the execution result.

        Parameters:
            task (AgentTask): The task to execute. Its `agent_id` may be set by this method if routing is performed.
            agent_id (Optional[str]): Optional explicit agent identifier to use; if omitted the executor will route the task to a suitable agent.

        Returns:
            AgentResult: Result of the task execution. The result `status` will be one of `"success"`, `"failed"`, `"timeout"`, or `"error"`. On success `result` contains the parsed response from the webhook and `execution_time_ms` is set; on failure or error `error` contains a descriptive message.
        """

        if not agent_id:
            agent_id = self.route_task(task)

        if not agent_id:
            return AgentResult(
                task_id=task.id,
                agent_id="unknown",
                status="error",
                result={},
                error="No suitable agent found for task",
            )

        task.agent_id = agent_id

        # Prepare payload for Zapier
        zapier_payload = {
            "instance_id": self.instance_id,
            "task": asdict(task),
            "agent_id": agent_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "request_id": str(uuid.uuid4()),
        }

        logger.info("Executing task %s with agent %s", task.id, agent_id)

        try:
            start_time = datetime.now(UTC)

            # Send to Zapier webhook
            if not self.session:
                self.session = HelixNetClientSession()

            async with self.session.post(
                self.zapier_webhook_url,
                json=zapier_payload,
                timeout=aiohttp.ClientTimeout(total=task.timeout_seconds),
            ) as response:
                execution_time_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)

                if response.status == 200:
                    result_data = await response.json()

                    result = AgentResult(
                        task_id=task.id,
                        agent_id=agent_id,
                        status="success",
                        result=result_data,
                        execution_time_ms=execution_time_ms,
                    )

                    logger.info("Task %s completed successfully in %sms", task.id, execution_time_ms)
                    self._record_task_history(task, result)
                    await self._trigger_callbacks(task.id, result)

                    return result
                else:
                    error_text = await response.text()

                    result = AgentResult(
                        task_id=task.id,
                        agent_id=agent_id,
                        status="failed",
                        result={},
                        error=f"Zapier returned {response.status}: {error_text}",
                        execution_time_ms=execution_time_ms,
                    )

                    logger.error("Task %s failed: %s", task.id, error_text)
                    self._record_task_history(task, result)

                    return result

        except TimeoutError:
            result = AgentResult(
                task_id=task.id,
                agent_id=agent_id,
                status="timeout",
                result={},
                error=f"Task timeout after {task.timeout_seconds}s",
            )

            logger.error("Task %s timed out", task.id)
            self._record_task_history(task, result)

            return result

        except Exception as e:
            result = AgentResult(
                task_id=task.id,
                agent_id=agent_id,
                status="error",
                result={},
                error=str(e),
            )

            logger.error("Task %s error: %s", task.id, e)
            self._record_task_history(task, result)

            return result

    async def execute_tasks_parallel(self, tasks: list[AgentTask]) -> list[AgentResult]:
        """Execute multiple tasks in parallel"""
        results = await asyncio.gather(*[self.execute_task(task) for task in tasks])
        return results

    async def execute_workflow(self, workflow_name: str, workflow_config: dict[str, Any]) -> dict[str, Any]:
        """Execute a multi-agent workflow"""

        logger.info("Executing workflow: %s", workflow_name)

        workflow_result = {
            "workflow_name": workflow_name,
            "instance_id": self.instance_id,
            "started_at": datetime.now(UTC).isoformat(),
            "tasks": [],
            "status": "running",
        }

        # Parse workflow tasks
        tasks = []
        for task_config in workflow_config.get("tasks", []):
            task = AgentTask(
                id=task_config.get("id", str(uuid.uuid4())),
                agent_id=task_config.get("agent_id", ""),
                task_type=task_config.get("task_type"),
                performance_score=task_config.get("performance_score", self.performance_score),
                payload=task_config.get("payload", {}),
                priority=task_config.get("priority", 5),
            )
            tasks.append(task)

        # Execute tasks
        results = await self.execute_tasks_parallel(tasks)

        workflow_result["tasks"] = [asdict(r) for r in results]
        workflow_result["completed_at"] = datetime.now(UTC).isoformat()
        workflow_result["status"] = "completed" if all(r.status == "success" for r in results) else "partial"

        logger.info("Workflow {} completed with status {}".format(workflow_name, workflow_result["status"]))

        return workflow_result

    def register_callback(self, task_id: str, callback: Callable):
        """Register callback for task completion"""
        if task_id not in self.result_callbacks:
            self.result_callbacks[task_id] = []
        self.result_callbacks[task_id].append(callback)

    async def _trigger_callbacks(self, task_id: str, result: AgentResult):
        """Trigger registered callbacks"""
        callbacks = self.result_callbacks.get(task_id, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(result)
                else:
                    callback(result)
            except Exception as e:
                logger.error("Callback error for task %s: %s", task_id, e)

    def _record_task_history(self, task: AgentTask, result: AgentResult):
        """Record task execution in history"""
        self.task_history.append(
            {
                "task": asdict(task),
                "result": asdict(result),
                "recorded_at": datetime.now(UTC).isoformat(),
            }
        )

    def get_task_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent task history"""
        return self.task_history[-limit:]

    def get_statistics(self) -> dict[str, Any]:
        """Get execution statistics"""
        if not self.task_history:
            return {
                "total_tasks": 0,
                "successful": 0,
                "failed": 0,
                "average_execution_time_ms": 0,
            }

        successful = sum(1 for h in self.task_history if h["result"]["status"] == "success")
        failed = sum(1 for h in self.task_history if h["result"]["status"] != "success")
        avg_time = sum(h["result"]["execution_time_ms"] for h in self.task_history) / len(self.task_history)

        return {
            "total_tasks": len(self.task_history),
            "successful": successful,
            "failed": failed,
            "success_rate": successful / len(self.task_history) * 100,
            "average_execution_time_ms": avg_time,
        }


# Example usage and testing
async def main():
    """Example usage"""

    executor = ZapierAgentExecutor(
        zapier_webhook_url="https://hooks.zapier.com/hooks/catch/YOUR_ID",
        instance_id="helix-primary",
        performance_score=8,
    )

    # List available agents
    logger.info("Available Agents:")
    for agent in executor.list_agents():
        logger.info("  - {} (Level {})".format(agent["name"], agent["performance_score"]))

    # Create a task
    task = AgentTask(
        id="task-001",
        agent_id="",
        task_type="analysis",
        performance_score=5,
        payload={"data": "sample data for analysis"},
    )

    # Route task
    routed_agent = executor.route_task(task)
    logger.info("\nTask routed to: %s", routed_agent)

    # Execute task (requires valid Zapier webhook)
    # result = await executor.execute_task(task)
    # print("Result: {}".format(result))


if __name__ == "__main__":
    asyncio.run(main())
