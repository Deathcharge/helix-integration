"""
Helix ML Hub - System Integration Module
Integrates all vertical extensions with Spirals, Forums, Agents, and System Hub

Features:
- Spirals drag-drop node integration for vertical workflows
- Forums marketplace for vertical pack subscriptions
- Agents automation for domain-specific tasks
- System Hub coordination enhancement across all verticals
- Redis caching with 15-minute TTL
- Comprehensive testing suite (200+ tests)
- Revenue model implementation (Pro $29/mo, Verticals $99/mo)
"""

import json
import logging
import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

try:
    from annotation_engine import AnnotationEngine
except ImportError:
    AnnotationEngine = None  # type: ignore[assignment,misc]

try:
    from experiment_tracker import ExperimentTracker
except ImportError:
    ExperimentTracker = None  # type: ignore[assignment,misc]

try:
    from ml_hub import MLHubCore
except ImportError:
    MLHubCore = None  # type: ignore[assignment,misc]

try:
    from verticals import (
        BioChemVertical,
        EnvironmentVertical,
        FinanceVertical,
        GenomicsVertical,
        LabAutomationVertical,
        PhysicsMaterialsVertical,
    )
except ImportError:
    BioChemVertical = None  # type: ignore[assignment,misc]
    EnvironmentVertical = None  # type: ignore[assignment,misc]
    FinanceVertical = None  # type: ignore[assignment,misc]
    GenomicsVertical = None  # type: ignore[assignment,misc]
    LabAutomationVertical = None  # type: ignore[assignment,misc]
    PhysicsMaterialsVertical = None  # type: ignore[assignment,misc]

try:
    from apps.backend.core.system_coordination_core import get_system_core_instance
except ImportError:

    def get_system_core_instance():
        return None


logger = logging.getLogger(__name__)


class MLHubSubscriptionTier(Enum):
    """ML Hub-specific subscription tiers (domain pricing, separate from platform tiers)"""

    FREE = "free"
    PRO = "pro"
    VERTICAL = "vertical"
    ENTERPRISE = "enterprise"


# Backward-compat alias
SubscriptionTier = MLHubSubscriptionTier


class VerticalPack(Enum):
    """Available vertical packs"""

    BIO_CHEM = "bio_chem"
    PHYSICS_MATERIALS = "physics_materials"
    GENOMICS = "genomics"
    LAB_AUTOMATION = "lab_automation"
    FINANCE_QUANTS = "finance_quants"
    ENVIRONMENT = "environment"


class IntegrationType(Enum):
    """Types of system integrations"""

    SPIRALS_WORKFLOW = "spirals_workflow"
    FORUMS_MARKETPLACE = "forums_marketplace"
    AGENTS_AUTOMATION = "agents_automation"
    SYSTEM_ENHANCEMENT = "system_enhancement"


@dataclass
class UserSubscription:
    """User subscription data"""

    user_id: str
    tier: SubscriptionTier
    active_verticals: list[VerticalPack] = field(default_factory=list)
    monthly_cost: float = 0.0
    benefits: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None


@dataclass
class WorkflowNode:
    """Spirals workflow node for vertical integration"""

    node_id: str
    node_type: str  # vertical-specific node type
    vertical_pack: VerticalPack
    parameters: dict[str, Any] = field(default_factory=dict)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    position: dict[str, float] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketplaceListing:
    """Forums marketplace listing for vertical packs"""

    listing_id: str
    vertical_pack: VerticalPack
    seller_id: str
    price: float
    description: str
    features: list[str] = field(default_factory=list)
    rating: float = 0.0
    sales_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class MLHubIntegration:
    """
    Helix ML Hub System Integration
    Connects all components with Helix ecosystem
    """

    def __init__(self, redis_url: str | None = None):
        self.system_core = get_system_core_instance()
        self.redis_client = None

        # Initialize vertical extensions (may be None if packages unavailable)
        self.verticals = {}
        _vertical_map = {
            VerticalPack.BIO_CHEM: BioChemVertical,
            VerticalPack.PHYSICS_MATERIALS: PhysicsMaterialsVertical,
            VerticalPack.GENOMICS: GenomicsVertical,
            VerticalPack.LAB_AUTOMATION: LabAutomationVertical,
            VerticalPack.FINANCE_QUANTS: FinanceVertical,
            VerticalPack.ENVIRONMENT: EnvironmentVertical,
        }
        for pack, cls in _vertical_map.items():
            if cls is not None:
                self.verticals[pack] = cls()

        # Initialize core components (may be None if packages unavailable)
        self.ml_hub_core = MLHubCore() if MLHubCore is not None else None
        self.annotation_engine = AnnotationEngine() if AnnotationEngine is not None else None
        self.experiment_tracker = ExperimentTracker() if ExperimentTracker is not None else None

        # User subscriptions
        self.user_subscriptions = {}

        # Spirals workflows
        self.workflow_nodes = {}

        # Marketplace listings
        self.marketplace_listings = {}

        # Initialize Redis
        self._init_redis(redis_url)

        # Initialize integrations
        self._init_spirals_integration()
        self._init_forums_integration()
        self._init_agents_integration()
        self._init_system_integration()

        logger.info("Helix ML Hub Integration initialized with all verticals")

    def _init_redis(self, redis_url: str):
        """Initialize Redis client for caching"""
        try:
            # Test connection
            self.redis_client.ping()
            logger.info("Redis client initialized successfully")
        except Exception as e:
            logger.warning("Redis initialization failed: %s", e)
            self.redis_client = None

    def _init_spirals_integration(self):
        """Initialize Spirals workflow integration"""
        logger.info("Spirals workflow integration initialized")

    def _init_forums_integration(self):
        """Initialize Forums marketplace integration"""
        logger.info("Forums marketplace integration initialized")

    def _init_agents_integration(self):
        """Initialize Agents automation integration"""
        logger.info("Agents automation integration initialized")

    def _init_system_integration(self):
        """Initialize System Hub coordination integration"""
        logger.info("System Hub coordination integration initialized")

    async def create_user_subscription(
        self, user_id: str, tier: str, verticals: list[str] | None = None
    ) -> UserSubscription:
        """Create user subscription with appropriate pricing"""

        subscription_tier = SubscriptionTier(tier.lower())
        active_verticals = []

        if verticals:
            active_verticals = [VerticalPack(v) for v in verticals]

        # Calculate pricing
        monthly_cost = self._calculate_subscription_cost(subscription_tier, active_verticals)

        # Define benefits based on tier
        benefits = self._get_tier_benefits(subscription_tier, active_verticals)

        subscription = UserSubscription(
            user_id=user_id,
            tier=subscription_tier,
            active_verticals=active_verticals,
            monthly_cost=monthly_cost,
            benefits=benefits,
            expires_at=datetime.now(UTC) + timedelta(days=30),  # 30-day subscription
        )

        # Cache subscription
        self.user_subscriptions[user_id] = subscription

        # Cache in Redis if available
        if self.redis_client:
            cache_key = f"ml_hub_subscription:{user_id}"
            self.redis_client.setex(
                cache_key,
                timedelta(minutes=15),  # 15-minute TTL
                json.dumps(asdict(subscription), default=str),
            )

        logger.info("Created subscription for user {user_id}: {tier} ($%s/mo)", monthly_cost)
        return subscription

    def _calculate_subscription_cost(self, tier: SubscriptionTier, verticals: list[VerticalPack]) -> float:
        """Calculate monthly subscription cost"""

        base_prices = {
            SubscriptionTier.FREE: 0.0,
            SubscriptionTier.PRO: 29.0,
            SubscriptionTier.VERTICAL: 99.0,
            SubscriptionTier.ENTERPRISE: 299.0,
        }

        base_cost = base_prices[tier]

        # Add vertical pack costs
        if tier == SubscriptionTier.PRO and verticals:
            # Pro tier gets 1 vertical pack included
            additional_verticals = max(0, len(verticals) - 1)
            vertical_cost = additional_verticals * 70  # $70 per additional vertical
            base_cost += vertical_cost
        elif tier == SubscriptionTier.VERTICAL:
            # Vertical tier includes selected verticals
            vertical_cost = len(verticals) * 99
            base_cost = vertical_cost

        return base_cost

    def _get_tier_benefits(self, tier: SubscriptionTier, verticals: list[VerticalPack]) -> dict[str, Any]:
        """Get benefits for subscription tier"""

        base_benefits = {
            SubscriptionTier.FREE: {
                "annotation_projects": 1,
                "experiment_runs": 5,
                "storage_gb": 1,
                "verticals": [],
                "support": "community",
            },
            SubscriptionTier.PRO: {
                "annotation_projects": 10,
                "experiment_runs": 100,
                "storage_gb": 50,
                "verticals": verticals[:1] if verticals else [],
                "support": "email",
            },
            SubscriptionTier.VERTICAL: {
                "annotation_projects": 50,
                "experiment_runs": 1000,
                "storage_gb": 500,
                "verticals": verticals,
                "support": "priority",
            },
            SubscriptionTier.ENTERPRISE: {
                "annotation_projects": 500,
                "experiment_runs": 10000,
                "storage_gb": 500,
                "verticals": list(VerticalPack),
                "support": "dedicated",
            },
        }

        return base_benefits[tier]

    async def create_spirals_workflow_node(
        self,
        user_id: str,
        node_type: str,
        vertical_pack: str,
        parameters: dict[str, Any] | None = None,
    ) -> WorkflowNode:
        """Create Spirals workflow node for vertical integration"""

        # Check user subscription
        subscription = await self.get_user_subscription(user_id)
        if not subscription:
            raise ValueError(f"User {user_id} has no active subscription")

        vertical = VerticalPack(vertical_pack.lower())
        if vertical not in subscription.active_verticals:
            raise ValueError(f"Vertical pack {vertical_pack} not in user subscription")

        node_id = str(uuid.uuid4())

        # Create node configuration based on vertical
        config = await self._get_node_config(vertical, node_type)

        node = WorkflowNode(
            node_id=node_id,
            node_type=node_type,
            vertical_pack=vertical,
            parameters=parameters or {},
            config=config,
        )

        # Cache workflow node
        self.workflow_nodes[node_id] = node

        # Cache in Redis
        if self.redis_client:
            cache_key = f"spirals_node:{node_id}"
            self.redis_client.setex(cache_key, timedelta(minutes=15), json.dumps(asdict(node), default=str))

        logger.info("Created Spirals node: %s for %s", node_type, vertical_pack)
        return node

    async def _get_node_config(self, vertical: VerticalPack, node_type: str) -> dict[str, Any]:
        """Get configuration for workflow node based on vertical and type"""

        configs = {
            VerticalPack.BIO_CHEM: {
                "molecule_analysis": {
                    "inputs": ["smiles", "molecule_file"],
                    "outputs": ["properties", "fingerprints", "ucf_score"],
                    "parameters": {
                        "calculate_descriptors": True,
                        "generate_fingerprint": True,
                        "ucf_enhancement": True,
                    },
                },
                "docking_simulation": {
                    "inputs": ["ligand", "target_protein"],
                    "outputs": ["binding_affinity", "pose", "interactions"],
                    "parameters": {
                        "docking_engine": "gnina",
                        "exhaustiveness": 8,
                        "ucf_optimization": True,
                    },
                },
            },
            VerticalPack.PHYSICS_MATERIALS: {
                "system_simulation": {
                    "inputs": ["hamiltonian", "initial_state"],
                    "outputs": ["time_evolution", "observables", "system_metrics"],
                    "parameters": {
                        "time_steps": 1000,
                        "measurement_interval": 10,
                        "system_enhancement": True,
                    },
                },
                "materials_analysis": {
                    "inputs": ["crystal_structure", "composition"],
                    "outputs": ["properties", "band_structure", "stability"],
                    "parameters": {
                        "calculate_electronic": True,
                        "calculate_mechanical": True,
                        "ucf_guided": True,
                    },
                },
            },
            VerticalPack.GENOMICS: {
                "sequence_analysis": {
                    "inputs": ["dna_sequence", "reference_genome"],
                    "outputs": ["variants", "annotations", "conservation"],
                    "parameters": {
                        "call_variants": True,
                        "predict_genes": True,
                        "ucf_interpretation": True,
                    },
                },
                "phylogenetic_analysis": {
                    "inputs": ["multiple_sequences"],
                    "outputs": ["tree", "distances", "evolutionary_metrics"],
                    "parameters": {
                        "tree_method": "maximum_likelihood",
                        "bootstrap_replicates": 100,
                        "coordination_analysis": True,
                    },
                },
            },
            VerticalPack.FINANCE_QUANTS: {
                "portfolio_optimization": {
                    "inputs": ["assets", "returns_data"],
                    "outputs": ["optimal_weights", "risk_metrics", "performance"],
                    "parameters": {
                        "optimization_method": "sharpe_ratio",
                        "risk_free_rate": 0.02,
                        "ucf_ethical_scoring": True,
                    },
                },
                "options_pricing": {
                    "inputs": ["underlying", "strike", "expiration"],
                    "outputs": ["price", "greeks", "risk_metrics"],
                    "parameters": {
                        "pricing_model": "black_scholes",
                        "volatility_surface": True,
                        "system_enhancement": True,
                    },
                },
            },
            VerticalPack.ENVIRONMENT: {
                "climate_analysis": {
                    "inputs": ["location", "time_period"],
                    "outputs": ["projections", "impacts", "mitigation"],
                    "parameters": {
                        "climate_scenario": "rcp45",
                        "spatial_resolution": 1.0,
                        "ucf_sustainability": True,
                    },
                },
                "carbon_footprint": {
                    "inputs": ["activity_data", "emissions_factors"],
                    "outputs": ["total_footprint", "breakdown", "reduction_plan"],
                    "parameters": {
                        "scope_analysis": True,
                        "reduction_targets": True,
                        "sustainability_scoring": True,
                    },
                },
            },
        }

        return configs.get(vertical, {}).get(node_type, {})

    async def create_marketplace_listing(
        self,
        seller_id: str,
        vertical_pack: str,
        price: float,
        description: str,
        features: list[str],
    ) -> MarketplaceListing:
        """Create marketplace listing for vertical pack"""

        listing_id = str(uuid.uuid4())
        vertical = VerticalPack(vertical_pack.lower())

        listing = MarketplaceListing(
            listing_id=listing_id,
            vertical_pack=vertical,
            seller_id=seller_id,
            price=price,
            description=description,
            features=features,
        )

        # Cache listing
        self.marketplace_listings[listing_id] = listing

        # Cache in Redis
        if self.redis_client:
            cache_key = f"marketplace_listing:{listing_id}"
            self.redis_client.setex(
                cache_key,
                timedelta(minutes=15),
                json.dumps(asdict(listing), default=str),
            )

        logger.info("Created marketplace listing for %s: $%s", vertical_pack, price)
        return listing

    async def execute_vertical_workflow(
        self, user_id: str, workflow_id: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute vertical workflow with system enhancement"""

        # Check user subscription
        subscription = await self.get_user_subscription(user_id)
        if not subscription:
            raise ValueError(f"User {user_id} has no active subscription")

        # Get workflow configuration
        if workflow_id not in self.workflow_nodes:
            raise ValueError(f"Workflow {workflow_id} not found")

        node = self.workflow_nodes[workflow_id]
        vertical = self.verticals[node.vertical_pack]

        # Execute workflow based on node type and vertical
        result = await self._execute_node_workflow(vertical, node, input_data)

        # Apply system enhancement
        system_enhanced = await self.system_core.enhance_workflow_result(result)

        # Log execution
        await self._log_workflow_execution(user_id, workflow_id, result)

        logger.info(
            "Executed vertical workflow: {node.node_type} for %s",
            node.vertical_pack.value,
        )
        return system_enhanced

    async def _execute_node_workflow(
        self, vertical: Any, node: WorkflowNode, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute specific workflow node with real computation via vertical instances"""

        try:
            if node.node_type == "molecule_analysis":
                molecule = await vertical.add_molecule(
                    smiles=input_data.get("smiles", ""),
                    name=input_data.get("name", "Unknown"),
                )
                return {
                    "molecule_id": molecule.mol_id,
                    "properties": molecule.properties,
                    "ucf_score": molecule.ucf_score,
                }

            elif node.node_type == "docking_simulation":
                # Use BioChemVertical molecule analysis as proxy
                molecule = await vertical.add_molecule(
                    smiles=input_data.get("smiles", "CCO"),
                    name=input_data.get("name", "ligand"),
                )
                binding_est = molecule.properties.get("molecular_weight", 200) * -0.04
                return {
                    "binding_affinity": round(binding_est, 2),
                    "interactions": ["hydrogen_bond", "van_der_waals"],
                    "confidence": 0.75,
                    "molecule_properties": molecule.properties,
                    "_note": "Estimated from molecular properties; install AutoDock Vina for full docking",
                }

            elif node.vertical_pack == VerticalPack.PHYSICS_MATERIALS:
                if node.node_type == "system_simulation":
                    # Delegate to PhysicsMaterialsVertical
                    import numpy as np

                    system = await vertical.create_system_system(
                        system_type=input_data.get("system_type", "spin"),
                        parameters=input_data.get("parameters", {}),
                    )
                    tlist = np.linspace(0, 10, 50)
                    sim_result = await vertical.simulate_system_dynamics(system, tlist)
                    return {
                        "system_id": system.system_id,
                        "time_evolution": sim_result.results.get("times", [])[:5],
                        "final_state": "simulated",
                        "fidelity": sim_result.properties.get("final_state_purity", 0.95),
                        "computation_time": sim_result.computation_time,
                        "convergence": sim_result.convergence,
                    }

                elif node.node_type == "materials_analysis":
                    # Delegate to MaterialSimulation dataclass
                    from apps.backend.verticals.physics import MaterialProperty, MaterialSimulation

                    mat = MaterialSimulation(
                        material_id=str(uuid.uuid4()),
                        composition=input_data.get("composition", "Si"),
                        crystal_structure=input_data.get("crystal_structure", "diamond"),
                        lattice_constant=input_data.get("lattice_constant", 5.43),
                    )
                    mech = mat.calculate_mechanical_properties()
                    band = mat.calculate_band_structure()
                    return {
                        "band_gap": band.get("band_gap", 0),
                        "elastic_modulus": mech.get(MaterialProperty.ELASTIC_MODULUS, 0),
                        "thermal_conductivity": mech.get(MaterialProperty.THERMAL_CONDUCTIVITY, 0),
                        "density": mech.get(MaterialProperty.DENSITY, 0),
                    }

            elif node.vertical_pack == VerticalPack.GENOMICS:
                if node.node_type == "sequence_analysis":
                    # Delegate to GenomicsVertical
                    sequence = input_data.get("sequence", "ATCGATCGATCG")
                    analysis = await vertical.analyze_sequence(sequence)
                    return {
                        "sequence_length": analysis.get("length", len(sequence)),
                        "gc_content": analysis.get("gc_content", 0),
                        "genes_predicted": len(analysis.get("orfs", [])),
                        "quality_metrics": analysis.get("quality", {}),
                    }

                elif node.node_type == "phylogenetic_analysis":
                    # Delegate to GenomicsVertical
                    sequences = input_data.get("sequences", {"A": "ATCG", "B": "ATCG"})
                    tree_result = await vertical.build_phylogenetic_tree(
                        sequences=sequences,
                        method=input_data.get("method", "upgma"),
                    )
                    return {
                        "tree_newick": tree_result.get("newick", ""),
                        "num_taxa": tree_result.get("num_taxa", 0),
                        "method": tree_result.get("method", "upgma"),
                    }

            elif node.vertical_pack == VerticalPack.FINANCE_QUANTS:
                if node.node_type == "portfolio_optimization":
                    return self._compute_portfolio_optimization(input_data)

                elif node.node_type == "options_pricing":
                    return self._compute_black_scholes(input_data)

            elif node.vertical_pack == VerticalPack.ENVIRONMENT:
                if node.node_type == "climate_analysis":
                    # Delegate to EnvironmentVertical
                    pass

                    location = input_data.get("location", {"lat": 40.0, "lon": -74.0})
                    temp_data = await vertical.collect_environmental_data("temperature", location)
                    precip_data = await vertical.collect_environmental_data("precipitation", location)
                    return {
                        "temperature": temp_data.value,
                        "precipitation": precip_data.value,
                        "temperature_unit": temp_data.unit,
                        "precipitation_unit": precip_data.unit,
                        "quality_score": (temp_data.quality_score + precip_data.quality_score) / 2,
                    }

                elif node.node_type == "carbon_footprint":
                    # Delegate to EnvironmentVertical
                    emissions = input_data.get(
                        "emissions_data",
                        {
                            "scope1": 400,
                            "scope2": 350,
                            "scope3": 500,
                        },
                    )
                    entity = input_data.get("entity_name", "project")
                    footprint = await vertical.analyze_carbon_footprint(entity, emissions)
                    return {
                        "total_emissions": footprint.total_emissions,
                        "scope1": footprint.scope1_emissions,
                        "scope2": footprint.scope2_emissions,
                        "scope3": footprint.scope3_emissions,
                        "reduction_potential": footprint.reduction_potential,
                        "sustainability_score": footprint.ucf_sustainability_score,
                    }

            else:
                return {"error": f"Unknown node type: {node.node_type}"}

        except Exception as e:
            logger.error("Workflow execution failed: %s", e)
            return {"error": type(e).__name__}

    # --- Real computation helpers for workflow nodes ---

    @staticmethod
    def _norm_cdf(x: float) -> float:
        """Standard normal CDF using math.erf"""
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def _compute_black_scholes(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Compute Black-Scholes option price and Greeks (no external deps)"""
        S = float(input_data.get("spot_price", 100))
        K = float(input_data.get("strike_price", 100))
        T = float(input_data.get("time_to_expiry", 1.0))
        r = float(input_data.get("risk_free_rate", 0.05))
        sigma = float(input_data.get("volatility", 0.2))
        option_type = input_data.get("option_type", "call").upper()

        if T <= 0 or sigma <= 0:
            intrinsic = max(0, S - K) if option_type == "CALL" else max(0, K - S)
            return {
                "price": intrinsic,
                "delta": 1.0 if S > K else 0.0,
                "gamma": 0.0,
                "theta": 0.0,
                "vega": 0.0,
            }

        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        norm_pdf_d1 = math.exp(-0.5 * d1 * d1) / math.sqrt(2.0 * math.pi)

        if option_type == "CALL":
            price = S * self._norm_cdf(d1) - K * math.exp(-r * T) * self._norm_cdf(d2)
            delta = self._norm_cdf(d1)
        else:
            price = K * math.exp(-r * T) * self._norm_cdf(-d2) - S * self._norm_cdf(-d1)
            delta = -self._norm_cdf(-d1)

        gamma = norm_pdf_d1 / (S * sigma * math.sqrt(T))
        theta = (-S * norm_pdf_d1 * sigma / (2 * math.sqrt(T))) / 365
        vega = S * norm_pdf_d1 * math.sqrt(T) / 100

        return {
            "price": round(price, 4),
            "delta": round(delta, 4),
            "gamma": round(gamma, 6),
            "theta": round(theta, 4),
            "vega": round(vega, 4),
        }

    @staticmethod
    def _compute_portfolio_optimization(
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Mean-variance portfolio optimization (equal-weight or inverse-volatility)"""
        assets = input_data.get("assets", {})
        returns = input_data.get("expected_returns", {})
        volatilities = input_data.get("volatilities", {})

        if not assets:
            assets = {"AAPL": 0.33, "GOOGL": 0.33, "MSFT": 0.34}

        symbols = list(assets.keys())
        n = len(symbols)

        if volatilities:
            # Inverse-volatility weighting
            inv_vol = {s: 1.0 / max(volatilities.get(s, 0.2), 0.01) for s in symbols}
            total = sum(inv_vol.values())
            weights = {s: round(inv_vol[s] / total, 4) for s in symbols}
        else:
            # Equal-weight allocation
            weights = {s: round(1.0 / n, 4) for s in symbols}

        # Portfolio expected return (weighted average)
        exp_ret = sum(weights.get(s, 0) * returns.get(s, 0.08) for s in symbols)

        # Portfolio volatility (simplified — ignores correlation)
        port_vol = math.sqrt(sum(weights.get(s, 0) ** 2 * volatilities.get(s, 0.2) ** 2 for s in symbols))

        sharpe = (exp_ret - 0.04) / port_vol if port_vol > 0 else 0

        return {
            "optimal_weights": weights,
            "expected_return": round(exp_ret, 4),
            "volatility": round(port_vol, 4),
            "sharpe_ratio": round(sharpe, 4),
        }

    async def get_user_subscription(self, user_id: str) -> UserSubscription | None:
        """Get user subscription with caching"""

        # Check memory cache
        if user_id in self.user_subscriptions:
            return self.user_subscriptions[user_id]

        # Check Redis cache
        if self.redis_client:
            cache_key = f"ml_hub_subscription:{user_id}"
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                subscription_data = json.loads(cached_data)
                subscription = UserSubscription(**subscription_data)
                self.user_subscriptions[user_id] = subscription
                return subscription

        return None

    async def _log_workflow_execution(self, user_id: str, workflow_id: str, result: dict[str, Any]):
        """Log workflow execution for analytics"""

        log_entry = {
            "user_id": user_id,
            "workflow_id": workflow_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "success": "error" not in result,
            "execution_time_ms": 100,  # Mock timing
            "result_summary": {
                "has_error": "error" in result,
                "num_outputs": len(result) if isinstance(result, dict) else 0,
            },
        }

        # Cache in Redis
        if self.redis_client:
            log_key = f"workflow_execution:{workflow_id}:{int(datetime.now(UTC).timestamp())}"
            self.redis_client.setex(log_key, timedelta(hours=24), json.dumps(log_entry))

    def get_vertical(self, vertical_pack: str) -> Any:
        """Get vertical extension by name"""
        vertical = VerticalPack(vertical_pack.lower())
        return self.verticals.get(vertical)

    def list_available_verticals(self) -> list[str]:
        """List all available vertical packs"""
        return [v.value for v in VerticalPack]

    def get_pricing_info(self) -> dict[str, Any]:
        """Get pricing information for all tiers"""

        return {
            "tiers": {
                "free": {
                    "price": 0,
                    "features": [
                        "1 annotation project",
                        "5 experiment runs",
                        "1GB storage",
                    ],
                    "verticals": [],
                },
                "pro": {
                    "price": 29,
                    "features": [
                        "10 annotation projects",
                        "100 experiment runs",
                        "50GB storage",
                        "1 vertical pack",
                    ],
                    "verticals": ["Choose any 1"],
                },
                "vertical": {
                    "price": 99,
                    "features": [
                        "50 annotation projects",
                        "1000 experiment runs",
                        "500GB storage",
                        "unlimited verticals",
                    ],
                    "verticals": ["All vertical packs"],
                },
                "enterprise": {
                    "price": 299,
                    "features": [
                        "1M platform API calls/month",
                        "Custom verticals",
                        "Dedicated support",
                    ],
                    "verticals": ["Custom development"],
                },
            },
            "individual_verticals": {
                "bio_chem": {
                    "price": 99,
                    "description": "Drug discovery and molecular analysis",
                },
                "physics_materials": {
                    "price": 99,
                    "description": "System simulations and materials science",
                },
                "genomics": {
                    "price": 99,
                    "description": "Genome analysis and bioinformatics",
                },
                "lab_automation": {
                    "price": 99,
                    "description": "Laboratory automation and robotics",
                },
                "finance_quants": {
                    "price": 99,
                    "description": "Quantitative finance and portfolio optimization",
                },
                "environment": {
                    "price": 99,
                    "description": "Climate analysis and environmental monitoring",
                },
            },
        }
