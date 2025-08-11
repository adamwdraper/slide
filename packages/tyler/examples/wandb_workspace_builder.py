#!/usr/bin/env python3
"""
Focused example: Building a W&B workspace for ML experiment analysis.

This example demonstrates how to use Tyler with W&B workspace tools to:
- Analyze existing ML experiment runs
- Create custom visualizations
- Build and save professional workspace dashboards

Use case: You have multiple ML experiments running and want to create
a dashboard to compare their performance and track key metrics.
"""

from dotenv import load_dotenv
load_dotenv()

import os
import asyncio
import weave
from tyler import Agent, Thread, Message
from tyler.utils.logging import get_logger

# Import specific W&B tools we'll use
from lye.wandb_workspaces import (
    get_project_runs,
    create_line_plot, 
    create_scalar_chart,
    create_workspace,
    save_workspace_view
)

logger = get_logger(__name__)

# Initialize weave for tracking
try:
    if os.getenv("WANDB_API_KEY"):
        weave.init("tyler-wandb-builder")
except Exception as e:
    logger.warning(f"Weave initialization failed: {e}")

def create_experiment_analysis_agent():
    """Create an agent specialized for ML experiment analysis."""
    
    # Custom tool for analyzing run performance
    def analyze_run_performance(runs_data: str, metric: str = "accuracy") -> str:
        """Analyze performance trends in ML runs."""
        try:
            import json
            runs = json.loads(runs_data)
            
            if not runs or len(runs) == 0:
                return "No runs data provided for analysis"
            
            # Extract performance metrics
            performance_summary = []
            best_run = None
            best_value = -float('inf')
            
            for run in runs:
                summary = run.get('summary', {})
                if metric in summary:
                    value = summary[metric]
                    performance_summary.append({
                        'run_name': run.get('name', 'Unknown'),
                        'run_id': run.get('id', 'Unknown'),
                        metric: value,
                        'state': run.get('state', 'Unknown')
                    })
                    
                    if value > best_value:
                        best_value = value
                        best_run = run
            
            # Create analysis summary
            if performance_summary:
                avg_performance = sum(r[metric] for r in performance_summary) / len(performance_summary)
                analysis = f"""
Performance Analysis for {metric}:
- Total runs analyzed: {len(performance_summary)}
- Average {metric}: {avg_performance:.4f}
- Best {metric}: {best_value:.4f} (Run: {best_run.get('name', 'Unknown')})
- Completed runs: {sum(1 for r in performance_summary if r['state'] == 'finished')}

Top 3 performing runs:"""
                
                sorted_runs = sorted(performance_summary, key=lambda x: x[metric], reverse=True)[:3]
                for i, run in enumerate(sorted_runs, 1):
                    analysis += f"\n{i}. {run['run_name']}: {run[metric]:.4f}"
                
                return analysis
            else:
                return f"No runs found with {metric} metric"
                
        except Exception as e:
            return f"Error analyzing runs: {str(e)}"
    
    # Define the custom analysis tool
    analysis_tool = {
        "definition": {
            "type": "function",
            "function": {
                "name": "analyze_run_performance",
                "description": "Analyze ML experiment run performance and identify top performers",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "runs_data": {
                            "type": "string",  
                            "description": "JSON string of runs data from W&B"
                        },
                        "metric": {
                            "type": "string",
                            "description": "Metric to analyze (e.g., 'accuracy', 'loss', 'f1_score')",
                            "default": "accuracy"
                        }
                    },
                    "required": ["runs_data"]
                }
            }
        },
        "implementation": analyze_run_performance
    }
    
    return Agent(
        name="ml_experiment_analyst",
        model_name="gpt-4o",
        purpose="""Expert ML experiment analyst who helps researchers understand their model performance, 
        create insightful visualizations, and build professional W&B workspace dashboards for experiment tracking.""",
        tools=[
            # W&B workspace tools
            get_project_runs,
            create_line_plot,
            create_scalar_chart, 
            create_workspace,
            save_workspace_view,
            # Custom analysis tool
            analysis_tool
        ]
    )

async def build_experiment_dashboard():
    """Build a comprehensive experiment dashboard."""
    
    print("🔬 ML Experiment Dashboard Builder")
    print("=" * 40)
    
    agent = create_experiment_analysis_agent()
    thread = Thread()
    
    # Configuration - replace with your actual W&B project
    entity = "your-wandb-entity"  # Replace with your W&B username/team
    project = "your-ml-project"   # Replace with your project name
    
    print(f"📊 Building dashboard for project: {entity}/{project}")
    print("⚠️  Note: Replace entity/project variables with your actual W&B project details")
    print()
    
    # Step 1: Analyze existing experiments
    analysis_request = f"""
    I need to build a comprehensive ML experiment dashboard. Here's what I want you to do:
    
    1. Get the latest 15 runs from W&B project '{entity}/{project}'
    2. Analyze the performance focusing on accuracy and loss metrics
    3. Identify the top 3 performing models
    4. Tell me what patterns you see in the successful experiments
    """
    
    print("🔍 Step 1: Analyzing experiment runs...")
    await run_conversation_step(agent, thread, analysis_request)
    
    # Step 2: Create visualizations
    visualization_request = """
    Now create the following visualizations for our dashboard:
    
    1. A line plot showing training accuracy vs validation accuracy over epochs
    2. A line plot showing training loss vs validation loss over steps  
    3. A scalar chart comparing final accuracy across all runs
    4. A scalar chart showing training time for each run
    
    Make sure each visualization has a descriptive title.
    """
    
    print("📈 Step 2: Creating visualizations...")
    await run_conversation_step(agent, thread, visualization_request)
    
    # Step 3: Build the workspace
    workspace_request = f"""
    Create a professional W&B workspace called 'ML Experiment Dashboard' for entity '{entity}' and project '{project}' with these sections:
    
    1. 'Model Performance' section:
       - Include the accuracy comparison scalar chart
       - Include the line plot for training vs validation accuracy
    
    2. 'Training Dynamics' section:
       - Include the loss comparison line plot  
       - Include the training time scalar chart
    
    3. 'Experiment Overview' section:
       - Add any summary metrics or insights
    
    Make each section informative and well-organized.
    """
    
    print("🏗️  Step 3: Building workspace...")
    await run_conversation_step(agent, thread, workspace_request)
    
    # Step 4: Save workspace view
    save_request = """
    Save this workspace as a view called 'Quarterly Model Review' with the description:
    'Comprehensive analysis of ML experiments for Q4 review - includes performance metrics, training dynamics, and top model identification'
    """
    
    print("💾 Step 4: Saving workspace view...")
    await run_conversation_step(agent, thread, save_request)
    
    print("✅ Dashboard build complete!")
    print()
    print("🎯 Your W&B workspace dashboard includes:")
    print("   • Performance analysis of your latest experiments")
    print("   • Interactive visualizations for key metrics") 
    print("   • Professional layout with organized sections")
    print("   • Saved view for future reference")

async def run_conversation_step(agent, thread, user_message):
    """Helper function to run a conversation step and display results."""
    
    message = Message(role="user", content=user_message)
    thread.add_message(message)
    
    try:
        result = await agent.go(thread)
        
        # Display the agent's response
        for msg in result.messages:
            if msg.role == "assistant":
                content = msg.content or ""
                if len(content) > 500:
                    content = content[:500] + "... [truncated]"
                print(f"🤖 {content}")
            elif msg.role == "tool":
                # Show tool usage without full output
                tool_result = msg.content
                success = "✅" if '"success": true' in tool_result else "❌"
                print(f"🔧 {msg.name}: {success}")
        
        print()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print()

async def quick_workspace_demo():
    """Quick demo showing workspace creation without requiring existing runs."""
    
    print("⚡ Quick W&B Workspace Demo")
    print("=" * 30)
    
    agent = create_experiment_analysis_agent()
    thread = Thread()
    
    demo_request = """
    Create a demo ML experiment workspace to show the capabilities:
    
    1. Create a line plot for 'epoch' vs ['train_accuracy', 'val_accuracy'] titled 'Model Accuracy Over Time'
    2. Create a scalar chart for 'final_f1_score' titled 'Final F1 Score Comparison'  
    3. Build a workspace called 'Demo ML Dashboard' for entity 'demo-user' and project 'demo-project' with:
       - 'Accuracy Trends' section with the line plot
       - 'Performance Summary' section with the scalar chart
    4. Explain what each visualization would show in a real experiment
    """
    
    await run_conversation_step(agent, thread, demo_request)
    
    print("✅ Demo complete! This shows how you can build workspaces even before running experiments.")

if __name__ == "__main__":
    try:
        print("🚀 W&B Workspace Builder with Tyler")
        print("=" * 50)
        
        if not os.getenv("WANDB_API_KEY"):
            print("⚠️  WANDB_API_KEY not set - running in demo mode")
            print("   For full functionality, get your API key from: https://wandb.ai/authorize")
            print()
            
            # Run quick demo instead
            asyncio.run(quick_workspace_demo())
        else:
            print("🔑 WANDB_API_KEY found - running full demo")
            print("📝 Remember to update the entity/project variables in the code")
            print()
            
            # Run full dashboard builder
            asyncio.run(build_experiment_dashboard())
            
    except KeyboardInterrupt:
        print("\n👋 Exiting gracefully...")
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"❌ Error: {e}")