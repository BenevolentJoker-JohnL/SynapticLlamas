#!/usr/bin/env python3
import sys
import os
import json
import argparse
import logging

# Add SOLLOL to path FIRST before any other imports
sollol_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'SOLLOL', 'src')
if sollol_path not in sys.path:
    sys.path.insert(0, sollol_path)

# Now import other modules
from orchestrator import run_parallel_agents
from distributed_orchestrator import DistributedOrchestrator
from node_registry import NodeRegistry
from adaptive_strategy import ExecutionMode
from load_balancer import RoutingStrategy
from dask_executor import DaskDistributedExecutor
from console_theme import (
    console, print_banner, print_section, print_info, print_success,
    print_error, print_warning, print_command, print_status_table,
    print_node_table, print_metrics_table, print_json_output,
    print_divider, print_agent_message, print_mode_switch, create_progress_bar
)
from rich import box
from rich.markdown import Markdown
from rich.panel import Panel

# Import SOLLOL modules
from sollol.rpc_registry import RPCBackendRegistry

# Configure logging to match SOLLOL format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


# Global registries for distributed mode
global_registry = NodeRegistry()  # Ollama nodes for task distribution
global_rpc_registry = RPCBackendRegistry()  # RPC backends for model sharding
global_orchestrator = None
global_dask_executor = None

# Configuration file paths
CONFIG_PATH = os.path.expanduser("~/.synapticllamas.json")
NODES_CONFIG_PATH = os.path.expanduser("~/.synapticllamas_nodes.json")

def load_config():
    """Load persistent configuration from ~/.synapticllamas.json"""
    default_config = {
        "mode": None,  # None = use CLI args, or "standard"/"distributed"/"dask"
        "collaborative_mode": False,
        "refinement_rounds": 1,
        "agent_timeout": 300,
        "ast_voting_enabled": False,
        "quality_threshold": 0.7,
        "max_quality_retries": 2,
        "flockparser_enabled": False,
        "model": "llama3.2",
        "synthesis_model": None,  # Optional larger model for Phase 4 (e.g., "llama3.1:70b")
        "strategy": None,  # None = auto, or ExecutionMode value string

        # Distribution settings - TWO distinct modes:
        "task_distribution_enabled": True,   # Parallel agent execution across Ollama nodes
        "model_sharding_enabled": False,     # RPC-based model distribution (llama.cpp)
        "rpc_backends": []  # List of RPC backend configs for model sharding
    }

    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                saved_config = json.load(f)
                default_config.update(saved_config)
                print(f"📁 Loaded settings from {CONFIG_PATH}")
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")

    return default_config

def save_config(config):
    """Auto-save configuration to ~/.synapticllamas.json"""
    try:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save config: {e}")


def interactive_mode(model="llama3.2", workers=3, distributed=False, use_dask=False, dask_scheduler=None):
    """Interactive CLI mode for continuous queries."""
    global global_orchestrator, global_registry, global_dask_executor

    # Load persistent configuration
    config = load_config()

    # Mutable state for mode switching
    # Use saved mode if available, otherwise use CLI args
    saved_mode = config.get("mode", None)
    if saved_mode:
        current_mode = saved_mode
    else:
        current_mode = "dask" if use_dask else ("distributed" if distributed else "standard")

    # Load strategy from config and convert back to ExecutionMode
    strategy_str = config.get("strategy", None)
    if strategy_str is None:
        current_strategy = None  # Auto
    else:
        # Convert string back to ExecutionMode enum
        try:
            current_strategy = ExecutionMode(strategy_str)
        except ValueError:
            current_strategy = None

    current_model = config.get("model", model)
    synthesis_model = config.get("synthesis_model", None)  # Optional large model for synthesis
    collaborative_mode = config.get("collaborative_mode", False)
    refinement_rounds = config.get("refinement_rounds", 1)
    agent_timeout = config.get("agent_timeout", 300)

    # AST Quality Voting settings
    ast_voting_enabled = config.get("ast_voting_enabled", False)
    quality_threshold = config.get("quality_threshold", 0.7)
    max_quality_retries = config.get("max_quality_retries", 2)

    # FlockParser RAG settings
    flockparser_enabled = config.get("flockparser_enabled", False)

    # Helper to auto-save settings (defined early so it can be used below)
    def update_config(**kwargs):
        nonlocal config
        config.update(kwargs)
        save_config(config)

    # Distribution settings - TWO distinct modes:
    # 1. Task Distribution: Parallel agent execution across Ollama nodes (default ON)
    # 2. Model Sharding: RPC-based model distribution via llama.cpp (default OFF)

    task_distribution_enabled = config.get("task_distribution_enabled", True)

    # Backward compatibility: map old "distributed_inference_enabled" to new name
    if "distributed_inference_enabled" in config:
        model_sharding_enabled = config.get("distributed_inference_enabled", False)
        # Migrate to new name
        update_config(model_sharding_enabled=model_sharding_enabled)
        config.pop("distributed_inference_enabled", None)
    else:
        model_sharding_enabled = config.get("model_sharding_enabled", False)

    rpc_backends = config.get("rpc_backends", [])

    # Filter out localhost from RPC backends (coordinator runs there, no distribution benefit)
    rpc_backends = [
        backend for backend in rpc_backends
        if backend['host'] not in ['127.0.0.1', 'localhost']
    ]
    if len(rpc_backends) != len(config.get("rpc_backends", [])):
        # Save cleaned config
        update_config(rpc_backends=rpc_backends)

    # Load RPC backends into registry for monitoring
    global_rpc_registry.load_from_config(rpc_backends)

    # Auto-discover RPC backends if model sharding is enabled
    if model_sharding_enabled:
        logger.info("🔍 Auto-discovering RPC backends for model sharding...")
        from sollol.rpc_discovery import auto_discover_rpc_backends
        discovered = auto_discover_rpc_backends()
        if discovered:
            # Merge with existing backends (avoid duplicates)
            existing_set = {(b['host'], b['port']) for b in rpc_backends}
            for backend in discovered:
                key = (backend['host'], backend['port'])
                if key not in existing_set:
                    rpc_backends.append(backend)
                    existing_set.add(key)

            update_config(rpc_backends=rpc_backends)
            logger.info(f"✅ RPC backends configured: {len(rpc_backends)} total (for model sharding)")
        else:
            logger.info("ℹ️  No RPC backends found. You can add them manually with: rpc add <host:port>")

    def print_welcome():
        console.clear()
        print_banner()

        if current_mode == "dask":
            mode_str = f"Dask Distributed ({dask_scheduler or 'local cluster'})"
        elif current_mode == "distributed":
            mode_str = "Distributed Load Balanced"
        else:
            mode_str = "Standard (Single Node)"

        console.print(f"\n[bold red]Mode:[/bold red] [cyan]{mode_str}[/cyan]")
        console.print(f"[bold red]Model:[/bold red] [cyan]{current_model}[/cyan]")
        console.print(f"[bold red]Collaboration:[/bold red] [cyan]{'ON' if collaborative_mode else 'OFF'}[/cyan]")
        console.print(f"[bold red]Intelligent Routing:[/bold red] [green]SOLLOL ENABLED ✅[/green]")
        print_divider()

        console.print("\n[bold red]🎮 MODE COMMANDS[/bold red]")
        print_command("mode standard", "Switch to standard mode")
        print_command("mode distributed", "Switch to distributed mode")
        print_command("mode dask", "Switch to Dask mode")

        console.print("\n[bold red]🎯 STRATEGY COMMANDS[/bold red]")
        print_command("strategy auto", "Intelligent auto-selection (RECOMMENDED)")
        print_command("strategy single", "Force single node")
        print_command("strategy parallel", "Force parallel same node")
        print_command("strategy multi", "Force multi-node")
        print_command("strategy gpu", "Force GPU routing")

        console.print("\n[bold red]🤝 COLLABORATION MODE[/bold red]")
        collab_status = "[green]ON[/green]" if collaborative_mode else "[dim]OFF[/dim]"
        synthesis_status = f"[cyan]{synthesis_model}[/cyan]" if synthesis_model else "[dim]None[/dim]"
        print_command(f"collab on/off [{collab_status}]", "Toggle collaborative workflow")
        print_command(f"refine <n> [{refinement_rounds}]", "Set refinement rounds (0-5)")
        print_command(f"timeout <sec> [{agent_timeout}s]", "Set inference timeout")
        print_command(f"synthesis <model> [{synthesis_status}]", "Set large model for Phase 4 synthesis")

        console.print("\n[bold red]🗳️  AST QUALITY VOTING[/bold red]")
        ast_status = "[green]ON[/green]" if ast_voting_enabled else "[dim]OFF[/dim]"
        print_command(f"ast on/off [{ast_status}]", "Toggle quality voting")
        print_command(f"quality <0.0-1.0> [{quality_threshold}]", "Set quality threshold")
        print_command(f"qretries <n> [{max_quality_retries}]", "Set max quality retries")

        console.print("\n[bold red]📚 FLOCKPARSER RAG[/bold red]")
        rag_status = "[green]ON[/green]" if flockparser_enabled else "[dim]OFF[/dim]"
        print_command(f"rag on/off [{rag_status}]", "Toggle PDF RAG enhancement")

        console.print("\n[bold red]⚡ DISTRIBUTION MODES[/bold red]")
        task_status = "Task: " + ("[green]ON[/green]" if task_distribution_enabled else "[dim]OFF[/dim]")
        model_status = "Model: " + ("[green]ON[/green]" if model_sharding_enabled else "[dim]OFF[/dim]")
        console.print(f"[dim white]Current: {task_status}, {model_status}[/dim white]")

        print_command(f"distributed task", "Ollama pool only (parallel agents, small models)")
        print_command(f"distributed model", "RPC sharding only (large models split across servers)")
        print_command(f"distributed both", "🔀 HYBRID: Small→Ollama, Large→RPC")
        print_command(f"distributed off", "Disable all distribution modes")

        console.print(f"\n[cyan]RPC Backend Management:[/cyan]")
        print_command(f"rpc discover", "Auto-discover RPC backends on network")
        print_command(f"rpc add <host:port>", "Add RPC backend (default port: 50052)")
        print_command(f"rpc remove <host:port>", "Remove RPC backend")
        print_command(f"rpc list", f"List RPC backends ({len(rpc_backends)} configured)")

        console.print(f"\n[dim]💡 Task distribution = parallel agents. Model sharding = split large models.[/dim]")

        console.print("\n[bold red]🔧 NODE COMMANDS[/bold red]")
        print_command("nodes", "List Ollama nodes")
        print_command("add <url>", "Add Ollama node")
        print_command("remove <url>", "Remove Ollama node")
        print_command("discover [cidr]", "Scan network or specific CIDR for nodes")
        print_command("health", "Health check all nodes")
        print_command("save/load <file>", "Save/load node config")

        console.print("\n[bold red]📊 INFO COMMANDS[/bold red]")
        print_command("status", "Show current configuration")
        print_command("metrics", "Show last query metrics")
        print_command("sollol", "Show SOLLOL routing stats")
        print_command("dashboard", "Launch SOLLOL web dashboard (port 8080)")
        print_command("benchmark", "Run auto-benchmark")
        if current_mode == "dask":
            print_command("dask", "Show Dask cluster info")

        print_divider()
        console.print("[dim white]Type your query to run agents, or 'exit' to quit[/dim white]\n")

    print_welcome()

    # Auto-load previously discovered nodes
    if os.path.exists(NODES_CONFIG_PATH):
        try:
            global_registry.load_config(NODES_CONFIG_PATH)
            node_count = len(global_registry.nodes)
            if node_count > 0:
                print_success(f"Auto-loaded {node_count} node(s) from previous session")
        except Exception as e:
            logger.warning(f"Failed to auto-load nodes: {e}")

    # Auto-discover Ollama nodes if in distributed mode
    if current_mode == "distributed":
        try:
            from sollol import discover_ollama_nodes
            logger.info("🔍 Auto-discovering known Ollama nodes (using SOLLOL)...")
            initial_count = len(global_registry.nodes)

            # Use SOLLOL's fast discovery (env vars + localhost)
            discovered_nodes = discover_ollama_nodes(
                timeout=1.0,
                exclude_localhost=False,
                auto_resolve_docker=True
            )

            # Add discovered nodes to registry
            for node_info in discovered_nodes:
                url = f"http://{node_info['host']}:{node_info['port']}"
                try:
                    global_registry.add_node(url, auto_probe=True)
                except Exception as e:
                    logger.debug(f"Failed to add {url}: {e}")

            discovered_count = len(global_registry.nodes) - initial_count
            if discovered_count > 0:
                print_success(f"Auto-discovered {discovered_count} additional Ollama node(s)")
                # Save updated node list
                global_registry.save_config(NODES_CONFIG_PATH)

            # Hint to user about network scanning
            if len(global_registry.nodes) <= 1:
                logger.info(f"💡 Only localhost found. Use 'discover' or set OLLAMA_NODES env var for network nodes")

            logger.info(f"✅ Total Ollama nodes available: {len(global_registry.nodes)}")
        except Exception as e:
            logger.warning(f"Ollama node auto-discovery failed: {e}")

    # Initialize based on mode
    def ensure_orchestrator():
        global global_orchestrator, global_dask_executor
        if current_mode == "dask":
            if global_dask_executor is None:
                global_dask_executor = DaskDistributedExecutor(dask_scheduler, global_registry)
            return global_dask_executor, None
        elif current_mode == "distributed":
            if global_orchestrator is None:
                global_orchestrator = DistributedOrchestrator(
                    global_registry,
                    use_flockparser=flockparser_enabled,
                    enable_distributed_inference=model_sharding_enabled,
                    rpc_backends=rpc_backends if model_sharding_enabled else None,
                    task_distribution_enabled=task_distribution_enabled
                )
            return None, global_orchestrator
        else:
            return None, None

    # Don't initialize orchestrator at startup if in distributed mode
    # This allows users to add nodes first via discover/add commands
    # Orchestrator will be created lazily when first needed
    if current_mode != "distributed":
        executor, orchestrator = ensure_orchestrator()
    else:
        executor, orchestrator = None, None

    last_result = None

    while True:
        try:
            # Get user input
            user_input = console.input("[bold red]SynapticLlamas>[/bold red] ").strip()

            if not user_input:
                continue

            # Parse command
            parts = user_input.split(maxsplit=1)
            command = parts[0].lower()

            # Handle exit commands
            if command in ['exit', 'quit', 'q']:
                console.print("\n[cyan]👋 Exiting SynapticLlamas. Goodbye![/cyan]\n")
                if executor:
                    executor.close()
                break

            # Mode switching
            elif command == 'mode':
                if len(parts) < 2:
                    print("❌ Usage: mode [standard|distributed|dask]\n")
                else:
                    new_mode = parts[1].lower()
                    if new_mode == 'standard':
                        current_mode = 'standard'
                        update_config(mode='standard')
                        print("✅ Switched to Standard Mode\n")
                    elif new_mode == 'distributed':
                        current_mode = 'distributed'
                        update_config(mode='distributed')
                        executor, orchestrator = ensure_orchestrator()
                        print("✅ Switched to Distributed Mode\n")
                    elif new_mode == 'dask':
                        current_mode = 'dask'
                        update_config(mode='dask')
                        executor, orchestrator = ensure_orchestrator()
                        print(f"✅ Switched to Dask Mode\n")
                        if executor:
                            print(f"🔗 Dashboard: {executor.client.dashboard_link}\n")
                    else:
                        print("❌ Unknown mode. Use: standard, distributed, or dask\n")

            # Collaboration mode toggle
            elif command == 'collab':
                if len(parts) < 2:
                    print(f"❌ Usage: collab [on|off]\n")
                else:
                    toggle = parts[1].lower()
                    if toggle == 'on':
                        collaborative_mode = True
                        update_config(collaborative_mode=True)
                        print("✅ Collaborative mode ENABLED")
                        print("   Agents will work sequentially with feedback loops\n")
                    elif toggle == 'off':
                        collaborative_mode = False
                        update_config(collaborative_mode=False)
                        print("✅ Collaborative mode DISABLED")
                        print("   Agents will work in parallel independently\n")
                    else:
                        print("❌ Use 'collab on' or 'collab off'\n")

            # Refinement rounds
            elif command == 'refine':
                if len(parts) < 2:
                    print(f"❌ Usage: refine <number>\n")
                else:
                    try:
                        rounds = int(parts[1])
                        if rounds < 0 or rounds > 5:
                            print("❌ Refinement rounds must be between 0 and 5\n")
                        else:
                            refinement_rounds = rounds
                            update_config(refinement_rounds=rounds)
                            print(f"✅ Refinement rounds set to {rounds}\n")
                    except ValueError:
                        print("❌ Please provide a number\n")

            # Synthesis model setting
            elif command == 'synthesis':
                if len(parts) < 2:
                    if synthesis_model:
                        print(f"Current synthesis model: {synthesis_model}")
                        print(f"Usage: synthesis <model_name> (e.g., llama3.1:70b)\n")
                        print(f"       synthesis none (to disable)\n")
                    else:
                        print("No synthesis model set")
                        print(f"Usage: synthesis <model_name> (e.g., llama3.1:70b)\n")
                else:
                    model_name = parts[1]
                    if model_name.lower() == 'none':
                        synthesis_model = None
                        update_config(synthesis_model=None)
                        print("✅ Synthesis model disabled (will use same model for all phases)\n")
                    else:
                        synthesis_model = model_name
                        update_config(synthesis_model=model_name)
                        print(f"✅ Synthesis model set to: {model_name}")
                        print(f"   Phases 1-3: {current_model}")
                        print(f"   Phase 4: {synthesis_model}\n")

            # Timeout setting
            elif command == 'timeout':
                if len(parts) < 2:
                    print(f"❌ Usage: timeout <seconds>\n")
                else:
                    try:
                        timeout_val = int(parts[1])
                        if timeout_val < 30:
                            print("❌ Timeout must be at least 30 seconds\n")
                        else:
                            agent_timeout = timeout_val
                            update_config(agent_timeout=timeout_val)
                            print(f"✅ Inference timeout set to {timeout_val}s\n")
                    except ValueError:
                        print("❌ Please provide a number\n")

            # AST voting toggle
            elif command == 'ast':
                if len(parts) < 2:
                    print(f"❌ Usage: ast [on|off]\n")
                else:
                    toggle = parts[1].lower()
                    if toggle == 'on':
                        ast_voting_enabled = True
                        update_config(ast_voting_enabled=True)
                        print("✅ AST Quality Voting ENABLED")
                        print("   Output will be evaluated by voting agents\n")
                    elif toggle == 'off':
                        ast_voting_enabled = False
                        update_config(ast_voting_enabled=False)
                        print("✅ AST Quality Voting DISABLED\n")
                    else:
                        print("❌ Use 'ast on' or 'ast off'\n")

            # Quality threshold
            elif command == 'quality':
                if len(parts) < 2:
                    print(f"❌ Usage: quality <0.0-1.0>\n")
                else:
                    try:
                        threshold = float(parts[1])
                        if threshold < 0.0 or threshold > 1.0:
                            print("❌ Quality threshold must be between 0.0 and 1.0\n")
                        else:
                            quality_threshold = threshold
                            update_config(quality_threshold=threshold)
                            print(f"✅ Quality threshold set to {threshold:.2f}\n")
                    except ValueError:
                        print("❌ Please provide a number between 0.0 and 1.0\n")

            # Quality retries
            elif command == 'qretries':
                if len(parts) < 2:
                    print(f"❌ Usage: qretries <number>\n")
                else:
                    try:
                        retries = int(parts[1])
                        if retries < 0 or retries > 5:
                            print("❌ Quality retries must be between 0 and 5\n")
                        else:
                            max_quality_retries = retries
                            update_config(max_quality_retries=retries)
                            print(f"✅ Max quality retries set to {retries}\n")
                    except ValueError:
                        print("❌ Please provide a number\n")

            # RAG toggle
            elif command == 'rag':
                if len(parts) < 2:
                    print(f"❌ Usage: rag [on|off]\n")
                else:
                    toggle = parts[1].lower()
                    if toggle == 'on':
                        flockparser_enabled = True
                        update_config(flockparser_enabled=True)
                        # Force re-initialization of orchestrator with new setting
                        global_orchestrator = None
                        print("✅ FlockParser RAG ENABLED")
                        print("   Research queries will be enhanced with PDF context\n")
                    elif toggle == 'off':
                        flockparser_enabled = False
                        update_config(flockparser_enabled=False)
                        # Force re-initialization of orchestrator
                        global_orchestrator = None
                        print("✅ FlockParser RAG DISABLED\n")
                    else:
                        print("❌ Use 'rag on' or 'rag off'\n")

            # Distributed mode selection
            elif command == 'distributed':
                if len(parts) < 2:
                    print(f"❌ Usage: distributed [task|model|both|off]\n")
                    print("   • task  - Task distribution (parallel agents across Ollama nodes)")
                    print("   • model - Model sharding (split large models via RPC backends)")
                    print("   • both  - Enable BOTH modes")
                    print("   • off   - Disable all distribution\n")
                else:
                    mode = parts[1].lower()
                    ollama_nodes_count = len(global_registry.get_healthy_nodes())

                    if mode == 'task':
                        task_distribution_enabled = True
                        model_sharding_enabled = False
                        current_model = "llama3.2"  # Use small model for task distribution
                        synthesis_model = None  # No synthesis model in task-only mode
                        update_config(task_distribution_enabled=True, model_sharding_enabled=False,
                                    model="llama3.2", synthesis_model=None)
                        global_orchestrator = None
                        print("✅ TASK DISTRIBUTION MODE")
                        print(f"   Using {ollama_nodes_count} Ollama nodes for load balancing")
                        print("   Agents execute in parallel across Ollama nodes")
                        print("   Model: llama3.2 (all phases)")
                        print("   Synthesis model: None")
                        print("   Model sharding: DISABLED\n")

                    elif mode == 'model':
                        if len(rpc_backends) == 0:
                            print("⚠️  No RPC backends configured!")
                            print("   Use 'rpc discover' or 'rpc add <host:port>' first\n")
                        else:
                            task_distribution_enabled = False
                            model_sharding_enabled = True
                            current_model = "llama3.1:70b"  # Use large model for sharding
                            synthesis_model = None  # Same model for all phases in sharding-only mode
                            update_config(task_distribution_enabled=False, model_sharding_enabled=True,
                                        model="llama3.1:70b", synthesis_model=None)
                            global_orchestrator = None
                            print("✅ MODEL SHARDING MODE")
                            print(f"   Using {len(rpc_backends)} RPC backend(s)")
                            print("   Model: llama3.1:70b (all phases, sharded via RPC)")
                            print("   Synthesis model: None")
                            print("   Large models (>13B) split via llama.cpp")
                            print("   Task distribution: DISABLED\n")

                    elif mode == 'both':
                        if len(rpc_backends) == 0:
                            print("⚠️  No RPC backends configured for model sharding!")
                            print("   Use 'rpc discover' or 'rpc add <host:port>' first\n")
                        else:
                            task_distribution_enabled = True
                            model_sharding_enabled = True
                            current_model = "llama3.2"  # Small model for phases 1-3
                            synthesis_model = "llama3.1:70b"  # Large model for phase 4
                            update_config(task_distribution_enabled=True, model_sharding_enabled=True,
                                        model="llama3.2", synthesis_model="llama3.1:70b")
                            global_orchestrator = None
                            print("✅ HYBRID MODE (Task Distribution + Model Sharding)")
                            print(f"   Task distribution: {ollama_nodes_count} Ollama nodes")
                            print(f"   Model sharding: {len(rpc_backends)} RPC backends")
                            print(f"   Phases 1-3 model: llama3.2 → Ollama pool (parallel agents)")
                            print(f"   Phase 4 synthesis: llama3.1:70b → RPC sharding")
                            print("   🔀 HybridRouter intelligently routes based on model size")
                            print("   💡 Use 'synthesis <model>' to change synthesis model\n")

                    elif mode == 'off':
                        task_distribution_enabled = False
                        model_sharding_enabled = False
                        update_config(task_distribution_enabled=False, model_sharding_enabled=False)
                        global_orchestrator = None
                        print("❌ ALL DISTRIBUTION DISABLED")
                        print("   Sequential execution only\n")

                    else:
                        print("❌ Unknown mode. Use: distributed [task|model|both|off]\n")

            # RPC backend management
            elif command == 'rpc':
                if len(parts) < 2:
                    print("❌ Usage: rpc [add|remove|list|discover] <host:port>\n")
                else:
                    subcommand = parts[1].lower()
                    if subcommand == 'discover':
                        print("🔍 Scanning network for RPC backends...\n")
                        from sollol.rpc_discovery import auto_discover_rpc_backends
                        discovered = auto_discover_rpc_backends()
                        if discovered:
                            # Add newly discovered backends (avoid duplicates)
                            added_count = 0
                            for backend in discovered:
                                if backend not in rpc_backends:
                                    rpc_backends.append(backend)
                                    added_count += 1
                                    print(f"   ✅ Found: {backend['host']}:{backend['port']}")

                            if added_count > 0:
                                update_config(rpc_backends=rpc_backends)
                                if model_sharding_enabled:
                                    global_orchestrator = None
                                print(f"\n✅ Added {added_count} new RPC backend(s)")
                                print(f"   Total backends: {len(rpc_backends)}\n")
                            else:
                                print("\nℹ️  All discovered backends already configured\n")
                        else:
                            print("❌ No RPC backends found on the network")
                            print("   Make sure RPC servers are running:")
                            print("   rpc-server --host 0.0.0.0 --port 50052 --mem 2048\n")
                    elif subcommand == 'list':
                        if len(rpc_backends) == 0:
                            print("📡 No RPC backends configured\n")
                        else:
                            print(f"📡 Configured RPC Backends ({len(rpc_backends)}):")
                            for backend in rpc_backends:
                                print(f"   • {backend['host']}:{backend['port']}")
                            print()
                    elif subcommand == 'add':
                        if len(parts) < 3:
                            print("❌ Usage: rpc add <host:port>\n")
                        else:
                            backend_str = parts[2]
                            if ':' in backend_str:
                                host, port = backend_str.rsplit(':', 1)
                                port = int(port)
                            else:
                                host = backend_str
                                port = 50052  # Default RPC port

                            backend = {"host": host, "port": port}
                            if backend not in rpc_backends:
                                rpc_backends.append(backend)
                                update_config(rpc_backends=rpc_backends)
                                # Force re-initialization if model sharding is enabled
                                if model_sharding_enabled:
                                    global_orchestrator = None
                                print(f"✅ Added RPC backend: {host}:{port}")
                                print(f"   Total backends: {len(rpc_backends)}\n")
                            else:
                                print(f"⚠️  Backend already configured: {host}:{port}\n")
                    elif subcommand == 'remove':
                        if len(parts) < 3:
                            print("❌ Usage: rpc remove <host:port>\n")
                        else:
                            backend_str = parts[2]
                            if ':' in backend_str:
                                host, port = backend_str.rsplit(':', 1)
                                port = int(port)
                            else:
                                host = backend_str
                                port = 50052

                            backend = {"host": host, "port": port}
                            if backend in rpc_backends:
                                rpc_backends.remove(backend)
                                update_config(rpc_backends=rpc_backends)
                                # Force re-initialization if model sharding is enabled
                                if model_sharding_enabled:
                                    global_orchestrator = None
                                print(f"✅ Removed RPC backend: {host}:{port}")
                                print(f"   Total backends: {len(rpc_backends)}\n")

                                # Warn if model sharding is enabled with no backends
                                if model_sharding_enabled and len(rpc_backends) == 0:
                                    print("⚠️  No RPC backends remaining! Model sharding will fail.\n")
                            else:
                                print(f"❌ Backend not found: {host}:{port}\n")
                    else:
                        print("❌ Unknown subcommand. Use: rpc [discover|add|remove|list]\n")

            # Strategy selection
            elif command == 'strategy':
                if len(parts) < 2:
                    print("❌ Usage: strategy [auto|single|parallel|multi|gpu]\n")
                else:
                    strat = parts[1].lower()
                    if strat == 'auto':
                        current_strategy = None
                        update_config(strategy=None)
                        print("✅ Strategy: Auto (adaptive)\n")
                    elif strat == 'single':
                        current_strategy = ExecutionMode.SINGLE_NODE
                        update_config(strategy=current_strategy.value)
                        print("✅ Strategy: Single Node (sequential)\n")
                    elif strat == 'parallel':
                        current_strategy = ExecutionMode.PARALLEL_SAME_NODE
                        update_config(strategy=current_strategy.value)
                        print("✅ Strategy: Parallel Same Node\n")
                    elif strat == 'multi':
                        current_strategy = ExecutionMode.PARALLEL_MULTI_NODE
                        update_config(strategy=current_strategy.value)
                        print("✅ Strategy: Parallel Multi-Node\n")
                    elif strat == 'gpu':
                        current_strategy = ExecutionMode.GPU_ROUTING
                        update_config(strategy=current_strategy.value)
                        print("✅ Strategy: GPU Routing\n")
                    else:
                        print("❌ Unknown strategy\n")

            # Status command
            elif command == 'status':
                status_data = {
                    "Mode": current_mode,
                    "Model": current_model,
                    "Synthesis Model": synthesis_model if synthesis_model else 'None (same as model)',
                    "Strategy": current_strategy.value if current_strategy else 'auto',
                    "Collaboration": 'ON' if collaborative_mode else 'OFF',
                    "Refinement Rounds": refinement_rounds if collaborative_mode else 'N/A',
                    "Ollama Nodes": len(global_registry),
                    "Healthy Nodes": len(global_registry.get_healthy_nodes()),
                    "GPU Nodes": len(global_registry.get_gpu_nodes()),
                    "Task Distribution": 'ON' if task_distribution_enabled else 'OFF',
                    "Model Sharding": 'ON' if model_sharding_enabled else 'OFF',
                    "RPC Backends": len(rpc_backends) if model_sharding_enabled else 'N/A'
                }
                if current_mode == 'dask' and executor:
                    status_data["Dask Workers"] = len(executor.client.scheduler_info()['workers'])

                print_status_table(status_data)

            # Benchmark command
            elif command == 'benchmark':
                if current_mode != 'distributed':
                    print("❌ Benchmarking only available in distributed mode\n")
                else:
                    print("🔬 Running auto-benchmark...\n")
                    if orchestrator:
                        from agents.researcher import Researcher
                        from agents.critic import Critic
                        from agents.editor import Editor
                        test_agents = [Researcher(current_model), Critic(current_model), Editor(current_model)]
                        orchestrator.adaptive_selector.run_auto_benchmark(
                            test_agents=test_agents,
                            test_input="Benchmark test: explain quantum computing",
                            iterations=2
                        )

            # Dashboard command
            elif command == 'dashboard':
                # Ensure the orchestrator is live before launching the dashboard
                if current_mode == 'distributed' and orchestrator is None:
                    _, orchestrator = ensure_orchestrator()
                    print_info("Orchestrator initialized for dashboard monitoring.")

                print("🚀 Launching SOLLOL Dashboard on http://localhost:8080")
                print("   Running in background thread...\n")
                import threading
                import sys

                # Get the current registry and load balancer
                current_registry = global_registry
                current_lb = None
                current_hybrid_router = None

                if orchestrator and hasattr(orchestrator, 'load_balancer'):
                    current_lb = orchestrator.load_balancer

                # Get hybrid router if available
                if orchestrator and hasattr(orchestrator, 'hybrid_router'):
                    current_hybrid_router = orchestrator.hybrid_router
                    logger.info("📡 Dashboard will monitor llama.cpp backend")

                def run_dashboard_thread():
                    # Use NEW SOLLOL UnifiedDashboard with universal observability
                    from sollol import UnifiedDashboard, DashboardClient
                    import time

                    # Create SOLLOL UnifiedDashboard with NEW features
                    dashboard = UnifiedDashboard(
                        router=current_hybrid_router,
                        ray_dashboard_port=8265,
                        dask_dashboard_port=8787,
                        dashboard_port=8080,
                        enable_dask=True,  # Enable Dask dashboard
                    )

                    logging.info("📊 Using NEW SOLLOL UnifiedDashboard with:")
                    logging.info("   • Universal network observability")
                    logging.info("   • Application tracking")
                    logging.info("   • Ray dashboard (port 8265)")
                    logging.info("   • Dask dashboard (port 8787)")
                    logging.info("   • WebSocket event streams")

                    # Start dashboard in background thread
                    import threading
                    server_thread = threading.Thread(
                        target=lambda: dashboard.run(host='0.0.0.0', debug=False),
                        daemon=True
                    )
                    server_thread.start()

                    # Wait for server to start, then register
                    time.sleep(2)

                    # NOW register SynapticLlamas with the dashboard (after server is ready)
                    logging.info("📱 Registering SynapticLlamas with dashboard...")
                    client = DashboardClient(
                        app_name="SynapticLlamas",
                        router_type="RayHybridRouter",
                        version="1.0.0",
                        dashboard_url="http://localhost:8080",
                        metadata={"nodes": len(current_registry) if current_registry else 0},
                        auto_register=True
                    )
                    logging.info(f"✅ Registered with dashboard: SynapticLlamas ({client.app_id})")

                    # Keep thread alive (server_thread is daemon, so it will die when main thread dies)
                    while True:
                        time.sleep(60)

                dashboard_thread = threading.Thread(target=run_dashboard_thread, daemon=True, name="DashboardServer")
                dashboard_thread.start()

                import time
                time.sleep(2)  # Give server time to start

                logging.info("📊 NEW SOLLOL Dashboard features enabled!")

                print("✅ Dashboard started in background!")
                print(f"   Tracking {len(current_registry)} nodes from your session")
                print("   Open http://localhost:8080 in your browser")
                print("   Dashboard will auto-shutdown when you exit SynapticLlamas\n")

            # Handle metrics
            elif command == 'metrics':
                if last_result:
                    print(f"\n{'=' * 70}")
                    print(" PERFORMANCE METRICS")
                    print(f"{'=' * 70}")
                    print(json.dumps(last_result['metrics'], indent=2))
                    if 'strategy_used' in last_result:
                        print(f"\nStrategy: {last_result['strategy_used']['mode'].value}")
                    print(f"{'=' * 70}\n")
                else:
                    print("❌ No results yet. Run a query first.\n")

            # Dask-specific commands
            elif use_dask and command == 'dask':
                if executor:
                    info = executor.client.scheduler_info()
                    print(f"\n{'=' * 70}")
                    print(" DASK CLUSTER INFO")
                    print(f"{'=' * 70}")
                    print(f"Dashboard: {executor.client.dashboard_link}")
                    print(f"Workers: {len(info['workers'])}")
                    print(f"Scheduler: {executor.client.scheduler.address}")
                    print(f"\nWorkers:")
                    for worker_id, worker_info in info['workers'].items():
                        print(f"  {worker_id}")
                        print(f"    Host: {worker_info.get('host', 'unknown')}")
                        print(f"    Cores: {worker_info.get('nthreads', 'unknown')}")
                    print(f"{'=' * 70}\n")
                else:
                    print("❌ Dask executor not initialized\n")

            # Node management commands
            elif command == 'nodes':
                # Show Ollama nodes (for task distribution)
                nodes_list = list(global_registry.nodes.values())
                if nodes_list:
                    print("🔀 OLLAMA NODES (Task Distribution - Parallel Agents)")
                    print_node_table([n.to_dict() for n in nodes_list])
                    # Also show current metrics for debugging
                    print("\n📊 Current Metrics:")
                    for node in nodes_list:
                        print(f"  {node.url}:")
                        print(f"    Total requests: {node.metrics.total_requests}")
                        print(f"    Avg latency: {node.metrics.avg_latency:.0f}ms")
                        print(f"    Load score: {node.calculate_load_score():.1f}")
                    print()
                else:
                    print("🔀 OLLAMA NODES (Task Distribution - Parallel Agents)")
                    print_warning("No Ollama nodes registered\n")

                # Show RPC backends (for model sharding)
                print("\n🔗 RPC BACKENDS (Model Sharding - Large Models)")
                rpc_backends_list = list(global_rpc_registry.backends.values())
                if rpc_backends_list:
                    from rich.table import Table
                    table = Table(box=box.ROUNDED)
                    table.add_column("Address", style="cyan")
                    table.add_column("Status", style="green")
                    table.add_column("Requests", justify="right")
                    table.add_column("Success Rate", justify="right")
                    table.add_column("Avg Latency", justify="right")

                    for backend in rpc_backends_list:
                        status = "✅ HEALTHY" if backend.is_healthy else "❌ OFFLINE"
                        status_style = "green" if backend.is_healthy else "red"

                        table.add_row(
                            backend.address,
                            f"[{status_style}]{status}[/{status_style}]",
                            str(backend.metrics.total_requests),
                            f"{backend.metrics.success_rate * 100:.1f}%",
                            f"{backend.metrics.avg_latency:.0f}ms"
                        )

                    console.print(table)
                    print()
                else:
                    print_warning("No RPC backends configured\n")
                    print("   Use 'rpc discover' or 'rpc add <host:port>' to add backends\n")

            elif command == 'add':
                if len(parts) < 2:
                    print("❌ Usage: add <url>\n")
                else:
                    url = parts[1]
                    try:
                        node = global_registry.add_node(url)
                        print(f"✅ Added node: {node.name}\n")

                        # Auto-save after adding node
                        try:
                            global_registry.save_config(NODES_CONFIG_PATH)
                            logger.info(f"Auto-saved {len(global_registry.nodes)} nodes to {NODES_CONFIG_PATH}")
                        except Exception as e:
                            logger.warning(f"Failed to auto-save nodes: {e}")
                    except Exception as e:
                        print(f"❌ Failed to add node: {e}\n")

            elif command == 'remove':
                if len(parts) < 2:
                    print("❌ Usage: remove <url>\n")
                else:
                    url = parts[1]
                    if global_registry.remove_node(url):
                        print(f"✅ Removed node: {url}\n")

                        # Auto-save after removing node
                        try:
                            global_registry.save_config(NODES_CONFIG_PATH)
                            logger.info(f"Auto-saved {len(global_registry.nodes)} nodes to {NODES_CONFIG_PATH}")
                        except Exception as e:
                            logger.warning(f"Failed to auto-save nodes: {e}")
                    else:
                        print(f"❌ Node not found: {url}\n")

            elif command == 'discover':
                if len(parts) > 1:
                    # User specified CIDR - use network scanning
                    cidr = parts[1]
                    print(f"📡 Scanning {cidr}...\n")
                    discovered = global_registry.discover_nodes(cidr)
                    print(f"✅ Discovered {len(discovered)} nodes\n")

                    # Auto-save discovered nodes
                    if len(discovered) > 0:
                        try:
                            global_registry.save_config(NODES_CONFIG_PATH)
                            logger.info(f"Auto-saved {len(global_registry.nodes)} nodes to {NODES_CONFIG_PATH}")
                        except Exception as e:
                            logger.warning(f"Failed to auto-save nodes: {e}")
                else:
                    # Auto-detect and scan local network
                    from network_utils import suggest_scan_ranges
                    print(f"🔍 Detecting network and scanning for Ollama nodes...\n")

                    ranges = suggest_scan_ranges()
                    if not ranges:
                        print("❌ Could not auto-detect network. Please specify CIDR manually.")
                        print("   Usage: discover 10.9.66.0/24\n")
                        continue

                    print(f"📡 Detected network ranges:")
                    for r in ranges:
                        print(f"   • {r}")
                    print()

                    # Scan all ranges
                    initial_count = len(global_registry.nodes)
                    total_discovered = []
                    for r in ranges:
                        print(f"Scanning {r}...")
                        discovered = global_registry.discover_nodes(r, timeout=1.0, max_workers=100)
                        total_discovered.extend(discovered)

                    discovered_count = len(global_registry.nodes) - initial_count
                    print(f"\n✅ Discovered {discovered_count} new node(s)\n")

                    # Auto-save discovered nodes
                    if discovered_count > 0:
                        try:
                            global_registry.save_config(NODES_CONFIG_PATH)
                            logger.info(f"Auto-saved {len(global_registry.nodes)} nodes to {NODES_CONFIG_PATH}")
                        except Exception as e:
                            logger.warning(f"Failed to auto-save nodes: {e}")

            elif command == 'health':
                print("🏥 Running health checks...\n")
                # Use faster timeouts with auto-removal of failed nodes
                results = global_registry.health_check_all(
                    timeout=2.0,
                    connection_timeout=1.0,
                    auto_remove=True,
                    max_failures=3
                )
                healthy = sum(1 for v in results.values() if v)
                print(f"✅ {healthy}/{len(results)} nodes healthy\n")

            elif command == 'save':
                if len(parts) < 2:
                    print("❌ Usage: save <filepath>\n")
                else:
                    global_registry.save_config(parts[1])
                    print(f"✅ Saved config to {parts[1]}\n")

            elif command == 'load':
                if len(parts) < 2:
                    print("❌ Usage: load <filepath>\n")
                else:
                    global_registry.load_config(parts[1])
                    print(f"✅ Loaded config from {parts[1]}\n")

            # Process query
            else:
                # Auto-detect if this needs long-form generation
                from content_detector import detect_content_type, ContentType
                content_type, estimated_chunks, metadata = detect_content_type(user_input)
                use_longform = metadata.get('requires_multi_turn', False)

                # Storytelling always uses longform, not collaborative
                # Override collaborative mode for storytelling
                use_collaborative = collaborative_mode
                if content_type == ContentType.STORYTELLING:
                    use_longform = True
                    use_collaborative = False  # Disable collaborative for stories

                if use_longform:
                    print(f"\n📚 Detected long-form {content_type.value} (est. {estimated_chunks} parts)...\n")
                elif use_collaborative:
                    print(f"\n🤝 Processing with collaborative workflow...\n")
                else:
                    print(f"\n⚡ Processing...\n")

                if current_mode == 'dask':
                    if not executor:
                        executor, _ = ensure_orchestrator()
                    result = executor.run(user_input, model=current_model)
                elif current_mode == 'distributed':
                    if not orchestrator:
                        _, orchestrator = ensure_orchestrator()

                    # Use long-form generation if detected
                    if use_longform:
                        result = orchestrator.run_longform(
                            user_input,
                            model=current_model,
                            auto_detect=True,
                            max_chunks=5
                        )
                    else:
                        result = orchestrator.run(
                            user_input,
                            model=current_model,
                            execution_mode=current_strategy,
                            collaborative=use_collaborative,
                            refinement_rounds=refinement_rounds,
                            timeout=agent_timeout,
                            enable_ast_voting=ast_voting_enabled,
                            quality_threshold=quality_threshold,
                            max_quality_retries=max_quality_retries,
                            synthesis_model=synthesis_model
                        )
                else:
                    # Standard mode doesn't support collaborative yet
                    if use_collaborative:
                        print("⚠️  Collaborative mode requires distributed mode")
                        print("   Switching to distributed mode...\n")
                        current_mode = 'distributed'
                        executor, orchestrator = ensure_orchestrator()
                        result = orchestrator.run(
                            user_input,
                            model=current_model,
                            execution_mode=current_strategy,
                            collaborative=use_collaborative,
                            refinement_rounds=refinement_rounds,
                            timeout=agent_timeout,
                            enable_ast_voting=ast_voting_enabled,
                            quality_threshold=quality_threshold,
                            max_quality_retries=max_quality_retries,
                            synthesis_model=synthesis_model
                        )
                    else:
                        result = run_parallel_agents(user_input, model=current_model, max_workers=workers)

                last_result = result

                # Display results
                console.print()

                # Display final markdown output
                markdown_output = result['result'].get('final_output', '')
                if isinstance(markdown_output, str) and markdown_output:
                    console.print(Panel(
                        Markdown(markdown_output),
                        title="[bold red]FINAL ANSWER[/bold red]",
                        border_style="red",
                        box=box.DOUBLE
                    ))
                else:
                    # Fallback to JSON if no markdown
                    print_json_output(result['result'])

                # Show execution summary
                print_divider()
                print_success(f"Completed in {result['metrics']['total_execution_time']:.2f}s")

                # Show phase timings (collaborative mode)
                if 'phase_timings' in result['metrics']:
                    console.print("\n[cyan]⏱️  Phase Timings:[/cyan]")
                    for phase_name, phase_time in result['metrics']['phase_timings']:
                        console.print(f"  [red]{phase_name}[/red] [cyan]→ {phase_time:.2f}s[/cyan]")

                # Show quality scores (AST voting)
                if 'quality_scores' in result['metrics'] and result['metrics']['quality_scores']:
                    quality_passed = result['metrics'].get('quality_passed', True)
                    status_icon = "✅" if quality_passed else "⚠️"
                    status_color = "green" if quality_passed else "yellow"

                    console.print(f"\n[cyan]🗳️  Quality Voting:[/cyan] [{status_color}]{status_icon}[/{status_color}]")
                    for score_data in result['metrics']['quality_scores']:
                        agent_name = score_data['agent']
                        score_val = score_data['score']
                        reasoning = score_data['reasoning']
                        console.print(f"  [red]{agent_name}[/red]: [cyan]{score_val:.2f}/1.0[/cyan] - [dim]{reasoning}[/dim]")
                        if score_data.get('issues'):
                            for issue in score_data['issues']:
                                console.print(f"    [yellow]⚠[/yellow] [dim]{issue}[/dim]")

                # Show node attribution
                if 'node_attribution' in result['metrics']:
                    console.print("\n[cyan]🖥️  Node Attribution:[/cyan]")
                    for node_attr in result['metrics']['node_attribution']:
                        agent_name = node_attr['agent']
                        node_url = node_attr['node']
                        exec_time = node_attr.get('time', 0)
                        if exec_time > 0:
                            console.print(f"  [red]{agent_name}[/red] → [dim]{node_url}[/dim] [cyan]({exec_time:.2f}s)[/cyan]")
                        else:
                            console.print(f"  [red]{agent_name}[/red] → [dim]{node_url}[/dim]")

                # Show RAG sources if available
                if 'metadata' in result and result['metadata'].get('rag_enabled'):
                    rag_sources = result['metadata'].get('rag_sources', [])
                    if rag_sources:
                        console.print("\n[cyan]📚 RAG Sources:[/cyan]")
                        for source in rag_sources:
                            console.print(f"  [dim]•[/dim] [green]{source}[/green]")

                if 'strategy_used' in result:
                    mode_val = result['strategy_used'].get('mode')
                    if hasattr(mode_val, 'value'):
                        console.print(f"\n[cyan]📊 Strategy:[/cyan] [red]{mode_val.value}[/red]")
                    elif isinstance(mode_val, str):
                        console.print(f"\n[cyan]📊 Mode:[/cyan] [red]{mode_val}[/red]")
                if 'dask_info' in result:
                    console.print(f"[cyan]🔧 Dask workers:[/cyan] [red]{result['dask_info']['workers']}[/red]")
                    console.print(f"[cyan]🔗 Dashboard:[/cyan] [dim]{result['dask_info']['dashboard']}[/dim]")
                console.print("[dim]Type 'metrics' for detailed performance data[/dim]\n")

        except KeyboardInterrupt:
            print("\n\n👋 Exiting SynapticLlamas. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")
            import traceback
            traceback.print_exc()


def single_query_mode(input_data, model, workers, show_metrics):
    """Single query mode for one-time execution."""
    print(f"\n🧠 SynapticLlamas - Parallel Agent Orchestration")
    print(f"{'=' * 70}")
    print(f"Model: {model}")
    print(f"Input: {input_data}")
    print(f"{'=' * 70}\n")

    # Run parallel agents
    result = run_parallel_agents(input_data, model=model, max_workers=workers)

    # Display JSON results
    print(f"\n{'=' * 70}")
    print(" JSON OUTPUT")
    print(f"{'=' * 70}")
    print(json.dumps(result['result'], indent=2))
    print(f"{'=' * 70}\n")

    # Display metrics if requested
    if show_metrics:
        print(f"\n{'=' * 70}")
        print(" PERFORMANCE METRICS")
        print(f"{'=' * 70}")
        print(json.dumps(result['metrics'], indent=2))
        print(f"{'=' * 70}\n")


def main():
    parser = argparse.ArgumentParser(description='SynapticLlamas - Distributed Parallel Agent Playground')
    parser.add_argument('--input', '-i', type=str, help='Input text to process (omit for interactive mode)')
    parser.add_argument('--model', '-m', type=str, default='llama3.2', help='Ollama model to use')
    parser.add_argument('--workers', '-w', type=int, default=3, help='Max parallel workers')
    parser.add_argument('--metrics', action='store_true', help='Show performance metrics')
    parser.add_argument('--interactive', action='store_true', help='Start in interactive mode')
    parser.add_argument('--distributed', '-d', action='store_true', help='Enable distributed mode with load balancing')
    parser.add_argument('--dask', action='store_true', help='Use Dask for distributed processing')
    parser.add_argument('--dask-scheduler', type=str, help='Dask scheduler address (e.g., tcp://192.168.1.50:8786)')
    parser.add_argument('--add-node', type=str, help='Add a node URL before starting')
    parser.add_argument('--discover', type=str, help='Discover nodes on network (CIDR notation)')
    parser.add_argument('--load-config', type=str, help='Load node configuration from file')
    parser.add_argument('--enable-distributed-inference', action='store_true', help='Enable llama.cpp distributed inference')
    parser.add_argument('--rpc-backend', type=str, action='append', help='Add RPC backend (host:port), can be used multiple times')

    args = parser.parse_args()

    # Force reload of modules to ensure latest definitions are used
    import importlib
    import ollama_node
    import node_registry
    importlib.reload(ollama_node)
    importlib.reload(node_registry)

    # Pre-setup for distributed/dask mode
    if args.distributed or args.dask:
        if args.add_node:
            try:
                global_registry.add_node(args.add_node)
                print(f"✅ Added node: {args.add_node}")
            except Exception as e:
                print(f"❌ Failed to add node: {e}")

        if args.discover:
            print(f"🔍 Discovering nodes on {args.discover}...")
            discovered = global_registry.discover_nodes(args.discover)
            print(f"✅ Discovered {len(discovered)} nodes")

        if args.load_config:
            global_registry.load_config(args.load_config)
            print(f"✅ Loaded config from {args.load_config}")

        # Handle distributed inference setup from CLI (backward compatibility)
        if args.enable_distributed_inference:
            config = load_config()
            config['model_sharding_enabled'] = True

            # Add RPC backends from CLI
            if args.rpc_backend:
                rpc_backends = []
                for backend_str in args.rpc_backend:
                    if ':' in backend_str:
                        host, port = backend_str.rsplit(':', 1)
                        port = int(port)
                    else:
                        host = backend_str
                        port = 50052
                    rpc_backends.append({"host": host, "port": port})

                config['rpc_backends'] = rpc_backends
                print(f"🔗 Configured {len(rpc_backends)} RPC backend(s) for distributed inference")

            save_config(config)

    # Interactive mode
    if args.interactive or not args.input:
        interactive_mode(
            model=args.model,
            workers=args.workers,
            distributed=args.distributed,
            use_dask=args.dask,
            dask_scheduler=args.dask_scheduler
        )
    else:
        # Single query mode
        single_query_mode(args.input, args.model, args.workers, args.metrics)


if __name__ == "__main__":
    main()
