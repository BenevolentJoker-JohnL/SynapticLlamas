#!/usr/bin/env python3
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
import json
import argparse
import sys


# Global registry for distributed mode
global_registry = NodeRegistry()
global_orchestrator = None
global_dask_executor = None


def interactive_mode(model="llama3.2", workers=3, distributed=False, use_dask=False, dask_scheduler=None):
    """Interactive CLI mode for continuous queries."""
    global global_orchestrator, global_registry, global_dask_executor

    # Mutable state for mode switching
    current_mode = "dask" if use_dask else ("distributed" if distributed else "standard")
    current_strategy = None  # Let adaptive selector choose
    current_model = model
    collaborative_mode = False  # Collaborative workflow toggle
    refinement_rounds = 1  # Number of refinement iterations
    agent_timeout = 300  # Default 5 minutes for CPU inference

    # AST Quality Voting settings
    ast_voting_enabled = False
    quality_threshold = 0.7  # 0.0 to 1.0
    max_quality_retries = 2

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
        print_command(f"collab on/off [{collab_status}]", "Toggle collaborative workflow")
        print_command(f"refine <n> [{refinement_rounds}]", "Set refinement rounds (0-5)")
        print_command(f"timeout <sec> [{agent_timeout}s]", "Set inference timeout")

        console.print("\n[bold red]🗳️  AST QUALITY VOTING[/bold red]")
        ast_status = "[green]ON[/green]" if ast_voting_enabled else "[dim]OFF[/dim]"
        print_command(f"ast on/off [{ast_status}]", "Toggle quality voting")
        print_command(f"quality <0.0-1.0> [{quality_threshold}]", "Set quality threshold")
        print_command(f"qretries <n> [{max_quality_retries}]", "Set max quality retries")

        console.print("\n[bold red]🔧 NODE COMMANDS[/bold red]")
        print_command("nodes", "List Ollama nodes")
        print_command("add <url>", "Add Ollama node")
        print_command("remove <url>", "Remove Ollama node")
        print_command("discover [cidr]", "Auto-detect and scan network")
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

    # Initialize based on mode
    def ensure_orchestrator():
        global global_orchestrator, global_dask_executor
        if current_mode == "dask":
            if global_dask_executor is None:
                global_dask_executor = DaskDistributedExecutor(dask_scheduler, global_registry)
            return global_dask_executor, None
        elif current_mode == "distributed":
            if global_orchestrator is None:
                global_orchestrator = DistributedOrchestrator(global_registry)
            return None, global_orchestrator
        else:
            return None, None

    executor, orchestrator = ensure_orchestrator()

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
                        print("✅ Switched to Standard Mode\n")
                    elif new_mode == 'distributed':
                        current_mode = 'distributed'
                        executor, orchestrator = ensure_orchestrator()
                        print("✅ Switched to Distributed Mode\n")
                    elif new_mode == 'dask':
                        current_mode = 'dask'
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
                        print("✅ Collaborative mode ENABLED")
                        print("   Agents will work sequentially with feedback loops\n")
                    elif toggle == 'off':
                        collaborative_mode = False
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
                            print(f"✅ Refinement rounds set to {rounds}\n")
                    except ValueError:
                        print("❌ Please provide a number\n")

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
                        print("✅ AST Quality Voting ENABLED")
                        print("   Output will be evaluated by voting agents\n")
                    elif toggle == 'off':
                        ast_voting_enabled = False
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
                            print(f"✅ Max quality retries set to {retries}\n")
                    except ValueError:
                        print("❌ Please provide a number\n")

            # Strategy selection
            elif command == 'strategy':
                if len(parts) < 2:
                    print("❌ Usage: strategy [auto|single|parallel|multi|gpu]\n")
                else:
                    strat = parts[1].lower()
                    if strat == 'auto':
                        current_strategy = None
                        print("✅ Strategy: Auto (adaptive)\n")
                    elif strat == 'single':
                        current_strategy = ExecutionMode.SINGLE_NODE
                        print("✅ Strategy: Single Node (sequential)\n")
                    elif strat == 'parallel':
                        current_strategy = ExecutionMode.PARALLEL_SAME_NODE
                        print("✅ Strategy: Parallel Same Node\n")
                    elif strat == 'multi':
                        current_strategy = ExecutionMode.PARALLEL_MULTI_NODE
                        print("✅ Strategy: Parallel Multi-Node\n")
                    elif strat == 'gpu':
                        current_strategy = ExecutionMode.GPU_ROUTING
                        print("✅ Strategy: GPU Routing\n")
                    else:
                        print("❌ Unknown strategy\n")

            # Status command
            elif command == 'status':
                status_data = {
                    "Mode": current_mode,
                    "Model": current_model,
                    "Strategy": current_strategy.value if current_strategy else 'auto',
                    "Collaboration": 'ON' if collaborative_mode else 'OFF',
                    "Refinement Rounds": refinement_rounds if collaborative_mode else 'N/A',
                    "Ollama Nodes": len(global_registry),
                    "Healthy Nodes": len(global_registry.get_healthy_nodes()),
                    "GPU Nodes": len(global_registry.get_gpu_nodes())
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
                print("🚀 Launching SOLLOL Dashboard on http://localhost:8080")
                print("   Running in background thread...\n")
                import threading
                import sys
                import os

                # Suppress Flask/Waitress logs
                import logging as log
                log.getLogger('werkzeug').setLevel(log.ERROR)
                log.getLogger('waitress').setLevel(log.ERROR)

                def run_dashboard_thread():
                    # Import here to avoid circular imports
                    sys.path.insert(0, os.getcwd())
                    from dashboard_server import run_dashboard
                    run_dashboard(host='0.0.0.0', port=8080, production=True)

                dashboard_thread = threading.Thread(target=run_dashboard_thread, daemon=True, name="DashboardServer")
                dashboard_thread.start()

                import time
                time.sleep(1)  # Give server time to start

                print("✅ Dashboard started in background!")
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
                nodes_list = list(global_registry.nodes.values())
                if nodes_list:
                    print_node_table([n.to_dict() for n in nodes_list])
                else:
                    print_warning("No nodes registered")

            elif command == 'add':
                if len(parts) < 2:
                    print("❌ Usage: add <url>\n")
                else:
                    url = parts[1]
                    try:
                        node = global_registry.add_node(url)
                        print(f"✅ Added node: {node.name}\n")
                    except Exception as e:
                        print(f"❌ Failed to add node: {e}\n")

            elif command == 'remove':
                if len(parts) < 2:
                    print("❌ Usage: remove <url>\n")
                else:
                    url = parts[1]
                    if global_registry.remove_node(url):
                        print(f"✅ Removed node: {url}\n")
                    else:
                        print(f"❌ Node not found: {url}\n")

            elif command == 'discover':
                if len(parts) > 1:
                    # User specified CIDR
                    cidr = parts[1]
                else:
                    # Auto-detect network
                    from network_utils import detect_local_network, suggest_scan_ranges

                    ranges = suggest_scan_ranges()

                    if ranges:
                        print(f"🔍 Auto-detected network ranges:")
                        for i, r in enumerate(ranges, 1):
                            print(f"  {i}. {r}")

                        if len(ranges) == 1:
                            cidr = ranges[0]
                            print(f"\n📡 Scanning {cidr}...\n")
                        else:
                            print(f"\n📡 Scanning all detected ranges...\n")
                            # Scan all ranges
                            total_discovered = []
                            for r in ranges:
                                discovered = global_registry.discover_nodes(r)
                                total_discovered.extend(discovered)
                            print(f"✅ Discovered {len(total_discovered)} nodes total\n")
                            continue
                    else:
                        print("❌ Could not auto-detect network. Please specify CIDR manually.")
                        print("   Usage: discover 192.168.1.0/24\n")
                        continue

                discovered = global_registry.discover_nodes(cidr)
                print(f"✅ Discovered {len(discovered)} nodes\n")

            elif command == 'health':
                print("🏥 Running health checks...\n")
                results = global_registry.health_check_all()
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
                if collaborative_mode:
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
                    result = orchestrator.run(
                        user_input,
                        model=current_model,
                        execution_mode=current_strategy,
                        collaborative=collaborative_mode,
                        refinement_rounds=refinement_rounds,
                        timeout=agent_timeout,
                        enable_ast_voting=ast_voting_enabled,
                        quality_threshold=quality_threshold,
                        max_quality_retries=max_quality_retries
                    )
                else:
                    # Standard mode doesn't support collaborative yet
                    if collaborative_mode:
                        print("⚠️  Collaborative mode requires distributed mode")
                        print("   Switching to distributed mode...\n")
                        current_mode = 'distributed'
                        executor, orchestrator = ensure_orchestrator()
                        result = orchestrator.run(
                            user_input,
                            model=current_model,
                            execution_mode=current_strategy,
                            collaborative=collaborative_mode,
                            refinement_rounds=refinement_rounds,
                            timeout=agent_timeout,
                            enable_ast_voting=ast_voting_enabled,
                            quality_threshold=quality_threshold,
                            max_quality_retries=max_quality_retries
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

    args = parser.parse_args()

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
