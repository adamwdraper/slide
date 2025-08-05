#!/usr/bin/env python3
"""
Research Assistant Example - Basic

A comprehensive research assistant using Tyler, Lye, and Narrator.
This demonstrates integration of all three Slide packages.
"""

from dotenv import load_dotenv
load_dotenv()

import asyncio
import os
from datetime import datetime
from typing import List, Dict, Any

# Import from all three packages
from tyler import Agent, Thread, Message, ThreadStore, FileStore
from lye import WEB_TOOLS, FILES_TOOLS, IMAGE_TOOLS


class ResearchAssistant:
    """A comprehensive research assistant that can gather, analyze, and report on topics."""
    
    def __init__(self, save_reports: bool = True):
        self.save_reports = save_reports
        self.agent = None
        self.thread_store = None
        self.file_store = None
        self.research_history = []
    
    async def setup(self):
        """Initialize the research assistant with storage and tools."""
        
        # Set up storage using Narrator
        self.thread_store = await ThreadStore.create("sqlite+aiosqlite:///research.db")
        self.file_store = await FileStore.create(base_path="./research_files")
        
        # Create agent using Tyler with Lye tools
        self.agent = Agent(
            name="research-assistant",
            model_name="gpt-4o",
            purpose="""You are an expert research assistant capable of:
            - Finding reliable information from multiple sources
            - Analyzing and synthesizing complex topics
            - Creating well-structured reports
            - Fact-checking and verifying information
            - Identifying key insights and trends
            """,
            tools=[*WEB_TOOLS, *FILES_TOOLS, *IMAGE_TOOLS],
            thread_store=self.thread_store,
            file_store=self.file_store
        )
        
        print("✅ Research Assistant initialized!")
    
    async def research_topic(
        self, 
        topic: str, 
        questions: List[str] = None,
        depth: str = "standard"  # quick, standard, comprehensive
    ) -> Dict[str, Any]:
        """Research a topic with optional specific questions."""
        
        print(f"\n🔍 Starting research on: {topic}")
        print(f"📊 Depth level: {depth}")
        
        # Create research thread
        thread_id = f"research-{topic.lower().replace(' ', '-')}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        thread = Thread(id=thread_id)
        
        # Build research prompt
        research_prompt = self._build_research_prompt(topic, questions, depth)
        thread.add_message(Message(role="user", content=research_prompt))
        
        # Execute research
        print("\n⏳ Researching... This may take a few minutes.")
        start_time = datetime.now()
        
        processed_thread, new_messages = await self.agent.go(thread)
        
        # Save thread using Narrator
        await self.thread_store.save_thread(processed_thread)
        
        # Extract results
        research_results = {
            "topic": topic,
            "thread_id": thread_id,
            "timestamp": datetime.now().isoformat(),
            "duration": (datetime.now() - start_time).total_seconds(),
            "depth": depth,
            "questions": questions or [],
            "findings": self._extract_findings(new_messages),
            "sources": self._extract_sources(new_messages),
            "report_path": None
        }
        
        # Save report if enabled
        if self.save_reports:
            report_path = await self._save_report(research_results)
            research_results["report_path"] = report_path
            print(f"\n💾 Report saved to: {report_path}")
        
        # Add to history
        self.research_history.append(research_results)
        
        print(f"\n✅ Research completed in {research_results['duration']:.1f} seconds!")
        
        return research_results
    
    def _build_research_prompt(self, topic: str, questions: List[str], depth: str) -> str:
        """Build a detailed research prompt based on parameters."""
        
        depth_instructions = {
            "quick": "Provide a brief overview with key points (5-10 minutes of research)",
            "standard": "Conduct thorough research with multiple sources (15-30 minutes)",
            "comprehensive": "Deep dive with extensive analysis and cross-referencing (30+ minutes)"
        }
        
        prompt = f"""Please conduct {depth} research on: {topic}

{depth_instructions[depth]}

Requirements:
1. Search for recent and authoritative information
2. Use multiple sources to verify facts
3. Identify key insights and trends
4. Note any controversies or differing viewpoints
5. Provide specific examples and data when available
"""
        
        if questions:
            prompt += "\n\nSpecific questions to address:\n"
            for i, question in enumerate(questions, 1):
                prompt += f"{i}. {question}\n"
        
        prompt += """
        
Format your research as a comprehensive report with:
- Executive Summary
- Key Findings
- Detailed Analysis
- Sources and References
- Recommendations (if applicable)

Save the complete report as 'research_report.md' when finished.
"""
        
        return prompt
    
    def _extract_findings(self, messages: List[Message]) -> List[str]:
        """Extract key findings from research messages."""
        findings = []
        
        for msg in messages:
            if msg.role == "assistant" and any(keyword in msg.content.lower() 
                for keyword in ["finding", "discovered", "learned", "insight"]):
                # Extract bullet points or key sentences
                lines = msg.content.split('\n')
                for line in lines:
                    if line.strip().startswith(('-', '•', '*')) or 'finding' in line.lower():
                        findings.append(line.strip())
        
        return findings[:10]  # Top 10 findings
    
    def _extract_sources(self, messages: List[Message]) -> List[str]:
        """Extract sources used in research."""
        sources = []
        
        for msg in messages:
            if msg.role == "tool" and "search" in msg.name.lower():
                # Extract URLs or source info from search results
                sources.append(f"Tool: {msg.name}")
        
        return sources
    
    async def _save_report(self, research_results: Dict[str, Any]) -> str:
        """Save research results as a formatted report."""
        
        # Generate report filename
        safe_topic = research_results["topic"].replace(" ", "_").replace("/", "-")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"research_{safe_topic}_{timestamp}.md"
        
        # Format report content
        report = f"""# Research Report: {research_results['topic']}

**Generated:** {research_results['timestamp']}
**Research Depth:** {research_results['depth']}
**Duration:** {research_results['duration']:.1f} seconds

## Executive Summary

This report presents comprehensive research findings on "{research_results['topic']}".

## Key Findings

"""
        
        for finding in research_results['findings']:
            report += f"- {finding}\n"
        
        if research_results['questions']:
            report += "\n## Specific Questions Addressed\n\n"
            for question in research_results['questions']:
                report += f"### {question}\n\n[Answer would be extracted from full research]\n\n"
        
        report += "\n## Sources\n\n"
        for source in research_results['sources']:
            report += f"- {source}\n"
        
        # Save report using Narrator's FileStore
        await self.file_store.save_file(filename, report.encode())
        
        return filename


async def main():
    """Example usage of the research assistant."""
    
    # Initialize research assistant
    assistant = ResearchAssistant(save_reports=True)
    await assistant.setup()
    
    # Example 1: Basic research
    print("\n=== Example 1: Basic Research ===")
    results = await assistant.research_topic(
        "Artificial Intelligence in Healthcare",
        depth="standard"
    )
    
    print("\nKey Findings:")
    for finding in results['findings'][:3]:
        print(f"- {finding}")
    
    # Example 2: Research with specific questions
    print("\n=== Example 2: Targeted Research ===")
    questions = [
        "What are the latest breakthroughs in quantum computing?",
        "Which companies are leading in quantum research?",
        "What are the main challenges facing quantum computing?"
    ]
    
    quantum_research = await assistant.research_topic(
        "Quantum Computing 2024",
        questions=questions,
        depth="quick"
    )
    
    print(f"\nResearch completed! Report saved to: {quantum_research['report_path']}")
    
    # Show research history
    history = assistant.research_history
    print(f"\n📚 Total research sessions: {len(history)}")
    print("Topics researched:")
    for item in history:
        print(f"  - {item['topic']} ({item['depth']})")


if __name__ == "__main__":
    print("🔬 Slide Research Assistant")
    print("=" * 40)
    print("This example demonstrates integration of Tyler, Lye, and Narrator")
    print("to create a comprehensive research assistant.\n")
    
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye! 👋")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nTroubleshooting:")
        print("- Make sure you've run 'uv sync --dev' from the project root")
        print("- Check that your API key is set correctly")
        raise